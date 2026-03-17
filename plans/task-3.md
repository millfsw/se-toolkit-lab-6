# Task 3: The System Agent - Implementation Plan

## Overview
Task 3 extends the agent from Task 2 with a new `query_api` tool that allows the LLM to query the deployed backend API. This enables the agent to answer:
1. **Static system facts** - framework, ports, status codes
2. **Data-dependent queries** - item count, scores, analytics

## Tool Schema Design

### query_api Tool
```json
{
  "type": "function",
  "function": {
    "name": "query_api",
    "description": "Call the backend API. Use for data queries (item count, analytics) and status code checks. Authentication is handled automatically.",
    "parameters": {
      "type": "object",
      "properties": {
        "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE"], "description": "HTTP method"},
        "path": {"type": "string", "description": "API path, e.g., '/items/' or '/analytics/completion-rate?lab=lab-99'"},
        "body": {"type": "object", "description": "Optional JSON request body for POST/PUT"}
      },
      "required": ["method", "path"]
    }
  }
}
```

## Authentication Handling
- Read `LMS_API_KEY` from environment (via `.env.docker.secret`)
- Include `Authorization: Bearer {LMS_API_KEY}` header in all API requests
- Read `AGENT_API_BASE_URL` from environment, default to `http://localhost:42002`

## System Prompt Updates
The system prompt must guide the LLM to choose the right tool:
- **Documentation questions** → `list_files(path='wiki')` then `read_file`
- **Code questions** → `list_files(path='.')` then `read_file`
- **Data/API questions** → `query_api` (item count, status codes, analytics)
- **Bug diagnosis** → `query_api` first to get error, then `read_file` to find bug

## Environment Variables
| Variable | Purpose | Source |
|----------|---------|--------|
| `LLM_API_KEY` | LLM provider API key | `.env.agent.secret` |
| `LLM_API_BASE` | LLM API endpoint URL | `.env.agent.secret` |
| `LLM_MODEL` | Model name | `.env.agent.secret` |
| `LMS_API_KEY` | Backend API key for query_api auth | `.env.docker.secret` |
| `AGENT_API_BASE_URL` | Base URL for query_api (optional) | defaults to `http://localhost:42002` |

## Implementation Steps
1. Ensure `query_api` tool is properly implemented with authentication
2. Update system prompt to clarify when to use each tool
3. Test with benchmark questions
4. Iterate based on failures

## Benchmark Questions Reference
| # | Question | Required Tool(s) | Expected Answer |
|---|----------|------------------|-----------------|
| 0 | Wiki: protect a branch | read_file | branch, protect |
| 1 | Wiki: SSH connection | read_file | ssh, key, connect |
| 2 | Backend framework | read_file | FastAPI |
| 3 | List API routers | list_files | items, interactions, analytics, pipeline |
| 4 | Items in database | query_api | number > 0 |
| 5 | Status code without auth | query_api | 401 or 403 |
| 6 | /analytics/completion-rate bug | query_api, read_file | ZeroDivisionError |
| 7 | /analytics/top-learners bug | query_api, read_file | TypeError, None, sorted |
| 8 | Request lifecycle | read_file | Caddy → FastAPI → auth → router → ORM → PostgreSQL |
| 9 | ETL idempotency | read_file | external_id check, duplicates skipped |

## Initial Score & Iteration Strategy
*To be filled after first run_eval.py execution*

### First Failures
*To be filled after first run_eval.py execution*

### Iteration Strategy
1. Run `uv run run_eval.py` to get initial score
2. For each failure:
   - Check if wrong tool was used → improve system prompt
   - Check if tool returned error → fix tool implementation
   - Check if answer doesn't match keywords → adjust answer phrasing
3. Re-run until all 10 pass
