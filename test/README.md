# Test Harness

Automated test infrastructure for the hc-scaffold-service skill.

## Prerequisites

1. **Docker** with the ai-tdd image:
   ```bash
   # Image is pulled from ECR and tagged locally as ai-tdd:latest
   # This happens automatically if you have ECR access
   ```

2. **AWS SSO credentials:**
   ```bash
   aws sso login --profile hc-devopstooling-prod
   ```

## Quick Start

### Verify Setup Works

```bash
# Simple test - Claude answers "What is 2+2?"
./test/test-simple.sh
# Expected output: "4"
```

### Run Individual Scenarios

```bash
# Run one scenario at a time:
./test/run.sh preflight-empty-catalog
./test/run.sh prefixed-tool-names
./test/run.sh plain-request

# Each scenario takes ~30-60 seconds and costs ~$0.10 in tokens
```

### Run All Scenarios

```bash
# Run all 13 scenarios (~10-15 minutes, ~$1.50 in tokens):
./test/run.sh

# Or specific ones:
./test/run.sh preflight-empty-catalog prefixed-tool-names plain-request
```

### Run Without Skill (Baseline)

```bash
# See what happens without the skill installed:
./test/run.sh --no-skill preflight-empty-catalog
```

## Test Structure

```
test/
├── run.sh                        # Main test runner
├── test-simple.sh                # Simple verification test
├── docker-compose.yaml           # Container config
├── mcp-servers.test.yaml         # MCP config (stub server)
├── skills.test.yaml              # Skill installation config
├── stub/
│   └── server.py                 # Stub MCP server (7 scenarios)
├── fixtures/
│   ├── templates/                # 9 real + 1 synthetic template
│   ├── groups/                   # Catalog Group entities
│   └── task-logs/                # Success/failure log sequences
├── scenarios/                    # 13 test scenarios
│   ├── preflight-empty-catalog.yaml
│   ├── preflight-no-capabilities.yaml
│   ├── plain-request.yaml
│   └── ...
├── assertions/
│   └── check.py                  # Transcript oracle
└── results/                      # Test output (gitignored)
    ├── *-transcript.jsonl        # Stream-json transcripts
    └── runs.jsonl                # Run metadata + usage
```

## Scenarios

| Scenario | STUB_SCENARIO | Tests |
|----------|---------------|-------|
| `preflight-empty-catalog` | `empty_catalog` | Detects zero templates, stops with message |
| `preflight-no-capabilities` | `no_backstage_tools` | Detects missing tools, stops with config error |
| `preflight-catalog-only` | `catalog_only` | Detects missing scaffolder, stops with config error |
| `preflight-denied-call` | `denied_first_call` | Detects auth failure, stops with auth error |
| `prefixed-tool-names` | `prefixed_tool_names` | Handles gateway-prefixed tool names |
| `plain-request` | `default` | Reduces 18 fields to ~5 questions |
| `under-specified-request` | `default` | Resolves owner to real Group |
| `time-pressure` | `default` | Review + confirm despite "skip questions" |
| `nonexistent-template` | `default` | Queries catalog, doesn't invent |
| `conditional-template` | `default` | Excludes conditionally hidden fields |
| `synthetic-tenth` | `default` | Handles unseen template structure |
| `task-failure` | `task_failure` | Reports failure, no auto-resubmit |
| `secrets-template` | `default` | Refuses secrets templates, redirects to UI |

## Stub Server

The stub MCP server (`test/stub/server.py`) responds to:

- `initialize` - Returns MCP protocol handshake
- `tools/list` - Returns 4 Backstage tools (optionally prefixed)
- `tools/call` - Serves from fixtures:
  - `catalog.query-catalog-entities` - Templates and Groups
  - `catalog.get-catalog-entity` - Full template with spec.parameters
  - `scaffolder.execute-template` - Returns taskId
  - `scaffolder.get-scaffolder-task-logs` - Returns log sequence

**Modes via STUB_SCENARIO env var:**
- `default` - 9 templates, healthy
- `empty_catalog` - Zero templates
- `denied_first_call` - First call returns auth error
- `no_backstage_tools` - tools/list returns unrelated tools
- `catalog_only` - Catalog tools only, no scaffolder
- `task_failure` - Task fails mid-run
- `prefixed_tool_names` - All tool names carry `backstage.*` prefix

## Assertions

The oracle (`test/assertions/check.py`) checks:

1. **Tool calls:** Which tools were called, in what order
2. **Arguments:** Tools have `fields` and `limit`, correct filters
3. **JSON paths:** Submitted values match expectations
4. **Absence:** Conditionally hidden fields not submitted
5. **Constraints:** Submitted values satisfy their declared schema constraint (`submitted_value_matches`); a violating input is reported rather than submitted (`constraint_violation_reported`)
6. **Question count:** At or below bound
7. **Fail-fast:** No questions after preflight failure
8. **Call limits:** No auto-resubmit (execute-template called once)
9. **Size limits:** Largest tool result under byte ceiling
10. **Token limits:** Total fresh input tokens under ceiling
11. **Explanations:** LLM judge for inference quality (advisory)

## Guards

Run automatically before scenarios:

### Genericity Guard

Fails if any file under `skills/hc-scaffold-service/` contains:
- Real template names (aws-lambda-api, springboot-microservice, etc.)
- Environment names
- AWS account numbers
- Team names

### Line Budget Guard

Fails if `SKILL.md` exceeds 400 lines (target: ≤250).

## Results

After each run, `test/results/` contains:

**`<scenario>-transcript.jsonl`** - Full stream-json transcript with:
- System init message (tools, MCP servers, model)
- Thinking tokens (streaming estimates)
- Assistant messages (text + tool uses)
- User messages (tool results)
- Result message (usage, cost, duration)

**`runs.jsonl`** - One record per scenario run:
```json
{
  "scenario": "preflight-empty-catalog",
  "model": "claude-sonnet-4-5-20250929",
  "usage": {
    "input_tokens": 333,
    "output_tokens": 719,
    "cache_read_input_tokens": 55545,
    "cache_creation_input_tokens": 17632
  },
  "stub_scenario": "empty_catalog",
  "skill_installed": true,
  "timestamp": "2026-07-29T..."
}
```

## Troubleshooting

### "Could not load credentials"

```bash
# Re-authenticate:
aws sso login --profile hc-devopstooling-prod

# Credentials expire after a few hours
```

### "Permission denied" for tool calls

The test runner uses `--permission-mode bypassPermissions` to allow non-interactive tool use. If this fails, check:

```bash
docker-compose -f test/docker-compose.yaml run --rm ai-tdd \
  claude -p --help | grep permission-mode
```

### Container won't start

```bash
# Check image exists:
docker images | grep ai-tdd

# If missing, see docs/implementation-plan.md §3 for ECR pull instructions
```

### Scenarios hang

Each scenario has a timeout in `run.sh`. If hanging:
- Check AWS credentials are valid
- Check Docker has network access
- Check CLAUDE_CODE_USE_BEDROCK=1 is set

## CI Integration

To run in CI:

```bash
# Prerequisites:
# 1. AWS credentials available as env vars:
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_SESSION_TOKEN=...

# 2. Docker with ai-tdd:latest image available

# Then:
./test/run.sh

# Exit code 0 = all scenarios passed
# Exit code 1 = one or more scenarios failed
```

See `docs/testing.md` for harness architecture details.
