#!/usr/bin/env python3
"""Primary exact checker: direct Littlewood--Richardson tableaux.

This implementation deliberately does not share its coefficient algorithm or
its interpolation algorithm with ``secondary.py``.  It counts semistandard
skew tableaux whose reverse row word is a lattice word, and reconstructs the
stretched polynomial by finite differences in the Newton basis.
"""

from __future__ import annotations

from fractions import Fraction
from functools import lru_cache
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import sys
from typing import NoReturn


VERIFIER_ID = "amf.stretched-lr.exact.v1"
RESULT_SCHEMA = "AMF_VERIFIER_RESULT_1"
CHECKER_ID = "PRIMARY_LR_TABLEAUX_AND_NEWTON_DIFFERENCES"
CANDIDATE_SCHEMA = "AMF_STRETCHED_LR_CANDIDATE_1"
LR_CONVENTION = "c^(t*lambda)_(t*mu,t*nu)"
POLYNOMIAL_BASIS = "monomial_t_constant_first"
SAMPLE_DOMAIN = "positive_integers_t=1..29"
SAMPLE_COUNT = 29
MAXIMUM_INPUT_BYTES = 262_144
MAXIMUM_INTEGER_BITS = 4096
DEFAULT_OPERATION_LIMIT = 25_000_000

_CANDIDATE_KEYS = {
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
_FACT_KEYS = {
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


class CandidateFailure(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class ComputationFailure(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _reject(code: str) -> NoReturn:
    raise CandidateFailure(code)


def _abort(code: str) -> NoReturn:
    raise ComputationFailure(code)


class WorkBudget:
    def __init__(self, limit: int):
        self.limit = limit
        self.used = 0

    def spend(self, amount: int = 1) -> None:
        if amount < 0 or self.used > self.limit - amount:
            _abort("COMPUTATION_LIMIT")
        self.used += amount


def _blank_facts() -> dict[str, object]:
    return {key: None for key in sorted(_FACT_KEYS)}


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


def _ensure_small_integer(value: object, *, nonnegative: bool = False) -> int:
    if type(value) is not int:
        _reject("INVALID_DOCUMENT")
    integer = int(value)
    if integer.bit_length() > MAXIMUM_INTEGER_BITS:
        _reject("INTEGER_TOO_LARGE")
    if nonnegative and integer < 0:
        _reject("INVALID_DOCUMENT")
    return integer


def _ensure_arithmetic_bound(value: int) -> None:
    if type(value) is not int or value.bit_length() > MAXIMUM_INTEGER_BITS:
        _abort("ARITHMETIC_LIMIT")


def _partition(value: object) -> tuple[int, ...]:
    if type(value) is not list or not 1 <= len(value) <= 7:
        _reject("INVALID_PARTITION")
    parts: list[int] = []
    for item in value:
        part = _ensure_small_integer(item)
        if not 1 <= part <= 30:
            _reject("INVALID_PARTITION")
        parts.append(part)
    if any(parts[index] < parts[index + 1] for index in range(len(parts) - 1)):
        _reject("INVALID_PARTITION")
    if sum(parts) > 30:
        _reject("PARTITION_BOUND")
    return tuple(parts)


def _rational(value: object) -> Fraction:
    if type(value) is not dict or set(value) != {"numerator", "denominator"}:
        _reject("INVALID_RATIONAL")
    numerator = _ensure_small_integer(value["numerator"])
    denominator = _ensure_small_integer(value["denominator"])
    if denominator <= 0:
        _reject("INVALID_RATIONAL")
    if math.gcd(abs(numerator), denominator) != 1:
        _reject("NONCANONICAL_RATIONAL")
    if numerator == 0 and denominator != 1:
        _reject("NONCANONICAL_RATIONAL")
    return Fraction(numerator, denominator)


def _evaluate_polynomial(coefficients: tuple[Fraction, ...], t: int) -> Fraction:
    value = Fraction(0)
    for coefficient in reversed(coefficients):
        value = value * t + coefficient
    return value


def _validate_candidate(
    document: object,
) -> tuple[
    tuple[int, ...],
    tuple[int, ...],
    tuple[int, ...],
    tuple[Fraction, ...],
    tuple[int, ...],
    int,
]:
    if type(document) is not dict or set(document) != _CANDIDATE_KEYS:
        _reject("INVALID_DOCUMENT")
    if document["schema"] != CANDIDATE_SCHEMA:
        _reject("INVALID_DOCUMENT")
    if document["lr_convention"] != LR_CONVENTION:
        _reject("INVALID_DOCUMENT")
    if document["polynomial_basis"] != POLYNOMIAL_BASIS:
        _reject("INVALID_DOCUMENT")
    if document["sample_domain"] != SAMPLE_DOMAIN:
        _reject("INVALID_DOCUMENT")

    outer = _partition(document["lambda"])
    inner = _partition(document["mu"])
    content = _partition(document["nu"])
    if sum(outer) != sum(inner) + sum(content):
        _reject("SIZE_RELATION")

    raw_coefficients = document["coefficients"]
    if type(raw_coefficients) is not list or not 1 <= len(raw_coefficients) <= 29:
        _reject("INVALID_DOCUMENT")
    coefficients = tuple(_rational(item) for item in raw_coefficients)
    if coefficients[-1] == 0:
        _reject("NONCANONICAL_POLYNOMIAL")
    degree_bound = len(outer) * (len(outer) + 1) // 2
    if len(coefficients) - 1 > degree_bound:
        _reject("DEGREE_BOUND")
    if not any(coefficient < 0 for coefficient in coefficients):
        _reject("NO_NEGATIVE_COEFFICIENT")

    raw_values = document["values_t_1_through_29"]
    if type(raw_values) is not list or len(raw_values) != SAMPLE_COUNT:
        _reject("INVALID_DOCUMENT")
    values = tuple(_ensure_small_integer(item, nonnegative=True) for item in raw_values)
    for t, declared in enumerate(values, start=1):
        evaluated = _evaluate_polynomial(coefficients, t)
        if evaluated.denominator != 1 or evaluated.numerator != declared:
            _reject("DECLARED_POLYNOMIAL_MISMATCH")
    return outer, inner, content, coefficients, values, degree_bound


def lr_coefficient_tableaux(
    outer: tuple[int, ...],
    inner: tuple[int, ...],
    content: tuple[int, ...],
    *,
    budget: WorkBudget,
) -> int:
    """Count LR tableaux of shape ``outer/inner`` and weight ``content``.

    Rows are represented by counts of each entry.  Since a semistandard row is
    weakly increasing, those counts determine the row.  When its reverse word
    is appended, the worst lattice-prefix inequality for entry ``j`` occurs
    just after that row's ``j`` block; hence
    ``row_count[j] <= used[j-1] - used[j]`` for every ``j > 1``.
    """

    if sum(outer) != sum(inner) + sum(content):
        return 0
    row_count = max(len(outer), len(inner))
    padded_outer = outer + (0,) * (row_count - len(outer))
    padded_inner = inner + (0,) * (row_count - len(inner))
    if any(padded_inner[index] > padded_outer[index] for index in range(row_count)):
        return 0
    alphabet_size = len(content)

    @lru_cache(maxsize=None)
    def visit(
        row: int,
        used: tuple[int, ...],
        previous_start: int,
        previous_values: tuple[int, ...],
    ) -> int:
        budget.spend()
        if row == row_count:
            return int(used == content)

        start = padded_inner[row]
        end = padded_outer[row]
        cells = end - start
        remaining = tuple(content[index] - used[index] for index in range(alphabet_size))
        if any(value < 0 for value in remaining):
            return 0
        remaining_cells = sum(
            padded_outer[index] - padded_inner[index]
            for index in range(row, row_count)
        )
        if sum(remaining) != remaining_cells:
            return 0
        if cells == 0:
            return visit(row + 1, used, start, ())

        capacities = [remaining[0]]
        capacities.extend(
            min(remaining[index], used[index - 1] - used[index])
            for index in range(1, alphabet_size)
        )
        if any(value < 0 for value in capacities) or sum(capacities) < cells:
            return 0

        above: list[int] = []
        previous_end = previous_start + len(previous_values)
        for column in range(start, end):
            if previous_start <= column < previous_end:
                above.append(previous_values[column - previous_start])
            else:
                above.append(0)

        suffix_capacity = [0] * (alphabet_size + 1)
        for index in range(alphabet_size - 1, -1, -1):
            suffix_capacity[index] = suffix_capacity[index + 1] + capacities[index]
        counts = [0] * alphabet_size
        total = 0

        def emit() -> None:
            nonlocal total
            budget.spend()
            values = tuple(
                entry
                for index, multiplicity in enumerate(counts, start=1)
                for entry in (index,) * multiplicity
            )
            if any(
                upper != 0 and lower <= upper
                for upper, lower in zip(above, values, strict=True)
            ):
                return
            next_used = tuple(
                used[index] + counts[index] for index in range(alphabet_size)
            )
            total += visit(row + 1, next_used, start, values)
            _ensure_arithmetic_bound(total)

        def generate(index: int, left: int) -> None:
            if index == alphabet_size:
                if left == 0:
                    emit()
                return
            lower = max(0, left - suffix_capacity[index + 1])
            upper = min(capacities[index], left)
            for multiplicity in range(lower, upper + 1):
                budget.spend()
                counts[index] = multiplicity
                generate(index + 1, left - multiplicity)

        generate(0, cells)
        return total

    coefficient = visit(0, (0,) * alphabet_size, 0, ())
    _ensure_arithmetic_bound(coefficient)
    return coefficient


def _multiply_by_linear(
    polynomial: list[Fraction], constant: int
) -> list[Fraction]:
    result = [Fraction(0)] * (len(polynomial) + 1)
    for degree, coefficient in enumerate(polynomial):
        result[degree] += coefficient * constant
        result[degree + 1] += coefficient
    return result


def interpolate_newton(values_at_one_through_29: tuple[int, ...]) -> tuple[Fraction, ...]:
    """Recover a degree-at-most-28 polynomial by forward differences."""

    if len(values_at_one_through_29) != SAMPLE_COUNT:
        _abort("INTERPOLATION_FAILURE")
    differences = [Fraction(value) for value in values_at_one_through_29]
    result = [Fraction(0)] * SAMPLE_COUNT
    # basis is binomial(t-1, k), initially k=0.
    basis = [Fraction(1)]
    for order in range(SAMPLE_COUNT):
        leading_difference = differences[0]
        for degree, coefficient in enumerate(basis):
            result[degree] += leading_difference * coefficient
        if order + 1 == SAMPLE_COUNT:
            break
        differences = [
            differences[index + 1] - differences[index]
            for index in range(len(differences) - 1)
        ]
        basis = _multiply_by_linear(basis, -(order + 1))
        divisor = order + 1
        basis = [coefficient / divisor for coefficient in basis]
    while len(result) > 1 and result[-1] == 0:
        result.pop()
    for coefficient in result:
        _ensure_arithmetic_bound(coefficient.numerator)
        _ensure_arithmetic_bound(coefficient.denominator)
    return tuple(result)


def _fraction_documents(coefficients: tuple[Fraction, ...]) -> list[dict[str, int]]:
    return [
        {"denominator": value.denominator, "numerator": value.numerator}
        for value in coefficients
    ]


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii") + b"\n"
    return hashlib.sha256(payload).hexdigest()


def _accepted_facts(
    outer: tuple[int, ...],
    inner: tuple[int, ...],
    content: tuple[int, ...],
    coefficients: tuple[Fraction, ...],
    values: tuple[int, ...],
    degree_bound: int,
) -> dict[str, object]:
    first_negative = next(
        index for index, coefficient in enumerate(coefficients) if coefficient < 0
    )
    return {
        "coefficients_sha256": _canonical_sha256(_fraction_documents(coefficients)),
        "degree_bound": degree_bound,
        "first_negative_degree": first_negative,
        "interpolation_points": SAMPLE_COUNT,
        "lambda": list(outer),
        "lambda_size": sum(outer),
        "mu": list(inner),
        "mu_size": sum(inner),
        "nu": list(content),
        "nu_size": sum(content),
        "sample_values_sha256": _canonical_sha256(list(values)),
    }


def evaluate_document_with_status(
    document: object,
    *,
    operation_limit: int = DEFAULT_OPERATION_LIMIT,
) -> tuple[dict[str, object], bool]:
    try:
        outer, inner, content, declared_coefficients, declared_values, degree_bound = (
            _validate_candidate(document)
        )
        if type(operation_limit) is not int or operation_limit < 1:
            _abort("COMPUTATION_LIMIT")
        budget = WorkBudget(operation_limit)
        computed_values: list[int] = []
        for t in range(1, SAMPLE_COUNT + 1):
            value = lr_coefficient_tableaux(
                tuple(t * part for part in outer),
                tuple(t * part for part in inner),
                tuple(t * part for part in content),
                budget=budget,
            )
            if value < 0:
                _abort("NEGATIVE_LR_COUNT")
            _ensure_arithmetic_bound(value)
            computed_values.append(value)
        values = tuple(computed_values)
        if values != declared_values:
            _reject("SAMPLE_MISMATCH")
        coefficients = interpolate_newton(values)
        if len(coefficients) - 1 > degree_bound:
            _abort("SOURCE_DEGREE_BOUND_VIOLATION")
        if coefficients != declared_coefficients:
            _reject("POLYNOMIAL_MISMATCH")
        return _result(
            True,
            "ACCEPTED",
            _accepted_facts(
                outer,
                inner,
                content,
                coefficients,
                values,
                degree_bound,
            ),
        ), False
    except CandidateFailure as failure:
        return _result(False, failure.code), False
    except ComputationFailure as failure:
        return _result(False, failure.code), True
    except (MemoryError, OverflowError, RecursionError):
        return _result(False, "COMPUTATION_FAILURE"), True


def evaluate_document(
    document: object,
    *,
    operation_limit: int = DEFAULT_OPERATION_LIMIT,
) -> dict[str, object]:
    return evaluate_document_with_status(
        document, operation_limit=operation_limit
    )[0]


def _pairs_without_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            _reject("INVALID_JSON")
        result[key] = value
    return result


def _forbid_number(_token: str) -> NoReturn:
    _reject("INVALID_JSON")


def _parse_integer(token: str) -> int:
    digits = token[1:] if token.startswith("-") else token
    if not digits or len(digits) > 1234:
        _reject("INTEGER_TOO_LARGE")
    try:
        value = int(token)
    except ValueError:
        _reject("INVALID_JSON")
    if value.bit_length() > MAXIMUM_INTEGER_BITS:
        _reject("INTEGER_TOO_LARGE")
    return value


def _read_snapshot(path: Path) -> bytes:
    try:
        named = path.lstat()
    except OSError:
        _abort("INPUT_UNAVAILABLE")
    if stat.S_ISLNK(named.st_mode) or not stat.S_ISREG(named.st_mode):
        _abort("INPUT_NOT_REGULAR")
    if named.st_size > MAXIMUM_INPUT_BYTES:
        _abort("INPUT_TOO_LARGE")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        _abort("INPUT_UNAVAILABLE")
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_dev != named.st_dev
            or opened.st_ino != named.st_ino
            or opened.st_size != named.st_size
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
        final = os.fstat(descriptor)
        if (
            final.st_size != opened.st_size
            or final.st_mtime_ns != opened.st_mtime_ns
            or final.st_ctime_ns != opened.st_ctime_ns
        ):
            _abort("INPUT_CHANGED")
        return bytes(payload)
    except OSError:
        _abort("INPUT_UNAVAILABLE")
    finally:
        os.close(descriptor)


def load_document(path: Path) -> object:
    raw = _read_snapshot(path)
    try:
        return json.loads(
            raw.decode("ascii", errors="strict"),
            object_pairs_hook=_pairs_without_duplicates,
            parse_int=_parse_integer,
            parse_float=_forbid_number,
            parse_constant=_forbid_number,
        )
    except (UnicodeError, json.JSONDecodeError, RecursionError, ValueError):
        _reject("INVALID_JSON")


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
    if len(arguments) != 2:
        _emit(_result(False, "USAGE_ERROR"))
        return 2
    try:
        document = load_document(Path(arguments[1]))
    except CandidateFailure as failure:
        _emit(_result(False, failure.code))
        return 1
    except ComputationFailure as failure:
        _emit(_result(False, failure.code))
        return 2
    result, infrastructure_failure = evaluate_document_with_status(document)
    _emit(result)
    if infrastructure_failure:
        return 2
    return 0 if result["accepted"] is True else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
