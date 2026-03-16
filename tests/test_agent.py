import subprocess
import json

def test_agent_output():
    result = subprocess.run(
        ["python3", "agent.py", "What is 2+2?"],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert "answer" in data
    assert "tool_calls" in data
    assert isinstance(data["tool_calls"], list)
