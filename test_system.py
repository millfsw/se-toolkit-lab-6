import subprocess
import json
import os

def run_agent(question):
    """Вспомогательная функция для запуска агента через subprocess"""
    result = subprocess.run(
        ["uv", "run", "agent.py", question],
        capture_output=True,
        text=True,
        encoding='utf-8'
    )
    return result

def test_agent_format():
    """Тест 1: Проверка базового формата JSON и обязательных полей"""
    result = run_agent("What is REST?")
    
    assert result.returncode == 0, f"Agent failed with error: {result.stderr}"
    
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        assert False, f"Output is not valid JSON: {result.stdout}"
    
    assert "answer" in data, "Missing 'answer' field"
    assert "tool_calls" in data, "Missing 'tool_calls' field"
    assert isinstance(data["tool_calls"], list), "'tool_calls' must be a list"

def test_wiki_search_tool_usage():
    """Тест 2: Проверка, что агент использует инструменты для поиска в wiki"""
    # Этот тест предполагает, что в папке wiki есть файл github.md или аналогичный
    result = run_agent("How to protect a branch on GitHub according to the wiki?")
    
    assert result.returncode == 0
    data = json.loads(result.stdout)
    
    # Проверяем, что в истории есть вызов read_file и поле source заполнено
    has_read_tool = any(call["tool"] == "read_file" for call in data.get("tool_calls", []))
    assert has_read_tool, "Agent should use 'read_file' for wiki questions"
    assert data.get("source") is not None, "Source field should be present for wiki questions"

def test_api_tool_usage():
    """Тест 3: Проверка, что агент использует query_api для вопросов о данных"""
    result = run_agent("How many items are in the database?")
    
    assert result.returncode == 0
    data = json.loads(result.stdout)
    
    # Проверяем использование query_api
    has_query_tool = any(call["tool"] == "query_api" for call in data.get("tool_calls", []))
    assert has_query_tool, "Agent should use 'query_api' to check database items"
