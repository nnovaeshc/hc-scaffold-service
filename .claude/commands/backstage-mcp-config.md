---
description: Add the Backstage MCP server to Claude Code so the hc-scaffold-service skill can reach it
allowed-tools: Bash(claude mcp add:*), Bash(claude mcp get:*), Bash(claude mcp list:*)
---

Add the Backstage MCP server that `hc-scaffold-service` (and `/scaffolder-update-frontmatter`) depend on, per `README.md` and `docs/usage.md`.

1. Check whether it's already configured: `claude mcp get backstage`.
   - If it exists and is connected or just needs auth (`! Needs authentication` is fine — auth happens in-browser on first real call), report that it's already set up and stop.
2. If it's not configured, add it exactly as documented:
   ```
   claude mcp add --transport http backstage https://mcp-gateway.platform.healthcare.com/api/mcp-actions/v1
   ```
3. Report the result. Note that authentication happens in the browser via Okta on first real use, not as part of this command.
