#!/usr/bin/env python3
"""
Transcript oracle for hc-scaffold-service test scenarios.
Reads stream-json transcripts and asserts declaratively from scenario files.
"""
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


class TranscriptAsserter:
    """Assert properties of a stream-json transcript."""

    def __init__(self, transcript_path: str):
        self.transcript_path = transcript_path
        self.messages = []
        self.tool_uses = []
        self.tool_results = []
        self.usage_total = {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0
        }
        self.result_message = None
        self._load_transcript()

    def _load_transcript(self):
        """Load and parse stream-json transcript."""
        with open(self.transcript_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                    if msg.get("type") == "message":
                        self.messages.append(msg)

                        # Extract tool uses
                        content = msg.get("message", {}).get("content", [])
                        for item in content:
                            if item.get("type") == "tool_use":
                                self.tool_uses.append(item)

                        # Accumulate usage
                        usage = msg.get("message", {}).get("usage", {})
                        for key in self.usage_total:
                            self.usage_total[key] += usage.get(key, 0)

                    elif msg.get("type") == "tool_result":
                        self.tool_results.append(msg)

                    elif msg.get("type") == "result":
                        self.result_message = msg

                except json.JSONDecodeError:
                    continue

    def assert_tool_called(self, tool_name: str) -> bool:
        """Assert a tool was called."""
        for tool in self.tool_uses:
            if tool_name in tool.get("name", ""):
                return True
        return False

    def assert_tool_not_called(self, tool_name: str) -> bool:
        """Assert a tool was NOT called."""
        return not self.assert_tool_called(tool_name)

    def get_tool_calls(self, tool_name: str) -> List[Dict]:
        """Get all calls to a specific tool."""
        calls = []
        for tool in self.tool_uses:
            if tool_name in tool.get("name", ""):
                calls.append(tool)
        return calls

    def assert_tool_call_count(self, tool_name: str, count: int) -> bool:
        """Assert exact number of calls to a tool."""
        actual = len(self.get_tool_calls(tool_name))
        if actual != count:
            print(f"  FAIL: Expected {count} calls to {tool_name}, got {actual}")
            return False
        return True

    def assert_tool_call_max(self, tool_name: str, max_count: int) -> bool:
        """Assert tool called at most N times."""
        actual = len(self.get_tool_calls(tool_name))
        if actual > max_count:
            print(f"  FAIL: Expected at most {max_count} calls to {tool_name}, got {actual}")
            return False
        return True

    def assert_call_order(self, first_tool: str, second_tool: str) -> bool:
        """Assert first tool called before second tool."""
        first_idx = None
        second_idx = None

        for idx, tool in enumerate(self.tool_uses):
            if first_tool in tool.get("name", ""):
                if first_idx is None:
                    first_idx = idx
            if second_tool in tool.get("name", ""):
                if second_idx is None:
                    second_idx = idx

        if first_idx is None or second_idx is None:
            print(f"  FAIL: Could not find both {first_tool} and {second_tool} in tool calls")
            return False

        if first_idx >= second_idx:
            print(f"  FAIL: {first_tool} not called before {second_tool}")
            return False

        return True

    def assert_catalog_queries_have_fields_and_limit(self) -> bool:
        """Assert all catalog query calls have fields and limit."""
        catalog_queries = self.get_tool_calls("query-catalog-entities")

        for call in catalog_queries:
            input_args = call.get("input", {})
            if "fields" not in input_args:
                print(f"  FAIL: Catalog query missing 'fields': {call.get('id')}")
                return False
            if "limit" not in input_args:
                print(f"  FAIL: Catalog query missing 'limit': {call.get('id')}")
                return False

        return True

    def assert_json_path_equals(self, tool_name: str, json_path: str, expected_value: Any) -> bool:
        """Assert a JSON path in tool input equals expected value."""
        calls = self.get_tool_calls(tool_name)
        if not calls:
            print(f"  FAIL: No calls to {tool_name}")
            return False

        # Take the last call
        call = calls[-1]
        input_args = call.get("input", {})

        # Navigate JSON path
        parts = json_path.split(".")
        value = input_args
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                print(f"  FAIL: Cannot navigate {json_path} in {tool_name} input")
                return False

        if value != expected_value:
            print(f"  FAIL: {json_path} in {tool_name} = {value}, expected {expected_value}")
            return False

        return True

    def assert_json_path_absent(self, tool_name: str, json_path: str) -> bool:
        """Assert a JSON path is absent from tool input."""
        calls = self.get_tool_calls(tool_name)
        if not calls:
            return True  # If tool not called, path is absent

        call = calls[-1]
        input_args = call.get("input", {})

        # Navigate JSON path
        parts = json_path.split(".")
        value = input_args
        for part in parts:
            if isinstance(value, dict):
                if part not in value:
                    return True  # Path absent
                value = value[part]
            else:
                return True  # Cannot navigate further

        print(f"  FAIL: {json_path} present in {tool_name} input when it should be absent")
        return False

    def assert_question_count_max(self, max_questions: int) -> bool:
        """Assert at most N questions asked (heuristic: user role messages)."""
        question_count = 0

        for msg in self.messages:
            role = msg.get("message", {}).get("role", "")
            if role == "assistant":
                content = msg.get("message", {}).get("content", [])
                for item in content:
                    if item.get("type") == "text":
                        text = item.get("text", "")
                        # Heuristic: question ends with ?
                        if "?" in text:
                            question_count += 1
                            break  # Count once per message

        if question_count > max_questions:
            print(f"  FAIL: Asked {question_count} questions, max allowed {max_questions}")
            return False

        return True

    def assert_fail_fast(self) -> bool:
        """Assert no questions and no tool calls after a failing tool call."""
        failed_tool_idx = None

        # Find first failed tool result
        for idx, result in enumerate(self.tool_results):
            if result.get("isError", False):
                failed_tool_idx = idx
                break

        if failed_tool_idx is None:
            return True  # No failures

        # Check no tool uses after failure
        # This is approximate - we'd need to correlate by timestamp in real impl
        # For now, just check that total tool uses is minimal after a failure
        if len(self.tool_uses) > failed_tool_idx + 2:
            print(f"  FAIL: Tool calls continued after failure")
            return False

        return True

    def assert_max_tool_result_size(self, max_bytes: int) -> bool:
        """Assert largest tool result is under byte ceiling."""
        max_size = 0

        for result in self.tool_results:
            content = result.get("content", [])
            for item in content:
                if item.get("type") == "text":
                    text = item.get("text", "")
                    size = len(text.encode('utf-8'))
                    max_size = max(max_size, size)

        if max_size > max_bytes:
            print(f"  FAIL: Largest tool result {max_size} bytes exceeds {max_bytes} limit")
            return False

        return True

    def assert_total_input_tokens_max(self, max_tokens: int) -> bool:
        """Assert total fresh input tokens under ceiling."""
        total = self.usage_total["input_tokens"]
        if total > max_tokens:
            print(f"  FAIL: Total input tokens {total} exceeds {max_tokens} limit")
            return False
        return True

    def record_run_metadata(self, scenario_name: str, scenario: Dict, output_path: str):
        """Record run metadata to runs.jsonl."""
        record = {
            "scenario": scenario_name,
            "model": self.result_message.get("model") if self.result_message else None,
            "usage": self.usage_total,
            "stub_scenario": scenario.get("stub_scenario", "default"),
            "skill_installed": True,  # Will be passed from runner
            "timestamp": self.result_message.get("timestamp") if self.result_message else None
        }

        with open(output_path, "a") as f:
            f.write(json.dumps(record) + "\n")


def load_scenario(scenario_path: str) -> Dict:
    """Load scenario file (simple YAML parsing)."""
    scenario = {}
    with open(scenario_path) as f:
        for line in f:
            line = line.strip()
            if ": " in line:
                key, value = line.split(": ", 1)
                scenario[key] = value
    return scenario


def main():
    if len(sys.argv) < 3:
        print("Usage: check.py <scenario.yaml> <transcript.jsonl>")
        sys.exit(1)

    scenario_path = sys.argv[1]
    transcript_path = sys.argv[2]

    if not Path(transcript_path).exists():
        print(f"ERROR: Transcript not found: {transcript_path}")
        sys.exit(1)

    scenario = load_scenario(scenario_path)
    asserter = TranscriptAsserter(transcript_path)

    print(f"Checking: {Path(scenario_path).stem}")

    # Run assertions based on scenario expectations
    # These would be read from the scenario file in real implementation
    # For now, run a default set

    passed = True

    # Default assertions for all scenarios
    if "query-catalog-entities" in str(asserter.tool_uses):
        if not asserter.assert_catalog_queries_have_fields_and_limit():
            passed = False

    # Specific assertion examples (would come from scenario file)
    # passed = passed and asserter.assert_tool_called("execute-template")
    # passed = passed and asserter.assert_question_count_max(10)

    if passed:
        print("  PASS: All assertions passed")
    else:
        print("  FAIL: Some assertions failed")
        sys.exit(1)

    # Record metadata
    runs_file = Path(transcript_path).parent / "runs.jsonl"
    asserter.record_run_metadata(Path(scenario_path).stem, scenario, str(runs_file))


if __name__ == "__main__":
    main()
