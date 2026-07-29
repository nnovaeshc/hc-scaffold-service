#!/usr/bin/env python3
"""
Paired A/B compare runner. Selects scenarios via scenario_lib filters, runs
each with the skill installed and without it against the same stub scenario,
writes the agentskills-compatible workspace tree, and rolls up benchmark.json.
See docs/align-tests-skill-creator.md sections 2.4-2.7 for the exact shapes.
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "test"))
from scenario_lib import select_scenarios, fair_prompt  # noqa: E402
sys.path.insert(0, str(REPO_ROOT / "test" / "assertions"))
from check import TranscriptAsserter, load_all_expectations, run_assertions, write_grading, write_timing  # noqa: E402


def next_iteration(workspace_dir: Path) -> int:
    workspace_dir.mkdir(parents=True, exist_ok=True)
    existing = []
    for p in workspace_dir.glob("iteration-*"):
        try:
            existing.append(int(p.name.split("-", 1)[1]))
        except ValueError:
            continue
    return (max(existing) + 1) if existing else 1


def export_aws_credentials(env: dict):
    try:
        out = subprocess.run(
            ["aws", "configure", "export-credentials", "--profile", "hc-devopstooling-prod", "--format", "env"],
            capture_output=True, text=True, check=True,
        ).stdout
        for line in out.splitlines():
            if line.startswith("export "):
                line = line[len("export "):]
            if "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip().strip('"')
    except Exception as e:
        print(f"WARNING: failed to export AWS credentials: {e}", file=sys.stderr)


def run_arm(scenario: dict, with_skill: bool, model: str, effort: str, env: dict, arm_dir: Path) -> dict:
    prompt = scenario["prompt"] if with_skill else fair_prompt(scenario)
    stub_scenario = scenario.get("stub_scenario", "default")

    claude_cmd = ["claude", "-p", "--verbose", "--output-format", "stream-json", "--permission-mode", "bypassPermissions"]
    if effort:
        claude_cmd += ["--effort", effort]
    claude_cmd.append(prompt)

    run_env = dict(env)
    run_env["STUB_SCENARIO"] = stub_scenario
    run_env["SKILLS_TEMPLATE"] = (
        "/work/test/skills.test.yaml" if with_skill else "/work/test/skills.none.test.yaml"
    )
    run_env["MODEL"] = model

    arm_dir.mkdir(parents=True, exist_ok=True)
    (arm_dir / "outputs").mkdir(exist_ok=True)
    transcript_path = arm_dir / "transcript.jsonl"

    quoted_cmd = " ".join(
        f"'{part}'" if " " in part or part == prompt else part for part in claude_cmd
    )
    result = subprocess.run(
        ["docker-compose", "-f", str(REPO_ROOT / "test" / "docker-compose.yaml"), "run", "--rm", "ai-tdd",
         "bash", "-c", quoted_cmd],
        cwd=REPO_ROOT, env=run_env, capture_output=True, text=True,
    )
    transcript_path.write_text(result.stdout + result.stderr)

    asserter = TranscriptAsserter(str(transcript_path))
    expectations = load_all_expectations(scenario)
    results = run_assertions(asserter, expectations)
    grading = write_grading(results, arm_dir)
    timing = write_timing(asserter, arm_dir)
    return {"grading": grading, "timing": timing, "pass": grading["summary"]["failed"] == 0}


def mean(values):
    values = [v for v in values if v is not None]
    return (sum(values) / len(values)) if values else 0.0


def build_benchmark(scenarios, per_scenario, filters, skill_sha, model, effort):
    with_pass = [r["with_skill"]["pass"] for r in per_scenario]
    without_pass = [r["without_skill"]["pass"] for r in per_scenario]
    with_time = [r["with_skill"]["timing"]["duration_ms"] / 1000.0 for r in per_scenario]
    without_time = [r["without_skill"]["timing"]["duration_ms"] / 1000.0 for r in per_scenario]
    with_tokens = [r["with_skill"]["timing"]["total_tokens"] for r in per_scenario]
    without_tokens = [r["without_skill"]["timing"]["total_tokens"] for r in per_scenario]

    with_summary = {
        "pass_rate": {"mean": mean([1.0 if p else 0.0 for p in with_pass])},
        "time_seconds": {"mean": mean(with_time)},
        "tokens": {"mean": mean(with_tokens)},
    }
    without_summary = {
        "pass_rate": {"mean": mean([1.0 if p else 0.0 for p in without_pass])},
        "time_seconds": {"mean": mean(without_time)},
        "tokens": {"mean": mean(without_tokens)},
    }
    delta = {
        "pass_rate": with_summary["pass_rate"]["mean"] - without_summary["pass_rate"]["mean"],
        "time_seconds": with_summary["time_seconds"]["mean"] - without_summary["time_seconds"]["mean"],
        "tokens": with_summary["tokens"]["mean"] - without_summary["tokens"]["mean"],
    }

    return {
        "schema_version": 1,
        "skill_sha": skill_sha,
        "model": model,
        "effort": effort or None,
        "filters": filters,
        "scenarios": sorted(s["name"] for s in scenarios),
        "run_summary": {
            "with_skill": with_summary,
            "without_skill": without_summary,
            "delta": delta,
        },
        "per_scenario": [
            {
                "name": r["name"],
                "with_skill_pass": r["with_skill"]["pass"],
                "without_skill_pass": r["without_skill"]["pass"],
                "pass_delta": int(r["with_skill"]["pass"]) - int(r["without_skill"]["pass"]),
                "timing": {
                    "with_skill": r["with_skill"]["timing"],
                    "without_skill": r["without_skill"]["timing"],
                },
                "grading_summaries": {
                    "with_skill": r["with_skill"]["grading"]["summary"],
                    "without_skill": r["without_skill"]["grading"]["summary"],
                },
            }
            for r in per_scenario
        ],
    }


def validate_benchmark_shape(benchmark: dict):
    """Minimal stdlib check against fixtures/compare-report.schema.json's required
    top-level and run_summary/per_scenario keys. Fails loudly on shape drift."""
    required_top = {"schema_version", "skill_sha", "model", "filters", "scenarios", "run_summary", "per_scenario"}
    missing = required_top - benchmark.keys()
    if missing:
        raise ValueError(f"benchmark.json missing top-level keys: {missing}")

    for arm in ("with_skill", "without_skill"):
        arm_summary = benchmark["run_summary"].get(arm, {})
        for metric in ("pass_rate", "time_seconds", "tokens"):
            if "mean" not in arm_summary.get(metric, {}):
                raise ValueError(f"benchmark.json run_summary.{arm}.{metric} missing 'mean'")

    for row in benchmark["per_scenario"]:
        required_row = {"name", "with_skill_pass", "without_skill_pass", "pass_delta"}
        row_missing = required_row - row.keys()
        if row_missing:
            raise ValueError(f"benchmark.json per_scenario row missing keys: {row_missing}")


def write_compare_md(benchmark: dict, path: Path):
    lines = [
        f"# Compare iteration — skill {benchmark['skill_sha'][:12]} — model {benchmark['model']}",
        "",
        "| scenario | with_skill_pass | without_skill_pass | pass_delta |",
        "|---|---|---|---|",
    ]
    for row in benchmark["per_scenario"]:
        lines.append(f"| {row['name']} | {row['with_skill_pass']} | {row['without_skill_pass']} | {row['pass_delta']} |")
    lines.append("")
    rs = benchmark["run_summary"]
    lines.append(
        f"mean pass_rate: with={rs['with_skill']['pass_rate']['mean']:.2f} "
        f"without={rs['without_skill']['pass_rate']['mean']:.2f} delta={rs['delta']['pass_rate']:.2f}"
    )
    path.write_text("\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tier")
    parser.add_argument("--type")
    parser.add_argument("--feature")
    parser.add_argument("--tests")
    parser.add_argument("--model", default=os.environ.get("MODEL", "claude-sonnet-4-5"))
    parser.add_argument("--effort", default=os.environ.get("EFFORT", ""))
    args = parser.parse_args()

    scenarios = select_scenarios(
        str(REPO_ROOT / "test" / "scenarios"),
        compare_only=True,
        tiers=args.tier,
        types=args.type,
        features=args.feature,
        tests=args.tests,
    )
    if not scenarios:
        print(
            f"ERROR: no compare scenarios match tier={args.tier} type={args.type} "
            f"feature={args.feature} tests={args.tests}",
            file=sys.stderr,
        )
        sys.exit(1)

    workspace_dir = REPO_ROOT / "test" / "workspace"
    iteration = next_iteration(workspace_dir)
    iteration_dir = workspace_dir / f"iteration-{iteration}"
    iteration_dir.mkdir(parents=True, exist_ok=True)

    env = dict(os.environ)
    export_aws_credentials(env)

    skill_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()

    print(f"==> Compare iteration {iteration}: {len(scenarios)} scenario(s)")
    per_scenario = []
    for scenario in scenarios:
        name = scenario["name"]
        print(f"==> Scenario: {name}")
        eval_dir = iteration_dir / f"eval-{name}"

        print("    with_skill...")
        with_result = run_arm(scenario, True, args.model, args.effort, env, eval_dir / "with_skill")
        print(f"    with_skill: {'PASS' if with_result['pass'] else 'FAIL'}")

        print("    without_skill...")
        without_result = run_arm(scenario, False, args.model, args.effort, env, eval_dir / "without_skill")
        print(f"    without_skill: {'PASS' if without_result['pass'] else 'FAIL'}")

        per_scenario.append({"name": name, "with_skill": with_result, "without_skill": without_result})

    filters = {
        "tiers": [args.tier] if args.tier else [],
        "types": [args.type] if args.type else [],
        "features": [args.feature] if args.feature else [],
        "tests": [args.tests] if args.tests else [],
    }
    benchmark = build_benchmark(scenarios, per_scenario, filters, skill_sha, args.model, args.effort)
    validate_benchmark_shape(benchmark)

    benchmark_path = iteration_dir / "benchmark.json"
    benchmark_path.write_text(json.dumps(benchmark, indent=2) + "\n")
    write_compare_md(benchmark, iteration_dir / "compare.md")

    print(f"==> Wrote {benchmark_path}")
    print(json.dumps(benchmark["run_summary"], indent=2))


if __name__ == "__main__":
    main()
