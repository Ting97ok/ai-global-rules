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
                "python3 tests/test_stop_check.py",
                "Ran 1 test in 0.03s\n\nOK",
                folder,
            )
            self.assertIn("block", result.stdout)
            self.assertIn("체크포인트", result.stdout)

    def test_테스트가_실패하면_체크포인트를_내지_않는다(self):
        with tempfile.TemporaryDirectory() as folder:
            repo_with_change(folder)
            result = run(
                "python3 ~/.claude/hooks/tests/test_stop_check.py",
                "FAIL: test_x\nRan 1 test in 0.03s\n\nFAILED (failures=1)\n",
                folder,
            )
            self.assertEqual("", result.stdout.strip(), result.stdout)

    def test_따옴표_안의_테스트_명령은_실행으로_보지_않는다(self):
        with tempfile.TemporaryDirectory() as folder:
            repo_with_change(folder)
            result = run(
                'claude -p "python3 tests/test_x.py 를 돌려줘" --output-format json',
                "세션이 끝났다",
                folder,
            )
            self.assertEqual("", result.stdout.strip(), result.stdout)

    def test_명령_앞의_cd_가_가리키는_저장소를_센다(self):
        with tempfile.TemporaryDirectory() as here, tempfile.TemporaryDirectory() as there:
            subprocess.run(["git", "init", "-q"], cwd=here, check=True)
            repo_with_change(there)
            result = run(
                f"cd {there} && python3 tests/test_x.py",
                "Ran 1 test in 0.03s\n\nOK",
                here,
            )
            self.assertIn("block", result.stdout)
            self.assertIn(there, result.stdout)

    def test_저장소_밖의_테스트_파일이면_체크포인트를_내지_않는다(self):
        with tempfile.TemporaryDirectory() as here, tempfile.TemporaryDirectory() as away:
            repo_with_change(here)
            outside = Path(away) / "test_usage.py"
            outside.write_text("", encoding="utf-8")
            result = run(f"python3 {outside}", "Ran 1 test in 0.03s\n\nOK", here)
            self.assertEqual("", result.stdout.strip(), result.stdout)


if __name__ == "__main__":
    unittest.main()
