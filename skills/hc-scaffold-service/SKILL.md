---
name: hc-scaffold-service
model: sonnet
description: Creates a new component from a Backstage software template based on a natural-language description of what is needed. Triggers on "scaffold", "Backstage template", "create service", "create component", "new service from template", or explicit invocation. Works with any registered template by walking its schema and deriving values from context, catalog precedent, and conversation.
---

# hc-scaffold-service

Create a new service or component from a Backstage software template through conversation, without opening the Backstage UI or learning the scaffolder API.

## When to Use

- The user wants to create a new service, component, or resource using Backstage
- The user mentions scaffolding, templates, or creating from a template
- The user explicitly invokes `/hc-scaffold-service`

## Workflow

Copy this checklist and check off each step as you complete it. Follow it in order. Stop immediately on any failure.

```
Scaffold Progress:
- [ ] 1. Preflight: verify MCP access (before asking anything)
- [ ] 2. Understand intent
- [ ] 3. Select template
- [ ] 4. Fetch full template schema
- [ ] 5. Check for secrets
- [ ] 6. Classify parameters
- [ ] 7. Collision check
- [ ] 8. Ask only the gaps
- [ ] 9. Review before submission
- [ ] 10. Confirm ownership and submission
- [ ] 11. Submit
- [ ] 12. Report task URL immediately
```

### 1. Preflight: Verify MCP Access (BEFORE asking anything)

**Check 1 - Capabilities present:**
- Call `tools/list` on the Backstage MCP server
- Verify BOTH capabilities exist:
  - Catalog query capability (tool name contains "catalog" and "query-catalog-entities")
  - Scaffolder execute capability (tool name contains "scaffolder" and "execute-template")
- Match by **capability, not exact string** - tool names may be prefixed (e.g., `backstage.catalog.query-catalog-entities`)

**If missing capabilities:**
```
The Backstage MCP server does not provide the required capabilities.

Missing: [list what's missing: "catalog query" or "scaffolder execution" or both]

Check your MCP server configuration. The skill needs both catalog query 
and scaffolder execution capabilities to function.
```
**STOP. Do not ask any questions. Do not proceed.**

**Check 2 - Live access:**
- Query catalog for `kind: Template` with `fields` and `limit` (this is the template list you need anyway)
- If **denied or transport error:**
```
The Backstage MCP server refused the request.

[Include the actual error message]

Verify your Backstage authentication and that the MCP server has 
permission to access both catalog and scaffolder APIs.
```
**STOP. Do not ask any questions. Do not proceed.**

- If **zero templates returned:**
```
The Backstage catalog contains no templates.

The catalog query succeeded but returned zero Template entities. 
Verify templates are registered in your Backstage instance.
```
**STOP. Do not ask any questions. Do not proceed.**

**Scaffolder permission** cannot be checked without side effects. It will surface at submission if denied.

**Three distinct failure modes**: config (missing tools), auth (denied call), empty catalog. Never collapse into generic "Backstage unavailable".

### 2. Understand Intent

Read the user's stated intent and the ambient repository context:
- What are they trying to build?
- What template might match?
- What values can be inferred from the working directory, git remote, or recent conversation?

### 3. Select Template

Present matching templates from the catalog query (you already have the list from preflight Check 2).

If the user named a specific template, verify it exists. If it does not exist in the catalog, report that and stop - never invent a template name from memory.

Confirm the template choice explicitly.

### 4. Fetch Full Template Schema

Call `get-catalog-entity` with the chosen template's entity reference to fetch the raw `spec.parameters`.

**Before classifying fields, read `reference.md`**. It contains the schema walk algorithm, precedence rules, and Backstage `ui:field` dialect.

### 5. Check for Secrets

Scan the full parameters tree for any field declaring secrets:
- `ui:field: Secret`
- `format: password`
- `x-backstage-secret: true`

**If found, refuse and redirect:**
```
This template requires secrets to be entered directly.

For security, secrets cannot be provided through this interface since they would 
pass through the LLM context. Use the Backstage web UI for this template:

https://backstage.platform.healthcare.com/create/templates/[templateRef]
```
**STOP. Do not proceed with this template.**

### 6. Classify Parameters

Walk `spec.parameters` pages in order. For each field:

**Read the schema**:
- JSON Schema type (string, number, boolean, array, object)
- `enum`, `enumNames`, `default`, `format`, `required`
- `ui:field`, `ui:options`
- `dependencies`, `$ref`, `items` (see `reference.md`)

**Classify by precedence** (first match wins):
1. **Determined**: constraint pins one value, or has a `default`, or composable from `ui:options`
2. **Inferable**: sibling field, catalog precedent, or stated intent implies it
3. **Must-ask**: no other source

**For catalog precedent**: Query existing entities sharing the same owner and type. If they consistently use a specific value for this field, propose it and name the precedent. Example: "Your other services use `production` for environment - use that here?" Never encode business rules (no team-to-account maps, no hardcoded environment names).

**Recognized `ui:field` widgets** (see `reference.md` for behavioral details):
- `OwnerPicker` → resolve to `group:<name>` from catalog Groups
- `RepoUrlPicker` → compose location from host/owner/repo parts
- `EntityPicker` → select existing catalog entity
- Unrecognized → fall back to declared JSON Schema type, no special behavior

### 7. Collision Check

Before asking anything, verify the proposed component name:
- **Catalog check**: query for existing entity with that name
- **GitHub check**: if template uses `RepoUrlPicker`, check if repo already exists

If collision found, modify the name (append suffix or prompt for alternative) and re-check.

### 8. Ask Only the Gaps

For each **must-ask** field, ask **one question at a time**, each with a recommendation.

**Do not script dialogue.** Phrasing is your judgment. The form's question text is the floor.

**Handle time pressure**: if the user says "skip the questions" or "just do it", you still MUST present the review and require explicit confirmation. Never skip the review or confirmation gates.

**Interaction floor**: when you have nothing to go on, ask what the Backstage web form asks. When you have precedent or constraints, reduce the question count.

### 9. Review Before Submission

Present a provenance-tagged review table. See `examples.md` for the shape.

Tag every value by source:
- "You stated"
- "Default" (from schema)
- "Constraint" (pinned by schema)
- "Catalog precedent" (name the precedent: "same as X service")
- "Derived from options"

List any conditionally hidden fields that will NOT be submitted due to dependencies.

### 10. Confirm Ownership and Submission

**Two explicit confirmations required**, regardless of confidence:

1. **Ownership**: "This will be owned by `group:<name>`. Confirm?"
2. **Submission**: "Submit this to Backstage scaffolder?" (Yes/No)

**If No**: return to step 8 to adjust values.

**Never submit without explicit confirmation.**

### 11. Submit

Call `execute-template` with:
- `templateRef`: the chosen template's entity reference
- `values`: object with all determined/asked field values

**Exclude conditionally hidden fields** per the dependencies rules in `reference.md`.

**Response**: the call returns `{ taskId }` only. This is NOT success - it means the task started.

### 12. Report Task URL Immediately

```
Task submitted: https://backstage.platform.healthcare.com/scaffolder/tasks/[taskId]
```

**Ask whether to follow along**: "Watch progress, or check later?"

**If "check later"**: hand back the URL and how to ask for status.

**If "watch"**: poll `get-scaffolder-task-logs` with the `after` cursor for incremental logs. Report step completions, not raw log dumps. 

**On task success**: report declared `output.links` per the matrix in `reference.md` (repository, pull request, catalog entry).

**On task failure**: report the failing step with log excerpt. **Do NOT auto-resubmit** - earlier steps have side effects.

**On access denied at submission**: report which call was refused and stop. Never retry with different credentials.

## Constraints (NEVER / ALWAYS)

| Rule | Reason |
|------|--------|
| **NEVER** ask the user anything before both preflight checks pass | Preflight failures are config/auth problems, not questions to negotiate |
| **NEVER** invent template names from memory | The catalog is authoritative; if a template is not listed, it does not exist |
| **NEVER** skip the review or confirmation gates | Explicit confirmation is required regardless of confidence |
| **NEVER** submit without the user's explicit "yes" to submission | This is not negotiable |
| **NEVER** resubmit after a task failure | Earlier steps have side effects; retrying is destructive |
| **NEVER** encode business rules | No team-to-account maps, no env names, no AWS accounts in the skill - use catalog precedent instead |
| **NEVER** fetch the whole catalog | Every query MUST have `fields` and `limit` |
| **NEVER** proceed with secrets-declaring templates | Refuse and redirect to Backstage UI |
| **ALWAYS** match tools by capability, not exact name | Gateway prefixing and configuration flags change tool names |
| **ALWAYS** read `reference.md` after fetching the template entity and before classifying parameters | The dialect details live there |
| **ALWAYS** exclude conditionally hidden fields from submission | Check `dependencies` rules |
| **ALWAYS** report provenance in the review | The user must see where every value came from |

## Rationalization Table (Built from Baseline Failures)

This table shows why defaults fail and what rule prevents each failure:

| Without this rule... | The model does... | Which causes... | Guarded by... |
|---------------------|-------------------|-----------------|---------------|
| Preflight verification | Asks template questions before checking MCP access | User wastes time on a conversation that cannot submit | Preflight checks BEFORE any questions |
| Fail-fast on config | Treats missing tools as "Backstage down" | Generic error instead of actionable config fix | Three distinct stop messages |
| Capability matching | Hardcodes `catalog.query-catalog-entities` | Fails when gateway prefixes tool names | Match by capability (substring/keyword) |
| Template existence check | Invents template names from training data | Submits to a template that does not exist | Query catalog; if not found, stop |
| Secrets refusal | Asks user to provide secrets in chat | Secrets pass through LLM context | Scan for secrets fields; refuse before asking |
| Collision check | Asks all questions then submits | Task fails because name already taken | Check catalog and GitHub before asking |
| Explicit confirmation | Submits immediately after gathering values | User has no chance to review or abort | Two-gate confirmation (ownership + submission) |
| No auto-resubmit | Retries task after failure | Re-runs side effects, creates duplicates | On failure, report and stop |
| Precedent over hardcoding | Encodes "team X owns account Y" | Breaks when teams or accounts change | Query catalog for precedent; never hardcode business logic |
| Context budget | Fetches full catalog on every query | Exhausts context with thousands of entities | Require `fields` and `limit` on every catalog query |

## Failure Modes

See `examples.md` for exact stop-message wording.

**Config failure**: missing capabilities → name what's missing, point at MCP config, stop.

**Auth failure**: denied call → report the error, stop.

**Empty catalog**: zero templates → report, stop.

**Secrets template**: redirect to Backstage UI, stop.

**Task failure**: report failing step, do not resubmit.

**Access denied at submit**: report which call was refused, stop.

## Notes

- The Backstage web form is the **floor**, not the target. Reduce question count by inferring and deriving.
- `reference.md` and `examples.md` are read on demand per explicit instruction above. They use synthetic field names only.
- Requires Sonnet or better. `model: sonnet` pins the model for the invoking turn only; the session model resumes on the next prompt. The pin is advisory - an org `availableModels` allowlist can exclude it silently, and no runtime model check exists.
- Background polling is out of scope - the MCP gateway requires per-user auth that a detached poller cannot obtain.
- Backstage attributes actions to a shared `mcp-gateway` service principal, not the individual engineer. This is accepted.
