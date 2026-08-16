#!/usr/bin/env python3
"""Secondary exact checker: Jacobi--Trudi determinant plus Pieri chains.

Unlike ``primary.py``, this implementation never enumerates LR tableaux.  It
expands ``s_nu`` as a Jacobi--Trudi determinant, evaluates each product of
complete homogeneous functions through the Pieri rule, and interpolates with
an exact rational Vandermonde solve.
"""

from __future__ import annotations

from fractions import Fraction
from functools import lru_cache
import hashlib
from itertools import permutations
import json
import math
import os
from pathlib import Path
import stat
import sys
from typing import NoReturn


VERIFIER_ID = "amf.stretched-lr.exact.v1"
RESULT_SCHEMA = "AMF_VERIFIER_RESULT_1"
CHECKER_ID = "SECONDARY_JACOBI_TRUDI_PIERI_AND_VANDERMONDE"
CANDIDATE_SCHEMA = "AMF_STRETCHED_LR_CANDIDATE_1"
LR_CONVENTION = "c^(t*lambda)_(t*mu,t*nu)"
POLYNOMIAL_BASIS = "monomial_t_constant_first"
SAMPLE_DOMAIN = "positive_integers_t=1..29"
SAMPLE_COUNT = 29
MAXIMUM_INPUT_BYTES = 262_144
MAXIMUM_INTEGER_BITS = 4096
DEFAULT_OPERATION_LIMIT = 25_000_000

_EXPECTED_FIELDS = frozenset(
    {
        "schema",
        "lr_convention",
        "polynomial_basis",
        "sample_domain",
        "lambda",
        "mu",
        "nu",
        "coefficients",
        "values_t_1_through_29",
    }
)
_FACT_FIELDS = (
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
)


class BadCandidate(ValueError):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class EngineFailure(RuntimeError):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _bad(reason: str) -> NoReturn:
    raise BadCandidate(reason)


def _engine(reason: str) -> NoReturn:
    raise EngineFailure(reason)


class Counter:
    def __init__(self, ceiling: int):
        self.ceiling = ceiling
        self.value = 0

    def tick(self, amount: int = 1) -> None:
        if amount < 0 or self.value > self.ceiling - amount:
            _engine("COMPUTATION_LIMIT")
        self.value += amount


def _empty_facts() -> dict[str, object]:
    return dict.fromkeys(_FACT_FIELDS)


def _make_result(
    accepted: bool,
    reason: str,
    facts: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "accepted": accepted,
        "checker": CHECKER_ID,
        "facts": _empty_facts() if facts is None else facts,
        "reason_code": reason,
        "schema": RESULT_SCHEMA,
        "verifier_id": VERIFIER_ID,
    }


def _bounded_integer(item: object, *, nonnegative: bool = False) -> int:
    if type(item) is not int:
        _bad("INVALID_DOCUMENT")
    result = int(item)
    if result.bit_length() > MAXIMUM_INTEGER_BITS:
        _bad("INTEGER_TOO_LARGE")
    if nonnegative and result < 0:
        _bad("INVALID_DOCUMENT")
    return result


def _arithmetic_guard(number: int) -> None:
    if type(number) is not int or number.bit_length() > MAXIMUM_INTEGER_BITS:
        _engine("ARITHMETIC_LIMIT")


def _read_partition(item: object) -> tuple[int, ...]:
    if type(item) is not list or len(item) < 1 or len(item) > 7:
        _bad("INVALID_PARTITION")
    answer = tuple(_bounded_integer(entry) for entry in item)
    if any(entry < 1 or entry > 30 for entry in answer):
        _bad("INVALID_PARTITION")
    if any(left < right for left, right in zip(answer, answer[1:])):
        _bad("INVALID_PARTITION")
    if sum(answer) > 30:
        _bad("PARTITION_BOUND")
    return answer


def _read_fraction(item: object) -> Fraction:
    if type(item) is not dict or tuple(sorted(item)) != ("denominator", "numerator"):
        _bad("INVALID_RATIONAL")
    top = _bounded_integer(item["numerator"])
    bottom = _bounded_integer(item["denominator"])
    if bottom < 1:
        _bad("INVALID_RATIONAL")
    if math.gcd(abs(top), bottom) != 1 or (top == 0 and bottom != 1):
        _bad("NONCANONICAL_RATIONAL")
    return Fraction(top, bottom)


def _horner(coefficients: tuple[Fraction, ...], argument: int) -> Fraction:
    accumulator = Fraction(0)
    for coefficient in coefficients[::-1]:
        accumulator *= argument
        accumulator += coefficient
    return accumulator


def _decode(
    candidate: object,
) -> tuple[
    tuple[int, ...],
    tuple[int, ...],
    tuple[int, ...],
    tuple[Fraction, ...],
    tuple[int, ...],
    int,
]:
    if type(candidate) is not dict or frozenset(candidate) != _EXPECTED_FIELDS:
        _bad("INVALID_DOCUMENT")
    constants = (
        ("schema", CANDIDATE_SCHEMA),
        ("lr_convention", LR_CONVENTION),
        ("polynomial_basis", POLYNOMIAL_BASIS),
        ("sample_domain", SAMPLE_DOMAIN),
    )
    if any(candidate[field] != expected for field, expected in constants):
        _bad("INVALID_DOCUMENT")

    outer = _read_partition(candidate["lambda"])
    first_inner = _read_partition(candidate["mu"])
    second_inner = _read_partition(candidate["nu"])
    if sum(outer) != sum(first_inner) + sum(second_inner):
        _bad("SIZE_RELATION")

    coefficient_data = candidate["coefficients"]
    if type(coefficient_data) is not list or not 1 <= len(coefficient_data) <= 29:
        _bad("INVALID_DOCUMENT")
    coefficients = tuple(_read_fraction(entry) for entry in coefficient_data)
    if coefficients[-1].numerator == 0:
        _bad("NONCANONICAL_POLYNOMIAL")
    maximum_degree = len(outer) * (len(outer) + 1) // 2
    if len(coefficients) - 1 > maximum_degree:
        _bad("DEGREE_BOUND")
    if all(coefficient >= 0 for coefficient in coefficients):
        _bad("NO_NEGATIVE_COEFFICIENT")

    sample_data = candidate["values_t_1_through_29"]
    if type(sample_data) is not list or len(sample_data) != SAMPLE_COUNT:
        _bad("INVALID_DOCUMENT")
    samples = tuple(_bounded_integer(entry, nonnegative=True) for entry in sample_data)
    for argument in range(1, SAMPLE_COUNT + 1):
        proposed = _horner(coefficients, argument)
        if proposed.denominator != 1 or proposed.numerator != samples[argument - 1]:
            _bad("DECLARED_POLYNOMIAL_MISMATCH")
    return outer, first_inner, second_inner, coefficients, samples, maximum_degree


def _permutation_sign(permutation: tuple[int, ...]) -> int:
    inversions = sum(
        permutation[left] > permutation[right]
        for left in range(len(permutation))
        for right in range(left + 1, len(permutation))
    )
    return -1 if inversions % 2 else 1


def lr_coefficient_jacobi_trudi_pieri(
    outer: tuple[int, ...],
    inner: tuple[int, ...],
    content_partition: tuple[int, ...],
    *,
    budget: Counter,
) -> int:
    """Return ``[s_outer] s_inner s_content`` by JT and Pieri.

    For each determinant term in
    ``s_content = det(h_(content_i-i+j))``, repeated Pieri multiplication
    counts chains from ``inner`` to ``outer`` whose successive differences are
    horizontal strips.  Equal products are grouped after sorting their strip
    sizes because the complete homogeneous functions commute.
    """

    if sum(outer) != sum(inner) + sum(content_partition):
        return 0
    rows = max(len(outer), len(inner))
    target = outer + (0,) * (rows - len(outer))
    start = inner + (0,) * (rows - len(inner))
    if any(start[index] > target[index] for index in range(rows)):
        return 0

    determinant_size = len(content_partition)
    grouped_terms: dict[tuple[int, ...], int] = {}
    for column_permutation in permutations(range(determinant_size)):
        budget.tick()
        strip_sizes = tuple(
            content_partition[row] - row + column_permutation[row]
            for row in range(determinant_size)
        )
        if any(size < 0 for size in strip_sizes):
            continue
        key = tuple(sorted((size for size in strip_sizes if size), reverse=True))
        grouped_terms[key] = grouped_terms.get(key, 0) + _permutation_sign(
            column_permutation
        )

    @lru_cache(maxsize=None)
    def horizontal_extensions(shape: tuple[int, ...], size: int) -> tuple[tuple[int, ...], ...]:
        budget.tick()
        desired_total = sum(shape) + size
        lower = shape
        upper = (target[0],) + tuple(
            min(target[index], shape[index - 1]) for index in range(1, rows)
        )
        if any(lower[index] > upper[index] for index in range(rows)):
            return ()

        suffix_lower = [0] * (rows + 1)
        suffix_upper = [0] * (rows + 1)
        for index in range(rows - 1, -1, -1):
            suffix_lower[index] = suffix_lower[index + 1] + lower[index]
            suffix_upper[index] = suffix_upper[index + 1] + upper[index]
        extensions: list[tuple[int, ...]] = []
        working = [0] * rows

        def generate(index: int, total_left: int) -> None:
            if index == rows:
                if total_left == 0:
                    extensions.append(tuple(working))
                return
            minimum = max(lower[index], total_left - suffix_upper[index + 1])
            maximum = min(upper[index], total_left - suffix_lower[index + 1])
            for part in range(minimum, maximum + 1):
                budget.tick()
                working[index] = part
                generate(index + 1, total_left - part)

        generate(0, desired_total)
        return tuple(extensions)

    @lru_cache(maxsize=None)
    def count_chains(shape: tuple[int, ...], sizes: tuple[int, ...]) -> int:
        budget.tick()
        if not sizes:
            return int(shape == target)
        total = 0
        for extension in horizontal_extensions(shape, sizes[0]):
            total += count_chains(extension, sizes[1:])
            _arithmetic_guard(total)
        return total

    coefficient = 0
    for sizes, signed_multiplicity in grouped_terms.items():
        if signed_multiplicity == 0:
            continue
        coefficient += signed_multiplicity * count_chains(start, sizes)
        _arithmetic_guard(coefficient)
    if coefficient < 0:
        _engine("NEGATIVE_LR_COUNT")
    return coefficient


def interpolate_vandermonde(values_at_one_through_29: tuple[int, ...]) -> tuple[Fraction, ...]:
    """Recover monomial coefficients by exact Gauss--Jordan elimination."""

    if len(values_at_one_through_29) != SAMPLE_COUNT:
        _engine("INTERPOLATION_FAILURE")
    matrix: list[list[Fraction]] = []
    for argument, value in enumerate(values_at_one_through_29, start=1):
        row = [Fraction(1)]
        for _degree in range(1, SAMPLE_COUNT):
            row.append(row[-1] * argument)
        row.append(Fraction(value))
        matrix.append(row)

    for column in range(SAMPLE_COUNT):
        pivot = next(
            (row for row in range(column, SAMPLE_COUNT) if matrix[row][column]),
            None,
        )
        if pivot is None:
            _engine("INTERPOLATION_FAILURE")
        if pivot != column:
            matrix[column], matrix[pivot] = matrix[pivot], matrix[column]
        divisor = matrix[column][column]
        matrix[column] = [entry / divisor for entry in matrix[column]]
        for row in range(SAMPLE_COUNT):
            if row == column or matrix[row][column] == 0:
                continue
            multiplier = matrix[row][column]
            matrix[row] = [
                left - multiplier * right
                for left, right in zip(matrix[row], matrix[column], strict=True)
            ]
    answer = [matrix[index][-1] for index in range(SAMPLE_COUNT)]
    while len(answer) > 1 and answer[-1] == 0:
        answer.pop()
    for coefficient in answer:
        _arithmetic_guard(coefficient.numerator)
        _arithmetic_guard(coefficient.denominator)
    return tuple(answer)


def _encoded_coefficients(coefficients: tuple[Fraction, ...]) -> list[dict[str, int]]:
    return [
        {"denominator": coefficient.denominator, "numerator": coefficient.numerator}
        for coefficient in coefficients
    ]


def _digest(value: object) -> str:
    serialized = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii") + b"\n"
    return hashlib.sha256(serialized).hexdigest()


def _facts(
    outer: tuple[int, ...],
    first_inner: tuple[int, ...],
    second_inner: tuple[int, ...],
    coefficients: tuple[Fraction, ...],
    values: tuple[int, ...],
    degree_bound: int,
) -> dict[str, object]:
    negative_degree = min(
        degree for degree, coefficient in enumerate(coefficients) if coefficient < 0
    )
    return {
        "coefficients_sha256": _digest(_encoded_coefficients(coefficients)),
        "degree_bound": degree_bound,
        "first_negative_degree": negative_degree,
        "interpolation_points": SAMPLE_COUNT,
        "lambda": list(outer),
        "lambda_size": sum(outer),
        "mu": list(first_inner),
        "mu_size": sum(first_inner),
        "nu": list(second_inner),
        "nu_size": sum(second_inner),
        "sample_values_sha256": _digest(list(values)),
    }


def evaluate_document_with_status(
    candidate: object,
    *,
    operation_limit: int = DEFAULT_OPERATION_LIMIT,
) -> tuple[dict[str, object], bool]:
    try:
        outer, first_inner, second_inner, proposed_coefficients, proposed_values, degree_bound = (
            _decode(candidate)
        )
        if type(operation_limit) is not int or operation_limit < 1:
            _engine("COMPUTATION_LIMIT")
        budget = Counter(operation_limit)
        observed: list[int] = []
        for scale in range(1, SAMPLE_COUNT + 1):
            coefficient = lr_coefficient_jacobi_trudi_pieri(
                tuple(scale * part for part in outer),
                tuple(scale * part for part in first_inner),
                tuple(scale * part for part in second_inner),
                budget=budget,
            )
            _arithmetic_guard(coefficient)
            observed.append(coefficient)
        values = tuple(observed)
        if values != proposed_values:
            _bad("SAMPLE_MISMATCH")
        coefficients = interpolate_vandermonde(values)
        if len(coefficients) - 1 > degree_bound:
            _engine("SOURCE_DEGREE_BOUND_VIOLATION")
        if coefficients != proposed_coefficients:
            _bad("POLYNOMIAL_MISMATCH")
        return _make_result(
            True,
            "ACCEPTED",
            _facts(
                outer,
                first_inner,
                second_inner,
                coefficients,
                values,
                degree_bound,
            ),
        ), False
    except BadCandidate as failure:
        return _make_result(False, failure.reason), False
    except EngineFailure as failure:
        return _make_result(False, failure.reason), True
    except (MemoryError, OverflowError, RecursionError):
        return _make_result(False, "COMPUTATION_FAILURE"), True


def evaluate_document(
    candidate: object,
    *,
    operation_limit: int = DEFAULT_OPERATION_LIMIT,
) -> dict[str, object]:
    return evaluate_document_with_status(
        candidate, operation_limit=operation_limit
    )[0]


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    answer: dict[str, object] = {}
    for key, value in pairs:
        if key in answer:
            _bad("INVALID_JSON")
        answer[key] = value
    return answer


def _not_json_number(_token: str) -> NoReturn:
    _bad("INVALID_JSON")


def _json_integer(token: str) -> int:
    magnitude = token.removeprefix("-")
    if not magnitude or len(magnitude) > 1234:
        _bad("INTEGER_TOO_LARGE")
    try:
        answer = int(token)
    except ValueError:
        _bad("INVALID_JSON")
    if answer.bit_length() > MAXIMUM_INTEGER_BITS:
        _bad("INTEGER_TOO_LARGE")
    return answer


def _snapshot(file_path: Path) -> bytes:
    try:
        named = file_path.lstat()
    except OSError:
        _engine("INPUT_UNAVAILABLE")
    if stat.S_ISLNK(named.st_mode) or not stat.S_ISREG(named.st_mode):
        _engine("INPUT_NOT_REGULAR")
    if named.st_size > MAXIMUM_INPUT_BYTES:
        _engine("INPUT_TOO_LARGE")
    open_flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    open_flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        handle = os.open(file_path, open_flags)
    except OSError:
        _engine("INPUT_UNAVAILABLE")
    try:
        actual = os.fstat(handle)
        if (
            not stat.S_ISREG(actual.st_mode)
            or (actual.st_dev, actual.st_ino, actual.st_size)
            != (named.st_dev, named.st_ino, named.st_size)
        ):
            _engine("INPUT_CHANGED")
        pieces = bytearray()
        while len(pieces) != actual.st_size:
            piece = os.read(handle, min(65_536, actual.st_size - len(pieces)))
            if piece == b"":
                _engine("INPUT_CHANGED")
            pieces += piece
        if os.read(handle, 1):
            _engine("INPUT_CHANGED")
        final = os.fstat(handle)
        if (final.st_size, final.st_mtime_ns, final.st_ctime_ns) != (
            actual.st_size,
            actual.st_mtime_ns,
            actual.st_ctime_ns,
        ):
            _engine("INPUT_CHANGED")
        return bytes(pieces)
    except OSError:
        _engine("INPUT_UNAVAILABLE")
    finally:
        os.close(handle)


def load_document(file_path: Path) -> object:
    payload = _snapshot(file_path)
    try:
        return json.loads(
            payload.decode("ascii", errors="strict"),
            object_pairs_hook=_unique_object,
            parse_int=_json_integer,
            parse_float=_not_json_number,
            parse_constant=_not_json_number,
        )
    except (UnicodeError, json.JSONDecodeError, RecursionError, ValueError):
        _bad("INVALID_JSON")


def _write_result(result: dict[str, object]) -> None:
    output = json.dumps(
        result,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    sys.stdout.buffer.write(output + b"\n")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        _write_result(_make_result(False, "USAGE_ERROR"))
        return 2
    try:
        candidate = load_document(Path(argv[1]))
    except BadCandidate as failure:
        _write_result(_make_result(False, failure.reason))
        return 1
    except EngineFailure as failure:
        _write_result(_make_result(False, failure.reason))
        return 2
    result, infrastructure_failure = evaluate_document_with_status(candidate)
    _write_result(result)
    if infrastructure_failure:
        return 2
    return 0 if result["accepted"] is True else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
