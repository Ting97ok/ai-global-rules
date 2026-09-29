#!/usr/bin/env python3
"""Codex 의 모델·추론 수준과 남은 사용량을 출력한다. 교차 검증을 마치고 보고할 때 사용한다.

Codex 는 대화마다 기록 파일(rollout)을 생성한다. 턴마다 `turn_context` 에 모델과 추론 수준을, `rate_limits` 에 사용량 한도를 기록한다.
첫 줄은 마지막 턴의 모델과 추론 수준이다. 턴 기록이 없는 옛 기록은 「모름」으로 출력한다.
이어서 값이 있는 한도마다 남은 비율과 초기화 시각을 출력한다. 한도 이름은 한도 기간(`window_minutes`)으로 결정한다.
인자가 파일이면 그 파일을, 파일이 아니면 이름 끝이 그 Codex 세션 ID 인 기록을, 인자가 없으면 가장 최근 기록을 읽는다.
기록 폴더는 `CODEX_HOME`(없으면 ~/.codex) 아래 sessions 다.
"""
import json
import os
import sys
import time
from pathlib import Path

SESSIONS = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "sessions"


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


def last_context(path):
    """마지막 턴의 turn_context. 같은 기록에서 이어 물으면 턴마다 모델이 바뀔 수 있다."""
    found = {}
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if '"turn_context"' not in line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("type") == "turn_context":
                found = row.get("payload") or {}
    return found


def line(window):
    if not isinstance(window, dict) or window.get("used_percent") is None:
        return None
    minutes = window.get("window_minutes")
    name = {300: "5시간", 10080: "주간"}.get(minutes, f"{minutes}분")
    left = round(100 - float(window["used_percent"]), 1)
    reset = window.get("resets_at")
    when = time.strftime("%m/%d %H:%M", time.localtime(reset)) if reset else "모름"
    return f"{name} {left}% 남음 ({when} 초기화)"


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    # 인자가 파일이 아니면 Codex 세션 ID 다. 기록 파일 이름 끝에 세션 ID 가 붙는다
    if arg is None:
        path = newest()
    elif Path(arg).is_file():
        path = Path(arg)
    else:
        path = next(SESSIONS.rglob(f"rollout-*-{arg}.jsonl"), None)
    if not path:
        print("Codex 기록을 찾지 못했다")
        return
    context = last_context(path)
    print(f"모델 {context.get('model', '모름')}, 추론 수준 {context.get('effort', '모름')}")
    limits = last_limits(path)
    if not limits:
        print("이 기록에 사용량이 없다")
        return
    for key in ("primary", "secondary"):
        got = line(limits.get(key))
        if got:
            print(got)


if __name__ == "__main__":
    main()
