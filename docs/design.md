# Design

Maintainer-facing. This document explains what the skill is, how it works, and why it is built this way. The decision record in the second half exists so that decisions are not silently re-litigated or accidentally undone.

## What this is

A conversational interface to Backstage's scaffolder, driven through the Backstage MCP server. An engineer describes what they want to create; the skill finds a suitable software template, works out as many of its parameters as it can, asks about the rest, and submits.

**It is an interface, not an implementation.** The skill adds no scaffolding logic of its own. Every action goes through the MCP tools that `@backstage/plugin-mcp-actions-backend` exposes, and Backstage remains the only thing that creates anything. There is no wrapper API and no reimplementation of scaffolder behaviour.

Some published write-ups describe a different model, where a scaffolder returns generated files that the agent writes to disk and commits. That belongs to third-party standalone Backstage MCP servers. The official plugin publishes to GitHub server-side and returns only a task id. Do not build toward the other model.

## The MCP surface, and what it forces

The skill is shaped by what the tools actually offer. Four matter:

- `catalog.query-catalog-entities` — entity search. There is **no** `scaffolder.list-templates` tool, so template discovery is a catalog query for `kind: Template`.
- `catalog.get-catalog-entity` — one entity. There is **no** resolved-schema tool, so the skill reads raw `spec.parameters` off the Template entity, including the `ui:` keys the web form consumes.
- `scaffolder.execute-template` — submission. Returns `{ taskId }` and nothing else.
- `scaffolder.get-scaffolder-task-logs` — progress, with an `after` cursor. There is **no** single-task-status tool, so progress means reading logs.

Two further constraints:

`scaffolder.dry-run-template` exists but takes template YAML as a **string**, not a `templateRef`. It cannot pre-validate a template that lives in the catalog, so it is unused.

`scaffolder.execute-template` carries `secrets` in its LLM-visible input. Any template declaring secrets is therefore refused and redirected to the Backstage web form.

A task id is not success. For templates with external actions — creating a GitHub repository, opening a pull request against the GitOps repo — the real work completes well after the tool call returns.

## Genericity: the primary constraint

The skill must work on templates written after it ships, in organisations it has never seen. This is the single most important property, and the easiest to lose: it is very tempting to read the templates in front of you and encode their specifics.

The rule that keeps it honest: **if a behaviour can only be expressed by naming a template, it is a bug in the rule.** Real templates are a test corpus that proves which JSON Schema constructs must be supported. They are not a source of rules.

The skill is five rules:

1. **The schema is the form.** Walk `spec.parameters` pages in order, supporting standard JSON Schema plus Backstage's `ui:` conventions — `enum`/`enumNames`, `default`, `format`, `required`, `dependencies` with `allOf`/`if`/`then`, `$ref` with `definitions`, and `items` in both schema and positional-tuple form. This is not org-specific; it is the schema dialect Backstage uses.
2. **Value precedence, evaluated per field.** A constraint pinning exactly one legal value, then a `default`, then what the engineer stated, then catalog precedent, then an enumerable enum, and only then a question.
3. **`ui:field` affects rendering, not the contract.** A field keeps its declared JSON Schema type whatever widget the web form renders. Every field is therefore askable.
4. **Tolerate schema noise.** Ignore unrecognised keys; fall back when a convention is absent, so a missing `enumNames` shows raw values. Real templates contain copy-paste errors, and a template with a stray nested key is still perfectly usable.
5. **Outputs are whatever `spec.output.links` declares.** Outcomes are not repo-centric — some templates create a repository, others only open a pull request.

**Precedent replaces domain knowledge.** Where a value is not derivable from the schema, the skill queries the catalog for existing entities with the same owner and type and proposes what they already use, naming the precedent. It encodes no business rules: no team-to-account mappings, no company mappings, no privilege orderings. This self-updates as the estate changes and degrades to a plain question when there is no precedent.

Two mechanisms enforce this, because genericity claimed is not genericity delivered:

- A grep guard over **all files** under `skills/hc-scaffold-service/` for template names, environment names, account numbers and team names. A hit fails the build. Naming real templates in these docs is fine and useful; skill examples/refs must stay synthetic.
- A synthetic template in the fixtures combining supported constructs in shapes none of the real templates use. The skill must handle it having never seen it.
- A hard line-budget gate on `SKILL.md` (≤400 lines) so dialect stays in `reference.md` rather than bloating the always-on body.

## Interaction model

The Backstage web form is the **floor, not the target**. When the skill has nothing to go on it asks what the form asks. Otherwise it investigates, infers and proposes, so the engineer spends attention only on genuine decisions. A template with eighteen form inputs should reduce to roughly five questions.

Fields are classified as:

- **Determined** — a `default` exists, a constraint pins one legal value, or the value is composable from the field's own `ui:options`. Taken silently, shown in review.
- **Inferable** — a sibling field implies it, the catalog can answer it, or stated intent supplies it. Proposed with a reason.
- **Must ask** — no default, no enum, or a genuine judgement call.

Built-in composite widgets are reproduced behaviourally rather than as text boxes. `RepoUrlPicker` composes a location string from host, owner and repository name, so each part is derived from `ui:options` where those pin a single value. `OwnerPicker` resolves against catalog `Group` entities, so an owner must resolve to a real Group and never to free text.

Regardless of confidence: ownership is explicitly confirmed, and **nothing is submitted without explicit confirmation**. The review tags every value by provenance — stated, from a default, pinned by a constraint, or from precedent with the precedent named — so a human can see what was assumed rather than told.

## Failing fast

The skill can do nothing useful without the Backstage MCP, so verification is the first action, before the engineer is asked anything. Presence and usability are separate checks, because the gateway authenticates per user through browser OAuth: a stale session yields a perfectly healthy `tools/list` and a failure on first real call.

- **Capabilities present**, from `tools/list`. Free, no side effects. Both a catalog query capability and a scaffolder execute capability are required, since a catalog-only surface can research but never submit.
- **Live access**, proven by a real call — the template listing the skill needs anyway. Verification therefore costs nothing extra rather than being a throwaway probe.

Three failure modes get three messages, because each needs a different action: missing capabilities is a configuration problem, a refused call is an authentication problem, and a successful call returning zero templates is an empty catalog.

Scaffolder **permission** cannot be pre-verified, because the only way to test it is to cause side effects. It surfaces at submission instead.

The second-order rule matters as much as the first: on failure the skill **stops rather than degrading**. No guessing template names from memory, no hand-rolling files, no offering to set things up manually. When an agent's only dependency is gone, being helpful anyway is the failure mode.

## Decision record

Each entry is a decision, why, and what was rejected. Reopen one only with a reason that is not already answered here.

**Interface, not reimplementation.** The skill drives the official MCP plugin and adds no scaffolding logic. Rejected: a wrapper API, and the "scaffolder returns files, agent commits them" model, which belongs to third-party MCP servers.

**UI parity is the floor, not the goal.** Reproducing the web form question-for-question was rejected: it is the worst acceptable outcome, not the target. The model's ability to investigate and recommend is the entire point, so the engineer should only think about a subset of the questions.

**Generic schema rules over per-template knowledge.** Rejected: teaching the skill the known custom widgets by reading their backend filter contracts. It would make every current template work, at the cost of knowledge that drifts the moment Backstage changes, and which arguably belongs in Backstage.

**Precedent instead of domain knowledge.** An earlier draft inferred a company and an AWS account from the owning team. Rejected: that is not in the schema, it is business knowledge, and hardcoding it is exactly the rot the genericity rule exists to prevent. Precedent from the catalog achieves the same reduction in questions while self-updating.

**No privilege or risk semantics.** A field whose enum happens to describe access levels is handled like any other enum. Rejected: encoding an ordering for well-known vocabularies so the skill could default to least privilege. Any ordering the skill invents is a business rule destined to drift, and the review step already puts the value in front of a human.

**No "unrenderable field" category.** An earlier draft classified unrecognised `ui:field` widgets as unrenderable and planned a handoff to the web form. That was wrong: `ui:field` only tells the frontend which component to render, and the field keeps its declared type, so it can always be asked for. The case collapses into the ordinary one of a field whose valid values the schema does not constrain. The web form remains an escape hatch the engineer can take at any point, not a special-cased pre-check.

**Fail fast with two checks, then stop.** Rejected: a presence-only check, which passes on a stale OAuth session and then breaks mid-interview. Also rejected: interviewing first and discovering the problem at submission, which is the outcome that destroys trust fastest.

**Tool references by capability, with canonical names as hints.** Rejected: hardcoding the dot-namespaced names. Gateway prefixing and the `mcpActions.namespacedToolNames` flag both change them, and neither is under our control, so hardcoding means a silent break the day a config we do not own changes.

**Client-side test oracle.** Assertions read the `claude -p --output-format stream-json` transcript and never the stub's internals. Rejected: assertions over a recording stub, which would only ever work against the stub. Reading the transcript means one suite runs unchanged against both the stub and production.

**Harness sized by behavioural claims.** One scenario per claim the skill makes, each recorded failing unaided before the rule that fixes it is written. Published guidance sets a floor of three evaluations and no ceiling, so the count comes from the artifact. Rejected: a suite at that published minimum, which would leave most of the skill's claims unverified; and scenarios written from imagined failure modes, which is what the evaluation-first loop exists to prevent. See [testing.md](testing.md).

**Deterministic assertions gate; the LLM judge advises.** Rejected: an LLM judge as primary oracle, which is flaky exactly at the pass/fail boundary. Also rejected: golden transcript snapshots, which churn with every model update.

**A stdio stub, not HTTP.** Transport is invisible to the skill — only tool names and schemas matter — so the simpler option wins. Rejected: an HTTP stub matching production transport, which buys fidelity the skill cannot observe at the cost of a server, a port and TLS. Also rejected for now: record/replay against production, which requires working production access before any test can run.

**Report the task URL, then ask whether to follow.** Rejected: blocking until the task reaches a terminal state, which hangs the session on a slow task. Also rejected: fire-and-forget, where a mid-task failure looks identical to success. Background polling that fully unblocks the session is desirable but blocked: the gateway authenticates per user via browser OAuth, so a detached poller has no credential of its own.

**Shared-identity attribution accepted.** Backstage sees a shared `mcp-gateway` service principal rather than the individual engineer, because the `backstage-auth-header` middleware is cluster-internal by design. Accepted rather than worked around. Per-engineer identity propagation is a separate piece of infrastructure work.

**Both invocation modes.** The skill is model-invocable from its `description` and also explicitly invocable as `/hc-scaffold-service`. Auto-activation is safe because submission is gated on confirmation regardless of how the skill started, and a skill nobody remembers exists gets no use. `disable-model-invocation` is omitted on purpose.

**One skill directory with progressive disclosure; not a monolith, not phase commands, not subagents.** Ship `skills/hc-scaffold-service/{SKILL.md,reference.md,examples.md}`. Iron rules and the checklist live in `SKILL.md`; schema dialect and algorithms live in `reference.md` and load only when the skill instructs a read; examples stay in `examples.md`. Rejected: stuffing every §4 requirement into a single `SKILL.md`; a `commands/` tree or phase slash commands (`/ask`, `/submit`); `agents/` or `context: fork` for schema walk / interview / submit. The sandbox copies the skill **directory** (`copytree`), so supporting files are available at runtime. Slash invoke is the skill itself — Claude Code merged custom commands into skills.
