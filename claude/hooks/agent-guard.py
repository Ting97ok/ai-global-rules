#!/usr/bin/env python3
"""PreToolUse(Agent) — 서브에이전트 호출에 model 을 지정하면 막는다.

~/.claude/CLAUDE.md 「작업 성향 · 모델」: 세션 모델을 상속시킨다. 프롬프트 캐시는 모델 단위라
다른 모델을 지정하면 매번 캐시를 놓치고, 모델 선택은 사용자 설정의 권한이다.
"""
import json
import sys


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return
    inp = payload.get("tool_input", {}) or {}
    model = inp.get("model")
    if model:
        print(f"[agent-guard] 서브에이전트에 model={model} 을 지정하지 않는다. "
              "세션 모델을 상속시킨다 (프롬프트 캐시는 모델 단위, 모델 선택은 사용자 권한). "
              "model 을 빼고 다시 호출한다.", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
