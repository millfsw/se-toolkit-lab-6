import os
import sys
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(".env.agent.secret")

# --- Реализация инструментов ---
def list_files(path="."):
    if ".." in path: return "Error: Access denied"
    try:
        return "\n".join(os.listdir(path))
    except Exception as e:
        return str(e)

def read_file(path):
    if ".." in path: return "Error: Access denied"
    try:
        with open(path, 'r') as f:
            return f.read()
    except Exception as e:
        return str(e)

# --- Схемы для LLM ---
tools_schema = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files in a directory",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read content of a file",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"]
            }
        }
    }
]

def main():
    question = sys.argv[1]
    client = OpenAI(api_key=os.getenv("LLM_API_KEY"), base_url=os.getenv("LLM_API_BASE"))
    
    messages = [
        {"role": "system", "content": "You are a wiki assistant. Use list_files to find info in 'wiki/' and read_file to answer. Always provide the source file path and section anchor in the 'source' field."},
        {"role": "user", "content": question}
    ]
    
    history_tool_calls = []
    
    for _ in range(10):  # Максимум 10 шагов
        response = client.chat.completions.create(
            model=os.getenv("LLM_MODEL"),
            messages=messages,
            tools=tools_schema
        )
        
        msg = response.choices[0].message
        
        if msg.tool_calls:
            messages.append(msg)
            for tool_call in msg.tool_calls:
                name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)
                
                # Вызов функции
                if name == "list_files":
                    result = list_files(**args)
                elif name == "read_file":
                    result = read_file(**args)
                
                history_tool_calls.append({
                    "tool": name,
                    "args": args,
                    "result": result
                })
                
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result
                })
        else:
            # Финальный ответ
            # Здесь можно попросить LLM вытащить source, если она его не дала в тексте
            print(json.dumps({
                "answer": msg.content,
                "source": "wiki/filename.md#section", # В идеале парсить из ответа LLM
                "tool_calls": history_tool_calls
            }))
            return

if __name__ == "__main__":
    main()
