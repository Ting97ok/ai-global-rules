#!/usr/bin/env python3
"""doc-skill-guard 훅 테스트.

실행: python3 ~/.claude/hooks/tests/test_doc_skill_guard.py
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent / "doc-skill-guard.py"


def skill_call(name):
    """Skill 도구 호출이 대화 기록에 남는 꼴."""
    return {
        "type": "assistant",
        "message": {
            "content": [
                {"type": "tool_use", "id": "toolu_1", "name": "Skill", "input": {"skill": name}}
            ]
        },
    }


def user_text(text):
    """사용자가 직접 쓴 메시지가 대화 기록에 남는 꼴."""
    return {"type": "user", "message": {"role": "user", "content": text}}


def write_call(path):
    """Write 도구 호출이 대화 기록에 남는 꼴."""
    return {
        "type": "assistant",
        "message": {"content": [
            {"type": "tool_use", "id": "toolu_w", "name": "Write", "input": {"file_path": str(path), "content": "x"}}
        ]},
    }


def tool_error(call_id):
    """도구 호출이 오류로 끝난 결과가 대화 기록에 남는 꼴."""
    return {"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": call_id, "content": "String to replace not found", "is_error": True}]}}


def transcript(rows, folder):
    path = Path(folder) / "transcript.jsonl"
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    return str(path)


def run(payload):
    return subprocess.run(
        [sys.executable, str(HOOK)], input=json.dumps(payload), capture_output=True, text=True
    )


class DocSkillGuard(unittest.TestCase):
    def test_스킬을_부르지_않고_문서를_쓰면_막는다(self):
        with tempfile.TemporaryDirectory() as folder:
            doc = Path(folder) / "docs" / "a.md"
            doc.parent.mkdir()
            result = run(
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "Write",
                    "transcript_path": transcript([skill_call("humanize-korean")], folder),
                    "tool_input": {"file_path": str(doc)},
                }
            )
            self.assertEqual(2, result.returncode, result.stderr)
            self.assertIn("doc-writing", result.stderr)

    def test_docs_밖의_문서도_스킬_없이_쓰면_막는다(self):
        with tempfile.TemporaryDirectory() as folder:
            doc = Path(folder) / "resume" / "이력서.md"
            result = run(
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "Write",
                    "transcript_path": transcript([skill_call("humanize-korean")], folder),
                    "tool_input": {"file_path": str(doc)},
                }
            )
            self.assertEqual(2, result.returncode, result.stderr)
            self.assertIn("doc-writing", result.stderr)

    def test_캐묻지_않고_새_문서를_만들면_막는다(self):
        with tempfile.TemporaryDirectory() as folder:
            doc = Path(folder) / "design" / "plan.html"
            result = run(
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "Write",
                    "transcript_path": transcript([skill_call("doc-writing")], folder),
                    "tool_input": {"file_path": str(doc)},
                }
            )
            self.assertEqual(2, result.returncode, result.stderr)
            self.assertIn("grill-me", result.stderr)

    def test_이미_있는_문서를_캐묻지_않고_고쳐도_막는다(self):
        with tempfile.TemporaryDirectory() as folder:
            doc = Path(folder) / "design" / "plan.html"
            doc.parent.mkdir()
            doc.write_text("<p>계획</p>\n", encoding="utf-8")
            result = run(
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "Edit",
                    "transcript_path": transcript([skill_call("doc-writing")], folder),
                    "tool_input": {"file_path": str(doc)},
                }
            )
            self.assertEqual(2, result.returncode, result.stderr)
            self.assertIn("grill-me", result.stderr)

    def test_캐묻기_스킬을_불렀으면_새_문서를_만들_수_있다(self):
        with tempfile.TemporaryDirectory() as folder:
            doc = Path(folder) / "design" / "plan.html"
            for grill in ("grill-me", "grill-with-docs"):
                with self.subTest(grill=grill):
                    result = run(
                        {
                            "hook_event_name": "PreToolUse",
                            "tool_name": "Write",
                            "transcript_path": transcript([skill_call("doc-writing"), skill_call(grill)], folder),
                            "tool_input": {"file_path": str(doc)},
                        }
                    )
                    self.assertEqual(0, result.returncode, result.stderr)

    def test_앞선_요청에서_부른_캐묻기는_새_요청에_쓰지_않는다(self):
        with tempfile.TemporaryDirectory() as folder:
            doc = Path(folder) / "design" / "plan.html"
            rows = [
                user_text("계획 문서 써 줘"),
                skill_call("doc-writing"),
                skill_call("grill-me"),
                user_text("이번엔 다른 문서를 고쳐 줘"),
            ]
            result = run(
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "Write",
                    "transcript_path": transcript(rows, folder),
                    "tool_input": {"file_path": str(doc)},
                }
            )
            self.assertEqual(2, result.returncode, result.stderr)
            self.assertIn("grill-me", result.stderr)

    def test_캐물은_뒤_쓴_문서는_새_요청에서도_다시_묻지_않는다(self):
        with tempfile.TemporaryDirectory() as folder:
            doc = Path(folder) / "design" / "plan.html"
            other = Path(folder) / "design" / "other.html"
            rows = [
                user_text("계획 문서 써 줘"),
                skill_call("doc-writing"),
                skill_call("grill-me"),
                write_call(doc),
                user_text("리뷰 반영해서 이 문장 고쳐 줘"),
            ]
            for path, expected in ((doc, 0), (other, 2)):
                with self.subTest(path=path.name):
                    result = run(
                        {
                            "hook_event_name": "PreToolUse",
                            "tool_name": "Edit",
                            "transcript_path": transcript(rows, folder),
                            "tool_input": {"file_path": str(path)},
                        }
                    )
                    self.assertEqual(expected, result.returncode, result.stderr)

    def test_실패한_쓰기는_캐물은_문서로_세지_않는다(self):
        with tempfile.TemporaryDirectory() as folder:
            doc = Path(folder) / "design" / "other.html"
            rows = [
                user_text("계획 문서 써 줘"),
                skill_call("doc-writing"),
                skill_call("grill-me"),
                write_call(doc),
                tool_error("toolu_w"),
                user_text("이번엔 저 문서를 고쳐 줘"),
            ]
            result = run(
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "Edit",
                    "transcript_path": transcript(rows, folder),
                    "tool_input": {"file_path": str(doc)},
                }
            )
            self.assertEqual(2, result.returncode, result.stderr)

    def test_질문_창의_답은_새_요청으로_보지_않는다(self):
        answer = {
            "type": "user",
            "toolUseResult": {"answers": {"독자가 누구입니까?": "외부 개발자"}},
            "message": {"content": [{"type": "tool_result", "tool_use_id": "toolu_q", "content": "외부 개발자"}]},
        }
        with tempfile.TemporaryDirectory() as folder:
            doc = Path(folder) / "design" / "plan.html"
            rows = [user_text("계획 문서 써 줘"), skill_call("doc-writing"), skill_call("grill-me"), answer]
            result = run(
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "Write",
                    "transcript_path": transcript(rows, folder),
                    "tool_input": {"file_path": str(doc)},
                }
            )
            self.assertEqual(0, result.returncode, result.stderr)

    def test_컴팩트_요약은_새_요청으로_보지_않는다(self):
        summary = {"type": "user", "isCompactSummary": True, "isVisibleInTranscriptOnly": True,
                   "message": {"role": "user", "content": "This session is being continued from a previous conversation."}}
        with tempfile.TemporaryDirectory() as folder:
            doc = Path(folder) / "design" / "plan.html"
            rows = [user_text("계획 문서 써 줘"), skill_call("doc-writing"), skill_call("grill-me"), summary]
            result = run(
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "Write",
                    "transcript_path": transcript(rows, folder),
                    "tool_input": {"file_path": str(doc)},
                }
            )
            self.assertEqual(0, result.returncode, result.stderr)

    def test_앞선_요청의_캐묻기_생략은_새_요청에_쓰지_않는다(self):
        with tempfile.TemporaryDirectory() as folder:
            doc = Path(folder) / "design" / "plan.html"
            rows = [user_text("캐묻기 생략"), skill_call("doc-writing"), user_text("이제 다른 문서도 고쳐 줘")]
            result = run(
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "Write",
                    "transcript_path": transcript(rows, folder),
                    "tool_input": {"file_path": str(doc)},
                }
            )
            self.assertEqual(2, result.returncode, result.stderr)

    def test_캐묻기_생략은_한_줄에_그_말만_썼을_때만_센다(self):
        cases = {
            "따로 쓴 줄": ("이번 메모는 바로 써 줘\n캐묻기 생략", 0),
            "부정하는 문장": ("캐묻기 생략은 하지 마", 2),
            "문장 속에 섞인 말": ("이번 메모는 캐묻기 생략하고 바로 써 줘", 2),
        }
        with tempfile.TemporaryDirectory() as folder:
            doc = Path(folder) / "design" / "plan.html"
            for name, (text, expected) in cases.items():
                with self.subTest(name=name):
                    result = run(
                        {
                            "hook_event_name": "PreToolUse",
                            "tool_name": "Write",
                            "transcript_path": transcript([user_text(text), skill_call("doc-writing")], folder),
                            "tool_input": {"file_path": str(doc)},
                        }
                    )
                    self.assertEqual(expected, result.returncode, result.stderr)

    def test_스킬_본문이나_작업_알림의_캐묻기_생략_문구로는_통과하지_않는다(self):
        rows = {
            "스킬 본문": {"type": "user", "isMeta": True,
                      "message": {"role": "user", "content": "사용자가 「캐묻기 생략」이라고 하면 건너뛴다"}},
            "작업 알림": user_text("<task-notification>\n<summary>캐묻기 생략 확인</summary>\n</task-notification>"),
        }
        with tempfile.TemporaryDirectory() as folder:
            doc = Path(folder) / "design" / "plan.html"
            for name, row in rows.items():
                with self.subTest(name=name):
                    result = run(
                        {
                            "hook_event_name": "PreToolUse",
                            "tool_name": "Write",
                            "transcript_path": transcript([skill_call("doc-writing"), row], folder),
                            "tool_input": {"file_path": str(doc)},
                        }
                    )
                    self.assertEqual(2, result.returncode, result.stderr)

    def test_질문_창의_답만_캐묻기_생략으로_센다(self):
        def answer_row(question, answer):
            return {
                "type": "user",
                "toolUseResult": {"questions": [{"question": question}], "answers": {question: answer}},
                "message": {"role": "user", "content": [
                    {"type": "tool_result", "tool_use_id": "toolu_q", "content": f'"{question}"="{answer}"'}]},
            }

        cases = {
            "답이 캐묻기 생략": (answer_row("이 문서를 어떻게 시작할까요?", "캐묻기 생략"), 0),
            "질문에만 그 말이 있음": (answer_row("캐묻기 생략할까요?", "아니, 물어봐"), 2),
        }
        with tempfile.TemporaryDirectory() as folder:
            doc = Path(folder) / "design" / "plan.html"
            for name, (row, expected) in cases.items():
                with self.subTest(name=name):
                    result = run(
                        {
                            "hook_event_name": "PreToolUse",
                            "tool_name": "Write",
                            "transcript_path": transcript([skill_call("doc-writing"), row], folder),
                            "tool_input": {"file_path": str(doc)},
                        }
                    )
                    self.assertEqual(expected, result.returncode, result.stderr)

    def test_AI_설정과_규칙_파일과_임시_파일은_스킬_없이도_통과한다(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = [
                Path(folder) / ".claude" / "agents" / "reviewer.md",
                Path(folder) / ".agents" / "skills" / "doc-writing" / "SKILL.md",
                Path(folder) / ".gemini" / "styleguide.md",
                Path(folder) / ".cursor" / "rules" / "style.md",
                Path(folder) / "CLAUDE.md",
                Path(folder) / "AGENTS.md",
                Path(folder) / "GEMINI.md",
                Path("/private/tmp/claude-501/scratchpad/answer.md"),
                Path("/tmp/note.html"),
            ]
            for path in paths:
                with self.subTest(path=str(path)):
                    result = run(
                        {
                            "hook_event_name": "PreToolUse",
                            "tool_name": "Write",
                            "transcript_path": transcript([skill_call("humanize-korean")], folder),
                            "tool_input": {"file_path": str(path)},
                        }
                    )
                    self.assertEqual(0, result.returncode, result.stderr)

    def test_도구_규약_폴더의_html_은_문서가_아니다(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = [
                Path(folder) / "src" / "main" / "resources" / "templates" / "installer.html",
                Path(folder) / "web" / "public" / "index.html",
                Path(folder) / "build" / "reports" / "tests" / "index.html",
            ]
            for path in paths:
                with self.subTest(path=str(path)):
                    result = run(
                        {
                            "hook_event_name": "PreToolUse",
                            "tool_name": "Write",
                            "transcript_path": transcript([skill_call("humanize-korean")], folder),
                            "tool_input": {"file_path": str(path)},
                        }
                    )
                    self.assertEqual(0, result.returncode, result.stderr)

    def test_앱_진입_html_은_문서가_아니다(self):
        with tempfile.TemporaryDirectory() as folder:
            existing = Path(folder) / "admin-fe" / "index.html"
            existing.parent.mkdir()
            existing.write_text('<body><div id="root"></div></body>\n', encoding="utf-8")
            cases = {
                "이미 있는 파일": {"file_path": str(existing)},
                "새 파일": {"file_path": str(Path(folder) / "guard-fe" / "index.html"),
                          "content": '<script type="module" src="/src/main.ts"></script>\n'},
            }
            for name, tool_input in cases.items():
                with self.subTest(name=name):
                    result = run(
                        {
                            "hook_event_name": "PreToolUse",
                            "tool_name": "Write",
                            "transcript_path": transcript([skill_call("humanize-korean")], folder),
                            "tool_input": tool_input,
                        }
                    )
                    self.assertEqual(0, result.returncode, result.stderr)

    def test_앱_진입_표시는_따옴표와_속성_순서가_달라도_알아본다(self):
        contents = {
            "작은따옴표 id": "<body><div class='app'></div><div id='app'></div></body>\n",
            "src 가 type 보다 앞": '<script src="/src/main.ts" type="module"></script>\n',
            "src 없는 모듈 스크립트": "<script type='module'>import './main.js'</script>\n",
        }
        with tempfile.TemporaryDirectory() as folder:
            for name, content in contents.items():
                with self.subTest(name=name):
                    result = run(
                        {
                            "hook_event_name": "PreToolUse",
                            "tool_name": "Write",
                            "transcript_path": transcript([skill_call("humanize-korean")], folder),
                            "tool_input": {"file_path": str(Path(folder) / "fe" / "index.html"), "content": content},
                        }
                    )
                    self.assertEqual(0, result.returncode, result.stderr)

    def test_리소스_폴더의_md_는_문서로_본다(self):
        with tempfile.TemporaryDirectory() as folder:
            doc = Path(folder) / "src" / "main" / "resources" / "docs" / "notice" / "api-design.md"
            result = run(
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "Write",
                    "transcript_path": transcript([skill_call("humanize-korean")], folder),
                    "tool_input": {"file_path": str(doc)},
                }
            )
            self.assertEqual(2, result.returncode, result.stderr)

    def test_문서가_아닌_파일은_스킬_없이도_통과한다(self):
        with tempfile.TemporaryDirectory() as folder:
            code = Path(folder) / "src" / "app.py"
            code.parent.mkdir()
            result = run(
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "Write",
                    "transcript_path": transcript([skill_call("humanize-korean")], folder),
                    "tool_input": {"file_path": str(code)},
                }
            )
            self.assertEqual(0, result.returncode, result.stderr)

    def test_셸로_문서를_고쳐도_막는다(self):
        with tempfile.TemporaryDirectory() as folder:
            result = run({
                "hook_event_name": "PreToolUse", "tool_name": "Bash",
                "tool_input": {"command": 'python3 -c \'import pathlib; pathlib.Path("README.md").write_text("x")\''},
                "transcript_path": transcript([], folder),
            })
            self.assertEqual(2, result.returncode, result.stderr)
            self.assertIn("doc-writing", result.stderr)
            self.assertIn("명령 전체가 실행되지 않았다", result.stderr)

    def test_파이썬으로_문서에_쓰는_여러_꼴을_잡는다(self):
        commands = {
            "open 쓰기": "python3 -c 'open(\"README.md\", \"w\").write(\"x\")'",
            "Path.open 쓰기": "python3 -c 'import pathlib; pathlib.Path(\"README.md\").open(\"w\").write(\"x\")'",
            "write_bytes": "python3 -c 'import pathlib; pathlib.Path(\"README.md\").write_bytes(b\"x\")'",
            "heredoc 안의 open 쓰기": "python3 - <<'PY'\nopen(\"README.md\", \"w\").write(\"x\")\nPY",
        }
        with tempfile.TemporaryDirectory() as folder:
            for name, command in commands.items():
                with self.subTest(name=name):
                    result = run({
                        "hook_event_name": "PreToolUse", "tool_name": "Bash",
                        "tool_input": {"command": command},
                        "transcript_path": transcript([], folder),
                    })
                    self.assertEqual(2, result.returncode, result.stderr)

    def test_문서가_아닌_내용을_문서_자리로_복사하거나_옮기면_막는다(self):
        commands = {
            "임시 파일을 옮김": "mv /private/tmp/draft/plan.md docs/plan.md",
            "변수로 적은 임시 파일을 옮김": 'S=/private/tmp/draft; mv "$S/plan.md" docs/plan.md',
            "문서가 아닌 파일을 복사": "cp -f draft.txt docs/plan.md && echo done",
        }
        with tempfile.TemporaryDirectory() as folder:
            for name, command in commands.items():
                with self.subTest(name=name):
                    result = run({
                        "hook_event_name": "PreToolUse", "tool_name": "Bash",
                        "tool_input": {"command": command},
                        "transcript_path": transcript([], folder),
                    })
                    self.assertEqual(2, result.returncode, result.stderr)

    def test_문서가_아닌_내용을_폴더로_복사하거나_옮겨도_막는다(self):
        commands = {
            "있는 폴더": "cp /private/tmp/draft/plan.md docs",
            "슬래시로 끝나는 폴더": "mv /private/tmp/draft/plan.md notes/",
        }
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "docs").mkdir()
            for name, command in commands.items():
                with self.subTest(name=name):
                    result = run({
                        "hook_event_name": "PreToolUse", "tool_name": "Bash", "cwd": folder,
                        "tool_input": {"command": command},
                        "transcript_path": transcript([], folder),
                    })
                    self.assertEqual(2, result.returncode, result.stderr)

    def test_문서끼리_이름을_바꾸거나_복사하면_막지_않는다(self):
        commands = {
            "이름 바꾸기": "mv docs/old.md docs/new.md",
            "틀 복사": "cp docs/template.md docs/plan.md",
        }
        with tempfile.TemporaryDirectory() as folder:
            for name, command in commands.items():
                with self.subTest(name=name):
                    result = run({
                        "hook_event_name": "PreToolUse", "tool_name": "Bash",
                        "tool_input": {"command": command},
                        "transcript_path": transcript([], folder),
                    })
                    self.assertEqual(0, result.returncode, result.stderr)

    def test_같은_명령에서_임시_폴더로_정한_변수_경로에_쓰면_막지_않는다(self):
        commands = {
            "리디렉션": 'S=/private/tmp/reader; cat docs/a.md > "$S/a.md"',
            "sed -i": "S=/private/tmp/reader; sed -i '' 's/a/b/' \"$S/a.md\"",
        }
        with tempfile.TemporaryDirectory() as folder:
            for name, command in commands.items():
                with self.subTest(name=name):
                    result = run({
                        "hook_event_name": "PreToolUse", "tool_name": "Bash",
                        "tool_input": {"command": command},
                        "transcript_path": transcript([], folder),
                    })
                    self.assertEqual(0, result.returncode, result.stderr)

    def test_명령_안의_cd_를_따라_경로를_푼다(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "docs").mkdir()
            commands = {
                "임시 폴더로 들어가 메모에 씀": ("cd /private/tmp/s && cat >> handoff.md <<'EOF'\n메모\nEOF", 0),
                "저장소 문서 폴더로 들어가 씀": (f"cd {folder}/docs && cat > plan.md <<'EOF'\n계획\nEOF", 2),
            }
            for name, (command, expected) in commands.items():
                with self.subTest(name=name):
                    result = run({
                        "hook_event_name": "PreToolUse", "tool_name": "Bash", "cwd": "/Users/someone/repo",
                        "tool_input": {"command": command},
                        "transcript_path": transcript([], folder),
                    })
                    self.assertEqual(expected, result.returncode, result.stderr)

    def test_파이썬으로_문서를_읽기만_하면_막지_않는다(self):
        with tempfile.TemporaryDirectory() as folder:
            result = run({
                "hook_event_name": "PreToolUse", "tool_name": "Bash",
                "tool_input": {"command": "python3 -c 'open(\"report.txt\", \"w\").write(open(\"docs/plan.md\").read())'"},
                "transcript_path": transcript([], folder),
            })
            self.assertEqual(0, result.returncode, result.stderr)

    def test_node_로_문서에_쓰면_막는다(self):
        commands = {
            "writeFileSync": "node -e 'require(\"fs\").writeFileSync(\"docs/plan.md\", \"x\")'",
            "writeFile": "node -e 'require(\"fs\").writeFile(\"docs/plan.md\", \"x\", () => {})'",
        }
        with tempfile.TemporaryDirectory() as folder:
            for name, command in commands.items():
                with self.subTest(name=name):
                    result = run({
                        "hook_event_name": "PreToolUse", "tool_name": "Bash",
                        "tool_input": {"command": command},
                        "transcript_path": transcript([], folder),
                    })
                    self.assertEqual(2, result.returncode, result.stderr)

    def test_perl_로_문서를_제자리에서_고치면_막는다(self):
        commands = {
            "-pi": "perl -pi -e 's/a/b/' docs/plan.md",
            "-i -pe": "perl -i -pe 's/a/b/' docs/plan.md",
        }
        with tempfile.TemporaryDirectory() as folder:
            for name, command in commands.items():
                with self.subTest(name=name):
                    result = run({
                        "hook_event_name": "PreToolUse", "tool_name": "Bash",
                        "tool_input": {"command": command},
                        "transcript_path": transcript([], folder),
                    })
                    self.assertEqual(2, result.returncode, result.stderr)

    def test_셸로_문서를_읽기만_하면_막지_않는다(self):
        commands = {
            "grep": "grep -n 복사 README.md | head -5",
            "perl 모듈 옵션": "perl -Mstrict -ne 'print' docs/plan.md",
            "화살표 문구": 'echo "== SKILL.md.bak -> SKILL.md 비교"; diff SKILL.md.bak SKILL.md',
            "heredoc 본문 속 명령 글자": "python3 - <<'PY'\nprint('cat >> handoff.md')\nPY",
        }
        with tempfile.TemporaryDirectory() as folder:
            for name, command in commands.items():
                with self.subTest(name=name):
                    result = run({
                        "hook_event_name": "PreToolUse", "tool_name": "Bash",
                        "tool_input": {"command": command},
                        "transcript_path": transcript([], folder),
                    })
                    self.assertEqual(0, result.returncode, result.stderr)


if __name__ == "__main__":
    unittest.main()
