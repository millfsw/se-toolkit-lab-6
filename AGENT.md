# System Agent: Final Architecture and Lessons Learned

## Setup and Configuration
The agent uses the `openai` library for LLM interactions with function calling capabilities. All sensitive configuration, including API keys and endpoints, is stored securely in `.env.agent.secret` file which is excluded from version control. The agent loads these environment variables using the `python-dotenv` library at startup. Key configuration includes LLM_API_KEY for authentication, LLM_API_BASE for the API endpoint, LLM_MODEL for model selection, and AGENT_API_BASE_URL for the backend API.

## Usage and Execution
To run the agent, users execute `uv run agent.py "Your question here"` from the command line. The agent expects a single question as a command-line argument and produces a JSON output containing the answer, source references, and tool call history. This structured output allows for easy integration with evaluation scripts like run_eval.py and provides transparency into the agent's reasoning process.

## LLM Provider and Model Selection
The agent is configured to use **Qwen 3 Coder Plus** through the **Qwen API**. This model was chosen for its strong performance on coding tasks and its ability to understand complex instructions about tool usage. The model demonstrates good reasoning capabilities when navigating file systems and interpreting API responses. The agent includes fallback mechanisms to handle different response formats and edge cases.

## Tool Implementation
The agent implements three primary tools for interacting with the environment:

1. **list_files(path)**: Navigates the project structure by listing directory contents. This tool helps the agent understand what files are available before reading them. It includes security checks to prevent path traversal attacks by blocking paths containing "..".

2. **read_file(path)**: Reads documentation and source code files. This tool is restricted to the project root and validates paths to prevent unauthorized access. It's essential for extracting information from wiki documentation and examining backend code structure.

3. **query_api(method, path, body)**: Communicates with the backend LMS API. This tool reads the AGENT_API_BASE_URL from environment variables, adds proper authentication headers (X-API-Key), and handles various HTTP methods. It includes timeout handling and returns structured JSON responses with status codes and body content.

## Agentic Loop and Reasoning Process
The agent uses a sophisticated "Reasoning and Acting" loop (ReAct pattern) that allows for iterative problem-solving. With a maximum of 20 iterations, the agent can make multiple sequential tool calls to gather information before formulating a final answer. The loop works as follows:

- **First iteration**: The LLM is forced to use a tool (tool_choice="required") to ensure it doesn't answer from memory.
- **Subsequent iterations**: Based on tool results, the LLM decides whether to use more tools or provide a final answer.
- **Termination**: When the LLM responds without tool calls, the agent outputs the answer along with source information and tool call history.

## Specialized Question Handling
The agent includes specialized handlers for different question categories to improve accuracy:

- **Wiki questions**: Automatically routes to list_files('wiki/') and read_file for documentation
- **Router module questions**: Examines backend/app/routers/ directory and analyzes each file's content to determine domain responsibilities
- **Item count questions**: Queries multiple API endpoint variations (/items/, /api/items/, etc.) and handles different JSON response formats
- **Framework questions**: Searches backend source code for framework indicators

## Security Considerations
Security was a primary concern during development. All file operations include path sanitization to prevent directory traversal attacks. The agent rejects any path containing ".." to ensure it cannot access files outside the project directory. API keys are stored in environment variables rather than hardcoded, and the .env.agent.secret file is excluded from version control. Tool descriptions in the function schema clearly communicate limitations to the LLM.

## Error Handling and Robustness
The agent includes comprehensive error handling:

- **File not found**: Returns descriptive error messages
- **API timeouts**: Catches exceptions and returns error information
- **Invalid JSON responses**: Gracefully handles malformed API responses
- **Missing environment variables**: Provides clear error messages about configuration issues
- **Maximum iterations**: Prevents infinite loops by terminating after 20 iterations

## Testing and Validation
The agent is tested using run_eval.py against a set of open questions. The evaluation checks for:
- Correct answer content using keyword matching
- Source file references when expected
- Proper tool usage patterns
- Response format compliance

Local tests ensure at least 80% pass rate before deployment.

## Lessons Learned
Throughout development, several important lessons emerged:

1. **Tool design matters**: Simple, focused tools with clear descriptions work better than complex, multi-purpose tools. The LLM understands specific tools like list_files and read_file more reliably.

2. **Authentication challenges**: The LMS API requires X-API-Key header, which wasn't initially obvious. Adding proper headers and testing multiple endpoint variations was crucial for item count questions.

3. **Response format variations**: APIs can return data in different formats (arrays, objects with items/data/results fields). The agent needs flexible parsing to handle all cases.

4. **Path traversal protection**: Simple validation blocking ".." is effective but must be consistently applied across all file operations.

5. **Iteration limits**: Some questions require multiple tool calls. Starting with tool_choice="required" ensures the agent uses tools rather than guessing.

6. **Environment configuration**: Clear documentation of required environment variables prevents deployment issues. The agent now provides helpful error messages when variables are missing.

7. **GitHub integration**: The agent must be in the correct path (/root/se-toolkit-lab-6/agent.py) for the autochecker to find it. This taught the importance of understanding the execution environment.

## Future Improvements
Potential enhancements for future versions include:
- Adding more specialized tools for specific question types
- Implementing caching for frequently accessed files
- Adding parallel tool execution for efficiency
- Improving error recovery with retry mechanisms
- Adding logging for debugging complex failures

## Conclusion
The system agent successfully combines LLM reasoning with practical tool use to answer questions about the project. Its modular design, comprehensive error handling, and specialized question handlers make it robust enough for production use. The agent passes local evaluation tests and is ready for hidden evaluation.
