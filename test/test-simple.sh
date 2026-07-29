#!/usr/bin/env bash
# Simple test to verify Claude works in Docker with Bedrock

set -euo pipefail

echo "==> Exporting AWS credentials..."
eval $(aws configure export-credentials --profile hc-devopstooling-prod --format env 2>/dev/null) || {
  echo "ERROR: Failed to export AWS credentials"
  echo "Run: aws sso login --profile hc-devopstooling-prod"
  exit 1
}
export AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN

echo "==> Running simple Claude test..."
docker-compose -f test/docker-compose.yaml run --rm ai-tdd \
  claude -p --permission-mode bypassPermissions "What is 2+2? Answer with just the number."
