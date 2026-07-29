# Frontmatter / trigger evals

How we exercise when `hc-scaffold-service` should and should not activate.

## What exists

| Artifact | Role |
|----------|------|
| Skill frontmatter `description` in [`skills/hc-scaffold-service/SKILL.md`](../skills/hc-scaffold-service/SKILL.md) | What Claude Code uses to decide whether to offer/load the skill |
| [`skills/hc-scaffold-service/evals/triggers.json`](../skills/hc-scaffold-service/evals/triggers.json) | Hand-maintained `should_trigger` / `should_not_trigger` prompts for description tuning |
| `task test:skill-creator:triggers` | Prints the interactive skill-creator prompt (not headless) |

The stub harness (`task test:scenario`, `task test:compare`) does **not** grade triggering. It assumes the skill is installed (or not, for baseline) and scores tool-call behaviour after that. Trigger accuracy is a separate property — see [testing.md](testing.md). CI does not run skill-creator.

## When to re-run skill-creator triggers

**Re-run** (interactive Claude Code + skill-creator plugin) whenever any of these happen:

| Change | Why |
|--------|-----|
| Edit the YAML frontmatter `description` in `SKILL.md` | That string is the only auto-activation signal; wording drift changes who fires |
| Sync trigger phrases via `.claude/commands/scaffolder-update-frontmatter.md` (or any catalog-driven phrase merge) | New phrases can over-trigger unrelated “create …” requests |
| Edit `skills/hc-scaffold-service/evals/triggers.json` | The suite of should / should-not prompts changed; description must still match |
| Real use shows a false positive or false negative activation | Description and `triggers.json` need a new case and a retune |

**Do not** treat a green `task test` / `task test:compare` as covering triggers. Those prove post-activation behaviour only.

**Skip** a triggers re-run when the change does not touch activation wording, for example:

- Body of `SKILL.md` / `reference.md` / `examples.md` only (no frontmatter `description` edit)
- Harness, fixtures, scenarios, or assertions only (unless you also add/change rows in `triggers.json`)
- Docs-only changes outside the skill package

After a required retune, commit any resulting `description` (and `triggers.json`) edits with the skill change; note in the PR that triggers were re-checked interactively.

### Agents

If you edit frontmatter `description` or `triggers.json`, **stop and tell the user** that skill-creator triggers must be re-run interactively — you cannot grade triggers headlessly. Print the install + prompt via `task test:skill-creator:install` and `task test:skill-creator:triggers`. Do not claim the change is merge-ready for activation until the user confirms the interactive tune (or explicitly skips with a reason).

`task test:skill-creator:eval` (evals.json through skill-creator) is optional and **not** a substitute for the stub harness; use it only when someone wants a secondary interactive behavioural pass. Triggers re-runs are about `triggers.json` + `description`, not that eval prompt.

## Frontmatter phrases → cases

Current description (post skill-creator tune) uses **INVOKE FOR** / **SKIP** framing rather than a flat “Triggers on …” list. It still covers scaffold / create / spin-up of service, component, API, microservice, or Lambda from a template (including when the user never says “Backstage”), plus explicit `/hc-scaffold-service`.

| Frontmatter cue | Example in `should_trigger` |
|-----------------|-------------------------------|
| scaffold / Lambda | "Scaffold a Lambda API for me" |
| Backstage template | "I need a new service from a Backstage template" / springboot wording |
| create service | "Create a service for payment callbacks" |
| create component | "Create a component for our catalog" |
| new service from template | "I want a new service from template without opening the UI" |
| explicit invocation | `/hc-scaffold-service` and slash + task |

| Should **not** fire (`SKIP` / `should_not_trigger`) | Why |
|-----------------------------------------------------|-----|
| Refactor / trivia / dep bump | Unrelated engineering |
| Explain Backstage catalog | Mentions Backstage but is Q&A, not scaffold |
| "Create a React component in this frontend app" | Code change inside an existing app |
| docker compose / git remotes / unit tests | Ops or local-dev against existing services |

Keep `triggers.json` and this table aligned when you add phrases. Prefer adding a `should_not_trigger` case for every new broad verb (“create …”) you put in the description.

The catalog sync command (`.claude/commands/scaffolder-update-frontmatter.md`) merges new phrases into the **INVOKE FOR** clause; after that sync, re-run skill-creator triggers again.

## How to run

```bash
task test:skill-creator:install   # once, in Claude Code
task test:skill-creator:triggers  # copy the printed prompt
```

Paste into Claude Code with the skill-creator plugin loaded. Iterate on the frontmatter `description` until should-trigger cases fire and should-not-trigger cases do not.

## Gap (intentional for now)

No mechanical `test/scenarios/*.yaml` yet asserts "Skill tool was / was not invoked" for natural-language prompts. Adding that would need a harness expectation (e.g. skill activation in the transcript) and fair prompts without a leading slash. Tracked as a follow-up if interactive trigger evals are not enough.
