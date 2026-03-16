# Plan for Task 1: Basic LLM Integration

1. **Provider**: Qwen Code (model: qwen3-coder-plus).
2. **Library**: `openai` python SDK for communication.
3. **Logic**: 
   - Parse input from `sys.argv`.
   - Load env from `.env.agent.secret`.
   - Call LLM via Chat Completions.
   - Output exact JSON: `{"answer": "...", "tool_calls": []}` to stdout.
