# Usage

For engineers creating things. If you are changing the skill itself, see [design.md](design.md) and [maintaining.md](maintaining.md).

## Starting

Describe what you want in your own words. You do not need to know which template you need, or what a template is:

```
I need a new Spring Boot service for handling quote callbacks
```

```
set me up a lambda that runs on a schedule
```

You can also invoke it explicitly with `/hc-scaffold-service`, which is useful when you want to browse what is available rather than having something in mind.

Being specific up front saves questions later. Mentioning the owning team, the environments you need, or that it will sit behind the API gateway means you will not be asked about them.

## What happens

**It checks Backstage first.** Before asking you anything, the skill confirms it can actually reach Backstage and use the scaffolder. If it cannot, it tells you why and stops — it will not interview you and then fail at the last step.

**It picks a template and confirms.** You will be shown what it intends to use and why.

**It works out what it can.** Many settings have a single legal value, a sensible default, or an answer that can be looked up in the catalog. Those are filled in without bothering you. Where other services owned by your team already made a choice, that choice is proposed as a precedent, and you will be told that is where it came from.

**It checks the name is free.** Both in the Backstage catalog and on GitHub, before you invest any thought.

**It asks about the rest, one at a time.** Each question comes with a recommendation, so the fast path is usually agreeing.

**It shows you everything before submitting.** Every value is labelled with where it came from:

```
name              quote-callback-service      you said this
owner             group:default/marketplace   you said this
port              8080                        template default
environments      dev, stg                    you said this
cpuArchitecture   arm64                       other marketplace services use this
injectToServiceMesh  true                     template default
```

Read the labels. Anything marked as a default or a precedent is an assumption, not something you asked for. Change anything you want, then confirm.

**Nothing is submitted until you confirm.** There is no way to skip this, including by asking to skip it.

## After submitting

You get a task URL immediately, and a choice: watch progress, or take the URL and check back later. Nothing is blocked either way.

Creation takes anywhere from a few seconds to a couple of minutes, because it may be creating a GitHub repository, registering a catalog entry, and opening a pull request against the GitOps repo.

What you get at the end depends on the template. Some create a repository and a catalog entry. Others only open a pull request — **that pull request still needs review and merge before anything deploys.** The skill tells you which outcome you got rather than assuming.

## Troubleshooting

**"No Backstage catalog tool is available"** — the MCP server is not configured in your client. Add it:

```bash
claude mcp add --transport http backstage \
  https://mcp-gateway.platform.healthcare.com/api/mcp-actions/v1
```

**"Access was denied"** — your session has expired, or you lack permission. Open Backstage in a browser and log in, then retry. If Backstage works in the browser and this does not, it is a permissions issue worth raising with the platform team; include which call was refused, since the skill names it.

**"The catalog has no templates"** — the connection works but Backstage returned nothing. This is a Backstage-side problem, not a client one.

**A template needs to be completed in the Backstage UI** — it declares secrets. Credentials are not passed through a chat, so use the web form for that template.

**A task failed partway** — you get the failing step and a log excerpt. The skill deliberately does not retry, because earlier steps have already had effects: a repository may exist, or a pull request may be open. Check what was created before resubmitting, or you will end up with duplicates.

**It is asking more questions than you expected** — that means it could not derive the answers. A template with no defaults and no precedent in the catalog genuinely needs input. Giving more context up front reduces this.

## Things it will not do

It will not scaffold anything outside a template. If nothing fits what you asked for, it says so rather than hand-rolling files, because a hand-rolled service skips the CI, GitOps and catalog wiring that templates exist to provide.

It will not retry a failed task automatically, or work around an access denial by trying another route.
