# Plan for Task 3: System Agent Integration

## 1. Tool Implementation: `query_api`
- **Library**: `httpx` for handling HTTP requests.
- **Parameters**: `method` (GET/POST/etc.), `path` (endpoint), and optional `body`.
- **Authentication**: Include `X-API-Key` header using `LMS_API_KEY` from environment variables.
- **Base URL**: Use `AGENT_API_BASE_URL` (default: http://localhost:42002).

## 2. System Prompt Update
- Instruct the LLM: "Use `query_api` for live system data or API status questions. If the API returns an error (e.g., 500), use `read_file` to inspect the backend source code and diagnose the bug."
- Emphasize that `source` is optional for system/data queries.

## 3. Benchmark Strategy
- Run `run_eval.py` to identify failing questions.
- **Iteration**: If the agent fails to find bugs (Questions 6-7), clarify in the prompt that it must look at router modules when an API error occurs.
- Ensure the tool schema explicitly mentions that `path` must start with a `/`.

## 4. Benchmark Results (Initial)
- **Initial Score**: 0/10 (before implementation).
- **Target Score**: 10/10.
