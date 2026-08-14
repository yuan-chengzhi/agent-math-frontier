#!/usr/bin/env python3
"""Exact offline checker for the frozen AIM #60 baseline-improvement target.

The checker trusts neither a search transcript nor a probable-prime flag.  A
candidate must cover every positive x below its claimed first prime with an
exact non-trivial divisor, either directly or through a checked congruence
rule.  The final value is proved prime by a compact Atkin--Morain ECPP
certificate whose elliptic-curve conditions are checked here using only
Python integer arithmetic.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
from typing import Any, NoReturn


VERIFIER_ID = "amf.aim60.certificate.v1"
CHECKER_ID = "EXACT_DIVISIBILITY_AND_ECPP"
RESULT_SCHEMA = "AMF_VERIFIER_RESULT_1"
CANDIDATE_SCHEMA = "AMF_AIM60_CANDIDATE_1"
BASELINE_SCHEMA = "AMF_AIM60_BASELINE_CERTIFICATE_1"

BASELINE_FIRST_PRIME_X = 616_980
MINIMUM_IMPROVEMENT_X = BASELINE_FIRST_PRIME_X + 1
MAXIMUM_FIRST_PRIME_X = 10_000_000
MAXIMUM_A = 10**20 - 1
MAXIMUM_INPUT_BYTES = 16 * 1024 * 1024
MAXIMUM_COVER_RULES = 128
MAXIMUM_TOTAL_RESIDUES = 4_096
MAXIMUM_COVER_OPERATIONS = 50_000_000
MAXIMUM_RULE_DIVISOR = 1_000_000_000
MAXIMUM_EXPLICIT_FACTORS = 250_000
MAXIMUM_ECPP_STEPS = 64
MAXIMUM_DECIMAL_DIGITS = 128

_UNSIGNED_DECIMAL = re.compile(r"^(0|[1-9][0-9]*)$")
_POSITIVE_DECIMAL = re.compile(r"^[1-9][0-9]*$")
_SIGNED_DECIMAL = re.compile(r"^(0|-?[1-9][0-9]*)$")


class CheckFailure(ValueError):
    """Bounded public rejection with a stable, non-reflective reason code."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class ApparatusFailure(RuntimeError):
    """An inconclusive verifier-resource failure, never a rejection."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _fail(code: str) -> NoReturn:
    raise CheckFailure(code)


def _abort(code: str) -> NoReturn:
    raise ApparatusFailure(code)


def _pairs_no_duplicates(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            _fail("DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _parse_small_int(token: str) -> int:
    # JSON integers are used only for bounded indices and residues.  Large
    # mathematical integers are canonical decimal strings.
    if len(token) > 10:
        _fail("INTEGER_OUT_OF_RANGE")
    try:
        value = int(token, 10)
    except ValueError:
        _fail("INVALID_JSON")
    if not -(1 << 31) <= value <= (1 << 31) - 1:
        _fail("INTEGER_OUT_OF_RANGE")
    return value


def _reject_number(_token: str) -> NoReturn:
    _fail("NON_INTEGER_NUMBER")


def read_regular_file(path: Path) -> bytes:
    """Read one bounded regular non-symlink file with race checks."""

    try:
        before = path.lstat()
    except OSError:
        _fail("INPUT_UNAVAILABLE")
    if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
        _fail("INPUT_NOT_REGULAR")
    if before.st_size > MAXIMUM_INPUT_BYTES:
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
            or opened.st_dev != before.st_dev
            or opened.st_ino != before.st_ino
            or opened.st_size != before.st_size
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
        after = os.fstat(descriptor)
        if (
            after.st_size != opened.st_size
            or after.st_mtime_ns != opened.st_mtime_ns
            or after.st_ctime_ns != opened.st_ctime_ns
        ):
            _fail("INPUT_CHANGED")
        return bytes(payload)
    except OSError:
        _fail("INPUT_UNAVAILABLE")
    finally:
        os.close(descriptor)


def decode_document(raw: bytes) -> dict[str, Any]:
    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_pairs_no_duplicates,
            parse_int=_parse_small_int,
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


def _decimal(
    value: object,
    *,
    signed: bool = False,
    positive: bool = False,
) -> int:
    if type(value) is not str or len(value) > MAXIMUM_DECIMAL_DIGITS:
        _fail("INVALID_DECIMAL")
    pattern = _SIGNED_DECIMAL if signed else (
        _POSITIVE_DECIMAL if positive else _UNSIGNED_DECIMAL
    )
    if pattern.fullmatch(value) is None:
        _fail("INVALID_DECIMAL")
    try:
        return int(value, 10)
    except (ValueError, MemoryError):
        _fail("INVALID_DECIMAL")


def _blank_facts() -> dict[str, object]:
    return {
        "a": None,
        "composite_values_certified": None,
        "congruence_rule_count": None,
        "explicit_factor_count": None,
        "first_prime_x": None,
        "prime_value": None,
        "prime_value_sha256": None,
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


def _is_prime_u64(n: int) -> bool:
    """Deterministic strong probable-prime test on 0 <= n < 2**64.

    The seven bases below are a complete deterministic witness set on this
    interval; unlike an open-ended Miller--Rabin run, this is not a
    probability claim.
    """

    if n < 2:
        return False
    small_primes = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37)
    for prime in small_primes:
        if n == prime:
            return True
        if n % prime == 0:
            return False

    odd_part = n - 1
    powers_of_two = 0
    while odd_part % 2 == 0:
        powers_of_two += 1
        odd_part //= 2
    for base in (2, 325, 9_375, 28_178, 450_775, 9_780_504, 1_795_265_022):
        base %= n
        if base == 0:
            continue
        value = pow(base, odd_part, n)
        if value in (1, n - 1):
            continue
        for _ in range(powers_of_two - 1):
            value = value * value % n
            if value == n - 1:
                break
        else:
            return False
    return True


Point = tuple[int, int] | None


def _point_add(left: Point, right: Point, modulus: int, curve_a: int) -> Point:
    """Conservative affine addition over Z/modulus Z.

    Every inversion must be a unit.  This is slightly more restrictive than
    projective arithmetic on a composite modulus, but cannot create a false
    acceptance: a non-unit denominator rejects the certificate.
    """

    if left is None:
        return right
    if right is None:
        return left
    x_left, y_left = left
    x_right, y_right = right
    if x_left == x_right:
        if (y_left + y_right) % modulus == 0:
            return None
        if y_left != y_right:
            _fail("ECPP_NONUNIT_ARITHMETIC")
        numerator = (3 * x_left * x_left + curve_a) % modulus
        denominator = (2 * y_left) % modulus
    else:
        numerator = (y_right - y_left) % modulus
        denominator = (x_right - x_left) % modulus
    if math.gcd(denominator, modulus) != 1:
        _fail("ECPP_NONUNIT_ARITHMETIC")
    slope = numerator * pow(denominator, -1, modulus) % modulus
    x_result = (slope * slope - x_left - x_right) % modulus
    y_result = (slope * (x_left - x_result) - y_left) % modulus
    return x_result, y_result


def _scalar_multiply(
    multiplier: int,
    point: Point,
    modulus: int,
    curve_a: int,
) -> Point:
    result: Point = None
    addend = point
    scalar = multiplier
    while scalar:
        if scalar & 1:
            result = _point_add(result, addend, modulus, curve_a)
        scalar >>= 1
        if scalar:
            addend = _point_add(addend, addend, modulus, curve_a)
    return result


def _ceil_fourth_root(n: int) -> int:
    root = math.isqrt(math.isqrt(n))
    while root**4 < n:
        root += 1
    while root > 0 and (root - 1) ** 4 >= n:
        root -= 1
    return root


def _parse_ecpp_step(value: object) -> dict[str, int]:
    fields = {"curve_a", "n", "point_x", "point_y", "s", "trace"}
    if type(value) is not dict or set(value) != fields:
        _fail("INVALID_ECPP_STEP")
    return {
        "n": _decimal(value["n"], positive=True),
        "trace": _decimal(value["trace"], signed=True),
        "s": _decimal(value["s"], positive=True),
        "curve_a": _decimal(value["curve_a"]),
        "point_x": _decimal(value["point_x"]),
        "point_y": _decimal(value["point_y"]),
    }


def verify_ecpp(certificate: object, expected_n: int) -> int:
    """Verify a PARI-shaped Atkin--Morain ECPP chain from first principles."""

    if type(certificate) is not dict or set(certificate) != {"kind", "steps"}:
        _fail("INVALID_ECPP_CERTIFICATE")
    if certificate["kind"] != "ATKIN_MORAIN_ECPP_1":
        _fail("INVALID_ECPP_CERTIFICATE")
    raw_steps = certificate["steps"]
    if (
        type(raw_steps) is not list
        or not 1 <= len(raw_steps) <= MAXIMUM_ECPP_STEPS
    ):
        _fail("INVALID_ECPP_CERTIFICATE")
    steps = [_parse_ecpp_step(step) for step in raw_steps]
    if steps[0]["n"] != expected_n:
        _fail("ECPP_TARGET_MISMATCH")

    quotients: list[int] = []
    for index, step in enumerate(steps):
        n = step["n"]
        trace = step["trace"]
        cofactor = step["s"]
        if n <= 2**64 or n % 2 == 0:
            _fail("ECPP_INVALID_MODULUS")
        if trace * trace >= 4 * n:
            _fail("ECPP_HASSE_BOUND")
        order = n + 1 - trace
        if order <= 0 or order % cofactor != 0:
            _fail("ECPP_INVALID_ORDER")
        q = order // cofactor
        # A ceiling fourth root gives a conservative, exact integer version
        # of q > (n^(1/4)+1)^2.
        if q <= (_ceil_fourth_root(n) + 1) ** 2:
            _fail("ECPP_Q_BOUND")
        if index + 1 < len(steps) and q != steps[index + 1]["n"]:
            _fail("ECPP_CHAIN_MISMATCH")
        quotients.append(q)

    terminal_prime = quotients[-1]
    if terminal_prime >= 2**64 or not _is_prime_u64(terminal_prime):
        _fail("ECPP_TERMINAL_NOT_PRIME")

    # Verify from the bottom upwards to mirror the recursive primality proof.
    for step, q in reversed(list(zip(steps, quotients))):
        n = step["n"]
        curve_a = step["curve_a"]
        point_x = step["point_x"]
        point_y = step["point_y"]
        if not (0 <= curve_a < n and 0 <= point_x < n and 0 <= point_y < n):
            _fail("ECPP_NONCANONICAL_COORDINATE")
        curve_b = (
            point_y * point_y
            - point_x * point_x * point_x
            - curve_a * point_x
        ) % n
        discriminant_part = (4 * pow(curve_a, 3, n) + 27 * pow(curve_b, 2, n)) % n
        if math.gcd(discriminant_part, n) != 1:
            _fail("ECPP_SINGULAR_CURVE")
        point = (point_x, point_y)
        if _scalar_multiply(step["s"], point, n, curve_a) is None:
            _fail("ECPP_SMALL_MULTIPLE_INFINITY")
        order = step["s"] * q
        if _scalar_multiply(order, point, n, curve_a) is not None:
            _fail("ECPP_ORDER_MULTIPLE_NONZERO")
    return len(steps)


def _validate_cover_rules(
    raw_rules: object,
    *,
    a: int,
    first_prime_x: int,
) -> tuple[bytearray, int]:
    if type(raw_rules) is not list or len(raw_rules) > MAXIMUM_COVER_RULES:
        _fail("INVALID_COVER_RULES")
    covered = bytearray(first_prime_x)
    total_residues = 0
    estimated_operations = 0
    previous_divisor = 0
    for raw_rule in raw_rules:
        if type(raw_rule) is not dict or set(raw_rule) != {"divisor", "residues"}:
            _fail("INVALID_COVER_RULE")
        divisor = _decimal(raw_rule["divisor"], positive=True)
        if not 2 <= divisor <= MAXIMUM_RULE_DIVISOR:
            _fail("COVER_DIVISOR_RANGE")
        if divisor <= previous_divisor:
            _fail("NONCANONICAL_COVER_RULES")
        previous_divisor = divisor
        residues = raw_rule["residues"]
        if type(residues) is not list or not residues:
            _fail("INVALID_COVER_RESIDUES")
        total_residues += len(residues)
        if total_residues > MAXIMUM_TOTAL_RESIDUES:
            _fail("COVER_RESIDUE_LIMIT")
        previous_residue = -1
        for residue in residues:
            if type(residue) is not int or not 0 <= residue < divisor:
                _fail("INVALID_COVER_RESIDUE")
            if residue <= previous_residue:
                _fail("NONCANONICAL_COVER_RESIDUES")
            previous_residue = residue
            if (pow(residue, 12, divisor) + a) % divisor != 0:
                _fail("FALSE_CONGRUENCE_RULE")
            start = divisor if residue == 0 else residue
            if start < first_prime_x:
                estimated_operations += 1 + (first_prime_x - 1 - start) // divisor
            if estimated_operations > MAXIMUM_COVER_OPERATIONS:
                _abort("COVER_OPERATION_LIMIT")
            while start < first_prime_x and start**12 + a <= divisor:
                start += divisor
            for x in range(start, first_prime_x, divisor):
                covered[x] = 1
    return covered, len(raw_rules)


def _validate_explicit_factors(
    raw_factors: object,
    *,
    a: int,
    first_prime_x: int,
    covered: bytearray,
) -> int:
    if type(raw_factors) is not list or len(raw_factors) > MAXIMUM_EXPLICIT_FACTORS:
        _fail("INVALID_FACTOR_CERTIFICATES")
    expected_count = sum(1 for x in range(1, first_prime_x) if not covered[x])
    if len(raw_factors) != expected_count:
        _fail("INCOMPLETE_COMPOSITE_COVERAGE")
    cursor = 0
    for x in range(1, first_prime_x):
        if covered[x]:
            continue
        raw = raw_factors[cursor]
        cursor += 1
        if type(raw) is not dict or set(raw) != {"factor", "x"}:
            _fail("INVALID_FACTOR_CERTIFICATE")
        if type(raw["x"]) is not int or raw["x"] != x:
            _fail("NONCANONICAL_FACTOR_SEQUENCE")
        factor = _decimal(raw["factor"], positive=True)
        value = x**12 + a
        if not 1 < factor < value or value % factor != 0:
            _fail("FALSE_COMPOSITE_FACTOR")
    return expected_count


def evaluate_document_with_status(
    document: object,
    *,
    expected_schema: str = CANDIDATE_SCHEMA,
    minimum_first_prime_x: int = MINIMUM_IMPROVEMENT_X,
) -> tuple[dict[str, object], bool]:
    fields = {
        "a",
        "composite_cover_rules",
        "explicit_factors",
        "first_prime_x",
        "primality_certificate",
        "schema",
    }
    if type(document) is not dict or set(document) != fields:
        return _result(False, "INVALID_DOCUMENT"), False
    if document["schema"] != expected_schema:
        return _result(False, "INVALID_SCHEMA"), False
    try:
        a = _decimal(document["a"], positive=True)
        if not 1 <= a <= MAXIMUM_A:
            _fail("A_OUT_OF_RANGE")
        first_prime_x = document["first_prime_x"]
        if (
            type(first_prime_x) is not int
            or not minimum_first_prime_x <= first_prime_x <= MAXIMUM_FIRST_PRIME_X
        ):
            _fail("FIRST_PRIME_X_OUT_OF_RANGE")
        covered, rule_count = _validate_cover_rules(
            document["composite_cover_rules"],
            a=a,
            first_prime_x=first_prime_x,
        )
        factor_count = _validate_explicit_factors(
            document["explicit_factors"],
            a=a,
            first_prime_x=first_prime_x,
            covered=covered,
        )
        prime_value = first_prime_x**12 + a
        verify_ecpp(document["primality_certificate"], prime_value)
    except CheckFailure as failure:
        return _result(False, failure.code), False
    except ApparatusFailure as failure:
        return _result(False, failure.code), True
    except (MemoryError, OverflowError):
        return _result(False, "RESOURCE_FAILURE"), True

    prime_text = str(prime_value)
    facts = {
        "a": str(a),
        "composite_values_certified": first_prime_x - 1,
        "congruence_rule_count": rule_count,
        "explicit_factor_count": factor_count,
        "first_prime_x": first_prime_x,
        "prime_value": prime_text,
        "prime_value_sha256": hashlib.sha256(prime_text.encode("ascii")).hexdigest(),
    }
    return _result(True, "ACCEPTED", facts), False


def evaluate_document(
    document: object,
    *,
    expected_schema: str = CANDIDATE_SCHEMA,
    minimum_first_prime_x: int = MINIMUM_IMPROVEMENT_X,
) -> dict[str, object]:
    """Compatibility wrapper for in-process callers."""

    return evaluate_document_with_status(
        document,
        expected_schema=expected_schema,
        minimum_first_prime_x=minimum_first_prime_x,
    )[0]


def evaluate_path_with_status(path: Path) -> tuple[dict[str, object], bool]:
    try:
        return evaluate_document_with_status(decode_document(read_regular_file(path)))
    except CheckFailure as failure:
        return _result(False, failure.code), False
    except ApparatusFailure as failure:
        return _result(False, failure.code), True
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
    result, apparatus_failure = evaluate_path_with_status(Path(argv[1]))
    _emit(result)
    if apparatus_failure:
        return 2
    return 0 if result["accepted"] is True else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
