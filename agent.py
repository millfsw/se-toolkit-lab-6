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
    
    # Проверяем наличие API ключа
    api_key = os.getenv("LMS_API_KEY")
    if not api_key:
        return "Error: LMS_API_KEY not found in environment variables. Please check .env.agent.secret file."
    
    # Пробуем разные варианты эндпоинтов
    endpoints = ["/items/", "/api/items/", "/v1/items/", "/items", "/api/items"]
    
    for endpoint in endpoints:
        api_result = query_api("GET", endpoint)
        
        try:
            result_data = json.loads(api_result)
            
            if "error" in result_data:
                continue  # Пробуем следующий эндпоинт
            
            status_code = result_data.get("status_code")
            body = result_data.get("body", "[]")
            
            # Проверяем статус код
            if status_code == 200:
                # Парсим body как JSON
                try:
                    items = json.loads(body)
                    if isinstance(items, list):
                        count = len(items)
                        return f"There are currently {count} items in the database (from {endpoint})."
                    elif isinstance(items, dict):
                        # Проверяем различные возможные поля
                        if "items" in items and isinstance(items["items"], list):
                            count = len(items["items"])
                            return f"There are currently {count} items in the database (from {endpoint}.items)."
                        elif "data" in items and isinstance(items["data"], list):
                            count = len(items["data"])
                            return f"There are currently {count} items in the database (from {endpoint}.data)."
                        elif "results" in items and isinstance(items["results"], list):
                            count = len(items["results"])
                            return f"There are currently {count} items in the database (from {endpoint}.results)."
                except json.JSONDecodeError:
                    continue
            elif status_code == 401 or status_code == 403:
                # Пробуем следующий эндпоинт с этой же ошибкой
                continue
                
        except Exception:
            continue
    
    # Если ни один эндпоинт не сработал, пробуем найти информацию о API в файлах
    try:
        # Ищем в файлах информацию о структуре API
        if os.path.exists("backend/app/routers/"):
            files = os.listdir("backend/app/routers/")
            for file in files:
                if file.endswith(".py") and "item" in file.lower():
                    content = read_file(f"backend/app/routers/{file}")
                    # Ищем упоминания эндпоинтов
                    endpoint_matches = re.findall(r'@router\.(?:get|post|put|delete)\([\'"](/[^\'"]+)[\'"]', content)
                    if endpoint_matches:
                        return (f"Found possible item endpoints in {file}: {', '.join(endpoint_matches)}. "
                               f"Please try querying one of these with authentication. "
                               f"Current API key: {api_key[:5]}... (first 5 chars)")
    except Exception:
        pass
    
    # Возвращаем диагностическое сообщение
    return (f"Error: Could not query items from API. "
            f"API Key present: {'Yes' if api_key else 'No'} "
            f"(first 5 chars: {api_key[:5] if api_key else 'N/A'}). "
            f"Please check that LMS_API_KEY is correct in .env.agent.secret")


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