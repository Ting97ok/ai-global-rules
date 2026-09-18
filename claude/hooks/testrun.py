#!/usr/bin/env python3
"""테스트·빌드 실행을 알아보는 판정. commit-checkpoint 와 stop-check 가 함께 쓴다.

RUNNER 는 명령 문자열에, FAILURE 는 그 명령의 출력에 건다.
실패 여부를 종료 코드로 보지 않는 이유는 파이프(`| tail`)를 물리면 0 으로 끝나서다.
"""
import json
import os
import re
import string

# 명령 첫머리에만 맞춘다. 파일 이름 속 도구 이름(build.gradle·gradle/)은 실행이 아니다
RUNNER = re.compile(
    r"(?:\w+=\S*\s+)*(?:npx\s+)?(?:\S*/)?"
    r"((gradlew|gradle|mvnw|mvn|pytest|tox|jest|vitest|rspec)\b"
    r"|(cargo\s+(test|build|check)|go\s+(test|build)|dotnet\s+test)\b"
    r"|(npm|yarn|pnpm|bun)\s+(run\s+)?(test|build|check|lint)\b"
    r"|make\s+(test|check|build)\b"
    r"|python3?\s+-m\s+(unittest|pytest)"
    r"|python3?\s+\S*test_\w+\.py)")
COMMAND_BREAK = re.compile(r"&&|\|\||[;|()\n]")
# for f in tests/test_*.py; do python3 "$f"; done 처럼 테스트 파일을 돌며 실행하는 꼴
TEST_LOOP = re.compile(r"\bfor\s+(\w+)\s+in\s+[^;\n]*\btest_[^;\n]*[;\n]\s*do\s+(?:\S*/)?python3?\s+\"?\$\{?\1\b")

# 실행조차 못 한 것도 실패다. 통과로 세면 「테스트가 통과했다」고 단정하게 된다
FAILURE = re.compile(
    r"BUILD FAILED|\bFAILED\b|\d+\s+failed|Tests?\s+failed|FAILURE:|\berror:"
    r"|command not found|No such file or directory|ModuleNotFoundError"
    r"|can't open file|is not recognized as", re.IGNORECASE)


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
    if TEST_LOOP.search(skeleton):
        return True
    skeleton = QUOTED.sub(" ", skeleton)
    return any(RUNNER.match(part.strip()) for part in COMMAND_BREAK.split(skeleton))


REDIRECT = re.compile(r"(?<![-=])>>?\s*['\"]?([\w./~+$-]+\.(?:md|html))")
TEE = re.compile(r"\btee\b\s+(?:-a\s+)?['\"]?([\w./~+$-]+\.(?:md|html))")
SED_I = re.compile(r"\bsed\b[^|;]*?-i[^|;]*?([\w./~+$-]+\.(?:md|html))")
# 제자리 옵션 i 앞에는 한 글자 옵션만 붙는다. -Mstrict 의 i 는 모듈 이름이다
PERL_I = re.compile(r"\bperl\b[^|;]*?\s-[\dlnpaws]*i[^|;]*?([\w./~+$-]+\.(?:md|html))")
NODE_WRITE = re.compile(r"\bwriteFile(?:Sync)?\(\s*['\"`]([^'\"`]+\.(?:md|html))['\"`]")
PY_WRITE = re.compile(
    r"open\(\s*['\"]([^'\"]+\.(?:md|html))['\"]\s*,\s*['\"][wax]"
    r"|Path\(\s*['\"]([^'\"]+\.(?:md|html))['\"]\s*\)\s*\.(?:write_text|write_bytes|open\(\s*['\"][wax])")
SHELL_WORD = r"""(?:"[^"]*"|'[^']*'|[^\s;&|<>()"'])+"""
COPY_MOVE = re.compile(rf"(?:^|[;&|(])\s*(?:cp|mv)((?:[ \t]+{SHELL_WORD})+)", re.M)
CD = re.compile(rf"(?:^|[;&|(])\s*cd[ \t]+({SHELL_WORD})", re.M)
ASSIGN = re.compile(r"""(?:^|[\s;&|(])(\w+)=("[^"]*"|'[^']*'|[^\s;&|)]*)""")
HEREDOC_BODY = re.compile(r"<<-?\s*(['\"]?)(\w+)\1[^\n]*\n(.*?)^\s*\2\b", re.S | re.M)


def without_heredoc_bodies(command):
    """heredoc 본문의 글자를 공백으로 바꾼다. 글자 위치와 줄바꿈은 그대로 둔다."""
    chars = list(command)
    for m in HEREDOC_BODY.finditer(command):
        for i in range(m.start(3), m.end(3)):
            if chars[i] != "\n":
                chars[i] = " "
    return "".join(chars)


def shell_env(shell):
    """환경 변수에 같은 명령에서 대입한 변수를 더한다."""
    env = dict(os.environ)
    for name, value in ASSIGN.findall(shell):
        env[name] = string.Template(value.strip("\"'")).safe_substitute(env)
    return env


def expand_word(word, env):
    """셸 낱말 하나의 따옴표를 떼고 변수와 ~ 를 푼다. 풀지 못한 변수는 그대로 남는다."""
    return os.path.expanduser(string.Template(re.sub(r"[\"']", "", word)).safe_substitute(env))


def cd_targets(command):
    """명령 안의 cd 가 가리키는 폴더를 (글자 위치, 경로) 로 나온 순서대로 낸다. heredoc 본문은 보지 않는다."""
    shell = without_heredoc_bodies(command or "")
    env = shell_env(shell)
    return [(m.start(), expand_word(m.group(1), env)) for m in CD.finditer(shell)]


def written_paths(command, cwd=""):
    """셸 명령이 문서를 고치는 것으로 보이면 그 경로를 낸다.

    문서 훅은 Write·Edit 도구에만 걸려서, 셸로 고치면 그대로 빠져나간다.
    리디렉션·tee·sed -i·perl -i 는 대상이 명령에 드러난다. 파이썬 open(…, "w")·Path(…).write_text 와
    Node writeFile 은 대상 자리에 문서 이름이 있을 때만 센다. 읽기만 하는 문서 이름까지 세면 분석 스크립트가 막힌다.
    cp·mv 는 임시 초안처럼 문서가 아닌 파일을 문서 자리에 넣을 때만 센다. 문서끼리 옮기거나 복사하는 것은 새로 쓰는 일이 아니다.
    같은 명령에서 대입한 변수와 환경 변수는 풀어서 본다. 임시 폴더를 변수로 적어도 임시 폴더로 알아보게 하려는 것이다.
    상대 경로는 그 쓰기보다 앞에 있는 cd 를 따라 푼다. cd 로 임시 폴더에 들어가 쓴 메모를 저장소 문서로 보지 않기 위해서다.
    셸 명령은 heredoc 본문을 뺀 글자에서 찾는다. 스크립트 속 문자열을 셸 쓰기로 보지 않기 위해서다. 파이썬·Node 쓰기는 본문에서 찾는다.
    """
    if not command:
        return []
    shell = without_heredoc_bodies(command)
    env = shell_env(shell)
    cds = cd_targets(command)

    def where(pos, path):
        """명령의 pos 자리에서 path 가 가리키는 경로."""
        here = cwd
        for start, target in cds:
            if start < pos:
                here = os.path.join(here, target)
        return os.path.join(here, expand_word(path, env)) if here else expand_word(path, env)

    scans = ((REDIRECT, shell), (TEE, shell), (SED_I, shell), (PERL_I, shell), (NODE_WRITE, command), (PY_WRITE, command))
    found = [where(m.start(), p) for pattern, text in scans for m in pattern.finditer(text) for p in m.groups() if p]
    for m in COPY_MOVE.finditer(shell):
        words = [w for w in re.findall(SHELL_WORD, m.group(1)) if not w.startswith("-")]
        *sources, target = words or [""]
        fresh = [s for s in sources if not is_document(where(m.start(), s))]
        if fresh and target.endswith((".md", ".html")):
            found.append(where(m.start(), target))
        elif target.endswith("/") or os.path.isdir(where(m.start(), target)):
            found += [where(m.start(), os.path.join(target, os.path.basename(s)))
                      for s in fresh if s.endswith((".md", ".html"))]
    return found


AI_CONFIG_DIRS = {".claude", ".codex", ".agents", ".gemini", ".cursor"}
AI_RULE_FILES = {"CLAUDE.md", "AGENTS.md", "GEMINI.md"}
TEMP_ROOTS = ("/tmp/", "/private/tmp/")
# 빌드 도구·프레임워크가 화면 템플릿·정적 파일·산출물을 두는 폴더 이름. 특정 프로젝트의 경로가 아니다
CODE_DIRS = {"resources", "public", "static", "templates", "assets", "build", "out", "dist", "target", "node_modules"}
APP_ROOT = re.compile(r"""<div\b[^>]*\bid\s*=\s*(['"])(?:root|app)\1""", re.I)
MODULE_SCRIPT = re.compile(r"""<script\b(?=[^>]*\btype\s*=\s*(['"])module\1)[^>]*>""", re.I)


def is_document(path, text=None):
    """사람이 읽을 문서 파일인지 본다. doc-skill-guard 와 prose-check 가 함께 쓴다.

    `docs/` 같은 경로 규약은 프로젝트마다 달라서 확장자로 가른다.
    AI 설정·규칙 파일과 임시 폴더의 파일은 사람이 읽을 문서가 아니다.
    `.html` 은 화면 템플릿이나 앱 진입 파일일 수 있어 도구 규약 폴더 안이거나 앱을 띄우는 내용이면 뺀다.
    `.md` 에는 폴더 조건을 걸지 않는다. 리소스 폴더 안에 API 설계 문서를 두는 저장소가 있어서다.
    text 는 아직 없는 파일에 쓰려는 내용이다. 없으면 파일을 읽는다.
    """
    if not path or not path.endswith((".md", ".html")):
        return False
    p = path.replace("\\", "/")
    parts = p.split("/")
    if parts[-1] in AI_RULE_FILES or AI_CONFIG_DIRS & set(parts) or p.startswith(TEMP_ROOTS):
        return False
    if not p.endswith(".html"):
        return True
    if CODE_DIRS & set(parts[:-1]):
        return False
    if text is None and os.path.isfile(path):
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError:
            text = ""
    return not (APP_ROOT.search(text or "") or MODULE_SCRIPT.search(text or ""))


def load_rows(path):
    """대화 기록 파일(JSONL)을 줄마다 읽는다. 읽지 못한 줄과 파일은 건너뛴다."""
    rows = []
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    rows.append(json.loads(line))
                except (json.JSONDecodeError, ValueError):
                    continue
    except OSError:
        return []
    return rows


def human_message(row):
    """Claude 기록에서 사용자가 직접 보낸 메시지면 그 글을 낸다. 스킬 본문·작업 알림·컴팩트 요약은 뺀다."""
    content = (row.get("message") or {}).get("content")
    if row.get("type") != "user" or row.get("isMeta") or row.get("isCompactSummary") or not isinstance(content, str):
        return ""
    return "" if content.lstrip().startswith("<task-notification>") else content


def answers(row):
    """질문 창에서 사용자가 고른 답을 낸다. 질문 문구는 뺀다."""
    result = row.get("toolUseResult")
    values = result.get("answers") if isinstance(result, dict) else None
    if row.get("type") != "user" or not isinstance(values, dict):
        return ""
    return "\n".join(a if isinstance(a, str) else "\n".join(a) for a in values.values())


def said(row, phrase):
    """그 줄이 사용자 메시지나 질문 창 답이고, 한 줄에 phrase 만 따로 썼는지 본다.

    「캐묻기 생략은 하지 마」 같은 문장은 세지 않는다.
    """
    text = human_message(row) + "\n" + answers(row)
    return any(line.strip() == phrase for line in text.splitlines())


def said_since_last_message(rows, phrase):
    """마지막 사용자 메시지와 그 뒤 질문 창 답에서 phrase 를 말했는지 본다. 앞선 요청에서 한 말은 다음 요청에 쓰지 않는다."""
    last = max((i for i, r in enumerate(rows) if human_message(r)), default=0)
    return any(said(r, phrase) for r in rows[last:])


PATCH_FILE = re.compile(r"^\*\*\* (?:Add|Update) File: (.+)$", re.M)


def edited_paths(payload):
    """이번 편집이 건드린 파일 경로.

    Claude 는 tool_input.file_path 로 준다. Codex 는 apply_patch 의 패치 본문으로 줘서
    `*** Add File:` `*** Update File:` 줄에서 뽑고 cwd 를 앞에 붙인다.
    """
    tool_input = payload.get("tool_input") or {}
    one = tool_input.get("file_path")
    if one:
        return [one]
    command = tool_input.get("command") or ""
    cwd = payload.get("cwd") or ""
    found = PATCH_FILE.findall(command) or written_paths(command, cwd)
    return [os.path.join(cwd, p.strip()) if cwd else p.strip() for p in found]


def failed_calls(rows):
    """오류로 끝난 도구 호출의 id. 실패한 쓰기를 한 일로 세지 않으려고 본다."""
    failed = set()
    for row in rows:
        content = (row.get("message") or {}).get("content")
        if row.get("type") != "user" or not isinstance(content, list):
            continue
        for b in content:
            if isinstance(b, dict) and b.get("type") == "tool_result" and b.get("is_error"):
                failed.add(b.get("tool_use_id"))
    return failed


def called_paths(row, skip=()):
    """Claude 기록 한 줄의 도구 호출이 쓰거나 고친 파일의 실제 경로. 셸로 고친 것도 센다.

    skip 에 든 id 의 호출은 뺀다. 오류로 끝난 호출을 거를 때 쓴다.
    """
    content = (row.get("message") or {}).get("content")
    if row.get("type") != "assistant" or not isinstance(content, list):
        return []
    paths = []
    for b in content:
        if not isinstance(b, dict) or b.get("type") != "tool_use" or b.get("id") in skip:
            continue
        given = b.get("input") or {}
        if b.get("name") in ("Write", "Edit", "MultiEdit"):
            paths.append(given.get("file_path"))
        elif b.get("name") == "Bash":
            paths += edited_paths({"tool_input": {"command": given.get("command") or ""}, "cwd": row.get("cwd")})
    return [os.path.realpath(os.path.expanduser(p)) for p in paths if p]


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
