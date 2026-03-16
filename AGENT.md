# Agent Documentation

## Setup
- Uses `openai` library.
- Environment variables are stored in `.env.agent.secret`.

## Usage
Run the agent with:
`uv run agent.py "Your question here"`

## Provider
- **Model**: Qwen 3 Coder Plus
- **Provider**: Qwen API

## Tools
- `list_files(path)`: Navigates the project structure.
- `read_file(path)`: Reads documentation files (restricted to project root).

## Agentic Loop
The agent uses a "Reasoning and Acting" loop (ReAct). It can make up to 10 sequential tool calls to find the correct information in the `wiki/` folder before giving a final answer.

## Safety
Input paths are sanitized to prevent `../` directory traversal attacks.