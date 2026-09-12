#!/usr/bin/env python3
"""stop-check 훅 테스트.

실행: python3 ~/.claude/hooks/tests/test_stop_check.py
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent / "stop-check.py"


def human(text):
    return {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": text}]}}


def bash_call(call_id, command):
    return {
        "type": "assistant",
        "message": {
            "content": [
                {"type": "tool_use", "id": call_id, "name": "Bash", "input": {"command": command}}
            ]
        },
    }


def bash_result(call_id, output):
    return {
        "type": "user",
        "message": {
            "content": [
                {"type": "tool_result", "tool_use_id": call_id, "content": output, "is_error": False}
            ]
        },
    }


def answer(text):
    return {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}


def transcript(rows, folder):
    path = Path(folder) / "transcript.jsonl"
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    return str(path)


def run(transcript_path):
    payload = {"hook_event_name": "Stop", "stop_hook_active": False,
               "transcript_path": transcript_path}
    return subprocess.run(
        [sys.executable, str(HOOK)], input=json.dumps(payload), capture_output=True, text=True
    )


COMMIT_ANSWER = """사이클 하나를 닫았다.

```bash
cd /repo && git commit -m "[Test] 실패 테스트 하나"
```
"""


class StopCheck(unittest.TestCase):
    def test_테스트가_빨간데_커밋_명령을_주면_막는다(self):
        rows = [
            human("훅 진행해"),
            bash_call("t1", "python3 ~/.claude/hooks/tests/test_doc_skill_guard.py"),
            bash_result("t1", "FAIL: test_막는다\nRan 1 test in 0.02s\n\nFAILED (failures=1)"),
            bash_call("t2", "cd /repo && git status --short && git log --oneline -2"),
            bash_result("t2", " M claude/hooks/doc-skill-guard.py"),
            answer(COMMIT_ANSWER),
        ]
        with tempfile.TemporaryDirectory() as folder:
            result = run(transcript(rows, folder))
            self.assertIn("block", result.stdout)
            self.assertIn("GREEN", result.stdout)

    def test_빈_커밋_명령은_빨간_상태에서도_막지_않는다(self):
        rows = [
            human("브랜치를 시작해"),
            bash_call("t1", "python3 ~/.claude/hooks/tests/test_doc_skill_guard.py"),
            bash_result("t1", "FAIL: test_x\nRan 1 test\n\nFAILED (failures=1)"),
            bash_call("t2", "cd /repo && git status --short"),
            bash_result("t2", " M claude/hooks/git-guard.py"),
            answer('브랜치를 엽니다.\n\n```bash\ncd /repo && git commit --allow-empty -m "[Docs] 브랜치 시작"\n```\n'),
        ]
        with tempfile.TemporaryDirectory() as folder:
            result = run(transcript(rows, folder))
            self.assertEqual("", result.stdout.strip(), result.stdout)

def codex_call(call_id, command):
    return {"type": "response_item", "payload": {
        "type": "custom_tool_call", "call_id": call_id, "name": "exec",
        "input": 'text(await tools.exec_command({cmd:"%s"}))' % command}}


def codex_result(call_id, output):
    return {"type": "response_item", "payload": {
        "type": "custom_tool_call_output", "call_id": call_id,
        "output": [{"type": "input_text", "text": output}]}}


def codex_message(role, text):
    key = "input_text" if role == "user" else "output_text"
    return {"type": "response_item", "payload": {
        "type": "message", "role": role, "content": [{"type": key, "text": text}]}}


class StopCheckCodex(unittest.TestCase):
    def test_Codex_기록에서도_빨간_상태의_커밋_명령을_막는다(self):
        rows = [
            codex_message("user", "테스트 돌리고 커밋 명령 줘"),
            codex_call("c1", "python3 tests/test_x.py"),
            codex_result("c1", "FAIL: test_x\nRan 1 test\n\nFAILED (failures=1)"),
            codex_call("c2", "git status --short"),
            codex_result("c2", " M a.py"),
            codex_message("assistant", COMMIT_ANSWER),
        ]
        with tempfile.TemporaryDirectory() as folder:
            result = run(transcript(rows, folder))
            self.assertIn("block", result.stdout)
            self.assertIn("GREEN", result.stdout)


if __name__ == "__main__":
    unittest.main()
