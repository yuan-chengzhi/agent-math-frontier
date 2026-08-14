#!/usr/bin/env python3
"""Provisionally rebased AIM #60 checker built on the audited v1 kernel."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


VERIFIER_ID = "amf.aim60.certificate.v2"
CANDIDATE_SCHEMA = "AMF_AIM60_CANDIDATE_2"
PROVISIONAL_PUBLIC_BASELINE_X = 1_455_090
MINIMUM_FIRST_PRIME_X = PROVISIONAL_PUBLIC_BASELINE_X + 1
BASE_PATH = Path(__file__).resolve().parents[1] / "amf.aim60.certificate.v1" / "check.py"


def _load_base():
    spec = importlib.util.spec_from_file_location("amf_aim60_v1_kernel", BASE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("v1 kernel unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASE = _load_base()


def _rebrand(result: dict[str, object]) -> dict[str, object]:
    branded = dict(result)
    branded["verifier_id"] = VERIFIER_ID
    return branded


def evaluate_document_with_status(document: object) -> tuple[dict[str, object], bool]:
    result, apparatus = BASE.evaluate_document_with_status(
        document,
        expected_schema=CANDIDATE_SCHEMA,
        minimum_first_prime_x=MINIMUM_FIRST_PRIME_X,
    )
    return _rebrand(result), apparatus


def evaluate_document(document: object) -> dict[str, object]:
    return evaluate_document_with_status(document)[0]


def evaluate_path_with_status(path: Path) -> tuple[dict[str, object], bool]:
    try:
        document = BASE.decode_document(BASE.read_regular_file(path))
    except BASE.CheckFailure as failure:
        return _rebrand(BASE._result(False, failure.code)), False
    except BASE.ApparatusFailure as failure:
        return _rebrand(BASE._result(False, failure.code)), True
    except (MemoryError, OverflowError):
        return _rebrand(BASE._result(False, "RESOURCE_FAILURE")), True
    return evaluate_document_with_status(document)


def _emit(result: dict[str, object]) -> None:
    payload = json.dumps(
        result,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii") + b"\n"
    sys.stdout.buffer.write(payload)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        _emit(_rebrand(BASE._result(False, "USAGE_ERROR")))
        return 2
    result, apparatus = evaluate_path_with_status(Path(argv[1]))
    _emit(result)
    if apparatus:
        return 2
    return 0 if result["accepted"] is True else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
