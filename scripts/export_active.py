#!/usr/bin/env python3
"""Fail-closed, content-addressed export of the active attack portfolio."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import tempfile
from typing import Any

from contracts import (
    ACTIVE_PORTFOLIO_SCHEMA,
    ContractError,
    PROBLEM_CARD_SCHEMA,
    canonical_json_bytes,
    canonical_sha256,
    load_json,
    make_file_binding,
    validate_problem_catalog,
    validate_target_bundle,
    validate_verifier_registry,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "active-portfolio.json"


def build_active_portfolio(root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve(strict=True)
    catalog = load_json(root / "data" / "problems.json")
    registry_value = load_json(root / "data" / "verifiers.json")
    validate_problem_catalog(catalog)
    registry = validate_verifier_registry(registry_value, root=root)

    active = sorted(
        (problem for problem in catalog["problems"] if problem["stage"] == "active"),
        key=lambda problem: problem["id"],
    )
    targets: list[dict[str, object]] = []
    for problem in active:
        problem_id = problem["id"]
        gates = problem["hard_gates"]
        if any(gates[field] != "pass" for field in sorted(gates)):
            raise ContractError(
                f"active problem {problem_id!r}: every hard gate must pass"
            )
        bundle_path = root / "targets" / problem_id / "target-bundle.json"
        bundle_binding = make_file_binding(bundle_path, root=root)
        bundle = load_json(bundle_path)
        validated = validate_target_bundle(
            bundle,
            root=root,
            problem=problem,
            verifier_registry=registry,
        )
        targets.append({
            "claim_scope": validated["target_card"]["claim_scope"],
            "problem_card_sha256": canonical_sha256(problem),
            "problem_id": problem_id,
            "target_bundle": bundle_binding,
            "target_card_sha256": validated["target_card_sha256"],
            "verification_mode": validated["verification_mode"],
            "verifier_id": validated["verifier_id"],
        })

    core: dict[str, object] = {
        "as_of": catalog["as_of"],
        "problem_catalog_sha256": canonical_sha256(catalog),
        "problem_card_schema": PROBLEM_CARD_SCHEMA,
        "schema": ACTIVE_PORTFOLIO_SCHEMA,
        "source_schema_version": catalog["schema_version"],
        "targets": targets,
        "verifier_registry_sha256": canonical_sha256(registry_value),
    }
    return {
        **core,
        "portfolio_ref": "active-portfolio/sha256/" + canonical_sha256({
            "domain": "AMF_ACTIVE_PORTFOLIO_1",
            "value": core,
        }),
    }


def _atomic_write(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check",
        action="store_true",
        help="fail unless data/active-portfolio.json is the exact current canonical export",
    )
    mode.add_argument(
        "--output",
        type=Path,
        help="write the canonical export to this path instead of stdout",
    )
    args = parser.parse_args()
    try:
        portfolio = build_active_portfolio()
        body = canonical_json_bytes(portfolio) + b"\n"
        if args.check:
            if not DEFAULT_OUTPUT.is_file() or DEFAULT_OUTPUT.read_bytes() != body:
                print(
                    "active portfolio export is stale or missing: "
                    + str(DEFAULT_OUTPUT.relative_to(ROOT)),
                    file=sys.stderr,
                )
                return 1
        elif args.output is not None:
            output = args.output if args.output.is_absolute() else ROOT / args.output
            try:
                output.resolve().relative_to(ROOT.resolve())
            except ValueError as exc:
                raise ContractError("output path must stay inside the repository") from exc
            _atomic_write(output, body)
        else:
            sys.stdout.buffer.write(body)
    except ContractError as exc:
        print(f"active export failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
