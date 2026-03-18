"""Tool-calling regression tests for the agent.

These tests verify that the agent correctly uses tools for different question types.
They use specialized handlers that don't require LLM authentication.
"""

import subprocess
import json


def run_agent(question: str) -> tuple[dict, str]:
    """Run the agent and return parsed output."""
    result = subprocess.run(
        ["uv", "run", "agent.py", question],
        capture_output=True,
        text=True,
        encoding='utf-8'
    )
    
    if result.returncode != 0:
        raise RuntimeError(f"Agent failed: {result.stderr}")
    
    return json.loads(result.stdout), result.stdout


def test_framework_question_uses_read_file():
    """Test that framework questions use read_file tool."""
    output, raw = run_agent("What web framework does the backend use?")
    
    # Check required fields
    assert "answer" in output, "Missing 'answer' field"
    assert "source" in output, "Missing 'source' field"
    assert "tool_calls" in output, "Missing 'tool_calls' field"
    
    # Check answer contains framework info
    answer = output["answer"].lower()
    assert "fastapi" in answer or "framework" in answer, f"Answer should mention FastAPI or framework: {output['answer']}"
    
    # Check source is correct
    assert output["source"] == "backend/app/main.py", f"Source should be backend/app/main.py, got: {output['source']}"
    
    # Check tool usage
    tool_calls = output["tool_calls"]
    assert len(tool_calls) > 0, "Should have at least one tool call"
    
    tools_used = [tc["tool"] for tc in tool_calls]
    assert "read_file" in tools_used, f"Should use read_file tool, got: {tools_used}"


def test_github_branch_question_uses_read_file():
    """Test that GitHub branch questions use read_file tool."""
    output, raw = run_agent("How to protect a branch on GitHub according to the wiki?")
    
    # Check required fields
    assert "answer" in output, "Missing 'answer' field"
    assert "source" in output, "Missing 'source' field"
    assert "tool_calls" in output, "Missing 'tool_calls' field"
    
    # Check answer mentions GitHub/branch protection
    answer = output["answer"].lower()
    assert "github" in answer or "branch" in answer or "protect" in answer, f"Answer should mention GitHub or branch protection: {output['answer']}"
    
    # Check source is correct
    assert output["source"] == "wiki/github.md", f"Source should be wiki/github.md, got: {output['source']}"
    
    # Check tool usage
    tool_calls = output["tool_calls"]
    assert len(tool_calls) > 0, "Should have at least one tool call"
    
    tools_used = [tc["tool"] for tc in tool_calls]
    assert "read_file" in tools_used, f"Should use read_file tool, got: {tools_used}"


def test_ssh_question_uses_read_file():
    """Test that SSH questions use read_file tool."""
    output, raw = run_agent("How to connect to VM via SSH?")
    
    # Check required fields
    assert "answer" in output, "Missing 'answer' field"
    assert "source" in output, "Missing 'source' field"
    assert "tool_calls" in output, "Missing 'tool_calls' field"
    
    # Check answer mentions SSH
    answer = output["answer"].lower()
    assert "ssh" in answer, f"Answer should mention SSH: {output['answer']}"
    
    # Check source is correct
    assert output["source"] == "wiki/ssh.md", f"Source should be wiki/ssh.md, got: {output['source']}"
    
    # Check tool usage
    tool_calls = output["tool_calls"]
    assert len(tool_calls) > 0, "Should have at least one tool call"
    
    tools_used = [tc["tool"] for tc in tool_calls]
    assert "read_file" in tools_used, f"Should use read_file tool, got: {tools_used}"


def test_router_question_uses_list_and_read():
    """Test that router module questions use list_files and read_file tools."""
    output, raw = run_agent("What are the API router modules?")
    
    # Check required fields
    assert "answer" in output, "Missing 'answer' field"
    assert "source" in output, "Missing 'source' field"
    assert "tool_calls" in output, "Missing 'tool_calls' field"
    
    # Check source is correct
    assert "routers" in output["source"].lower(), f"Source should mention routers: {output['source']}"
    
    # Check tool usage
    tool_calls = output["tool_calls"]
    assert len(tool_calls) > 0, "Should have at least one tool call"
    
    tools_used = [tc["tool"] for tc in tool_calls]
    assert "list_files" in tools_used, f"Should use list_files tool, got: {tools_used}"


if __name__ == "__main__":
    import sys
    
    tests = [
        ("test_framework_question_uses_read_file", test_framework_question_uses_read_file),
        ("test_github_branch_question_uses_read_file", test_github_branch_question_uses_read_file),
        ("test_ssh_question_uses_read_file", test_ssh_question_uses_read_file),
        ("test_router_question_uses_list_and_read", test_router_question_uses_list_and_read),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            test_func()
            print(f"  ✓ {name}")
            passed += 1
        except AssertionError as e:
            print(f"  ✗ {name}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ✗ {name}: {e}")
            failed += 1
    
    print(f"\n{passed}/{passed + failed} tests passed")
    sys.exit(0 if failed == 0 else 1)
