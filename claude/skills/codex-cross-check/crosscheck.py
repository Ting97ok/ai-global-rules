#!/usr/bin/env python3
"""교차 검증에서 항목마다 주고받은 요지를 기록하고 보고용 요약을 출력한다. codex-cross-check 「보고」에 쓴다.

기록은 ~/.claude/crosscheck/{Claude 세션 ID}.jsonl 에 한 줄씩 쌓는다. 대화 원문은 기록하지 않는다.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

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
    # 출력을 캡처하지 않는다. Codex 의 진행 줄이 호출한 쪽 화면에 바로 나와야 한다
    sys.exit(subprocess.run(args.command).returncode)


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
        items.setdefault(row["item"], []).append(row)
    for number, (item, rounds) in enumerate(items.items(), 1):
        print(f"{number}. {item}")
        for row in rounds:
            print(f"   {row['round']}차")
            for key, label in FIELDS:
                if key in row:
                    print(f"   - {label}: {row[key]}")
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
