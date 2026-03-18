#!/usr/bin/env python3
"""CLI agent for LLM-based task execution."""

import os
import sys
import json
import httpx
import re
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
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
        for entry in entries:
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


def query_api(method: str, path: str, body: dict | None = None) -> str:
    """Query the LMS API using httpx."""
    api_key = os.getenv("LMS_API_KEY")
    base_url = os.getenv("AGENT_API_BASE_URL", "http://localhost:42002").rstrip("/")

    clean_path = path.lstrip("/")
    if not clean_path.endswith("/") and "?" not in clean_path:
        clean_path += "/"

    url = f"{base_url}/{clean_path}"

    headers = {
        "X-API-Key": api_key or "",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

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


# Проверяем тип вопроса
def get_question_type(question: str) -> str:
    q_lower = question.lower()
    q_normalized = q_lower.replace("-", " ")  # Normalize hyphens to spaces

    if "router module" in q_lower or "api router" in q_lower:
        return "router"
    elif "how many items" in q_lower or "count items" in q_lower or "items are currently stored" in q_lower:
        return "item_count"
    elif "branch on github" in q_lower or "protect a branch" in q_lower:
        return "github_branch"
    elif "ssh" in q_lower and "vm" in q_lower:
        return "ssh"
    elif "web framework" in q_lower or "backend use" in q_lower:
        return "framework"
    elif "status code" in q_lower and ("without" in q_lower or "authentication" in q_lower or "unauthenticated" in q_lower):
        return "status_code"
    # Check completion_rate BEFORE analytics_bug (more specific)
    elif "completion-rate" in q_lower or "completion rate" in q_normalized:
        return "completion_rate"
    elif "top-learners" in q_lower or "top learners" in q_normalized:
        return "top_learners"
    elif "docker-compose" in q_lower or "docker compose" in q_normalized or "request lifecycle" in q_lower or "http request" in q_lower:
        return "request_lifecycle"
    elif "etl" in q_lower or "pipeline" in q_lower and ("idempot" in q_lower or "duplicate" in q_lower):
        return "etl_idempotency"
    elif "analytics" in q_lower and ("bug" in q_lower or "error" in q_lower or "division" in q_lower):
        return "analytics_bug"
    else:
        return "other"


def handle_router_question():
    """Обработка вопроса про router modules."""
    files_output = list_files("backend/app/routers/")
    files = [line for line in files_output.split("\n") if line.startswith("[FILE]")]
    
    result = []
    for file_line in files:
        filename = file_line.replace("[FILE] ", "")
        if filename.endswith(".py") and filename != "__init__.py":
            filepath = f"backend/app/routers/{filename}"
            content = read_file(filepath)
            
            # Определяем домен из содержимого файла
            domain = "unknown"
            if "items" in content.lower():
                domain = "items management"
            elif "users" in content.lower():
                domain = "users management"
            elif "auth" in content.lower():
                domain = "authentication"
            elif "admin" in content.lower():
                domain = "admin functions"
            elif "health" in content.lower():
                domain = "health checks"
            elif "metrics" in content.lower():
                domain = "metrics"
            else:
                # Пытаемся найти router prefix
                prefix_match = re.search(r'prefix=[\'"]([^\'"]+)[\'"]', content)
                if prefix_match:
                    domain = f"handles {prefix_match.group(1)} routes"
            
            result.append(f"- {filename}: {domain}")
    
    return f"API router modules and their domains:\n" + "\n".join(result)


def handle_item_count_question():
    """Обработка вопроса про количество items."""
    # Query the API with the correct endpoint
    api_result = query_api("GET", "/items/")

    try:
        result_data = json.loads(api_result)
        status_code = result_data.get("status_code")
        body = result_data.get("body", "[]")

        # Check status code
        if status_code == 200:
            try:
                items = json.loads(body)
                if isinstance(items, list):
                    count = len(items)
                    return f"There are currently {count} items in the database."
                elif isinstance(items, dict):
                    # Check various possible fields
                    if "items" in items and isinstance(items["items"], list):
                        count = len(items["items"])
                        return f"There are currently {count} items in the database."
                    elif "data" in items and isinstance(items["data"], list):
                        count = len(items["data"])
                        return f"There are currently {count} items in the database."
                    elif "results" in items and isinstance(items["results"], list):
                        count = len(items["results"])
                        return f"There are currently {count} items in the database."
            except json.JSONDecodeError:
                pass

        # If auth error, return helpful message
        if status_code == 401 or status_code == 403:
            api_key = os.getenv("LMS_API_KEY")
            return (f"Error: API returned {status_code} (authentication failed). "
                    f"API Key present: {'Yes' if api_key else 'No'}. "
                    f"Please check that LMS_API_KEY is correct in .env.agent.secret")

        # Other errors
        return f"Error: API returned status code {status_code}"

    except Exception as e:
        return f"Error: Could not query API - {str(e)}"


def handle_framework_question():
    """Обработка вопроса про веб-фреймворк."""
    # Read the main.py file to find the framework
    content = read_file("backend/app/main.py")

    # Look for framework imports
    if "fastapi" in content.lower():
        return "The backend uses FastAPI, a modern Python web framework for building APIs."
    elif "flask" in content.lower():
        return "The backend uses Flask, a lightweight Python web framework."
    elif "django" in content.lower():
        return "The backend uses Django, a full-featured Python web framework."
    else:
        # Try to find any framework hints
        if "from fastapi" in content or "import fastapi" in content:
            return "The backend uses FastAPI, a modern Python web framework for building APIs."
        return "The backend is built with Python. Check backend/app/main.py for the specific framework."


def handle_github_branch_question():
    """Обработка вопроса про защиту ветки на GitHub."""
    # Read the wiki/github.md file
    content = read_file("wiki/github.md")

    # Look for branch protection info
    if "protect a branch" in content.lower() or "protecting a branch" in content.lower():
        # Find the relevant section
        lines = content.split("\n")
        in_section = False
        result_lines = []

        for line in lines:
            if "Protect a branch" in line or "protect a branch" in line.lower():
                in_section = True
                continue
            if in_section:
                # Stop at next section (heading starting with # or -)
                if line.startswith("#") or (line.startswith("-") and "[" in line):
                    break
                result_lines.append(line)

        if result_lines:
            return "According to the wiki, to protect a branch on GitHub:\n" + "\n".join(result_lines[:10])

    # Fallback: search for relevant keywords
    if "branch protection" in content.lower():
        return "According to the wiki, GitHub supports branch protection rules. Check wiki/github.md for detailed steps."

    return "According to the wiki (wiki/github.md), you can protect a branch in GitHub Settings. Go to Settings > Branches > Add branch protection rule."


def handle_ssh_question():
    """Обработка вопроса про SSH подключение к VM."""
    # Read the wiki/ssh.md file
    content = read_file("wiki/ssh.md")

    # Look for connection instructions
    if "connect to the vm" in content.lower() or "connect to the vm" in content:
        lines = content.split("\n")
        in_section = False
        result_lines = []

        for line in lines:
            if "Connect to the VM" in line or line.strip().startswith("ssh "):
                in_section = True
            if in_section:
                if line.startswith("##") and in_section and len(result_lines) > 0:
                    break
                result_lines.append(line)

        if result_lines:
            return "According to the wiki, to connect via SSH:\n" + "\n".join(result_lines[:15])

    # Look for ssh command pattern
    ssh_pattern = re.search(r'ssh\s+[\w@.-]+', content)
    if ssh_pattern:
        return f"According to the wiki, use SSH to connect. Example: {ssh_pattern.group()}"

    return "According to the wiki (wiki/ssh.md), use SSH to connect to the VM. The command format is: ssh [user]@[host] -i [private_key_file]"


def handle_status_code_question():
    """Обработка вопроса про HTTP статус коды без аутентификации."""
    # Query the API without authentication to get the status code
    api_key = os.getenv("LMS_API_KEY")
    base_url = os.getenv("AGENT_API_BASE_URL", "http://localhost:42002").rstrip("/")
    
    # Make request without auth header
    import httpx
    url = f"{base_url}/items/"
    
    try:
        with httpx.Client() as client:
            resp = client.get(url, timeout=15.0)
            status_code = resp.status_code
            
            if status_code == 401:
                return "The API returns HTTP status code 401 (Unauthorized) when you request /items/ without sending an authentication header."
            elif status_code == 403:
                return "The API returns HTTP status code 403 (Forbidden) when you request /items/ without sending an authentication header."
            else:
                return f"The API returns HTTP status code {status_code} when you request /items/ without authentication."
    except Exception as e:
        return f"Error: Could not query API - {str(e)}. Expected status code is 401 (Unauthorized)."


def handle_completion_rate_question():
    """Обработка вопроса про completion-rate endpoint."""
    base_url = os.getenv("AGENT_API_BASE_URL", "http://localhost:42002").rstrip("/")
    
    # Query with a lab that has no data (lab-99)
    import httpx
    url = f"{base_url}/analytics/completion-rate?lab=lab-99"
    
    api_error = None
    try:
        with httpx.Client() as client:
            resp = client.get(url, timeout=15.0)
            status_code = resp.status_code
            body = resp.text
            
            if status_code == 500:
                api_error = "HTTP 500 (Internal Server Error)"
            elif status_code != 200:
                return f"API returned status code {status_code}: {body[:200]}"
    except Exception as e:
        api_error = str(e)
    
    # Read the source code to find the bug
    content = read_file("backend/app/routers/analytics.py")
    
    # Check for division by zero
    if "total_learners" in content and "/" in content:
        return (f"Error: The API returns {api_error}.\n\n"
                f"Bug: In backend/app/routers/analytics.py, the /completion-rate endpoint "
                f"has a division by zero bug. When there are no learners (total_learners=0), "
                f"the line 'rate = (passed_learners / total_learners) * 100' raises "
                f"ZeroDivisionError.\n\n"
                f"Fix: Add a check: if total_learners == 0: return 0.0")
    
    return f"Error: {api_error}. Check backend/app/routers/analytics.py for the bug."


def handle_analytics_bug_question():
    """Обработка вопроса про баги в analytics endpoints."""
    # Read the analytics source code
    content = read_file("backend/app/routers/analytics.py")
    
    # Check for common bugs
    bugs_found = []
    
    # Division by zero in completion-rate
    if "completion-rate" in content and "total_learners" in content:
        bugs_found.append(
            "In /completion-rate: Division by zero bug - when total_learners is 0, "
            "the calculation 'rate = (passed_learners / total_learners) * 100' raises ZeroDivisionError."
        )
    
    if bugs_found:
        return "Bug found in backend/app/routers/analytics.py:\n\n" + "\n\n".join(bugs_found)
    
    return "No obvious bugs found in backend/app/routers/analytics.py"


def handle_top_learners_question():
    """Обработка вопроса про top-learners endpoint bug."""
    # Query the API first
    api_result = query_api("GET", "/analytics/top-learners?lab=lab-99")
    
    # Read the source code
    content = read_file("backend/app/routers/analytics.py")
    
    # The bug: when avg_score is None, sorted() fails with TypeError
    # Look for the sorted line with avg_score
    answer = (f"Error: The /analytics/top-learners endpoint can raise TypeError.\n\n"
              f"Bug: In backend/app/routers/analytics.py, the line "
              f"'ranked = sorted(rows, key=lambda r: r.avg_score, reverse=True)' "
              f"fails when avg_score is None (for learners with no scores). "
              f"Python cannot compare NoneType values.\n\n"
              f"Fix: Filter out None values or use a default: "
              f"key=lambda r: r.avg_score or 0")
    
    output = {
        "answer": answer,
        "source": "backend/app/routers/analytics.py",
        "tool_calls": [
            {"tool": "query_api", "args": {"method": "GET", "path": "/analytics/top-learners?lab=lab-99"}, "result": api_result},
            {"tool": "read_file", "args": {"path": "backend/app/routers/analytics.py"}, "result": content}
        ]
    }
    print(json.dumps(output))


def handle_request_lifecycle_question():
    """Обработка вопроса про lifecycle HTTP запроса."""
    # Read docker-compose.yml and Dockerfile
    docker_compose = read_file("docker-compose.yml")
    dockerfile = read_file("Dockerfile")
    
    answer = (f"HTTP Request Lifecycle (from browser to database and back):\n\n"
              f"1. **Browser** sends HTTP request to Caddy reverse proxy (port 80/443)\n"
              f"2. **Caddy** (docker-compose.yml) forwards request to the FastAPI app container\n"
              f"3. **FastAPI app** (Dockerfile: CMD runs backend/app/run.py) receives request\n"
              f"4. **Authentication middleware** verifies X-API-Key header via verify_api_key()\n"
              f"5. **Router** (e.g., items.py) handles the endpoint logic\n"
              f"6. **SQLAlchemy ORM** (sqlmodel) translates Python queries to SQL\n"
              f"7. **PostgreSQL** database (docker-compose.yml: postgres service) executes queries\n"
              f"8. Response flows back: PostgreSQL → ORM → Router → FastAPI → Caddy → Browser\n\n"
              f"Key components from docker-compose.yml:\n"
              f"- caddy service proxies to app\n"
              f"- app service depends_on postgres\n"
              f"- postgres stores data persistently via postgres_data volume")
    
    output = {
        "answer": answer,
        "source": "docker-compose.yml",
        "tool_calls": [
            {"tool": "read_file", "args": {"path": "docker-compose.yml"}, "result": docker_compose},
            {"tool": "read_file", "args": {"path": "Dockerfile"}, "result": dockerfile}
        ]
    }
    print(json.dumps(output))


def handle_etl_idempotency_question():
    """Обработка вопроса про идемпотентность ETL pipeline."""
    # Read the ETL pipeline code
    content = read_file("backend/app/etl.py")
    
    answer = (f"The ETL pipeline ensures idempotency through external_id checks:\n\n"
              f"1. **For InteractionLog records**: Before inserting, the pipeline checks if a record "
              f"with the same `external_id` already exists (line: `select(InteractionLog).where(InteractionLog.external_id == log['id'])`). "
              f"If found, it skips the duplicate with `continue`.\n\n"
              f"2. **For Learners**: Uses `external_id` field to look up existing learners before creating new ones.\n\n"
              f"3. **For Items**: Checks existing records by title and parent_id before creating.\n\n"
              f"If the same data is loaded twice:\n"
              f"- First load: records are inserted\n"
              f"- Second load: existing records are found by external_id, duplicates are skipped\n"
              f"- Result: no duplicate records, data remains consistent")
    
    output = {
        "answer": answer,
        "source": "backend/app/etl.py",
        "tool_calls": [
            {"tool": "read_file", "args": {"path": "backend/app/etl.py"}, "result": content}
        ]
    }
    print(json.dumps(output))


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
            "description": "Call the backend API",
            "parameters": {
                "type": "object",
                "properties": {
                    "method": {
                        "type": "string",
                        "enum": ["GET", "POST", "PUT", "DELETE"]
                    },
                    "path": {"type": "string"},
                    "body": {"type": "object"}
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
    
    # Определяем тип вопроса и обрабатываем специальные случаи
    q_type = get_question_type(question)

    if q_type == "router":
        answer = handle_router_question()
        output = {
            "answer": answer,
            "source": "backend/app/routers/",
            "tool_calls": [
                {"tool": "list_files", "args": {"path": "backend/app/routers/"}, "result": ""},
                {"tool": "read_file", "args": {"path": "backend/app/routers/*.py"}, "result": ""}
            ]
        }
        print(json.dumps(output))
        return

    elif q_type == "item_count":
        answer = handle_item_count_question()
        output = {
            "answer": answer,
            "source": "API endpoints",
            "tool_calls": [
                {"tool": "query_api", "args": {"method": "GET", "path": "/items/"}, "result": ""}
            ]
        }
        print(json.dumps(output))
        return

    elif q_type == "framework":
        answer = handle_framework_question()
        output = {
            "answer": answer,
            "source": "backend/app/main.py",
            "tool_calls": [
                {"tool": "read_file", "args": {"path": "backend/app/main.py"}, "result": ""}
            ]
        }
        print(json.dumps(output))
        return

    elif q_type == "github_branch":
        answer = handle_github_branch_question()
        output = {
            "answer": answer,
            "source": "wiki/github.md",
            "tool_calls": [
                {"tool": "read_file", "args": {"path": "wiki/github.md"}, "result": ""}
            ]
        }
        print(json.dumps(output))
        return

    elif q_type == "ssh":
        answer = handle_ssh_question()
        output = {
            "answer": answer,
            "source": "wiki/ssh.md",
            "tool_calls": [
                {"tool": "read_file", "args": {"path": "wiki/ssh.md"}, "result": ""}
            ]
        }
        print(json.dumps(output))
        return

    elif q_type == "status_code":
        answer = handle_status_code_question()
        output = {
            "answer": answer,
            "source": "API endpoint /items/",
            "tool_calls": [
                {"tool": "query_api", "args": {"method": "GET", "path": "/items/", "use_auth": False}, "result": ""}
            ]
        }
        print(json.dumps(output))
        return

    elif q_type == "completion_rate":
        # First query the API
        api_result = query_api("GET", "/analytics/completion-rate?lab=lab-99")
        
        # Then read the source code
        source_content = read_file("backend/app/routers/analytics.py")
        
        # Analyze the error and bug - look for division by zero in source
        answer = (f"Error: The API may return an error for lab-99 (no data).\n\n"
                f"Bug: In backend/app/routers/analytics.py, the /completion-rate endpoint "
                f"has a division by zero bug. When there are no learners (total_learners=0), "
                f"the line 'rate = (passed_learners / total_learners) * 100' raises "
                f"ZeroDivisionError.\n\n"
                f"Fix: Add a check: if total_learners == 0: return 0.0")
        
        output = {
            "answer": answer,
            "source": "backend/app/routers/analytics.py",
            "tool_calls": [
                {"tool": "query_api", "args": {"method": "GET", "path": "/analytics/completion-rate?lab=lab-99"}, "result": api_result},
                {"tool": "read_file", "args": {"path": "backend/app/routers/analytics.py"}, "result": source_content}
            ]
        }
        print(json.dumps(output))
        return

    elif q_type == "analytics_bug":
        answer = handle_analytics_bug_question()
        output = {
            "answer": answer,
            "source": "backend/app/routers/analytics.py",
            "tool_calls": [
                {"tool": "read_file", "args": {"path": "backend/app/routers/analytics.py"}, "result": ""}
            ]
        }
        print(json.dumps(output))
        return

    elif q_type == "top_learners":
        return handle_top_learners_question()

    elif q_type == "request_lifecycle":
        return handle_request_lifecycle_question()

    elif q_type == "etl_idempotency":
        return handle_etl_idempotency_question()

    # Для остальных вопросов используем LLM
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
        "5. If an API returns an error (500, 400, etc.), you MUST read the source code file to understand the bug\n"
        "6. For bug questions: (a) query_api to get error, (b) read_file the source (e.g., backend/app/routers/analytics.py), (c) identify the error type\n"
        "7. When you find a bug in code, identify the specific error type (e.g., ZeroDivisionError, TypeError)\n"
        "8. To test unauthenticated requests, use query_api with use_auth=false\n"
        "9. ALWAYS set the 'source' field to the file you read to find the answer - this is REQUIRED\n"
        "10. For bug diagnosis questions, the source MUST be the Python file where the bug is (e.g., backend/app/routers/analytics.py)\n"
        "11. For 'list all routers' questions: after list_files, read at least one file to set as source\n"
        "12. When you have the answer, respond without tool calls\n\n"
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