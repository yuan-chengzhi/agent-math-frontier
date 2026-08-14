#!/usr/bin/env python3
"""Compile one reviewed PMW activation plan into content-addressed evidence.

This is deliberately an offline, zero-model compiler.  It never invents
reviewer authority or session evidence, never refreshes status from the web,
and never silently replaces evidence.  ``--check`` and ``--write`` both run
the frozen verifier and red-team test modules inside a no-network macOS
Seatbelt before comparing or installing canonical outputs.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime, timezone
import errno
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tempfile
from typing import Any, Callable, NoReturn
from urllib.parse import urlparse

from contracts import (
    ACTIVE_PORTFOLIO_SCHEMA,
    BASELINE_RECEIPT_SCHEMA,
    BUDGET_RECEIPT_SCHEMA,
    ContractError,
    PROBLEM_CARD_SCHEMA,
    RED_TEAM_RECEIPT_SCHEMA,
    REVIEW_ATTESTATION_SCOPE,
    REVIEW_RECEIPT_SCHEMA,
    TARGET_BUNDLE_SCHEMA,
    canonical_json_bytes,
    canonical_sha256,
    load_json,
    make_file_binding,
    raw_sha256,
    validate_baseline_receipt,
    validate_budget_receipt,
    validate_problem_catalog,
    validate_red_team_receipt,
    validate_review_receipt,
    validate_target_bundle,
    validate_target_card,
    validate_verifier_registry,
)
from export_active import build_active_portfolio


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PLAN = ROOT / "activation" / "pmw-frontier-choice-2026-08-14.json"
PLAN_SCHEMA = "AMF_ACTIVATION_PLAN_1"
BRIEF_SCHEMA = "AMF_AGENT_BASELINE_BRIEF_1"
AUTHORITY_SCHEMA = "AMF_CODEX_REVIEWER_AUTHORITY_1"
SESSION_SCHEMA = "AMF_CODEX_REVIEW_SESSION_EVIDENCE_1"
ACTIVATION_ID = "pmw-frontier-choice-2026-08-14"
CHECKED_AT = "2026-08-14"

EXACT_LIMITS = {
    "context_tokens": 1_050_000,
    "input_tokens": 922_000,
    "model_calls": 2,
    "output_tokens": 128_000,
    "tool_calls": 512,
    "verifier_calls": 8,
    "wall_ms": 15_600_000,
}
EXACT_MAXIMUM_ARTIFACT_BYTES = 67_108_864
EXACT_STOP_CONDITIONS = (
    "Each life uses exactly one persistent Pi RPC session with at most two charged provider turns: S0 then S1.",
    "S0 stops after 1,200,000 wall-clock milliseconds or 24 tool calls, whichever occurs first.",
    "S1 stops after 14,400,000 wall-clock milliseconds; the complete life stops after 15,600,000 wall-clock milliseconds or 512 cumulative tool calls, whichever occurs first.",
    "The life stops before provider input exceeds 922,000 tokens or context occupancy reaches the separately frozen hard-stop threshold; the configured context window is 1,050,000 tokens.",
    "Each provider turn may request at most 128,000 output tokens, and the complete life may invoke its target verifier at most 8 times.",
    "No automatic retry, replacement life, context compaction, or host-authored summary is permitted.",
    "A verifier timeout, resource ceiling, implementation disagreement, or other apparatus failure is inconclusive and is not mathematical rejection.",
    "No receipt or target bundle grants model-launch or provider-billing authority.",
)
TEST_TIMEOUT_SECONDS = 1_200
TEST_OUTPUT_LIMIT = 1_048_576
FORBIDDEN_BRIEF_FIELDS = frozenset({
    "fit", "recommendation", "selection_note", "selection_note_zh"
})
IDENTIFIER_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
TASK_PATH_RE = re.compile(r"^/root/[a-z0-9][a-z0-9_-]{0,127}$")


@dataclass(frozen=True)
class TargetSpec:
    problem_id: str
    verifier_id: str
    baseline_id: str
    baseline_description: str
    baseline_artifacts: tuple[str, ...]
    statement_report: str
    open_status_report: str
    red_team_corpus: str
    red_team_report: str
    test_modules: tuple[str, str]


TARGET_SPECS: dict[str, TargetSpec] = {
    "degree-diameter-3-9-record": TargetSpec(
        problem_id="degree-diameter-3-9-record",
        verifier_id="amf.dd39.exact.v1",
        baseline_id="dd39-maintained-order-600-2026-08-14",
        baseline_description=(
            "Frozen factual record and provenance metadata, a neutral agent baseline "
            "brief, and repository-owned conversion code. No third-party raw or "
            "normalized adjacency list is redistributed or bound."
        ),
        baseline_artifacts=(
            "targets/degree-diameter-3-9-record/evidence/baseline/agent-brief.json",
            "targets/degree-diameter-3-9-record/evidence/baseline/convert_implicit.py",
            "targets/degree-diameter-3-9-record/evidence/baseline/source-metadata.json",
        ),
        statement_report=(
            "targets/degree-diameter-3-9-record/evidence/reviews/"
            "statement-fidelity-codex-2026-08-14.md"
        ),
        open_status_report=(
            "targets/degree-diameter-3-9-record/evidence/reviews/"
            "open-status-codex-2026-08-14.md"
        ),
        red_team_corpus=(
            "targets/degree-diameter-3-9-record/evidence/red-team/"
            "corpus-codex-2026-08-14.json"
        ),
        red_team_report=(
            "targets/degree-diameter-3-9-record/evidence/red-team/"
            "report-codex-2026-08-14.md"
        ),
        test_modules=("tests.test_dd39_verifier", "tests.test_dd39_red_team"),
    ),
    "erdos-64": TargetSpec(
        problem_id="erdos-64",
        verifier_id="amf.erdos64.counterexample.v1",
        baseline_id="erdos64-frontier-baselines-2026-08-14",
        baseline_description=(
            "Frozen source metadata, neutral frontier-route brief, and the pinned "
            "upstream Lean statement snapshot; the snapshot contains sorry and is "
            "not treated as root-proof evidence."
        ),
        baseline_artifacts=(
            "targets/erdos-64/evidence/baseline/agent-brief.json",
            "targets/erdos-64/evidence/baseline/source-metadata.json",
            "targets/erdos-64/evidence/sources/FormalConjectures-Erdos64-b33d8678.lean",
        ),
        statement_report=(
            "targets/erdos-64/evidence/reviews/"
            "statement-fidelity-codex-2026-08-14.md"
        ),
        open_status_report=(
            "targets/erdos-64/evidence/reviews/open-status-codex-2026-08-14.md"
        ),
        red_team_corpus=(
            "targets/erdos-64/evidence/red-team/corpus-codex-2026-08-14.json"
        ),
        red_team_report=(
            "targets/erdos-64/evidence/red-team/report-codex-2026-08-14.md"
        ),
        test_modules=("tests.test_erdos64_verifier", "tests.test_erdos64_red_team"),
    ),
    "frontier-stretched-lr": TargetSpec(
        problem_id="frontier-stretched-lr",
        verifier_id="amf.stretched-lr.exact.v1",
        baseline_id="stretched-lr-frontier-baselines-2026-08-14",
        baseline_description=(
            "Frozen source metadata and a neutral agent brief recording the exact "
            "bounded task and known route baselines through 2026-08-14."
        ),
        baseline_artifacts=(
            "targets/frontier-stretched-lr/evidence/baseline/agent-brief.json",
            "targets/frontier-stretched-lr/evidence/baseline/source-metadata.json",
        ),
        statement_report=(
            "targets/frontier-stretched-lr/evidence/reviews/"
            "statement-fidelity-codex-2026-08-14.md"
        ),
        open_status_report=(
            "targets/frontier-stretched-lr/evidence/reviews/"
            "open-status-codex-2026-08-14.md"
        ),
        red_team_corpus=(
            "targets/frontier-stretched-lr/evidence/red-team/"
            "corpus-codex-2026-08-14.json"
        ),
        red_team_report=(
            "targets/frontier-stretched-lr/evidence/red-team/"
            "report-codex-2026-08-14.md"
        ),
        test_modules=(
            "tests.test_stretched_lr_verifier",
            "tests.test_stretched_lr_red_team",
        ),
    ),
}
ALLOWED_TARGETS = tuple(sorted(TARGET_SPECS))
FORBIDDEN_TARGET = "aim-60-first-prime"

STATEMENT_REVIEWER = {
    "axis": "STATEMENT_FIDELITY",
    "reviewer_id": "codex-subagent-statement-review-2026-08-14",
    "reviewer_task_path": "/root/statement_review",
}
OPEN_STATUS_REVIEWER = {
    "axis": "OPEN_STATUS_AND_NOVELTY",
    "reviewer_id": "codex-subagent-open-status-review-2026-08-14",
    "reviewer_task_path": "/root/open_status_review",
}
RED_TEAM_REVIEWER_ID = "codex-verifier-red-team-2026-08-14"


class ActivationError(ContractError):
    """A stable fail-closed activation error."""


def _fail(label: str, message: str) -> NoReturn:
    raise ActivationError(f"{label}: {message}")


def _exact(value: object, fields: frozenset[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or frozenset(value) != fields:
        actual = sorted(value) if type(value) is dict else type(value).__name__
        _fail(label, f"expected exact fields {sorted(fields)}, got {actual}")
    return dict(value)


def _text(value: object, label: str, *, maximum: int = 65_536) -> str:
    if type(value) is not str or not value or "\x00" in value:
        _fail(label, "must be non-empty NUL-free text")
    try:
        size = len(value.encode("utf-8", errors="strict"))
    except UnicodeError as exc:
        raise ActivationError(f"{label}: invalid UTF-8") from exc
    if size > maximum:
        _fail(label, f"must be at most {maximum} UTF-8 bytes")
    return value


def _iso_date(value: object, label: str) -> str:
    text = _text(value, label, maximum=10)
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise ActivationError(f"{label}: must be an ISO date") from exc
    if parsed > date.today():
        _fail(label, "must not be in the future")
    return text


def _iso_datetime(value: object, label: str) -> str:
    text = _text(value, label, maximum=64)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ActivationError(f"{label}: must be an ISO-8601 datetime") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        _fail(label, "must include an explicit UTC offset")
    if parsed.astimezone(timezone.utc) > datetime.now(timezone.utc):
        _fail(label, "must not be in the future")
    return text


def _limitations(value: object, label: str) -> tuple[str, ...]:
    if type(value) is not list or not 1 <= len(value) <= 16:
        _fail(label, "must be a non-empty list of at most 16 limitations")
    result = tuple(_text(item, f"{label}[{index}]", maximum=4_000) for index, item in enumerate(value))
    if len(result) != len(set(result)):
        _fail(label, "must not contain duplicate limitations")
    return result


def _relative(value: object, label: str) -> str:
    text = _text(value, label, maximum=512)
    if "\\" in text:
        _fail(label, "must use POSIX separators")
    pure = PurePosixPath(text)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        _fail(label, "must be a normalized repository-relative path")
    if pure.as_posix() != text:
        _fail(label, "must be normalized")
    return text


def _regular_text(path: Path, *, label: str) -> str:
    try:
        metadata = path.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            _fail(label, "must be a regular non-symlink file")
        raw = path.read_bytes()
    except OSError as exc:
        raise ActivationError(f"{label}: unavailable: {exc}") from exc
    if len(raw) != metadata.st_size or not raw:
        _fail(label, "must be stable and non-empty")
    try:
        return raw.decode("utf-8", errors="strict")
    except UnicodeError as exc:
        raise ActivationError(f"{label}: invalid UTF-8") from exc


def _review_process_paths(problem_id: str, kind: str) -> tuple[str, str]:
    prefix = f"targets/{problem_id}/evidence/reviews/process"
    if kind == "statement":
        return (
            f"{prefix}/statement-authority-2026-08-14.json",
            f"{prefix}/statement-session-2026-08-14.json",
        )
    if kind == "open_status":
        return (
            f"{prefix}/open-status-authority-2026-08-14.json",
            f"{prefix}/open-status-session-2026-08-14.json",
        )
    raise AssertionError(kind)


def _expected_plan_target(spec: TargetSpec) -> dict[str, object]:
    statement_authority, statement_session = _review_process_paths(
        spec.problem_id, "statement"
    )
    open_authority, open_session = _review_process_paths(spec.problem_id, "open_status")
    return {
        "problem_id": spec.problem_id,
        "baseline": {
            "baseline_id": spec.baseline_id,
            "description": spec.baseline_description,
            "artifacts": list(spec.baseline_artifacts),
        },
        "reviews": {
            "statement": {
                **STATEMENT_REVIEWER,
                "review_id": f"{spec.problem_id}-statement-fidelity-2026-08-14",
                "verdict": "PASS",
                "report": spec.statement_report,
                "reviewer_authority": statement_authority,
                "review_session_evidence": statement_session,
            },
            "open_status": {
                **OPEN_STATUS_REVIEWER,
                "review_id": f"{spec.problem_id}-open-status-2026-08-14",
                "verdict": "PASS",
                "report": spec.open_status_report,
                "reviewer_authority": open_authority,
                "review_session_evidence": open_session,
            },
        },
        "red_team": {
            "reviewer_id": RED_TEAM_REVIEWER_ID,
            "corpus": spec.red_team_corpus,
            "report": spec.red_team_report,
        },
        "test_modules": list(spec.test_modules),
    }


def validate_plan(value: object) -> dict[str, Any]:
    plan = _exact(
        value,
        frozenset({
            "schema", "activation_id", "checked_at", "execution_policy",
            "budget", "targets",
        }),
        "activation_plan",
    )
    if plan["schema"] != PLAN_SCHEMA:
        _fail("activation_plan.schema", f"must be {PLAN_SCHEMA}")
    if plan["activation_id"] != ACTIVATION_ID:
        _fail("activation_plan.activation_id", f"must be {ACTIVATION_ID}")
    if _iso_date(plan["checked_at"], "activation_plan.checked_at") != CHECKED_AT:
        _fail("activation_plan.checked_at", f"must be {CHECKED_AT}")
    policy = _exact(
        plan["execution_policy"],
        frozenset({"network", "model_calls", "test_timeout_seconds"}),
        "activation_plan.execution_policy",
    )
    if policy != {
        "network": False,
        "model_calls": 0,
        "test_timeout_seconds": TEST_TIMEOUT_SECONDS,
    }:
        _fail("activation_plan.execution_policy", "must equal the frozen offline policy")
    budget = _exact(
        plan["budget"],
        frozenset({"limits", "maximum_artifact_bytes", "retain_failures", "stop_conditions"}),
        "activation_plan.budget",
    )
    if budget["limits"] != EXACT_LIMITS:
        _fail("activation_plan.budget.limits", "must equal the frozen runtime caps")
    if budget["maximum_artifact_bytes"] != EXACT_MAXIMUM_ARTIFACT_BYTES:
        _fail("activation_plan.budget.maximum_artifact_bytes", "does not equal runtime")
    if budget["retain_failures"] is not True:
        _fail("activation_plan.budget.retain_failures", "must be true")
    if budget["stop_conditions"] != list(EXACT_STOP_CONDITIONS):
        _fail("activation_plan.budget.stop_conditions", "must equal the eight frozen conditions in order")
    targets = plan["targets"]
    if type(targets) is not list:
        _fail("activation_plan.targets", "must be a list")
    ids = [item.get("problem_id") if type(item) is dict else None for item in targets]
    if ids != list(ALLOWED_TARGETS) or len(ids) != len(set(ids)):
        _fail(
            "activation_plan.targets",
            f"must be exactly the sorted, unique allowlist {list(ALLOWED_TARGETS)}",
        )
    for index, item in enumerate(targets):
        expected = _expected_plan_target(TARGET_SPECS[ids[index]])
        if item != expected:
            _fail(
                f"activation_plan.targets[{index}]",
                "must exactly equal the frozen target declaration",
            )
    if any(FORBIDDEN_TARGET in canonical_json_bytes(item).decode("utf-8") for item in targets):
        _fail("activation_plan.targets", "quarantined AIM target is forbidden")
    return plan


def validate_agent_brief(
    value: object, *, problem_id: str, checked_at: str
) -> set[str]:
    brief = _exact(
        value,
        frozenset({
            "schema", "problem_id", "as_of", "status_statement", "baseline_facts",
            "known_route_baselines", "verification_caveats", "provenance_caveats",
        }),
        f"agent_brief[{problem_id}]",
    )
    if brief["schema"] != BRIEF_SCHEMA or brief["problem_id"] != problem_id:
        _fail(f"agent_brief[{problem_id}]", "schema/problem binding mismatch")
    if _iso_date(brief["as_of"], f"agent_brief[{problem_id}].as_of") != checked_at:
        _fail(f"agent_brief[{problem_id}].as_of", "must equal activation date")

    def reject_fields(node: object, label: str) -> None:
        if type(node) is dict:
            forbidden = FORBIDDEN_BRIEF_FIELDS.intersection(node)
            if forbidden:
                _fail(label, f"agent-visible selection fields forbidden: {sorted(forbidden)}")
            for key, child in node.items():
                reject_fields(child, f"{label}.{key}")
        elif type(node) is list:
            for index, child in enumerate(node):
                reject_fields(child, f"{label}[{index}]")

    reject_fields(brief, f"agent_brief[{problem_id}]")
    _text(brief["status_statement"], f"agent_brief[{problem_id}].status_statement", maximum=4_000)
    for field in ("baseline_facts", "verification_caveats", "provenance_caveats"):
        values = brief[field]
        if type(values) is not list or not 1 <= len(values) <= 16 or len(values) != len(set(values)):
            _fail(f"agent_brief[{problem_id}].{field}", "must be a unique non-empty list of 1..16 items")
        for index, item in enumerate(values):
            _text(item, f"agent_brief[{problem_id}].{field}[{index}]", maximum=4_000)
    routes = brief["known_route_baselines"]
    if type(routes) is not list or len(routes) > 32:
        _fail(f"agent_brief[{problem_id}].known_route_baselines", "must contain at most 32 routes")
    ids: set[str] = set()
    for index, value in enumerate(routes):
        route = _exact(
            value,
            frozenset({"id", "scope", "result", "source", "research_consequence"}),
            f"agent_brief[{problem_id}].known_route_baselines[{index}]",
        )
        route_id = _text(route["id"], f"agent_brief[{problem_id}].route[{index}].id", maximum=128)
        if IDENTIFIER_RE.fullmatch(route_id) is None or route_id in ids:
            _fail(f"agent_brief[{problem_id}].route[{index}].id", "must be grammatical and unique")
        ids.add(route_id)
        for field, maximum in (("scope", 2_000), ("result", 4_000), ("research_consequence", 4_000)):
            _text(route[field], f"agent_brief[{problem_id}].route[{index}].{field}", maximum=maximum)
        source = _text(route["source"], f"agent_brief[{problem_id}].route[{index}].source", maximum=2_048)
        parsed = urlparse(source)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            _fail(f"agent_brief[{problem_id}].route[{index}].source", "must be an absolute credential-free HTTPS URL")
    return ids


def _validate_authority(
    value: object,
    *,
    problem_id: str,
    reviewer_id: str,
    reviewer_task_path: str,
    axis: str,
) -> None:
    authority = _exact(
        value,
        frozenset({
            "schema", "reviewer_id", "authority_kind", "reviewer_task_path",
            "problem_id", "axis", "solver_role", "domain_expert_claimed",
            "external_identity_verified", "cryptographic_signature_present",
            "attestation_scope", "recorded_at", "limitations",
        }),
        "reviewer_authority",
    )
    expected = {
        "schema": AUTHORITY_SCHEMA,
        "reviewer_id": reviewer_id,
        "authority_kind": "HOST_ASSIGNED_CODEX_SUBAGENT_ROLE",
        "reviewer_task_path": reviewer_task_path,
        "problem_id": problem_id,
        "axis": axis,
        "solver_role": False,
        "domain_expert_claimed": False,
        "external_identity_verified": False,
        "cryptographic_signature_present": False,
        "attestation_scope": "PROCESS_PROVENANCE_ONLY_NOT_MATHEMATICAL_TRUTH",
    }
    if any(authority.get(key) != expected_value for key, expected_value in expected.items()):
        _fail("reviewer_authority", "does not exactly bind the honest assigned authority")
    if TASK_PATH_RE.fullmatch(reviewer_task_path) is None:
        _fail("reviewer_authority.reviewer_task_path", "invalid host task path")
    _iso_datetime(authority["recorded_at"], "reviewer_authority.recorded_at")
    _limitations(authority["limitations"], "reviewer_authority.limitations")


def _validate_session(
    value: object,
    *,
    problem_id: str,
    reviewer_id: str,
    reviewer_task_path: str,
    axis: str,
    verdict: str,
    report_path: str,
    report_sha256: str,
    problem_card_sha256: str,
    target_card_sha256: str,
) -> None:
    session = _exact(
        value,
        frozenset({
            "schema", "reviewer_id", "reviewer_task_path", "problem_id", "axis",
            "verdict", "report_path", "report_sha256", "reviewed_problem_card_sha256",
            "reviewed_target_card_sha256", "solver_lives_started_at_review",
            "completion_observed_by_host", "session_reference_kind",
            "provider_session_id", "transcript_ref", "recorded_at", "limitations",
        }),
        "review_session_evidence",
    )
    expected = {
        "schema": SESSION_SCHEMA,
        "reviewer_id": reviewer_id,
        "reviewer_task_path": reviewer_task_path,
        "problem_id": problem_id,
        "axis": axis,
        "verdict": verdict,
        "report_path": report_path,
        "report_sha256": report_sha256,
        "reviewed_problem_card_sha256": problem_card_sha256,
        "reviewed_target_card_sha256": target_card_sha256,
        "solver_lives_started_at_review": 0,
        "completion_observed_by_host": True,
        "session_reference_kind": "CONVERSATION_LOCAL_TASK_PATH",
        "provider_session_id": None,
        "transcript_ref": None,
    }
    if any(session.get(key) != expected_value for key, expected_value in expected.items()):
        _fail("review_session_evidence", "does not exactly bind the completed review process")
    _iso_datetime(session["recorded_at"], "review_session_evidence.recorded_at")
    _limitations(session["limitations"], "review_session_evidence.limitations")


def _virtual_binding(path: str, body: bytes) -> dict[str, object]:
    return {"path": path, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def _receipt_paths(problem_id: str) -> dict[str, str]:
    prefix = f"targets/{problem_id}/evidence/receipts"
    return {
        "baseline": f"{prefix}/baseline-{ACTIVATION_ID}.json",
        "statement": f"{prefix}/review-statement-{ACTIVATION_ID}.json",
        "open_status": f"{prefix}/review-open-status-{ACTIVATION_ID}.json",
        "red_team": f"{prefix}/red-team-{ACTIVATION_ID}.json",
        "budget": f"{prefix}/budget-{ACTIVATION_ID}.json",
        "bundle": f"targets/{problem_id}/target-bundle.json",
    }


@dataclass(frozen=True)
class PreparedActivation:
    outputs: dict[str, bytes]
    input_manifest_sha256: str
    test_modules: dict[str, tuple[str, str]]


def _input_manifest(root: Path, relative_paths: set[str]) -> tuple[str, dict[str, object]]:
    bindings = [make_file_binding(root / path, root=root) for path in sorted(relative_paths)]
    manifest = {
        "schema": "AMF_ACTIVATION_INPUT_MANIFEST_1",
        "activation_id": ACTIVATION_ID,
        "files": bindings,
    }
    return canonical_sha256(manifest), manifest


def _validate_report(
    root: Path,
    *,
    relative_path: str,
    kind: str,
    target_sha: str,
    brief_sha: str,
    verifier_manifest_sha: str | None = None,
) -> None:
    text = _regular_text(root / relative_path, label=f"{kind}_report")
    if target_sha not in text:
        _fail(f"{kind}_report", "does not contain the live target-card SHA-256")
    if kind == "statement":
        # The final-card raw hash transitively binds the card's source_revision.
        # Some original reports name the primary source rather than repeating
        # the repository's synthetic revision label, so do not invent a text
        # requirement that was absent from the completed review.
        if "Verdict: **PASS**" not in text:
            _fail("statement_report", "missing PASS verdict")
    elif kind == "open_status":
        if "Final verdict: **PASS**" not in text or brief_sha not in text:
            _fail("open_status_report", "missing PASS verdict or live agent-brief SHA-256")
    elif kind == "red_team":
        if (
            "Verdict: **PASS**" not in text
            or f"Reviewer: `{RED_TEAM_REVIEWER_ID}`" not in text
            or verifier_manifest_sha is None
            or verifier_manifest_sha not in text
        ):
            _fail("red_team_report", "missing final PASS, reviewer, or live manifest binding")
    else:
        raise AssertionError(kind)


def _build_activation(root: Path, plan_path: Path) -> tuple[PreparedActivation, set[str]]:
    root = root.resolve(strict=True)
    plan_path = plan_path.resolve(strict=True)
    try:
        plan_relative = plan_path.relative_to(root).as_posix()
    except ValueError as exc:
        raise ActivationError("activation plan must stay inside the repository") from exc
    plan = validate_plan(load_json(plan_path))
    catalog_value = load_json(root / "data/problems.json")
    validate_problem_catalog(catalog_value)
    registry_value = load_json(root / "data/verifiers.json")
    registry = validate_verifier_registry(registry_value, root=root)
    problems = {problem["id"]: problem for problem in catalog_value["problems"]}
    active_ids = tuple(sorted(
        problem_id for problem_id, problem in problems.items() if problem["stage"] == "active"
    ))
    if active_ids != ALLOWED_TARGETS:
        _fail("problem_catalog.active", f"must be exactly {list(ALLOWED_TARGETS)}")
    aim = problems.get(FORBIDDEN_TARGET)
    if (
        aim is None
        or aim["stage"] == "active"
        or aim["hard_gates"]["open_status"] != "fail"
    ):
        _fail("problem_catalog.aim-60-first-prime", "must remain non-active with open_status=fail")

    input_paths = {
        plan_relative,
        "data/problems.json",
        "data/verifiers.json",
        "schemas/activation-plan.schema.json",
        "schemas/active-portfolio.v1.schema.json",
        "schemas/agent-baseline-brief.schema.json",
        "schemas/problem-card.v1.schema.json",
        "schemas/receipts.v1.schema.json",
        "schemas/target-bundle.v1.schema.json",
        "schemas/target-card.v1.schema.json",
        "schemas/verifier-manifest.v1.schema.json",
        "schemas/verifier-registry.v1.schema.json",
        "scripts/contracts.py",
        "scripts/export_active.py",
        "scripts/prepare_activation.py",
    }
    outputs: dict[str, bytes] = {}
    bundle_facts: list[dict[str, object]] = []
    global_route_ids: set[str] = set()

    for declared in plan["targets"]:
        problem_id = declared["problem_id"]
        spec = TARGET_SPECS[problem_id]
        problem = problems[problem_id]
        if any(value != "pass" for value in problem["hard_gates"].values()):
            _fail(f"problem[{problem_id}].hard_gates", "all gates must pass")
        target_path_text = f"targets/{problem_id}/target-card.json"
        target_path = root / target_path_text
        target_binding = make_file_binding(target_path, root=root)
        target_value = load_json(target_path)
        target = validate_target_card(
            target_value,
            root=root,
            expected_problem_id=problem_id,
            expected_problem_card_sha256=canonical_sha256(problem),
            expected_source_revision=problem["formalization"]["revision"],
        )
        target_sha = target_binding["sha256"]
        if target["verifier_id"] != spec.verifier_id:
            _fail(f"target[{problem_id}].verifier_id", "does not equal frozen verifier")
        verifier = registry.get(spec.verifier_id)
        if verifier is None:
            _fail(f"target[{problem_id}].verifier_id", "is not registered")
        manifest_binding = verifier["manifest"]
        manifest_value = verifier["manifest_value"]
        if manifest_value["binds_verification_mode"] != problem["verification"]["mode"]:
            _fail(f"target[{problem_id}].verifier", "verification-mode mismatch")

        baseline = declared["baseline"]
        for artifact in baseline["artifacts"]:
            input_paths.add(_relative(artifact, f"target[{problem_id}].baseline.artifact"))
        if problem_id == "degree-diameter-3-9-record":
            forbidden_names = {"Exoo_600.txt", "Exoo_600.normalized.json"}
            if any(PurePosixPath(path).name in forbidden_names for path in baseline["artifacts"]):
                _fail("target[degree-diameter-3-9-record].baseline", "must not bind redistributed graph bytes")
        brief_path_text = f"targets/{problem_id}/evidence/baseline/agent-brief.json"
        if brief_path_text not in baseline["artifacts"]:
            _fail(f"target[{problem_id}].baseline", "must bind the neutral agent brief")
        brief_path = root / brief_path_text
        brief_route_ids = validate_agent_brief(
            load_json(brief_path), problem_id=problem_id, checked_at=plan["checked_at"]
        )
        overlap = global_route_ids.intersection(brief_route_ids)
        if overlap:
            _fail("agent_briefs.known_route_baselines", f"globally duplicate route IDs {sorted(overlap)}")
        global_route_ids.update(brief_route_ids)
        brief_sha = raw_sha256(brief_path)

        input_paths.update({
            target_path_text,
            target["candidate_schema"]["path"],
            manifest_binding["path"],
            spec.statement_report,
            spec.open_status_report,
            spec.red_team_corpus,
            spec.red_team_report,
            *(binding["path"] for binding in manifest_value["source_artifacts"]),
            *(f"tests/{module.rsplit('.', 1)[1]}.py" for module in spec.test_modules),
        })
        _validate_report(
            root,
            relative_path=spec.statement_report,
            kind="statement",
            target_sha=target_sha,
            brief_sha=brief_sha,
        )
        _validate_report(
            root,
            relative_path=spec.open_status_report,
            kind="open_status",
            target_sha=target_sha,
            brief_sha=brief_sha,
        )

        review_receipts: dict[str, dict[str, Any]] = {}
        for kind in ("statement", "open_status"):
            review = declared["reviews"][kind]
            authority_path = _relative(
                review["reviewer_authority"], f"target[{problem_id}].{kind}.authority"
            )
            session_path = _relative(
                review["review_session_evidence"], f"target[{problem_id}].{kind}.session"
            )
            input_paths.update({authority_path, session_path})
            _validate_authority(
                load_json(root / authority_path),
                problem_id=problem_id,
                reviewer_id=review["reviewer_id"],
                reviewer_task_path=review["reviewer_task_path"],
                axis=review["axis"],
            )
            _validate_session(
                load_json(root / session_path),
                problem_id=problem_id,
                reviewer_id=review["reviewer_id"],
                reviewer_task_path=review["reviewer_task_path"],
                axis=review["axis"],
                verdict=review["verdict"],
                report_path=review["report"],
                report_sha256=raw_sha256(root / review["report"]),
                problem_card_sha256=canonical_sha256(problem),
                target_card_sha256=target_sha,
            )
            review_receipt = {
                "schema": REVIEW_RECEIPT_SCHEMA,
                "problem_id": problem_id,
                "target_card_sha256": target_sha,
                "review_id": review["review_id"],
                "reviewer_id": review["reviewer_id"],
                "axis": review["axis"],
                "verdict": review["verdict"],
                "independent_from_solver": True,
                "source_revision": target["source_revision"],
                "report": make_file_binding(root / review["report"], root=root),
                "reviewer_authority": make_file_binding(root / authority_path, root=root),
                "review_session_evidence": make_file_binding(root / session_path, root=root),
                "attestation_scope": REVIEW_ATTESTATION_SCOPE,
                "checked_at": plan["checked_at"],
            }
            validate_review_receipt(
                review_receipt,
                root=root,
                problem_id=problem_id,
                target_card_sha256=target_sha,
                source_revision=target["source_revision"],
            )
            review_receipts[kind] = review_receipt

        corpus = load_json(root / spec.red_team_corpus)
        corpus = _exact(
            corpus,
            frozenset({"schema", "problem_id", "reviewer_id", "cases"}),
            f"target[{problem_id}].red_team.corpus",
        )
        cases = corpus["cases"]
        if (
            corpus["schema"] != "AMF_RED_TEAM_CORPUS_DRAFT_1"
            or corpus["problem_id"] != problem_id
            or corpus["reviewer_id"] != RED_TEAM_REVIEWER_ID
            or type(cases) is not list
            or not cases
        ):
            _fail(f"target[{problem_id}].red_team.corpus", "invalid corpus identity or cases")
        case_ids: set[str] = set()
        for index, value in enumerate(cases):
            case = _exact(
                value,
                frozenset({"id", "class", "expected"}),
                f"target[{problem_id}].red_team.cases[{index}]",
            )
            case_id = _text(case["id"], f"target[{problem_id}].red_team.cases[{index}].id", maximum=128)
            if case_id in case_ids:
                _fail(f"target[{problem_id}].red_team.cases", "duplicate case id")
            case_ids.add(case_id)
            _text(case["class"], f"target[{problem_id}].red_team.cases[{index}].class", maximum=128)
            _text(case["expected"], f"target[{problem_id}].red_team.cases[{index}].expected", maximum=1_024)
        _validate_report(
            root,
            relative_path=spec.red_team_report,
            kind="red_team",
            target_sha=target_sha,
            brief_sha=brief_sha,
            verifier_manifest_sha=manifest_binding["sha256"],
        )

        baseline_receipt = {
            "schema": BASELINE_RECEIPT_SCHEMA,
            "problem_id": problem_id,
            "target_card_sha256": target_sha,
            "baseline_id": baseline["baseline_id"],
            "description": baseline["description"],
            "source_revision": target["source_revision"],
            "checked_at": plan["checked_at"],
            "artifacts": [
                make_file_binding(root / path, root=root) for path in baseline["artifacts"]
            ],
        }
        validate_baseline_receipt(
            baseline_receipt,
            root=root,
            problem_id=problem_id,
            target_card_sha256=target_sha,
            source_revision=target["source_revision"],
        )
        red_receipt = {
            "schema": RED_TEAM_RECEIPT_SCHEMA,
            "problem_id": problem_id,
            "target_card_sha256": target_sha,
            "verifier_id": spec.verifier_id,
            "verifier_manifest_sha256": manifest_binding["sha256"],
            "reviewer_id": RED_TEAM_REVIEWER_ID,
            "corpus": make_file_binding(root / spec.red_team_corpus, root=root),
            "report": make_file_binding(root / spec.red_team_report, root=root),
            "case_count": len(cases),
            "passed": True,
            "checked_at": plan["checked_at"],
        }
        validate_red_team_receipt(
            red_receipt,
            root=root,
            problem_id=problem_id,
            target_card_sha256=target_sha,
            verifier_id=spec.verifier_id,
            verifier_manifest_sha256=manifest_binding["sha256"],
        )
        budget_receipt = {
            "schema": BUDGET_RECEIPT_SCHEMA,
            "problem_id": problem_id,
            "target_card_sha256": target_sha,
            "limits": dict(EXACT_LIMITS),
            "maximum_artifact_bytes": EXACT_MAXIMUM_ARTIFACT_BYTES,
            "retain_failures": True,
            "stop_conditions": list(EXACT_STOP_CONDITIONS),
            "checked_at": plan["checked_at"],
        }
        validate_budget_receipt(
            budget_receipt,
            problem_id=problem_id,
            target_card_sha256=target_sha,
        )

        paths = _receipt_paths(problem_id)
        receipt_values = {
            "baseline": baseline_receipt,
            "statement": review_receipts["statement"],
            "open_status": review_receipts["open_status"],
            "red_team": red_receipt,
            "budget": budget_receipt,
        }
        receipt_bodies: dict[str, bytes] = {}
        for kind, value in receipt_values.items():
            body = canonical_json_bytes(value) + b"\n"
            outputs[paths[kind]] = body
            receipt_bodies[kind] = body
        bundle = {
            "schema": TARGET_BUNDLE_SCHEMA,
            "problem_id": problem_id,
            "problem_card_sha256": canonical_sha256(problem),
            "target_card": target_binding,
            "baseline_receipts": [
                _virtual_binding(paths["baseline"], receipt_bodies["baseline"])
            ],
            "review_receipts": [
                _virtual_binding(paths["statement"], receipt_bodies["statement"]),
                _virtual_binding(paths["open_status"], receipt_bodies["open_status"]),
            ],
            "red_team_receipt": _virtual_binding(paths["red_team"], receipt_bodies["red_team"]),
            "budget_receipt": _virtual_binding(paths["budget"], receipt_bodies["budget"]),
        }
        bundle_body = canonical_json_bytes(bundle) + b"\n"
        outputs[paths["bundle"]] = bundle_body
        bundle_facts.append({
            "claim_scope": target["claim_scope"],
            "problem_card_sha256": canonical_sha256(problem),
            "problem_id": problem_id,
            "target_bundle": _virtual_binding(paths["bundle"], bundle_body),
            "target_card_sha256": target_sha,
            "verification_mode": problem["verification"]["mode"],
            "verifier_id": spec.verifier_id,
        })

    portfolio_core: dict[str, object] = {
        "as_of": catalog_value["as_of"],
        "problem_catalog_sha256": canonical_sha256(catalog_value),
        "problem_card_schema": PROBLEM_CARD_SCHEMA,
        "schema": ACTIVE_PORTFOLIO_SCHEMA,
        "source_schema_version": catalog_value["schema_version"],
        "targets": sorted(bundle_facts, key=lambda item: str(item["problem_id"])),
        "verifier_registry_sha256": canonical_sha256(registry_value),
    }
    portfolio = {
        **portfolio_core,
        "portfolio_ref": "active-portfolio/sha256/" + canonical_sha256({
            "domain": "AMF_ACTIVE_PORTFOLIO_1", "value": portfolio_core,
        }),
    }
    outputs["data/active-portfolio.json"] = canonical_json_bytes(portfolio) + b"\n"
    manifest_sha, _manifest = _input_manifest(root, input_paths)
    return PreparedActivation(
        outputs=dict(sorted(outputs.items())),
        input_manifest_sha256=manifest_sha,
        test_modules={problem_id: TARGET_SPECS[problem_id].test_modules for problem_id in ALLOWED_TARGETS},
    ), input_paths


TestRunner = Callable[[Path, str, tuple[str, str], int], None]


def run_frozen_tests(
    root: Path, problem_id: str, modules: tuple[str, str], timeout_seconds: int
) -> None:
    """Run exact frozen tests with no network, credentials, or repository writes."""

    sandbox_exec = Path("/usr/bin/sandbox-exec")
    try:
        metadata = sandbox_exec.lstat()
    except OSError as exc:
        raise ActivationError("test sandbox: /usr/bin/sandbox-exec is required") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        _fail("test sandbox", "sandbox-exec must be a regular non-symlink file")
    escaped_root = str(root).replace("\\", "\\\\").replace('"', '\\"')
    profile = (
        '(version 1)\n'
        '(allow default)\n'
        '(deny network*)\n'
        f'(deny file-write* (subpath "{escaped_root}"))\n'
    )
    temporary_root = os.environ.get("TMPDIR", "/private/tmp")
    environment = {
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
        "TMPDIR": temporary_root,
    }
    command = [
        str(sandbox_exec), "-p", profile, sys.executable,
        "-m", "unittest", *modules,
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=root,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ActivationError(f"tests[{problem_id}]: timeout after {timeout_seconds}s") from exc
    output = completed.stdout
    if len(output) > TEST_OUTPUT_LIMIT:
        _fail(f"tests[{problem_id}]", f"output exceeds {TEST_OUTPUT_LIMIT} bytes")
    if completed.returncode != 0 or b"OK" not in output:
        rendered = output.decode("utf-8", errors="replace")[-8_000:]
        _fail(f"tests[{problem_id}]", f"failed with exit {completed.returncode}:\n{rendered}")


def prepare_activation(
    *,
    root: Path = ROOT,
    plan_path: Path | None = None,
    test_runner: TestRunner = run_frozen_tests,
) -> PreparedActivation:
    root = root.resolve(strict=True)
    selected_plan = plan_path or root / "activation/pmw-frontier-choice-2026-08-14.json"
    prepared, input_paths = _build_activation(root, selected_plan)
    for problem_id in ALLOWED_TARGETS:
        test_runner(root, problem_id, prepared.test_modules[problem_id], TEST_TIMEOUT_SECONDS)
    after_sha, _after = _input_manifest(root, input_paths)
    if after_sha != prepared.input_manifest_sha256:
        _fail("activation input manifest", "changed while frozen tests were running")
    return prepared


def _validate_output_parent(root: Path, path: Path) -> None:
    resolved_root = root.resolve(strict=True)
    try:
        path.relative_to(resolved_root)
    except ValueError as exc:
        raise ActivationError(f"output {path}: escapes repository") from exc
    relative_parent = path.parent.relative_to(resolved_root)
    current = resolved_root
    for part in relative_parent.parts:
        current = current / part
        if current.exists():
            metadata = current.lstat()
            if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
                _fail(str(current), "output parent must be a real directory")


def _ensure_output_parent(root: Path, path: Path) -> None:
    path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    _validate_output_parent(root, path)


def _read_existing_output(path: Path) -> bytes | None:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise ActivationError(f"output {path}: unavailable: {exc}") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        _fail(str(path), "existing output must be a regular non-symlink file")
    body = path.read_bytes()
    if len(body) != metadata.st_size:
        _fail(str(path), "changed while being read")
    return body


def _exclusive_or_identical(path: Path, body: bytes) -> bool:
    existing = _read_existing_output(path)
    if existing is not None:
        if existing != body:
            _fail(str(path), "exists with different bytes; refusing to overwrite evidence")
        return False
    descriptor, temporary_text = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_text)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path)
        except OSError as exc:
            if exc.errno != errno.EEXIST:
                raise
            raced = _read_existing_output(path)
            if raced != body:
                _fail(str(path), "concurrent different output won exclusive creation")
            return False
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        return True
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _validate_installed(root: Path, prepared: PreparedActivation) -> None:
    for relative, expected in prepared.outputs.items():
        actual = _read_existing_output(root / relative)
        if actual != expected:
            _fail(relative, "canonical output is missing or stale")
    catalog = load_json(root / "data/problems.json")
    registry_value = load_json(root / "data/verifiers.json")
    registry = validate_verifier_registry(registry_value, root=root)
    problems = {problem["id"]: problem for problem in catalog["problems"]}
    for problem_id in ALLOWED_TARGETS:
        bundle = load_json(root / f"targets/{problem_id}/target-bundle.json")
        validate_target_bundle(
            bundle, root=root, problem=problems[problem_id], verifier_registry=registry
        )
    expected_portfolio = load_json(root / "data/active-portfolio.json")
    if build_active_portfolio(root) != expected_portfolio:
        _fail("data/active-portfolio.json", "does not equal independent exporter result")


def check_outputs(root: Path, prepared: PreparedActivation) -> None:
    _validate_installed(root.resolve(strict=True), prepared)


def write_outputs(root: Path, prepared: PreparedActivation) -> tuple[str, ...]:
    root = root.resolve(strict=True)
    # Preflight every output before creating the first one.
    for relative, body in prepared.outputs.items():
        path = root / relative
        _validate_output_parent(root, path)
        existing = _read_existing_output(path)
        if existing is not None and existing != body:
            _fail(relative, "exists with different bytes; refusing to overwrite evidence")
    created: list[Path] = []
    try:
        for relative, body in prepared.outputs.items():
            path = root / relative
            _ensure_output_parent(root, path)
            if _exclusive_or_identical(path, body):
                created.append(path)
        _validate_installed(root, prepared)
    except BaseException:
        for path in reversed(created):
            try:
                expected = prepared.outputs[path.relative_to(root).as_posix()]
                if _read_existing_output(path) == expected:
                    path.unlink()
            except OSError:
                pass
        raise
    return tuple(path.relative_to(root).as_posix() for path in created)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="run gates and require exact installed outputs")
    mode.add_argument("--write", action="store_true", help="run gates and exclusively install exact outputs")
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    args = parser.parse_args()
    try:
        plan_path = args.plan if args.plan.is_absolute() else ROOT / args.plan
        prepared = prepare_activation(root=ROOT, plan_path=plan_path)
        if args.check:
            check_outputs(ROOT, prepared)
            print(
                f"activation check PASS: {ACTIVATION_ID}; "
                f"input_manifest_sha256={prepared.input_manifest_sha256}; zero_model_calls=true"
            )
        else:
            created = write_outputs(ROOT, prepared)
            print(
                f"activation write PASS: {ACTIVATION_ID}; created={len(created)}; "
                f"input_manifest_sha256={prepared.input_manifest_sha256}; zero_model_calls=true"
            )
    except (ActivationError, ContractError, OSError) as exc:
        print(f"activation preparation failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
