#!/usr/bin/env python3
"""Promote a scenario arm result from test/results into a campaign iteration."""
import argparse
import json
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent


def mean(xs):
    return sum(xs) / len(xs) if xs else None


def _arm_summary(grading):
    s = grading["summary"]
    return {
        "passed": s["passed"],
        "failed": s["failed"],
        "total": s["total"],
        "pass_rate": s["pass_rate"],
    }


def _recompute_summary(bm):
    for arm in ("with_skill", "without_skill"):
        pass_rates, durs, toks = [], [], []
        for r in bm["per_scenario"]:
            gs = (r.get("grading_summaries") or {}).get(arm)
            if gs and gs.get("pass_rate") is not None:
                pass_rates.append(gs["pass_rate"])
            t = (r.get("timing") or {}).get(arm) or {}
            if t.get("duration_ms") is not None:
                durs.append(t["duration_ms"] / 1000.0)
            if t.get("total_tokens") is not None:
                toks.append(t["total_tokens"])
        bm["run_summary"][arm] = {
            "pass_rate": {"mean": mean(pass_rates)},
            "time_seconds": {"mean": mean(durs)},
            "tokens": {"mean": mean(toks)},
        }
    ws = bm["run_summary"]["with_skill"]["pass_rate"]["mean"]
    wo = bm["run_summary"]["without_skill"]["pass_rate"]["mean"]
    wt = bm["run_summary"]["with_skill"]["time_seconds"]["mean"]
    wot = bm["run_summary"]["without_skill"]["time_seconds"]["mean"]
    wk = bm["run_summary"]["with_skill"]["tokens"]["mean"]
    wok = bm["run_summary"]["without_skill"]["tokens"]["mean"]
    bm["run_summary"]["delta"] = {
        "pass_rate": (ws - wo) if ws is not None and wo is not None else None,
        "time_seconds": (wt - wot) if wt is not None and wot is not None else None,
        "tokens": (wk - wok) if wk is not None and wok is not None else None,
    }


def promote(name: str, iteration: int, arm: str) -> None:
    if arm not in ("with_skill", "without_skill"):
        raise SystemExit(f"arm must be with_skill or without_skill, got {arm!r}")

    campaign = REPO / "test" / "workspace" / f"iteration-{iteration}"
    src = REPO / "test" / "results" / name
    transcript = REPO / "test" / "results" / f"{name}-transcript.jsonl"
    arm_dir = campaign / f"eval-{name}" / arm
    arm_dir.mkdir(parents=True, exist_ok=True)
    (arm_dir / "outputs").mkdir(exist_ok=True)
    for f in ("grading.json", "timing.json"):
        shutil.copy2(src / f, arm_dir / f)
    if transcript.exists():
        shutil.copy2(transcript, arm_dir / "transcript.jsonl")

    grading = json.loads((arm_dir / "grading.json").read_text())
    timing = json.loads((arm_dir / "timing.json").read_text())
    summary = grading["summary"]
    passed = summary["failed"] == 0

    bm_path = campaign / "benchmark.json"
    bm = json.loads(bm_path.read_text())
    existing = next((r for r in bm["per_scenario"] if r["name"] == name), None)
    if existing is None:
        existing = {
            "name": name,
            "with_skill_pass": None,
            "without_skill_pass": None,
            "pass_delta": None,
            "timing": {"with_skill": None, "without_skill": None},
            "grading_summaries": {"with_skill": None, "without_skill": None},
            "cached": {"with_skill": None, "without_skill": None},
        }
        bm["per_scenario"].append(existing)

    existing[f"{arm}_pass"] = passed
    existing["timing"][arm] = timing
    existing["grading_summaries"][arm] = _arm_summary(grading)
    existing["cached"][arm] = False
    if existing["with_skill_pass"] is not None and existing["without_skill_pass"] is not None:
        existing["pass_delta"] = int(existing["with_skill_pass"]) - int(existing["without_skill_pass"])
    else:
        existing["pass_delta"] = None

    bm["scenarios"] = [r["name"] for r in bm["per_scenario"]]
    _recompute_summary(bm)
    bm_path.write_text(json.dumps(bm, indent=2) + "\n")
    print(f"promoted {name}/{arm} pass={passed} assertions={summary}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("name")
    p.add_argument("--iteration", type=int, required=True)
    p.add_argument(
        "--arm",
        choices=("with_skill", "without_skill"),
        default="with_skill",
    )
    args = p.parse_args()
    promote(args.name, args.iteration, args.arm)


if __name__ == "__main__":
    main()
