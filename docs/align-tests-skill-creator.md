# Align testing with Claude skill-creator best practices

**Audience:** an implementing agent with **no** prior conversation context. This file is the sole source of truth for this work. Do not invent requirements from memory. Do not reopen decisions marked settled.

**Voice:** imperative, same as [implementation-plan.md](implementation-plan.md).

**Related docs to update as part of this work** (not optional reading for “ideas” — amend them in the tasks below):

- [skill-vs-baseline.md](skill-vs-baseline.md) — A/B infra plan; **rewrite its CLI section to Task-first** and point measurement at `benchmark.json` / workspace layout defined here
- [testing.md](testing.md), [maintaining.md](maintaining.md), [implementation-plan.md](implementation-plan.md) (testing/harness sections only)
- [CLAUDE.md](../CLAUDE.md), [README.md](../README.md)

**External specs (read if needed for format details):**

- https://agentskills.io/skill-creation/evaluating-skills
- https://code.claude.com/docs/en/skills#run-evals-with-skill-creator
- https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview
- https://taskfile.dev/docs/guide

---

## 0. Repo facts (do not rediscover by guessing)

Workspace root: repo containing this file at `docs/align-tests-skill-creator.md`.

Already present:

- Skill package: `skills/hc-scaffold-service/{SKILL.md,reference.md,examples.md}`
- Scenarios: `test/scenarios/*.yaml` (13 files). Labels `compare` / `tier` / `type` / `feature` may be **missing** — add them per [skill-vs-baseline.md](skill-vs-baseline.md) §3 one-time values if absent
- Stub MCP: `test/stub/server.py` with `STUB_SCENARIO` modes
- Harness: `test/run.sh`, `test/docker-compose.yaml`, `test/mcp-servers.test.yaml`, `test/skills.test.yaml`, `test/assertions/check.py`
- `test/run.sh` parses `--no-skill` into `INSTALL_SKILL` but **does not** disable skill install in docker (bug to fix)
- **No** `Taskfile.yml` at repo root
- **No** `skills/hc-scaffold-service/evals/`
- **No** agentskills workspace tree under `test/workspace/`

Atomic commits: **MUST** follow [CLAUDE.md](../CLAUDE.md) / implementation-plan §2 — one logical deliverable per commit; commit before starting the next task; never one giant squash at the end.

**Do not** execute a full expensive tier-3 A/B matrix as part of this work. Infra + Taskfile + one smoke paired run (e.g. a single tier-1 scenario or `task test:compare:tier1` if cheap enough) is enough to prove wiring. Operators run full compares later.

---

## 1. Decisions (settled — do not reopen)

### 1.1 Hybrid runner

| Layer | Role |
|-------|------|
| Primary | MCP stub + `test/run.sh` (fail-fast, schema, tool-call assertions) |
| Compatibility | skill-creator / agentskills formats (`evals/evals.json`, workspace, `grading.json`, `timing.json`, `benchmark.json`) |
| Secondary | skill-creator Claude Code plugin (trigger/description tuning; interactive only) |

**MUST NOT** replace the stub harness with skill-creator as the primary runner.

### 1.2 Authoring vs emitted evals

| Source | Path | Contents |
|--------|------|----------|
| Author | `test/scenarios/<name>.yaml` | `name`, `prompt`, `expected_output`, `stub_scenario`, `compare`, `tier`, `type`, `feature`, mechanical `expectations`, optional `compare_prompt` |
| Emitted | `skills/hc-scaffold-service/evals/evals.json` | Official skill-creator cases: `id`, `prompt`, `expected_output`, `assertions` (strings) |
| Emitted | `skills/hc-scaffold-service/evals/triggers.json` | should-trigger / should-not-trigger prompts for description tuning |

`task test:evals:sync` writes evals.json from scenarios. `task test:evals:check` fails if drift.

### 1.3 Operator entrypoint

Root `Taskfile.yml` (go-task `version: '3'`). Documented commands are **`task …` only**.

### 1.4 Fair prompts

For without-skill / `--no-skill` arm: **MUST NOT** send a leading `/hc-scaffold-service` slash. Use `compare_prompt` if set; else strip a leading `/hc-scaffold-service` (+ following space) from `prompt`.

---

## 2. Exact schemas the implementer MUST produce

### 2.1 Scenario YAML (minimum fields)

```yaml
name: plain-request                 # MUST equal filename basename
description: "..."
compare: true
tier: 1                             # 1|2|3
type: preflight                     # preflight|discipline|interview
feature: fail-fast                  # see skill-vs-baseline vocabulary
stub_scenario: default
prompt: "..."
expected_output: "Human-readable success description for graders and evals.json"
# compare_prompt: "..."             # optional fair prompt for no-skill arm
# replies:                          # optional multi-turn follow-ups (see docs/testing.md)
#   - "Yes"
#   - "Yes, submit"
expectations:
  - question_count_max: 5
  - tool_called: execute-template
```

One-time label values if missing: copy from [skill-vs-baseline.md](skill-vs-baseline.md) §3 “One-time label values”.

### 2.2 `skills/hc-scaffold-service/evals/evals.json`

```json
{
  "skill_name": "hc-scaffold-service",
  "evals": [
    {
      "id": 1,
      "prompt": "<from scenario prompt or compare_prompt for display; use natural-language prompt>",
      "expected_output": "<from scenario expected_output>",
      "assertions": [
        "<natural-language mirror of each mechanical expectation>"
      ],
      "files": []
    }
  ]
}
```

Map scenario `name` → stable numeric `id` (sort scenarios by `name`, assign 1..N). Include a `name` string field **inside each eval object** if skill-creator ignores unknown fields — or put `name` only in scenarios and keep evals.json strictly to the official fields. **Settled:** official fields only in evals.json; sync script maintains a sidecar `skills/hc-scaffold-service/evals/scenario-map.json` `{ "1": "plain-request", ... }` for harness join.

### 2.3 `skills/hc-scaffold-service/evals/triggers.json`

```json
{
  "skill_name": "hc-scaffold-service",
  "should_trigger": [
    "I need to create a new Spring Boot service from a Backstage template",
    "Scaffold a Lambda API for me",
    "/hc-scaffold-service"
  ],
  "should_not_trigger": [
    "Refactor this Python module for readability",
    "What is the capital of France?",
    "Open a PR to bump a dependency version only"
  ]
}
```

At least 3 should_trigger and 2 should_not_trigger. Edit freely if wording is weak; keep counts.

### 2.4 Workspace layout (per compare / paired run)

```text
test/workspace/iteration-<N>/
  benchmark.json
  eval-<scenario-name>/
    with_skill/
      transcript.jsonl
      outputs/           # may be empty; create dir
      timing.json
      grading.json
    without_skill/
      transcript.jsonl
      outputs/
      timing.json
      grading.json
```

`iteration-<N>`: integer; use next free N under `test/workspace/` (start at 1). Do not overwrite prior iterations.

### 2.5 `timing.json`

```json
{
  "total_tokens": 0,
  "duration_ms": 0,
  "input_tokens": 0,
  "output_tokens": 0,
  "cache_creation_input_tokens": 0,
  "cache_read_input_tokens": 0
}
```

`total_tokens` = sum of input + output + cache fields available from the transcript. `duration_ms` = wall clock for that arm.

### 2.6 `grading.json`

```json
{
  "assertion_results": [
    {
      "text": "tool execute-template was called",
      "passed": true,
      "evidence": "tool_use name=... found at ..."
    }
  ],
  "summary": {
    "passed": 1,
    "failed": 0,
    "total": 1,
    "pass_rate": 1.0
  }
}
```

Emit from `test/assertions/check.py` (extend it). Exit non-zero if any assertion failed (preserve current fail behavior).

### 2.7 `benchmark.json`

```json
{
  "schema_version": 1,
  "skill_sha": "<git rev-parse HEAD>",
  "model": "<actual model from transcript>",
  "effort": "<or null>",
  "filters": { "tiers": [], "types": [], "features": [], "tests": [] },
  "scenarios": ["..."],
  "run_summary": {
    "with_skill": {
      "pass_rate": { "mean": 0.0 },
      "time_seconds": { "mean": 0.0 },
      "tokens": { "mean": 0.0 }
    },
    "without_skill": {
      "pass_rate": { "mean": 0.0 },
      "time_seconds": { "mean": 0.0 },
      "tokens": { "mean": 0.0 }
    },
    "delta": {
      "pass_rate": 0.0,
      "time_seconds": 0.0,
      "tokens": 0.0
    }
  },
  "per_scenario": []
}
```

`per_scenario` entries: `{ "name", "with_skill_pass", "without_skill_pass", "pass_delta", "timing", "grading_summaries" }` as needed for `test:diff`.

Optional markdown view `test/workspace/iteration-<N>/compare.md` generated from the same data (stable columns; see skill-vs-baseline report rules). Prefer implementing markdown generation; if time-boxed, `benchmark.json` alone is enough for Done, and markdown can follow in a later commit.

---

## 3. Required Taskfile tasks (exact names)

Create [`Taskfile.yml`](../Taskfile.yml) at repo root.

| Task | Behavior |
|------|----------|
| `test:guards` | Run genericity grep + `wc -l` SKILL.md ≤ 400 (logic today in `test/run.sh`; extract or invoke a shared script) |
| `test:evals:sync` | Regenerate evals.json + scenario-map.json from scenarios |
| `test:evals:check` | Exit 1 if sync would change files |
| `test:list` | Print `name tier type feature` for `compare: true` scenarios |
| `test:scenario` | `INSTALL_SKILL=true`; run `TESTS` (comma-separated names) or all |
| `test:scenario:no-skill` | Same with skill disabled |
| `test:compare` | Paired A/B for selected scenarios; write iteration workspace + benchmark.json |
| `test:compare:tier1` | `TIER=1` compare |
| `test:compare:tier` | Requires `TIER` |
| `test:compare:type` | Requires `TYPE` |
| `test:compare:feature` | Requires `FEATURE` |
| `test:compare:tests` | Requires `TESTS` |
| `test:diff` | Requires `A` and `B` paths; run `test/assertions/diff_compare.py` |
| `test:skill-creator:install` | Echo: `/plugin install skill-creator@claude-plugins-official` then `/reload-plugins` |
| `test:skill-creator:eval` | Echo exact prompt: `Evaluate my hc-scaffold-service skill with skill-creator using skills/hc-scaffold-service/evals/evals.json` |
| `test:skill-creator:triggers` | Echo prompt to tune description using `evals/triggers.json` |
| `test` | `task: [test:guards, test:compare:tier1]` |

Vars: `TESTS`, `TIER`, `TYPE`, `FEATURE`, `MODEL`, `EFFORT`, `A`, `B`. Forward into `test/run.sh`.

Accept `--without-skill` as alias of `--no-skill` on `run.sh`.

Prerequisite check: if `task` is missing, docs say install via https://taskfile.dev/installation/ (`brew install go-task`).

---

## 4. Tasks (execute in order)

### T1 — Amend docs to Task-first + hybrid artifacts

Update these files so they do not contradict this plan:

1. [skill-vs-baseline.md](skill-vs-baseline.md): replace raw `./test/run.sh --compare` examples with `task test:compare…`; state measurement outputs are workspace + `benchmark.json`; add hybrid + skill-creator prompt tasks; keep tier/type/feature label schema on YAMLs.
2. [testing.md](testing.md): Running section uses `task …` only; describe evals sync and workspace layout.
3. [maintaining.md](maintaining.md): after skill change → `task test` (or `task test:compare:tier1`); full `task test:compare` before merge.
4. [implementation-plan.md](implementation-plan.md): note Taskfile + evals.json as harness requirements; baseline = without_skill arm; do not require redoing completed T1–T9 history — add a short “Testing alignment” note or amend T6/T7/T10 language going forward.

**Commit:** `docs: align testing plans with skill-creator hybrid and Taskfile`

*Done when:* those docs cite `task` for operator commands and point at this file.

### T2 — Scenario labels + expected_output + fair prompts

For each file in `test/scenarios/*.yaml`:

- Ensure `compare`, `tier`, `type`, `feature`, `name`, `expected_output`
- Ensure prompts used for no-skill are fair (add `compare_prompt` where `prompt` starts with `/hc-scaffold-service`)

**Commit:** `test: add compare labels and expected_output to scenarios`

*Done when:* all 13 scenario files validate against §2.1 fields.

### T3 — Fix `--no-skill` + skills.none template

1. Add `test/skills.none.test.yaml` with no local skill (or `enabled: false` / empty local list — whichever the ai-tdd entrypoint accepts; mirror `skills.test.yaml` shape with skill absent/disabled).
2. When `INSTALL_SKILL=false`, set `SKILLS_TEMPLATE` to that file in docker-compose/run.sh.
3. Apply fair-prompt stripping when `INSTALL_SKILL=false`.

**Commit:** `test: honor --no-skill with skills.none template`

*Done when:* `./test/run.sh --no-skill plain-request` (or via task once T5 exists) does not install `hc-scaffold-service`.

### T4 — grading.json, timing.json, workspace writer, benchmark.json

Extend `test/assertions/check.py` and `test/run.sh` (or new `test/assertions/write_workspace.py`) to:

- Write arms under `test/workspace/iteration-N/eval-<name>/{with_skill,without_skill}/`
- Emit grading.json + timing.json per arm
- For `--compare`, run both arms and write `benchmark.json`

Add `test/assertions/diff_compare.py` comparing two `benchmark.json` files (schema_version, filters/scenarios mismatch, pass flips; metric drift advisory).

Add `test/fixtures/compare-report.schema.json` (or benchmark schema) and validate on write.

**Commit:** `test: emit agentskills workspace grading timing and benchmark`

*Done when:* a paired run of one scenario creates the tree in §2.4 and a valid benchmark.json.

### T5 — Taskfile.yml

Add root `Taskfile.yml` implementing §3. Wire to `test/run.sh` / new scripts. `desc:` on every task. `test:evals:sync` / `check` may stub to “not implemented” only until T6 — prefer implementing sync in T6 same day; if split, T5 tasks that need sync can call a placeholder that errors with “run T6”.

**Commit:** `chore: add Taskfile.yml for test entrypoints`

*Done when:* `task --list` shows all §3 names; `task test:guards` works.

### T6 — evals sync + triggers

1. Add `test/scripts/sync_evals.py` (or similar) implementing §2.2 + scenario-map.json.
2. Write `skills/hc-scaffold-service/evals/triggers.json` per §2.3.
3. Wire `task test:evals:sync` and `task test:evals:check`.
4. Run sync; commit generated evals.json + map + triggers.

**Commit:** `test: add evals.json sync and trigger cases`

*Done when:* `task test:evals:check` passes after sync; evals exist under the skill directory.

### T7 — CLAUDE.md + README.md

Document:

- Install go-task
- After skill edits: `task test` (guards + tier1 compare)
- Before merge: `task test:compare`
- skill-creator: `task test:skill-creator:install` then paste prompts from eval/triggers tasks
- Link this doc and [skill-vs-baseline.md](skill-vs-baseline.md)

**Commit:** `docs: document task-based testing and skill-creator hybrid`

*Done when:* README and CLAUDE.md contain working `task` examples and no longer tell users to run raw `run.sh --compare` as the primary path.

### T8 — Smoke (optional but recommended)

Run `task test:guards` and one paired smoke (`task test:compare:tests TESTS=<one-tier1-name>` or `task test:compare:tier1` if affordable). Fix breakages. Do **not** require committing large transcripts; gitignore `test/workspace/**/transcript.jsonl` if needed, but allow committing a tiny smoke benchmark if useful.

**Commit (only if code/docs change):** `fix: smoke paired compare wiring`

*Done when:* smoke proves no-skill + with-skill + benchmark path works, or issues filed as follow-ups in maintaining.md (prefer fix).

---

## 5. Out of scope

- Live Backstage for all evals
- Full tier-2/3 compare matrix in this change set
- Headless skill-creator plugin automation
- Changing SKILL.md behavior except description fixes proven by trigger evals (optional follow-up)
- Replacing mechanical `expectations` with LLM-only grading

---

## 6. Done when (whole plan)

- [ ] `Taskfile.yml` exists; `task --list` shows §3 tasks
- [ ] Docs listed in §0 / T1 / T7 are Task-first and consistent with hybrid
- [ ] `--no-skill` / `task test:scenario:no-skill` does not install the skill
- [ ] Fair prompts on without-skill arm
- [ ] Scenarios have labels + `expected_output`
- [ ] Paired compare writes §2.4 workspace + §2.7 `benchmark.json`
- [ ] `skills/hc-scaffold-service/evals/evals.json` + `triggers.json` + sync/check tasks
- [ ] `task test:diff` works on two benchmark files
- [ ] Atomic commits exist per T1–T7 (and T8 if used)

---

## 7. Stop conditions / ask the human

Stop and ask only if:

- ai-tdd rejects `skills.none.test.yaml` shape and there is no obvious disable flag
- docker/`ai-tdd:latest` cannot run in the environment and a documented local substitute is required

Otherwise implement as written.
