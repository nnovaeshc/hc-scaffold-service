# CLAUDE.md

Agent entry point for implementing and maintaining hc-scaffold-service.

## Implementation plan

Follow [docs/implementation-plan.md](docs/implementation-plan.md) as the source of truth for build order, requirements, and task sequence.

## Atomic commits (mandatory)

Make many small commits:
- One task, feature, or test per commit
- One logical change per commit
- Commit a finished task before starting the next task
- Never squash the work into one giant commit at the end

## Testing

Install [Task](https://taskfile.dev/installation/) (`brew install go-task`) once; it is the only documented way to run the harness.

- After any change under `skills/hc-scaffold-service/`: `task test` (guards + tier-1 compare) minimum.
- Before treating a change as done for merge/release: `task test:compare` (full paired A/B).
- After adding or editing a scenario: `task test:evals:sync`; CI checks drift with `task test:evals:check`.
- skill-creator (trigger/description tuning, interactive only): `task test:skill-creator:install`, then paste the prompt from `task test:skill-creator:eval` or `task test:skill-creator:triggers`.

See [docs/align-tests-skill-creator.md](docs/align-tests-skill-creator.md) for the full task list and artifact schemas, and [docs/skill-vs-baseline.md](docs/skill-vs-baseline.md) for the compare CLI and A/B measurement design.

## Key documentation

- [docs/implementation-plan.md](docs/implementation-plan.md) — build order and requirements
- [docs/design.md](docs/design.md) — architecture and decision record
- [docs/testing.md](docs/testing.md) — test harness architecture
- [docs/align-tests-skill-creator.md](docs/align-tests-skill-creator.md) — Taskfile tasks and workspace/benchmark.json schemas
- [docs/skill-vs-baseline.md](docs/skill-vs-baseline.md) — skill-vs-baseline A/B comparison
- [docs/maintaining.md](docs/maintaining.md) — how to change the skill safely
- [docs/usage.md](docs/usage.md) — user walkthrough and troubleshooting
- [README.md](README.md) — user-facing entry point
