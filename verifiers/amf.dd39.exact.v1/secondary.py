#!/usr/bin/env python3
"""Independent bit-set wavefront checker for degree--diameter (3, 9).

No parser or graph routine is imported from the primary checker.  Distances
are computed by repeated bit-set neighborhood expansion rather than queue BFS.
"""

from __future__ import annotations

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
CHECKER_ID = "SECONDARY_BITSET_WAVEFRONT"
MINIMUM_ORDER = 601
MAXIMUM_ORDER = 1534
MAXIMUM_EDGES = 3 * MAXIMUM_ORDER // 2
MAXIMUM_INPUT_BYTES = 262_144


class CheckFailure(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _fail(code: str) -> NoReturn:
    raise CheckFailure(code)


def _object_without_duplicate_keys(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            _fail("DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _bounded_integer(token: str) -> int:
    if len(token) > 19:
        _fail("INTEGER_OUT_OF_RANGE")
    try:
        value = int(token)
    except ValueError:
        _fail("INVALID_JSON")
    if not -(1 << 63) <= value <= (1 << 63) - 1:
        _fail("INTEGER_OUT_OF_RANGE")
    return value


def _forbid_noninteger(_token: str) -> NoReturn:
    _fail("NON_INTEGER_NUMBER")


def read_regular_file(path: Path) -> bytes:
    try:
        path_stat = path.lstat()
    except OSError:
        _fail("INPUT_UNAVAILABLE")
    if stat.S_ISLNK(path_stat.st_mode) or not stat.S_ISREG(path_stat.st_mode):
        _fail("INPUT_NOT_REGULAR")
    if path_stat.st_size > MAXIMUM_INPUT_BYTES:
        _fail("INPUT_TOO_LARGE")

    open_flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    open_flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, open_flags)
    except OSError:
        _fail("INPUT_UNAVAILABLE")
    try:
        first_stat = os.fstat(fd)
        if not stat.S_ISREG(first_stat.st_mode):
            _fail("INPUT_NOT_REGULAR")
        if (
            first_stat.st_dev != path_stat.st_dev
            or first_stat.st_ino != path_stat.st_ino
            or first_stat.st_size != path_stat.st_size
        ):
            _fail("INPUT_CHANGED")
        data = bytearray()
        while len(data) < first_stat.st_size:
            block = os.read(fd, min(65_536, first_stat.st_size - len(data)))
            if not block:
                _fail("INPUT_CHANGED")
            data.extend(block)
        if os.read(fd, 1):
            _fail("INPUT_CHANGED")
        second_stat = os.fstat(fd)
        if (
            second_stat.st_size != first_stat.st_size
            or second_stat.st_mtime_ns != first_stat.st_mtime_ns
            or second_stat.st_ctime_ns != first_stat.st_ctime_ns
        ):
            _fail("INPUT_CHANGED")
        return bytes(data)
    except OSError:
        _fail("INPUT_UNAVAILABLE")
    finally:
        os.close(fd)


def decode_document(raw: bytes) -> dict[str, Any]:
    try:
        value = json.loads(
            raw.decode("utf-8", "strict"),
            object_pairs_hook=_object_without_duplicate_keys,
            parse_int=_bounded_integer,
            parse_float=_forbid_noninteger,
            parse_constant=_forbid_noninteger,
        )
    except CheckFailure:
        raise
    except (UnicodeError, json.JSONDecodeError, RecursionError, ValueError):
        _fail("INVALID_JSON")
    if not isinstance(value, dict):
        _fail("INVALID_DOCUMENT")
    return value


def _empty_facts() -> dict[str, object]:
    return dict(
        connected=None,
        diameter=None,
        edge_count=None,
        max_degree=None,
        n=None,
    )


def _result(
    accepted: bool,
    reason_code: str,
    facts: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "accepted": accepted,
        "checker": CHECKER_ID,
        "facts": _empty_facts() if facts is None else facts,
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
    if not isinstance(document, dict) or type(document) is not dict:
        return _result(False, "INVALID_DOCUMENT")
    if frozenset(document.keys()) != frozenset(("schema", "n", "edges")):
        return _result(False, "INVALID_DOCUMENT")
    if document.get("schema") != expected_schema:
        return _result(False, "INVALID_SCHEMA")
    order = document.get("n")
    if type(order) is not int or order < minimum_order or order > MAXIMUM_ORDER:
        return _result(False, "ORDER_OUT_OF_RANGE")
    edge_rows = document.get("edges")
    if type(edge_rows) is not list:
        return _result(False, "INVALID_EDGE_LIST")
    if len(edge_rows) > MAXIMUM_EDGES:
        return _result(False, "EDGE_COUNT_LIMIT")

    neighbor_masks = [0 for _ in range(order)]
    degree_counts = [0 for _ in range(order)]
    encoded_edges: set[int] = set()
    for row in edge_rows:
        if type(row) is not list or len(row) != 2:
            return _result(False, "INVALID_EDGE")
        first = row[0]
        second = row[1]
        if type(first) is not int or type(second) is not int:
            return _result(False, "INVALID_EDGE")
        if first < 0 or second < 0 or first >= order or second >= order:
            return _result(False, "VERTEX_OUT_OF_RANGE")
        if first == second:
            return _result(False, "SELF_LOOP")
        if first > second:
            return _result(False, "NONCANONICAL_EDGE")
        edge_code = first * MAXIMUM_ORDER + second
        if edge_code in encoded_edges:
            return _result(False, "DUPLICATE_EDGE")
        encoded_edges.add(edge_code)
        neighbor_masks[first] |= 1 << second
        neighbor_masks[second] |= 1 << first
        degree_counts[first] += 1
        degree_counts[second] += 1

    maximum_degree = max(degree_counts, default=0)
    facts: dict[str, object] = {
        "connected": None,
        "diameter": None,
        "edge_count": len(edge_rows),
        "max_degree": maximum_degree,
        "n": order,
    }
    if maximum_degree > 3:
        return _result(False, "DEGREE_LIMIT", facts)

    universe = (1 << order) - 1
    graph_diameter = 0
    for source in range(order):
        reached = 1 << source
        frontier = reached
        eccentricity = 0
        while reached != universe:
            expanded = 0
            cursor = frontier
            while cursor:
                least_bit = cursor & -cursor
                vertex = least_bit.bit_length() - 1
                expanded |= neighbor_masks[vertex]
                cursor ^= least_bit
            frontier = expanded & ~reached
            if frontier == 0:
                facts["connected"] = False
                return _result(False, "DISCONNECTED", facts)
            reached |= frontier
            eccentricity += 1
        if eccentricity > graph_diameter:
            graph_diameter = eccentricity

    facts["connected"] = True
    facts["diameter"] = graph_diameter
    if graph_diameter > 9:
        return _result(False, "DIAMETER_LIMIT", facts)
    return _result(True, "ACCEPTED", facts)


def evaluate_path_with_status(path: Path) -> tuple[dict[str, object], bool]:
    """Return ``(result, infrastructure_failure)`` for the CLI boundary."""

    try:
        raw = read_regular_file(path)
        parsed = decode_document(raw)
        return evaluate_document(parsed), False
    except CheckFailure as failure:
        return _result(False, failure.code), False
    except (MemoryError, OverflowError):
        return _result(False, "RESOURCE_FAILURE"), True


def evaluate_path(path: Path) -> dict[str, object]:
    """Compatibility wrapper for in-process callers."""

    return evaluate_path_with_status(path)[0]


def _print_result(result: dict[str, object]) -> None:
    encoded = json.dumps(
        result,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        ensure_ascii=True,
    ).encode("ascii")
    sys.stdout.buffer.write(encoded + b"\n")


def main(arguments: list[str]) -> int:
    if len(arguments) != 2:
        _print_result(_result(False, "USAGE_ERROR"))
        return 2
    answer, infrastructure_failure = evaluate_path_with_status(Path(arguments[1]))
    _print_result(answer)
    if infrastructure_failure:
        return 2
    return 0 if answer["accepted"] is True else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
