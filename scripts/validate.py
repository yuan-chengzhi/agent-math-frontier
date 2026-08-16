#!/usr/bin/env python3
"""Validate the hand-curated ledger and optional generated upstream indexes."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import urlparse

from contracts import (
    ContractError,
    load_json,
    validate_problem_card,
    validate_problem_catalog,
    validate_verifier_registry,
)


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


class ValidationError(Exception):
    pass


def load(name: str) -> dict:
    path = DATA / name
    try:
        return load_json(path)
    except (OSError, ContractError) as exc:
        raise ValidationError(f"{path}: {exc}") from exc


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def valid_url(value: str | None) -> bool:
    if value is None:
        return True
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def validate_problem(problem: dict, source_ids: set[str]) -> None:
    prefix = f"problem {problem.get('id', '<missing-id>')}"
    try:
        validate_problem_card(problem, label=prefix)
    except ContractError as exc:
        raise ValidationError(str(exc)) from exc
    require(problem["source"]["collection_id"] in source_ids, f"{prefix}: unknown collection")
    require(valid_url(problem["source"]["canonical_url"]), f"{prefix}: invalid canonical URL")


def validate_generated_indexes() -> None:
    erdos_path = DATA / "upstream" / "erdos-problems.json"
    formal_path = DATA / "upstream" / "formal-conjectures-open.json"
    if erdos_path.exists():
        erdos = json.loads(erdos_path.read_text(encoding="utf-8"))
        require(len(erdos.get("problems", [])) >= 1000, "Erdős generated index is unexpectedly small")
        numbers = [item["number"] for item in erdos["problems"]]
        require(len(numbers) == len(set(numbers)), "Erdős generated index has duplicate numbers")
    if formal_path.exists():
        formal = json.loads(formal_path.read_text(encoding="utf-8"))
        require(len(formal.get("declarations", [])) >= 500, "Formal Conjectures index is unexpectedly small")
        keys = [(item["path"], item["declaration"]) for item in formal["declarations"]]
        require(len(keys) == len(set(keys)), "Formal Conjectures index has duplicate declarations")


def main() -> int:
    try:
        sources = load("sources.json")
        problems = load("problems.json")
        verifiers = load("verifiers.json")
        precedents = load("precedents.json")
        quarantine = load("quarantine.json")
        validate_problem_catalog(problems)
        validate_verifier_registry(verifiers, root=ROOT)
        source_ids = {item["id"] for item in sources["collections"]}
        require(len(source_ids) == len(sources["collections"]), "duplicate collection IDs")

        ids: list[str] = []
        for problem in problems["problems"]:
            validate_problem(problem, source_ids)
            ids.append(problem["id"])
        require(len(ids) == len(set(ids)), "duplicate problem IDs")

        precedent_ids = [item["id"] for item in precedents["precedents"]]
        require(len(precedent_ids) == len(set(precedent_ids)), "duplicate precedent IDs")
        for item in precedents["precedents"]:
            require(valid_url(item["url"]), f"precedent {item['id']}: invalid URL")

        quarantine_ids = [item["id"] for item in quarantine["items"]]
        require(len(quarantine_ids) == len(set(quarantine_ids)), "duplicate quarantine IDs")
        for item in quarantine["items"]:
            require(all(valid_url(url) for url in item["sources"]), f"quarantine {item['id']}: invalid URL")

        validate_generated_indexes()
    except (ValidationError, ContractError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"validation failed: {exc}", file=sys.stderr)
        return 1

    print(
        f"validated {len(ids)} curated problems, {len(source_ids)} collections, "
        f"{len(precedent_ids)} precedents and {len(quarantine_ids)} quarantine records"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
