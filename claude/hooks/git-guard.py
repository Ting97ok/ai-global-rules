#!/usr/bin/env python3
"""PreToolUse(Bash) — git·gh 명령에서 규칙 위반을 실행 전에 차단한다.

차단 대상 (~/.claude/CLAUDE.md 「커밋 체크포인트」·「브랜치·PR 흐름」):
  1. git add -A / --all / .            경로를 명시한다
  2. 커밋 메시지 접두사 없음            [Feat] [Fix] [HotFix] [Docs] [Test] [Refactor]
  3. 커밋 메시지·PR 본문의 도구 서명    Co-Authored-By: Claude / Generated with Claude Code
  4. git push 의 + 강제 refspec          이력을 재작성하지 않는다 (--force 는 settings 가 차단한다)
  5. gh pr merge --merge / --rebase      스쿼시만 사용한다
  6. 드래프트가 아닌 gh pr create, gh pr ready, gh pr merge 에 PR 본문 3항목이 없음
  7. PR 본문의 전각 대시 문장 연결 (PR 본문도 문서 작성 규칙을 따른다)
  8. 브랜치의 두 번째 커밋인데 열린 PR 이 없음   드래프트 PR 을 먼저 연다
  9. `검토:` 줄에 댓글 주소가 없음            그 결정을 기록한 PR 댓글 주소를 추가한다
 10. gh pr comment 인데 푸시하지 않은 커밋이 있음   댓글과 관계없는 커밋이 타임라인에서 댓글 아래에 표시된다
 11. gh pr comment 인데 댓글의 「변경 파일:」에 없는 미커밋 변경이 있음   관계없는 변경을 먼저 커밋·푸시한다
 12. 「교차 검증 지적:」 줄이 있는 댓글                교차 검증 결과는 댓글로 게시하지 않는다
 13. 「사용자 피드백:」 줄이 두 번 이상인 댓글          피드백은 건마다 댓글을 별도로 게시한다
 14. 결정 댓글의 한 줄에 문장이 둘 이상               줄마다 한 문장으로 요약한다. 「다.」로 끝나는 문장을 집계한다

`git -C 경로 …` 는 그 경로에서 실행한 git 명령으로 보고 같은 기준으로 검사한다.
이 훅은 Claude 가 Bash 도구로 실행하는 명령에만 적용된다. 사용자가 `!` 로 실행하는 커밋은 stop-check 가 추천 명령에서 확인한다.
종료 코드 2 + stderr 가 차단이다. 판단이 필요한 것은 여기 두지 않는다.
"""
import json
import os
import re
import shlex
import subprocess
import sys

PREFIX = re.compile(r"^\[(Feat|Fix|HotFix|Docs|Test|Refactor)\]")
SIGNATURE = re.compile(r"Co-Authored-By:\s*Claude|Generated with \[?Claude Code|🤖", re.IGNORECASE)
SECTIONS = ("작업 내용", "검토에서 바뀐", "인수 확인")
COMMENT_URL = re.compile(r"https://github\.com/\S+/(pull|issues)/\d+#issuecomment-\d+")
CHANGED_FILES = re.compile(r"^\s*변경 파일\s*:(.*)$", re.M)
CROSS_CHECK_LINE = re.compile(r"^\s*교차 검증 지적\s*:", re.M)
FEEDBACK_LINE = re.compile(r"^\s*사용자 피드백\s*:", re.M)
DECISION_LINE = re.compile(r"^\s*(1차 AI 결정|사용자 피드백|2차 AI 결정\(피드백 반영\)|2차 AI 결정 근거"
                           r"|직전 결정|다시 바뀐 계기|새 결정|새 결정 근거)\s*:(.*)$", re.M)
SENTENCE_END = re.compile(r"다\.(?=\s|$)")


def fail(msg):
    print("[git-guard] " + msg, file=sys.stderr)
    sys.exit(2)


def segments(command):
    """&&, ;, | 로 이어진 명령을 나눈다. 따옴표 안은 나누지 않는다."""
    out, buf, q = [], "", None
    i = 0
    while i < len(command):
        c = command[i]
        if q:
            buf += c
            if c == q:
                q = None
        elif c in "\"'":
            q = c
            buf += c
        elif command.startswith("&&", i) or command.startswith("||", i):
            out.append(buf); buf = ""; i += 1
        elif c in ";|":
            out.append(buf); buf = ""
        else:
            buf += c
        i += 1
    out.append(buf)
    return [s.strip() for s in out if s.strip()]


def tokens(seg):
    try:
        return shlex.split(seg)
    except ValueError:
        return seg.split()


def current_branch(cwd):
    r = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                       cwd=cwd or None, capture_output=True, text=True, timeout=10)
    return r.stdout.strip() if r.returncode == 0 else ""


def needs_comment_link(message):
    """커밋 본문의 `검토:` 줄에 그 결정을 남긴 PR 댓글 주소가 없으면 True."""
    for line in message.splitlines():
        if line.strip().startswith("검토:"):
            return not COMMENT_URL.search(line)
    return False


def commits_ahead(cwd):
    """기본 브랜치 이후 이 브랜치에 쌓인 커밋 수. 셀 수 없으면 -1."""
    for base in ("main", "master"):
        r = subprocess.run(["git", "rev-list", "--count", base + "..HEAD"],
                           cwd=cwd or None, capture_output=True, text=True, timeout=10)
        if r.returncode == 0 and r.stdout.strip().isdigit():
            return int(r.stdout.strip())
    return -1


def pr_state(cwd):
    """이 브랜치에 열린 PR 이 있으면 True, 없으면 False, 확인할 수 없으면 None."""
    try:
        r = subprocess.run(["gh", "pr", "view", "--json", "number"],
                           cwd=cwd or None, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode == 0:
        return True
    return False if "no pull requests found" in r.stderr.lower() else None


def needs_pr(branch, ahead, pr):
    """브랜치에 커밋이 하나 쌓였는데 열린 PR 이 없으면 True.

    첫 커밋 전에는 PR 을 열 수 없어서(빈 브랜치는 GitHub 가 거절한다) 두 번째 커밋에서 한 번만 본다.
    """
    if branch in ("", "main", "master", "HEAD"):
        return False
    if pr is not False:
        return False
    return ahead == 1


def option_values(toks, names):
    """--body X / --body=X / -b X 꼴의 값을 전부 모은다."""
    vals = []
    for i, t in enumerate(toks):
        for n in names:
            if t == n and i + 1 < len(toks):
                vals.append(toks[i + 1])
            elif t.startswith(n + "="):
                vals.append(t[len(n) + 1:])
    return vals


def pr_body_from_args(toks, cwd):
    body = "\n".join(option_values(toks, ["--body", "-b"]))
    for f in option_values(toks, ["--body-file", "-F"]):
        p = f if os.path.isabs(f) else os.path.join(cwd or ".", f)
        try:
            body += "\n" + open(p, encoding="utf-8").read()
        except OSError:
            pass
    return body


def pr_body_from_github(toks, cwd):
    args = [t for t in toks[3:] if not t.startswith("-")]
    cmd = ["gh", "pr", "view"] + args[:1] + ["--json", "body", "-q", ".body"]
    r = subprocess.run(cmd, cwd=cwd or None, capture_output=True, text=True, timeout=20)
    return r.stdout if r.returncode == 0 else None


def missing_sections(body):
    return [s for s in SECTIONS if s not in (body or "")]


def comment_format_problems(body):
    """댓글 본문이 「브랜치·PR 흐름」의 댓글 형식을 어긴 곳을 모은다."""
    problems = []
    if CROSS_CHECK_LINE.search(body):
        problems.append("Codex 교차 검증 결과는 PR 댓글로 남기지 않는다. 결과는 답변에서만 보고한다")
    if len(FEEDBACK_LINE.findall(body)) > 1:
        problems.append("피드백이 여러 건이면 한 댓글에 모으지 않고 건마다 댓글을 따로 올린다")
    long_lines = [m.group(1) for m in DECISION_LINE.finditer(body) if len(SENTENCE_END.findall(m.group(2))) > 1]
    if long_lines:
        problems.append("댓글은 요약해서 줄마다 한 문장으로 쓴다. 문장이 둘 이상인 줄: " + ", ".join(long_lines))
    return problems


def unpushed_commits(cwd):
    """업스트림에 올리지 않은 커밋 수. 업스트림이 없으면 0 이다."""
    r = subprocess.run(["git", "rev-list", "--count", "@{u}..HEAD"],
                       cwd=cwd or None, capture_output=True, text=True, timeout=10)
    return int(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip().isdigit() else 0


def unlisted_changes(body, cwd):
    """댓글의 「변경 파일:」 줄에 이름이 없는 미커밋 추적 파일.

    「없음」으로 시작하면 뒤 문장은 설명이라 적은 파일이 없는 것으로 본다. 줄이 없으면 묻지 않는다.
    """
    found = CHANGED_FILES.search(body or "")
    if not found:
        return []
    listed = "" if found.group(1).strip().startswith("없음") else found.group(1)
    r = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"],
                       cwd=cwd or None, capture_output=True, text=True, timeout=10)
    if r.returncode != 0:
        return []
    paths = [line[3:].split(" -> ")[-1] for line in r.stdout.splitlines() if len(line) > 3]
    return [p for p in paths if os.path.basename(p) not in listed]


def check_git(toks, cwd):
    # 전역 옵션을 건너뛰고 하위 명령을 읽는다. git -C 경로 … 는 그 경로에서 실행한 git 명령과 같다
    while len(toks) > 1 and toks[1].startswith("-"):
        if toks[1] in ("-C", "-c") and len(toks) > 2:
            if toks[1] == "-C":
                cwd = os.path.join(cwd, toks[2])
            toks = toks[:1] + toks[3:]
        elif toks[1].startswith("--"):
            toks = toks[:1] + toks[2:]
        else:
            break
    sub = toks[1] if len(toks) > 1 else ""
    if sub == "add":
        for t in toks[2:]:
            if t in ("-A", "--all", "."):
                fail("git add 에 경로를 명시한다. -A / --all / . 은 다른 작업을 섞는다")
    elif sub == "commit":
        msgs = option_values(toks, ["-m", "--message"])
        if msgs:
            if not PREFIX.match(msgs[0]):
                fail("커밋 제목은 [Feat] [Fix] [HotFix] [Docs] [Test] [Refactor] 중 하나로 시작한다")
            for m in msgs:
                if SIGNATURE.search(m):
                    fail("커밋 메시지에 도구 서명(Co-Authored-By: Claude / Generated with Claude Code)을 넣지 않는다")
            for m in msgs:
                if needs_comment_link(m):
                    fail("`검토:` 줄에는 그 결정을 남긴 PR 댓글 주소를 단다. 댓글을 먼저 올리고 그 주소를 붙인다")
        branch = current_branch(cwd)
        ahead = commits_ahead(cwd) if branch not in ("", "main", "master", "HEAD") else 0
        if ahead == 1 and needs_pr(branch, ahead, pr_state(cwd)):
            fail("브랜치 작업은 드래프트 PR 을 먼저 연다. gh pr create --draft 로 열고 이어서 커밋한다")
    elif sub == "push":
        for t in toks[2:]:
            if t.startswith("+") and not t.startswith("+="):
                fail("push 의 + refspec 은 강제 푸시다. PR 브랜치 이력을 다시 쓰지 않는다")


def check_gh(toks, cwd):
    if len(toks) < 3 or toks[1] != "pr":
        return
    sub = toks[2]
    if sub in ("create", "edit"):
        body = pr_body_from_args(toks, cwd)
        if SIGNATURE.search(body):
            fail("PR 본문에 도구 서명을 넣지 않는다")
        if " — " in body:
            fail("PR 본문도 문서 작성 규칙을 따른다. 전각 대시로 문장을 잇지 않는다")
        if sub == "create" and "--draft" not in toks and "-d" not in toks:
            miss = missing_sections(body)
            if miss:
                fail("드래프트가 아닌 PR 은 본문에 「작업 내용 / 검토에서 바뀐 것 / 인수 확인」이 있어야 한다. "
                     f"빠진 것: {', '.join(miss)}. 먼저 --draft 로 열거나 본문을 채운다")
    elif sub == "comment":
        body = pr_body_from_args(toks, cwd)
        problems = comment_format_problems(body)
        if problems:
            fail(" / ".join(problems))
        ahead = unpushed_commits(cwd)
        if ahead:
            fail(f"푸시하지 않은 커밋이 {ahead}개 있다. 이대로 댓글을 올리면 댓글과 관계없는 커밋이 타임라인에서 "
                 "댓글 아래에 놓인다. 사용자 푸시를 먼저 받고 댓글을 올린다")
        stray = unlisted_changes(body, cwd)
        if stray:
            fail(f"댓글의 「변경 파일:」에 없는 미커밋 변경이 있다: {', '.join(stray)}. "
                 "댓글과 관계없는 변경은 먼저 커밋·푸시하고 댓글을 올린다")
    elif sub == "merge":
        if "--merge" in toks or "-m" in toks or "--rebase" in toks or "-r" in toks:
            fail("PR 은 스쿼시로 합친다 (--squash). 사이클 이력은 PR 에 남는다")
        body = pr_body_from_github(toks, cwd)
        if body is not None:
            miss = missing_sections(body)
            if miss:
                fail(f"PR 본문에 빠진 항목이 있다: {', '.join(miss)}. 합치기 전에 채운다")
    elif sub == "ready":
        body = pr_body_from_github(toks, cwd)
        if body is not None:
            miss = missing_sections(body)
            if miss:
                fail(f"드래프트를 풀기 전에 PR 본문을 채운다. 빠진 것: {', '.join(miss)}")


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return
    command = payload.get("tool_input", {}).get("command", "") or ""
    cwd = payload.get("cwd") or os.getcwd()
    for seg in segments(command):
        toks = tokens(seg)
        # 앞에 붙은 cd … 나 환경변수는 건너뛰고 실제 명령을 찾는다.
        # cd 가 가리키는 곳이 이 명령의 저장소다. 추천 커밋 명령은 늘 `cd {절대경로} &&` 로 시작한다
        while toks and (toks[0] in ("cd", "env", "sudo") or "=" in toks[0] and not toks[0].startswith("-")):
            if toks[0] == "cd":
                if len(toks) > 1:
                    cwd = toks[1]
                toks = toks[2:]
            else:
                toks = toks[1:]
        if not toks:
            continue
        if toks[0] == "git":
            check_git(toks, cwd)
        elif toks[0] == "gh":
            check_gh(toks, cwd)


if __name__ == "__main__":
    main()
