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
