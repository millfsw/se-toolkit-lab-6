#!/usr/bin/env python3
"""CLI agent for LLM-based task execution."""

import os
import sys
import json
import httpx
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from both files
load_dotenv(".env.agent.secret")
load_dotenv(".env.docker.secret")

MAX_ITERATIONS = 20


def list_files(path: str = ".") -> str:
    """List files and directories in the given path."""
    if ".." in path:
        return "Error: Access denied - path traversal not allowed"
    try:
        entries = os.listdir(path)
        result = []
        for entry in sorted(entries):
            full_path = os.path.join(path, entry)
            prefix = "[DIR]" if os.path.isdir(full_path) else "[FILE]"
            result.append(f"{prefix} {entry}")
        return "\n".join(result)
    except Exception as e:
        return f"Error: {e}"


def read_file(path: str) -> str:
    """Read the content of a file."""
    if ".." in path:
        return "Error: Access denied - path traversal not allowed"
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error: {e}"


def query_api(method: str, path: str, body: dict | None = None, use_auth: bool = True) -> str:
    """Query the LMS API using httpx.
    
    Args:
        method: HTTP method (GET, POST, PUT, DELETE)
        path: API endpoint path
        body: Optional JSON body for POST/PUT requests
        use_auth: Whether to include authentication header (default: True)
    """
    api_key = os.getenv("LMS_API_KEY")
    base_url = os.getenv("AGENT_API_BASE_URL", "http://localhost:42002").rstrip("/")

    clean_path = path.lstrip("/")
    # Only add trailing slash if it's a simple path without query params
    if not clean_path.endswith("/") and "?" not in clean_path:
        clean_path += "/"

    url = f"{base_url}/{clean_path}"

    # Use Bearer token authentication as expected by the backend
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    if use_auth and api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        with httpx.Client() as client:
            resp = client.request(
                method,
                url,
                json=body if body else None,
                headers=headers,
                timeout=15.0
            )

            return json.dumps({
                "status_code": resp.status_code,
                "body": resp.text,
                "headers": dict(resp.headers)
            })
    except Exception as e:
        return json.dumps({"error": str(e)})


tools_schema = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files in a directory",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read file content",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_api",
            "description": "Call the backend API. Use use_auth=false to test unauthenticated requests.",
            "parameters": {
                "type": "object",
                "properties": {
                    "method": {
                        "type": "string",
                        "enum": ["GET", "POST", "PUT", "DELETE"]
                    },
                    "path": {"type": "string"},
                    "body": {"type": "object"},
                    "use_auth": {
                        "type": "boolean",
                        "description": "Whether to include authentication header (default: true)"
                    }
                },
                "required": ["method", "path"]
            }
        }
    }
]


def main():
    if len(sys.argv) < 2:
        print("Usage: python agent.py <question>", file=sys.stderr)
        sys.exit(1)

    question = sys.argv[1]

    # Initialize LLM client
    client = OpenAI(
        api_key=os.getenv("LLM_API_KEY"),
        base_url=os.getenv("LLM_API_BASE")
    )

    system_prompt = (
        "You are an agent that uses tools to answer questions.\n\n"
        "Rules:\n"
        "1. Always use tools first - don't answer from memory\n"
        "2. For wiki questions, look in wiki/ directory\n"
        "3. For backend questions, look in backend/ directory\n"
        "4. For API questions, use query_api with the correct endpoint\n"
        "5. If an API returns an error, read the source code file mentioned in the traceback to understand the bug\n"
        "6. When you find a bug in code, identify the specific error type (e.g., ZeroDivisionError, TypeError)\n"
        "7. To test unauthenticated requests, use query_api with use_auth=false\n"
        "8. Always set the 'source' field to the file you read to find the answer\n"
        "9. When you have the answer, respond without tool calls\n\n"
        "API Endpoints:\n"
        "- /items/ - Get all items (returns a list)\n"
        "- /analytics/scores?lab=lab-XX - Get score distribution\n"
        "- /analytics/completion-rate?lab=lab-XX - Get completion rate\n"
        "- /analytics/top-learners?lab=lab-XX - Get top learners\n"
        "- /analytics/pass-rates?lab=lab-XX - Get pass rates\n"
        "- /analytics/timeline?lab=lab-XX - Get timeline\n"
        "- /analytics/groups?lab=lab-XX - Get groups\n"
        "- /learners/ - Get all learners\n"
        "- /interactions/ - Get all interactions\n"
        "- /pipeline/ - Pipeline status\n\n"
        "Important paths:\n"
        "- Wiki: wiki/\n"
        "- Backend routers: backend/app/routers/\n"
        "- Main app: backend/app/\n"
        "- Analytics router: backend/app/routers/analytics.py\n"
        "- ETL pipeline: backend/app/routers/pipeline.py\n"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question}
    ]

    history_tool_calls = []
    last_read_file_source = None

    for iteration in range(MAX_ITERATIONS):
        if iteration == 0:
            response = client.chat.completions.create(
                model=os.getenv("LLM_MODEL"),
                messages=messages,
                tools=tools_schema,
                tool_choice="required"
            )
        else:
            response = client.chat.completions.create(
                model=os.getenv("LLM_MODEL"),
                messages=messages,
                tools=tools_schema
            )

        msg = response.choices[0].message

        if msg.tool_calls:
            messages.append({
                "role": "assistant",
                "content": "",
                "tool_calls": msg.tool_calls
            })
        else:
            messages.append({
                "role": "assistant",
                "content": msg.content or ""
            })

        if not msg.tool_calls:
            output = {
                "answer": msg.content or "",
                "source": last_read_file_source,
                "tool_calls": history_tool_calls
            }
            print(json.dumps(output))
            return

        for tc in msg.tool_calls:
            name = tc.function.name
            args_str = tc.function.arguments

            try:
                args = json.loads(args_str)
            except json.JSONDecodeError:
                continue

            if name == "list_files":
                result = list_files(**args)
            elif name == "read_file":
                result = read_file(**args)
                last_read_file_source = args.get("path")
            elif name == "query_api":
                result = query_api(**args)
            else:
                result = json.dumps({"error": f"Unknown tool: {name}"})

            history_tool_calls.append({
                "tool": name,
                "args": args,
                "result": result
            })

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "name": name,
                "content": result
            })

    output = {
        "answer": "Error: Max iterations reached",
        "source": last_read_file_source,
        "tool_calls": history_tool_calls
    }
    print(json.dumps(output))


if __name__ == "__main__":
    main()
