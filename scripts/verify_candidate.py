#!/usr/bin/env python3
"""Run the content-pinned verifier selected by a portfolio problem ID."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import stat
import subprocess
import sys

from contracts import ContractError, load_json, validate_verifier_registry
from export_experimental import ROOT, build_experimental_portfolio


def resolve_verifier(problem_id: str) -> tuple[dict[str, object], dict[str, object]]:
    portfolio = build_experimental_portfolio(ROOT)
    selected = next(
        (target for target in portfolio["targets"] if target["problem_id"] == problem_id),
        None,
    )
    if selected is None:
        raise ContractError(f"unknown experimental problem id {problem_id!r}")
    registry = validate_verifier_registry(
        load_json(ROOT / "data" / "verifiers.json"),
        root=ROOT,
    )
    entry = registry[selected["verifier_id"]]
    return selected, entry["manifest_value"]


def run_candidate(problem_id: str, candidate_path: Path) -> int:
    selected, manifest = resolve_verifier(problem_id)
    try:
        metadata = candidate_path.lstat()
        candidate = candidate_path.resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ContractError("candidate path is unavailable") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise ContractError("candidate must be a regular non-symlink file")

    command = list(manifest["command"])
    if command.count("{candidate_path}") != 1:
        raise ContractError("verifier manifest must contain exactly one candidate placeholder")
    command = [str(candidate) if token == "{candidate_path}" else token for token in command]
    entrypoint = (ROOT / command[0]).resolve(strict=True)
    entrypoint.relative_to(ROOT.resolve(strict=True))
    if entrypoint.suffix == ".py":
        process_command = [sys.executable, "-I", str(entrypoint), *command[1:]]
    else:
        process_command = [str(entrypoint), *command[1:]]
    working = (ROOT / manifest["working_directory"]).resolve(strict=True)

    try:
        completed = subprocess.run(
            process_command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=working,
            env={
                "LANG": "C",
                "LC_ALL": "C",
                "PATH": "/usr/bin:/bin",
                "PYTHONHASHSEED": "0",
            },
            check=False,
            timeout=manifest["timeout_seconds"],
        )
    except subprocess.TimeoutExpired as exc:
        raise ContractError(
            f"verifier {selected['verifier_id']} exceeded its pinned timeout"
        ) from exc
    maximum = manifest["maximum_output_bytes"]
    if len(completed.stdout) > maximum or len(completed.stderr) > maximum:
        raise ContractError("verifier output exceeded its pinned bound")
    if completed.stderr:
        sys.stderr.buffer.write(completed.stderr)
    sys.stdout.buffer.write(completed.stdout)
    return completed.returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("problem_id", nargs="?", help="problem ID from the experimental portfolio")
    parser.add_argument("candidate", nargs="?", type=Path, help="candidate JSON file")
    parser.add_argument("--list", action="store_true", help="list runnable problem IDs and roles")
    args = parser.parse_args()
    try:
        if args.list:
            if args.problem_id is not None or args.candidate is not None:
                raise ContractError("--list takes no problem or candidate argument")
            portfolio = build_experimental_portfolio(ROOT)
            print(json.dumps(
                [
                    {
                        "problem_id": target["problem_id"],
                        "role": target["role"],
                        "verifier_id": target["verifier_id"],
                    }
                    for target in portfolio["targets"]
                ],
                ensure_ascii=False,
                indent=2,
            ))
            return 0
        if args.problem_id is None or args.candidate is None:
            raise ContractError("problem_id and candidate are required unless --list is used")
        path = args.candidate if args.candidate.is_absolute() else Path.cwd() / args.candidate
        return run_candidate(args.problem_id, path)
    except (ContractError, OSError, ValueError) as exc:
        print(f"candidate verification failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
