#!/usr/bin/env python3
"""commit-checkpoint 훅 테스트.

실행: python3 ~/.claude/hooks/tests/test_commit_checkpoint.py
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent / "commit-checkpoint.py"


def repo_with_change(folder):
    """미커밋 변경이 하나 있는 저장소를 만든다."""
    subprocess.run(["git", "init", "-q"], cwd=folder, check=True)
    (Path(folder) / "a.py").write_text("print('ok')\n", encoding="utf-8")


def write_row(path):
    """Write 도구 호출이 대화 기록에 남는 꼴."""
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": "toolu_w", "name": "Write", "input": {"file_path": str(path), "content": "x"}}]}}


def run(command, response, cwd, transcript=None):
    payload = {
        "hook_event_name": "PostToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "tool_response": response,
    }
    if transcript:
        payload["transcript_path"] = transcript
    return subprocess.run(
        [sys.executable, str(HOOK)], input=json.dumps(payload),
        capture_output=True, text=True, cwd=cwd,
    )


class CommitCheckpoint(unittest.TestCase):
    def test_파이썬_테스트가_통과하면_체크포인트를_낸다(self):
        with tempfile.TemporaryDirectory() as folder:
            repo_with_change(folder)
            result = run(
                "python3 tests/test_stop_check.py",
                "Ran 1 test in 0.03s\n\nOK",
                folder,
            )
            self.assertIn("block", result.stdout)
            self.assertIn("체크포인트", result.stdout)

    def test_테스트가_실패하면_체크포인트를_내지_않는다(self):
        with tempfile.TemporaryDirectory() as folder:
            repo_with_change(folder)
            result = run(
                "python3 ~/.claude/hooks/tests/test_stop_check.py",
                "FAIL: test_x\nRan 1 test in 0.03s\n\nFAILED (failures=1)\n",
                folder,
            )
            self.assertEqual("", result.stdout.strip(), result.stdout)

    def test_따옴표_안의_테스트_명령은_실행으로_보지_않는다(self):
        with tempfile.TemporaryDirectory() as folder:
            repo_with_change(folder)
            result = run(
                'claude -p "python3 tests/test_x.py 를 돌려줘" --output-format json',
                "세션이 끝났다",
                folder,
            )
            self.assertEqual("", result.stdout.strip(), result.stdout)

    def test_명령_앞의_cd_가_가리키는_저장소를_센다(self):
        with tempfile.TemporaryDirectory() as here, tempfile.TemporaryDirectory() as there:
            subprocess.run(["git", "init", "-q"], cwd=here, check=True)
            repo_with_change(there)
            result = run(
                f"cd {there} && python3 tests/test_x.py",
                "Ran 1 test in 0.03s\n\nOK",
                here,
            )
            self.assertIn("block", result.stdout)
            self.assertIn(there, result.stdout)

    def test_저장소_밖의_테스트_파일이면_체크포인트를_내지_않는다(self):
        with tempfile.TemporaryDirectory() as here, tempfile.TemporaryDirectory() as away:
            repo_with_change(here)
            outside = Path(away) / "test_usage.py"
            outside.write_text("", encoding="utf-8")
            result = run(f"python3 {outside}", "Ran 1 test in 0.03s\n\nOK", here)
            self.assertEqual("", result.stdout.strip(), result.stdout)

    def test_cd_가_변수면_어느_저장소인지_모르니_내지_않는다(self):
        with tempfile.TemporaryDirectory() as folder:
            repo_with_change(folder)
            result = run(
                'P=/tmp/x; cd "$P" && python3 tests/test_x.py',
                "Ran 1 test in 0.03s\n\nOK",
                folder,
            )
            self.assertEqual("", result.stdout.strip(), result.stdout)

    def test_이번_세션에서_고친_파일이_남았을_때만_체크포인트를_낸다(self):
        with tempfile.TemporaryDirectory() as folder, tempfile.TemporaryDirectory() as logs:
            repo_with_change(folder)
            log = Path(logs) / "transcript.jsonl"
            cases = {
                "세션 전부터 있던 변경뿐": ([], False),
                "이번 세션에서 고친 파일": ([write_row(Path(folder) / "a.py")], True),
            }
            for name, (rows, expected) in cases.items():
                with self.subTest(name=name):
                    log.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
                    result = run("python3 tests/test_x.py", "Ran 1 test in 0.03s\n\nOK", folder, str(log))
                    self.assertEqual(expected, "체크포인트" in result.stdout, result.stdout)

    def test_파일_이름에_빌드_도구_이름이_있는_조회_명령은_실행으로_보지_않는다(self):
        with tempfile.TemporaryDirectory() as folder:
            repo_with_change(folder)
            for command in ("grep -n jackson build.gradle", "git show HEAD:build.gradle | head", "ls gradle/"):
                with self.subTest(command=command):
                    result = run(command, "implementation 'x'", folder)
                    self.assertEqual("", result.stdout.strip(), result.stdout)

    def test_명령_자리에_온_빌드_도구는_실행으로_본다(self):
        with tempfile.TemporaryDirectory() as folder:
            repo_with_change(folder)
            for command in ("./gradlew test --tests FooTest", "JAVA_HOME=/opt/jdk ./gradlew build", "npx vitest run",
                            'for f in tests/test_*.py; do python3 "$f"; done'):
                with self.subTest(command=command):
                    result = run(command, "BUILD SUCCESSFUL", folder)
                    self.assertIn("체크포인트", result.stdout)

    def test_명령이_아예_실행되지_못하면_체크포인트를_내지_않는다(self):
        with tempfile.TemporaryDirectory() as folder:
            repo_with_change(folder)
            for output in ("zsh: command not found: pytest",
                           "python3: can't open file 'tests/test_x.py': "
                           "[Errno 2] No such file or directory"):
                result = run("python3 tests/test_x.py", output, folder)
                self.assertEqual("", result.stdout.strip(), output)


if __name__ == "__main__":
    unittest.main()
