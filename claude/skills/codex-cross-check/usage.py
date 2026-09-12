#!/usr/bin/env python3
"""Codex 의 남은 사용량을 읽는다. 교차 검증을 끝내고 보고할 때 쓴다.

Codex 는 대화마다 기록 파일(rollout)에 `rate_limits` 를 남긴다. 5시간 창과 7일 창 두 가지다.
인자로 기록 파일을 주면 그 파일을, 안 주면 가장 최근 파일을 본다.
"""
import json
import sys
import time
from pathlib import Path

SESSIONS = Path.home() / ".codex/sessions"


def newest():
    files = sorted(SESSIONS.rglob("rollout-*.jsonl"), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def find(value):
    """중첩된 어디에 있든 rate_limits 값을 꺼낸다."""
    if isinstance(value, dict):
        if "rate_limits" in value and isinstance(value["rate_limits"], dict):
            return value["rate_limits"]
        for v in value.values():
            got = find(v)
            if got:
                return got
    return None


def last_limits(path):
    found = None
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if '"rate_limits"' not in line:
                continue
            try:
                got = find(json.loads(line))
            except json.JSONDecodeError:
                continue
            if got:
                found = got
    return found


def line(name, window):
    if not isinstance(window, dict) or window.get("used_percent") is None:
        return None
    left = round(100 - float(window["used_percent"]), 1)
    reset = window.get("resets_at")
    when = time.strftime("%m/%d %H:%M", time.localtime(reset)) if reset else "모름"
    return f"{name} {left}% 남음 ({when} 초기화)"


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else newest()
    if not path or not Path(path).exists():
        print("Codex 기록을 찾지 못했다")
        return
    limits = last_limits(path)
    if not limits:
        print("이 기록에 사용량이 없다")
        return
    for name, key in (("5시간", "primary"), ("7일", "secondary")):
        got = line(name, limits.get(key))
        if got:
            print(got)


if __name__ == "__main__":
    main()
