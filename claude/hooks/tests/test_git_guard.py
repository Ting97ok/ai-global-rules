#!/usr/bin/env python3
"""git-guard 훅 테스트.

실행: python3 ~/.claude/hooks/tests/test_git_guard.py
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HOOK = Path(__file__).resolve().parent.parent / "git-guard.py"
_spec = importlib.util.spec_from_file_location("git_guard", HOOK)
git_guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(git_guard)

BODY = "작업 내용\n검토에서 바뀐 것\n인수 확인\n앞 문장이 있다 — 뒤 문장이 이어진다.\n"


def run(command, cwd):
    payload = {"hook_event_name": "PreToolUse", "tool_name": "Bash",
               "tool_input": {"command": command}, "cwd": cwd}
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload),
                          capture_output=True, text=True)


class PrFirst(unittest.TestCase):
    def test_브랜치에_커밋이_하나_있는데_PR_이_없으면_막는다(self):
        self.assertTrue(git_guard.needs_pr("docs/doc-writing-skill", 1, False))

    def test_검토_줄에_댓글_주소가_없으면_막는다(self):
        self.assertTrue(git_guard.needs_comment_link("검토: 지적 → 바뀐 것"))
        self.assertFalse(git_guard.needs_comment_link(
            "검토: 지적 → 바뀐 것 (https://github.com/o/r/pull/2#issuecomment-1)"))


def pushed_repo(folder):
    """원격에 한 번 푸시한 작업 저장소를 만든다. 추적하는 파일은 a.java 하나다."""
    remote, work = Path(folder) / "remote.git", Path(folder) / "work"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    subprocess.run(["git", "clone", "-q", str(remote), str(work)], check=True, capture_output=True)
    (work / "a.java").write_text("class A {}\n", encoding="utf-8")
    subprocess.run(["git", "add", "a.java"], cwd=work, check=True)
    commit(work, "[Feat] 처음")
    subprocess.run(["git", "push", "-q", "-u", "origin", "HEAD"], cwd=work, check=True, capture_output=True)
    return work


def commit(work, message):
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", message],
                   cwd=work, check=True)


# ~/.claude/CLAUDE.md 「브랜치·PR 흐름」 — 댓글과 관계없는 커밋이 타임라인에서 댓글 아래에 놓이지 않게 한다
class CommentTiming(unittest.TestCase):
    def test_푸시하지_않은_커밋이_있으면_댓글을_막는다(self):
        with tempfile.TemporaryDirectory() as folder:
            work = pushed_repo(folder)
            (work / "a.java").write_text("class A { int x; }\n", encoding="utf-8")
            subprocess.run(["git", "add", "a.java"], cwd=work, check=True)
            commit(work, "[Feat] 푸시 전")
            result = run(f'cd {work} && gh pr comment 13 --body "제목\n변경 파일: 없음"', folder)
            self.assertEqual(2, result.returncode, result.stderr or "막지 않았다")
            self.assertIn("푸시", result.stderr)

    def test_변경_파일에_없는_미커밋_변경이_있으면_댓글을_막는다(self):
        with tempfile.TemporaryDirectory() as folder:
            work = pushed_repo(folder)
            (work / "a.java").write_text("class A { int x; }\n", encoding="utf-8")
            result = run(f'cd {work} && gh pr comment 13 --body "제목\n변경 파일: 없음. a.java 는 그대로 커밋한다"', folder)
            self.assertEqual(2, result.returncode, result.stderr or "막지 않았다")
            self.assertIn("a.java", result.stderr)

    def test_변경_파일에_적은_파일만_미커밋이면_댓글을_통과한다(self):
        with tempfile.TemporaryDirectory() as folder:
            work = pushed_repo(folder)
            (work / "a.java").write_text("class A { int x; }\n", encoding="utf-8")
            result = run(f'cd {work} && gh pr comment 13 --body "제목\n변경 파일: a.java"', folder)
            self.assertEqual(0, result.returncode, result.stderr)


DECISION = ("요청 로그 필터 이름에서 나온 피드백\n\n"
            "1차 AI 결정: 필터 이름을 LogFilter 로 바꿨다.\n"
            "사용자 피드백: 요청 로그를 남기는 필터라 이름에 요청이 들어가야 한다.\n"
            "2차 AI 결정(피드백 반영): 필터 이름을 RequestLogFilter 로 되돌렸다.\n"
            "2차 AI 결정 근거: 필터가 보는 범위가 HTTP 요청 하나하나다.\n"
            "변경 파일: docs/08-request-log.html\n")


# ~/.claude/CLAUDE.md 「브랜치·PR 흐름」 — 댓글은 요약해서 건마다 따로 올리고 교차 검증 결과는 올리지 않는다
class CommentFormat(unittest.TestCase):
    def comment(self, body):
        with tempfile.TemporaryDirectory() as folder:
            return run(f'gh pr comment 13 --body "{body}"', folder)

    def test_규칙대로_쓴_결정_댓글은_통과한다(self):
        result = self.comment(DECISION)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_교차_검증_결과_댓글을_막는다(self):
        result = self.comment("08문서를 교차 검증한 결과\n\nAI 초안: 장 번호를 적었다.\n교차 검증 지적: 장 번호가 틀렸다.\n")
        self.assertEqual(2, result.returncode, result.stderr or "막지 않았다")
        self.assertIn("교차 검증", result.stderr)

    def test_피드백_여러_건을_한_댓글에_모으면_막는다(self):
        result = self.comment(DECISION + "\n" + DECISION)
        self.assertEqual(2, result.returncode, result.stderr or "막지 않았다")
        self.assertIn("건마다", result.stderr)

    def test_한_줄에_문장이_둘_이상이면_막는다(self):
        result = self.comment(DECISION.replace(
            "HTTP 요청 하나하나다.", "HTTP 요청 하나하나다. 로그 줄의 eventType 도 request 다."))
        self.assertEqual(2, result.returncode, result.stderr or "막지 않았다")
        self.assertIn("2차 AI 결정 근거", result.stderr)


class TargetRepo(unittest.TestCase):
    def test_cd_가_가리키는_저장소의_PR_본문을_읽는다(self):
        with tempfile.TemporaryDirectory() as here, tempfile.TemporaryDirectory() as there:
            (Path(there) / "body.md").write_text(BODY, encoding="utf-8")
            result = run(f"cd {there} && gh pr edit 4 --body-file body.md", here)
            self.assertEqual(2, result.returncode, result.stdout or "막지 않았다")
            self.assertIn("전각 대시", result.stderr)

    def test_전역_옵션을_준_git_명령도_검사하고_C_경로의_저장소를_본다(self):
        with tempfile.TemporaryDirectory() as here:
            work = pushed_repo(here)
            subprocess.run(["git", "switch", "-q", "-c", "feat/x"], cwd=work, check=True)
            (work / "a.java").write_text("class A { int x; }\n", encoding="utf-8")
            subprocess.run(["git", "add", "a.java"], cwd=work, check=True)
            commit(work, "[Feat] 브랜치 첫 커밋")
            # 열린 PR 이 없는 브랜치처럼 답하는 gh
            gh = Path(here) / "bin" / "gh"
            gh.parent.mkdir()
            gh.write_text('#!/bin/sh\necho "no pull requests found for branch" >&2\nexit 1\n', encoding="utf-8")
            gh.chmod(0o755)
            cases = {
                "경로 없는 git add": (f"git -C {work} add -A", "경로를 명시한다"),
                "접두사 없는 커밋": (f'git -C {work} commit -m "접두사 없음"', "커밋 제목"),
                "+ refspec 푸시": (f"git -C {work} push origin +feat/x", "강제 푸시"),
                "PR 없는 브랜치의 두 번째 커밋": (f'git -C {work} commit -m "[Feat] 둘째"', "드래프트 PR"),
                "-c 가 앞선 접두사 없는 커밋": ('git -c user.name=x commit -m "접두사 없음"', "커밋 제목"),
                "--no-pager 가 앞선 경로 없는 git add": (f"git --no-pager -C {work} add -A", "경로를 명시한다"),
                "-c 와 -C 를 준 PR 없는 브랜치의 두 번째 커밋":
                    (f'git -c core.x=y -C {work} commit -m "[Feat] 둘째"', "드래프트 PR"),
            }
            with mock.patch.dict(os.environ, {"PATH": f"{gh.parent}{os.pathsep}{os.environ['PATH']}"}):
                for name, (command, expected) in cases.items():
                    with self.subTest(name=name):
                        result = run(command, here)
                        self.assertEqual(2, result.returncode, result.stderr or "막지 않았다")
                        self.assertIn(expected, result.stderr)


if __name__ == "__main__":
    unittest.main()
