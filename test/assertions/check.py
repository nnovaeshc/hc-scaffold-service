#!/usr/bin/env python3
"""
Transcript oracle for hc-scaffold-service test scenarios.
Reads stream-json transcripts and asserts declaratively from scenario files.
"""
import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scenario_lib import load_scenario  # noqa: E402


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
        """Load and parse stream-json transcript. Each line is a top-level
        event with `type` in {"assistant", "user", "system", "result"}; the
        first two carry a nested `message.content` block list."""
        with open(self.transcript_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue

                msg_type = msg.get("type")

                if msg_type in ("assistant", "user"):
                    self.messages.append(msg)
                    content = msg.get("message", {}).get("content", [])

                    if msg_type == "assistant":
                        for item in content:
                            if item.get("type") == "tool_use":
                                self.tool_uses.append(item)
                        usage = msg.get("message", {}).get("usage", {})
                        for key in self.usage_total:
                            self.usage_total[key] += usage.get(key, 0)
                    else:
                        for item in content:
                            if item.get("type") == "tool_result":
                                self.tool_results.append(item)

                elif msg_type == "result":
                    self.result_message = msg

    def assistant_text(self) -> str:
        """Concatenate all assistant text blocks, for keyword heuristics."""
        chunks = []
        for msg in self.messages:
            if msg.get("type") != "assistant":
                continue
            for item in msg.get("message", {}).get("content", []):
                if item.get("type") == "text":
                    chunks.append(item.get("text", ""))
        return "\n".join(chunks)

    def get_tool_calls(self, tool_name: str) -> List[Dict]:
        return [t for t in self.tool_uses if tool_name in t.get("name", "")]

    # -- mechanical assertions --------------------------------------------

    def assert_tool_called(self, tool_name: str) -> (bool, str):
        found = bool(self.get_tool_calls(tool_name))
        return found, f"tool_use name~={tool_name} found={found}"

    def assert_tool_not_called(self, tool_name: str) -> (bool, str):
        found = bool(self.get_tool_calls(tool_name))
        return (not found), f"tool_use name~={tool_name} found={found}"

    def assert_tool_call_count(self, tool_name: str, count: int) -> (bool, str):
        actual = len(self.get_tool_calls(tool_name))
        return actual == count, f"{tool_name} called {actual} times, expected {count}"

    def assert_tool_call_max(self, tool_name: str, max_count: int) -> (bool, str):
        actual = len(self.get_tool_calls(tool_name))
        return actual <= max_count, f"{tool_name} called {actual} times, max {max_count}"

    def assert_catalog_queries_have_fields_and_limit(self) -> (bool, str):
        calls = self.get_tool_calls("query-catalog-entities")
        for call in calls:
            input_args = call.get("input", {})
            if "fields" not in input_args or "limit" not in input_args:
                return False, f"catalog query missing fields/limit: {call.get('id')}"
        return True, f"{len(calls)} catalog queries all carry fields+limit"

    def assert_json_path_absent(self, tool_name: str, json_path: str) -> (bool, str):
        calls = self.get_tool_calls(tool_name)
        if not calls:
            return True, f"{tool_name} not called; {json_path} trivially absent"
        call = calls[-1]
        value = call.get("input", {})
        parts = json_path.split(".")
        for part in parts:
            if isinstance(value, dict):
                if part not in value:
                    return True, f"{json_path} absent from {tool_name} input"
                value = value[part]
            else:
                return True, f"{json_path} not navigable in {tool_name} input"
        return False, f"{json_path} present in {tool_name} input when it should be absent"

    def assert_submitted_value_matches(self, spec: str) -> (bool, str):
        """spec is "<dot.path>=<regex>", e.g. "values.componentId=^[a-z0-9-]+$".
        The regex may not contain ':' - scenario_lib partitions the expectation
        line on the first colon."""
        json_path, _, pattern = spec.partition("=")
        calls = self.get_tool_calls("execute-template")
        if not calls:
            return False, f"execute-template not called; cannot check {json_path}"
        value = calls[-1].get("input", {})
        for part in json_path.split("."):
            if not isinstance(value, dict) or part not in value:
                return False, f"{json_path} absent from execute-template input"
            value = value[part]
        matched = re.fullmatch(pattern, str(value)) is not None
        return matched, f"{json_path}={value!r} vs /{pattern}/ matched={matched}"

    def assert_question_count_max(self, max_questions: int) -> (bool, str):
        count = 0
        for msg in self.messages:
            if msg.get("type") != "assistant":
                continue
            for item in msg.get("message", {}).get("content", []):
                if item.get("type") == "text" and "?" in item.get("text", ""):
                    count += 1
                    break
        return count <= max_questions, f"asked {count} questions, max {max_questions}"

    def assert_question_count(self, expected: int) -> (bool, str):
        count = 0
        for msg in self.messages:
            if msg.get("type") != "assistant":
                continue
            for item in msg.get("message", {}).get("content", []):
                if item.get("type") == "text" and "?" in item.get("text", ""):
                    count += 1
                    break
        return count == expected, f"asked {count} questions, expected {expected}"

    def assert_filter_kind(self, kind: str) -> (bool, str):
        calls = self.get_tool_calls("query-catalog-entities")
        for call in calls:
            filt = call.get("input", {}).get("filter", {})
            if isinstance(filt, dict) and filt.get("kind") == kind:
                return True, f"found catalog query with filter.kind={kind}"
        return False, f"no catalog query filtered on kind={kind}"

    # -- keyword-heuristic assertions (no mechanical trace available) -----

    def _assistant_text_matches(self, patterns: List[str]) -> (bool, str):
        text = self.assistant_text().lower()
        for pattern in patterns:
            if re.search(pattern, text):
                return True, f"assistant text matched /{pattern}/"
        return False, f"assistant text matched none of {patterns}"

    def assert_error_reported(self, expected: bool) -> (bool, str):
        matched, evidence = self._assistant_text_matches(
            [r"not found", r"doesn't exist", r"no (matching )?template", r"couldn't find", r"\berror\b"]
        )
        return matched == expected, evidence

    def assert_config_failure_message(self, expected: bool) -> (bool, str):
        matched, evidence = self._assistant_text_matches(
            [r"configur", r"capabilit", r"not available", r"cannot proceed"]
        )
        return matched == expected, evidence

    def assert_auth_failure_message(self, expected: bool) -> (bool, str):
        matched, evidence = self._assistant_text_matches(
            [r"auth", r"denied", r"permission", r"unauthorized"]
        )
        return matched == expected, evidence

    def assert_empty_catalog_message(self, expected: bool) -> (bool, str):
        matched, evidence = self._assistant_text_matches(
            [r"no templates?", r"empty catalog", r"catalog returned"]
        )
        return matched == expected, evidence

    def assert_refusal_message(self, expected: bool) -> (bool, str):
        matched, evidence = self._assistant_text_matches(
            [r"cannot submit", r"won't", r"refuse", r"secret"]
        )
        return matched == expected, evidence

    def assert_constraint_violation_reported(self, expected: bool) -> (bool, str):
        matched, evidence = self._assistant_text_matches(
            [r"must match", r"invalid", r"constraint", r"pattern", r"too long", r"not allowed"]
        )
        return matched == expected, evidence

    def assert_redirect_to_backstage_ui(self, expected: bool) -> (bool, str):
        matched, evidence = self._assistant_text_matches(
            [r"backstage.{0,20}(ui|website|browser|portal)"]
        )
        return matched == expected, evidence

    def assert_task_failure_reported(self, expected: bool) -> (bool, str):
        matched, evidence = self._assistant_text_matches([r"fail"])
        return matched == expected, evidence

    def assert_confirmation_required(self, expected: bool) -> (bool, str):
        matched, evidence = self._assistant_text_matches([r"confirm", r"proceed\?", r"submit\?"])
        return matched == expected, evidence

    def assert_review_shown(self, expected: bool) -> (bool, str):
        matched, evidence = self._assistant_text_matches([r"review"])
        return matched == expected, evidence

    def assert_completion(self, expected: bool) -> (bool, str):
        ok = self.result_message is not None and not self.result_message.get("is_error", False)
        return ok == expected, f"result_message present={self.result_message is not None}"


def load_all_expectations(scenario: Dict[str, Any]) -> List[Dict[str, Any]]:
    return scenario.get("expectations", [])


def run_assertions(asserter: TranscriptAsserter, expectations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Run each declared expectation, returning grading.json-shaped assertion_results."""
    results = []
    for expectation in expectations:
        for key, value in expectation.items():
            method_name = f"assert_{key}"
            method = getattr(asserter, method_name, None)
            if method is None:
                results.append({
                    "text": f"{key} = {value}",
                    "passed": False,
                    "evidence": f"no assertion implemented for '{key}'",
                })
                continue
            try:
                if key in ("tool_called", "tool_not_called", "filter_kind"):
                    passed, evidence = method(value)
                elif key == "tool_call_count_execute_template":
                    passed, evidence = method("execute-template", value)
                elif key == "catalog_queries_have_fields_and_limit":
                    passed, evidence = method() if value else (True, "assertion opted out")
                elif key == "json_path_absent":
                    tool_name, _, path = value.partition(".") if isinstance(value, str) else ("", "", "")
                    # json_path_absent value is "values.field"; tool is always execute-template here
                    passed, evidence = method("execute-template", value)
                else:
                    passed, evidence = method(value)
            except TypeError:
                passed, evidence = method()
            results.append({"text": f"{key}: {value}", "passed": passed, "evidence": evidence})
    return results


def write_grading(results: List[Dict[str, Any]], outdir: Path):
    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    grading = {
        "assertion_results": results,
        "summary": {
            "passed": passed,
            "failed": total - passed,
            "total": total,
            "pass_rate": (passed / total) if total else 1.0,
        },
    }
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "grading.json").write_text(json.dumps(grading, indent=2) + "\n")
    return grading


def actual_model(asserter: TranscriptAsserter) -> Optional[str]:
    """Model actually used, read from the result message's modelUsage keys
    rather than what was requested - a request can be silently substituted."""
    if not asserter.result_message:
        return None
    model_usage = asserter.result_message.get("modelUsage") or {}
    if model_usage:
        return next(iter(model_usage))
    return asserter.result_message.get("model")


def write_timing(asserter: TranscriptAsserter, outdir: Path):
    usage = asserter.usage_total
    total_tokens = sum(usage.values())
    duration_ms = 0
    if asserter.result_message:
        duration_ms = asserter.result_message.get("duration_ms", 0)
    timing = {
        "total_tokens": total_tokens,
        "duration_ms": duration_ms,
        "input_tokens": usage["input_tokens"],
        "output_tokens": usage["output_tokens"],
        "cache_creation_input_tokens": usage["cache_creation_input_tokens"],
        "cache_read_input_tokens": usage["cache_read_input_tokens"],
    }
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "timing.json").write_text(json.dumps(timing, indent=2) + "\n")
    return timing


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario_path")
    parser.add_argument("transcript_path")
    parser.add_argument("--outdir", help="Write grading.json/timing.json here (agentskills workspace arm dir)")
    args = parser.parse_args()

    if not Path(args.transcript_path).exists():
        print(f"ERROR: Transcript not found: {args.transcript_path}")
        sys.exit(1)

    scenario = load_scenario(args.scenario_path)
    asserter = TranscriptAsserter(args.transcript_path)

    print(f"Checking: {Path(args.scenario_path).stem}")

    expectations = load_all_expectations(scenario)
    results = run_assertions(asserter, expectations)

    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"  {status}: {r['text']} ({r['evidence']})")

    if args.outdir:
        outdir = Path(args.outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        (outdir / "outputs").mkdir(exist_ok=True)
        write_grading(results, outdir)
        write_timing(asserter, outdir)

    if results and not all(r["passed"] for r in results):
        print("  FAIL: Some assertions failed")
        sys.exit(1)
    print("  PASS: All assertions passed")


if __name__ == "__main__":
    main()
