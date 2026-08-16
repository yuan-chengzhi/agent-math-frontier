#!/usr/bin/env python3
"""Fail-closed dispatcher for two independent DD(3,9) checkers."""

from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
from typing import NoReturn


VERIFIER_ID = "amf.dd39.exact.v1"
RESULT_SCHEMA = "AMF_VERIFIER_RESULT_1"
DISPATCHER_ID = "DISPATCH_PRIMARY_AND_SECONDARY"
PRIMARY_ID = "PRIMARY_ALL_PAIRS_QUEUE_BFS"
SECONDARY_ID = "SECONDARY_BITSET_WAVEFRONT"
HERE = Path(__file__).resolve().parent
PRIMARY_PATH = HERE / "primary.py"
SECONDARY_PATH = HERE / "secondary.py"
MAXIMUM_INPUT_BYTES = 262_144
MAXIMUM_CHECKER_OUTPUT_BYTES = 65_536
CHECKER_TIMEOUT_SECONDS = 30


class DispatchFailure(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _fail(code: str) -> NoReturn:
    raise DispatchFailure(code)


def _pairs_without_duplicates(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            _fail("CHECKER_INVALID_OUTPUT")
        result[key] = value
    return result


def _forbid_number(_token: str) -> NoReturn:
    _fail("CHECKER_INVALID_OUTPUT")


def _small_integer(token: str) -> int:
    if len(token) > 19:
        _fail("CHECKER_INVALID_OUTPUT")
    try:
        value = int(token)
    except ValueError:
        _fail("CHECKER_INVALID_OUTPUT")
    if not -(1 << 63) <= value <= (1 << 63) - 1:
        _fail("CHECKER_INVALID_OUTPUT")
    return value


def _blank_facts() -> dict[str, object]:
    return {
        "connected": None,
        "diameter": None,
        "edge_count": None,
        "max_degree": None,
        "n": None,
    }


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
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_dev != named.st_dev
            or opened.st_ino != named.st_ino
            or opened.st_size != named.st_size
        ):
            _fail("INPUT_CHANGED")
        payload = bytearray()
        while len(payload) < opened.st_size:
            chunk = os.read(descriptor, min(65_536, opened.st_size - len(payload)))
            if not chunk:
                _fail("INPUT_CHANGED")
            payload.extend(chunk)
        if os.read(descriptor, 1):
            _fail("INPUT_CHANGED")
        final = os.fstat(descriptor)
        if (
            final.st_size != opened.st_size
            or final.st_mtime_ns != opened.st_mtime_ns
            or final.st_ctime_ns != opened.st_ctime_ns
        ):
            _fail("INPUT_CHANGED")
        return bytes(payload)
    except OSError:
        _fail("INPUT_UNAVAILABLE")
    finally:
        os.close(descriptor)


def _validate_facts(value: object, *, accepted: bool) -> dict[str, object]:
    keys = {"connected", "diameter", "edge_count", "max_degree", "n"}
    if type(value) is not dict or set(value) != keys:
        _fail("CHECKER_INVALID_OUTPUT")
    facts = dict(value)
    if facts["connected"] is not None and type(facts["connected"]) is not bool:
        _fail("CHECKER_INVALID_OUTPUT")
    for field in ("diameter", "edge_count", "max_degree", "n"):
        item = facts[field]
        if item is not None and (type(item) is not int or item < 0 or item > (1 << 31)):
            _fail("CHECKER_INVALID_OUTPUT")
    if accepted and not (
        facts["connected"] is True
        and type(facts["diameter"]) is int
        and facts["diameter"] <= 9
        and type(facts["edge_count"]) is int
        and type(facts["max_degree"]) is int
        and facts["max_degree"] <= 3
        and type(facts["n"]) is int
        and 601 <= facts["n"] <= 1534
        and facts["edge_count"] <= 3 * facts["n"] // 2
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
            parse_int=_small_integer,
            parse_float=_forbid_number,
            parse_constant=_forbid_number,
        )
    except DispatchFailure:
        raise
    except (UnicodeError, json.JSONDecodeError, RecursionError, ValueError):
        _fail("CHECKER_INVALID_OUTPUT")
    expected_fields = {
        "accepted", "checker", "facts", "reason_code", "schema", "verifier_id",
    }
    if type(value) is not dict or set(value) != expected_fields:
        _fail("CHECKER_INVALID_OUTPUT")
    if value["schema"] != RESULT_SCHEMA or value["verifier_id"] != VERIFIER_ID:
        _fail("CHECKER_INVALID_OUTPUT")
    if value["checker"] != expected_checker:
        _fail("CHECKER_INVALID_OUTPUT")
    if type(value["accepted"]) is not bool:
        _fail("CHECKER_INVALID_OUTPUT")
    if type(value["reason_code"]) is not str or not 1 <= len(value["reason_code"]) <= 64:
        _fail("CHECKER_INVALID_OUTPUT")
    facts = _validate_facts(value["facts"], accepted=value["accepted"])
    if return_code == 0:
        if value["accepted"] is not True or value["reason_code"] != "ACCEPTED":
            _fail("CHECKER_INVALID_OUTPUT")
        infrastructure_failure = False
    elif return_code == 1:
        if value["accepted"] is not False or value["reason_code"] == "ACCEPTED":
            _fail("CHECKER_INVALID_OUTPUT")
        if value["reason_code"] == "RESOURCE_FAILURE":
            _fail("CHECKER_INVALID_OUTPUT")
        infrastructure_failure = False
    elif return_code == 2:
        if value["accepted"] is not False or value["reason_code"] == "ACCEPTED":
            _fail("CHECKER_INVALID_OUTPUT")
        infrastructure_failure = True
    else:
        _fail("CHECKER_PROCESS_FAILURE")
    return {
        "accepted": value["accepted"],
        "facts": facts,
        "reason_code": value["reason_code"],
    }, infrastructure_failure


def _run_checker(
    checker_path: Path,
    expected_checker: str,
    candidate_path: Path,
) -> tuple[dict[str, object], bool]:
    try:
        checker_stat = checker_path.lstat()
        if stat.S_ISLNK(checker_stat.st_mode) or not stat.S_ISREG(checker_stat.st_mode):
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
    """Return (result, infrastructure_failure).

    Alternate checker paths are an in-process test seam; the command-line
    interface never accepts checker selection from a candidate author.
    """

    try:
        raw = _read_snapshot(candidate_path)
        with tempfile.TemporaryDirectory(prefix="amf-dd39-") as directory:
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
