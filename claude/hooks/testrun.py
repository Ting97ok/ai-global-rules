#!/usr/bin/env python3
"""테스트·빌드 실행을 알아보는 판정. commit-checkpoint 와 stop-check 가 함께 쓴다.

RUNNER 는 명령 문자열에, FAILURE 는 그 명령의 출력에 건다.
실패 여부를 종료 코드로 보지 않는 이유는 파이프(`| tail`)를 물리면 0 으로 끝나서다.
"""
import re

RUNNER = re.compile(
    r"\b(gradlew|gradle|mvnw|mvn|pytest|tox|jest|vitest|rspec"
    r"|cargo\s+(test|build|check)|go\s+(test|build)|dotnet\s+test"
    r"|(npm|yarn|pnpm|bun)\s+(run\s+)?(test|build|check|lint)"
    r"|make\s+(test|check|build))\b"
    r"|python3?\s+-m\s+(unittest|pytest)"
    r"|python3?\s+\S*test_\w+\.py")

FAILURE = re.compile(
    r"BUILD FAILED|\bFAILED\b|\d+\s+failed|Tests?\s+failed|FAILURE:|\berror:", re.IGNORECASE)
