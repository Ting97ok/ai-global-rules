#!/usr/bin/env python3
"""usage.py 테스트.

실행: python3 ~/.claude/skills/codex-cross-check/tests/test_usage.py
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOL = Path(__file__).resolve().parent.parent / "usage.py"


def row(primary, secondary, resets):
    return {"type": "event_msg", "payload": {"type": "token_count", "rate_limits": {
        "primary": {"used_percent": primary, "window_minutes": 300, "resets_at": resets},
        "secondary": {"used_percent": secondary, "window_minutes": 10080, "resets_at": resets}}}}


class Usage(unittest.TestCase):
    def test_마지막_기록의_남은_사용량을_읽는다(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "rollout.jsonl"
            path.write_text("\n".join(json.dumps(r) for r in [
                row(10.0, 1.0, 1789218738), {"type": "message"}, row(13.5, 2.0, 1789218738),
            ]), encoding="utf-8")
            out = subprocess.run([sys.executable, str(TOOL), str(path)],
                                 capture_output=True, text=True).stdout
            self.assertIn("86.5", out)
            self.assertIn("98", out)


if __name__ == "__main__":
    unittest.main()
