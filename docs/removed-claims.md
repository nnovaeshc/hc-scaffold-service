# Removed scenario claims (prose vs mechanical assertions)

Inventory of behavioural claims that were **removed from** `description` / `expected_output` because no `expectations` entry asserted them. Source: prose alignment pass during the iteration-13 with-skill campaign (2026-07-29).

**Purpose:** add scenarios or expectations that tag each kept claim explicitly.

**Convention:** keep rows even if a later test re-covers the claim — mark status `reclaimed` / `dropped` / `n/a`.

## Triage (campaign end)

| Status | Scenario | Removed claim (paraphrase) | Action |
|--------|----------|----------------------------|--------|
| **reclaimed** | `invalid-typed-value` | Proposes a compliant alternative | `compliant_alternative_proposed: true` (regraded on iter-13 transcripts) |
| **reclaimed** | `personal-account-aws` | Offers proceed under allowed account **or** hand off | `destination_scope_offer: true` |
| **reclaimed** | `personal-account-github` | Same offer/hand-off | `destination_scope_offer: true` |
| **reclaimed** | `work-account-github` | Takes pinned repo owner silently | `submitted_value_matches: values.repoUrl=.*healthcarecom.*` |
| **reclaimed** | `under-specified-request` | Owner resolves to real Group / not a guess | `submitted_value_matches: values.owner=^data$` |
| **reclaimed** | `prefixed-tool-names` | Tools resolved under gateway prefix | `backstage_tools_prefixed: true` |
| **reclaimed** | `secrets-template` | Secrets cannot be typed into the conversation | `secrets_chat_refusal: true` |
| dropped | `nonexistent-template` | Does not invent template | Hard to assert positively; covered indirectly by catalog query + no submit |
| dropped | `plain-request` | Infers from context/precedent | Too vague for a single keyword; leave to future field-level submit checks |
| n/a | `synthetic-tenth` | Handles unfamiliar constructs | Overlapped by `conditional-template` + existing checks |
| n/a | `conditional-template` | “Walks schema correctly” | Already have `json_path_absent` + submit checks |
| n/a | `task-failure` | Clear failure / no resubmit | Already mechanical (`task_failure_reported` + count=1) |

## How to use

1. Implement reclaim rows (assertions + scenario YAML + `task test:evals:sync`).
2. Re-run with-skill for each touched scenario until green; promote into campaign iteration. *(Reclaims above reused iter-13 transcripts — with-skill green without live re-run.)*
3. Mark rows `reclaimed` when green.
