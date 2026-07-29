#!/usr/bin/env bash
set -euo pipefail

# Test harness entry point for hc-scaffold-service skill
# Runs scenarios, checks assertions, records usage, enforces guards

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Flags
INSTALL_SKILL=true
MODEL="${MODEL:-claude-sonnet-4-5}"
EFFORT="${EFFORT:-}"

usage() {
  cat <<EOF
Usage: $0 [OPTIONS] [SCENARIO...]

Run hc-scaffold-service test scenarios.

OPTIONS:
  --no-skill          Run without installing the skill (baseline mode)
  --without-skill     Alias of --no-skill
  --model MODEL       Override model (default: claude-sonnet-4-5)
  --effort LEVEL      Set effort level (low|medium|high|xhigh|max)
  -h, --help          Show this help

SCENARIO:
  One or more scenario files from test/scenarios/
  If none specified, runs all scenarios.

EXAMPLES:
  $0                                    # Run all scenarios with skill
  $0 --no-skill                         # Run all without skill (baseline)
  $0 --model opus-5 plain-request       # Run one scenario with opus-5
  $0 --effort high conditional-template # Run with high effort

EOF
  exit 0
}

# Parse arguments
SCENARIOS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-skill|--without-skill)
      INSTALL_SKILL=false
      shift
      ;;
    --model)
      MODEL="$2"
      shift 2
      ;;
    --effort)
      EFFORT="$2"
      shift 2
      ;;
    -h|--help)
      usage
      ;;
    *)
      SCENARIOS+=("$1")
      shift
      ;;
  esac
done

# If no scenarios specified, find all
if [[ ${#SCENARIOS[@]} -eq 0 ]]; then
  if [[ -d test/scenarios ]]; then
    mapfile -t SCENARIOS < <(ls test/scenarios/*.yaml 2>/dev/null | xargs -n1 basename | sed 's/\.yaml$//' || true)
  fi
fi

if [[ "$INSTALL_SKILL" == "true" ]]; then
  export SKILLS_TEMPLATE="/work/test/skills.test.yaml"
else
  export SKILLS_TEMPLATE="/work/test/skills.none.test.yaml"
fi

echo "==> Test harness for hc-scaffold-service"
echo "    Model: $MODEL"
[[ -n "$EFFORT" ]] && echo "    Effort: $EFFORT"
echo "    Skill installed: $INSTALL_SKILL"
echo "    Scenarios: ${SCENARIOS[*]:-none}"
echo

# Export AWS credentials for Docker container
echo "==> Exporting AWS credentials..."
if ! eval $(aws configure export-credentials --profile hc-devopstooling-prod --format env 2>/dev/null); then
  echo "WARNING: Failed to export AWS credentials. Tests may fail if Bedrock access is needed."
  echo "Make sure 'aws sso login --profile hc-devopstooling-prod' has been run."
fi
export AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN
echo

# Guard 1: Grep genericity check
echo "==> Running genericity guard..."
FORBIDDEN_PATTERNS=(
  "aws-lambda-api"
  "aws-lambda-cron"
  "aws-lambda-sqs"
  "springboot-microservice"
  "locust-python-boilerplate"
  "cron-automated-test"
  "github-repo"
  "mcp-server"
  "ephemeral-environments"
)

GREP_FAILED=false
for pattern in "${FORBIDDEN_PATTERNS[@]}"; do
  if grep -r "$pattern" skills/hc-scaffold-service/ 2>/dev/null; then
    echo "ERROR: Found forbidden pattern '$pattern' in skill package"
    GREP_FAILED=true
  fi
done

if $GREP_FAILED; then
  echo "FAIL: Genericity guard failed - template names found in skill"
  exit 1
fi
echo "PASS: No template names in skill package"

# Guard 2: Line budget check on SKILL.md
echo "==> Running line-budget guard..."
SKILL_LINES=$(wc -l < skills/hc-scaffold-service/SKILL.md || echo "999")
if [[ $SKILL_LINES -gt 400 ]]; then
  echo "FAIL: SKILL.md has $SKILL_LINES lines (hard limit: 400)"
  exit 1
fi
echo "PASS: SKILL.md has $SKILL_LINES lines (within 400 limit)"

# Check if image exists, build if needed
if ! docker image inspect ai-tdd:latest >/dev/null 2>&1; then
  echo "==> Building ai-tdd:latest from healthcare-images..."
  if [[ ! -d ../healthcare-images/ai/ai-tdd/latest ]]; then
    echo "ERROR: healthcare-images not found at ../healthcare-images"
    echo "Clone healthcarecom/healthcare-images adjacent to this repo"
    exit 1
  fi
  docker build -t ai-tdd:latest ../healthcare-images/ai/ai-tdd/latest
fi

# Run scenarios
mkdir -p test/results
for scenario in "${SCENARIOS[@]}"; do
  scenario_file="test/scenarios/${scenario}.yaml"
  if [[ ! -f "$scenario_file" ]]; then
    echo "WARNING: Scenario file not found: $scenario_file"
    continue
  fi

  echo "==> Running scenario: $scenario"

  # Extract prompt and stub scenario from yaml
  # Simple extraction - assumes prompt:, compare_prompt: and stub_scenario: are on their own lines
  prompt=$(sed -n 's/^prompt: //p' "$scenario_file")
  compare_prompt=$(sed -n 's/^compare_prompt: //p' "$scenario_file")
  stub_scenario=$(sed -n 's/^stub_scenario: //p' "$scenario_file" | head -1)
  stub_scenario=${stub_scenario:-default}

  # Fair prompt for the no-skill arm: use compare_prompt if set, else strip
  # a leading /hc-scaffold-service (and following space) from prompt.
  if [[ "$INSTALL_SKILL" == "false" ]]; then
    if [[ -n "$compare_prompt" ]]; then
      prompt="$compare_prompt"
    else
      prompt="${prompt#/hc-scaffold-service }"
      prompt="${prompt#/hc-scaffold-service}"
    fi
  fi

  # Build claude command
  claude_cmd="claude -p --verbose --output-format stream-json --permission-mode bypassPermissions"
  [[ -n "$EFFORT" ]] && claude_cmd="$claude_cmd --effort $EFFORT"
  claude_cmd="$claude_cmd '$prompt'"

  # Run in docker
  transcript_file="test/results/${scenario}-transcript.jsonl"
  export STUB_SCENARIO="$stub_scenario"

  docker-compose -f test/docker-compose.yaml run --rm ai-tdd \
    bash -c "$claude_cmd" > "$transcript_file" 2>&1 || true

  # Run assertions
  if [[ -f test/assertions/check.py ]]; then
    echo "  Checking assertions..."
    python3 test/assertions/check.py "$scenario_file" "$transcript_file"
  fi

  echo
done

echo "==> All scenarios complete"
echo "Results in test/results/"
