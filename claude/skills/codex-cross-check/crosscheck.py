#!/usr/bin/env python3
"""교차 검증의 Codex 호출과 항목별 요지를 기록하고 보고용 요약을 출력한다. codex-cross-check 「진행」·「보고」에서 사용한다.

  run --session ID -- 명령…
      Codex 호출을 실행한다. 출력은 캡처하지 않고 종료 코드를 그대로 반환한다.
      호출이 끝나면 호출을 시작한 뒤 수정된 Codex 기록 파일에서 세션 ID·모델·추론 수준·사용량을 읽어 기록한다.
  note --session ID --item 제목 --round 차수 [--claude --codex --split --decision --reason]
      항목의 한 차수에서 Claude 요지·Codex 요지·갈린 곳·결정·근거를 기록한다.
  report --session ID
      마지막 report 뒤에 기록한 항목을 항목별로 출력하고 마지막 줄에 마지막 호출의 usage.py 출력을 붙인다.

기록은 ~/.claude/crosscheck/{Claude 세션 ID}.jsonl 에 한 줄씩 추가한다. 대화 원문은 기록하지 않는다.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import usage

# note 가 받는 요지와 report 가 붙이는 이름
FIELDS = (("claude", "Claude"), ("codex", "Codex"), ("split", "갈림"), ("decision", "결정"), ("reason", "근거"))


def log_path(session):
    return Path.home() / ".claude" / "crosscheck" / f"{session}.jsonl"


def write(session, row):
    path = log_path(session)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def run(args):
    started = time.time()
    # 출력을 캡처하지 않는다. Codex 의 진행 줄이 호출한 쪽 화면에 바로 나와야 한다
    code = subprocess.run(args.command).returncode
    # 이 호출이 쓴 기록. 새 작업은 파일을 새로 만들고 이어 묻기는 앞선 파일에 이어 쓴다
    written = [p for p in usage.SESSIONS.rglob("rollout-*.jsonl") if p.stat().st_mtime >= started]
    if written:
        path = max(written, key=lambda p: p.stat().st_mtime)
        context = usage.last_context(path)
        write(args.session, {"run": {"codex_session": path.stem[-36:], "model": context.get("model"),
                                     "effort": context.get("effort"), "rate_limits": usage.last_limits(path)}})
    sys.exit(code)


def note(args):
    row = {"item": args.item, "round": args.round}
    row.update({key: getattr(args, key) for key, _ in FIELDS if getattr(args, key)})
    write(args.session, row)


def report(args):
    rows = [json.loads(line) for line in log_path(args.session).read_text(encoding="utf-8").splitlines()]
    # 앞선 report 가 출력한 항목은 다시 출력하지 않는다. 표시 행 뒤의 기록만 읽는다
    start = max((i + 1 for i, row in enumerate(rows) if row.get("report")), default=0)
    items = {}
    for row in rows[start:]:
        if "item" in row:
            items.setdefault(row["item"], []).append(row)
    for number, (item, rounds) in enumerate(items.items(), 1):
        print(f"{number}. {item}")
        for row in rounds:
            print(f"   {row['round']}차")
            for key, label in FIELDS:
                if key in row:
                    print(f"   - {label}: {row[key]}")
    # 마지막 줄은 마지막 호출의 모델·사용량이다. 호출 기록이 없으면 usage.py 가 가장 최근 Codex 기록을 읽는다
    calls = [row["run"]["codex_session"] for row in rows if "run" in row]
    usage_out = subprocess.run([sys.executable, str(Path(__file__).with_name("usage.py")), *calls[-1:]],
                               capture_output=True, text=True).stdout
    print(usage_out, end="")
    write(args.session, {"report": True})


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="action", required=True)
    p = commands.add_parser("run")
    p.add_argument("--session", required=True)
    p.add_argument("command", nargs="+")
    p.set_defaults(func=run)
    p = commands.add_parser("note")
    p.add_argument("--session", required=True)
    p.add_argument("--item", required=True)
    p.add_argument("--round", required=True)
    for key, _ in FIELDS:
        p.add_argument(f"--{key}")
    p.set_defaults(func=note)
    p = commands.add_parser("report")
    p.add_argument("--session", required=True)
    p.set_defaults(func=report)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
