#!/usr/bin/env python3
"""테스트·빌드가 통과했는데 미커밋 변경이 남아 있으면 커밋 체크포인트를 내라고 되먹인다.

한 사이클(RED → GREEN)이 닫힌 자리가 곧 체크포인트다(~/.claude/CLAUDE.md 「커밋 체크포인트」·「TDD」).
파일 개수로 재지 않는 이유는 여러 사이클이 한 파일에 쌓일 수 있어서다 — 「방금 초록이 됐다」가 실제 신호다.
저장소는 명령 앞의 `cd {경로}` 를 따른다. 셸의 현재 폴더가 작업 저장소와 다를 때가 많다.

Codex 는 훅에 종료 코드를 주지 않는다. `tool_response` 가 출력 문자열 하나뿐이고 `transcript_path`
도 비어 있다. 그래서 이 훅의 실패 판정은 출력 문구에만 기댄다. 종료 코드로만 실패한 실행은 놓친다.
"""
import json
import os
import re
import subprocess
import sys

from testrun import as_text, called_paths, cd_targets, is_test_run, load_rows, run_failed


VARIABLE = re.compile(r"[$`]")
TEST_PATH = re.compile(r"\S*(?:test_\w+\.py|\.test\.sh)")


def target_dir(command, fallback):
    """명령 안의 마지막 `cd {경로}` 가 가리키는 폴더. 없으면 셸의 현재 폴더.

    같은 명령에서 대입하지 않은 변수는 셸을 돌려야 알 수 있다. 그때는 모른다고 답해 엉뚱한 저장소를 세지 않는다.
    """
    found = cd_targets(command)
    if not found:
        return fallback
    target = found[-1][1]
    return False if VARIABLE.search(target) else target


def related(command, root):
    """명령이 돌린 테스트 파일이 이 저장소 안에 있는지.

    셸의 현재 폴더가 작업 저장소와 다를 때가 있다. 그때 남의 저장소의 미커밋 변경을
    세지 않으려고 본다. 경로를 적지 않는 명령(`./gradlew test`)은 현재 폴더에서 도니 통과다.
    """
    paths = TEST_PATH.findall(command or "")
    if not paths:
        return True
    root = os.path.realpath(root)
    for p in paths:
        full = os.path.realpath(os.path.join(root, os.path.expanduser(p)))
        if full == root or full.startswith(root + os.sep):
            return True
    return False


def changed_files(porcelain):
    """`git status --porcelain -z` 출력에서 바뀐 경로를 낸다. 이름을 바꾼 것은 새 경로만 센다."""
    files, old_name_next = [], False
    for entry in porcelain.split("\0"):
        if old_name_next:
            old_name_next = False
        elif len(entry) > 3:
            files.append(entry[3:])
            old_name_next = entry[0] in "RC"
    return files


def touched(root, rel, edits):
    """이번 세션에서 고친 파일인지 본다. 추적하지 않는 폴더는 그 안의 파일을 고쳤는지 본다.

    세션을 시작하기 전부터 있던 변경으로 체크포인트를 내지 않기 위해서다.
    """
    full = os.path.realpath(os.path.join(root, rel))
    return full in edits or (rel.endswith("/") and any(e.startswith(full + os.sep) for e in edits))


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return

    command = payload.get("tool_input", {}).get("command", "")
    if not is_test_run(command):
        return

    response = as_text(payload.get("tool_response", ""))
    if run_failed(payload.get("tool_response", "")):
        # 빨강은 체크포인트가 아니다. 다만 컨테이너가 못 뜬 것은 코드 버그처럼 보이므로 원인을 짚어 준다
        if re.search(r"Could not find a valid Docker|docker.*(not running|connection refused)|Testcontainers", response, re.IGNORECASE):
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse",
                  "additionalContext": "[참고] 테스트 실패 출력에 Docker·Testcontainers 가 보인다. 코드 버그로 단정하기 전에 Docker 가 떠 있는지 먼저 확인한다."}},
                  ensure_ascii=False))
        return

    cwd = target_dir(command, payload.get("cwd") or None)
    if cwd is False:   # 변수라 어느 저장소인지 모른다
        return
    status = subprocess.run(["git", "status", "--porcelain", "-z"], cwd=cwd,
                            capture_output=True, text=True, timeout=10)
    if status.returncode != 0:
        return
    changed = changed_files(status.stdout)
    if not changed:
        return

    root = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=cwd,
                          capture_output=True, text=True, timeout=10).stdout.strip()
    if not root or not related(command, root):
        return
    transcript = payload.get("transcript_path") or ""
    if os.path.isfile(transcript):
        edits = {p for row in load_rows(transcript) for p in called_paths(row)}
        changed = [rel for rel in changed if touched(root, rel, edits)]
        if not changed:
            return

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
