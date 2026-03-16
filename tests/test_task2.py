import subprocess
import json

def test_merge_conflict_search():
    res = subprocess.run(["python3", "agent.py", "How to resolve merge conflicts?"], capture_output=True, text=True)
    data = json.loads(res.stdout)
    # Проверяем, что агент хотя бы пытался читать файлы
    assert any(tc['tool'] == 'read_file' for tc in data['tool_calls'])
    assert "source" in data

def test_list_wiki():
    res = subprocess.run(["python3", "agent.py", "What's in the wiki?"], capture_output=True, text=True)
    data = json.loads(res.stdout)
    assert any(tc['tool'] == 'list_files' for tc in data['tool_calls'])
