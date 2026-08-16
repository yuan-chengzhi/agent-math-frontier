from __future__ import annotations

from fractions import Fraction
import importlib.util
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "verifiers" / "amf.stretched-lr.exact.v1"
TARGET = ROOT / "targets" / "frontier-stretched-lr"
REGRESSIONS = TARGET / "evidence" / "regression" / "cases.json"
sys.path.insert(0, str(ROOT / "scripts"))

from contracts import (  # noqa: E402
    canonical_sha256,
    load_json,
    validate_target_card,
    validate_verifier_registry,
)


def load_module(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


PRIMARY = load_module("amf_lr_primary", VERIFIER / "primary.py")
SECONDARY = load_module("amf_lr_secondary", VERIFIER / "secondary.py")
DISPATCH = load_module("amf_lr_dispatch", VERIFIER / "dispatch.py")


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii") + b"\n"


def rationals(values: list[tuple[int, int]]) -> list[dict[str, int]]:
    return [
        {"denominator": denominator, "numerator": numerator}
        for numerator, denominator in values
    ]


def candidate(
    outer: list[int],
    inner: list[int],
    content: list[int],
    coefficients: list[tuple[int, int]],
    values: list[int],
) -> dict[str, object]:
    return {
        "coefficients": rationals(coefficients),
        "lambda": outer,
        "lr_convention": PRIMARY.LR_CONVENTION,
        "mu": inner,
        "nu": content,
        "polynomial_basis": PRIMARY.POLYNOMIAL_BASIS,
        "sample_domain": PRIMARY.SAMPLE_DOMAIN,
        "schema": PRIMARY.CANDIDATE_SCHEMA,
        "values_t_1_through_29": values,
    }


def partitions(total: int, largest: int | None = None):
    if total == 0:
        yield ()
        return
    ceiling = total if largest is None else min(total, largest)
    for first in range(ceiling, 0, -1):
        for rest in partitions(total - first, first):
            yield (first,) + rest


def primary_lr(outer: tuple[int, ...], inner: tuple[int, ...], content: tuple[int, ...]) -> int:
    return PRIMARY.lr_coefficient_tableaux(
        outer,
        inner,
        content,
        budget=PRIMARY.WorkBudget(2_000_000),
    )


def secondary_lr(outer: tuple[int, ...], inner: tuple[int, ...], content: tuple[int, ...]) -> int:
    return SECONDARY.lr_coefficient_jacobi_trudi_pieri(
        outer,
        inner,
        content,
        budget=SECONDARY.Counter(2_000_000),
    )


class StretchedLittlewoodRichardsonTests(unittest.TestCase):
    def write_candidate(self, directory: Path, value: object, name: str = "candidate.json") -> Path:
        path = directory / name
        path.write_bytes(canonical_bytes(value))
        return path

    def normalized(self, result: dict[str, object]) -> dict[str, object]:
        return {
            "accepted": result["accepted"],
            "facts": result["facts"],
            "reason_code": result["reason_code"],
        }

    def test_registered_manifest_and_active_target_card_obey_contract(self) -> None:
        registry = validate_verifier_registry(
            load_json(ROOT / "data" / "verifiers.json"), root=ROOT
        )
        self.assertIn(PRIMARY.VERIFIER_ID, registry)
        manifest = registry[PRIMARY.VERIFIER_ID]["manifest_value"]
        self.assertEqual(
            manifest["binds_verification_mode"],
            "exact_integer_polynomial_two_implementations",
        )

        catalog = load_json(ROOT / "data" / "problems.json")
        problem = next(
            item for item in catalog["problems"]
            if item["id"] == "frontier-stretched-lr"
        )
        self.assertEqual(problem["stage"], "active")
        card = validate_target_card(
            load_json(TARGET / "target-card.json"),
            root=ROOT,
            expected_problem_id=problem["id"],
            expected_problem_card_sha256=canonical_sha256(problem),
            expected_source_revision=problem["formalization"]["revision"],
        )
        self.assertEqual(card["verifier_id"], PRIMARY.VERIFIER_ID)

    def test_current_route_baseline_excludes_the_known_length_four_range(self) -> None:
        metadata = load_json(
            TARGET / "evidence" / "baseline" / "source-metadata.json"
        )
        self.assertEqual(metadata["schema"], "AMF_STRETCHED_LR_BASELINE_SOURCES_1")
        self.assertEqual(
            metadata["known_positive_subrange"]["source"],
            "https://arxiv.org/abs/2607.22301v1",
        )
        self.assertIn(
            "length at least 5",
            metadata["known_positive_subrange"]["route_floor"],
        )

    def test_regression_artifact_is_exact_and_both_mathematical_paths_reproduce_it(self) -> None:
        artifact = load_json(REGRESSIONS)
        self.assertEqual(artifact["schema"], "AMF_STRETCHED_LR_REGRESSIONS_1")
        self.assertEqual(len(artifact["cases"]), 3)
        for case in artifact["cases"]:
            observed_primary: list[int] = []
            observed_secondary: list[int] = []
            for scale in range(1, 30):
                outer = tuple(scale * part for part in case["lambda"])
                inner = tuple(scale * part for part in case["mu"])
                content = tuple(scale * part for part in case["nu"])
                observed_primary.append(primary_lr(outer, inner, content))
                observed_secondary.append(secondary_lr(outer, inner, content))
            self.assertEqual(
                observed_primary,
                case["expected_values_t_1_through_29"],
                case["id"],
            )
            self.assertEqual(observed_secondary, observed_primary, case["id"])
            primary_polynomial = PRIMARY.interpolate_newton(tuple(observed_primary))
            secondary_polynomial = SECONDARY.interpolate_vandermonde(
                tuple(observed_secondary)
            )
            expected = tuple(
                Fraction(value["numerator"], value["denominator"])
                for value in case["expected_coefficients"]
            )
            self.assertEqual(primary_polynomial, expected)
            self.assertEqual(secondary_polynomial, expected)

    def test_exhaustive_small_coefficients_agree_and_inner_roles_are_symmetric(self) -> None:
        checked = 0
        for outer_size in range(2, 9):
            for outer in partitions(outer_size):
                for inner_size in range(1, outer_size):
                    for inner in partitions(inner_size):
                        for content in partitions(outer_size - inner_size):
                            first = primary_lr(outer, inner, content)
                            second = secondary_lr(outer, inner, content)
                            self.assertEqual(
                                first,
                                second,
                                (outer, inner, content),
                            )
                            swapped = primary_lr(outer, content, inner)
                            self.assertEqual(first, swapped, (outer, inner, content))
                            checked += 1
        self.assertGreater(checked, 4_900)

    def test_outer_inner_content_roles_and_size_equation_are_not_permuted(self) -> None:
        self.assertEqual(primary_lr((3, 2, 1), (2, 1), (2, 1)), 2)
        self.assertEqual(secondary_lr((3, 2, 1), (2, 1), (2, 1)), 2)
        self.assertEqual(primary_lr((2, 1), (3, 2, 1), (2, 1)), 0)
        self.assertEqual(secondary_lr((2, 1), (3, 2, 1), (2, 1)), 0)

        wrong_equation = candidate(
            [3, 2, 1], [2, 1], [1], [(-1, 1), (1, 1)], list(range(29))
        )
        for checker in (PRIMARY, SECONDARY):
            with self.subTest(checker=checker.CHECKER_ID):
                result = checker.evaluate_document(wrong_equation)
                self.assertEqual(result["reason_code"], "SIZE_RELATION")

    def test_interpolation_paths_agree_on_integer_and_rational_coefficients(self) -> None:
        generator = random.Random(0x1A2B3C)
        polynomials = [
            (Fraction(0), Fraction(-1, 2), Fraction(1, 2)),
            (Fraction(1), Fraction(1)),
        ]
        for _case in range(20):
            degree = generator.randint(0, 8)
            polynomials.append(
                tuple(Fraction(generator.randint(-5, 5)) for _ in range(degree + 1))
            )
        for polynomial in polynomials:
            values = tuple(
                sum(
                    coefficient * (argument ** degree)
                    for degree, coefficient in enumerate(polynomial)
                )
                for argument in range(1, 30)
            )
            if any(value.denominator != 1 for value in values):
                continue
            integer_values = tuple(value.numerator for value in values)
            expected = list(polynomial)
            while len(expected) > 1 and expected[-1] == 0:
                expected.pop()
            self.assertEqual(PRIMARY.interpolate_newton(integer_values), tuple(expected))
            self.assertEqual(
                SECONDARY.interpolate_vandermonde(integer_values), tuple(expected)
            )

    def test_honest_positive_regression_is_not_misreported_as_success(self) -> None:
        positive = candidate(
            [3, 2, 1],
            [2, 1],
            [2, 1],
            [(1, 1), (1, 1)],
            list(range(2, 31)),
        )
        for checker in (PRIMARY, SECONDARY):
            result, infrastructure = checker.evaluate_document_with_status(positive)
            self.assertFalse(infrastructure)
            self.assertFalse(result["accepted"])
            self.assertEqual(result["reason_code"], "NO_NEGATIVE_COEFFICIENT")

    def test_forged_negative_polynomial_reaches_both_cores_and_is_rejected(self) -> None:
        # t-1 is nonnegative on the required sample domain and has a negative
        # constant coefficient, but the true stretched polynomial is t+1.
        forged = candidate(
            [3, 2, 1],
            [2, 1],
            [2, 1],
            [(-1, 1), (1, 1)],
            list(range(29)),
        )
        results = []
        for checker in (PRIMARY, SECONDARY):
            result, infrastructure = checker.evaluate_document_with_status(forged)
            self.assertFalse(infrastructure)
            self.assertEqual(result["reason_code"], "SAMPLE_MISMATCH")
            results.append(self.normalized(result))
        self.assertEqual(results[0], results[1])

        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_candidate(Path(temporary), forged)
            dispatched, infrastructure = DISPATCH.dispatch_path(path)
        self.assertFalse(infrastructure)
        self.assertFalse(dispatched["accepted"])
        self.assertEqual(dispatched["reason_code"], "SAMPLE_MISMATCH")

    def test_acceptance_assembly_is_exercised_only_through_explicit_test_seams(self) -> None:
        # This is not mathematical evidence.  The patched oracle deliberately
        # returns t-1 instead of the true t+1 for the regression triple, solely
        # to exercise production acceptance assembly without inventing a
        # counterexample fixture.
        synthetic = candidate(
            [3, 2, 1],
            [2, 1],
            [2, 1],
            [(-1, 1), (1, 1)],
            list(range(29)),
        )

        def synthetic_oracle(
            outer: tuple[int, ...],
            _inner: tuple[int, ...],
            _content: tuple[int, ...],
            **_kwargs: object,
        ) -> int:
            return outer[-1] - 1

        with mock.patch.object(PRIMARY, "lr_coefficient_tableaux", synthetic_oracle):
            primary_result, primary_infrastructure = PRIMARY.evaluate_document_with_status(
                synthetic
            )
        with mock.patch.object(
            SECONDARY,
            "lr_coefficient_jacobi_trudi_pieri",
            synthetic_oracle,
        ):
            secondary_result, secondary_infrastructure = (
                SECONDARY.evaluate_document_with_status(synthetic)
            )
        self.assertFalse(primary_infrastructure)
        self.assertFalse(secondary_infrastructure)
        self.assertTrue(primary_result["accepted"])
        self.assertTrue(secondary_result["accepted"])
        self.assertEqual(
            self.normalized(primary_result), self.normalized(secondary_result)
        )

        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            candidate_path = self.write_candidate(directory, synthetic)
            normalized = self.normalized(primary_result)

            def accepting_checker(path: Path, checker_id: str) -> None:
                output = {
                    **normalized,
                    "checker": checker_id,
                    "schema": DISPATCH.RESULT_SCHEMA,
                    "verifier_id": DISPATCH.VERIFIER_ID,
                }
                path.write_text(
                    textwrap.dedent(
                        f"""\
                        import json
                        print(json.dumps({output!r}, sort_keys=True, separators=(\",\", \":\")))
                        """
                    ),
                    encoding="ascii",
                )

            first = directory / "first.py"
            second = directory / "second.py"
            accepting_checker(first, DISPATCH.PRIMARY_ID)
            accepting_checker(second, DISPATCH.SECONDARY_ID)
            dispatched, infrastructure = DISPATCH.dispatch_path(
                candidate_path,
                primary_path=first,
                secondary_path=second,
            )
        self.assertFalse(infrastructure)
        self.assertTrue(dispatched["accepted"])
        self.assertEqual(dispatched["reason_code"], "ACCEPTED")

    def test_partition_bounds_rational_canonicality_and_extra_fields_fail_closed(self) -> None:
        base = candidate(
            [3, 2, 1], [2, 1], [2, 1], [(-1, 1), (1, 1)], list(range(29))
        )
        mutations: list[tuple[str, dict[str, object], str]] = []

        extra = dict(base)
        extra["claimed_verified"] = True
        mutations.append(("extra", extra, "INVALID_DOCUMENT"))

        nonpartition = dict(base)
        nonpartition["lambda"] = [2, 3, 1]
        mutations.append(("order", nonpartition, "INVALID_PARTITION"))

        long_partition = dict(base)
        long_partition["lambda"] = [3, 2, 1, 1, 1, 1, 1, 1]
        mutations.append(("length", long_partition, "INVALID_PARTITION"))

        excessive_sum = dict(base)
        excessive_sum["lambda"] = [20, 11]
        mutations.append(("sum", excessive_sum, "PARTITION_BOUND"))

        unreduced = dict(base)
        unreduced["coefficients"] = rationals([(-2, 2), (1, 1)])
        mutations.append(("fraction", unreduced, "NONCANONICAL_RATIONAL"))

        trailing_zero = dict(base)
        trailing_zero["coefficients"] = rationals([(-1, 1), (1, 1), (0, 1)])
        mutations.append(("trailing", trailing_zero, "NONCANONICAL_POLYNOMIAL"))

        for name, value, reason in mutations:
            for checker in (PRIMARY, SECONDARY):
                with self.subTest(case=name, checker=checker.CHECKER_ID):
                    result = checker.evaluate_document(value)
                    self.assertEqual(result["reason_code"], reason)

    def test_declared_values_must_be_integral_nonnegative_and_match_polynomial(self) -> None:
        negative_value = candidate(
            [3, 2, 1], [2, 1], [2, 1], [(-1, 1), (1, 1)], list(range(29))
        )
        negative_value["values_t_1_through_29"] = [-1] + list(range(1, 29))

        inconsistent = candidate(
            [3, 2, 1], [2, 1], [2, 1], [(-1, 1), (1, 1)], list(range(29))
        )
        inconsistent["values_t_1_through_29"] = [1] + list(range(1, 29))

        rational_at_integer = candidate(
            [3, 2, 1], [2, 1], [2, 1], [(-1, 2), (1, 1)], list(range(29))
        )

        for checker in (PRIMARY, SECONDARY):
            self.assertEqual(
                checker.evaluate_document(negative_value)["reason_code"],
                "INVALID_DOCUMENT",
            )
            self.assertEqual(
                checker.evaluate_document(inconsistent)["reason_code"],
                "DECLARED_POLYNOMIAL_MISMATCH",
            )
            self.assertEqual(
                checker.evaluate_document(rational_at_integer)["reason_code"],
                "DECLARED_POLYNOMIAL_MISMATCH",
            )

    def test_operation_limits_are_infrastructure_failures(self) -> None:
        forged = candidate(
            [3, 2, 1], [2, 1], [2, 1], [(-1, 1), (1, 1)], list(range(29))
        )
        for checker in (PRIMARY, SECONDARY):
            result, infrastructure = checker.evaluate_document_with_status(
                forged, operation_limit=1
            )
            self.assertTrue(infrastructure)
            self.assertEqual(result["reason_code"], "COMPUTATION_LIMIT")

    def test_duplicate_float_huge_integer_deep_json_and_oversize_fail_closed(self) -> None:
        payloads = {
            "duplicate.json": b'{"schema":"x","schema":"y"}\n',
            "float.json": b'{"x":1.25}\n',
            "huge.json": b'{"x":' + b"9" * 1300 + b"}\n",
            "deep.json": b"[" * 1500 + b"0" + b"]" * 1500,
        }
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            for name, payload in payloads.items():
                path = directory / name
                path.write_bytes(payload)
                result, infrastructure = DISPATCH.dispatch_path(path)
                self.assertFalse(infrastructure, name)
                self.assertFalse(result["accepted"], name)
                self.assertIn(
                    result["reason_code"],
                    {"INVALID_JSON", "INTEGER_TOO_LARGE"},
                    name,
                )

            oversized = directory / "oversized.json"
            oversized.write_bytes(b" " * (DISPATCH.MAXIMUM_INPUT_BYTES + 1))
            result, infrastructure = DISPATCH.dispatch_path(oversized)
            self.assertTrue(infrastructure)
            self.assertEqual(result["reason_code"], "INPUT_TOO_LARGE")

    def test_symlink_and_fifo_are_rejected_without_following_or_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            regular = directory / "regular.json"
            regular.write_text("{}\n", encoding="ascii")
            link = directory / "link.json"
            link.symlink_to(regular)
            result, infrastructure = DISPATCH.dispatch_path(link)
            self.assertTrue(infrastructure)
            self.assertEqual(result["reason_code"], "INPUT_NOT_REGULAR")

            if hasattr(os, "mkfifo"):
                fifo = directory / "candidate.fifo"
                os.mkfifo(fifo)
                result, infrastructure = DISPATCH.dispatch_path(fifo)
                self.assertTrue(infrastructure)
                self.assertEqual(result["reason_code"], "INPUT_NOT_REGULAR")

    def test_dispatcher_detects_independent_checker_disagreement(self) -> None:
        forged = candidate(
            [3, 2, 1], [2, 1], [2, 1], [(-1, 1), (1, 1)], list(range(29))
        )
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            candidate_path = self.write_candidate(directory, forged)

            def fake_checker(path: Path, checker_id: str, reason: str) -> None:
                output = {
                    "accepted": False,
                    "checker": checker_id,
                    "facts": DISPATCH._blank_facts(),
                    "reason_code": reason,
                    "schema": DISPATCH.RESULT_SCHEMA,
                    "verifier_id": DISPATCH.VERIFIER_ID,
                }
                path.write_text(
                    textwrap.dedent(
                        f"""\
                        import json
                        print(json.dumps({output!r}, sort_keys=True, separators=(\",\", \":\")))
                        raise SystemExit(1)
                        """
                    ),
                    encoding="ascii",
                )

            first = directory / "first.py"
            second = directory / "second.py"
            fake_checker(first, DISPATCH.PRIMARY_ID, "FIRST_REJECTION")
            fake_checker(second, DISPATCH.SECONDARY_ID, "SECOND_REJECTION")
            result, infrastructure = DISPATCH.dispatch_path(
                candidate_path,
                primary_path=first,
                secondary_path=second,
            )
        self.assertTrue(infrastructure)
        self.assertEqual(result["reason_code"], "CHECKER_DISAGREEMENT")

    def test_cli_contract_is_one_json_line_and_exit_codes_are_stable(self) -> None:
        forged = candidate(
            [3, 2, 1], [2, 1], [2, 1], [(-1, 1), (1, 1)], list(range(29))
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_candidate(Path(temporary), forged)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(VERIFIER / "dispatch.py"),
                    "--candidate",
                    str(path),
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=30,
            )
        self.assertEqual(completed.returncode, 1)
        self.assertEqual(completed.stderr, b"")
        self.assertEqual(completed.stdout.count(b"\n"), 1)
        result = json.loads(completed.stdout)
        self.assertEqual(result["reason_code"], "SAMPLE_MISMATCH")


if __name__ == "__main__":
    unittest.main()
