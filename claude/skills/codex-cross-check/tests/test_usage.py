#!/usr/bin/env python3
"""usage.py 테스트.

실행: python3 ~/.claude/skills/codex-cross-check/tests/test_usage.py
"""
import json
import os
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


def window_row(minutes):
    """창이 하나뿐인 기록. 주간 창 하나만 쓰는 계정은 primary 에 주간 창이 오고 secondary 는 비어 있다."""
    return {"type": "event_msg", "payload": {"type": "token_count", "rate_limits": {
        "primary": {"used_percent": 7.0, "window_minutes": minutes, "resets_at": 1791047840},
        "secondary": None}}}


def context_row(model, effort):
    return {"type": "turn_context", "payload": {"model": model, "effort": effort}}


def usage(rows):
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "rollout.jsonl"
        path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
        return subprocess.run([sys.executable, str(TOOL), str(path)], capture_output=True, text=True).stdout


class Usage(unittest.TestCase):
    def test_창_이름은_창_길이로_정하고_빈_창은_출력하지_않는다(self):
        for minutes, name in {300: "5시간", 10080: "주간", 60: "60분"}.items():
            with self.subTest(minutes=minutes):
                out = usage([window_row(minutes)])
                lines = [l for l in out.splitlines() if "남음" in l]
                self.assertEqual(1, len(lines), out)
                self.assertTrue(lines[0].startswith(f"{name} "), out)

    def test_첫_줄에_마지막_턴의_모델과_추론_수준을_출력한다(self):
        # 같은 기록에서 이어 물으면 턴마다 모델이 바뀔 수 있다. 옛 기록에는 턴 기록이 없고 rate_limits 가 null 이다
        turns = [context_row("gpt-5.6-sol", "medium"), context_row("gpt-6-sol", "high")]
        old = {"type": "event_msg", "payload": {"type": "token_count", "rate_limits": None}}
        cases = {
            "사용량 있음": ([*turns, window_row(10080)], "모델 gpt-6-sol, 추론 수준 high"),
            "사용량 없음": (turns, "모델 gpt-6-sol, 추론 수준 high"),
            "옛 기록": ([old], "모델 모름, 추론 수준 모름"),
        }
        for name, (rows, first) in cases.items():
            with self.subTest(name=name):
                out = usage(rows)
                self.assertEqual(first, out.splitlines()[0], out)

    def test_인자가_파일이_아니면_CODEX_HOME_에서_그_세션의_기록을_찾는다(self):
        wanted, newer = "00000000-0000-7000-8000-000000000001", "00000000-0000-7000-8000-000000000002"
        with tempfile.TemporaryDirectory() as home:
            day = Path(home) / "sessions" / "2026" / "09" / "28"
            day.mkdir(parents=True)
            (day / f"rollout-2026-09-28T15-18-38-{wanted}.jsonl").write_text(
                json.dumps(context_row("gpt-6-sol", "high")), encoding="utf-8")
            # 가장 최근 기록을 읽으면 틀리게 하려고 다른 세션의 기록을 더 최근으로 둔다
            recent = day / f"rollout-2026-09-28T16-00-00-{newer}.jsonl"
            recent.write_text(json.dumps(context_row("gpt-5.6-sol", "medium")), encoding="utf-8")
            os.utime(recent, (2e9, 2e9))
            out = subprocess.run([sys.executable, str(TOOL), wanted], capture_output=True, text=True,
                                 env={**os.environ, "CODEX_HOME": home}).stdout
            self.assertEqual("모델 gpt-6-sol, 추론 수준 high", out.splitlines()[0], out)

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
