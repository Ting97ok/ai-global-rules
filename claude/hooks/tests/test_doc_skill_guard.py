#!/usr/bin/env python3
"""doc-skill-guard 훅 테스트.

실행: python3 ~/.claude/hooks/tests/test_doc_skill_guard.py
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent / "doc-skill-guard.py"


def skill_call(name):
    """Skill 도구 호출이 대화 기록에 남는 꼴."""
    return {
        "type": "assistant",
        "message": {
            "content": [
                {"type": "tool_use", "id": "toolu_1", "name": "Skill", "input": {"skill": name}}
            ]
        },
    }


def transcript(rows, folder):
    path = Path(folder) / "transcript.jsonl"
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    return str(path)


def run(payload):
    return subprocess.run(
        [sys.executable, str(HOOK)], input=json.dumps(payload), capture_output=True, text=True
    )


class DocSkillGuard(unittest.TestCase):
    def test_스킬을_부르지_않고_문서를_쓰면_막는다(self):
        with tempfile.TemporaryDirectory() as folder:
            doc = Path(folder) / "docs" / "a.md"
            doc.parent.mkdir()
            result = run(
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "Write",
                    "transcript_path": transcript([skill_call("humanize-korean")], folder),
                    "tool_input": {"file_path": str(doc)},
                }
            )
            self.assertEqual(2, result.returncode, result.stderr)
            self.assertIn("doc-writing", result.stderr)


if __name__ == "__main__":
    unittest.main()
