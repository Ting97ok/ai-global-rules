#!/usr/bin/env python3
"""crosscheck.py 테스트. 실제 Codex 는 호출하지 않는다.

실행: python3 ~/.claude/skills/codex-cross-check/tests/test_crosscheck.py
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOL = Path(__file__).resolve().parent.parent / "crosscheck.py"
USAGE = TOOL.with_name("usage.py")


def env(home):
    """기록 폴더가 임시 폴더를 가리키도록 HOME 과 CODEX_HOME 을 바꾼다."""
    return {**os.environ, "HOME": home, "CODEX_HOME": str(Path(home) / ".codex")}


def crosscheck(home, *args):
    return subprocess.run([sys.executable, str(TOOL), *args], capture_output=True, text=True, env=env(home))


OLD, NEW = "00000000-0000-7000-8000-00000000000a", "00000000-0000-7000-8000-00000000000b"


def limits(used):
    return {"primary": {"used_percent": used, "window_minutes": 10080, "resets_at": 1791047840}, "secondary": None}


def turn(model, used):
    """Codex 기록 파일에 한 턴이 남기는 줄. 모델·추론 수준과 사용량이 들어 있다."""
    return "".join(json.dumps(row) + "\n" for row in [
        {"type": "turn_context", "payload": {"model": model, "effort": "high"}},
        {"type": "event_msg", "payload": {"type": "token_count", "rate_limits": limits(used)}}])


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

    def test_report_는_마지막_report_뒤에_기록한_항목만_출력한다(self):
        with tempfile.TemporaryDirectory() as home:
            note(home, "창 이름", "1", claude="창 길이로 정한다", codex="같다", decision="일치")
            crosscheck(home, "report", "--session", "s1")
            note(home, "기록 위치", "1", claude="세션마다 파일 하나", codex="같다", decision="일치")
            out = crosscheck(home, "report", "--session", "s1").stdout
            self.assertTrue(out.startswith("1. 기록 위치\n"), out)
            self.assertNotIn("창 이름", out)

    def test_report_는_마지막_줄에_마지막_호출의_usage_출력을_붙인다(self):
        # run 기록이 없으면 usage.py 를 인자 없이 실행해 가장 최근 Codex 기록을 읽는다
        for name, called in {"run 기록 있음": True, "run 기록 없음": False}.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as home:
                day = Path(home) / ".codex" / "sessions" / "2026" / "09" / "28"
                day.mkdir(parents=True)
                note(home, "창 이름", "1", claude="창 길이로 정한다", codex="같다", decision="일치")
                if called:
                    new = day / f"rollout-2026-09-28T10-00-00-{NEW}.jsonl"
                    crosscheck(home, "run", "--session", "s1", "--", sys.executable, "-c",
                               f"open({str(new)!r}, 'w').write({turn('gpt-6-sol', 7.0)!r})")
                # 다른 작업이 run 뒤에 남긴 더 최근 기록
                latest = day / f"rollout-2026-09-28T11-00-00-{OLD}.jsonl"
                latest.write_text(turn("gpt-5.6-sol", 50.0), encoding="utf-8")
                os.utime(latest, (2e9, 2e9))
                out = crosscheck(home, "report", "--session", "s1").stdout
                tail = subprocess.run([sys.executable, str(USAGE), *([NEW] if called else [])],
                                      capture_output=True, text=True, env=env(home)).stdout
                self.assertIn("gpt-6-sol" if called else "gpt-5.6-sol", tail)
                self.assertTrue(out.startswith("1. 창 이름\n"), out)
                self.assertTrue(out.endswith(tail), out)


class Run(unittest.TestCase):
    def test_run_은_감싼_명령의_출력을_캡처하지_않고_흘리며_종료_코드를_돌려준다(self):
        with tempfile.TemporaryDirectory() as home:
            signal = Path(home) / "signal"
            # 가짜 Codex 호출. 첫 줄을 낸 뒤 신호를 기다린다. 신호가 5초 안에 오지 않으면 9 로 끝난다
            fake = ("import os, sys, time\n"
                    "print('진행 중', flush=True)\n"
                    "for _ in range(50):\n"
                    f"    if os.path.exists({str(signal)!r}):\n"
                    "        print('Codex 답', flush=True)\n"
                    "        sys.exit(3)\n"
                    "    time.sleep(0.1)\n"
                    "sys.exit(9)\n")
            proc = subprocess.Popen([sys.executable, str(TOOL), "run", "--session", "s1", "--", sys.executable, "-c", fake],
                                    stdout=subprocess.PIPE, text=True, env=env(home))
            # 출력을 캡처했다가 끝에 내보내면 여기서 가짜 호출이 끝날 때까지 기다리게 되고 신호가 늦는다
            first = proc.stdout.readline()
            signal.touch()
            rest = proc.stdout.read()
            self.assertEqual(3, proc.wait())
            self.assertEqual("진행 중\n", first)
            self.assertIn("Codex 답", rest)

    def test_run_은_호출이_쓴_Codex_기록의_세션_ID_모델_추론_수준_사용량을_기록한다(self):
        # 새 작업은 기록 파일을 새로 만들고, 이어 묻기(--resume-last)는 앞선 파일에 이어 쓴다.
        # 호출이 기록을 남기지 못했으면 앞선 호출의 기록을 이번 호출로 기록하지 않는다
        for name, written in {"새 기록": NEW, "이어 쓴 기록": OLD, "기록 없음": None}.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as home:
                day = Path(home) / ".codex" / "sessions" / "2026" / "09" / "28"
                day.mkdir(parents=True)
                old = day / f"rollout-2026-09-28T09-00-00-{OLD}.jsonl"
                old.write_text(turn("gpt-5.6-sol", 1.0), encoding="utf-8")
                os.utime(old, (1e9, 1e9))
                target = day / f"rollout-2026-09-28T10-00-00-{NEW}.jsonl" if written == NEW else old
                fake = f"open({str(target)!r}, 'a').write({turn('gpt-6-sol', 7.0)!r})" if written else "pass"
                crosscheck(home, "run", "--session", "s1", "--", sys.executable, "-c", fake)
                log = Path(home) / ".claude" / "crosscheck" / "s1.jsonl"
                rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()] if log.exists() else []
                expected = [{"run": {"codex_session": written, "model": "gpt-6-sol", "effort": "high",
                                     "rate_limits": limits(7.0)}}] if written else []
                self.assertEqual(expected, rows)


if __name__ == "__main__":
    unittest.main()
