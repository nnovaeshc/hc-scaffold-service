# Reference: Schema Dialect and Algorithms

Detailed schema walking, precedence, and Backstage conventions.

## Contents

- Schema Walk Algorithm - page and field traversal order, classification
- Construct Support - JSON Schema keywords, Backstage `ui:` dialect, conditionals
- Value Precedence (per field) - resolution order, first match wins
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
