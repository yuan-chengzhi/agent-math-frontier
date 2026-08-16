#!/usr/bin/env python3
"""Primary exact checker for the degree--diameter (3, 9) target.

This implementation deliberately owns its parser and graph logic.  The
secondary checker does not import it: agreement is established by the
dispatcher only after two separate processes have inspected the same byte
snapshot.
"""

from __future__ import annotations

from collections import deque
import json
import os
from pathlib import Path
import stat
import sys
from typing import Any, NoReturn


VERIFIER_ID = "amf.dd39.exact.v1"
RESULT_SCHEMA = "AMF_VERIFIER_RESULT_1"
CANDIDATE_SCHEMA = "AMF_DD39_CANDIDATE_1"
BASELINE_SCHEMA = "AMF_DD39_BASELINE_GRAPH_1"
CHECKER_ID = "PRIMARY_ALL_PAIRS_QUEUE_BFS"
MINIMUM_ORDER = 601
MAXIMUM_ORDER = 1534  # Moore bound for maximum degree 3 and diameter 9.
MAXIMUM_EDGES = 3 * MAXIMUM_ORDER // 2
MAXIMUM_INPUT_BYTES = 262_144


class CheckFailure(ValueError):
    """Bounded public failure with a stable, non-reflective reason code."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _fail(code: str) -> NoReturn:
    raise CheckFailure(code)


def _pairs_no_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            _fail("DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _parse_int(token: str) -> int:
    # Reject enormous integer literals before constructing an unbounded Python
    # integer.  Every value admitted by the format is nonnegative and <= 1533.
    if len(token) > 19:
        _fail("INTEGER_OUT_OF_RANGE")
    try:
        value = int(token, 10)
    except ValueError:
        _fail("INVALID_JSON")
    if value < -(1 << 63) or value > (1 << 63) - 1:
        _fail("INTEGER_OUT_OF_RANGE")
    return value


def _reject_number(_token: str) -> NoReturn:
    _fail("NON_INTEGER_NUMBER")


def read_regular_file(path: Path) -> bytes:
    """Read one bounded regular non-symlink file with basic race checks."""

    try:
        before = path.lstat()
    except OSError:
        _fail("INPUT_UNAVAILABLE")
    if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
        _fail("INPUT_NOT_REGULAR")
    if before.st_size > MAXIMUM_INPUT_BYTES:
        _fail("INPUT_TOO_LARGE")

    flags = os.O_RDONLY
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        _fail("INPUT_UNAVAILABLE")
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_dev != before.st_dev
            or opened.st_ino != before.st_ino
            or opened.st_size != before.st_size
        ):
            _fail("INPUT_CHANGED")
        chunks: list[bytes] = []
        remaining = opened.st_size
        while remaining:
            chunk = os.read(descriptor, min(65_536, remaining))
            if not chunk:
                _fail("INPUT_CHANGED")
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(descriptor, 1):
            _fail("INPUT_CHANGED")
        after = os.fstat(descriptor)
        if (
            after.st_size != opened.st_size
            or after.st_mtime_ns != opened.st_mtime_ns
            or after.st_ctime_ns != opened.st_ctime_ns
        ):
            _fail("INPUT_CHANGED")
        return b"".join(chunks)
    except OSError:
        _fail("INPUT_UNAVAILABLE")
    finally:
        os.close(descriptor)


def decode_document(raw: bytes) -> dict[str, Any]:
    try:
        text = raw.decode("utf-8", errors="strict")
        value = json.loads(
            text,
            object_pairs_hook=_pairs_no_duplicates,
            parse_int=_parse_int,
            parse_float=_reject_number,
            parse_constant=_reject_number,
        )
    except CheckFailure:
        raise
    except (UnicodeError, json.JSONDecodeError, RecursionError, ValueError):
        _fail("INVALID_JSON")
    if type(value) is not dict:
        _fail("INVALID_DOCUMENT")
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
        "checker": CHECKER_ID,
        "facts": _blank_facts() if facts is None else facts,
        "reason_code": reason_code,
        "schema": RESULT_SCHEMA,
        "verifier_id": VERIFIER_ID,
    }


def evaluate_document(
    document: object,
    *,
    minimum_order: int = MINIMUM_ORDER,
    expected_schema: str = CANDIDATE_SCHEMA,
) -> dict[str, object]:
    """Validate and measure a graph using queue-based all-pairs BFS."""

    if type(document) is not dict or set(document) != {"schema", "n", "edges"}:
        return _result(False, "INVALID_DOCUMENT")
    if document["schema"] != expected_schema:
        return _result(False, "INVALID_SCHEMA")
    n = document["n"]
    if type(n) is not int or not minimum_order <= n <= MAXIMUM_ORDER:
        return _result(False, "ORDER_OUT_OF_RANGE")
    edges = document["edges"]
    if type(edges) is not list:
        return _result(False, "INVALID_EDGE_LIST")
    if len(edges) > MAXIMUM_EDGES:
        return _result(False, "EDGE_COUNT_LIMIT")

    adjacency: list[list[int]] = [[] for _ in range(n)]
    seen: set[tuple[int, int]] = set()
    for edge in edges:
        if type(edge) is not list or len(edge) != 2:
            return _result(False, "INVALID_EDGE")
        left, right = edge
        if type(left) is not int or type(right) is not int:
            return _result(False, "INVALID_EDGE")
        if left < 0 or right < 0 or left >= n or right >= n:
            return _result(False, "VERTEX_OUT_OF_RANGE")
        if left == right:
            return _result(False, "SELF_LOOP")
        if left > right:
            return _result(False, "NONCANONICAL_EDGE")
        pair = (left, right)
        if pair in seen:
            return _result(False, "DUPLICATE_EDGE")
        seen.add(pair)
        adjacency[left].append(right)
        adjacency[right].append(left)

    maximum_degree = max((len(neighbors) for neighbors in adjacency), default=0)
    facts: dict[str, object] = {
        "connected": None,
        "diameter": None,
        "edge_count": len(edges),
        "max_degree": maximum_degree,
        "n": n,
    }
    if maximum_degree > 3:
        return _result(False, "DEGREE_LIMIT", facts)

    diameter = 0
    for source in range(n):
        distances = [-1] * n
        distances[source] = 0
        pending: deque[int] = deque([source])
        while pending:
            vertex = pending.popleft()
            next_distance = distances[vertex] + 1
            for neighbor in adjacency[vertex]:
                if distances[neighbor] == -1:
                    distances[neighbor] = next_distance
                    pending.append(neighbor)
        if -1 in distances:
            facts["connected"] = False
            return _result(False, "DISCONNECTED", facts)
        eccentricity = max(distances)
        if eccentricity > diameter:
            diameter = eccentricity

    facts["connected"] = True
    facts["diameter"] = diameter
    if diameter > 9:
        return _result(False, "DIAMETER_LIMIT", facts)
    return _result(True, "ACCEPTED", facts)


def evaluate_path_with_status(path: Path) -> tuple[dict[str, object], bool]:
    """Return ``(result, infrastructure_failure)`` for the CLI boundary."""

    try:
        return evaluate_document(decode_document(read_regular_file(path))), False
    except CheckFailure as failure:
        return _result(False, failure.code), False
    except (MemoryError, OverflowError):
        return _result(False, "RESOURCE_FAILURE"), True


def evaluate_path(path: Path) -> dict[str, object]:
    """Compatibility wrapper for in-process callers."""

    return evaluate_path_with_status(path)[0]


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
        _emit(_result(False, "USAGE_ERROR"))
        return 2
    result, infrastructure_failure = evaluate_path_with_status(Path(argv[1]))
    _emit(result)
    if infrastructure_failure:
        return 2
    return 0 if result["accepted"] is True else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
