#!/usr/bin/env python3
"""commit-checkpoint 훅 테스트.

실행: python3 ~/.claude/hooks/tests/test_commit_checkpoint.py
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent / "commit-checkpoint.py"


def repo_with_change(folder):
    """미커밋 변경이 하나 있는 저장소를 만든다."""
    subprocess.run(["git", "init", "-q"], cwd=folder, check=True)
    (Path(folder) / "a.py").write_text("print('ok')\n", encoding="utf-8")


def run(command, response, cwd):
    payload = {
        "hook_event_name": "PostToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "tool_response": response,
    }
    return subprocess.run(
        [sys.executable, str(HOOK)], input=json.dumps(payload),
        capture_output=True, text=True, cwd=cwd,
    )


class CommitCheckpoint(unittest.TestCase):
    def test_파이썬_테스트가_통과하면_체크포인트를_낸다(self):
        with tempfile.TemporaryDirectory() as folder:
            repo_with_change(folder)
            result = run(
                "python3 ~/.claude/hooks/tests/test_stop_check.py",
                "Ran 1 test in 0.03s\n\nOK",
                folder,
            )
            self.assertIn("block", result.stdout)
            self.assertIn("체크포인트", result.stdout)


if __name__ == "__main__":
    unittest.main()
