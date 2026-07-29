#!/usr/bin/env python3
"""
Consolidated TEST_REPORT.html generator. Reads whatever test/eval artifacts
currently exist on disk (guards + evals:check re-run fresh; all
test/workspace/iteration-*/benchmark.json for trend + latest for detail) and
writes test/workspace/TEST_REPORT.html. Decoupled from running tests: run any
subset of `task test*` you like, then `task test:report` to refresh the view.
Safe to re-run any number of times; always reflects current disk state.
"""
import html
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "test"))
from scenario_lib import load_all_scenarios  # noqa: E402

WORKSPACE_DIR = REPO_ROOT / "test" / "workspace"
REPORT_PATH = WORKSPACE_DIR / "TEST_REPORT.html"
SKILL_NAME = "hc-scaffold-service"


def run_check(cmd, cwd=REPO_ROOT):
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return proc.returncode == 0, (proc.stdout + proc.stderr).strip()


def load_iterations():
    iterations = []
    for path in sorted(WORKSPACE_DIR.glob("iteration-*")):
        m = re.match(r"iteration-(\d+)$", path.name)
        if not m:
            continue
        bm_path = path / "benchmark.json"
        if not bm_path.exists():
            continue
        try:
            benchmark = json.loads(bm_path.read_text())
        except json.JSONDecodeError:
            continue
        iterations.append({"num": int(m.group(1)), "dir": path, "benchmark": benchmark})
    iterations.sort(key=lambda i: i["num"])
    return iterations


def load_scenario_detail(iteration_dir, scenario_name):
    eval_dir = iteration_dir / f"eval-{scenario_name}"
    detail = {}
    for arm in ("with_skill", "without_skill"):
        grading_path = eval_dir / arm / "grading.json"
        if grading_path.exists():
            detail[arm] = json.loads(grading_path.read_text())
    return detail


def find_regressions(current, previous):
    prev_by_name = {r["name"]: r for r in previous["benchmark"]["per_scenario"]}
    regressions = []
    for row in current["benchmark"]["per_scenario"]:
        prev = prev_by_name.get(row["name"])
        if prev and prev["with_skill_pass"] and not row["with_skill_pass"]:
            regressions.append(row["name"])
    return regressions


def find_non_discriminating(current):
    flagged = []
    for row in current["benchmark"]["per_scenario"]:
        detail = load_scenario_detail(current["dir"], row["name"])
        without = detail.get("without_skill", {}).get("summary", {})
        if without.get("pass_rate") == 1.0:
            flagged.append(row["name"])
    return flagged


def esc(s):
    return html.escape(str(s))


def build_metric_series(iterations, metric):
    with_vals, without_vals = [], []
    for it in iterations:
        rs = it["benchmark"]["run_summary"]
        with_vals.append(rs["with_skill"][metric]["mean"])
        without_vals.append(rs["without_skill"][metric]["mean"])
    return with_vals, without_vals


def render_svg_line_chart(iterations, metric, title):
    if len(iterations) < 2:
        return ""
    with_vals, without_vals = build_metric_series(iterations, metric)
    all_vals = with_vals + without_vals
    lo, hi = min(all_vals), max(all_vals)
    if hi == lo:
        hi = lo + 1
    w, h, pad = 480, 140, 24
    n = len(iterations)

    def point(i, v):
        x = pad + (w - 2 * pad) * (i / (n - 1) if n > 1 else 0)
        y = h - pad - (h - 2 * pad) * ((v - lo) / (hi - lo))
        return x, y

    def polyline(vals, color):
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in (point(i, v) for i, v in enumerate(vals)))
        return f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2"/>'

    dots = []
    for i, v in enumerate(with_vals):
        x, y = point(i, v)
        dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="#2563eb"/>')
    for i, v in enumerate(without_vals):
        x, y = point(i, v)
        dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="#9ca3af"/>')

    labels = "".join(
        f'<text x="{point(i, lo)[0]:.1f}" y="{h - 4}" font-size="10" text-anchor="middle" fill="#666">i{it["num"]}</text>'
        for i, it in enumerate(iterations)
    )

    return f"""
    <div class="chart">
      <div class="chart-title">{esc(title)}</div>
      <svg width="{w}" height="{h}" viewBox="0 0 {w} {h}">
        {polyline(with_vals, '#2563eb')}
        {polyline(without_vals, '#9ca3af')}
        {''.join(dots)}
        {labels}
      </svg>
      <div class="legend"><span class="dot" style="background:#2563eb"></span>with-skill
        <span class="dot" style="background:#9ca3af"></span>without-skill</div>
    </div>
    """


def main():
    all_scenarios = load_all_scenarios(str(REPO_ROOT / "test" / "scenarios"))
    compare_scenarios = [s for s in all_scenarios if s.get("compare")]

    guards_ok, guards_out = run_check(["task", "test:guards"])
    evals_ok, evals_out = run_check(["python3", "test/scripts/sync_evals.py", "--check"])

    iterations = load_iterations()
    triggers_path = REPO_ROOT / "skills" / SKILL_NAME / "evals" / "triggers.json"
    triggers = json.loads(triggers_path.read_text()) if triggers_path.exists() else None

    verdict = "PASS"
    verdict_reasons = []

    if not guards_ok:
        verdict = "FAIL"
        verdict_reasons.append("guards failed")
    if not evals_ok:
        verdict = "FAIL"
        verdict_reasons.append("evals.json/scenario-map.json drift")

    if not iterations:
        if verdict == "PASS":
            verdict = "PASS WITH ISSUES"
            verdict_reasons.append("no compare data")
        current = None
        previous = None
        regressions = []
        non_discriminating = []
        coverage_note = f"0/{len(compare_scenarios)}"
    else:
        current = iterations[-1]
        previous = iterations[-2] if len(iterations) > 1 else None
        regressions = find_regressions(current, previous) if previous else []
        non_discriminating = find_non_discriminating(current)
        covered = len(current["benchmark"]["per_scenario"])
        coverage_note = f"{covered}/{len(compare_scenarios)}"

        if regressions:
            verdict = "FAIL"
            verdict_reasons.append(f"regression(s): {', '.join(regressions)}")
        if verdict != "FAIL":
            rs = current["benchmark"]["run_summary"]
            if rs["with_skill"]["pass_rate"]["mean"] < 1.0:
                verdict = "PASS WITH ISSUES"
                verdict_reasons.append("with-skill pass rate < 100%")
            if covered < len(compare_scenarios):
                verdict = "PASS WITH ISSUES" if verdict == "PASS" else verdict
                verdict_reasons.append(f"partial scenario coverage ({coverage_note})")
            if non_discriminating:
                verdict = "PASS WITH ISSUES" if verdict == "PASS" else verdict
                verdict_reasons.append(f"non-discriminating check(s): {', '.join(non_discriminating)}")

    verdict_class = {"PASS": "pass", "PASS WITH ISSUES": "warn", "FAIL": "fail"}[verdict]

    # ---- Executive summary ----
    exec_rows = [
        f"<tr><td>Skill</td><td>{esc(SKILL_NAME)}</td></tr>",
        f"<tr><td>Iteration(s) on disk</td><td>{esc(', '.join(str(i['num']) for i in iterations) or '(none)')}</td></tr>",
        f"<tr><td>Verdict</td><td><span class='badge {verdict_class}'>{esc(verdict)}</span> "
        f"{esc('; '.join(verdict_reasons)) if verdict_reasons else ''}</td></tr>",
        f"<tr><td>Guards (genericity + line budget)</td><td>{'PASS' if guards_ok else 'FAIL'}</td></tr>",
        f"<tr><td>evals.json/scenario-map.json drift</td><td>{'in sync' if evals_ok else 'OUT OF SYNC'}</td></tr>",
        f"<tr><td>Scenario coverage (current iteration)</td><td>{esc(coverage_note)}</td></tr>",
    ]
    if current:
        rs = current["benchmark"]["run_summary"]
        exec_rows.append(
            f"<tr><td>Pass rate: with-skill vs. baseline</td><td>"
            f"{rs['with_skill']['pass_rate']['mean']:.0%} vs. {rs['without_skill']['pass_rate']['mean']:.0%} "
            f"(delta {rs['delta']['pass_rate']:+.0%})</td></tr>"
        )
        if previous:
            prev_rs = previous["benchmark"]["run_summary"]
            exec_rows.append(
                f"<tr><td>Pass rate vs. previous iteration (i{previous['num']} → i{current['num']})</td><td>"
                f"{prev_rs['with_skill']['pass_rate']['mean']:.0%} → {rs['with_skill']['pass_rate']['mean']:.0%}</td></tr>"
            )
        exec_rows.append(
            f"<tr><td>Regressions vs. previous iteration</td><td>"
            f"{esc(', '.join(regressions)) if regressions else 'none'}</td></tr>"
        )
        exec_rows.append(
            f"<tr><td>Cost: with-skill vs. baseline</td><td>"
            f"time {rs['with_skill']['time_seconds']['mean']:.1f}s vs. {rs['without_skill']['time_seconds']['mean']:.1f}s, "
            f"tokens {rs['with_skill']['tokens']['mean']:,.0f} vs. {rs['without_skill']['tokens']['mean']:,.0f}</td></tr>"
        )
    trig_note = (
        f"NOT automatically measured — {len(triggers['should_trigger'])} should-trigger / "
        f"{len(triggers['should_not_trigger'])} should-not-trigger prompts exist in "
        f"skills/{SKILL_NAME}/evals/triggers.json but are only graded manually via "
        f"<code>task test:skill-creator:triggers</code>."
        if triggers else "triggers.json not found."
    )
    exec_rows.append(f"<tr><td>Triggering accuracy</td><td>{trig_note}</td></tr>")

    exec_html = "<table class='kv'>" + "".join(exec_rows) + "</table>"

    # ---- Per-test breakdown ----
    per_test_html = []
    if current:
        detail_by_name = {s["name"]: s for s in compare_scenarios}
        for row in current["benchmark"]["per_scenario"]:
            scenario = detail_by_name.get(row["name"], {})
            detail = load_scenario_detail(current["dir"], row["name"])
            block = [f"<div class='test-block'>", f"<h3>{esc(row['name'])} "
                     f"<span class='badge {'pass' if row['with_skill_pass'] else 'fail'}'>"
                     f"{'PASS' if row['with_skill_pass'] else 'FAIL'}</span></h3>"]
            block.append(f"<p><strong>Prompt:</strong> {esc(scenario.get('prompt', '(unknown — scenario file missing/renamed)'))}</p>")
            block.append(f"<p><strong>Expected:</strong> {esc(scenario.get('expected_output', '(unknown)'))}</p>")

            for arm, label in (("with_skill", "With skill"), ("without_skill", "Baseline (no skill)")):
                arm_detail = detail.get(arm)
                block.append(f"<div class='arm'><h4>{label}</h4>")
                if not arm_detail:
                    block.append("<p class='missing'>No grading.json found for this arm — could not verify.</p>")
                else:
                    block.append("<table class='assertions'><tr><th>Assertion</th><th>Result</th><th>Evidence</th></tr>")
                    for a in arm_detail["assertion_results"]:
                        cls = "pass" if a["passed"] else "fail"
                        block.append(
                            f"<tr><td>{esc(a['text'])}</td><td class='{cls}'>{'PASS' if a['passed'] else 'FAIL'}</td>"
                            f"<td>{esc(a['evidence'])}</td></tr>"
                        )
                    block.append("</table>")
                block.append("</div>")

            if row["name"] in non_discriminating:
                block.append(
                    "<p class='flag'>⚠ Non-discriminating: the baseline (no-skill) arm already passes all "
                    "assertions for this scenario — this check would not catch a broken skill.</p>"
                )
            block.append("</div>")
            per_test_html.append("".join(block))
    per_test_section = "".join(per_test_html) or (
        "<p><strong>No compare data yet.</strong> Run <code>task test:compare</code> "
        "(or <code>task test:compare:tier1</code> for a cheap smoke run) to populate "
        "test/workspace/iteration-N/, then re-run <code>task test:report</code>.</p>"
    )

    # ---- Aggregate metrics table ----
    agg_html = "<p>No compare data available.</p>"
    if current:
        rs = current["benchmark"]["run_summary"]
        agg_html = f"""
        <table class='metrics'>
          <tr><th>Metric</th><th>With skill</th><th>Baseline</th><th>Delta</th></tr>
          <tr><td>Pass rate</td><td>{rs['with_skill']['pass_rate']['mean']:.0%}</td>
              <td>{rs['without_skill']['pass_rate']['mean']:.0%}</td>
              <td>{rs['delta']['pass_rate']:+.0%}</td></tr>
          <tr><td>Time (s, mean)</td><td>{rs['with_skill']['time_seconds']['mean']:.2f}</td>
              <td>{rs['without_skill']['time_seconds']['mean']:.2f}</td>
              <td>{rs['delta']['time_seconds']:+.2f}</td></tr>
          <tr><td>Tokens (mean)</td><td>{rs['with_skill']['tokens']['mean']:,.0f}</td>
              <td>{rs['without_skill']['tokens']['mean']:,.0f}</td>
              <td>{rs['delta']['tokens']:+,.0f}</td></tr>
        </table>
        <p class='note'>Single run per scenario per arm — no stddev available (write_workspace.py runs each once).</p>
        """

    # ---- Trend section ----
    trend_html = ""
    if len(iterations) > 1:
        rows = []
        for it in iterations:
            rs = it["benchmark"]["run_summary"]
            rows.append(
                f"<tr><td>i{it['num']}</td>"
                f"<td>{rs['with_skill']['pass_rate']['mean']:.0%}</td>"
                f"<td>{rs['without_skill']['pass_rate']['mean']:.0%}</td>"
                f"<td>{rs['with_skill']['time_seconds']['mean']:.1f}s</td>"
                f"<td>{rs['with_skill']['tokens']['mean']:,.0f}</td></tr>"
            )
        # consistently-failing assertions across iterations, per scenario+assertion text
        fail_counts = {}
        seen_iters = {}
        for it in iterations:
            for row in it["benchmark"]["per_scenario"]:
                d = load_scenario_detail(it["dir"], row["name"])
                for arm in ("with_skill",):
                    for a in d.get(arm, {}).get("assertion_results", []):
                        key = (row["name"], a["text"])
                        seen_iters.setdefault(key, set()).add(it["num"])
                        if not a["passed"]:
                            fail_counts[key] = fail_counts.get(key, 0) + 1
        consistent_failures = [
            f"<li>{esc(name)} — “{esc(text)}” failed in {fail_counts[(name, text)]}/{len(seen_iters[(name, text)])} iteration(s)</li>"
            for (name, text), count in fail_counts.items()
            if count == len(seen_iters[(name, text)]) and len(seen_iters[(name, text)]) > 1
        ]
        trend_html = f"""
        <table class='trend'>
          <tr><th>Iteration</th><th>Pass % (with)</th><th>Pass % (baseline)</th><th>Time (with)</th><th>Tokens (with)</th></tr>
          {''.join(rows)}
        </table>
        {render_svg_line_chart(iterations, 'pass_rate', 'Pass rate trend (blue=with-skill, gray=baseline)')}
        {render_svg_line_chart(iterations, 'tokens', 'Token usage trend')}
        <h4>Consistently failing assertions (signal, not flakiness)</h4>
        <ul>{''.join(consistent_failures) or '<li>none</li>'}</ul>
        """

    # ---- Known gaps ----
    gaps = []
    if non_discriminating:
        gaps.append(f"Non-discriminating checks (baseline already passes): {', '.join(non_discriminating)}.")
    if current and len(current["benchmark"]["per_scenario"]) < len(compare_scenarios):
        missing = sorted(set(s["name"] for s in compare_scenarios) - set(r["name"] for r in current["benchmark"]["per_scenario"]))
        gaps.append(f"Scenario coverage is partial ({coverage_note}). Not yet run: {', '.join(missing)}.")
    gaps.append(
        "Triggering accuracy is not automatically graded in this repo's harness — "
        "triggers.json prompts are only used in the manual/interactive skill-creator tuning flow."
    )
    baseline_dir = REPO_ROOT / "test" / "baseline"
    if baseline_dir.exists() and not any(baseline_dir.iterdir()):
        gaps.append(
            "test/baseline/ is empty — recorded-unaided-failure discipline "
            "(docs/maintaining.md) has no artifacts on disk yet."
        )
    gaps.append(
        "docs/testing.md references an advisory LLM judge for inference-quality; "
        "it is not implemented in test/assertions/check.py (docs ahead of code)."
    )
    gaps_html = "<ul>" + "".join(f"<li>{g}</li>" for g in gaps) + "</ul>"

    guards_detail = f"<pre>{esc(guards_out)}</pre>"
    evals_detail = f"<pre>{esc(evals_out)}</pre>"

    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>TEST_REPORT — {esc(SKILL_NAME)}</title>
<style>
  body {{ font-family: -apple-system, Helvetica, Arial, sans-serif; max-width: 980px; margin: 2rem auto; padding: 0 1rem; color: #1a1a1a; }}
  h1 {{ margin-bottom: 0.2rem; }}
  h2 {{ border-bottom: 1px solid #ddd; padding-bottom: 0.3rem; margin-top: 2.5rem; }}
  table {{ border-collapse: collapse; width: 100%; margin: 0.5rem 0 1rem; }}
  td, th {{ border: 1px solid #ddd; padding: 0.4rem 0.6rem; text-align: left; font-size: 0.92rem; }}
  th {{ background: #f5f5f5; }}
  table.kv td:first-child {{ font-weight: 600; width: 280px; }}
  .badge {{ display: inline-block; padding: 0.15rem 0.6rem; border-radius: 4px; font-weight: 700; font-size: 0.85rem; }}
  .badge.pass {{ background: #dcfce7; color: #166534; }}
  .badge.warn {{ background: #fef9c3; color: #854d0e; }}
  .badge.fail {{ background: #fee2e2; color: #991b1b; }}
  td.pass {{ color: #166534; font-weight: 600; }}
  td.fail {{ color: #991b1b; font-weight: 600; }}
  .test-block {{ border: 1px solid #eee; border-radius: 8px; padding: 1rem; margin-bottom: 1.2rem; }}
  .arm {{ margin-top: 0.6rem; }}
  .flag {{ background: #fef9c3; padding: 0.5rem; border-radius: 4px; }}
  .missing {{ color: #92400e; font-style: italic; }}
  .note {{ color: #666; font-size: 0.85rem; }}
  .chart {{ display: inline-block; margin: 0.5rem 1rem 0.5rem 0; }}
  .chart-title {{ font-size: 0.85rem; color: #444; margin-bottom: 0.2rem; }}
  .legend {{ font-size: 0.8rem; color: #444; }}
  .dot {{ display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin: 0 4px 0 8px; }}
  pre {{ background: #f8f8f8; padding: 0.6rem; border-radius: 4px; overflow-x: auto; font-size: 0.82rem; }}
  details summary {{ cursor: pointer; font-weight: 600; margin: 0.4rem 0; }}
</style>
</head>
<body>
<h1>TEST_REPORT — {esc(SKILL_NAME)}</h1>
<p class="note">Generated by test/scripts/generate_report.py from whatever is currently on disk under test/workspace/. Re-run <code>task test:report</code> anytime after any subset of tests to refresh.</p>

<h2>1. Executive summary</h2>
{exec_html}
<details><summary>Guards output</summary>{guards_detail}</details>
<details><summary>Evals sync-check output</summary>{evals_detail}</details>

<h2>2. Per-test breakdown</h2>
{per_test_section}

<h2>3. Aggregate metrics</h2>
{agg_html}

<h2>4. Trend across iterations</h2>
{trend_html or '<p>Only one iteration on disk — trend requires 2+.</p>'}

<h2>5. Known gaps / next steps</h2>
{gaps_html}

</body>
</html>
"""
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(html_doc)
    print(f"Wrote {REPORT_PATH}")
    print(f"Verdict: {verdict}" + (f" ({'; '.join(verdict_reasons)})" if verdict_reasons else ""))


if __name__ == "__main__":
    main()
