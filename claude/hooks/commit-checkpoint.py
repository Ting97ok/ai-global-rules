#!/usr/bin/env python3
"""테스트·빌드가 통과했는데 미커밋 변경이 남아 있으면 커밋 체크포인트를 내라고 되먹인다.

한 사이클(RED → GREEN)이 닫힌 자리가 곧 체크포인트다(~/.claude/CLAUDE.md 「커밋 체크포인트」·「TDD」).
파일 개수로 재지 않는 이유는 여러 사이클이 한 파일에 쌓일 수 있어서다 — 「방금 초록이 됐다」가 실제 신호다.
"""
import json
import re
import subprocess
import sys

RUNNER = re.compile(
    r"\b(gradlew|gradle|mvnw|mvn|pytest|tox|jest|vitest|rspec"
    r"|cargo\s+(test|build|check)|go\s+(test|build)|dotnet\s+test"
    r"|(npm|yarn|pnpm|bun)\s+(run\s+)?(test|build|check|lint)"
    r"|make\s+(test|check|build))\b"
    r"|python3?\s+-m\s+(unittest|pytest)"
    r"|python3?\s+\S*test_\w+\.py")

FAILURE = re.compile(
    r"BUILD FAILED|\bFAILED\b|\d+\s+failed|Tests?\s+failed|FAILURE:|\berror:", re.IGNORECASE)


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return

    command = payload.get("tool_input", {}).get("command", "")
    if not RUNNER.search(command):
        return

    response = json.dumps(payload.get("tool_response", ""), ensure_ascii=False)
    if FAILURE.search(response):
        # 빨강은 체크포인트가 아니다. 다만 컨테이너가 못 뜬 것은 코드 버그처럼 보이므로 원인을 짚어 준다
        if re.search(r"Could not find a valid Docker|docker.*(not running|connection refused)|Testcontainers", response, re.IGNORECASE):
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse",
                  "additionalContext": "[참고] 테스트 실패 출력에 Docker·Testcontainers 가 보인다. 코드 버그로 단정하기 전에 Docker 가 떠 있는지 먼저 확인한다."}},
                  ensure_ascii=False))
        return

    status = subprocess.run(["git", "status", "--porcelain"],
                            capture_output=True, text=True, timeout=10)
    if status.returncode != 0:
        return
    changed = [line for line in status.stdout.splitlines() if line.strip()]
    if not changed:
        return

    root = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                          capture_output=True, text=True, timeout=10).stdout.strip()

    print(json.dumps({
        "decision": "block",
        "reason": (
            "커밋 체크포인트다. 테스트·빌드가 통과했고 미커밋 변경이 "
            f"{len(changed)}개 파일에 남아 있다 — 사이클 하나가 닫힌 자리다.\n"
            "다음 사이클의 RED 를 쓰지 말고 여기서 멈춘다:\n"
            "1. 작업 내역과 슬라이스 진행 표를 낸다\n"
            f"2. `cd {root} && git add {{경로}} && git commit -m ...` 를 성격별로 나눠 제시한다 "
            "(git add -A 금지, 커밋 간 파일이 겹치지 않게)\n"
            "3. 스스로 정한 값·문서에 없는 기본값·기존 테스트를 고친 것이 있으면 함께 알린다\n"
            "4. 사용자 커밋을 기다린다"
        ),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
