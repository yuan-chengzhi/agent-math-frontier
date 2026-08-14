#!/usr/bin/env python3
"""Fail-closed dispatcher for the two independent stretched-LR checkers."""

from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
from typing import NoReturn


VERIFIER_ID = "amf.stretched-lr.exact.v1"
RESULT_SCHEMA = "AMF_VERIFIER_RESULT_1"
DISPATCHER_ID = "DISPATCH_LR_PRIMARY_AND_SECONDARY"
PRIMARY_ID = "PRIMARY_LR_TABLEAUX_AND_NEWTON_DIFFERENCES"
SECONDARY_ID = "SECONDARY_JACOBI_TRUDI_PIERI_AND_VANDERMONDE"
HERE = Path(__file__).resolve().parent
PRIMARY_PATH = HERE / "primary.py"
SECONDARY_PATH = HERE / "secondary.py"
MAXIMUM_INPUT_BYTES = 262_144
MAXIMUM_CHECKER_OUTPUT_BYTES = 262_144
CHECKER_TIMEOUT_SECONDS = 180
MAXIMUM_INTEGER_BITS = 4096

_FACT_FIELDS = {
    "coefficients_sha256",
    "degree_bound",
    "first_negative_degree",
    "interpolation_points",
    "lambda",
    "lambda_size",
    "mu",
    "mu_size",
    "nu",
    "nu_size",
    "sample_values_sha256",
}


class DispatchFailure(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _fail(code: str) -> NoReturn:
    raise DispatchFailure(code)


def _blank_facts() -> dict[str, object]:
    return {key: None for key in sorted(_FACT_FIELDS)}


def _result(
    accepted: bool,
    reason_code: str,
    facts: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "accepted": accepted,
        "checker": DISPATCHER_ID,
        "facts": _blank_facts() if facts is None else facts,
        "reason_code": reason_code,
        "schema": RESULT_SCHEMA,
        "verifier_id": VERIFIER_ID,
    }


def _pairs_without_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            _fail("CHECKER_INVALID_OUTPUT")
        value[key] = item
    return value


def _forbid_number(_token: str) -> NoReturn:
    _fail("CHECKER_INVALID_OUTPUT")


def _bounded_integer(token: str) -> int:
    digits = token[1:] if token.startswith("-") else token
    if not digits or len(digits) > 1234:
        _fail("CHECKER_INVALID_OUTPUT")
    try:
        value = int(token)
    except ValueError:
        _fail("CHECKER_INVALID_OUTPUT")
    if value.bit_length() > MAXIMUM_INTEGER_BITS:
        _fail("CHECKER_INVALID_OUTPUT")
    return value


def _read_snapshot(path: Path) -> bytes:
    try:
        named = path.lstat()
    except OSError:
        _fail("INPUT_UNAVAILABLE")
    if stat.S_ISLNK(named.st_mode) or not stat.S_ISREG(named.st_mode):
        _fail("INPUT_NOT_REGULAR")
    if named.st_size > MAXIMUM_INPUT_BYTES:
        _fail("INPUT_TOO_LARGE")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        _fail("INPUT_UNAVAILABLE")
    try:
        actual = os.fstat(descriptor)
        if (
            not stat.S_ISREG(actual.st_mode)
            or (actual.st_dev, actual.st_ino, actual.st_size)
            != (named.st_dev, named.st_ino, named.st_size)
        ):
            _fail("INPUT_CHANGED")
        data = bytearray()
        while len(data) < actual.st_size:
            chunk = os.read(descriptor, min(65_536, actual.st_size - len(data)))
            if not chunk:
                _fail("INPUT_CHANGED")
            data.extend(chunk)
        if os.read(descriptor, 1):
            _fail("INPUT_CHANGED")
        final = os.fstat(descriptor)
        if (final.st_size, final.st_mtime_ns, final.st_ctime_ns) != (
            actual.st_size,
            actual.st_mtime_ns,
            actual.st_ctime_ns,
        ):
            _fail("INPUT_CHANGED")
        return bytes(data)
    except OSError:
        _fail("INPUT_UNAVAILABLE")
    finally:
        os.close(descriptor)


def _partition(value: object) -> list[int]:
    if type(value) is not list or not 1 <= len(value) <= 7:
        _fail("CHECKER_INVALID_OUTPUT")
    if any(type(item) is not int or not 1 <= item <= 30 for item in value):
        _fail("CHECKER_INVALID_OUTPUT")
    if any(value[index] < value[index + 1] for index in range(len(value) - 1)):
        _fail("CHECKER_INVALID_OUTPUT")
    if sum(value) > 30:
        _fail("CHECKER_INVALID_OUTPUT")
    return list(value)


def _validate_facts(value: object, *, accepted: bool) -> dict[str, object]:
    if type(value) is not dict or set(value) != _FACT_FIELDS:
        _fail("CHECKER_INVALID_OUTPUT")
    facts = dict(value)
    if not accepted:
        if any(item is not None for item in facts.values()):
            _fail("CHECKER_INVALID_OUTPUT")
        return facts

    outer = _partition(facts["lambda"])
    first_inner = _partition(facts["mu"])
    second_inner = _partition(facts["nu"])
    for field, partition in (
        ("lambda_size", outer),
        ("mu_size", first_inner),
        ("nu_size", second_inner),
    ):
        if type(facts[field]) is not int or facts[field] != sum(partition):
            _fail("CHECKER_INVALID_OUTPUT")
    if facts["lambda_size"] != facts["mu_size"] + facts["nu_size"]:
        _fail("CHECKER_INVALID_OUTPUT")
    expected_bound = len(outer) * (len(outer) + 1) // 2
    if facts["degree_bound"] != expected_bound:
        _fail("CHECKER_INVALID_OUTPUT")
    if facts["interpolation_points"] != 29:
        _fail("CHECKER_INVALID_OUTPUT")
    negative_degree = facts["first_negative_degree"]
    if type(negative_degree) is not int or not 0 <= negative_degree <= expected_bound:
        _fail("CHECKER_INVALID_OUTPUT")
    for field in ("coefficients_sha256", "sample_values_sha256"):
        digest = facts[field]
        if (
            type(digest) is not str
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            _fail("CHECKER_INVALID_OUTPUT")
    return facts


def _parse_checker_result(
    raw: bytes,
    *,
    expected_checker: str,
    return_code: int,
) -> tuple[dict[str, object], bool]:
    if len(raw) > MAXIMUM_CHECKER_OUTPUT_BYTES:
        _fail("CHECKER_OUTPUT_LIMIT")
    try:
        value = json.loads(
            raw.decode("ascii", errors="strict"),
            object_pairs_hook=_pairs_without_duplicates,
            parse_int=_bounded_integer,
            parse_float=_forbid_number,
            parse_constant=_forbid_number,
        )
    except DispatchFailure:
        raise
    except (UnicodeError, json.JSONDecodeError, RecursionError, ValueError):
        _fail("CHECKER_INVALID_OUTPUT")
    required = {"accepted", "checker", "facts", "reason_code", "schema", "verifier_id"}
    if type(value) is not dict or set(value) != required:
        _fail("CHECKER_INVALID_OUTPUT")
    if value["schema"] != RESULT_SCHEMA or value["verifier_id"] != VERIFIER_ID:
        _fail("CHECKER_INVALID_OUTPUT")
    if value["checker"] != expected_checker:
        _fail("CHECKER_INVALID_OUTPUT")
    if type(value["accepted"]) is not bool:
        _fail("CHECKER_INVALID_OUTPUT")
    reason = value["reason_code"]
    if type(reason) is not str or not 1 <= len(reason) <= 64:
        _fail("CHECKER_INVALID_OUTPUT")
    accepted = bool(value["accepted"])
    facts = _validate_facts(value["facts"], accepted=accepted)
    if return_code == 0:
        if not accepted or reason != "ACCEPTED":
            _fail("CHECKER_INVALID_OUTPUT")
        infrastructure_failure = False
    elif return_code == 1:
        if accepted or reason == "ACCEPTED":
            _fail("CHECKER_INVALID_OUTPUT")
        infrastructure_failure = False
    elif return_code == 2:
        if accepted or reason == "ACCEPTED":
            _fail("CHECKER_INVALID_OUTPUT")
        infrastructure_failure = True
    else:
        _fail("CHECKER_PROCESS_FAILURE")
    return {
        "accepted": accepted,
        "facts": facts,
        "reason_code": reason,
    }, infrastructure_failure


def _run_checker(
    checker_path: Path,
    expected_checker: str,
    candidate_path: Path,
) -> tuple[dict[str, object], bool]:
    try:
        checker_status = checker_path.lstat()
        if stat.S_ISLNK(checker_status.st_mode) or not stat.S_ISREG(checker_status.st_mode):
            _fail("CHECKER_UNAVAILABLE")
        completed = subprocess.run(
            [sys.executable, "-I", str(checker_path), str(candidate_path)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(HERE),
            env={
                "LANG": "C",
                "LC_ALL": "C",
                "PATH": "/usr/bin:/bin",
                "PYTHONHASHSEED": "0",
            },
            check=False,
            timeout=CHECKER_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        _fail("CHECKER_TIMEOUT")
    except OSError:
        _fail("CHECKER_UNAVAILABLE")
    if completed.stderr:
        _fail("CHECKER_PROCESS_FAILURE")
    return _parse_checker_result(
        completed.stdout,
        expected_checker=expected_checker,
        return_code=completed.returncode,
    )


def dispatch_path(
    candidate_path: Path,
    *,
    primary_path: Path = PRIMARY_PATH,
    secondary_path: Path = SECONDARY_PATH,
) -> tuple[dict[str, object], bool]:
    """Return ``(result, infrastructure_failure)``.

    Alternate checker paths are an in-process test seam.  The command-line
    verifier never accepts checker selection from a candidate author.
    """

    try:
        raw = _read_snapshot(candidate_path)
        with tempfile.TemporaryDirectory(prefix="amf-stretched-lr-") as directory:
            snapshot = Path(directory) / "candidate.json"
            descriptor = os.open(
                snapshot,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0),
                0o400,
            )
            try:
                offset = 0
                while offset < len(raw):
                    written = os.write(descriptor, raw[offset:])
                    if written <= 0:
                        _fail("SNAPSHOT_FAILURE")
                    offset += written
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            primary, primary_infrastructure = _run_checker(
                primary_path, PRIMARY_ID, snapshot
            )
            secondary, secondary_infrastructure = _run_checker(
                secondary_path, SECONDARY_ID, snapshot
            )
    except DispatchFailure as failure:
        return _result(False, failure.code), True
    except (MemoryError, OverflowError):
        return _result(False, "DISPATCH_RESOURCE_FAILURE"), True

    if primary_infrastructure or secondary_infrastructure:
        return _result(False, "CHECKER_INFRASTRUCTURE_FAILURE"), True
    if primary != secondary:
        return _result(False, "CHECKER_DISAGREEMENT"), True
    return _result(
        bool(primary["accepted"]),
        str(primary["reason_code"]),
        dict(primary["facts"]),
    ), False


def _emit(result: dict[str, object]) -> None:
    encoded = json.dumps(
        result,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    sys.stdout.buffer.write(encoded + b"\n")


def main(arguments: list[str]) -> int:
    if len(arguments) != 3 or arguments[1] != "--candidate":
        _emit(_result(False, "USAGE_ERROR"))
        return 2
    result, infrastructure_failure = dispatch_path(Path(arguments[2]))
    _emit(result)
    if infrastructure_failure:
        return 2
    return 0 if result["accepted"] is True else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
