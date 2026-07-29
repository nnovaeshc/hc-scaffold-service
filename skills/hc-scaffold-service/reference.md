# Reference: Schema Dialect and Algorithms

Detailed schema walking, precedence, and Backstage conventions.

## Contents

- Schema Walk Algorithm - page and field traversal order, classification
- Construct Support - JSON Schema keywords, Backstage `ui:` dialect, conditionals
- Value Precedence (per field) - resolution order, first match wins
- Constraint Validation - keyword checks, candidate repair, nested scope
- Destination Scope - recognizing an explicit destination outside what the template allows
- Recognized `ui:field` Widgets - OwnerPicker, RepoUrlPicker, EntityPicker, others
- Collision Detection - catalog and GitHub name checks
- Output Links Reporting - link type heuristics for task output
- Context Budget: Query Shape - required `fields` and `limit` on every query
- Secrets Refusal - detection keys and the redirect message

## Schema Walk Algorithm

1. **Process `spec.parameters` in order** - each item is a page
2. **For each page:**
   - Walk `properties` object in declaration order
   - Check `required` array for mandatory fields
   - Evaluate `dependencies` with `allOf`/`if`/`then` conditionals
   - Resolve `$ref` into `definitions` when present
3. **For each field:**
   - Extract declared JSON Schema type: string, number, boolean, array, object
   - Note `enum` (allowable values) and `enumNames` (display labels)
   - Note `default` if present
   - Note `format` (email, uri, date, etc.) if present
   - Note every constraint keyword present: `pattern`, length, numeric bounds, item counts (see Constraint Validation)
   - Inspect `ui:field` for rendering widget
   - Inspect `ui:options` for widget-specific constraints
   - Check `items` - may be a schema (homogeneous array) or positional tuple
4. **Classify field as:**
   - **Determined**: has a `default`, or constraint pins one legal value, or composable from `ui:options`
   - **Inferable**: sibling field, catalog precedent, or stated intent implies it
   - **Must-ask**: no other source

## Construct Support

### JSON Schema

- **`type`**: string, number, integer, boolean, array, object
- **`enum`**: list of allowable values
- **`enumNames`**: parallel array of human-readable labels (fallback: show raw enum values)
- **`default`**: pre-filled value
- **`format`**: hint for validation (email, uri, date, uuid, etc.)
- **`required`**: array of field names that must have a value
- **`pattern`**: regular expression the string value must match
- **`minLength`** / **`maxLength`**: string length bounds
- **`minimum`** / **`maximum`** / **`exclusiveMinimum`** / **`exclusiveMaximum`**: numeric bounds
- **`multipleOf`**: numeric divisor
- **`minItems`** / **`maxItems`** / **`uniqueItems`**: array bounds
- **`const`**: single allowed value (equivalent to a one-item `enum`)
- **`dependencies`**: fields that gate other fields
- **`$ref`**: reference to `definitions` block (resolve recursively)
- **`definitions`**: named schema fragments
- **`items`**: array member schema (either single schema for homogeneous, or tuple of positional schemas)

### Backstage `ui:` Dialect

- **`ui:field`**: rendering widget name (see Recognized Widgets below)
- **`ui:options`**: widget-specific configuration object
- **`ui:autofocus`**: boolean hint to focus this field first
- **Unrecognized keys**: ignore silently

### Conditionals: `dependencies`, `allOf`, `if`/`then`

When a field appears in `dependencies`:
```yaml
dependencies:
  triggerField:
    allOf:
      - if:
          properties:
            triggerField:
              const: specificValue
        then:
          required:
            - conditionalField
```

**Behavior**: `conditionalField` is required only when `triggerField` equals `specificValue`. If the condition is not met, do not submit `conditionalField` even if a value exists in the form state.

## Value Precedence (per field)

Evaluate in this order; first match wins:

1. **Constraint pins exactly one legal value**: single-item `enum`, or `ui:options` that lock all parts of a composite field
2. **`default`** declared in schema
3. **Engineer stated** in conversation
4. **Catalog precedent**: existing entities with same owner and type use this value
5. **Enumerable enum**: if `enum` present with ≤5 items, present as recommendation
6. **Ask**

Never skip 1 or 2 to honor 3. If a `default` exists, apply it unless the engineer explicitly overrode it.

## Constraint Validation

Submission is one shot: `execute-template` returns a `taskId`, not a validation verdict, and a failed task must not be resubmitted. Every value must therefore satisfy the schema **before** it is submitted, whoever produced it.

Validation is driven **only** by the keywords the schema declares. A keyword that is absent imposes no check. **Never invent a constraint** - not from what a value "looks like", not from what similar templates do, not from naming conventions you have seen. An invented rule rejects legal values on templates you have never seen.

### Keyword checks

| Declared | Check the value against it |
|----------|---------------------------|
| `type` | Value is that type, or unambiguously coercible to it (`"true"` → boolean, `"3"` → number) |
| `pattern` | Full string matches the regex as written |
| `minLength` / `maxLength` | String length within bounds |
| `minimum` / `maximum` / `exclusive*` | Number within bounds |
| `multipleOf` | Number divides evenly |
| `enum` / `const` | Value is a member / equals the constant, exact case |
| `minItems` / `maxItems` / `uniqueItems` | Array length within bounds; no duplicates |
| `required` | Field is present and not empty |
| `format` | For `email`, `uri`, `uuid`, `date`: check the shape. All other formats are advisory - report a mismatch, do not block |

Constraints **compose**: a value must satisfy every keyword declared on the field, not just the first that fails.

Constraints reachable through `ui:options` are checked the same way: `RepoUrlPicker`'s `allowedHosts` / `allowedOwners` are membership constraints on the composed parts, and `EntityPicker` / `OwnerPicker` values must resolve to a real catalog entity (see Recognized Widgets).

Unrecognized keywords are not constraints. Mention them to the engineer if they look load-bearing; never block on them. An unrecognized `ui:field` does not exempt a field - its declared JSON Schema keywords still apply.

### Scope

- Every field in the submitted payload, whatever its provenance: engineer-stated, `default`, catalog precedent, or derived from context.
- Inside `$ref`-resolved objects and `items` schemas, including each positional entry of a tuple.
- Skip fields excluded by `dependencies` - they are not submitted, so their constraints do not apply.

### Candidate repair

When a value fails, propose exactly one compliant candidate derived **mechanically from the violated keyword**:

| Violated | Proposal |
|----------|----------|
| `pattern` restricted to lowercase/digits/separator | Lowercase, replace runs of disallowed characters with the separator the pattern allows, trim leading and trailing separators |
| `maxLength` | Truncate at a word or separator boundary |
| `enum` / `const` | The member closest to what was given, quoted exactly as declared |
| numeric bound | The nearest allowed value |
| anything else | No proposal. Say what is required and ask |

Never rewrite silently, and never submit the original value. The proposal is a suggestion the engineer confirms or replaces - a repaired name is still their decision, since it becomes a repository name and a catalog identity.

## Destination Scope

A **destination-scoping field** is any field a template constrains to a fixed set of accounts, owners,
or orgs: an `enum` on an account/owner/org-shaped field, or `RepoUrlPicker`'s `allowedHosts` /
`allowedOwners`. These are ordinary constrained fields under Value Precedence and Constraint
Validation - the difference here is what to do when the engineer's own words name a destination
outside the set.

**This only applies when the engineer stated a destination.** Most requests name none; in that case
the constrained value is Determined as usual, taken silently, shown in review. Nothing changes for the
common case.

**When the engineer names a destination not in the constrained set**, this is not a malformed value to
repair - it is evidence the template is the wrong tool for what they asked. Do not propose the nearest
allowed member the way a pattern or enum violation would. Instead, name what the template can actually
produce (quoting the constraint), state that the stated destination is out of scope for it, and ask
whether to proceed with the template's supported destination or handle the request outside Backstage
with default tooling. Do not classify parameters or ask must-ask questions until this is resolved.

## Recognized `ui:field` Widgets

### `OwnerPicker`

Resolves to a catalog Group. Query `kind: Group` entities, extract `metadata.name`, return as `group:<name>`.

**`ui:options.catalogFilter`**: may constrain to `kind: Group` (already the default).

**Never accept free text** - owner must resolve to a real Group entity.

### `RepoUrlPicker`

Composes a repository location string from parts: host, owner (org), repo name.

**`ui:options`** may pin:
- `allowedHosts`: array (if one item, host is determined)
- `allowedOwners`: array (if one item, owner is determined)
- `allowedRepos`: rarely used

**Derive each part**:
- If pinned to one value, it is determined
- Otherwise, infer from context or ask

**Format**: `<host>?owner=<owner>&repo=<repo>` (URL-encoded)

### `EntityPicker`

Select an existing catalog entity by reference.

**`ui:options.catalogFilter`**: `kind`, `spec.type`, `metadata.namespace`

Query catalog with the filter, present matching entities.

### Other widgets

`OwnedEntityPicker`, `EntityNamePicker`, `MyGroupsPicker` follow similar patterns. `CodeEditorPicker`, `MultilineText` are just text with rendering hints. Unrecognized widgets fall back to their declared JSON Schema type.

## Collision Detection

Before asking anything, verify the proposed `componentId` or `name`:

1. **Catalog check**: query `kind: Component` (or template's `spec.type`) with the proposed name
2. **GitHub check**: if a `RepoUrlPicker` is present, check the GitHub API for an existing repo at the derived location

If collision found, modify the name (append a suffix or prompt for a different name) and re-check.

## Output Links Reporting

`spec.output.links` declares what the scaffolder creates. Each link has a `url` (template interpolated) and optional `title`.

**Link type heuristics:**
- Contains `pull` or `merge_request`: **Pull request** - flag that it requires human review before deploy
- Contains `github.com/<org>/<repo>` without `pull`: **Repository** - offer to clone
- Contains `catalog.`: **Catalog entity reference** - report as a new catalog entry
- Otherwise: **Generic link** - just report the URL

Example output message:
```
Created repository: https://github.com/acme/payment-api
Pull request requires review: https://github.com/acme/payment-api/pull/1
Catalog entry: component:default/payment-api
```

## Context Budget: Query Shape

**Every catalog query** must include:

```json
{
  "filter": { "kind": "Template" },
  "fields": ["metadata.name", "metadata.title", "metadata.description"],
  "limit": 50
}
```

**`fields`**: project only the keys you need. For template listing, request only metadata. Fetch full `spec.parameters` for the chosen template only via `get-catalog-entity`.

**`limit`**: cap results. For template discovery, 50 is generous. For Groups (owner resolution), 20 is sufficient.

**Never fetch the whole catalog** without `fields` and `limit`.

## Secrets Refusal

If `spec.parameters` anywhere declares a field with `ui:field: Secret` or `format: password` or `x-backstage-secret: true`, refuse and redirect:

```
This template requires secrets to be entered directly.

For security, secrets cannot be provided through this interface since they would 
pass through the LLM context. Use the Backstage web UI for this template:

https://backstage.platform.healthcare.com/create/templates/<templateRef>
```

Check the full parameters tree before asking the engineer anything.
