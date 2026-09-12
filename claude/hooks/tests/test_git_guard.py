#!/usr/bin/env python3
"""git-guard 훅 테스트.

실행: python3 ~/.claude/hooks/tests/test_git_guard.py
"""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent / "git-guard.py"
_spec = importlib.util.spec_from_file_location("git_guard", HOOK)
git_guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(git_guard)

BODY = "작업 내용\n검토에서 바뀐 것\n인수 확인\n앞 문장이 있다 — 뒤 문장이 이어진다.\n"


def run(command, cwd):
    payload = {"hook_event_name": "PreToolUse", "tool_name": "Bash",
               "tool_input": {"command": command}, "cwd": cwd}
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload),
                          capture_output=True, text=True)


class PrFirst(unittest.TestCase):
    def test_브랜치에_커밋이_하나_있는데_PR_이_없으면_막는다(self):
        self.assertTrue(git_guard.needs_pr("docs/doc-writing-skill", 1, False))

    def test_검토_줄에_댓글_주소가_없으면_막는다(self):
        self.assertTrue(git_guard.needs_comment_link("검토: 지적 → 바뀐 것"))
        self.assertFalse(git_guard.needs_comment_link(
            "검토: 지적 → 바뀐 것 (https://github.com/o/r/pull/2#issuecomment-1)"))


class TargetRepo(unittest.TestCase):
    def test_cd_가_가리키는_저장소의_PR_본문을_읽는다(self):
        with tempfile.TemporaryDirectory() as here, tempfile.TemporaryDirectory() as there:
            (Path(there) / "body.md").write_text(BODY, encoding="utf-8")
            result = run(f"cd {there} && gh pr edit 4 --body-file body.md", here)
            self.assertEqual(2, result.returncode, result.stdout or "막지 않았다")
            self.assertIn("전각 대시", result.stderr)


if __name__ == "__main__":
    unittest.main()
