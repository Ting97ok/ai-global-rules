#!/usr/bin/env python3
"""Stop — 답변을 끝내기 전에 마지막 답변의 bash 블록을 검사한다. ~/.claude/CLAUDE.md 「작업 성향 · 보여주기와 명령」.

반려 대상 (decision: block 으로 답변을 반려해 수정하게 한다):
  1. 사용자에게 요청하는 조회 명령. 첫 줄이 cat·less·more·head·tail·bat·sed -n·grep 으로 시작하고(앞의 `cd … &&` 는
     제외한다) 2번의 커밋·푸시·PR 명령이 없는 블록. 확인해야 할 내용은 답변에 직접 포함한다.
  2. 커밋·푸시·PR 명령(git add/commit/push, gh pr create/edit/ready/merge/comment)을 제시하면서
     이번 턴에 상태 확인(git status / git log / git diff / git branch / gh pr view|list)을 실제로 실행하지 않은 것.
     `git -C 경로 status` 처럼 경로를 지정한 상태 확인도 포함한다.
  3. 이번 턴의 마지막 테스트 실행이 실패했는데 2번의 커밋·푸시·PR 명령을 제시하는 것. 한 사이클은 GREEN 까지 진행한다(「TDD」).
     내용이 없는 빈 커밋(--allow-empty)은 제외한다. 브랜치를 열어 드래프트 PR 을 생성하는 자리라 사이클과 무관하다.
     한 턴에서 RED → 수정 → GREEN 을 진행하는 것이 정상이라 마지막 실행만 확인한다.
  4. 현재 대화에서 수정한 문서가 커밋에 새 파일이거나 추가·삭제 50줄 이상으로 포함되는데, 마지막으로 수정한 뒤
     그 문서의 독자 테스트(사본 폴더 이름이 reader-test-{문서 이름} 인 Codex 작업)를 실행하지 않은 것.
     doc-writing 「처음 읽는 독자로 확인한다」. 결과가 아니라 실행 여부만 확인하되, 오류로 끝난 호출과 완료 알림이 없는
     백그라운드 호출은 집계하지 않는다. 사용자가 마지막 메시지에서 한 줄에 「독자 테스트 생략」이라고 작성했으면 통과시킨다.
  5. 커밋 명령을 제시한 답 뒤에 받은 요청에 PR 댓글 판단 없이 답하는 것. 체크포인트에 대한 반박일 수 있어서다.
     「댓글」을 기록했거나 `gh pr comment` 를 실행했으면 통과한다. 요청 뒤에 사용자가 `!` 명령을 실행했으면 PR 댓글 판단을 요구하지 않는다.
     Codex 교차 검증은 PR 댓글로 게시하지 않으므로 교차 검증만으로는 PR 댓글 판단을 요구하지 않는다.
  6. 커밋 명령의 `검토:` 줄에 PR 댓글 주소가 없는 것. 커밋은 사용자가 실행하므로 git-guard 9번이 실행되지 않는다.
  7. 요청 뒤에 PR 댓글을 게시했는데 커밋 명령 뒤에 `git push` 블록이 없는 것.
  5~7 은 ~/.claude/CLAUDE.md 「브랜치·PR 흐름」이다.
  8. 마지막 요청 뒤에 교차 검증의 Codex 작업(codex-companion task)을 crosscheck.py run 으로 감싸지 않고 호출한 것.
     직접 호출하면 모델과 사용량이 기록되지 않는다. --cwd 가 reader-test-* 인 독자 테스트는 제외한다.
  9. 마지막 요청 뒤에 crosscheck.py note 로 기록한 항목의 제목(--item)이 그 note 뒤에 나간 답변 어디에도 없는 것.
     보고를 마친 뒤 사용자가 `!` 명령을 실행해도 같은 제목을 다시 요구하지 않는다.
  8·9 는 codex-cross-check 「진행」·「보고」다. 교차 검증은 백그라운드로 실행되고 작업 알림 뒤에 답이 나가므로 기준은 마지막 요청이다.
  요청은 작업 알림·스킬 본문·훅 되먹임·`!` 명령을 제외한 사용자 메시지다. 판정은 testrun human_message 가 한다.
이미 이 훅으로 반려된 턴(stop_hook_active)은 다시 반려하지 않는다. 무한 루프 방지.
"""
import json
import os
import re
import shlex
import subprocess
import sys

from testrun import (FAILURE, as_text, called_paths, cd_targets, content_blocks, expand_word, human_message,
                     is_document, is_test_run, load_rows, run_failed, said_since_last_message, shell_command,
                     shell_env, without_heredoc_bodies)

VIEW_ONLY = re.compile(r"^\s*(cat|less|more|head|tail|bat)\s|^\s*sed\s+-n\s|^\s*grep\s")
# git 과 하위 명령 사이에 오는 `-C 경로`. 따옴표로 감싼 경로도 받는다
GIT = r"""\bgit\s+(?:-C\s+(?P<dir>"[^"]*"|'[^']*'|\S+)\s+)?"""
GIT_ACTION = re.compile(GIT + r"(add|commit|push)\b|\bgh\s+pr\s+(create|edit|ready|merge|comment)\b")
STATE_CHECK = re.compile(GIT + r"(status|log|diff|branch|rev-parse)\b|\bgh\s+pr\s+(view|list|status)\b")
EMPTY_COMMIT = re.compile(GIT + r"commit\b[^\n]*--allow-empty")
COMMIT = re.compile(GIT + r"commit\b")
GIT_ADD = re.compile(GIT + r"add\s+(?P<paths>[^;&|\n]+)")
GIT_PUSH = re.compile(GIT + r"push\b")
GH_COMMENT = re.compile(r"\bgh\s+pr\s+comment\b")
COMMENT_URL = re.compile(r"https://github\.com/\S+/(pull|issues)/\d+#issuecomment-\d+")
BASH_BLOCK = re.compile(r"```(?:bash|sh|zsh|shell)\s*\n(.*?)```", re.S)
# doc-writing 「처음 읽는 독자로 확인한다」의 「크게 고친 문서」 기준. 오타 수정 같은 작은 커밋은 묻지 않는다
BIG_CHANGE = 50


def staged_documents(block):
    """커밋 명령 앞의 `cd 저장소` 에서 커밋될 문서 가운데 새 파일이거나 크게 고친 것의 절대 경로를 낸다.

    이미 스테이징된 것에 더해 같은 명령의 `git add` 가 올릴 것도 본다.
    커밋 명령은 인덱스를 비운 채 `git add 경로 && git commit` 으로 내므로, 스테이징된 것만 보면 검사가 걸리지 않는다.
    """
    cds = cd_targets(block)
    repo = cds[0][1] if cds else ""
    given = COMMIT.search(block)["dir"]
    if given:
        # git -C 경로 commit 은 그 경로에서 커밋한다
        repo = os.path.join(repo, expand_word(given, shell_env(block)))
    if not repo:
        return []
    adding = [p for m in GIT_ADD.finditer(block) for p in shlex.split(m["paths"]) if not p.startswith("-")]

    def git(*args):
        return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True)

    stat = git("diff", "--cached", "--numstat")
    if stat.returncode != 0:
        return []
    added = set(git("diff", "--cached", "--name-only", "--diff-filter=A").stdout.splitlines())
    lines = stat.stdout.splitlines()
    if adding:
        added |= set(git("ls-files", "--others", "--exclude-standard", "--", *adding).stdout.splitlines())
        lines += git("diff", "--numstat", "--", *adding).stdout.splitlines()
    sizes = {}
    for line in lines:
        plus, minus, rel = line.split("\t", 2)
        sizes[rel] = sizes.get(rel, 0) + (int(plus) + int(minus) if plus.isdigit() and minus.isdigit() else 0)
    found = []
    for rel in sorted(added | set(sizes)):
        path = os.path.join(repo, rel)
        if (rel in added or sizes[rel] >= BIG_CHANGE) and is_document(path):
            found.append(os.path.realpath(path))
    return found


def last_edits(rows):
    """Claude 기록에서 파일마다 마지막으로 고친 줄의 번호를 낸다. 셸로 고친 것도 센다."""
    return {p: i for i, row in enumerate(rows) for p in called_paths(row)}


CODEX_TASK = re.compile(r"codex-companion\S*\s+task\b")
READER_DIR = re.compile(r"reader-test-([\w.-]+?)(?:\.(?:md|html))?(?=[/\s'\"]|$)")
WRAPPED = re.compile(r"\bcrosscheck\.py\s+run\b")
READER_CWD = re.compile(r"--cwd[=\s]+['\"]?\S*reader-test-")
NOTE = re.compile(r"\bcrosscheck\.py\s+note\b")


def document_name(path):
    return os.path.splitext(os.path.basename(path))[0]


BACKGROUND = "Command running in background"
NOTICE = re.compile(r"<tool-use-id>([^<]+)</tool-use-id>.*?<status>(\w+)</status>.*?\(exit code (\d+)\)", re.S)


def finished(rows):
    """백그라운드 작업 가운데 끝까지 돌고 종료 코드 0 으로 끝난 도구 호출 id 를 모은다.

    완료 알림은 queue-operation·attachment·user 줄 가운데 어디에나 들어오므로 줄 전체 글에서 찾는다.
    """
    done = set()
    for row in rows:
        text = json.dumps(row, ensure_ascii=False)
        if "<task-notification>" not in text:
            continue
        for tool_id, status, code in NOTICE.findall(text):
            if status == "completed" and code == "0":
                done.add(tool_id)
    return done


def tool_results(rows):
    """Claude 기록에서 도구 호출 id 마다 (오류였는지, 결과 글)을 낸다."""
    found = {}
    for row in rows:
        if row.get("type") != "user":
            continue
        for b in content_blocks(row):
            if b.get("type") == "tool_result":
                found[b.get("tool_use_id")] = (bool(b.get("is_error")), as_text(b.get("content")))
    return found


def reader_tests(rows):
    """문서 이름(확장자를 뺀 파일 이름)마다 독자 테스트를 돌린 줄의 번호.

    사본 폴더 이름 reader-test-{문서 이름} 으로 교차 검증 호출과 가르고, 한 문서의 테스트가 다른 문서를 통과시키지 않게 한다.
    결과가 없거나 오류로 끝난 호출은 세지 않는다. Codex 를 못 썼으면 사용자 판단을 받게 하려는 것이다.
    """
    results = tool_results(rows)
    done = finished(rows)
    found = {}
    for i, row in enumerate(rows):
        if row.get("type") != "assistant":
            continue
        for b in content_blocks(row):
            command = (b.get("input") or {}).get("command") or ""
            if b.get("name") != "Bash" or not CODEX_TASK.search(command):
                continue
            outcome = results.get(b.get("id"))
            if outcome is None or outcome[0]:
                continue
            if outcome[1].startswith(BACKGROUND) and b.get("id") not in done:
                continue
            for name in set(READER_DIR.findall(command)):
                found.setdefault(name, []).append(i)
    return found


def codex_payload(row):
    """Codex 기록의 payload. Claude 기록이면 None."""
    p = row.get("payload")
    return p if isinstance(p, dict) else None


INJECTED = re.compile(r"<(hook_prompt|recommended_plugins|user_instructions|environment_context)\b")


def is_human_turn(row):
    p = codex_payload(row)
    if p is not None:
        if p.get("type") != "message" or p.get("role") != "user":
            return False
        # 도구가 끼워 넣은 메시지도 user 역할로 들어온다. 훅 되먹임·플러그인 안내가 그렇다
        return not INJECTED.search(as_text(p.get("content")))
    if row.get("type") != "user":
        return False
    blocks = content_blocks(row)
    return any(b.get("type") == "text" and b.get("text", "").strip() for b in blocks) \
        and not any(b.get("type") == "tool_result" for b in blocks)


def row_text(row):
    return "\n".join(b.get("text", "") for b in content_blocks(row) if b.get("type") == "text")


def is_request(row):
    """사용자가 직접 쓴 요청인지. Claude 기록은 doc-skill-guard 와 같은 testrun human_message 로 판정한다."""
    if codex_payload(row) is not None:
        return is_human_turn(row)
    return bool(human_message(row))


def is_user_command(row):
    return row.get("type") == "user" and row_text(row).lstrip().startswith("<bash-input>")


def commands_in(rows):
    """Bash 도구와 Codex exec 로 돌린 명령을 모은다."""
    found = []
    for r in rows:
        p = codex_payload(r)
        if p is not None:
            if p.get("type") == "custom_tool_call":
                found.append(shell_command(p.get("input")))
        elif r.get("type") == "assistant":
            found += [(b.get("input") or {}).get("command", "") or "" for b in content_blocks(r)
                      if b.get("type") == "tool_use" and b.get("name") == "Bash"]
    return found


def answer_before(rows, index):
    """index 줄 앞에서 마지막으로 나간 답의 글."""
    for r in reversed(rows[:index]):
        p = codex_payload(r)
        if p is not None and p.get("type") == "message" and p.get("role") == "assistant":
            return as_text(p.get("content"))
        if p is None and r.get("type") == "assistant" and row_text(r).strip():
            return row_text(r)
    return ""


def comment_problems(rows, last_text, blocks):
    """「브랜치·PR 흐름」의 댓글 판단과 댓글 뒤의 커밋·푸시 명령을 본다.

    답은 작업 알림 뒤에 나가기도 하므로 기준은 이번 턴이 아니라 마지막 요청이다.
    """
    problems = []
    commits = [b for b in blocks if COMMIT.search(b)]
    if any("검토:" in b and not COMMENT_URL.search(b) for b in commits):
        problems.append("`검토:` 줄에는 그 결정을 남긴 PR 댓글 주소를 단다. 댓글을 먼저 올리고 그 주소를 붙인다")
    requests = [i for i, r in enumerate(rows) if is_request(r)]
    if not requests:
        return problems
    since = rows[requests[-1] + 1:]
    # 스크립트 heredoc 안에 적힌 명령 글자는 실행한 명령이 아니다
    comment_rows = [i for i, r in enumerate(since)
                    if any(GH_COMMENT.search(without_heredoc_bodies(c)) for c in commands_in([r]))]
    commented = bool(comment_rows)
    # 댓글 뒤에 사용자가 `!` 로 커밋·푸시를 돌렸으면 그 댓글의 커밋은 이미 처리됐다
    pending = commented and not any(is_user_command(r) for r in since[comment_rows[-1] + 1:])
    if pending and commits and not any(GIT_PUSH.search(b) for b in blocks):
        problems.append("이번 요청에서 PR 댓글을 올렸다. 댓글을 반영한 커밋 명령 뒤에 "
                        "`cd {저장소} && git push` 블록을 따로 낸다")
    if commented or "댓글" in last_text or any(is_user_command(r) for r in since):
        return problems
    if any(COMMIT.search(b) for b in BASH_BLOCK.findall(answer_before(rows, requests[-1]))):
        problems.append("커밋 명령을 낸 답 뒤에 받은 요청이다. 사용자가 AI 결정에 반박해 방향이 바뀌었으면 "
                        "「댓글 → 커밋 → 푸시」 순서로 가고, 아니면 댓글 대상이 아닌 이유를 답변에 한 줄로 적는다")
    return problems


def direct_codex_tasks(rows):
    """마지막 요청 뒤에 crosscheck.py run 으로 감싸지 않고 실행한 Codex 작업. 독자 테스트는 대상이 아니다.

    교차 검증은 백그라운드로 실행되고 작업 알림 뒤에 답이 나가므로 기준은 이번 턴이 아니라 마지막 요청이다.
    """
    requests = [i for i, r in enumerate(rows) if is_request(r)]
    since = rows[requests[-1] + 1:] if requests else rows
    return [c for c in map(without_heredoc_bodies, commands_in(since))
            if CODEX_TASK.search(c) and not WRAPPED.search(c) and not READER_CWD.search(c)]


def reply(row):
    """그 줄이 나간 답이면 그 글."""
    p = codex_payload(row)
    if p is not None:
        return as_text(p.get("content")) if p.get("type") == "message" and p.get("role") == "assistant" else ""
    return row_text(row) if row.get("type") == "assistant" else ""


def unreported_items(rows):
    """마지막 요청 뒤에 crosscheck.py note 로 기록했는데 그 뒤에 나간 답변 어디에도 제목이 없는 항목.

    보고를 마친 뒤 사용자가 `!` 명령을 실행하면 다음 답변도 같은 요청 범위다. 마지막 답변만 보면 같은 제목을 다시 요구하게 된다.
    """
    requests = [i for i, r in enumerate(rows) if is_request(r)]
    start = requests[-1] + 1 if requests else 0
    missing = []
    for i in range(start, len(rows)):
        for command in map(without_heredoc_bodies, commands_in([rows[i]])):
            if not NOTE.search(command):
                continue
            try:
                words = shlex.split(command)
            except ValueError:
                words = command.split()
            later = [reply(r) for r in rows[i + 1:]]
            missing += [words[j + 1] for j, word in enumerate(words[:-1])
                        if word == "--item" and not any(words[j + 1] in text for text in later)]
    return missing


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return
    if payload.get("stop_hook_active"):
        return
    rows = load_rows(payload.get("transcript_path", ""))
    if not rows:
        return

    # 마지막 사람 발화 이후의 턴만 본다
    start = 0
    for i, r in enumerate(rows):
        if is_human_turn(r):
            start = i
    turn = rows[start + 1:]

    ran_commands, last_text = [], ""
    commands, last_test_failed = {}, False
    for r in turn:
        p = codex_payload(r)
        if p is not None:
            t = p.get("type")
            if t == "custom_tool_call":
                command = shell_command(p.get("input"))
                ran_commands.append(command)
                commands[p.get("call_id")] = command
            elif t == "custom_tool_call_output":
                if is_test_run(commands.get(p.get("call_id"), "")):
                    last_test_failed = run_failed(p.get("output"))
            elif t == "message" and p.get("role") == "assistant":
                last_text = as_text(p.get("content"))
            continue
        kind = r.get("type")
        if kind == "assistant":
            texts = []
            for b in content_blocks(r):
                if b.get("type") == "tool_use" and b.get("name") == "Bash":
                    command = (b.get("input") or {}).get("command", "") or ""
                    ran_commands.append(command)
                    commands[b.get("id")] = command
                elif b.get("type") == "text":
                    texts.append(b.get("text", ""))
            if texts:
                last_text = "\n".join(texts)
        elif kind == "user":
            # 테스트 실행의 결과는 종료 코드가 아니라 출력으로 본다 — 파이프를 물리면 0 으로 끝난다
            for b in content_blocks(r):
                if b.get("type") != "tool_result":
                    continue
                if not is_test_run(commands.get(b.get("tool_use_id"), "")):
                    continue
                last_test_failed = bool(FAILURE.search(as_text(b.get("content"))))

    blocks = BASH_BLOCK.findall(last_text)
    problems = comment_problems(rows, last_text, blocks)
    if direct_codex_tasks(rows):
        problems.append("교차 검증의 Codex 작업은 `crosscheck.py run --session {Claude 세션 ID} -- …` 로 감싸 호출한다. "
                        "직접 호출하면 모델과 사용량이 기록되지 않는다. 독자 테스트(--cwd 가 reader-test-*)는 대상이 아니다")
    missing = unreported_items(rows)
    if missing:
        problems.append("교차 검증에서 기록한 항목을 답변에 보고하지 않았다: " + ", ".join(missing) +
                        ". `crosscheck.py report --session {Claude 세션 ID}` 출력으로 항목마다 요약을 싣는다")
    for b in blocks:
        first = b.strip().split("\n", 1)[0]
        # 앞의 cd … && 는 건너뛰고 실제 명령을 본다
        core = re.sub(r"^\s*cd\s+\S+\s*&&\s*", "", first)
        if VIEW_ONLY.match(core) and not GIT_ACTION.search(b):
            problems.append("조회 명령을 사용자에게 시키지 않는다. 그 내용을 답변에 직접 싣는다: " + core[:60])
    if any(GIT_ACTION.search(b) for b in blocks):
        if not any(STATE_CHECK.search(c) for c in ran_commands):
            problems.append("커밋·푸시·PR 명령을 주기 전에 이번 턴에서 상태를 확인한다 (git status / git log / gh pr view). "
                            "확인을 실제로 돌리고, 그 결과에 맞춰 명령을 다시 낸다")
        if last_test_failed and any(GIT_ACTION.search(b) and not EMPTY_COMMIT.search(b) for b in blocks):
            problems.append("이번 턴의 마지막 테스트 실행이 실패했다. 한 사이클은 GREEN 까지 진행하고 커밋 명령은 그때 낸다. "
                            "고치지 못했으면 커밋 명령 없이 무엇이 막혔는지 보고한다")
    commits = [b for b in blocks if COMMIT.search(b) and not EMPTY_COMMIT.search(b)]
    if said_since_last_message(rows, "독자 테스트 생략"):
        commits = []
    edits = last_edits(rows) if commits else {}
    tests = reader_tests(rows) if commits else {}
    unread = [p for b in commits for p in staged_documents(b)
              if p in edits and not any(t > edits[p] for t in tests.get(document_name(p), []))]
    if unread:
        problems.append("독자 테스트를 돌리지 않은 문서를 커밋하려 한다: " +
                        ", ".join(os.path.basename(p) for p in unread) +
                        ". doc-writing 「처음 읽는 독자로 확인한다」대로 사본 폴더 이름을 reader-test-{문서 이름} 으로 해 돌리고 "
                        "결과를 보고한 뒤 커밋 명령을 낸다. 사용자가 한 줄에 「독자 테스트 생략」이라고 썼으면 통과한다")
    if problems:
        print(json.dumps({"decision": "block",
                          "reason": "[stop-check] " + " / ".join(problems)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
