# Plan for Task 2: Documentation Agent

1.  **Tools Definition**:
    *   `list_files(path)`: Lists directory contents using `os.listdir`.
    *   `read_file(path)`: Returns file content using `open().read()`.
    *   **Security**: Validate that `path` does not contain `..` to prevent directory traversal.

2.  **Agentic Loop**:
    *   Initialize `messages` with a system prompt and user question.
    *   Loop up to 10 times:
        *   Call LLM with `tools` schema.
        *   If `tool_calls` present: execute tool, append result to `messages` as `tool` role, continue.
        *   If no `tool_calls`: extract final answer and exit loop.

3.  **Output**:
    *   Maintain a list of executed `tool_calls` with their arguments and results.
    *   Return JSON with `answer`, `source`, and `tool_calls`.
