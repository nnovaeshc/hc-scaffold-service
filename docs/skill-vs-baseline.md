# Skill vs no-skill A/B testing infrastructure

Imperative plan to build continuous skill-vs-baseline comparison. Same voice as [implementation-plan.md](implementation-plan.md): decisions are settled; do not reopen them.

**This document plans infrastructure and docs.** Implementing it does **not** require executing a full `--compare` run or committing populated metrics. Operators run compares later.

Related: [testing.md](testing.md), [maintaining.md](maintaining.md), [CLAUDE.md](../CLAUDE.md), [README.md](../README.md).

## 1. Goal

Build harness support so skill usefulness is measured by pairing the **same** sandbox scenarios **with** the skill and **without** it.

Ship:

- Working `--compare` (and filters) on `test/run.sh`
- Labels on scenario YAML files (sole classification source)
- Stable report generator + shape validation + diff helper
- Updates to `CLAUDE.md` and `README.md` for how/when to run A/B

**Measurement (settled):** for each selected scenario, report (1) oracle pass/fail delta and (2) metrics from `runs.jsonl`: questions, turns, tokens, cost, duration. Pass/fail is primary; metrics explain cost/efficiency.

```mermaid
flowchart TD
  yaml["scenarios/*.yaml labels"]
  filters["--tier --type --feature --tests"]
  select[Intersect]
  armA[no skill]
  armB[with skill]
  report[Stable report]
  yaml --> select
  filters --> select
  select --> armA
  select --> armB
  armA --> report
  armB --> report
```

## 2. Useful vs not useful for compare

**Useful for compare:** any scenario file with `compare: true`. Discover the set by reading `test/scenarios/*.yaml` or `./test/run.sh --list-compare`. **MUST NOT** maintain a living inventory table in docs (it drifts).

**Not useful for compare** (remain package/process gates; never selected by `--compare`):

- Grep genericity guard over `skills/hc-scaffold-service/`
- `SKILL.md` line-budget gate (`wc -l` ≤ 400)
- Stub `STUB_SCENARIO` modes as standalone tests
- Oracle unit checks on hand-made transcripts
- T8-style one-time baseline recording for rationalization authoring
- Implementation-plan T11–T15 process (prod verify, live run, docs refresh, Jira)
- Advisory LLM judge as the sole gate

Expected v1: all current files under `test/scenarios/` are `compare: true` (13 scenarios).

## 3. Labels live on the tests

**Required place:** `test/scenarios/*.yaml`. The harness reads labels at runtime.

Each compare scenario YAML **MUST** include:

```yaml
name: preflight-empty-catalog       # test id; MUST match filename basename (no .yaml)
description: Empty catalog fail-fast
compare: true                       # false/omit => excluded from A/B
tier: 1                             # 1 cheap/fail-fast … 3 complex
type: preflight                     # preflight | discipline | interview
feature: fail-fast                  # finer behavior label
stub_scenario: empty_catalog
prompt: Create a new service
# optional compare_prompt: "..."    # fair no-skill prompt if needed
expectations:
  - question_count: 0
```

| Field | Role |
|-------|------|
| `name` | Test id for `--tests`; equals file basename |
| `tier` | Cost/depth for `--tier` |
| `type` | Broad class for `--type` |
| `feature` | Behavior under test for `--feature` |
| `compare` | Opt-in to A/B suite |

### Vocabulary

- **`tier`:** `1` = fail-fast/cheap; `2` = medium discipline; `3` = complex interview/schema.
- **`type`:** `preflight` | `discipline` | `interview`.
- **`feature`:** `fail-fast` | `confirmation` | `template-discovery` | `schema-walk` | `no-resubmit` | `secrets-refusal` | `capability-matching` | `inference` | `question-budget`.

### One-time label values (write into YAMLs once; do not copy into living docs)

When adding fields to existing scenarios, set:

- **Tier 1 / type `preflight` / feature `fail-fast`:** `preflight-no-capabilities`, `preflight-denied-call`, `preflight-empty-catalog`, `preflight-catalog-only`
- **Tier 2 / type `discipline`:** `nonexistent-template` (`template-discovery`), `secrets-template` (`secrets-refusal`), `task-failure` (`no-resubmit`), `prefixed-tool-names` (`capability-matching`), `time-pressure` (`confirmation`)
- **Tier 3 / type `interview`:** `plain-request` (`question-budget`), `under-specified-request` (`inference`), `conditional-template` (`schema-walk`), `synthetic-tenth` (`schema-walk`)

After that, inventory = the YAML files + `./test/run.sh --list-compare`.

### Fair prompts

Several scenarios currently start prompts with `/hc-scaffold-service`. That slash is not a real skill invoke when the skill is absent. For the no-skill arm the runner **MUST** use a fair prompt: strip a leading `/hc-scaffold-service` or use optional `compare_prompt` from the YAML. Same `stub_scenario` and `expectations` for both arms.

## 4. CLI

Primary entry: `./test/run.sh --compare`. Filters **combine with AND** (intersection). Empty intersection → exit non-zero with a clear error listing the filters.

```bash
./test/run.sh --compare
./test/run.sh --compare --tier 1
./test/run.sh --compare --tier 1,2
./test/run.sh --compare --tier 1 --tests preflight-empty-catalog,preflight-denied-call
./test/run.sh --compare --type preflight
./test/run.sh --compare --feature fail-fast,confirmation
./test/run.sh --compare --tier 2 --type discipline
./test/run.sh --list-compare
```

| Flag | Accepts | Meaning |
|------|---------|---------|
| `--compare` | flag | Pair no-skill then with-skill; write report |
| `--tier` | comma-separated ints | YAML `tier` ∈ set |
| `--type` | comma-separated | YAML `type` ∈ set |
| `--feature` | comma-separated | YAML `feature` ∈ set |
| `--tests` | comma-separated `name`s | YAML `name` ∈ set (must be `compare: true`) |
| `--list-compare` | flag | Print `name tier type feature` from YAMLs; no runs |
| `--no-skill` / `--without-skill` | flag | Single-arm baseline only (no pair, no compare report) |
| `--model` / `--effort` | as today | Applied to both arms when comparing |

`--tests` may use scenario file basenames without `.yaml`. Unknown `--tests` / `--type` / `--feature` values → hard fail.

**After any change under `skills/hc-scaffold-service/`:**

- Minimum: `./test/run.sh --compare --tier 1`
- Before treating the change as done for merge/release: `./test/run.sh --compare` (all compare scenarios)

Report metadata **MUST** record the effective `filters` and the exact sorted list of scenario `name`s executed so two runs with the same filters remain comparable.

## 5. What to build

### 5.1 Harness: no-skill arm

Today `test/run.sh` parses `--no-skill` but does **not** disable skill install in docker. `docs/testing.md` may say `--without-skill`.

**MUST:**

1. Add `test/skills.none.test.yaml` (no local skill installed).
2. When `--no-skill` or `--without-skill`: set `SKILLS_TEMPLATE` to that file; do not enable `hc-scaffold-service`.
3. Accept `--without-skill` as an alias of `--no-skill`.

### 5.2 Harness: compare mode + filters

**MUST:**

1. Add `compare`, `tier`, `type`, `feature` (and aligned `name`) on all compare scenario YAMLs.
2. Implement `--compare` with `--tier` / `--type` / `--feature` / `--tests` AND semantics.
3. Implement `--list-compare`.
4. For each selected scenario: run no-skill arm then with-skill arm (same model/effort), then generate the report for the **selected** set only (canonical sort by `name`).
5. Package guards (grep / line budget): run once when the skill is present; skip on pure `--no-skill` runs; **not** part of the per-scenario A/B delta.
6. Each `runs.jsonl` row **MUST** include: `skill_installed`, `name`, `tier`, `type`, `feature`, model (actual from transcript), effort, tokens, cost, duration, question/turn counts, pass/fail, assertion failures, skill git SHA.

### 5.3 Report generator + shape stability

Outputs when an operator runs `--compare` (not required during infra implementation):

- `test/results/compare-<UTC>-<skill-sha>.md` — human summary
- Append one JSON object per compare **run** to `test/results/compare.jsonl` (embed a `scenarios` array; do not emit one top-level line per scenario alone)

Per scenario: both arms’ pass/fail + metrics + deltas (`improved` / `worsened` / `unchanged`).

Large transcripts stay gitignored. Summary markdown/jsonl may be committed when someone wants history.

#### Making successive reports comparable

Model runs are non-deterministic: two compares will **not** produce identical pass/fail or token numbers. Guarantees are **structural** and **input-control** only.

**Stable shape (same every run for a given filter set):**

1. `schema_version` on every report (start at `1`; bump only when columns/sections change).
2. Fixed markdown template — same headings and table columns every time. Missing values are `null` / `—`; never drop columns.
3. Canonical scenario order — alphabetical by `name` within the selection.
4. Fixed column set, for example:  
   `scenario | tier | type | feature | no_skill_pass | with_skill_pass | pass_delta | q_no | q_yes | q_delta | tokens_no | tokens_yes | tokens_delta | cost_no | cost_yes | turns_no | turns_yes`
5. Metadata block first (same keys every time): `schema_version`, `skill_sha`, `claude_code_version`, `model`, `effort`, `filters`, sorted `scenarios`, `started_at`, `finished_at`, `run_id`, repo/harness commit SHA.
6. `compare.jsonl` uses the same keys as the markdown tables.

**Controlled variables:**

| Control | Rule |
|---------|------|
| Scenario set | Derived only from YAML labels + CLI filters; record exact set in metadata |
| Prompts | Fair-prompt function is pure/deterministic |
| Stub | `stub_scenario` from YAML; record fixture/repo SHA in metadata |
| Model / effort | Same on both arms; record actual model from transcript |
| Skill SHA | With-skill arm records SHA; no-skill records `skill_installed: false` |

**Validate on write:** `test/fixtures/compare-report.schema.json`. Fail `--compare` if the generated report shape drifts. Do **not** assert metric equality.

**Diff helper:** `test/assertions/diff_compare.py` compares two reports and surfaces schema mismatch, filter/scenario-set mismatch, model/effort mismatch, pass/fail flips, and advisory metric drift. Do not fail the build on metric noise by default.

```bash
python3 test/assertions/diff_compare.py \
  test/results/compare-AAA.md \
  test/results/compare-BBB.md
```

### 5.4 CLAUDE.md and README.md

**CLAUDE.md** — short section:

- After any change under `skills/hc-scaffold-service/`, run A/B before considering the change done
- Minimum: `./test/run.sh --compare --tier 1`
- Full: `./test/run.sh --compare`
- Pointer to this document

**README.md** — contributor-facing:

- What A/B means (skill vs unaided model on the same scenarios)
- When to run (after skill changes; optional usefulness snapshot anytime)
- How: `--compare` examples including `--tier` / `--type` / `--feature` / `--tests`
- Links to this document and [testing.md](testing.md)

Also add one-line cross-links from [testing.md](testing.md) and [maintaining.md](maintaining.md) to this document.

## 6. Out of scope

- Executing `--compare` or committing a populated metrics report as part of building the infra
- Changing skill content to chase scores
- Production live A/B
- Multi-model matrix (keep `--model` / `--effort` flags only)

## 7. Implementation order

Execute in order. Follow atomic commits (one logical deliverable per commit).

1. **This document is already the spec** — next commits implement harness/docs below (do not rewrite this file into an inventory table).
2. Label all scenario YAMLs (`compare`, `tier`, `type`, `feature`, aligned `name`). Commit: `test: add compare tier type feature labels to scenarios`
3. Add `test/skills.none.test.yaml`; fix `--no-skill` / `--without-skill` wiring; fair prompts. Commit: `test: honor --no-skill with skills.none template`
4. Implement `--compare`, filters, `--list-compare`, report generator, schema fixture, `diff_compare.py`, `runs.jsonl` fields. Commit(s): `test: add --compare with filters and stable reports` (split if large).
5. Update `CLAUDE.md`, `README.md`, [testing.md](testing.md), [maintaining.md](maintaining.md). Commit: `docs: document how and when to run skill vs baseline A/B`

## 8. Done when

- Scenario YAMLs carry labels; `--list-compare` prints them
- `--no-skill` actually runs without the skill installed
- `--compare` with `--tier` / `--type` / `--feature` / `--tests` selects the intersection and writes a schema-valid report
- `CLAUDE.md` and `README.md` state how/when to run A/B
- No living scenario classification table exists in docs
