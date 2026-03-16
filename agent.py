import os
import sys
import json
from openai import OpenAI
from dotenv import load_dotenv

# Загружаем настройки
load_dotenv(".env.agent.secret")

def main():
    if len(sys.argv) < 2:
        print("Usage: uv run agent.py 'question'", file=sys.stderr)
        sys.exit(1)

    question = sys.argv[1]
    
    client = OpenAI(
        api_key=os.getenv("LLM_API_KEY"),
        base_url=os.getenv("LLM_API_BASE")
    )

    try:
        response = client.chat.completions.create(
            model=os.getenv("LLM_MODEL", "qwen3-coder-plus"),
            messages=[{"role": "user", "content": question}]
        )
        
        answer = response.choices[0].message.content
        
        # Только JSON в stdout
        print(json.dumps({
            "answer": answer,
            "tool_calls": []
        }))
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
