#!/usr/bin/env python3
"""Export every machine-addressable card as an experimental portfolio.

Unlike ``export_active.py``, this exporter intentionally does not pretend that
independent reviews, novelty checks, red-team receipts, and frozen budgets have
already happened.  It requires a frozen target card, candidate schema, and a
registered exact verifier for every proof-assistant or executable-spec problem.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import tempfile
from typing import Any

from contracts import (
    ContractError,
    EXPERIMENTAL_PORTFOLIO_SCHEMA,
    PROBLEM_CARD_SCHEMA,
    canonical_json_bytes,
    canonical_sha256,
    load_json,
    make_file_binding,
    validate_problem_catalog,
    validate_target_card,
    validate_verifier_registry,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "experimental-portfolio.json"
MACHINE_LEVELS = frozenset({"proof_assistant", "executable_spec"})


def _role(problem: dict[str, Any], target: dict[str, Any]) -> str:
    if problem["stage"] == "active":
        return "audited_active"
    if target["verifier_id"] == "amf.aim60.certificate.v1":
        return "verifier_regression_only"
    return "experimental_active"


def build_experimental_portfolio(root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve(strict=True)
    catalog = load_json(root / "data" / "problems.json")
    registry_value = load_json(root / "data" / "verifiers.json")
    validate_problem_catalog(catalog)
    registry = validate_verifier_registry(registry_value, root=root)

    selected = sorted(
        (
            problem
            for problem in catalog["problems"]
            if problem["formalization"]["level"] in MACHINE_LEVELS
        ),
        key=lambda problem: problem["id"],
    )
    targets: list[dict[str, object]] = []
    role_counts = {
        "audited_active": 0,
        "experimental_active": 0,
        "verifier_regression_only": 0,
    }
    for problem in selected:
        problem_id = problem["id"]
        problem_hash = canonical_sha256(problem)
        target_path = root / "targets" / problem_id / "target-card.json"
        target_binding = make_file_binding(target_path, root=root)
        target = validate_target_card(
            load_json(target_path),
            root=root,
            expected_problem_id=problem_id,
            expected_problem_card_sha256=problem_hash,
            expected_source_revision=problem["formalization"]["revision"],
        )
        verifier = registry.get(target["verifier_id"])
        if verifier is None:
            raise ContractError(
                f"experimental problem {problem_id!r}: unregistered verifier "
                f"{target['verifier_id']!r}"
            )
        mode = problem["verification"]["mode"]
        if verifier["manifest_value"]["binds_verification_mode"] != mode:
            raise ContractError(
                f"experimental problem {problem_id!r}: verifier mode mismatch"
            )
        role = _role(problem, target)
        role_counts[role] += 1
        targets.append({
            "claim_scope": target["claim_scope"],
            "formalization_level": problem["formalization"]["level"],
            "hard_gates": dict(problem["hard_gates"]),
            "problem_card_sha256": problem_hash,
            "problem_id": problem_id,
            "role": role,
            "strict_stage": problem["stage"],
            "target_card": target_binding,
            "verification_mode": mode,
            "verifier_id": target["verifier_id"],
        })

    core: dict[str, object] = {
        "as_of": catalog["as_of"],
        "problem_card_schema": PROBLEM_CARD_SCHEMA,
        "problem_catalog_sha256": canonical_sha256(catalog),
        "schema": EXPERIMENTAL_PORTFOLIO_SCHEMA,
        "source_schema_version": catalog["schema_version"],
        "summary": {**role_counts, "total": len(targets)},
        "targets": targets,
        "verifier_registry_sha256": canonical_sha256(registry_value),
    }
    return {
        **core,
        "portfolio_ref": "experimental-portfolio/sha256/" + canonical_sha256({
            "domain": EXPERIMENTAL_PORTFOLIO_SCHEMA,
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
        help="fail unless data/experimental-portfolio.json is the exact canonical export",
    )
    mode.add_argument(
        "--output",
        type=Path,
        help="write the canonical export to this path instead of stdout",
    )
    args = parser.parse_args()
    try:
        portfolio = build_experimental_portfolio()
        body = canonical_json_bytes(portfolio) + b"\n"
        if args.check:
            if not DEFAULT_OUTPUT.is_file() or DEFAULT_OUTPUT.read_bytes() != body:
                print(
                    "experimental portfolio export is stale or missing: "
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
        print(f"experimental export failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
