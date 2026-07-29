#!/usr/bin/env python3
"""
Local result cache for the eval harness. Keys on skill content (with_skill
arm only), the scenario file, all fixtures, and harness/grading code, plus
model/effort/arm — so a scenario x arm result is reused only when everything
that could affect its outcome is unchanged. See docs/testing.md for the
harness this backs.
"""
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = REPO_ROOT / "test" / ".cache"

SKILL_FILES = [
    REPO_ROOT / "skills" / "hc-scaffold-service" / "SKILL.md",
    REPO_ROOT / "skills" / "hc-scaffold-service" / "reference.md",
    REPO_ROOT / "skills" / "hc-scaffold-service" / "examples.md",
]
HARNESS_FILES = [
    REPO_ROOT / "test" / "run.sh",
    REPO_ROOT / "test" / "assertions" / "write_workspace.py",
    REPO_ROOT / "test" / "assertions" / "check.py",
    REPO_ROOT / "test" / "scenario_lib.py",
    REPO_ROOT / "test" / "stub" / "server.py",
]


def _hash_files(paths) -> hashlib.sha256:
    h = hashlib.sha256()
    for path in sorted(paths):
        h.update(str(path.relative_to(REPO_ROOT)).encode())
        if path.exists():
            h.update(path.read_bytes())
    return h


def compute_key(scenario_path: Path, with_skill: bool, model: str, effort: str) -> str:
    fixtures = [p for p in REPO_ROOT.joinpath("test", "fixtures").rglob("*") if p.is_file()]
    h = _hash_files(HARNESS_FILES + sorted(fixtures))
    if with_skill:
        h.update(_hash_files(SKILL_FILES).digest())
    h.update(Path(scenario_path).read_bytes())
    h.update(f"|{with_skill}|{model}|{effort}".encode())
    return h.hexdigest()


def get(key: str):
    path = CACHE_DIR / f"{key}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def put(key: str, result: dict):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    result = dict(result, cached=True)
    (CACHE_DIR / f"{key}.json").write_text(json.dumps(result, indent=2) + "\n")


def main():
    import argparse

    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_key = sub.add_parser("key")
    p_key.add_argument("scenario_path")
    p_key.add_argument("with_skill", choices=["true", "false"])
    p_key.add_argument("--model", default="")
    p_key.add_argument("--effort", default="")

    p_get = sub.add_parser("get")
    p_get.add_argument("key")

    p_put = sub.add_parser("put")
    p_put.add_argument("key")
    p_put.add_argument("result_json", help="Path to a JSON file with the result to cache")

    args = parser.parse_args()

    if args.cmd == "key":
        print(compute_key(Path(args.scenario_path), args.with_skill == "true", args.model, args.effort))
    elif args.cmd == "get":
        result = get(args.key)
        if result is None:
            sys.exit(1)
        print(json.dumps(result))
    elif args.cmd == "put":
        put(args.key, json.loads(Path(args.result_json).read_text()))


if __name__ == "__main__":
    main()
