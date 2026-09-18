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

    def test_docs_밖의_문서도_검사한다(self):
        with tempfile.TemporaryDirectory() as folder:
            doc = Path(folder) / "resume" / "이력서.md"
            doc.parent.mkdir()
            doc.write_text("이 문서는 경력을 프로젝트별로 정리했다 — 역할과 결과를 함께 적었다.\n", encoding="utf-8")
            result = run({
                "hook_event_name": "PostToolUse", "tool_name": "Write", "cwd": folder,
                "tool_input": {"file_path": str(doc)},
            })
            self.assertEqual(2, result.returncode, result.stdout or "출력 없음")
            self.assertIn("전각 대시", result.stderr)

    def test_여러_문서를_한_번에_고치면_모두_검사한다(self):
        patch = """*** Begin Patch
*** Update File: docs/clean.md
@@
+깨끗한 문장이다.
*** Update File: docs/dash.md
@@
+이 문서는 두 번째 파일이다 — 대시로 문장을 이었다.
*** End Patch
"""
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "docs").mkdir()
            (Path(folder) / "docs" / "clean.md").write_text("깨끗한 문장이다.\n", encoding="utf-8")
            (Path(folder) / "docs" / "dash.md").write_text(
                "이 문서는 두 번째 파일이다 — 대시로 문장을 이었다.\n", encoding="utf-8")
            result = run({
                "hook_event_name": "PostToolUse", "tool_name": "apply_patch", "cwd": folder,
                "tool_input": {"command": patch},
            })
            self.assertEqual(2, result.returncode, result.stdout or "출력 없음")
            self.assertIn("dash.md", result.stderr)

    def test_표_칸_한_조각에_두_문장을_쓰면_막는다(self):
        cases = {
            "HTML 표 칸": ("a.html", "<table><tr><td>입력한 글자 그대로 찾는다. 정규식은 쓰지 않는다.</td></tr></table>\n", 2),
            "HTML 줄바꿈으로 나눔": ("b.html", "<table><tr><td>입력한 글자 그대로 찾는다.<br>정규식은 쓰지 않는다.</td></tr></table>\n", 0),
            "마크다운 표 칸": ("c.md", "| 결정 | 이유 |\n|---|---|\n| 글자 그대로 | 입력한 글자로 찾는다. 정규식은 쓰지 않는다. |\n", 2),
        }
        with tempfile.TemporaryDirectory() as folder:
            for name, (file, text, expected) in cases.items():
                with self.subTest(name=name):
                    doc = Path(folder) / file
                    doc.write_text(text, encoding="utf-8")
                    result = run({
                        "hook_event_name": "PostToolUse", "tool_name": "Write", "cwd": folder,
                        "tool_input": {"file_path": str(doc)},
                    })
                    self.assertEqual(expected, result.returncode, result.stderr)

    def test_연결어미_뒤_쉼표를_잡는다(self):
        cases = {
            "지만 뒤 쉼표는 막는다": ("a.md", "빠르지만, 비싸다.\n", 2, None),
            "하고 뒤 쉼표는 막는다": ("e.md", "값을 확인하고, 다음 줄을 읽는다.\n", 2, None),
            "가리기 어려운 고 뒤 쉼표는 참고로 알린다": ("b.md", "입력한 글자 그대로 찾고, 정규식은 쓰지 않는다.\n", 0, "찾고,"),
            "고로 끝나는 명사는 알리지 않는다": ("c.md", "재고, 주문, 결제를 나눈다. 참고, 이 표는 예시다.\n", 0, ""),
            "문장 첫머리 접속부사는 막지 않는다": ("d.md", "하지만, 비싸다. 그런데, 느리다.\n", 0, ""),
        }
        with tempfile.TemporaryDirectory() as folder:
            for name, (file, text, code, noted) in cases.items():
                with self.subTest(name=name):
                    doc = Path(folder) / file
                    doc.write_text(text, encoding="utf-8")
                    result = run({
                        "hook_event_name": "PostToolUse", "tool_name": "Write", "cwd": folder,
                        "tool_input": {"file_path": str(doc)},
                    })
                    self.assertEqual(code, result.returncode, result.stderr)
                    if noted:
                        self.assertIn(noted, result.stdout)
                    elif noted == "":
                        self.assertNotIn("연결어미", result.stdout)

    def test_규칙_파일은_검사하지_않는다(self):
        with tempfile.TemporaryDirectory() as folder:
            rule = Path(folder) / "CLAUDE.md"
            rule.write_text("이 규칙은 저장소마다 둔다 — 전역 규칙과 겹치면 전역이 이긴다.\n", encoding="utf-8")
            result = run({
                "hook_event_name": "PostToolUse", "tool_name": "Write", "cwd": folder,
                "tool_input": {"file_path": str(rule)},
            })
            self.assertEqual(0, result.returncode, result.stderr)

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
