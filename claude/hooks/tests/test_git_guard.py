#!/usr/bin/env python3
"""git-guard 훅 테스트.

실행: python3 ~/.claude/hooks/tests/test_git_guard.py
"""
import importlib.util
import unittest
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent / "git-guard.py"
_spec = importlib.util.spec_from_file_location("git_guard", HOOK)
git_guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(git_guard)


class PrFirst(unittest.TestCase):
    def test_브랜치에_커밋이_하나_있는데_PR_이_없으면_막는다(self):
        self.assertTrue(git_guard.needs_pr("docs/doc-writing-skill", 1, False))


if __name__ == "__main__":
    unittest.main()
