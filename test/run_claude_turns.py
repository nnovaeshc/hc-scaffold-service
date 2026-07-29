#!/usr/bin/env python3
"""
Run one or more claude -p turns inside a single ai-tdd docker container so
session state (and --resume) survives between turns. Concatenates stream-json
output into one transcript.

Used by write_workspace.py and run.sh. See docs/testing.md (multi-turn replies).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent


def shell_quote(s: str) -> str:
    """Single-quote a string for bash."""
    return "'" + s.replace("'", "'\\''") + "'"


def extract_session_id(transcript_text: str) -> Optional[str]:
    """Return the first session_id found in a stream-json transcript."""
    for line in transcript_text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        sid = obj.get("session_id")
        if isinstance(sid, str) and sid:
            return sid
    return None


def build_claude_argv(
    prompt: str,
    *,
    model: str = "",
    effort: str = "",
    resume: Optional[str] = None,
) -> List[str]:
    cmd = [
        "claude",
        "-p",
        "--verbose",
        "--output-format",
        "stream-json",
        "--permission-mode",
        "bypassPermissions",
    ]
    if resume:
        cmd += ["--resume", resume]
    if model:
        cmd += ["--model", model]
    if effort:
        cmd += ["--effort", effort]
    cmd.append(prompt)
    return cmd


def _format_argv(argv: Sequence[str]) -> str:
    """Shell-quote argv; leave $SESSION unquoted so bash expands it."""
    parts = []
    for p in argv:
        if p == "$SESSION":
            parts.append('"$SESSION"')
        else:
            parts.append(shell_quote(p))
    return " ".join(parts)


def build_inner_script(
    prompt: str,
    replies: Sequence[str],
    *,
    model: str = "",
    effort: str = "",
) -> str:
    """Bash that runs turn 0 then --resume turns, writing one concatenated transcript."""
    lines = [
        "set -euo pipefail",
        "OUT=/tmp/hc-scaffold-transcript.jsonl",
        ': > "$OUT"',
        f"{_format_argv(build_claude_argv(prompt, model=model, effort=effort))} >> \"$OUT\" 2>&1 || true",
    ]
    if replies:
        lines += [
            "SESSION=$(python3 - <<'PY'",
            "import json",
            "for line in open('/tmp/hc-scaffold-transcript.jsonl'):",
            "    line=line.strip()",
            "    if not line.startswith('{'):",
            "        continue",
            "    try:",
            "        o=json.loads(line)",
            "    except Exception:",
            "        continue",
            "    sid=o.get('session_id')",
            "    if isinstance(sid,str) and sid:",
            "        print(sid)",
            "        break",
            "PY",
            ")",
            'if [[ -z "${SESSION}" ]]; then',
            '  echo "ERROR: no session_id in first-turn transcript" >&2',
            '  cat "$OUT"',
            "  exit 1",
            "fi",
        ]
        for reply in replies:
            argv = build_claude_argv(reply, model=model, effort=effort, resume="$SESSION")
            lines.append(f'{_format_argv(argv)} >> "$OUT" 2>&1 || true')
    lines.append('cat "$OUT"')
    return "\n".join(lines) + "\n"


def run_turns(
    prompt: str,
    replies: Sequence[str],
    *,
    model: str = "",
    effort: str = "",
    env: Optional[dict] = None,
    stub_scenario: str = "default",
    with_skill: bool = True,
) -> str:
    """Execute multi-turn claude in one docker-compose run; return transcript text."""
    run_env = dict(env or os.environ)
    run_env["STUB_SCENARIO"] = stub_scenario
    run_env["SKILLS_TEMPLATE"] = (
        "/work/test/skills.test.yaml" if with_skill else "/work/test/skills.none.test.yaml"
    )
    if model:
        run_env["MODEL"] = model

    inner = build_inner_script(prompt, replies, model=model, effort=effort)
    result = subprocess.run(
        [
            "docker-compose",
            "-f",
            str(REPO_ROOT / "test" / "docker-compose.yaml"),
            "run",
            "--rm",
            "ai-tdd",
            "bash",
            "-c",
            inner,
        ],
        cwd=REPO_ROOT,
        env=run_env,
        capture_output=True,
        text=True,
    )
    # Prefer stdout (cat of transcript); append stderr only when stdout empty
    if result.stdout.strip():
        return result.stdout
    return result.stdout + result.stderr


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--reply", action="append", default=[], dest="replies")
    parser.add_argument("--model", default="")
    parser.add_argument("--effort", default="")
    parser.add_argument("--stub-scenario", default="default")
    parser.add_argument("--with-skill", choices=["true", "false"], default="true")
    parser.add_argument(
        "--print-script",
        action="store_true",
        help="Print the inner bash script and exit (no docker).",
    )
    args = parser.parse_args()

    if args.print_script:
        sys.stdout.write(
            build_inner_script(args.prompt, args.replies, model=args.model, effort=args.effort)
        )
        return

    text = run_turns(
        args.prompt,
        args.replies,
        model=args.model,
        effort=args.effort,
        stub_scenario=args.stub_scenario,
        with_skill=args.with_skill == "true",
    )
    sys.stdout.write(text)


if __name__ == "__main__":
    main()
