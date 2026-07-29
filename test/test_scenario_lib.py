#!/usr/bin/env python3
"""Unit tests for scenario_lib replies parsing (no Claude / Bedrock)."""
import tempfile
import unittest
from pathlib import Path

from scenario_lib import load_scenario


class TestLoadReplies(unittest.TestCase):
    def test_replies_list(self):
        text = """name: sample
prompt: Create something
replies:
  - "Yes"
  - "Yes, submit"
expectations:
  - tool_called: execute-template
"""
        path = Path(tempfile.mkdtemp()) / "sample.yaml"
        path.write_text(text)
        scenario = load_scenario(str(path))
        self.assertEqual(scenario["replies"], ["Yes", "Yes, submit"])
        self.assertEqual(len(scenario["expectations"]), 1)

    def test_missing_replies_defaults_empty(self):
        text = """name: sample
prompt: Create something
expectations:
  - tool_not_called: execute-template
"""
        path = Path(tempfile.mkdtemp()) / "sample.yaml"
        path.write_text(text)
        scenario = load_scenario(str(path))
        self.assertEqual(scenario["replies"], [])


if __name__ == "__main__":
    unittest.main()
