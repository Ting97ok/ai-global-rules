#!/usr/bin/env python3
"""stop-check 훅 테스트.

실행: python3 ~/.claude/hooks/tests/test_stop_check.py
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent / "stop-check.py"


def human(text):
    return {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": text}]}}


def bash_call(call_id, command):
    return {
        "type": "assistant",
        "message": {
            "content": [
                {"type": "tool_use", "id": call_id, "name": "Bash", "input": {"command": command}}
            ]
        },
    }


def bash_result(call_id, output):
    return {
        "type": "user",
        "message": {
            "content": [
                {"type": "tool_result", "tool_use_id": call_id, "content": output, "is_error": False}
            ]
        },
    }


def answer(text):
    return {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}


def transcript(rows, folder):
    path = Path(folder) / "transcript.jsonl"
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    return str(path)


def run(transcript_path):
    payload = {"hook_event_name": "Stop", "stop_hook_active": False,
               "transcript_path": transcript_path}
    return subprocess.run(
        [sys.executable, str(HOOK)], input=json.dumps(payload), capture_output=True, text=True
    )


COMMIT_ANSWER = """사이클 하나를 닫았다.

```bash
cd /repo && git commit -m "[Test] 실패 테스트 하나"
```
"""


def write_call(call_id, path):
    return {
        "type": "assistant",
        "message": {
            "content": [
                {"type": "tool_use", "id": call_id, "name": "Write", "input": {"file_path": str(path), "content": "x"}}
            ]
        },
    }


def staged_repo(folder, rel, lines, changed=None, stage=True):
    """임시 저장소에 문서를 스테이징한다.

    changed 가 없으면 lines 줄짜리 새 파일이다. 있으면 lines 줄을 먼저 커밋해 두고 앞의 changed 줄만 고친다.
    stage 가 거짓이면 고친 채로 두고 스테이징하지 않는다.
    """
    repo = Path(folder) / "repo"
    doc = repo / rel
    doc.parent.mkdir(parents=True)
    git = ["git", "-c", "user.email=t@t", "-c", "user.name=t"]
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    body = [f"<p>{i}번째 문단이다.</p>\n" for i in range(lines)]
    if changed is not None:
        doc.write_text("".join(body), encoding="utf-8")
        subprocess.run(["git", "add", rel], cwd=repo, check=True)
        subprocess.run(git + ["commit", "-q", "-m", "[Docs] 처음"], cwd=repo, check=True)
        body[:changed] = [f"<p>{i}번째 문단을 고쳤다.</p>\n" for i in range(changed)]
    doc.write_text("".join(body), encoding="utf-8")
    if stage:
        subprocess.run(["git", "add", rel], cwd=repo, check=True)
    return repo, doc


def reader_call(call_id, stem):
    return bash_call(call_id, "node ~/.claude/plugins/cache/openai-codex/codex/1.0.6/scripts/codex-companion.mjs task "
                              f"--fresh --cwd /private/tmp/s/reader-test-{stem} "
                              f"--prompt-file /private/tmp/s/reader-test-{stem}/prompt.txt")


def commit_answer(repo, add=None):
    staging = f"git add {add} && " if add else ""
    return answer(f'문서를 스테이징했다.\n\n```bash\ncd {repo} && {staging}git commit -m "[Docs] 계획 문서"\n```\n')


class ReaderTest(unittest.TestCase):
    def test_커밋_명령이_git_add_로_올리는_새_문서도_독자_테스트를_요구한다(self):
        with tempfile.TemporaryDirectory() as folder:
            repo, doc = staged_repo(folder, "docs/plan.html", 60, stage=False)
            rows = [
                human("계획 문서 커밋 명령 줘"),
                write_call("w1", doc),
                bash_call("s1", f"cd {repo} && git status --short"),
                bash_result("s1", "?? docs/plan.html"),
                commit_answer(repo, add="docs/plan.html"),
            ]
            result = run(transcript(rows, folder))
            self.assertIn("block", result.stdout)
            self.assertIn("독자 테스트", result.stdout)

    def test_커밋_명령이_git_add_로_올리는_큰_변경도_독자_테스트를_요구한다(self):
        with tempfile.TemporaryDirectory() as folder:
            repo, doc = staged_repo(folder, "docs/plan.html", 60, changed=30, stage=False)
            rows = [
                human("계획 문서 커밋 명령 줘"),
                write_call("w1", doc),
                bash_call("s1", f"cd {repo} && git status --short"),
                bash_result("s1", " M docs/plan.html"),
                commit_answer(repo, add="docs/plan.html"),
            ]
            result = run(transcript(rows, folder))
            self.assertIn("block", result.stdout)
            self.assertIn("독자 테스트", result.stdout)

    def test_새_문서를_독자_테스트_없이_커밋하면_막는다(self):
        with tempfile.TemporaryDirectory() as folder:
            repo, doc = staged_repo(folder, "docs/plan.html", 60)
            rows = [
                human("계획 문서 커밋 명령 줘"),
                write_call("w1", doc),
                bash_call("s1", f"cd {repo} && git status --short"),
                bash_result("s1", "A  docs/plan.html"),
                commit_answer(repo),
            ]
            result = run(transcript(rows, folder))
            self.assertIn("block", result.stdout)
            self.assertIn("독자 테스트", result.stdout)

    def test_문서를_고친_뒤_독자_테스트를_돌렸으면_통과한다(self):
        with tempfile.TemporaryDirectory() as folder:
            repo, doc = staged_repo(folder, "docs/plan.html", 60)
            rows = [
                human("계획 문서 커밋 명령 줘"),
                write_call("w1", doc),
                reader_call("r1", "plan"),
                bash_result("r1", "## 질문과 답"),
                bash_call("s1", f"cd {repo} && git status --short"),
                bash_result("s1", "A  docs/plan.html"),
                commit_answer(repo),
            ]
            result = run(transcript(rows, folder))
            self.assertEqual("", result.stdout.strip(), result.stdout)

    def test_실패한_독자_테스트_호출은_세지_않는다(self):
        with tempfile.TemporaryDirectory() as folder:
            repo, doc = staged_repo(folder, "docs/plan.html", 60)
            failed = bash_result("r1", "Exit code 1\nCodex 로그인이 풀렸다")
            failed["message"]["content"][0]["is_error"] = True
            rows = [
                human("계획 문서 커밋 명령 줘"),
                write_call("w1", doc),
                reader_call("r1", "plan"),
                failed,
                bash_call("s1", f"cd {repo} && git status --short"),
                bash_result("s1", "A  docs/plan.html"),
                commit_answer(repo),
            ]
            result = run(transcript(rows, folder))
            self.assertIn("block", result.stdout)
            self.assertIn("독자 테스트", result.stdout)

    def test_백그라운드_독자_테스트는_완료_알림이_있어야_센다(self):
        launched = "Command running in background with ID: b1. Output is being written to: /tmp/b1.output"
        done = {"type": "queue-operation", "operation": "enqueue",
                "content": "<task-notification>\n<task-id>b1</task-id>\n<tool-use-id>r1</tool-use-id>\n"
                           "<status>completed</status>\n<summary>Background command \"독자 테스트\" completed "
                           "(exit code 0)</summary>\n</task-notification>"}
        cases = {"완료 알림 없음": ([], "block"), "완료 알림 있음": ([done], "")}
        for name, (notices, expected) in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as folder:
                repo, doc = staged_repo(folder, "docs/plan.html", 60)
                rows = [
                    human("계획 문서 커밋 명령 줘"),
                    write_call("w1", doc),
                    reader_call("r1", "plan"),
                    bash_result("r1", launched),
                    *notices,
                    bash_call("s1", f"cd {repo} && git status --short"),
                    bash_result("s1", "A  docs/plan.html"),
                    commit_answer(repo),
                ]
                result = run(transcript(rows, folder))
                if expected:
                    self.assertIn(expected, result.stdout)
                else:
                    self.assertEqual("", result.stdout.strip(), result.stdout)

    def test_추가_삭제_50줄과_새_파일을_기준으로_묻는다(self):
        cases = {
            "기존 문서 합계 48줄": ({"lines": 60, "changed": 24}, ""),
            "기존 문서 합계 50줄": ({"lines": 60, "changed": 25}, "block"),
            "3줄짜리 새 문서": ({"lines": 3}, "block"),
        }
        for name, (shape, expected) in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as folder:
                repo, doc = staged_repo(folder, "docs/plan.html", **shape)
                rows = [
                    human("계획 문서 커밋 명령 줘"),
                    write_call("w1", doc),
                    bash_call("s1", f"cd {repo} && git status --short"),
                    bash_result("s1", "M  docs/plan.html"),
                    commit_answer(repo),
                ]
                result = run(transcript(rows, folder))
                if expected:
                    self.assertIn(expected, result.stdout)
                else:
                    self.assertEqual("", result.stdout.strip(), result.stdout)

    def test_공백이_있는_저장소_경로도_읽는다(self):
        with tempfile.TemporaryDirectory() as folder:
            spaced = Path(folder) / "work space"
            spaced.mkdir()
            repo, doc = staged_repo(spaced, "docs/plan.html", 60)
            rows = [
                human("계획 문서 커밋 명령 줘"),
                write_call("w1", doc),
                bash_call("s1", f'cd "{repo}" && git status --short'),
                bash_result("s1", "A  docs/plan.html"),
                answer(f'```bash\ncd "{repo}" && git commit -m "[Docs] 계획 문서"\n```\n'),
            ]
            result = run(transcript(rows, folder))
            self.assertIn("block", result.stdout)
            self.assertIn("plan.html", result.stdout)

    def test_git_C_로_경로를_준_커밋_명령도_독자_테스트를_요구한다(self):
        cases = {
            "스테이징한 새 문서": ("", True, "git -C {repo} commit"),
            "git add 로 올리는 새 문서": ("", False, "git -C {repo} add docs/plan.html && git -C {repo} commit"),
            "따옴표로 감싼 공백 경로": ("work space", True, 'git -C "{repo}" commit'),
        }
        for name, (parent, stage, command) in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as folder:
                (Path(folder) / parent).mkdir(exist_ok=True)
                repo, doc = staged_repo(Path(folder) / parent, "docs/plan.html", 60, stage=stage)
                rows = [
                    human("계획 문서 커밋 명령 줘"),
                    write_call("w1", doc),
                    bash_call("s1", f'git -C "{repo}" status --short'),
                    bash_result("s1", "?? docs/plan.html"),
                    answer(f'```bash\n{command.format(repo=repo)} -m "[Docs] 계획 문서"\n```\n'),
                ]
                result = run(transcript(rows, folder))
                self.assertIn("block", result.stdout)
                self.assertIn("plan.html", result.stdout)

    def test_한_문서의_독자_테스트는_다른_문서에_쓰지_않는다(self):
        with tempfile.TemporaryDirectory() as folder:
            repo, doc = staged_repo(folder, "docs/plan.html", 60)
            other = repo / "docs" / "guide.html"
            other.write_text("".join(f"<p>{i}번째 안내다.</p>\n" for i in range(60)), encoding="utf-8")
            subprocess.run(["git", "add", "docs/guide.html"], cwd=repo, check=True)
            rows = [
                human("문서 두 개 커밋 명령 줘"),
                write_call("w1", doc),
                write_call("w2", other),
                reader_call("r1", "plan"),
                bash_result("r1", "## 질문과 답"),
                bash_call("s1", f"cd {repo} && git status --short"),
                bash_result("s1", "A  docs/guide.html\nA  docs/plan.html"),
                commit_answer(repo),
            ]
            result = run(transcript(rows, folder))
            self.assertIn("block", result.stdout)
            self.assertIn("guide.html", result.stdout)
            self.assertNotIn("plan.html", result.stdout)

    def test_독자_테스트_뒤에_문서를_다시_고치면_막는다(self):
        with tempfile.TemporaryDirectory() as folder:
            repo, doc = staged_repo(folder, "docs/plan.html", 60)
            rows = [
                human("계획 문서 커밋 명령 줘"),
                write_call("w1", doc),
                reader_call("r1", "plan"),
                bash_result("r1", "## 질문과 답"),
                write_call("w2", doc),
                bash_call("s1", f"cd {repo} && git status --short"),
                bash_result("s1", "A  docs/plan.html"),
                commit_answer(repo),
            ]
            result = run(transcript(rows, folder))
            self.assertIn("block", result.stdout)
            self.assertIn("독자 테스트", result.stdout)

    def test_사용자가_독자_테스트_생략이라고_쓰면_통과한다(self):
        with tempfile.TemporaryDirectory() as folder:
            repo, doc = staged_repo(folder, "docs/plan.html", 60)
            rows = [
                {"type": "user", "message": {"role": "user", "content": "계획 문서 커밋 명령 줘\n독자 테스트 생략"}},
                write_call("w1", doc),
                bash_call("s1", f"cd {repo} && git status --short"),
                bash_result("s1", "A  docs/plan.html"),
                commit_answer(repo),
            ]
            result = run(transcript(rows, folder))
            self.assertEqual("", result.stdout.strip(), result.stdout)

    def test_문서가_아닌_파일은_크게_고쳐도_묻지_않는다(self):
        with tempfile.TemporaryDirectory() as folder:
            repo, rule = staged_repo(folder, "CLAUDE.md", 60)
            rows = [
                human("규칙 파일 커밋 명령 줘"),
                write_call("w1", rule),
                bash_call("s1", f"cd {repo} && git status --short"),
                bash_result("s1", "A  CLAUDE.md"),
                commit_answer(repo),
            ]
            result = run(transcript(rows, folder))
            self.assertEqual("", result.stdout.strip(), result.stdout)

    def test_이_대화에서_고치지_않은_문서는_묻지_않는다(self):
        with tempfile.TemporaryDirectory() as folder:
            repo, _ = staged_repo(folder, "docs/plan.html", 60)
            rows = [
                human("내가 쓴 문서 커밋 명령 줘"),
                bash_call("s1", f"cd {repo} && git status --short"),
                bash_result("s1", "A  docs/plan.html"),
                commit_answer(repo),
            ]
            result = run(transcript(rows, folder))
            self.assertEqual("", result.stdout.strip(), result.stdout)

    def test_작은_변경은_독자_테스트를_묻지_않는다(self):
        with tempfile.TemporaryDirectory() as folder:
            repo, doc = staged_repo(folder, "docs/plan.html", 60, changed=3)
            rows = [
                human("오타만 고치고 커밋 명령 줘"),
                write_call("w1", doc),
                bash_call("s1", f"cd {repo} && git status --short"),
                bash_result("s1", "M  docs/plan.html"),
                commit_answer(repo),
            ]
            result = run(transcript(rows, folder))
            self.assertEqual("", result.stdout.strip(), result.stdout)


class StopCheck(unittest.TestCase):
    def test_테스트가_빨간데_커밋_명령을_주면_막는다(self):
        rows = [
            human("훅 진행해"),
            bash_call("t1", "python3 ~/.claude/hooks/tests/test_doc_skill_guard.py"),
            bash_result("t1", "FAIL: test_막는다\nRan 1 test in 0.02s\n\nFAILED (failures=1)"),
            bash_call("t2", "cd /repo && git status --short && git log --oneline -2"),
            bash_result("t2", " M claude/hooks/doc-skill-guard.py"),
            answer(COMMIT_ANSWER),
        ]
        with tempfile.TemporaryDirectory() as folder:
            result = run(transcript(rows, folder))
            self.assertIn("block", result.stdout)
            self.assertIn("GREEN", result.stdout)

    def test_git_C_로_경로를_준_상태_확인도_센다(self):
        for name, check in {"경로": "git -C /repo status --short",
                            "따옴표로 감싼 경로": 'git -C "/work space/repo" log --oneline -2'}.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as folder:
                rows = [human("커밋 명령 줘"), bash_call("s1", check), bash_result("s1", " M a.java"),
                        answer(COMMIT_ANSWER)]
                stdout = run(transcript(rows, folder)).stdout
                self.assertEqual("", stdout.strip(), stdout)

    def test_빈_커밋_명령은_빨간_상태에서도_막지_않는다(self):
        rows = [
            human("브랜치를 시작해"),
            bash_call("t1", "python3 ~/.claude/hooks/tests/test_doc_skill_guard.py"),
            bash_result("t1", "FAIL: test_x\nRan 1 test\n\nFAILED (failures=1)"),
            bash_call("t2", "cd /repo && git status --short"),
            bash_result("t2", " M claude/hooks/git-guard.py"),
            answer('브랜치를 엽니다.\n\n```bash\ncd /repo && git commit --allow-empty -m "[Docs] 브랜치 시작"\n```\n'),
        ]
        with tempfile.TemporaryDirectory() as folder:
            result = run(transcript(rows, folder))
            self.assertEqual("", result.stdout.strip(), result.stdout)

    def test_git_C_로_경로를_준_커밋_푸시_명령도_검사한다(self):
        status = [bash_call("s1", "git -C /repo status --short"), bash_result("s1", " M a.java")]
        red = [bash_call("t1", "python3 ~/.claude/hooks/tests/test_doc_skill_guard.py"),
               bash_result("t1", "FAIL: test_x\nRan 1 test\n\nFAILED (failures=1)")]
        comment = [bash_call("g1", "gh pr comment 13 --body-file /private/tmp/s/comment.md"),
                   bash_result("g1", "https://github.com/o/r/pull/13#issuecomment-1")]
        commit = 'git -C /repo add a.java && git -C /repo commit -m "[Feat] 바꾼다"'
        review = commit + ' -m "검토: 지적 → 바뀐 것 (https://github.com/o/r/pull/13#issuecomment-1)"'
        cases = {
            "상태 확인 없는 커밋 명령": ([], [commit], "상태를 확인"),
            "검토 줄에 댓글 주소가 없는 커밋 명령": (status, [commit + ' -m "검토: 지적 → 바뀐 것"'], "댓글 주소"),
            "댓글 뒤에 푸시 블록이 없는 커밋 명령": (comment + status, [review], "git push"),
            "댓글 뒤에 푸시 블록도 준 커밋 명령": (comment + status, [review, "git -C /repo push"], ""),
            "빨간 상태의 빈 커밋 명령": (red + status, ['git -C /repo commit --allow-empty -m "[Fix] 브랜치 시작"'], ""),
        }
        for name, (before, blocks, expected) in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as folder:
                text = "".join(f"```bash\n{b}\n```\n\n" for b in blocks)
                stdout = run(transcript([human("커밋 명령 줘"), *before, answer(text)], folder)).stdout
                if expected:
                    self.assertIn(expected, stdout)
                else:
                    self.assertEqual("", stdout.strip(), stdout)


COMPANION = "node ~/.claude/plugins/cache/openai-codex/codex/1.0.6/scripts/codex-companion.mjs"
CROSSCHECK_RUN = "python3 ~/.claude/skills/codex-cross-check/crosscheck.py run --session s1 --"
CROSS_CHECK_TASK = f"{COMPANION} task --fresh --cwd /repo --prompt-file /private/tmp/s/xcheck-prompt.md"


def cross_check_call(call_id):
    return bash_call(call_id, f"{CROSSCHECK_RUN} {CROSS_CHECK_TASK}")


def notification(tool_id):
    return {"type": "user", "message": {"role": "user", "content":
            f"<task-notification>\n<tool-use-id>{tool_id}</tool-use-id>\n<status>completed</status>\n"
            "(exit code 0)\n</task-notification>"}}


def user_command(command):
    return {"type": "user", "message": {"role": "user", "content": f"<bash-input>{command}</bash-input>"}}


REVIEW_COMMIT = ('```bash\ncd /repo && git add a.java && git commit -m "[Feat] 바꾼다" '
                 '-m "검토: 지적 → 바뀐 것 (https://github.com/o/r/pull/13#issuecomment-1)"\n```\n')


# ~/.claude/CLAUDE.md 「브랜치·PR 흐름」 — 반박으로 방향이 바뀌거나 교차 검증에서 초안이 틀리면 댓글이 먼저다
class CommentDecision(unittest.TestCase):
    def check(self, rows):
        with tempfile.TemporaryDirectory() as folder:
            return run(transcript(rows, folder)).stdout

    # Codex 교차 검증은 PR 댓글로 남기지 않는다. 교차 검증만으로는 댓글 판단을 묻지 않는다
    def test_교차_검증만으로는_댓글_판단을_묻지_않는다(self):
        stdout = self.check([
            human("중첩이 꼭 필요해?"),
            cross_check_call("c1"),
            bash_result("c1", "Command running in background with ID: b1."),
            notification("c1"),
            answer("필요합니다. 안쪽 finally 가 정리를 보장합니다."),
        ])
        self.assertEqual("", stdout.strip(), stdout)

    def test_커밋_명령을_낸_답_뒤의_요청에_댓글_판단_없이_답하면_막는다(self):
        stdout = self.check([
            human("진행해"),
            answer(COMMIT_ANSWER),
            human("중첩이 꼭 필요해?"),
            answer("필요합니다. 안쪽 finally 가 정리를 보장합니다."),
        ])
        self.assertIn("block", stdout)
        self.assertIn("반박", stdout)

    def test_커밋_명령을_낸_답_뒤의_요청에_댓글_판단을_적으면_통과한다(self):
        stdout = self.check([
            human("진행해"),
            answer(COMMIT_ANSWER),
            human("중첩이 꼭 필요해?"),
            answer("필요합니다. 결정이 그대로라 댓글 대상이 아닙니다."),
        ])
        self.assertEqual("", stdout.strip(), stdout)

    def test_사용자가_명령을_돌린_뒤의_답은_댓글_판단을_묻지_않는다(self):
        stdout = self.check([
            human("진행해"),
            answer(COMMIT_ANSWER),
            human("중첩이 꼭 필요해?"),
            answer("필요합니다. 결정이 그대로라 댓글 대상이 아닙니다."),
            user_command('cd /repo && git commit -m "[Test] 실패 테스트 하나"'),
            bash_call("s1", "cd /repo && git status --short"),
            bash_result("s1", " M a.java"),
            answer(COMMIT_ANSWER),
        ])
        self.assertEqual("", stdout.strip(), stdout)

    def test_heredoc_본문에_적힌_댓글_명령은_댓글을_올린_것으로_세지_않는다(self):
        stdout = self.check([
            human("진행해"),
            answer(COMMIT_ANSWER),
            human("중첩이 꼭 필요해?"),
            bash_call("p1", "python3 - <<'EOF'\ncmd = 'cd /repo && gh pr comment 13 --body x'\nEOF"),
            bash_result("p1", "exit 2"),
            answer("필요합니다. 안쪽 finally 가 정리를 보장합니다."),
        ])
        self.assertIn("block", stdout)
        self.assertIn("반박", stdout)

    def test_검토_줄에_댓글_주소가_없는_커밋_명령을_막는다(self):
        stdout = self.check([
            human("반영해"),
            bash_call("s1", "cd /repo && git status --short"),
            bash_result("s1", " M a.java"),
            answer('```bash\ncd /repo && git add a.java && git commit -m "[Feat] 바꾼다" -m "검토: 지적 → 바뀐 것"\n```\n'),
        ])
        self.assertIn("block", stdout)
        self.assertIn("댓글 주소", stdout)

    def test_댓글을_올린_뒤_커밋_명령만_주고_푸시가_없으면_막는다(self):
        stdout = self.check([
            human("반영해"),
            bash_call("g1", "cd /repo && gh pr comment 13 --body-file /private/tmp/s/comment.md"),
            bash_result("g1", "https://github.com/o/r/pull/13#issuecomment-1"),
            bash_call("s1", "cd /repo && git status --short"),
            bash_result("s1", " M a.java"),
            answer(REVIEW_COMMIT),
        ])
        self.assertIn("block", stdout)
        self.assertIn("git push", stdout)

    def test_댓글을_반영한_커밋을_사용자가_돌린_뒤에는_푸시_블록을_묻지_않는다(self):
        stdout = self.check([
            human("반영해"),
            bash_call("g1", "cd /repo && gh pr comment 13 --body-file /private/tmp/s/comment.md"),
            bash_result("g1", "https://github.com/o/r/pull/13#issuecomment-1"),
            answer(REVIEW_COMMIT + "\n```bash\ncd /repo && git push\n```\n"),
            user_command('cd /repo && git add a.java && git commit -m "[Refactor] 바꾼다"'),
            user_command("cd /repo && git push"),
            bash_call("s1", "cd /repo && git status --short"),
            bash_result("s1", " M b.java"),
            answer(COMMIT_ANSWER),
        ])
        self.assertEqual("", stdout.strip(), stdout)

    def test_댓글을_올린_뒤_커밋과_푸시_명령을_주면_통과한다(self):
        stdout = self.check([
            human("반영해"),
            bash_call("g1", "cd /repo && gh pr comment 13 --body-file /private/tmp/s/comment.md"),
            bash_result("g1", "https://github.com/o/r/pull/13#issuecomment-1"),
            bash_call("s1", "cd /repo && git status --short"),
            bash_result("s1", " M a.java"),
            answer(REVIEW_COMMIT + "\n```bash\ncd /repo && git push\n```\n"),
        ])
        self.assertEqual("", stdout.strip(), stdout)


# codex-cross-check 「진행」. 교차 검증의 Codex 작업은 crosscheck.py run 으로 감싸 모델과 사용량을 기록한다
class CrossCheckRun(unittest.TestCase):
    def test_Codex_작업을_crosscheck_run_없이_직접_호출하면_반려한다(self):
        cases = {
            "직접 호출": (CROSS_CHECK_TASK, "block"),
            "run 으로 감싼 호출": (f"{CROSSCHECK_RUN} {CROSS_CHECK_TASK}", ""),
            "독자 테스트": (f"{COMPANION} task --fresh --cwd /private/tmp/s/reader-test-plan "
                        "--prompt-file /private/tmp/s/reader-test-plan/prompt.txt", ""),
            "독자 테스트 폴더의 파일만 넘긴 교차 검증": (f"{COMPANION} task --fresh --cwd /repo "
                                          "--prompt-file /private/tmp/s/reader-test-plan/judge.md", "block"),
            "작업이 아닌 명령": (f"{COMPANION} setup --json && {COMPANION} status && {COMPANION} result", ""),
            "heredoc 본문에 적힌 호출": (f"cat > /private/tmp/s/p.md <<'EOF'\n{CROSS_CHECK_TASK}\nEOF", ""),
        }
        for name, (command, expected) in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as folder:
                rows = [human("교차 검증해"), bash_call("c1", command), bash_result("c1", "## 답"),
                        answer("검증을 마쳤습니다.")]
                stdout = run(transcript(rows, folder)).stdout
                if expected:
                    self.assertIn("crosscheck.py run", stdout)
                else:
                    self.assertEqual("", stdout.strip(), stdout)

    def test_note_로_기록한_항목의_제목이_답변에_없으면_반려한다(self):
        crosscheck = "python3 ~/.claude/skills/codex-cross-check/crosscheck.py"
        notes = (f"{crosscheck} note --session s1 --item '한도 이름' --round 1 --claude '한도 기간으로 정한다' "
                 f"--codex '같다' --decision 일치 && {crosscheck} note --session s1 --item '기록 위치' --round 1 "
                 "--claude '세션마다 파일 하나' --codex '같다' --decision 일치")
        noted = [human("교차 검증해"), bash_call("n1", notes), bash_result("n1", "")]
        cases = {
            "두 항목 모두 보고": ([*noted, answer("1. 한도 이름\n2. 기록 위치")], None),
            "한 항목 누락": ([*noted, answer("1. 한도 이름")], "기록 위치"),
            "앞선 요청에서 기록한 항목": ([*noted, answer("1. 한도 이름\n2. 기록 위치"),
                                  human("다음 작업 진행해"), answer("진행했습니다.")], None),
            "앞선 답변에서 보고한 뒤 사용자 명령": ([*noted, answer("1. 한도 이름\n2. 기록 위치"),
                                        user_command('git commit -m "[Docs] 보고"'), answer("커밋이 들어갔습니다.")], None),
            "note 전 답변에만 제목": ([human("교차 검증해"), answer("한도 이름과 기록 위치를 검증합니다."),
                                bash_call("n1", notes), bash_result("n1", ""), answer("1. 한도 이름")], "기록 위치"),
            "heredoc 본문에 적힌 note 명령": ([human("교차 검증해"),
                                         bash_call("p1", f"cat > /private/tmp/s/p.md <<'EOF'\n{notes}\nEOF"),
                                         bash_result("p1", ""), answer("프롬프트를 작성했습니다.")], None),
        }
        for name, (rows, missing) in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as folder:
                stdout = run(transcript(rows, folder)).stdout
                if missing:
                    self.assertIn("block", stdout)
                    self.assertIn(missing, stdout)
                    self.assertNotIn("한도 이름", stdout)
                else:
                    self.assertEqual("", stdout.strip(), stdout)


def codex_call(call_id, command):
    return {"type": "response_item", "payload": {
        "type": "custom_tool_call", "call_id": call_id, "name": "exec",
        "input": 'text(await tools.exec_command({cmd:"%s"}))' % command}}


def codex_result(call_id, output):
    return {"type": "response_item", "payload": {
        "type": "custom_tool_call_output", "call_id": call_id,
        "output": [{"type": "input_text", "text": output}]}}


def codex_message(role, text):
    key = "input_text" if role == "user" else "output_text"
    return {"type": "response_item", "payload": {
        "type": "message", "role": role, "content": [{"type": key, "text": text}]}}


class StopCheckCodex(unittest.TestCase):
    def test_Codex_기록에서도_빨간_상태의_커밋_명령을_막는다(self):
        rows = [
            codex_message("user", "테스트 돌리고 커밋 명령 줘"),
            codex_call("c1", "python3 tests/test_x.py"),
            codex_result("c1", "FAIL: test_x\nRan 1 test\n\nFAILED (failures=1)"),
            codex_call("c2", "git status --short"),
            codex_result("c2", " M a.py"),
            codex_message("assistant", COMMIT_ANSWER),
        ]
        with tempfile.TemporaryDirectory() as folder:
            result = run(transcript(rows, folder))
            self.assertIn("block", result.stdout)
            self.assertIn("GREEN", result.stdout)

    def test_도구가_끼워_넣은_메시지는_사람_발화로_보지_않는다(self):
        rows = [
            codex_message("user", "테스트 돌리고 커밋 명령 줘"),
            codex_call("c1", "python3 tests/test_x.py"),
            codex_result("c1", "FAIL: test_x\nFAILED (failures=1)"),
            codex_call("c2", "git status --short"),
            codex_result("c2", " M a.py"),
            codex_message("user", '<hook_prompt hook_run_id="stop:5:/x/hooks.json">[stop-check] 이전 지적</hook_prompt>'),
            codex_message("assistant", COMMIT_ANSWER),
        ]
        with tempfile.TemporaryDirectory() as folder:
            result = run(transcript(rows, folder))
            self.assertIn("GREEN", result.stdout)
            self.assertNotIn("상태를 확인한다", result.stdout)

    def test_Codex_출력의_종료_코드로_실패를_읽는다(self):
        chunk = ('{"chunk_id":"8f72b7","exit_code":1,'
                 '"output":"F\\n====\\nFAIL: test_x\\n----\\nAssertionError\\n"}')
        rows = [
            codex_message("user", "테스트 돌리고 커밋 명령 줘"),
            codex_call("c1", "python3 tests/test_x.py"),
            codex_result("c1", "Script completed\nWall time 2.9 seconds\nOutput:\n"),
            codex_call("c2", "git status --short"),
            codex_result("c2", " M a.py"),
            codex_message("assistant", COMMIT_ANSWER),
        ]
        rows[2]["payload"]["output"].append({"type": "input_text", "text": chunk})
        with tempfile.TemporaryDirectory() as folder:
            result = run(transcript(rows, folder))
            self.assertIn("GREEN", result.stdout)

    def test_한_호출에_담긴_명령을_모두_본다(self):
        many = ('text(await tools.exec_command({cmd:"cat SKILL.md",max_output_tokens:3000}));\n'
                'text(await tools.exec_command({cmd:"python3 tests/test_x.py",max_output_tokens:2000}));\n'
                'text(await tools.exec_command({cmd:"git status --short",max_output_tokens:2000}));')
        rows = [
            codex_message("user", "테스트 돌리고 커밋 명령 줘"),
            {"type": "response_item", "payload": {
                "type": "custom_tool_call", "call_id": "c1", "name": "exec", "input": many}},
            codex_result("c1", '{"exit_code":1,"output":"FAIL"}'),
            codex_message("assistant", COMMIT_ANSWER),
        ]
        with tempfile.TemporaryDirectory() as folder:
            result = run(transcript(rows, folder))
            self.assertIn("GREEN", result.stdout)
            self.assertNotIn("상태를 확인한다", result.stdout)


if __name__ == "__main__":
    unittest.main()
