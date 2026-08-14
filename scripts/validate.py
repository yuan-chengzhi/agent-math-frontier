#!/usr/bin/env python3
"""Validate the hand-curated ledger and optional generated upstream indexes."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

FIT_KEYS = {
    "verifiability",
    "feedback_richness",
    "representation",
    "decomposability",
    "tool_readiness",
    "partial_value",
    "math_value",
    "status_confidence",
    "resource_feasibility",
}
GATE_KEYS = {
    "open_status",
    "exact_target",
    "verification_path",
    "valuable_partial_progress",
    "reproducibility",
}
LEVELS = {"proof_assistant", "executable_spec", "precise_informal", "research_program"}
RECOMMENDATIONS = {"shortlist", "incubate", "watch", "quarantine"}
GATE_VALUES = {"pass", "conditional", "fail", "unknown"}


class ValidationError(Exception):
    pass


def load(name: str) -> dict:
    path = DATA / name
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
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
    required = {
        "id",
        "title_zh",
        "title_en",
        "domains",
        "track",
        "stage",
        "recommendation",
        "source",
        "statement",
        "formalization",
        "verification",
        "hard_gates",
        "fit",
        "risks_zh",
        "selection_note_zh",
    }
    require(required <= problem.keys(), f"{prefix}: missing {sorted(required - problem.keys())}")
    require(problem["recommendation"] in RECOMMENDATIONS, f"{prefix}: bad recommendation")
    require(problem["stage"] in {"raw", "curated", "active", "retired"}, f"{prefix}: bad stage")
    require(problem["source"]["collection_id"] in source_ids, f"{prefix}: unknown collection")
    require(valid_url(problem["source"]["canonical_url"]), f"{prefix}: invalid canonical URL")
    try:
        checked = date.fromisoformat(problem["source"]["checked_at"])
    except (KeyError, ValueError) as exc:
        raise ValidationError(f"{prefix}: invalid checked_at") from exc
    require(checked <= date.today(), f"{prefix}: checked_at is in the future")

    formal = problem["formalization"]
    require(formal["level"] in LEVELS, f"{prefix}: bad formalization level")
    require(valid_url(formal.get("artifact_url")), f"{prefix}: invalid artifact URL")
    if formal["level"] == "proof_assistant":
        require(bool(formal.get("system")), f"{prefix}: proof-assistant system missing")
        require(bool(formal.get("artifact_url")), f"{prefix}: artifact URL missing")
        require(bool(formal.get("revision")), f"{prefix}: revision missing")
        require(bool(formal.get("declaration")), f"{prefix}: declaration missing")
        require("/blob/main/" not in formal["artifact_url"], f"{prefix}: artifact must be revision-pinned")
    else:
        require(formal.get("system") is None, f"{prefix}: non-formal target must not name a proof assistant")

    gates = problem["hard_gates"]
    require(set(gates) == GATE_KEYS, f"{prefix}: hard-gate keys differ from schema")
    for key, value in gates.items():
        require(value in GATE_VALUES, f"{prefix}: invalid gate value {key}={value}")

    fit = problem["fit"]
    require(set(fit) == FIT_KEYS, f"{prefix}: fit dimensions differ from schema")
    require("total" not in fit and "score" not in problem, f"{prefix}: scalar ranking is forbidden")
    for key, value in fit.items():
        require(isinstance(value, int) and 0 <= value <= 3, f"{prefix}: {key} must be 0..3")

    require(problem["verification"].get("independent") is True, f"{prefix}: independent verification required")
    require(bool(problem["risks_zh"]), f"{prefix}: at least one risk is required")


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
        precedents = load("precedents.json")
        quarantine = load("quarantine.json")
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
    except (ValidationError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"validation failed: {exc}", file=sys.stderr)
        return 1

    print(
        f"validated {len(ids)} curated problems, {len(source_ids)} collections, "
        f"{len(precedent_ids)} precedents and {len(quarantine_ids)} quarantine records"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
