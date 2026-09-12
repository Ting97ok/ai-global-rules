#!/usr/bin/env python3
"""prose-check 훅 테스트.

실행: python3 ~/.claude/hooks/tests/test_prose_check.py
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent / "prose-check.py"

PATCH = """*** Begin Patch
*** Update File: docs/a.md
@@
-옛 문장
+이 훅은 문서의 산문만 검사한다 — 코드 블록 안은 보지 않는다.
*** End Patch
"""


def run(payload):
    return subprocess.run(
        [sys.executable, str(HOOK)], input=json.dumps(payload), capture_output=True, text=True
    )


class ProseCheck(unittest.TestCase):
    def test_Codex_패치_본문에서_문서_경로를_읽는다(self):
        with tempfile.TemporaryDirectory() as folder:
            doc = Path(folder) / "docs" / "a.md"
            doc.parent.mkdir()
            doc.write_text("이 훅은 문서의 산문만 검사한다 — 코드 블록 안은 보지 않는다.\n", encoding="utf-8")
            result = run({
                "hook_event_name": "PostToolUse",
                "tool_name": "apply_patch",
                "cwd": folder,
                "tool_input": {"command": PATCH},
            })
            self.assertEqual(2, result.returncode, result.stdout or "출력 없음")
            self.assertIn("전각 대시", result.stderr)

    def test_셸로_고친_문서도_검사한다(self):
        with tempfile.TemporaryDirectory() as folder:
            doc = Path(folder) / "docs" / "b.md"
            doc.parent.mkdir()
            doc.write_text("이 훅은 산문만 본다 — 코드 블록은 건너뛴다.\n", encoding="utf-8")
            result = run({
                "hook_event_name": "PostToolUse", "tool_name": "Bash", "cwd": folder,
                "tool_input": {"command": "printf '%s' \"$TEXT\" > docs/b.md"},
            })
            self.assertEqual(2, result.returncode, result.stdout or "출력 없음")
            self.assertIn("전각 대시", result.stderr)


if __name__ == "__main__":
    unittest.main()
