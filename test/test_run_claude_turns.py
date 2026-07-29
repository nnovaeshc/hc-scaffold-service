#!/usr/bin/env python3
"""Unit tests for multi-turn script builder (no Claude / Bedrock / docker)."""
import unittest

from run_claude_turns import build_claude_argv, build_inner_script, extract_session_id, shell_quote


class TestShellQuote(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(shell_quote("Yes"), "'Yes'")

    def test_embedded_quote(self):
        self.assertEqual(shell_quote("it's"), "'it'\\''s'")


class TestExtractSessionId(unittest.TestCase):
    def test_from_system_line(self):
        text = '{"type":"system","session_id":"abc-123"}\n{"type":"assistant"}\n'
        self.assertEqual(extract_session_id(text), "abc-123")

    def test_missing(self):
        self.assertIsNone(extract_session_id('{"type":"assistant"}\nnot json\n'))


class TestBuildInnerScript(unittest.TestCase):
    def test_single_turn_no_resume(self):
        script = build_inner_script("Create a service", [])
        self.assertIn("claude", script)
        self.assertIn("'Create a service'", script)
        self.assertNotIn("--resume", script)
        self.assertIn('cat "$OUT"', script)

    def test_multi_turn_uses_resume(self):
        script = build_inner_script("Create a repo", ["Yes", "Yes, submit"])
        self.assertIn("--resume", script)
        self.assertIn('"$SESSION"', script)
        self.assertIn("'Yes'", script)
        self.assertIn("'Yes, submit'", script)
        self.assertIn("session_id", script)

    def test_build_claude_argv_resume(self):
        argv = build_claude_argv("Yes", resume="sid-1", model="m", effort="low")
        self.assertEqual(argv[:2], ["claude", "-p"])
        self.assertIn("--resume", argv)
        self.assertIn("sid-1", argv)
        self.assertIn("--model", argv)
        self.assertEqual(argv[-1], "Yes")


if __name__ == "__main__":
    unittest.main()
