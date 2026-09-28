#!/usr/bin/env python3
"""crosscheck.py 테스트. 실제 Codex 는 호출하지 않는다.

실행: python3 ~/.claude/skills/codex-cross-check/tests/test_crosscheck.py
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOL = Path(__file__).resolve().parent.parent / "crosscheck.py"


def crosscheck(home, *args):
    """기록 폴더가 임시 폴더를 가리키도록 HOME 과 CODEX_HOME 을 바꿔 실행한다."""
    env = {**os.environ, "HOME": home, "CODEX_HOME": str(Path(home) / ".codex")}
    return subprocess.run([sys.executable, str(TOOL), *args], capture_output=True, text=True, env=env)


def note(home, item, round_, **fields):
    flags = [part for key, value in fields.items() for part in (f"--{key}", value)]
    return crosscheck(home, "note", "--session", "s1", "--item", item, "--round", round_, *flags)


class Report(unittest.TestCase):
    def test_note_로_기록한_항목을_report_가_항목별_차수별로_출력한다(self):
        with tempfile.TemporaryDirectory() as home:
            note(home, "창 이름", "1", claude="창 길이로 정한다", codex="키로 정한다",
                 split="이름을 정하는 기준", decision="Claude 안", reason="주간 창이 primary 로 온다")
            note(home, "기록 위치", "1", claude="세션마다 파일 하나", codex="같다", decision="일치")
            note(home, "창 이름", "2", claude="창 길이로 정한다", codex="동의한다", decision="Claude 안")
            out = crosscheck(home, "report", "--session", "s1").stdout
            self.assertTrue(out.startswith(
                "1. 창 이름\n"
                "   1차\n"
                "   - Claude: 창 길이로 정한다\n"
                "   - Codex: 키로 정한다\n"
                "   - 갈림: 이름을 정하는 기준\n"
                "   - 결정: Claude 안\n"
                "   - 근거: 주간 창이 primary 로 온다\n"
                "   2차\n"
                "   - Claude: 창 길이로 정한다\n"
                "   - Codex: 동의한다\n"
                "   - 결정: Claude 안\n"
                "2. 기록 위치\n"
                "   1차\n"
                "   - Claude: 세션마다 파일 하나\n"
                "   - Codex: 같다\n"
                "   - 결정: 일치\n"), out)


if __name__ == "__main__":
    unittest.main()
