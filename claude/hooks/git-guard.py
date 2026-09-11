#!/usr/bin/env python3
"""PreToolUse(Bash) — git·gh 명령에서 규칙 위반을 실행 전에 막는다.

막는 것 (~/.claude/CLAUDE.md 「커밋 체크포인트」·「브랜치·PR 흐름」):
  1. git add -A / --all / .            경로를 명시한다
  2. 커밋 메시지 접두사 없음            [Feat] [Fix] [HotFix] [Docs] [Test] [Refactor]
  3. 커밋 메시지·PR 본문의 도구 서명    Co-Authored-By: Claude / Generated with Claude Code
  4. git push 의 + 강제 refspec          이력을 다시 쓰지 않는다 (--force 는 settings 가 막는다)
  5. gh pr merge --merge / --rebase      스쿼시만 쓴다
  6. 드래프트가 아닌 gh pr create, gh pr ready, gh pr merge 에 PR 본문 3항목이 없음
  7. PR 본문의 전각 대시 문장 잇기 (PR 본문도 문서 작성 규칙을 따른다)

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


def check_git(toks, cwd):
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
        # 앞에 붙은 cd … 나 환경변수는 건너뛰고 실제 명령을 찾는다
        while toks and (toks[0] in ("cd", "env", "sudo") or "=" in toks[0] and not toks[0].startswith("-")):
            toks = toks[2:] if toks[0] == "cd" else toks[1:]
        if not toks:
            continue
        if toks[0] == "git":
            check_git(toks, cwd)
        elif toks[0] == "gh":
            check_gh(toks, cwd)


if __name__ == "__main__":
    main()
