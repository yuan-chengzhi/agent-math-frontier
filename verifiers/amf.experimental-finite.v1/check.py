#!/usr/bin/env python3
"""Offline exact checkers for the unaudited experimental target tier.

The profile is selected by the content-pinned verifier manifest, never by the
candidate.  Acceptance is deliberately one-sided: it certifies the finite
mathematical object described by that profile, but it does not certify
novelty, current-record status, statement fidelity, or proof-assistant closure.
"""

from __future__ import annotations

from collections import deque
from fractions import Fraction
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
from typing import Any, Callable, NoReturn


RESULT_SCHEMA = "AMF_VERIFIER_RESULT_1"
MAXIMUM_INPUT_BYTES = 16 * 1024 * 1024
MAXIMUM_DECIMAL_DIGITS = 4096
MAXIMUM_TOTAL_DECIMAL_DIGITS = 250_000
MAXIMUM_COVER_PERIOD = 5_000_000
MAXIMUM_COVER_OPERATIONS = 50_000_000
U64_LIMIT = 1 << 64

_SIGNED_DECIMAL = re.compile(r"^(0|-?[1-9][0-9]*)$")
_POSITIVE_DECIMAL = re.compile(r"^[1-9][0-9]*$")


PROFILE_META: dict[str, tuple[str, str]] = {
    "erdos307": ("amf.erdos307.exact.v1", "PRIME_CERTIFICATES_AND_EXACT_RATIONAL"),
    "erdos835-k10": ("amf.erdos835.k10.v1", "COMPLETE_K10_COLOR_TABLE"),
    "erdos23-oddcycle": ("amf.erdos23.oddcycle.v1", "TRIANGLE_FREE_AND_EDGE_DISJOINT_ODD_CYCLES"),
    "erdos7-cover": ("amf.erdos7.cover.v1", "EXACT_LCM_RESIDUE_COVER"),
    "r55-graph43": ("amf.r55.graph43.v1", "EXACT_FIVE_CLIQUE_AND_COCLIQUE_SEARCH"),
    "book-range100": ("amf.book.range100.v1", "EXACT_BOOK_COMMON_NEIGHBOR_COUNTS"),
    "diophantine-eq1": ("amf.diophantine.eq1.v1", "EXACT_BIG_INTEGER_SUBSTITUTION"),
    "cage3g13": ("amf.cage3g13.exact.v1", "EXACT_CUBIC_CONNECTIVITY_AND_GIRTH"),
    "srg692075": ("amf.srg692075.exact.v1", "EXACT_STRONGLY_REGULAR_PARAMETERS"),
    "costas32": ("amf.costas32.exact.v1", "EXACT_PERMUTATION_DISPLACEMENTS"),
}


class CandidateFailure(ValueError):
    """A malformed candidate or a candidate that fails the frozen property."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class ApparatusFailure(RuntimeError):
    """An inconclusive verifier resource/integrity failure."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _fail(code: str) -> NoReturn:
    raise CandidateFailure(code)


def _abort(code: str) -> NoReturn:
    raise ApparatusFailure(code)


def _pairs_no_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            _fail("DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _parse_int(token: str) -> int:
    if len(token) > 19:
        _fail("INTEGER_OUT_OF_RANGE")
    try:
        value = int(token, 10)
    except ValueError:
        _fail("INVALID_JSON")
    if not -(1 << 63) <= value <= (1 << 63) - 1:
        _fail("INTEGER_OUT_OF_RANGE")
    return value


def _reject_number(_token: str) -> NoReturn:
    _fail("NON_INTEGER_NUMBER")


def read_regular_file(path: Path) -> bytes:
    try:
        before = path.lstat()
    except OSError:
        _abort("INPUT_UNAVAILABLE")
    if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
        _abort("INPUT_NOT_REGULAR")
    if before.st_size > MAXIMUM_INPUT_BYTES:
        _fail("INPUT_TOO_LARGE")

    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        _abort("INPUT_UNAVAILABLE")
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_dev != before.st_dev
            or opened.st_ino != before.st_ino
            or opened.st_size != before.st_size
        ):
            _abort("INPUT_CHANGED")
        payload = bytearray()
        while len(payload) < opened.st_size:
            chunk = os.read(descriptor, min(65_536, opened.st_size - len(payload)))
            if not chunk:
                _abort("INPUT_CHANGED")
            payload.extend(chunk)
        if os.read(descriptor, 1):
            _abort("INPUT_CHANGED")
        after = os.fstat(descriptor)
        if (
            after.st_size != opened.st_size
            or after.st_mtime_ns != opened.st_mtime_ns
            or after.st_ctime_ns != opened.st_ctime_ns
        ):
            _abort("INPUT_CHANGED")
        return bytes(payload)
    except OSError:
        _abort("INPUT_UNAVAILABLE")
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
        _fail("INVALID_JSON")
    if type(value) is not dict:
        _fail("INVALID_DOCUMENT")
    return value


def _require_fields(value: object, fields: set[str], code: str = "INVALID_DOCUMENT") -> dict[str, Any]:
    if type(value) is not dict or set(value) != fields:
        _fail(code)
    return value


def _decimal(value: object, *, positive: bool = False) -> int:
    if type(value) is not str or len(value) > MAXIMUM_DECIMAL_DIGITS:
        _fail("INVALID_DECIMAL")
    pattern = _POSITIVE_DECIMAL if positive else _SIGNED_DECIMAL
    if pattern.fullmatch(value) is None:
        _fail("INVALID_DECIMAL")
    try:
        return int(value, 10)
    except (ValueError, MemoryError):
        _fail("INVALID_DECIMAL")


def _is_prime_u64(n: int) -> bool:
    """Deterministic Miller--Rabin on 0 <= n < 2**64."""

    if n < 2:
        return False
    for prime in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
        if n == prime:
            return True
        if n % prime == 0:
            return False
    odd_part = n - 1
    powers = 0
    while odd_part % 2 == 0:
        odd_part //= 2
        powers += 1
    for base in (2, 325, 9_375, 28_178, 450_775, 9_780_504, 1_795_265_022):
        base %= n
        if base == 0:
            continue
        value = pow(base, odd_part, n)
        if value in (1, n - 1):
            continue
        for _ in range(powers - 1):
            value = value * value % n
            if value == n - 1:
                break
        else:
            return False
    return True


def _parse_prime_certificates(value: object) -> dict[int, dict[str, Any]]:
    if type(value) is not list or len(value) > 2048:
        _fail("INVALID_PRIME_CERTIFICATES")
    certificates: dict[int, dict[str, Any]] = {}
    for raw in value:
        item = _require_fields(raw, {"prime", "factors", "witness"}, "INVALID_PRIME_CERTIFICATE")
        prime = _decimal(item["prime"], positive=True)
        if prime < U64_LIMIT or prime in certificates:
            _fail("INVALID_PRIME_CERTIFICATE")
        if type(item["factors"]) is not list or not item["factors"] or len(item["factors"]) > 2048:
            _fail("INVALID_PRIME_FACTORIZATION")
        certificates[prime] = item
    return certificates


def _verify_certified_prime(
    n: int,
    certificates: dict[int, dict[str, Any]],
    states: dict[int, int],
    used: set[int],
) -> None:
    if n < U64_LIMIT:
        if not _is_prime_u64(n):
            _fail("NONPRIME_ENTRY")
        return
    state = states.get(n, 0)
    if state == 1:
        _fail("CYCLIC_PRIME_CERTIFICATE")
    if state == 2:
        return
    certificate = certificates.get(n)
    if certificate is None:
        _fail("MISSING_PRIME_CERTIFICATE")
    states[n] = 1
    used.add(n)
    factors: list[tuple[int, int]] = []
    previous = 1
    product = 1
    for raw_factor in certificate["factors"]:
        if type(raw_factor) is not list or len(raw_factor) != 2:
            _fail("INVALID_PRIME_FACTORIZATION")
        q = _decimal(raw_factor[0], positive=True)
        exponent = raw_factor[1]
        if type(exponent) is not int or not 1 <= exponent <= 4096 or q <= previous or q >= n:
            _fail("INVALID_PRIME_FACTORIZATION")
        previous = q
        _verify_certified_prime(q, certificates, states, used)
        product *= pow(q, exponent)
        if product > n - 1:
            _fail("INVALID_PRIME_FACTORIZATION")
        factors.append((q, exponent))
    if product != n - 1:
        _fail("INVALID_PRIME_FACTORIZATION")
    witness = _decimal(certificate["witness"], positive=True)
    if not 2 <= witness <= n - 2 or pow(witness, n - 1, n) != 1:
        _fail("INVALID_LUCAS_WITNESS")
    for q, _exponent in factors:
        if math.gcd(pow(witness, (n - 1) // q, n) - 1, n) != 1:
            _fail("INVALID_LUCAS_WITNESS")
    states[n] = 2


def _check_erdos307(document: object) -> dict[str, object]:
    value = _require_fields(document, {"schema", "P", "Q", "prime_certificates"})
    if value["schema"] != "AMF_ERDOS307_RECIPROCAL_PRIMES_1":
        _fail("INVALID_SCHEMA")
    if type(value["P"]) is not list or type(value["Q"]) is not list:
        _fail("INVALID_PRIME_SETS")
    if not 1 <= len(value["P"]) <= 512 or not 1 <= len(value["Q"]) <= 512:
        _fail("PRIME_SET_SIZE_LIMIT")
    raw_values = value["P"] + value["Q"]
    if any(type(item) is not str for item in raw_values):
        _fail("INVALID_DECIMAL")
    if sum(len(item) for item in raw_values) > MAXIMUM_TOTAL_DECIMAL_DIGITS:
        _fail("DECIMAL_BUDGET")
    left = [_decimal(item, positive=True) for item in value["P"]]
    right = [_decimal(item, positive=True) for item in value["Q"]]
    if len(set(left)) != len(left) or len(set(right)) != len(right):
        _fail("DUPLICATE_PRIME")
    certificates = _parse_prime_certificates(value["prime_certificates"])
    states: dict[int, int] = {}
    used: set[int] = set()
    for prime in set(left + right):
        _verify_certified_prime(prime, certificates, states, used)
    if used != set(certificates):
        _fail("UNUSED_PRIME_CERTIFICATE")
    left_sum = sum((Fraction(1, prime) for prime in left), Fraction())
    right_sum = sum((Fraction(1, prime) for prime in right), Fraction())
    if left_sum * right_sum != 1:
        _fail("RATIONAL_IDENTITY_FALSE")
    return {
        "P_count": len(left),
        "Q_count": len(right),
        "certified_large_primes": len(certificates),
        "total_memberships": len(left) + len(right),
    }


def _check_erdos835_k10(document: object) -> dict[str, object]:
    value = _require_fields(document, {"schema", "k", "colors"})
    if value["schema"] != "AMF_ERDOS835_K10_COLORING_1":
        _fail("INVALID_SCHEMA")
    if value["k"] != 10:
        _fail("INVALID_K")
    colors = value["colors"]
    expected = math.comb(20, 10)
    if type(colors) is not list or len(colors) != expected:
        _fail("INVALID_COLOR_TABLE_LENGTH")
    if any(type(color) is not int or not 0 <= color <= 10 for color in colors):
        _fail("INVALID_COLOR")
    table = dict(zip(itertools.combinations(range(20), 10), colors, strict=True))
    all_colors = set(range(11))
    checked = 0
    for superset in itertools.combinations(range(20), 11):
        seen = {
            table[superset[:index] + superset[index + 1 :]]
            for index in range(11)
        }
        if seen != all_colors:
            _fail("MISSING_COLOR_IN_11_SUBSET")
        checked += 1
    return {"k": 10, "colored_subsets": expected, "constraints_checked": checked}


def _parse_graph_edges(raw_edges: object, n: int, *, maximum_edges: int | None = None) -> tuple[list[int], set[tuple[int, int]]]:
    if type(raw_edges) is not list:
        _fail("INVALID_EDGE_LIST")
    cap = n * (n - 1) // 2 if maximum_edges is None else min(maximum_edges, n * (n - 1) // 2)
    if len(raw_edges) > cap:
        _fail("EDGE_COUNT_LIMIT")
    adjacency = [0] * n
    edges: set[tuple[int, int]] = set()
    for raw in raw_edges:
        if type(raw) is not list or len(raw) != 2:
            _fail("INVALID_EDGE")
        left, right = raw
        if type(left) is not int or type(right) is not int:
            _fail("INVALID_EDGE")
        if not 0 <= left < right < n:
            _fail("NONCANONICAL_EDGE")
        edge = (left, right)
        if edge in edges:
            _fail("DUPLICATE_EDGE")
        edges.add(edge)
        adjacency[left] |= 1 << right
        adjacency[right] |= 1 << left
    return adjacency, edges


def _check_erdos23_oddcycle(document: object) -> dict[str, object]:
    value = _require_fields(document, {"schema", "n_parameter", "edges", "odd_cycles"})
    if value["schema"] != "AMF_ERDOS23_ODD_CYCLE_COUNTEREXAMPLE_1":
        _fail("INVALID_SCHEMA")
    parameter = value["n_parameter"]
    if type(parameter) is not int or not 1 <= parameter <= 100:
        _fail("PARAMETER_OUT_OF_RANGE")
    order = 5 * parameter
    adjacency, edges = _parse_graph_edges(value["edges"], order, maximum_edges=124_750)
    for left, right in edges:
        if adjacency[left] & adjacency[right]:
            _fail("TRIANGLE_FOUND")
    cycles = value["odd_cycles"]
    required = parameter * parameter + 1
    if type(cycles) is not list or not required <= len(cycles) <= 10_001:
        _fail("INSUFFICIENT_ODD_CYCLES")
    used_edges: set[tuple[int, int]] = set()
    for raw_cycle in cycles:
        if type(raw_cycle) is not list or not 5 <= len(raw_cycle) <= order or len(raw_cycle) % 2 == 0:
            _fail("INVALID_ODD_CYCLE")
        if any(type(vertex) is not int or not 0 <= vertex < order for vertex in raw_cycle):
            _fail("INVALID_ODD_CYCLE")
        if len(set(raw_cycle)) != len(raw_cycle):
            _fail("NON_SIMPLE_ODD_CYCLE")
        for index, left in enumerate(raw_cycle):
            right = raw_cycle[(index + 1) % len(raw_cycle)]
            edge = (left, right) if left < right else (right, left)
            if edge not in edges:
                _fail("ODD_CYCLE_EDGE_MISSING")
            if edge in used_edges:
                _fail("ODD_CYCLES_NOT_EDGE_DISJOINT")
            used_edges.add(edge)
    return {
        "edge_count": len(edges),
        "n_parameter": parameter,
        "odd_cycles_certified": len(cycles),
        "order": order,
        "bipartization_lower_bound": len(cycles),
    }


def _check_erdos7_cover(document: object) -> dict[str, object]:
    value = _require_fields(document, {"schema", "classes"})
    if value["schema"] != "AMF_ERDOS7_ODD_COVER_1":
        _fail("INVALID_SCHEMA")
    classes = value["classes"]
    if type(classes) is not list or not 2 <= len(classes) <= 512:
        _fail("INVALID_CLASS_COUNT")
    parsed: list[tuple[int, int]] = []
    moduli: set[int] = set()
    period = 1
    estimated_operations = 0
    for raw in classes:
        item = _require_fields(raw, {"residue", "modulus"}, "INVALID_CLASS")
        residue = item["residue"]
        modulus = item["modulus"]
        if type(residue) is not int or type(modulus) is not int:
            _fail("INVALID_CLASS")
        if not 3 <= modulus <= 1_000_000 or modulus % 2 == 0 or not 0 <= residue < modulus:
            _fail("INVALID_CLASS")
        if modulus in moduli:
            _fail("DUPLICATE_MODULUS")
        moduli.add(modulus)
        period = math.lcm(period, modulus)
        if period > MAXIMUM_COVER_PERIOD:
            _fail("PERIOD_LIMIT")
        parsed.append((residue, modulus))
    for residue, modulus in parsed:
        estimated_operations += 1 + (period - 1 - residue) // modulus
    if estimated_operations > MAXIMUM_COVER_OPERATIONS:
        _abort("COVER_WORK_LIMIT")
    try:
        covered = bytearray(period)
        for residue, modulus in parsed:
            count = 1 + (period - 1 - residue) // modulus
            covered[residue:period:modulus] = b"\x01" * count
    except (MemoryError, OverflowError):
        _abort("RESOURCE_FAILURE")
    if 0 in covered:
        _fail("UNCOVERED_RESIDUE")
    return {"class_count": len(parsed), "period": period, "residues_checked": period}


def _has_clique(adjacency: list[int], size: int) -> bool:
    def search(candidates: int, depth: int) -> bool:
        needed = size - depth
        while candidates.bit_count() >= needed:
            bit = candidates & -candidates
            vertex = bit.bit_length() - 1
            candidates ^= bit
            if needed == 1 or search(candidates & adjacency[vertex], depth + 1):
                return True
        return False

    return search((1 << len(adjacency)) - 1, 0)


def _check_r55_graph43(document: object) -> dict[str, object]:
    value = _require_fields(document, {"schema", "n", "edges"})
    if value["schema"] != "AMF_R55_GRAPH43_1":
        _fail("INVALID_SCHEMA")
    if value["n"] != 43:
        _fail("INVALID_ORDER")
    adjacency, edges = _parse_graph_edges(value["edges"], 43)
    if _has_clique(adjacency, 5):
        _fail("FIVE_CLIQUE_FOUND")
    all_vertices = (1 << 43) - 1
    complement = [all_vertices & ~(adjacency[vertex] | (1 << vertex)) for vertex in range(43)]
    if _has_clique(complement, 5):
        _fail("FIVE_INDEPENDENT_SET_FOUND")
    return {"edge_count": len(edges), "n": 43, "ramsey_lower_bound": 44}


def _adjacency_from_column_major(bits: object, order: int) -> list[int]:
    expected = order * (order - 1) // 2
    if type(bits) is not str or len(bits) != expected:
        _fail("INVALID_ADJACENCY_STRING_LENGTH")
    adjacency = [0] * order
    index = 0
    for right in range(1, order):
        for left in range(right):
            token = bits[index]
            index += 1
            if token == "1":
                adjacency[left] |= 1 << right
                adjacency[right] |= 1 << left
            elif token != "0":
                _fail("INVALID_ADJACENCY_BIT")
    return adjacency


def _check_book_range100(document: object) -> dict[str, object]:
    value = _require_fields(document, {"schema", "n_min", "n_max", "graphs"})
    if value["schema"] != "AMF_BOOK_RANGE100_GRAPHS_1":
        _fail("INVALID_SCHEMA")
    if value["n_min"] != 2 or value["n_max"] != 100:
        _fail("INVALID_PARAMETER_RANGE")
    graphs = value["graphs"]
    if type(graphs) is not list or len(graphs) != 99:
        _fail("INVALID_GRAPH_COUNT")
    total_edges = 0
    for offset, bits in enumerate(graphs):
        n = offset + 2
        order = 4 * n - 2
        adjacency = _adjacency_from_column_major(bits, order)
        all_vertices = (1 << order) - 1
        complement = [all_vertices & ~(adjacency[v] | (1 << v)) for v in range(order)]
        for right in range(1, order):
            for left in range(right):
                if adjacency[left] & (1 << right):
                    total_edges += 1
                    if (adjacency[left] & adjacency[right]).bit_count() >= n - 1:
                        _fail("BOOK_IN_GRAPH")
                elif (complement[left] & complement[right]).bit_count() >= n:
                    _fail("BOOK_IN_COMPLEMENT")
    return {"graphs_checked": 99, "maximum_n": 100, "maximum_order": 398, "total_edges": total_edges}


def _check_diophantine_eq1(document: object) -> dict[str, object]:
    value = _require_fields(document, {"schema", "equation_id", "solutions"})
    if value["schema"] != "AMF_SMALL_DIOPHANTINE_EQ1_1":
        _fail("INVALID_SCHEMA")
    if value["equation_id"] != "z2+y2z+x3-2":
        _fail("INVALID_EQUATION")
    solutions = value["solutions"]
    if type(solutions) is not list or len(solutions) != 3:
        _fail("INVALID_SOLUTION_COUNT")
    x_values: set[int] = set()
    largest_digits = 0
    for raw in solutions:
        item = _require_fields(raw, {"x", "y", "z"}, "INVALID_SOLUTION")
        if any(type(item[field]) is not str for field in ("x", "y", "z")):
            _fail("INVALID_DECIMAL")
        if sum(len(item[field]) for field in ("x", "y", "z")) > MAXIMUM_TOTAL_DECIMAL_DIGITS:
            _fail("DECIMAL_BUDGET")
        x = _decimal(item["x"])
        y = _decimal(item["y"])
        z = _decimal(item["z"])
        if abs(x) <= 10**50:
            _fail("X_THRESHOLD")
        if x in x_values:
            _fail("DUPLICATE_X")
        x_values.add(x)
        if z * z + y * y * z + x * x * x - 2 != 0:
            _fail("EQUATION_FALSE")
        largest_digits = max(largest_digits, len(str(abs(x))), len(str(abs(y))), len(str(abs(z))))
    digest = hashlib.sha256(
        "\n".join(sorted(str(x) for x in x_values)).encode("ascii")
    ).hexdigest()
    return {"equation_id": value["equation_id"], "largest_coordinate_digits": largest_digits, "solution_count": 3, "x_set_sha256": digest}


def _graph_is_connected(adjacency: list[int]) -> bool:
    if not adjacency:
        return False
    seen = 1
    frontier = 1
    while frontier:
        bit = frontier & -frontier
        frontier ^= bit
        vertex = bit.bit_length() - 1
        new = adjacency[vertex] & ~seen
        seen |= new
        frontier |= new
    return seen.bit_count() == len(adjacency)


def _girth(adjacency: list[int], cutoff: int | None = None) -> int | None:
    order = len(adjacency)
    best = order + 1
    for root in range(order):
        distance = [-1] * order
        parent = [-1] * order
        distance[root] = 0
        queue: deque[int] = deque([root])
        while queue:
            left = queue.popleft()
            neighbors = adjacency[left]
            while neighbors:
                bit = neighbors & -neighbors
                neighbors ^= bit
                right = bit.bit_length() - 1
                if distance[right] < 0:
                    distance[right] = distance[left] + 1
                    parent[right] = left
                    queue.append(right)
                elif parent[left] != right:
                    best = min(best, distance[left] + distance[right] + 1)
                    if cutoff is not None and best < cutoff:
                        return best
    return None if best == order + 1 else best


def _check_cage3g13(document: object) -> dict[str, object]:
    value = _require_fields(document, {"schema", "n", "edges"})
    if value["schema"] != "AMF_CAGE3G13_GRAPH_1":
        _fail("INVALID_SCHEMA")
    n = value["n"]
    if type(n) is not int or not 4 <= n < 272:
        _fail("INVALID_ORDER")
    adjacency, edges = _parse_graph_edges(value["edges"], n, maximum_edges=3 * n // 2)
    if any(row.bit_count() != 3 for row in adjacency):
        _fail("NOT_CUBIC")
    if not _graph_is_connected(adjacency):
        _fail("NOT_CONNECTED")
    girth = _girth(adjacency, cutoff=13)
    if girth is not None and girth < 13:
        _fail("GIRTH_TOO_SMALL")
    return {"edge_count": len(edges), "girth": girth, "n": n, "record_upper_bound": n}


def _check_srg692075(document: object) -> dict[str, object]:
    value = _require_fields(document, {"schema", "n", "edges"})
    if value["schema"] != "AMF_SRG_69_20_7_5_GRAPH_1":
        _fail("INVALID_SCHEMA")
    if value["n"] != 69:
        _fail("INVALID_ORDER")
    adjacency, edges = _parse_graph_edges(value["edges"], 69, maximum_edges=690)
    if len(edges) != 690 or any(row.bit_count() != 20 for row in adjacency):
        _fail("INVALID_DEGREE")
    for right in range(1, 69):
        for left in range(right):
            common = (adjacency[left] & adjacency[right]).bit_count()
            expected = 7 if adjacency[left] & (1 << right) else 5
            if common != expected:
                _fail("INVALID_COMMON_NEIGHBOR_COUNT")
    return {"edge_count": 690, "k": 20, "lambda": 7, "mu": 5, "n": 69}


def _is_costas(permutation: list[int]) -> bool:
    displacements: set[tuple[int, int]] = set()
    for right in range(1, len(permutation)):
        for left in range(right):
            displacement = (right - left, permutation[right] - permutation[left])
            if displacement in displacements:
                return False
            displacements.add(displacement)
    return True


def _check_costas32(document: object) -> dict[str, object]:
    value = _require_fields(document, {"schema", "order", "permutation"})
    if value["schema"] != "AMF_COSTAS32_PERMUTATION_1":
        _fail("INVALID_SCHEMA")
    if value["order"] != 32:
        _fail("INVALID_ORDER")
    permutation = value["permutation"]
    if type(permutation) is not list or len(permutation) != 32:
        _fail("INVALID_PERMUTATION")
    if any(type(item) is not int for item in permutation) or set(permutation) != set(range(1, 33)):
        _fail("INVALID_PERMUTATION")
    if not _is_costas(permutation):
        _fail("DUPLICATE_DISPLACEMENT")
    return {"displacements_checked": 496, "order": 32}


CHECKERS: dict[str, Callable[[object], dict[str, object]]] = {
    "erdos307": _check_erdos307,
    "erdos835-k10": _check_erdos835_k10,
    "erdos23-oddcycle": _check_erdos23_oddcycle,
    "erdos7-cover": _check_erdos7_cover,
    "r55-graph43": _check_r55_graph43,
    "book-range100": _check_book_range100,
    "diophantine-eq1": _check_diophantine_eq1,
    "cage3g13": _check_cage3g13,
    "srg692075": _check_srg692075,
    "costas32": _check_costas32,
}


def _result(profile: str, accepted: bool, reason_code: str, facts: dict[str, object] | None = None) -> dict[str, object]:
    verifier_id, checker_id = PROFILE_META.get(profile, ("amf.experimental.unknown.v1", "UNKNOWN_PROFILE"))
    return {
        "accepted": accepted,
        "checker": checker_id,
        "facts": {} if facts is None else facts,
        "reason_code": reason_code,
        "schema": RESULT_SCHEMA,
        "verifier_id": verifier_id,
    }


def evaluate_document(profile: str, document: object) -> tuple[dict[str, object], bool]:
    checker = CHECKERS.get(profile)
    if checker is None:
        return _result(profile, False, "UNKNOWN_PROFILE"), True
    try:
        return _result(profile, True, "ACCEPTED", checker(document)), False
    except CandidateFailure as failure:
        return _result(profile, False, failure.code), False
    except ApparatusFailure as failure:
        return _result(profile, False, failure.code), True
    except (MemoryError, OverflowError, RecursionError):
        return _result(profile, False, "RESOURCE_FAILURE"), True


def evaluate_path(profile: str, path: Path) -> tuple[dict[str, object], bool]:
    try:
        document = decode_document(read_regular_file(path))
    except CandidateFailure as failure:
        return _result(profile, False, failure.code), False
    except ApparatusFailure as failure:
        return _result(profile, False, failure.code), True
    except (MemoryError, OverflowError, RecursionError):
        return _result(profile, False, "RESOURCE_FAILURE"), True
    return evaluate_document(profile, document)


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
    if len(arguments) != 4 or arguments[2] != "--candidate" or arguments[1] not in CHECKERS:
        profile = arguments[1] if len(arguments) > 1 else "unknown"
        _emit(_result(profile, False, "USAGE_ERROR"))
        return 2
    result, apparatus_failure = evaluate_path(arguments[1], Path(arguments[3]))
    _emit(result)
    if apparatus_failure:
        return 2
    return 0 if result["accepted"] is True else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
