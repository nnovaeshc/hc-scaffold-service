---
description: Sync the hc-scaffold-service skill's trigger phrases with the live Backstage scaffolder catalog
allowed-tools: mcp__backstage__authenticate, mcp__backstage__complete_authentication, ToolSearch, Read, Edit, Bash(git diff:*), Bash(git checkout:*), Bash(git add:*), Bash(git commit:*), Bash(git push:*), AskUserQuestion
---

Sync the trigger-phrase list in `skills/hc-scaffold-service/SKILL.md`'s frontmatter `description` with the templates actually available on the live Backstage scaffolder, so the skill auto-invokes for template kinds that exist today (e.g. a live "github-repo" template should make "create a new github repository" trigger this skill instead of the GitHub MCP/`gh` CLI).

Do this exactly, in order:

## 1. Get live scaffolder templates via the Backstage MCP

- Try calling a Backstage MCP tool that lists Scaffolder templates (catalog entities of kind `Template`). If no such tool is loaded yet, run `ToolSearch` with a query like "backstage template catalog scaffolder" to find and load it.
- If the only Backstage tools available are `mcp__backstage__authenticate` / `mcp__backstage__complete_authentication`, the server isn't authenticated yet:
  1. Call `mcp__backstage__authenticate`.
  2. Show the returned authorization URL to the user and ask them to open it, approve, and paste back the resulting `http://localhost:<port>/callback?...` URL.
  3. Call `mcp__backstage__complete_authentication` with that callback URL.
  4. Re-run `ToolSearch` to pick up the newly available tools, then list templates.
- Collect each template's name, title, description, and tags.

## 2. Derive candidate trigger phrases

For each template, derive 1-3 short, natural phrasings a user would actually type to request it (e.g. a `github-repo` template → "new github repository", "create a github repo"). Base these on the template's title/description/tags, not just its machine name.

## 3. Merge into SKILL.md frontmatter

- Read `skills/hc-scaffold-service/SKILL.md` (the copy on this branch — not any path under `.claude/worktrees/`).
- The frontmatter `description` uses **INVOKE FOR** / **SKIP** framing (skill-creator tune): a WHAT sentence, then `INVOKE FOR …` (when to activate, with example phrasings), then `SKIP …` (false-positive guards). Only extend the **INVOKE FOR** clause with new natural phrasings derived from live templates. Do not rewrite WHAT or SKIP unless a new phrase would clearly collide with an existing SKIP case — in that case, add a matching `should_not_trigger` row in `skills/hc-scaffold-service/evals/triggers.json` and mention it when you ask the user.
- Merge candidate phrases into the INVOKE FOR examples/list, de-duplicating case-insensitively. Prefer short natural requests (“create a github repo”) over machine template names. Do not remove existing INVOKE FOR cues.
- Use `Edit` to apply the change to the frontmatter only. Do not modify any other part of the file.
- After Keep, remind the user to re-run skill-creator triggers (step 6) — catalog sync changes activation wording.

## 4. Show the diff

Run `git diff -- skills/hc-scaffold-service/SKILL.md` and show the output to the user.

## 5. Ask what to do with the change

Use `AskUserQuestion` with exactly these three options:
- **Keep and commit** — stage and commit only `skills/hc-scaffold-service/SKILL.md` with a concise commit message (e.g. `skill: sync trigger phrases with live scaffolder catalog`), then push the current branch to its remote.
- **Keep but don't commit** — leave the file modified on disk, uncommitted. Do nothing further.
- **Discard changes** — run `git checkout -- skills/hc-scaffold-service/SKILL.md` to revert.

## 6. After Keep (commit or not): remind about skill-creator triggers

If the user chose either Keep option and the frontmatter `description` actually changed, tell them they must re-run interactive skill-creator triggers before treating activation as verified — the stub harness does not grade triggering. Point them at [docs/triggers.md](../../docs/triggers.md) and print:

```bash
task test:skill-creator:install
task test:skill-creator:triggers
```

If new phrases are broad (e.g. “create a github repo”), also suggest adding matching `should_not_trigger` rows in `skills/hc-scaffold-service/evals/triggers.json` before that tune.

Only commit if the user picks "Keep and commit", and only push after that commit succeeds. Never commit or push on any other path.
