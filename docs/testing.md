# Testing

Maintainer-facing. How the harness is built and how to extend it.

## The problem

The artifact under test is a prompt, and the system under test is a model. Behaviour is non-deterministic, so the usual approach of asserting on return values does not apply. Two decisions make it tractable.

**Assert on tool calls, not prose.** Nearly everything worth checking is mechanically observable in what the skill *did*: which tools it called, in what order, with what arguments, and what payload it finally submitted. Wording varies run to run; tool calls do not.

**Read the client transcript, never the server.** `claude -p --output-format stream-json` emits every `tool_use` block with its full input. Assertions read that. This is why the same suite runs unchanged against the stub and against production — assertions coupled to a stub's recording would only ever work against the stub.

## Layout

```
test/
├── docker-compose.yaml      # runs ai-tdd:latest with the repo mounted at /work
├── mcp-servers.test.yaml    # the stub as the only enabled MCP server
├── skills.test.yaml         # installs the skill from the mounted repo
├── stub/server.py           # stdio MCP fixture server
├── fixtures/
│   ├── templates/           # 9 real templates + 1 synthetic
│   ├── groups/              # catalog Group entities
│   └── task-logs/           # success and mid-run-failure log sequences
├── scenarios/               # one file per scenario: prompt + expectations
├── assertions/check.py      # the transcript oracle
├── baseline/                # recorded failures from running without the skill
├── results/runs.jsonl       # one record per run: model, effort, tokens, cost
└── run.sh
```

## The sandbox

The harness runs inside `ai-tdd:latest`, built from `healthcarecom/healthcare-images` at `ai/ai-tdd/latest`. It is **built locally**, not pulled from a registry. The image already pins Claude Code and sets `CLAUDE_CODE_USE_BEDROCK=1` and `AWS_REGION=us-east-1`, so there is no Dockerfile here.

Two environment variables do all the wiring, so nothing needs rebuilding and nothing is mounted over a baked-in path:

- `MCP_SERVERS_TEMPLATE` → `/work/test/mcp-servers.test.yaml`
- `SKILLS_TEMPLATE` → `/work/test/skills.test.yaml`

The container entrypoint reads both on every start. It merges MCP servers into `${CLAUDE_CONFIG_DIR}/.claude.json`, and copies each local skill **directory** (`shutil.copytree`) to `${CLAUDE_CONFIG_DIR}/skills/<name>/`, which is why `skills/hc-scaffold-service/` — including `SKILL.md`, `reference.md`, and `examples.md` — is the correct repo layout.

Two things to know or the container will not start. The MCP config validator fails if any declared `secret_vars` entry is empty, so **the stub declares none**. And the image's default `github` and `atlassian` servers are explicitly disabled here, so the sandbox needs no real credentials.

## The stub

A stdio JSON-RPC server handling `initialize`, `tools/list` and `tools/call`, standard library only. It serves fixtures and has **no test responsibility** — it makes no assertions and records nothing. Transport is stdio rather than production's HTTP because the skill cannot observe transport; only tool names and schemas reach it.

Behaviour is selected by `STUB_SCENARIO`, so failure cases are fixture sets rather than code paths:

- `default` — all ten templates, healthy
- `empty_catalog` — the Template query returns nothing
- `denied_first_call` — healthy `tools/list`, authorization error on the first catalog call
- `no_backstage_tools` — `tools/list` returns unrelated tools only
- `catalog_only` — catalog capability present, scaffolder capability absent
- `task_failure` — submission succeeds, logs show a mid-run failure with earlier steps already successful
- `prefixed_tool_names` — healthy, but every tool name carries a gateway-style prefix

The last one is load-bearing. The real tool names through the gateway depend on config we do not own, so this scenario proves capability matching works rather than assuming it.

## Fixtures

Nine real templates from `healthcarecom/platform-backstage-templates`, taken from the nine registered in `all-templates.yaml`. Note that `argocd-app` exists as a directory in that repo but is **not registered**, so it never reaches the catalog and is deliberately absent here.

The tenth, `synthetic-tenth.yaml`, is written by hand and is the genericity proof. It combines supported constructs in shapes none of the real templates use: a conditional gating a required field, a `$ref` into `definitions`, a positional-tuple array, an `enum` with no `enumNames`, an unrecognised `ui:field`, a required field with neither default nor enum, an unrecognised key nested in a property, and a two-page parameter structure. Its outputs declare a pull request only, no repository.

When a real template starts using a construct the synthetic one does not cover, extend the synthetic one.

## Running

```bash
cd test && ./run.sh              # all scenarios, with the skill
./run.sh --without-skill         # baseline: how the model behaves unaided
./run.sh --scenario time-pressure
./run.sh --model <slug>          # override the model; recorded in results
```

`run.sh` also runs the package guards: a grep genericity scan over **all files** under `skills/hc-scaffold-service/`, and a `wc -l` line-budget check on `SKILL.md` (≤400). Those are part of the suite, not separate steps.

## Red first

Every scenario is run **without** the skill before it is run with it, and the failures are recorded verbatim in `test/baseline/`. This is not ceremony. The rationalization table in `SKILL.md` is built from those recorded failures, so the rules address how the model actually goes wrong rather than how we imagine it might.

If you add a rule without a corresponding observed failure, you are guessing.

## Assertions available

From `assertions/check.py`, driven declaratively by each scenario file:

- a named tool was or was not called
- call ordering, for example that a `Group` query precedes submission
- every catalog query carries both `fields` and `limit`, which is how context budgeting is enforced
- a JSON path within the submitted `values` equals an expected value
- a named key is **absent** from the submitted `values`, which is how conditionally hidden fields are checked
- question count at or below a bound
- zero questions asked and no tool calls after a failing one, which is how fail-fast is checked
- a tool called at most N times, which is how "no auto-resubmit" is checked
- the largest single `tool_result` payload at or below a byte ceiling, which is the direct test of context budgeting
- total fresh input tokens at or below a per-scenario ceiling

An advisory LLM judge covers the one thing with no mechanical trace: whether an inference was *explained* rather than silently applied. It reports and never fails the build alone.

## Measurement

Every run appends one JSON object to `test/results/runs.jsonl`. A green suite is meaningless without knowing what produced it: the same prompt on a smaller model, or with less thinking budget, is a different experiment.

Recorded per run:

- **model actually used**, read from `message.model` in the transcript rather than from what was requested — a request can be silently substituted, and the substitution is exactly what you want to catch
- **thinking or effort configuration** in force
- **token counts**: `input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`
- **cost, wall-clock duration, and turn count**
- **Claude Code version, the skill's git commit SHA**, the stub scenario, and whether the skill was installed

That last group is what separates a reproducible result from an anecdote. A `runs.jsonl` entry without a version and a SHA cannot be compared against anything later.

Two different jobs here, and they should not be confused. The **byte ceiling on `tool_result` payloads is the deterministic gate** — it is independent of tokenizer and caching behaviour, so it fails only when the skill genuinely fetched too much. **Token counts are a trend and cost record**, with a deliberately generous ceiling as a regression tripwire; a tight bound would produce false failures every time caching behaviour or the model changes.

The runner takes the model as a parameter, so key scenarios can be run across models to find out which ones the skill actually works on. There is no matrix runner and there does not need to be one — the point is that the model is never hardcoded, so adding a matrix later is a loop rather than a redesign.

## Adding a scenario

Write the prompt and its expectations in `test/scenarios/`. Run it without the skill first and record what happens. If it already passes unaided, it is not testing anything — either make the pressure real or drop it. Then run it with the skill and iterate.

**Commit the scenario (and baseline) before editing the skill.** Scenario files and skill package changes are separate commits — see [implementation-plan.md](implementation-plan.md) §2 and [maintaining.md](maintaining.md).

The scenarios that earn their place are the ones where a model naturally misbehaves: inventing a value instead of composing it from constraints, skipping the review under time pressure, assuming the owning team, hallucinating a template name rather than querying, resubmitting after a failure, and asking every question and thereby defeating the point.

## Production

Because assertions are client-side, the same scenarios can run against the real endpoint. Read-only scenarios are safe to repeat. Anything that submits creates real resources, so use a throwaway name and clean up.
