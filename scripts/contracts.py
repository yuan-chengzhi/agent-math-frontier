#!/usr/bin/env python3
"""Strict, dependency-free machine contracts for active research targets.

The Markdown catalog is a human view.  This module is the fail-closed boundary
used by validation and by the PMW active-portfolio exporter.  JSON hashes are
computed over a canonical representation; file bindings hash exact raw bytes.
"""

from __future__ import annotations

from datetime import date
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
from typing import Any, NoReturn
from urllib.parse import urlparse


PROBLEM_CATALOG_SCHEMA_VERSION = 1
PROBLEM_CARD_SCHEMA = "AMF_PROBLEM_CARD_1"
TARGET_CARD_SCHEMA = "AMF_TARGET_CARD_1"
TARGET_BUNDLE_SCHEMA = "AMF_TARGET_BUNDLE_1"
VERIFIER_REGISTRY_SCHEMA = "AMF_VERIFIER_REGISTRY_1"
VERIFIER_MANIFEST_SCHEMA = "AMF_VERIFIER_MANIFEST_1"
BASELINE_RECEIPT_SCHEMA = "AMF_BASELINE_RECEIPT_1"
REVIEW_RECEIPT_SCHEMA = "AMF_REVIEW_RECEIPT_1"
RED_TEAM_RECEIPT_SCHEMA = "AMF_RED_TEAM_RECEIPT_1"
BUDGET_RECEIPT_SCHEMA = "AMF_BUDGET_RECEIPT_2"
ACTIVE_PORTFOLIO_SCHEMA = "AMF_ACTIVE_PORTFOLIO_1"

FORMALIZATION_LEVELS = frozenset({
    "proof_assistant",
    "executable_spec",
    "precise_informal",
    "research_program",
})
STAGES = frozenset({"raw", "curated", "active", "retired"})
RECOMMENDATIONS = frozenset({"shortlist", "incubate", "watch", "quarantine"})
GATE_KEYS = frozenset({
    "open_status",
    "exact_target",
    "verification_path",
    "valuable_partial_progress",
    "reproducibility",
})
GATE_VALUES = frozenset({"pass", "conditional", "fail", "unknown"})
FIT_KEYS = frozenset({
    "verifiability",
    "feedback_richness",
    "representation",
    "decomposability",
    "tool_readiness",
    "partial_value",
    "math_value",
    "status_confidence",
    "resource_feasibility",
})
CLAIM_SCOPES = frozenset({
    "FULL_PROBLEM",
    "RECORD_IMPROVEMENT",
    "BOUNDED_COUNTEREXAMPLE",
    "FINITE_INSTANCE",
    "PARAMETER_RANGE",
    "SUBCLASS_RESULT",
    "FORMALIZATION_MILESTONE",
})
REVIEW_AXES = frozenset({
    "STATEMENT_FIDELITY",
    "OPEN_STATUS_AND_NOVELTY",
    "MATHEMATICAL_SIGNIFICANCE",
})
REVIEW_VERDICTS = frozenset({"PASS", "CONDITIONAL", "FAIL"})
RESOURCE_FIELDS = frozenset({
    "context_tokens",
    "host_context_steers",
    "host_phase_prompts",
    "input_tokens_per_provider_request",
    "output_tokens_per_provider_request",
    "provider_request_attempts",
    "tool_calls",
    "verifier_calls",
    "wall_ms",
})

_PROBLEM_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,127}$")
_SEMANTIC_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_VERIFIER_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,110}\.v[1-9][0-9]{0,15}$")
_VERIFIER_VERSION = re.compile(r"^v[1-9][0-9]{0,15}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MAX_I64 = (1 << 63) - 1

MAX_JSON_BYTES = 16 * 1024 * 1024
MAX_BOUND_FILE_BYTES = 1 << 30
REVIEW_ATTESTATION_SCOPE = (
    "IDENTITY_AND_PROCESS_BINDING_ONLY_NOT_MATHEMATICAL_TRUTH_OR_CRYPTOGRAPHIC_SIGNATURE"
)


class ContractError(ValueError):
    """A stable, fail-closed contract violation."""


def _fail(label: str, message: str) -> NoReturn:
    raise ContractError(f"{label}: {message}")


def _duplicate_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            _fail("json", f"duplicate key {key!r}")
        value[key] = item
    return value


def _reject_number(value: str) -> NoReturn:
    _fail("json", f"non-integer or non-finite number {value!r}")


def load_json(path: Path) -> dict[str, Any]:
    """Load one bounded regular-file JSON object with strict JSON semantics."""

    try:
        metadata = path.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            _fail(str(path), "JSON input must be a regular non-symlink file")
        if metadata.st_size > MAX_JSON_BYTES:
            _fail(str(path), f"JSON input exceeds maximum {MAX_JSON_BYTES} bytes")
        raw = path.read_bytes()
        if len(raw) != metadata.st_size:
            _fail(str(path), "JSON input changed while it was being read")
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_duplicate_pairs,
            parse_constant=_reject_number,
            parse_float=_reject_number,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"{path}: invalid JSON: {exc}") from exc
    if type(value) is not dict:
        _fail(str(path), "top-level value must be an object")
    canonical_json_bytes(value)
    return value


def _canonical_value(value: object, label: str = "json") -> None:
    if value is None or type(value) in {bool, int}:
        if type(value) is int and not -_MAX_I64 <= value <= _MAX_I64:
            _fail(label, "integer exceeds signed 64-bit range")
        return
    if type(value) is str:
        try:
            value.encode("utf-8", errors="strict")
        except UnicodeError as exc:
            raise ContractError(f"{label}: invalid UTF-8 string") from exc
        if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
            _fail(label, "surrogate code point is forbidden")
        return
    if type(value) is list:
        for index, item in enumerate(value):
            _canonical_value(item, f"{label}[{index}]")
        return
    if type(value) is dict:
        for key in sorted(value):
            if type(key) is not str:
                _fail(label, "object keys must be strings")
            _canonical_value(key, f"{label}.key")
            _canonical_value(value[key], f"{label}.{key}")
        return
    _fail(label, f"unsupported value type {type(value).__name__}")


def canonical_json_bytes(value: object) -> bytes:
    """RFC-8259-shaped deterministic JSON used for logical identities."""

    _canonical_value(value)
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def raw_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1_048_576):
            digest.update(chunk)
    return digest.hexdigest()


def make_file_binding(path: Path, *, root: Path) -> dict[str, object]:
    """Return the exact raw-byte binding for one safe repository file."""

    try:
        resolved_root = root.resolve(strict=True)
        metadata = path.lstat()
        resolved = path.resolve(strict=True)
        relative = resolved.relative_to(resolved_root)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ContractError(f"{path}: file is unavailable or escapes the repository") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        _fail(str(path), "artifact must be a regular non-symlink file")
    if metadata.st_size > MAX_BOUND_FILE_BYTES:
        _fail(str(path), f"artifact exceeds maximum {MAX_BOUND_FILE_BYTES} bytes")
    relative_text = relative.as_posix()
    binding = {
        "path": relative_text,
        "bytes": metadata.st_size,
        "sha256": raw_sha256(path),
    }
    validate_file_binding(binding, root=root, label=f"binding[{relative_text}]")
    return binding


def _exact(value: object, fields: frozenset[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or frozenset(value) != fields:
        actual = sorted(value) if type(value) is dict else type(value).__name__
        _fail(label, f"expected exact fields {sorted(fields)}, got {actual}")
    return dict(value)


def _text(
    value: object,
    label: str,
    *,
    minimum: int = 1,
    maximum: int = 65_536,
    pattern: re.Pattern[str] | None = None,
) -> str:
    if type(value) is not str or "\x00" in value:
        _fail(label, "must be NUL-free text")
    try:
        size = len(value.encode("utf-8", errors="strict"))
    except UnicodeError as exc:
        raise ContractError(f"{label}: invalid UTF-8") from exc
    if not minimum <= size <= maximum:
        _fail(label, f"UTF-8 byte length must be {minimum}..{maximum}")
    if pattern is not None and pattern.fullmatch(value) is None:
        _fail(label, "text does not match its grammar")
    return value


def _enum(value: object, allowed: frozenset[str], label: str) -> str:
    result = _text(value, label, maximum=128)
    if result not in allowed:
        _fail(label, f"must be one of {sorted(allowed)}")
    return result


def _integer(
    value: object,
    label: str,
    *,
    minimum: int = 0,
    maximum: int = _MAX_I64,
) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        _fail(label, f"must be an integer in {minimum}..{maximum}")
    return value


def _boolean(value: object, label: str) -> bool:
    if type(value) is not bool:
        _fail(label, "must be a boolean")
    return value


def _date(value: object, label: str) -> str:
    result = _text(value, label, maximum=10)
    try:
        parsed = date.fromisoformat(result)
    except ValueError as exc:
        raise ContractError(f"{label}: must be an ISO date") from exc
    if parsed > date.today():
        _fail(label, "date is in the future")
    return result


def _https(value: object, label: str) -> str:
    result = _text(value, label, maximum=2_048)
    parsed = urlparse(result)
    if parsed.scheme != "https" or not parsed.netloc:
        _fail(label, "must be an absolute HTTPS URL")
    return result


def _sha(value: object, label: str) -> str:
    return _text(value, label, maximum=64, pattern=_SHA256)


def _problem_id_value(value: object, label: str = "problem_id") -> str:
    return _text(value, label, maximum=128, pattern=_PROBLEM_ID)


def _verifier_id_value(value: object, label: str = "verifier_id") -> str:
    return _text(value, label, maximum=128, pattern=_VERIFIER_ID)


def _verification_mode_value(value: object, label: str = "verification_mode") -> str:
    return _text(value, label, maximum=128, pattern=_SEMANTIC_ID)


def _text_list(
    value: object,
    label: str,
    *,
    minimum_items: int = 0,
    maximum_items: int = 128,
    unique: bool = False,
) -> list[str]:
    if type(value) is not list or not minimum_items <= len(value) <= maximum_items:
        _fail(label, f"must contain {minimum_items}..{maximum_items} items")
    result = [_text(item, f"{label}[{index}]") for index, item in enumerate(value)]
    if unique and len(set(result)) != len(result):
        _fail(label, "items must be unique")
    return result


def validate_problem_card(value: object, *, label: str = "problem") -> dict[str, Any]:
    problem = _exact(value, frozenset({
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
    }), label)
    problem_id = _problem_id_value(problem["id"], f"{label}.id")
    _text(problem["title_zh"], f"{label}.title_zh", maximum=500)
    _text(problem["title_en"], f"{label}.title_en", maximum=500)
    _text_list(problem["domains"], f"{label}.domains", minimum_items=1, unique=True)
    _text(problem["track"], f"{label}.track", maximum=128, pattern=_SEMANTIC_ID)
    stage = _enum(problem["stage"], STAGES, f"{label}.stage")
    _enum(problem["recommendation"], RECOMMENDATIONS, f"{label}.recommendation")

    source = _exact(problem["source"], frozenset({
        "collection_id", "canonical_url", "source_label", "checked_at", "status_confidence",
    }), f"{label}.source")
    _text(source["collection_id"], f"{label}.source.collection_id", maximum=128, pattern=_PROBLEM_ID)
    _https(source["canonical_url"], f"{label}.source.canonical_url")
    _text(source["source_label"], f"{label}.source.source_label", maximum=1_000)
    _date(source["checked_at"], f"{label}.source.checked_at")
    _enum(source["status_confidence"], frozenset({"low", "medium", "high"}), f"{label}.source.status_confidence")

    statement = _exact(problem["statement"], frozenset({
        "summary_zh", "target_zh", "success_artifact_zh", "partial_progress_zh",
    }), f"{label}.statement")
    for field in sorted(statement):
        _text(statement[field], f"{label}.statement.{field}", maximum=8_000)

    formal = _exact(problem["formalization"], frozenset({
        "level", "state", "system", "artifact_url", "revision", "declaration", "fidelity",
    }), f"{label}.formalization")
    level = _enum(formal["level"], FORMALIZATION_LEVELS, f"{label}.formalization.level")
    _text(formal["state"], f"{label}.formalization.state", maximum=128)
    _text(formal["revision"], f"{label}.formalization.revision", maximum=512)
    _text(formal["fidelity"], f"{label}.formalization.fidelity", maximum=128)
    if level == "proof_assistant":
        _text(formal["system"], f"{label}.formalization.system", maximum=128)
        artifact_url = _https(formal["artifact_url"], f"{label}.formalization.artifact_url")
        if "/blob/main/" in artifact_url:
            _fail(f"{label}.formalization.artifact_url", "artifact must be revision-pinned")
        _text(formal["declaration"], f"{label}.formalization.declaration", maximum=512)
    elif formal["system"] is not None or formal["artifact_url"] is not None or formal["declaration"] is not None:
        _fail(f"{label}.formalization", "non-proof-assistant target must use null system/artifact/declaration")

    verification = _exact(problem["verification"], frozenset({
        "mode", "independent", "notes_zh",
    }), f"{label}.verification")
    _verification_mode_value(verification["mode"], f"{label}.verification.mode")
    if _boolean(verification["independent"], f"{label}.verification.independent") is not True:
        _fail(f"{label}.verification.independent", "must be true")
    _text(verification["notes_zh"], f"{label}.verification.notes_zh", maximum=4_000)

    gates = _exact(problem["hard_gates"], GATE_KEYS, f"{label}.hard_gates")
    for key in sorted(gates):
        _enum(gates[key], GATE_VALUES, f"{label}.hard_gates.{key}")
    if stage == "active" and any(gates[key] != "pass" for key in GATE_KEYS):
        _fail(label, f"active problem {problem_id!r} requires every hard gate to pass")

    fit = _exact(problem["fit"], FIT_KEYS, f"{label}.fit")
    for key in sorted(fit):
        _integer(fit[key], f"{label}.fit.{key}", maximum=3)
    _text_list(problem["risks_zh"], f"{label}.risks_zh", minimum_items=1, maximum_items=32)
    _text(problem["selection_note_zh"], f"{label}.selection_note_zh", maximum=4_000)
    return problem


def validate_problem_catalog(value: object) -> dict[str, Any]:
    catalog = _exact(value, frozenset({
        "schema_version", "as_of", "scale", "formalization_levels", "problems",
    }), "problem_catalog")
    if _integer(catalog["schema_version"], "problem_catalog.schema_version", minimum=1) != PROBLEM_CATALOG_SCHEMA_VERSION:
        _fail("problem_catalog.schema_version", f"unsupported version; expected {PROBLEM_CATALOG_SCHEMA_VERSION}")
    _date(catalog["as_of"], "problem_catalog.as_of")
    scale = _exact(catalog["scale"], frozenset({
        "score_min", "score_max", "score_meaning", "warning",
    }), "problem_catalog.scale")
    _integer(scale["score_min"], "problem_catalog.scale.score_min", maximum=3)
    _integer(scale["score_max"], "problem_catalog.scale.score_max", maximum=3)
    if scale["score_min"] != 0 or scale["score_max"] != 3:
        _fail("problem_catalog.scale", "the version-1 scale must be exactly 0..3")
    _text(scale["score_meaning"], "problem_catalog.scale.score_meaning", maximum=1_000)
    _text(scale["warning"], "problem_catalog.scale.warning", maximum=1_000)
    levels = _exact(catalog["formalization_levels"], FORMALIZATION_LEVELS, "problem_catalog.formalization_levels")
    for key in sorted(levels):
        _text(levels[key], f"problem_catalog.formalization_levels.{key}", maximum=1_000)
    problems_value = catalog["problems"]
    if type(problems_value) is not list:
        _fail("problem_catalog.problems", "must be a list")
    ids: list[str] = []
    for index, item in enumerate(problems_value):
        problem = validate_problem_card(item, label=f"problem_catalog.problems[{index}]")
        ids.append(problem["id"])
    if len(ids) != len(set(ids)):
        _fail("problem_catalog.problems", "problem ids must be unique")
    return catalog


def validate_file_binding(value: object, *, root: Path, label: str) -> tuple[dict[str, Any], Path]:
    binding = _exact(value, frozenset({"path", "bytes", "sha256"}), label)
    raw_path = _text(binding["path"], f"{label}.path", maximum=512)
    if "\\" in raw_path:
        _fail(f"{label}.path", "must use POSIX separators")
    pure = PurePosixPath(raw_path)
    if pure.is_absolute() or not pure.parts or any(part in {"", ".", ".."} for part in pure.parts):
        _fail(f"{label}.path", "must be a normalized repository-relative path")
    _integer(binding["bytes"], f"{label}.bytes", maximum=MAX_BOUND_FILE_BYTES)
    _sha(binding["sha256"], f"{label}.sha256")
    selected = root.joinpath(*pure.parts)
    try:
        metadata = selected.lstat()
        resolved_root = root.resolve(strict=True)
        resolved = selected.resolve(strict=True)
        resolved.relative_to(resolved_root)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ContractError(f"{label}: bound file is unavailable or escapes the repository") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        _fail(label, "bound artifact must be a regular non-symlink file")
    if metadata.st_size > MAX_BOUND_FILE_BYTES:
        _fail(label, f"bound artifact exceeds maximum {MAX_BOUND_FILE_BYTES} bytes")
    if binding["bytes"] != metadata.st_size:
        _fail(label, f"file binding size mismatch; observed {metadata.st_size} bytes")
    observed = {"path": raw_path, "bytes": metadata.st_size, "sha256": raw_sha256(selected)}
    if binding != observed:
        _fail(label, f"file binding mismatch; observed {observed}")
    return binding, selected


def validate_target_card(
    value: object,
    *,
    root: Path,
    expected_problem_id: str,
    expected_problem_card_sha256: str,
    expected_source_revision: str,
) -> dict[str, Any]:
    card = _exact(value, frozenset({
        "schema",
        "problem_id",
        "problem_card_sha256",
        "canonical_statement",
        "source_revision",
        "claim_scope",
        "success_criterion",
        "partial_progress_criterion",
        "stop_conditions",
        "candidate_schema",
        "verifier_id",
    }), "target_card")
    if card["schema"] != TARGET_CARD_SCHEMA:
        _fail("target_card.schema", f"must be {TARGET_CARD_SCHEMA}")
    if _problem_id_value(card["problem_id"], "target_card.problem_id") != expected_problem_id:
        _fail("target_card.problem_id", "does not match active problem")
    if _sha(card["problem_card_sha256"], "target_card.problem_card_sha256") != expected_problem_card_sha256:
        _fail("target_card.problem_card_sha256", "does not bind the active problem card")
    for field in (
        "canonical_statement",
        "success_criterion",
        "partial_progress_criterion",
    ):
        _text(card[field], f"target_card.{field}", maximum=32_768)
    if _text(card["source_revision"], "target_card.source_revision", maximum=32_768) != expected_source_revision:
        _fail("target_card.source_revision", "does not bind the problem card source revision")
    _enum(card["claim_scope"], CLAIM_SCOPES, "target_card.claim_scope")
    _text_list(card["stop_conditions"], "target_card.stop_conditions", minimum_items=1, maximum_items=32, unique=True)
    _candidate_binding, candidate_path = validate_file_binding(
        card["candidate_schema"], root=root, label="target_card.candidate_schema"
    )
    candidate_schema = load_json(candidate_path)
    if candidate_schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        _fail("target_card.candidate_schema", "must be a draft-2020-12 JSON Schema")
    if candidate_schema.get("type") != "object":
        _fail("target_card.candidate_schema", "top-level candidate must be an object")
    _verifier_id_value(card["verifier_id"], "target_card.verifier_id")
    return card


def validate_verifier_registry(value: object, *, root: Path) -> dict[str, dict[str, Any]]:
    registry = _exact(value, frozenset({"schema", "verifiers"}), "verifier_registry")
    if registry["schema"] != VERIFIER_REGISTRY_SCHEMA:
        _fail("verifier_registry.schema", f"must be {VERIFIER_REGISTRY_SCHEMA}")
    entries = registry["verifiers"]
    if type(entries) is not list:
        _fail("verifier_registry.verifiers", "must be a list")
    result: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(entries):
        entry = _exact(item, frozenset({"verifier_id", "protocol", "manifest"}), f"verifier_registry.verifiers[{index}]")
        verifier_id = _verifier_id_value(entry["verifier_id"], f"verifier_registry.verifiers[{index}].verifier_id")
        if entry["protocol"] != "AMF_VERIFIER_PROTOCOL_1":
            _fail(f"verifier_registry.verifiers[{index}].protocol", "unsupported protocol")
        _binding, path = validate_file_binding(entry["manifest"], root=root, label=f"verifier_registry.verifiers[{index}].manifest")
        manifest = load_json(path)
        validate_verifier_manifest(manifest, root=root, expected_verifier_id=verifier_id)
        if verifier_id in result:
            _fail("verifier_registry.verifiers", f"duplicate verifier id {verifier_id!r}")
        result[verifier_id] = {**entry, "manifest_value": manifest}
    return result


def validate_verifier_manifest(value: object, *, root: Path, expected_verifier_id: str) -> dict[str, Any]:
    manifest = _exact(value, frozenset({
        "schema",
        "verifier_id",
        "binds_verification_mode",
        "version",
        "command",
        "working_directory",
        "timeout_seconds",
        "maximum_output_bytes",
        "network",
        "source_artifacts",
    }), "verifier_manifest")
    if manifest["schema"] != VERIFIER_MANIFEST_SCHEMA:
        _fail("verifier_manifest.schema", f"must be {VERIFIER_MANIFEST_SCHEMA}")
    if _verifier_id_value(manifest["verifier_id"], "verifier_manifest.verifier_id") != expected_verifier_id:
        _fail("verifier_manifest.verifier_id", "registry/manifest mismatch")
    _verification_mode_value(
        manifest["binds_verification_mode"],
        "verifier_manifest.binds_verification_mode",
    )
    version = _text(
        manifest["version"],
        "verifier_manifest.version",
        maximum=17,
        pattern=_VERIFIER_VERSION,
    )
    if not expected_verifier_id.endswith(f".{version}"):
        _fail("verifier_manifest.version", "must match the verifier_id version suffix")
    command = _text_list(manifest["command"], "verifier_manifest.command", minimum_items=1, maximum_items=32)
    working = _text(manifest["working_directory"], "verifier_manifest.working_directory", maximum=512)
    if "\\" in working:
        _fail("verifier_manifest.working_directory", "must use POSIX separators")
    pure = PurePosixPath(working)
    normalized_working = pure.as_posix() if pure.parts else "."
    if (
        pure.is_absolute()
        or any(part in {"", ".."} for part in pure.parts)
        or normalized_working != working
    ):
        _fail("verifier_manifest.working_directory", "must be normalized and repository-relative")
    try:
        working_path = (root / working).resolve(strict=True)
        working_path.relative_to(root.resolve(strict=True))
    except (OSError, RuntimeError, ValueError) as exc:
        raise ContractError("verifier_manifest.working_directory: unavailable or escapes repository") from exc
    if not working_path.is_dir():
        _fail("verifier_manifest.working_directory", "must select a directory")
    _integer(manifest["timeout_seconds"], "verifier_manifest.timeout_seconds", minimum=1, maximum=86_400)
    _integer(manifest["maximum_output_bytes"], "verifier_manifest.maximum_output_bytes", minimum=1, maximum=1 << 30)
    if _boolean(manifest["network"], "verifier_manifest.network") is not False:
        _fail("verifier_manifest.network", "active verifiers must be offline")
    artifacts = manifest["source_artifacts"]
    if type(artifacts) is not list or not artifacts:
        _fail("verifier_manifest.source_artifacts", "must bind at least one source artifact")
    bound_paths = []
    for index, binding in enumerate(artifacts):
        validated, _path = validate_file_binding(binding, root=root, label=f"verifier_manifest.source_artifacts[{index}]")
        bound_paths.append(validated["path"])
    if command[0] not in bound_paths:
        _fail("verifier_manifest.command", "entrypoint must be a bound verifier source artifact")
    return manifest


def _load_bound_json(value: object, *, root: Path, label: str) -> tuple[dict[str, Any], dict[str, Any]]:
    binding, path = validate_file_binding(value, root=root, label=label)
    return binding, load_json(path)


def _receipt_common(
    receipt: dict[str, Any],
    *,
    schema: str,
    problem_id: str,
    target_card_sha256: str,
    label: str,
) -> None:
    if receipt["schema"] != schema:
        _fail(f"{label}.schema", f"must be {schema}")
    if _problem_id_value(receipt["problem_id"], f"{label}.problem_id") != problem_id:
        _fail(f"{label}.problem_id", "receipt belongs to another problem")
    if _sha(receipt["target_card_sha256"], f"{label}.target_card_sha256") != target_card_sha256:
        _fail(f"{label}.target_card_sha256", "receipt does not bind the target card")


def validate_baseline_receipt(
    value: object,
    *,
    root: Path,
    problem_id: str,
    target_card_sha256: str,
    source_revision: str,
) -> dict[str, Any]:
    receipt = _exact(value, frozenset({
        "schema", "problem_id", "target_card_sha256", "baseline_id", "description",
        "source_revision", "checked_at", "artifacts",
    }), "baseline_receipt")
    _receipt_common(receipt, schema=BASELINE_RECEIPT_SCHEMA, problem_id=problem_id, target_card_sha256=target_card_sha256, label="baseline_receipt")
    _text(receipt["baseline_id"], "baseline_receipt.baseline_id", maximum=256)
    _text(receipt["description"], "baseline_receipt.description", maximum=8_000)
    if _text(receipt["source_revision"], "baseline_receipt.source_revision", maximum=1_024) != source_revision:
        _fail("baseline_receipt.source_revision", "does not bind the target source revision")
    _date(receipt["checked_at"], "baseline_receipt.checked_at")
    artifacts = receipt["artifacts"]
    if type(artifacts) is not list or not artifacts:
        _fail("baseline_receipt.artifacts", "must bind at least one frozen baseline artifact")
    for index, binding in enumerate(artifacts):
        validate_file_binding(binding, root=root, label=f"baseline_receipt.artifacts[{index}]")
    return receipt


def validate_review_receipt(
    value: object,
    *,
    root: Path,
    problem_id: str,
    target_card_sha256: str,
    source_revision: str,
) -> dict[str, Any]:
    receipt = _exact(value, frozenset({
        "schema", "problem_id", "target_card_sha256", "review_id", "reviewer_id",
        "axis", "verdict", "independent_from_solver", "source_revision", "report",
        "reviewer_authority", "review_session_evidence", "attestation_scope", "checked_at",
    }), "review_receipt")
    _receipt_common(receipt, schema=REVIEW_RECEIPT_SCHEMA, problem_id=problem_id, target_card_sha256=target_card_sha256, label="review_receipt")
    _text(receipt["review_id"], "review_receipt.review_id", maximum=256)
    _text(receipt["reviewer_id"], "review_receipt.reviewer_id", maximum=256)
    _enum(receipt["axis"], REVIEW_AXES, "review_receipt.axis")
    _enum(receipt["verdict"], REVIEW_VERDICTS, "review_receipt.verdict")
    if _boolean(receipt["independent_from_solver"], "review_receipt.independent_from_solver") is not True:
        _fail("review_receipt.independent_from_solver", "must be true")
    if _text(receipt["source_revision"], "review_receipt.source_revision", maximum=1_024) != source_revision:
        _fail("review_receipt.source_revision", "does not bind the target source revision")
    bound_paths = []
    for field in ("report", "reviewer_authority", "review_session_evidence"):
        binding, _path = validate_file_binding(
            receipt[field], root=root, label=f"review_receipt.{field}"
        )
        if binding["bytes"] == 0:
            _fail(f"review_receipt.{field}", "must bind a non-empty artifact")
        bound_paths.append(binding["path"])
    if len(bound_paths) != len(set(bound_paths)):
        _fail("review_receipt", "report, authority, and session evidence must be distinct files")
    if receipt["attestation_scope"] != REVIEW_ATTESTATION_SCOPE:
        _fail(
            "review_receipt.attestation_scope",
            "must disclaim mathematical truth and cryptographic-signature claims",
        )
    _date(receipt["checked_at"], "review_receipt.checked_at")
    return receipt


def validate_red_team_receipt(
    value: object,
    *,
    root: Path,
    problem_id: str,
    target_card_sha256: str,
    verifier_id: str,
    verifier_manifest_sha256: str,
) -> dict[str, Any]:
    receipt = _exact(value, frozenset({
        "schema", "problem_id", "target_card_sha256", "verifier_id",
        "verifier_manifest_sha256", "reviewer_id", "corpus", "report",
        "case_count", "passed", "checked_at",
    }), "red_team_receipt")
    _receipt_common(receipt, schema=RED_TEAM_RECEIPT_SCHEMA, problem_id=problem_id, target_card_sha256=target_card_sha256, label="red_team_receipt")
    if _verifier_id_value(receipt["verifier_id"], "red_team_receipt.verifier_id") != verifier_id:
        _fail("red_team_receipt.verifier_id", "does not bind the target verifier")
    if _sha(receipt["verifier_manifest_sha256"], "red_team_receipt.verifier_manifest_sha256") != verifier_manifest_sha256:
        _fail("red_team_receipt.verifier_manifest_sha256", "does not bind the registered verifier manifest")
    _text(receipt["reviewer_id"], "red_team_receipt.reviewer_id", maximum=256)
    validate_file_binding(receipt["corpus"], root=root, label="red_team_receipt.corpus")
    validate_file_binding(receipt["report"], root=root, label="red_team_receipt.report")
    _integer(receipt["case_count"], "red_team_receipt.case_count", minimum=1, maximum=10_000_000)
    if _boolean(receipt["passed"], "red_team_receipt.passed") is not True:
        _fail("red_team_receipt.passed", "must be true")
    _date(receipt["checked_at"], "red_team_receipt.checked_at")
    return receipt


def validate_budget_receipt(
    value: object,
    *,
    problem_id: str,
    target_card_sha256: str,
) -> dict[str, Any]:
    receipt = _exact(value, frozenset({
        "schema", "problem_id", "target_card_sha256", "limits",
        "maximum_artifact_bytes", "retain_failures", "stop_conditions", "checked_at",
    }), "budget_receipt")
    _receipt_common(receipt, schema=BUDGET_RECEIPT_SCHEMA, problem_id=problem_id, target_card_sha256=target_card_sha256, label="budget_receipt")
    limits = _exact(receipt["limits"], RESOURCE_FIELDS, "budget_receipt.limits")
    for field in sorted(limits):
        _integer(limits[field], f"budget_receipt.limits.{field}", minimum=1)
    _integer(receipt["maximum_artifact_bytes"], "budget_receipt.maximum_artifact_bytes", minimum=1, maximum=1 << 40)
    if _boolean(receipt["retain_failures"], "budget_receipt.retain_failures") is not True:
        _fail("budget_receipt.retain_failures", "must be true")
    _text_list(receipt["stop_conditions"], "budget_receipt.stop_conditions", minimum_items=1, maximum_items=32, unique=True)
    _date(receipt["checked_at"], "budget_receipt.checked_at")
    return receipt


def validate_target_bundle(
    value: object,
    *,
    root: Path,
    problem: dict[str, Any],
    verifier_registry: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    bundle = _exact(value, frozenset({
        "schema",
        "problem_id",
        "problem_card_sha256",
        "target_card",
        "baseline_receipts",
        "review_receipts",
        "red_team_receipt",
        "budget_receipt",
    }), "target_bundle")
    if bundle["schema"] != TARGET_BUNDLE_SCHEMA:
        _fail("target_bundle.schema", f"must be {TARGET_BUNDLE_SCHEMA}")
    problem_id = problem["id"]
    if _problem_id_value(bundle["problem_id"], "target_bundle.problem_id") != problem_id:
        _fail("target_bundle.problem_id", "bundle belongs to another problem")
    problem_hash = canonical_sha256(problem)
    if _sha(bundle["problem_card_sha256"], "target_bundle.problem_card_sha256") != problem_hash:
        _fail("target_bundle.problem_card_sha256", "bundle does not bind the exact problem card")

    target_binding, target_path = validate_file_binding(bundle["target_card"], root=root, label="target_bundle.target_card")
    target_value = load_json(target_path)
    target = validate_target_card(
        target_value,
        root=root,
        expected_problem_id=problem_id,
        expected_problem_card_sha256=problem_hash,
        expected_source_revision=problem["formalization"]["revision"],
    )
    target_sha = target_binding["sha256"]
    verifier_id = target["verifier_id"]
    verifier = verifier_registry.get(verifier_id)
    if verifier is None:
        _fail("target_card.verifier_id", f"unregistered verifier {verifier_id!r}")
    verification_mode = _verification_mode_value(
        problem["verification"]["mode"], "problem.verification.mode"
    )
    if verifier["manifest_value"]["binds_verification_mode"] != verification_mode:
        _fail(
            "verifier_manifest.binds_verification_mode",
            "does not match problem.verification.mode",
        )
    verifier_manifest_sha = verifier["manifest"]["sha256"]

    baseline_bindings = bundle["baseline_receipts"]
    if type(baseline_bindings) is not list or not baseline_bindings:
        _fail("target_bundle.baseline_receipts", "must bind at least one baseline receipt")
    for index, binding in enumerate(baseline_bindings):
        _bound, receipt = _load_bound_json(binding, root=root, label=f"target_bundle.baseline_receipts[{index}]")
        baseline = validate_baseline_receipt(
            receipt,
            root=root,
            problem_id=problem_id,
            target_card_sha256=target_sha,
            source_revision=target["source_revision"],
        )
        if baseline["checked_at"] < problem["source"]["checked_at"]:
            _fail("baseline_receipt.checked_at", "predates the problem card status check")

    review_bindings = bundle["review_receipts"]
    if type(review_bindings) is not list or len(review_bindings) < 2:
        _fail("target_bundle.review_receipts", "must bind at least two independent review receipts")
    reviews = []
    for index, binding in enumerate(review_bindings):
        _bound, receipt = _load_bound_json(binding, root=root, label=f"target_bundle.review_receipts[{index}]")
        reviews.append(validate_review_receipt(
            receipt,
            root=root,
            problem_id=problem_id,
            target_card_sha256=target_sha,
            source_revision=target["source_revision"],
        ))
    reviewers = [review["reviewer_id"] for review in reviews]
    if len(reviewers) != len(set(reviewers)):
        _fail("target_bundle.review_receipts", "reviewers must be distinct")
    if any(review["verdict"] != "PASS" for review in reviews):
        _fail("target_bundle.review_receipts", "every active review verdict must pass")
    if any(review["checked_at"] < problem["source"]["checked_at"] for review in reviews):
        _fail("target_bundle.review_receipts", "an active review predates the problem status check")
    axes = {review["axis"] for review in reviews}
    if not {"STATEMENT_FIDELITY", "OPEN_STATUS_AND_NOVELTY"} <= axes:
        _fail("target_bundle.review_receipts", "statement-fidelity and open-status reviews are both required")

    _red_binding, red_receipt = _load_bound_json(bundle["red_team_receipt"], root=root, label="target_bundle.red_team_receipt")
    red = validate_red_team_receipt(
        red_receipt,
        root=root,
        problem_id=problem_id,
        target_card_sha256=target_sha,
        verifier_id=verifier_id,
        verifier_manifest_sha256=verifier_manifest_sha,
    )
    if red["reviewer_id"] in set(reviewers):
        _fail("target_bundle.red_team_receipt", "red-team reviewer must be distinct from target reviewers")
    if red["checked_at"] < problem["source"]["checked_at"]:
        _fail("target_bundle.red_team_receipt", "red-team receipt predates the problem status check")

    _budget_binding, budget_receipt = _load_bound_json(bundle["budget_receipt"], root=root, label="target_bundle.budget_receipt")
    budget = validate_budget_receipt(budget_receipt, problem_id=problem_id, target_card_sha256=target_sha)
    if budget["checked_at"] < problem["source"]["checked_at"]:
        _fail("target_bundle.budget_receipt", "budget receipt predates the problem status check")
    return {
        "bundle": bundle,
        "target_card": target,
        "target_card_sha256": target_sha,
        "verification_mode": verification_mode,
        "verifier_id": verifier_id,
    }


__all__ = [
    "ACTIVE_PORTFOLIO_SCHEMA",
    "BASELINE_RECEIPT_SCHEMA",
    "BUDGET_RECEIPT_SCHEMA",
    "ContractError",
    "MAX_BOUND_FILE_BYTES",
    "MAX_JSON_BYTES",
    "PROBLEM_CARD_SCHEMA",
    "RED_TEAM_RECEIPT_SCHEMA",
    "REVIEW_ATTESTATION_SCOPE",
    "REVIEW_RECEIPT_SCHEMA",
    "TARGET_BUNDLE_SCHEMA",
    "TARGET_CARD_SCHEMA",
    "VERIFIER_MANIFEST_SCHEMA",
    "VERIFIER_REGISTRY_SCHEMA",
    "canonical_json_bytes",
    "canonical_sha256",
    "load_json",
    "make_file_binding",
    "raw_sha256",
    "validate_file_binding",
    "validate_problem_card",
    "validate_problem_catalog",
    "validate_review_receipt",
    "validate_target_bundle",
    "validate_verifier_registry",
]
