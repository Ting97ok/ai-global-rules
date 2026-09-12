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

    def test_코드_블록_안의_한_줄만_고치면_산문으로_보지_않는다(self):
        import subprocess as sp
        with tempfile.TemporaryDirectory() as folder:
            doc = Path(folder) / "docs" / "a.md"
            doc.parent.mkdir()
            doc.write_text("# 제목\n\n설명 문장이다.\n\n```python\nx = 1\n```\n", encoding="utf-8")
            for cmd in (["git", "init", "-q"], ["git", "add", "docs/a.md"],
                        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
                         "commit", "-q", "-m", "[Docs] 처음"]):
                sp.run(cmd, cwd=folder, check=True)
            doc.write_text("# 제목\n\n설명 문장이다.\n\n```python\n"
                           "x = 1  # 앞 문장이 있다 — 뒤 문장이 이어진다.\n```\n", encoding="utf-8")
            result = run({
                "hook_event_name": "PostToolUse", "tool_name": "Edit", "cwd": folder,
                "tool_input": {"file_path": str(doc)},
            })
            self.assertEqual(0, result.returncode, result.stderr)


if __name__ == "__main__":
    unittest.main()
