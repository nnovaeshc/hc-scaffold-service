#!/usr/bin/env python3
"""Unit tests for assertion dispatch (no Claude / Bedrock)."""
import json
import tempfile
import unittest
from pathlib import Path

from check import TranscriptAsserter, run_assertions


def _write_transcript(tool_uses):
    """Minimal stream-json with assistant tool_use blocks."""
    content = [
        {"type": "tool_use", "id": f"t{i}", "name": name, "input": inp}
        for i, (name, inp) in enumerate(tool_uses)
    ]
    line = json.dumps({
        "type": "assistant",
        "message": {"role": "assistant", "content": content, "usage": {}},
    })
    path = Path(tempfile.mkdtemp()) / "transcript.jsonl"
    path.write_text(line + "\n")
    return path


class TestAssertionAliases(unittest.TestCase):
    def test_tool_call_count_execute_template_dispatches(self):
        path = _write_transcript([
            ("mcp__backstage__execute-template", {"templateRef": "template:default/x", "values": {}}),
        ])
        asserter = TranscriptAsserter(str(path))
        results = run_assertions(asserter, [{"tool_call_count_execute_template": 1}])
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0]["passed"], results[0])
        self.assertNotIn("no assertion implemented", results[0]["evidence"])

    def test_tool_call_count_execute_template_wrong_count(self):
        path = _write_transcript([])
        asserter = TranscriptAsserter(str(path))
        results = run_assertions(asserter, [{"tool_call_count_execute_template": 1}])
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0]["passed"], results[0])
        self.assertIn("called 0 times", results[0]["evidence"])

    def test_backstage_tools_prefixed(self):
        path = _write_transcript([
            ("mcp__backstage__backstage_catalog_query-catalog-entities", {"filter": {}}),
        ])
        asserter = TranscriptAsserter(str(path))
        results = run_assertions(asserter, [{"backstage_tools_prefixed": True}])
        self.assertTrue(results[0]["passed"], results[0])

    def test_backstage_tools_prefixed_rejects_unprefixed(self):
        path = _write_transcript([
            ("mcp__backstage__catalog_query-catalog-entities", {"filter": {}}),
        ])
        asserter = TranscriptAsserter(str(path))
        results = run_assertions(asserter, [{"backstage_tools_prefixed": True}])
        self.assertFalse(results[0]["passed"], results[0])


if __name__ == "__main__":
    unittest.main()
