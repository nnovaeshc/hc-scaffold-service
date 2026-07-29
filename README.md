# hc-scaffold-service

Create a new service from a Backstage software template by describing what you want, without opening the Backstage UI or learning the scaffolder API.

## What it does

You say what you want to build. The skill finds a matching template, works out as many of its settings as it can from your repository context and the Backstage catalog, asks you about the parts that need a human decision, shows you everything before submitting, and then reports what was created.

The Backstage web form for a service template can have eighteen fields. Most of them have a correct answer that can be looked up or derived. This skill exists so you only think about the handful that genuinely need you.

It creates nothing by itself. Every action runs through Backstage, which remains the system of record, and nothing is submitted without your explicit confirmation.

## Prerequisites

**Claude Code or Claude Desktop.** This skill is not available in the Backstage UI or any other client.

**Access to the Backstage MCP server.** Add it once:

```bash
claude mcp add --transport http backstage \
  https://mcp-gateway.platform.healthcare.com/api/mcp-actions/v1
```

Authentication happens in your browser on first use, through Okta. If you can log into Backstage, you can use this.

## Install

```bash
claude plugin marketplace add nnovaeshc/hc-scaffold-service
claude plugin install hc-scaffold-service@hc-scaffold-service-marketplace
```

## Use it

Just describe what you need:

```
I need a new Spring Boot service for handling quote callbacks
```

Or invoke it explicitly:

```
/hc-scaffold-service
```

See [docs/usage.md](docs/usage.md) for a full walkthrough, what the review step shows you, and what to do when something fails.

## Known limitations

**Backstage records the action against a shared service account.** Because of how the MCP gateway authenticates, Backstage attributes what you create to a generic `mcp-gateway` identity rather than to you personally. Everything is created correctly; only the audit attribution is generic. Use the Backstage UI if you need the record to carry your name.

**Templates that require secrets are refused.** A handful of templates ask for credentials. Those are redirected to the Backstage UI, because a secret typed into a chat would pass through the model. This is deliberate.

**Long-running tasks do not follow you around.** After submitting, you are offered the choice to watch progress or to take the task URL and check later. There is no background notification when a task finishes.

## Documentation

- [docs/usage.md](docs/usage.md) — walkthrough and troubleshooting, for users
- [docs/design.md](docs/design.md) — architecture and the full decision record, for maintainers
- [docs/testing.md](docs/testing.md) — how the test harness works, for maintainers
- [docs/skill-vs-baseline.md](docs/skill-vs-baseline.md) — skill-vs-baseline A/B comparison, for maintainers
- [docs/align-tests-skill-creator.md](docs/align-tests-skill-creator.md) — Taskfile tasks and workspace/benchmark.json schemas, for maintainers
- [docs/maintaining.md](docs/maintaining.md) — how to change the skill safely, for maintainers
- [docs/implementation-plan.md](docs/implementation-plan.md) — the build plan, until it is done
- [CLAUDE.md](CLAUDE.md) — agent entry point (created by the implementer as the first plan task)

## Contributing / implementing

**Atomic commits are mandatory.** Contributors and implementing agents MUST make many small commits: one task, feature, or test per commit; one logical change per commit; commit a finished task before starting the next; never squash the work into one giant commit at the end.

Build order and the full commit rule live in [docs/implementation-plan.md](docs/implementation-plan.md). Agents MUST follow [CLAUDE.md](CLAUDE.md) (once present) and that plan — do not invent a different sequence.

**Skill changes are verified by tests, because a prompt has no compiler.** Anthropic's guidance on [authoring](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) and [evaluating](https://code.claude.com/docs/en/skills#evaluate-and-iterate-on-a-skill) skills is evaluation-first and ships no runner for the loop it describes, so `test/` is ours. The suite carries one scenario per behavioural claim the skill makes, each recorded failing without the skill before the rule that fixes it is written. Add a claim and you add a scenario; that is where the size of `test/` comes from.

[docs/testing.md](docs/testing.md) has the full rationale and the harness architecture.

**Running the harness.** Install [Task](https://taskfile.dev/installation/) (`brew install go-task`); it is the only documented entry point.

```bash
task test                    # guards + cheap tier-1 paired compare (skill vs unaided model)
task test:compare            # full paired A/B across all compare scenarios
task test:compare:tier TIER=1,2
task test:compare:type TYPE=preflight
task test:compare:tests TESTS=plain-request,time-pressure
```

This is "skill vs baseline": the same scenario run once with `hc-scaffold-service` installed and once without, so a change's actual effect is measured rather than assumed. Run the minimum after any skill edit; run the full compare before merge. See [docs/skill-vs-baseline.md](docs/skill-vs-baseline.md) and [docs/align-tests-skill-creator.md](docs/align-tests-skill-creator.md) for the full CLI, the workspace/`benchmark.json` layout the compare writes, and the skill-creator hybrid (`task test:skill-creator:*`) for trigger/description tuning.