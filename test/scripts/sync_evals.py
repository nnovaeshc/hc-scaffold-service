#!/usr/bin/env python3
"""
Regenerate skills/hc-scaffold-service/evals/{evals.json,scenario-map.json} from
test/scenarios/*.yaml, per docs/align-tests-skill-creator.md §2.2. evals.json
uses only the official skill-creator fields (id, prompt, expected_output,
assertions, files); scenario-map.json is the sidecar the harness uses to join
a numeric id back to a scenario name.
"""
import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "test"))
from scenario_lib import load_all_scenarios  # noqa: E402

EVALS_DIR = REPO_ROOT / "skills" / "hc-scaffold-service" / "evals"
EVALS_PATH = EVALS_DIR / "evals.json"
SCENARIO_MAP_PATH = EVALS_DIR / "scenario-map.json"

# Natural-language mirror for each mechanical expectation key, used to build
# evals.json assertions. {value} is substituted with the expectation's value.
ASSERTION_TEMPLATES = {
    "tool_called": "the {value} tool is called",
    "tool_not_called": "the {value} tool is never called",
    "tool_call_count_execute_template": "execute-template is called exactly {value} time(s)",
    "question_count": "exactly {value} questions are asked",
    "question_count_max": "at most {value} questions are asked",
    "catalog_queries_have_fields_and_limit": "every catalog query carries both fields and limit",
    "json_path_absent": "{value} is absent from the submitted values",
    "submitted_value_matches": "the submitted value satisfies its declared constraint ({value})",
    "constraint_violation_reported": "the assistant reports the violated schema constraint instead of submitting",
    "filter_kind": "a catalog query filters on kind: {value}",
    "config_failure_message": "a configuration failure is reported",
    "auth_failure_message": "an authorization failure is reported",
    "empty_catalog_message": "an empty-catalog failure is reported",
    "error_reported": "an error is reported rather than a fabricated result",
    "refusal_message": "the assistant refuses to submit",
    "redirect_to_backstage_ui": "the assistant redirects the user to the Backstage UI",
    "task_failure_reported": "the task failure is reported",
    "confirmation_required": "explicit confirmation is required before submission",
    "review_shown": "a review of the values is shown before submission",
    "completion": "the flow completes",
}


def expectation_to_assertion(expectation: dict) -> str:
    (key, value), = expectation.items()
    template = ASSERTION_TEMPLATES.get(key)
    if template is None:
        return f"{key}: {value}"
    return template.format(value=value)


def build_evals(scenarios_dir: str):
    scenarios = load_all_scenarios(scenarios_dir)
    evals = []
    scenario_map = {}
    for idx, scenario in enumerate(scenarios, start=1):
        evals.append({
            "id": idx,
            "prompt": scenario.get("prompt", ""),
            "expected_output": scenario.get("expected_output", ""),
            "assertions": [expectation_to_assertion(e) for e in scenario.get("expectations", [])],
            "files": [],
        })
        scenario_map[str(idx)] = scenario["name"]
    evals_doc = {"skill_name": "hc-scaffold-service", "evals": evals}
    return evals_doc, scenario_map


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Fail if sync would change files")
    parser.add_argument("--dir", default=str(REPO_ROOT / "test" / "scenarios"))
    args = parser.parse_args()

    evals_doc, scenario_map = build_evals(args.dir)
    evals_text = json.dumps(evals_doc, indent=2) + "\n"
    scenario_map_text = json.dumps(scenario_map, indent=2) + "\n"

    if args.check:
        current_evals = EVALS_PATH.read_text() if EVALS_PATH.exists() else ""
        current_map = SCENARIO_MAP_PATH.read_text() if SCENARIO_MAP_PATH.exists() else ""
        if current_evals != evals_text or current_map != scenario_map_text:
            print("FAIL: evals.json / scenario-map.json are out of sync with test/scenarios/*.yaml")
            print("Run: task test:evals:sync")
            sys.exit(1)
        print("PASS: evals.json and scenario-map.json are in sync")
        return

    EVALS_DIR.mkdir(parents=True, exist_ok=True)
    EVALS_PATH.write_text(evals_text)
    SCENARIO_MAP_PATH.write_text(scenario_map_text)
    print(f"Wrote {EVALS_PATH}")
    print(f"Wrote {SCENARIO_MAP_PATH}")


if __name__ == "__main__":
    main()
