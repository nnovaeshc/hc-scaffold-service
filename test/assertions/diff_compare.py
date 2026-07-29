#!/usr/bin/env python3
"""
Diff two benchmark.json files. Fails the build on schema/filter/model mismatch
or pass/fail flips; reports metric drift advisory-only. See
docs/align-tests-skill-creator.md §2.7 and skill-vs-baseline.md §5.3.
"""
import argparse
import json
import sys
from pathlib import Path


def load(path: str) -> dict:
    return json.loads(Path(path).read_text())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("a")
    parser.add_argument("b")
    args = parser.parse_args()

    a = load(args.a)
    b = load(args.b)

    hard_fail = False

    if a.get("schema_version") != b.get("schema_version"):
        print(f"SCHEMA MISMATCH: {args.a} v{a.get('schema_version')} vs {args.b} v{b.get('schema_version')}")
        hard_fail = True

    if sorted(a.get("scenarios", [])) != sorted(b.get("scenarios", [])):
        print("SCENARIO SET MISMATCH:")
        print(f"  {args.a}: {sorted(a.get('scenarios', []))}")
        print(f"  {args.b}: {sorted(b.get('scenarios', []))}")
        hard_fail = True

    if a.get("filters") != b.get("filters"):
        print(f"FILTER MISMATCH: {a.get('filters')} vs {b.get('filters')}")
        hard_fail = True

    if a.get("model") != b.get("model") or a.get("effort") != b.get("effort"):
        print(f"MODEL/EFFORT MISMATCH: ({a.get('model')}, {a.get('effort')}) vs ({b.get('model')}, {b.get('effort')})")
        hard_fail = True

    a_rows = {row["name"]: row for row in a.get("per_scenario", [])}
    b_rows = {row["name"]: row for row in b.get("per_scenario", [])}

    for name in sorted(set(a_rows) & set(b_rows)):
        ra, rb = a_rows[name], b_rows[name]
        for arm in ("with_skill_pass", "without_skill_pass"):
            if ra.get(arm) != rb.get(arm):
                print(f"PASS/FAIL FLIP [{name}.{arm}]: {ra.get(arm)} -> {rb.get(arm)}")
                hard_fail = True

    print("\n--- advisory metric drift ---")
    for metric in ("pass_rate", "time_seconds", "tokens"):
        a_delta = a.get("run_summary", {}).get("delta", {}).get(metric)
        b_delta = b.get("run_summary", {}).get("delta", {}).get(metric)
        print(f"{metric}: delta {a_delta} -> {b_delta}")

    if hard_fail:
        print("\nFAIL: benchmark comparison found hard mismatches")
        sys.exit(1)

    print("\nPASS: no schema/filter/model/pass-fail mismatches (metric drift is advisory)")


if __name__ == "__main__":
    main()
