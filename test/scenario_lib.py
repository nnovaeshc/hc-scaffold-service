#!/usr/bin/env python3
"""
Shared, dependency-free scenario YAML loader and filter, matching the flat
schema documented in docs/align-tests-skill-creator.md §2.1: top-level scalar
keys plus one `expectations:` list of single-key scalar mappings.
"""
import glob
import os
import sys
from typing import Any, Dict, List, Optional


def _parse_scalar(raw: str) -> Any:
    s = raw.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        s = s[1:-1]
    if s == "true":
        return True
    if s == "false":
        return False
    try:
        return int(s)
    except ValueError:
        pass
    return s


def load_scenario(path: str) -> Dict[str, Any]:
    """Parse a scenario YAML file. Assumes the flat schema documented above.

    Optional `replies:` is a list of single-line follow-up user messages used
    by the multi-turn harness after the initial prompt (confirmations, etc.).
    """
    data: Dict[str, Any] = {}
    expectations: List[Dict[str, Any]] = []
    replies: List[str] = []
    in_expectations = False
    in_replies = False

    with open(path) as f:
        for raw_line in f:
            line = raw_line.rstrip("\n")
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            if not line.startswith(" ") and stripped.startswith("expectations:"):
                in_expectations = True
                in_replies = False
                continue

            if not line.startswith(" ") and stripped.startswith("replies:"):
                in_replies = True
                in_expectations = False
                continue

            if in_expectations:
                if line.startswith("  - "):
                    item = line[4:].strip()
                    key, _, val = item.partition(":")
                    expectations.append({key.strip(): _parse_scalar(val)})
                    continue
                if line.startswith(" "):
                    continue
                in_expectations = False

            if in_replies:
                if line.startswith("  - "):
                    replies.append(str(_parse_scalar(line[4:].strip())))
                    continue
                if line.startswith(" "):
                    continue
                in_replies = False

            if line.startswith(" "):
                continue

            key, sep, val = stripped.partition(":")
            if not sep:
                continue
            data[key.strip()] = _parse_scalar(val)

    data["expectations"] = expectations
    data["replies"] = replies
    data.setdefault("compare", False)
    return data


def load_all_scenarios(scenarios_dir: str) -> List[Dict[str, Any]]:
    scenarios = []
    for path in sorted(glob.glob(os.path.join(scenarios_dir, "*.yaml"))):
        scenario = load_scenario(path)
        scenario["_path"] = path
        scenarios.append(scenario)
    return sorted(scenarios, key=lambda s: s["name"])


def _split_filter(value: Optional[str]) -> Optional[set]:
    if not value:
        return None
    return {v.strip() for v in value.split(",") if v.strip()}


def select_scenarios(
    scenarios_dir: str,
    compare_only: bool = True,
    tiers: Optional[str] = None,
    types: Optional[str] = None,
    features: Optional[str] = None,
    tests: Optional[str] = None,
) -> List[Dict[str, Any]]:
    tier_set = _split_filter(tiers)
    type_set = _split_filter(types)
    feature_set = _split_filter(features)
    test_set = _split_filter(tests)

    selected = []
    for scenario in load_all_scenarios(scenarios_dir):
        if compare_only and not scenario.get("compare"):
            continue
        if tier_set is not None and str(scenario.get("tier")) not in tier_set:
            continue
        if type_set is not None and scenario.get("type") not in type_set:
            continue
        if feature_set is not None and scenario.get("feature") not in feature_set:
            continue
        if test_set is not None and scenario.get("name") not in test_set:
            continue
        selected.append(scenario)
    return selected


def fair_prompt(scenario: Dict[str, Any]) -> str:
    """Prompt to use for the without-skill arm: compare_prompt if set, else
    the prompt with a leading /hc-scaffold-service (and following space) stripped."""
    if scenario.get("compare_prompt"):
        return scenario["compare_prompt"]
    prompt = scenario.get("prompt", "")
    prefix = "/hc-scaffold-service"
    if prompt.startswith(prefix + " "):
        return prompt[len(prefix) + 1:]
    if prompt == prefix:
        return ""
    return prompt


def main():
    import argparse
    import json

    parser = argparse.ArgumentParser(description="List/select test scenarios")
    parser.add_argument("--dir", default="test/scenarios")
    parser.add_argument("--all", action="store_true", help="Include compare:false scenarios")
    parser.add_argument("--tier")
    parser.add_argument("--type")
    parser.add_argument("--feature")
    parser.add_argument("--tests")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    selected = select_scenarios(
        args.dir,
        compare_only=not args.all,
        tiers=args.tier,
        types=args.type,
        features=args.feature,
        tests=args.tests,
    )

    if any([args.tier, args.type, args.feature, args.tests]) and not selected:
        print(
            f"ERROR: no scenarios match filters tier={args.tier} type={args.type} "
            f"feature={args.feature} tests={args.tests}",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.json:
        print(json.dumps(selected))
    else:
        for s in selected:
            print(f"{s['name']} {s.get('tier')} {s.get('type')} {s.get('feature')}")


if __name__ == "__main__":
    main()
