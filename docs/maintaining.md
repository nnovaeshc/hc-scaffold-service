# Maintaining

Maintainer-facing. How to change this skill without breaking the properties it was built for. Read [design.md](design.md) first — particularly the decision record, which explains why things are the way they are.

## Agent entry and build order

Until implementation is finished, [implementation-plan.md](implementation-plan.md) is the source of truth for build order. [CLAUDE.md](../CLAUDE.md) (created as plan task T1) points agents there. Testing-harness build order and schemas specifically live in [align-tests-skill-creator.md](align-tests-skill-creator.md).

**Atomic commits are mandatory** for implementers and maintainers evolving this repo: one task / feature / test per commit; one logical change per commit; commit before starting the next task; never squash a green task into a later mega-commit. See §2 of the implementation plan.

## What you are editing

The shipped artifact is the directory `skills/hc-scaffold-service/` — three files with progressive disclosure:

- `SKILL.md` — always-on iron rules, checklist, fail-fast, NEVER/ALWAYS, rationalizations
- `reference.md` — schema dialect, precedence detail, `ui:field` recipes, query shapes, links matrix
- `examples.md` — review-table shape, fail-fast message templates, synthetic ask sequence

Everything else in this repo is packaging, tests or documentation. A change to any of those three files is a behaviour change with no compiler to catch you, which is why the guards below exist. Prefer fixing failures by tightening a NEVER or adding a rationalization row in `SKILL.md`; put schema prose in `reference.md`, not in `SKILL.md`. Keep `SKILL.md` ≤400 lines (`wc -l`).

Do not add `commands/`, phase slash commands, or `agents/` / `context: fork` for the main path.

## The guards

**The grep guard.** No file under `skills/hc-scaffold-service/` may contain a template name, environment name, AWS account number, or team name. `run.sh` scans the **entire skill directory except `evals/`** and a hit fails the build.

Naming real templates in these docs is fine and useful — the constraint is about what the skill *knows*, not what maintainers can write down. Examples and references inside the skill must use synthetic field shapes only. `evals/` is exempt for the same reason `test/fixtures/` is: `evals.json` is generated from `test/scenarios/*.yaml`, whose prompts legitimately reference real templates for testing purposes — that is test data, not skill instruction content.

**The line-budget gate.** `wc -l skills/hc-scaffold-service/SKILL.md` must be ≤ 400. Failures that tempt you to paste schema walk into `SKILL.md` belong in `reference.md` instead.

**The synthetic template.** `test/fixtures/templates/synthetic-tenth.yaml` combines supported schema constructs in shapes no real template uses. If the skill only works on templates someone looked at while writing it, this scenario fails.

These guards exist because genericity degrades invisibly. Nothing breaks the day someone adds a template-specific rule; it breaks months later on a template nobody anticipated.

## Making a change

1. **Write the failing scenario first.** Add it to `test/scenarios/` (with `compare`/`tier`/`type`/`feature`/`expected_output` — see [align-tests-skill-creator.md](align-tests-skill-creator.md) §2.1) and run `task test:scenario:no-skill` to see how the model behaves unaided. If it already does the right thing, you do not need a rule. **Commit** the scenario (and baseline recording) before editing the skill.
2. **Record the failure verbatim** in `test/baseline/`.
3. **Change the skill package.** Prefer a NEVER/ALWAYS tighten or a rationalization row in `SKILL.md`. Put dialect detail in `reference.md`. Phrase constraints as absolute rules — hedged guidance gets rationalized away under pressure. **Commit** the skill change separately from the scenario commit.
4. **Add the rationalization** to the table in `SKILL.md`, quoting the reasoning the model actually used. Naming the specific excuse is what makes the rule stick.
5. **Run `task test`** (guards + tier-1 compare) as a minimum gate. Confirm the grep guard and `SKILL.md` line budget still pass. Then **ask the user before running `task test:compare`** (full paired A/B) and recommend it, explaining why: a rule that fixes one scenario can loosen another, and only the paired run shows that. It is also expensive — every scenario runs twice through a live model, hundreds of thousands of tokens per iteration — so the user may have a good reason to skip it (the change is docs-only, touches no skill file, or a recent iteration already covers the affected scenarios). Their call, but make the tradeoff explicit rather than either running it silently or quietly skipping it.
6. **Check the benchmark.** Every paired run writes `timing.json` / `grading.json` per arm, rolled up into `test/workspace/iteration-<N>/benchmark.json`. Compare against the previous iteration with `task test:diff A=... B=...`: a rule that passes but doubles token usage is worth knowing about, and a suite that only passes on the largest model with maximum thinking is a fragile result rather than a green one.
7. **Keep evals in sync.** Run `task test:evals:sync` so `skills/hc-scaffold-service/evals/evals.json` reflects the new/changed scenario; `task test:evals:check` fails CI on drift.
8. **Re-run skill-creator triggers when activation wording changes.** The harness does not grade whether the skill auto-activates. If you edited the frontmatter `description`, changed `evals/triggers.json`, or synced phrases from the live catalog, ask the user to run the interactive skill-creator triggers pass (`task test:skill-creator:install` then `task test:skill-creator:triggers`). Skip when only skill body / harness / docs changed. Details: [triggers.md](triggers.md).

## When a rule keeps getting rationalized

If the model works around a rule across several runs, the rule is not strong enough or is competing with something else. Reach for these in order: make it absolute rather than advisory; name the specific rationalization in the table; move it earlier, since rules stated late read as afterthoughts; and check whether another instruction is pulling the other way, such as brevity guidance competing with a required review step.

Adding words rarely helps. Naming the excuse usually does.

## What not to add

The decision record in [design.md](design.md) explains each of these. In short, these will be tempting and are all mistakes:

- **Per-template special cases.** If a rule can only be expressed by naming a template, the rule is wrong.
- **Business rules.** Team-to-account maps, company mappings, privilege orderings. Use catalog precedent instead: query what similar entities already do. It self-updates; a hardcoded map rots.
- **Knowledge of custom field extensions.** Teaching the skill what a custom widget expects duplicates knowledge that lives in Backstage and drifts when Backstage changes.
- **Hardcoded MCP tool names.** Match by capability. Names change with gateway prefixing and with the `namespacedToolNames` flag, neither of which we control.
- **A degraded path when Backstage is unreachable.** The skill stops. Guessing template names or hand-rolling files is worse than failing.
- **Auto-retry after a failed task.** Earlier steps have side effects; a retry duplicates repositories and pull requests.

## Drift to watch

**Backstage upgrades** can change tool names, add tools, or change schema handling. The `prefixed_tool_names` scenario covers renaming. A genuinely new capability — a resolved-schema tool, a single-task-status tool, a `templateRef`-accepting dry run — would each simplify the skill materially and is worth acting on:

- a resolved-schema tool would remove raw `ui:` interpretation
- a single-task-status tool would remove log polling
- a dry run accepting a `templateRef` would allow pre-validation before submission

**New schema constructs** in real templates. If a template uses something the five rules do not cover, extend the rules generically and add the construct to the synthetic template. Do not special-case the template.

**Constraint keywords are enforced from the schema, never hardcoded.** Validation (`reference.md` → Constraint Validation) is driven only by the keywords a template declares — `pattern`, lengths, bounds, item counts, `enum`. A template registered tomorrow is validated by the same rules. Do not add a per-template or per-field validation rule, and do not teach the skill naming conventions: an invented constraint rejects legal values on templates nobody has seen yet, which is the failure the genericity guards exist to catch. When a real template uses a keyword the table does not cover, add the keyword generically and add it to `synthetic-tenth.yaml`.

**The sandbox image** (`healthcarecom/healthcare-images`, `ai/ai-tdd/latest`) can change its config contract. The harness depends on `MCP_SERVERS_TEMPLATE`, `SKILLS_TEMPLATE`, `CLAUDE_CONFIG_DIR`, and local skills being copied to `${CLAUDE_CONFIG_DIR}/skills/<name>/`.

**Claude Code plugin format.** Packaging follows the upstream plugin format plus the contract in `healthcarecom/ai-config` `docs/plugin-format.md`, which requires `.claude-plugin/plugin.json` with `name` matching the directory.

## Migrating to ai-config

This repo is a personal-namespace staging ground. The eventual home is `healthcarecom/ai-config` under `claude-code-plugins/hc-scaffold-service/`.

`metadata.yaml` is already written to that repo's schema, so migration is mostly a move plus a catalog entry in that repo's `.claude-plugin/marketplace.json`. That repo's CI enforces bidirectional consistency between plugin directories and catalog entries, and `plugin.json`'s `name` must equal the directory name. Validate locally before opening the PR:

```bash
uv --project tools run ai-config validate-plugins
```

The `test/` directory does not belong in `ai-config` as-is. Decide at migration time whether it moves, stays here, or is rehomed as CI.

## Open items

**Background task following.** After submitting, the engineer chooses to watch or to check later; there is no unattended notification. The blocker is authentication: the gateway authenticates per user through browser OAuth, so a detached poller has no credential. Solving it needs a token-bearing path, not a skill change.

**Shared-identity attribution.** Backstage attributes actions to a shared `mcp-gateway` principal. Accepted deliberately. Fixing it means making the `backstage-auth-header` middleware carry per-user identity, which is infrastructure work outside this repo.
