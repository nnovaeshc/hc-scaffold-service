# Examples

Synthetic examples for the hc-scaffold-service skill. All field names and template structures are illustrative only.

## Provenance review table template

Before submission, present a review table showing every value and its source:

```
| Field            | Value                  | Source            |
|------------------|------------------------|-------------------|
| componentId      | payment-callback-api   | You stated        |
| owner            | group:backend-team     | Catalog precedent |
| description      | Payment callback API   | You stated        |
| repoUrl          | github.com/acme/...    | Derived from options |
| environment      | production             | Default           |
| databaseType     | postgres               | Template default  |
| enableMonitoring | false                  | Constraint        |
```

**Provenance categories:**
- "You stated" - engineer provided this value
- "Default" - from `spec.parameters` `default`
- "Constraint" - pinned by schema (single-value `enum`, or `ui:options` constraint)
- "Catalog precedent" - derived from existing entities (name the precedent: "same as payment-service")
- "Derived from options" - composed from `ui:options` fields

## Fail-fast messages

### Configuration failure (missing capabilities)

```
The Backstage MCP server does not provide the required capabilities.

Missing: scaffolder execution capability

Check your MCP server configuration. The skill needs both catalog query 
and scaffolder execution capabilities to function.
```

### Auth failure (denied call)

```
The Backstage MCP server refused the request.

Authorization denied: insufficient permissions to query catalog

Verify your Backstage authentication and that the MCP server has 
permission to access both catalog and scaffolder APIs.
```

### Empty catalog

```
The Backstage catalog contains no templates.

The catalog query succeeded but returned zero Template entities. 
Verify templates are registered in your Backstage instance.
```

## Synthetic multi-page ask sequence

**Page 1 fields:**
- `componentId` (required, string)
- `owner` (required, OwnerPicker → Group resolution)
- `description` (string, optional)

**Page 2 fields:**
- `databaseConfig.dbType` (enum: postgres | mysql, default postgres)
- `databaseConfig.connectionString` (string, conditional on dbType)
- `enableAdvanced` (boolean, default false)
- `advancedOptions` (object, conditional - only if enableAdvanced=true)

**Ask flow:**
1. "What should I call this component?" → derives `componentId`
2. Collision check: query catalog + GitHub
3. "Which team owns this?" → resolves to `group:some-team` via catalog Groups
4. Skip `description` if intent already clear
5. Keep `databaseConfig.dbType` at default (postgres)
6. Do not ask for `advancedOptions` since `enableAdvanced` defaults to false

**Review:**

| Field                         | Value           | Source            |
|-------------------------------|-----------------|-------------------|
| componentId                   | data-processor  | You stated        |
| owner                         | group:data-team | Resolved from catalog |
| databaseConfig.dbType         | postgres        | Template default  |
| enableAdvanced                | false           | Template default  |

Conditionally hidden fields (not submitted):
- `databaseConfig.connectionString` (conditional, dbType allows default)
- `advancedOptions` (conditional, enableAdvanced is false)
