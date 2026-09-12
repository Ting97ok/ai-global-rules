#!/usr/bin/env python3
"""memory-note 훅 테스트.

실행: python3 ~/.claude/hooks/tests/test_memory_note.py
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent / "memory-note.py"

PATCH = """*** Begin Patch
*** Add File: memory/이번-작업.md
@@
+이번 작업에서만 쓰는 메모
*** End Patch
"""


def run(payload):
    return subprocess.run(
        [sys.executable, str(HOOK)], input=json.dumps(payload), capture_output=True, text=True
    )


class MemoryNote(unittest.TestCase):
    def test_Codex_패치로_메모리에_써도_되새긴다(self):
        result = run({
            "hook_event_name": "PostToolUse",
            "tool_name": "apply_patch",
            "cwd": "/Users/x/.claude/projects/-Users-x-work",
            "tool_input": {"command": PATCH},
        })
        self.assertIn("기록 위치", result.stdout)


if __name__ == "__main__":
    unittest.main()
