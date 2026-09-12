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


def as_text(value):
    """도구 응답을 읽는 그대로의 문자열로 만든다.

    json.dumps 로 감싸면 줄바꿈이 두 글자 `\\n` 이 돼서 「FAILED」 앞 글자가 n 이 된다.
    그러면 낱말 경계가 깨져 실패를 놓친다.
    """
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return "\n".join(as_text(v) for v in value.values())
    if isinstance(value, list):
        return "\n".join(as_text(v) for v in value)
    return str(value)


HEREDOC = re.compile(r"<<-?\s*'?\"?(\w+)'?\"?.*?^\1\b", re.S | re.M)
QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"", re.S)


def is_test_run(command):
    """명령이 실제로 테스트·빌드를 돌리는지 본다.

    인용 부호와 heredoc 안의 글자는 실행이 아니라 텍스트다. 프롬프트나 파일 내용에
    테스트 명령이 적혀 있어도 실행으로 세지 않는다.
    """
    skeleton = HEREDOC.sub(" ", command or "")
    skeleton = QUOTED.sub(" ", skeleton)
    return bool(RUNNER.search(skeleton))


PATCH_FILE = re.compile(r"^\*\*\* (?:Add|Update) File: (.+)$", re.M)


def edited_paths(payload):
    """이번 편집이 건드린 파일 경로.

    Claude 는 tool_input.file_path 로 준다. Codex 는 apply_patch 의 패치 본문으로 줘서
    `*** Add File:` `*** Update File:` 줄에서 뽑고 cwd 를 앞에 붙인다.
    """
    import os

    tool_input = payload.get("tool_input") or {}
    one = tool_input.get("file_path")
    if one:
        return [one]
    cwd = payload.get("cwd") or ""
    return [os.path.join(cwd, p.strip()) if cwd else p.strip()
            for p in PATCH_FILE.findall(tool_input.get("command") or "")]


CODEX_CMD = re.compile(r'cmd\s*:\s*"((?:[^"\\\\]|\\\\.)*)"')


def shell_command(raw):
    """셸 호출 기록에서 실제 명령을 꺼낸다.

    Claude 는 명령 문자열을 그대로 준다. Codex 는 `tools.exec_command({cmd:"…"})` 로 감싸서
    명령이 따옴표 안에 들어간다. 감싼 채로 두면 인용 구간을 지우는 판정이 명령까지 지운다.
    한 호출에 명령이 여럿 담기므로 모두 꺼내 줄바꿈으로 잇는다.
    """
    found = CODEX_CMD.findall(raw or "")
    if not found:
        return raw or ""
    return "\n".join(c.replace('\\"', '"').replace("\\\\", "\\") for c in found)


EXIT_CODE = re.compile(r'"exit_code"\s*:\s*(\d+)')


def run_failed(output):
    """실행 결과가 실패인지 본다.

    Codex 는 출력을 JSON 조각으로 감싸면서 종료 코드를 남긴다. 그 안의 줄바꿈은 두 글자가 되어
    문구 검사가 낱말 경계를 놓치므로, 종료 코드가 있으면 그것을 먼저 본다.
    """
    text = as_text(output)
    codes = EXIT_CODE.findall(text)
    if codes:
        return any(c != "0" for c in codes)
    return bool(FAILURE.search(text))


REDIRECT = re.compile(r">>?\s*['\"]?([\w./~+$-]+\.(?:md|html))")
TEE = re.compile(r"\btee\b\s+(?:-a\s+)?['\"]?([\w./~+$-]+\.(?:md|html))")
SED_I = re.compile(r"\bsed\b[^|;]*?-i[^|;]*?([\w./~+-]+\.(?:md|html))")
PY_WRITE = re.compile(r"write_text|writelines|\.write\(|open\([^)]*['\"][wa]")
ANY_DOC = re.compile(r"[\w./~+-]+\.(?:md|html)")


def written_paths(command):
    """셸 명령이 문서를 고치는 것으로 보이면 그 경로를 낸다.

    문서 훅은 Write·Edit 도구에만 걸려서, 셸로 고치면 그대로 빠져나간다.
    리디렉션·tee·sed -i 는 대상이 명령에 드러나고, 파이썬으로 쓸 때는 경로가 본문 안에 있다.
    """
    if not command:
        return []
    found = REDIRECT.findall(command) + TEE.findall(command) + SED_I.findall(command)
    if PY_WRITE.search(command):
        found += ANY_DOC.findall(command)
    return found
