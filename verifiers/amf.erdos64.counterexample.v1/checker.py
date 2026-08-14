#!/usr/bin/env python3
"""Sound, resource-bounded exact checker for an Erdős--Gyárfás counterexample.

Acceptance means that the supplied finite simple graph has minimum degree at
least three and has no simple cycle of any power-of-two length 2^k, k >= 2.
The search is exhaustive only when it finishes. Hitting the deterministic step
ceiling is an apparatus error (exit 2), never a mathematical rejection.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import sys
from typing import Any, NoReturn


VERIFIER_ID = "amf.erdos64.counterexample.v1"
RESULT_SCHEMA = "AMF_VERIFIER_RESULT_1"
CANDIDATE_SCHEMA = "AMF_ERDOS64_GRAPH_COUNTEREXAMPLE_1"
CHECKER_ID = "CANONICAL_MIN_VERTEX_EXACT_CYCLE_DFS"
MINIMUM_ORDER = 4
MAXIMUM_ORDER = 64
MAXIMUM_EDGES = MAXIMUM_ORDER * (MAXIMUM_ORDER - 1) // 2
MAXIMUM_INPUT_BYTES = 262_144
MAXIMUM_SEARCH_STEPS = 20_000_000


class CandidateFailure(ValueError):
    """A malformed or mathematically failing candidate."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class ApparatusFailure(RuntimeError):
    """An inconclusive failure that must not be reported as rejection."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _candidate_fail(code: str) -> NoReturn:
    raise CandidateFailure(code)


def _apparatus_fail(code: str) -> NoReturn:
    raise ApparatusFailure(code)


def _pairs_no_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            _candidate_fail("DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _parse_int(token: str) -> int:
    if len(token) > 19:
        _candidate_fail("INTEGER_OUT_OF_RANGE")
    try:
        value = int(token, 10)
    except ValueError:
        _candidate_fail("INVALID_JSON")
    if not -(1 << 63) <= value <= (1 << 63) - 1:
        _candidate_fail("INTEGER_OUT_OF_RANGE")
    return value


def _reject_number(_token: str) -> NoReturn:
    _candidate_fail("NON_INTEGER_NUMBER")


def read_regular_file(path: Path) -> bytes:
    """Read one bounded regular non-symlink file with race checks."""

    try:
        before = path.lstat()
    except OSError:
        _apparatus_fail("INPUT_UNAVAILABLE")
    if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
        _apparatus_fail("INPUT_NOT_REGULAR")
    if before.st_size > MAXIMUM_INPUT_BYTES:
        _candidate_fail("INPUT_TOO_LARGE")

    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        _apparatus_fail("INPUT_UNAVAILABLE")
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_dev != before.st_dev
            or opened.st_ino != before.st_ino
            or opened.st_size != before.st_size
        ):
            _apparatus_fail("INPUT_CHANGED")
        chunks: list[bytes] = []
        remaining = opened.st_size
        while remaining:
            chunk = os.read(descriptor, min(65_536, remaining))
            if not chunk:
                _apparatus_fail("INPUT_CHANGED")
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(descriptor, 1):
            _apparatus_fail("INPUT_CHANGED")
        after = os.fstat(descriptor)
        if (
            after.st_size != opened.st_size
            or after.st_mtime_ns != opened.st_mtime_ns
            or after.st_ctime_ns != opened.st_ctime_ns
        ):
            _apparatus_fail("INPUT_CHANGED")
        return b"".join(chunks)
    except OSError:
        _apparatus_fail("INPUT_UNAVAILABLE")
    finally:
        os.close(descriptor)


def decode_document(raw: bytes) -> dict[str, Any]:
    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_pairs_no_duplicates,
            parse_int=_parse_int,
            parse_float=_reject_number,
            parse_constant=_reject_number,
        )
    except CandidateFailure:
        raise
    except (UnicodeError, json.JSONDecodeError, RecursionError, ValueError):
        _candidate_fail("INVALID_JSON")
    if type(value) is not dict:
        _candidate_fail("INVALID_DOCUMENT")
    return value


def power_of_two_cycle_lengths(n: int) -> list[int]:
    lengths: list[int] = []
    value = 4
    while value <= n:
        lengths.append(value)
        value *= 2
    return lengths


class SearchBudget:
    def __init__(self, limit: int):
        if type(limit) is not int or limit < 1:
            raise ValueError("search limit must be a positive integer")
        self.limit = limit
        self.steps = 0

    def tick(self) -> None:
        self.steps += 1
        if self.steps > self.limit:
            _apparatus_fail("SEARCH_STEP_LIMIT")


def find_simple_cycle_of_length(
    adjacency: list[tuple[int, ...]],
    length: int,
    budget: SearchBudget,
) -> list[int] | None:
    """Return a witness or exhaustively establish absence at one exact length.

    Every undirected simple cycle is considered with its least vertex as
    ``start``. Restricting all other vertices to be greater than ``start`` is
    therefore complete. Of the two orientations, ``first < last`` keeps one.
    """

    n = len(adjacency)
    if length < 3 or length > n:
        return None
    adjacency_masks = [sum(1 << neighbor for neighbor in row) for row in adjacency]
    path: list[int] = []

    def extend(start: int, first: int, current: int, used: int) -> list[int] | None:
        depth = len(path)
        if depth == length:
            budget.tick()
            if first < current and adjacency_masks[current] & (1 << start):
                return list(path)
            return None

        for neighbor in adjacency[current]:
            budget.tick()
            bit = 1 << neighbor
            if neighbor <= start or used & bit:
                continue
            if depth + 1 == length and not (adjacency_masks[neighbor] & (1 << start)):
                continue
            path.append(neighbor)
            witness = extend(start, first, neighbor, used | bit)
            if witness is not None:
                return witness
            path.pop()
        return None

    for start in range(n):
        for first in adjacency[start]:
            budget.tick()
            if first <= start:
                continue
            path[:] = [start, first]
            witness = extend(start, first, first, (1 << start) | (1 << first))
            if witness is not None:
                return witness
    return None


def _blank_facts() -> dict[str, object]:
    return {
        "checked_lengths": [],
        "cycle_witness": None,
        "edge_count": None,
        "forbidden_lengths": [],
        "minimum_degree": None,
        "n": None,
        "search_steps": 0,
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
    maximum_order: int = MAXIMUM_ORDER,
    required_minimum_degree: int = 3,
    search_step_limit: int = MAXIMUM_SEARCH_STEPS,
) -> dict[str, object]:
    """Evaluate one parsed document; may raise on an inconclusive step cap."""

    required_fields = {"schema", "kind", "n", "edges"}
    if type(document) is not dict or set(document) != required_fields:
        return _result(False, "INVALID_DOCUMENT")
    if document["schema"] != CANDIDATE_SCHEMA:
        return _result(False, "INVALID_SCHEMA")
    if document["kind"] != "graph_counterexample":
        return _result(False, "INVALID_KIND")
    n = document["n"]
    if type(n) is not int or not minimum_order <= n <= maximum_order:
        return _result(False, "ORDER_OUT_OF_RANGE")
    edges = document["edges"]
    if type(edges) is not list:
        return _result(False, "INVALID_EDGE_LIST")
    if len(edges) > min(MAXIMUM_EDGES, n * (n - 1) // 2):
        return _result(False, "EDGE_COUNT_LIMIT")

    adjacency_lists: list[list[int]] = [[] for _ in range(n)]
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
        adjacency_lists[left].append(right)
        adjacency_lists[right].append(left)

    adjacency = [tuple(sorted(row)) for row in adjacency_lists]
    minimum_degree = min((len(row) for row in adjacency), default=0)
    forbidden_lengths = power_of_two_cycle_lengths(n)
    facts: dict[str, object] = {
        "checked_lengths": [],
        "cycle_witness": None,
        "edge_count": len(edges),
        "forbidden_lengths": forbidden_lengths,
        "minimum_degree": minimum_degree,
        "n": n,
        "search_steps": 0,
    }
    if minimum_degree < required_minimum_degree:
        return _result(False, "MINIMUM_DEGREE", facts)

    budget = SearchBudget(search_step_limit)
    checked: list[int] = []
    try:
        for length in forbidden_lengths:
            witness = find_simple_cycle_of_length(adjacency, length, budget)
            facts["search_steps"] = budget.steps
            if witness is not None:
                facts["cycle_witness"] = witness
                return _result(False, "POWER_OF_TWO_CYCLE_FOUND", facts)
            checked.append(length)
            facts["checked_lengths"] = list(checked)
    except ApparatusFailure:
        facts["search_steps"] = budget.steps
        raise
    return _result(True, "ACCEPTED", facts)


def evaluate_path(path: Path) -> tuple[dict[str, object], bool]:
    try:
        document = decode_document(read_regular_file(path))
        return evaluate_document(document), False
    except CandidateFailure as failure:
        return _result(False, failure.code), False
    except ApparatusFailure as failure:
        return _result(False, failure.code), True
    except (MemoryError, OverflowError, RecursionError):
        return _result(False, "RESOURCE_FAILURE"), True


def _emit(result: dict[str, object]) -> None:
    payload = json.dumps(
        result,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii") + b"\n"
    sys.stdout.buffer.write(payload)


def main(arguments: list[str]) -> int:
    if len(arguments) != 3 or arguments[1] != "--candidate":
        _emit(_result(False, "USAGE_ERROR"))
        return 2
    result, apparatus_failure = evaluate_path(Path(arguments[2]))
    _emit(result)
    if apparatus_failure:
        return 2
    return 0 if result["accepted"] is True else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
