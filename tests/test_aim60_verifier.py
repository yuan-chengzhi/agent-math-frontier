from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "verifiers" / "amf.aim60.certificate.v1"
VERIFIER_V2 = ROOT / "verifiers" / "amf.aim60.certificate.v2"
TARGET = ROOT / "targets" / "aim-60-first-prime"
BASELINE = TARGET / "evidence" / "baseline"
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


CHECKER = load_module("amf_aim60_checker", VERIFIER / "check.py")
CHECKER_V2 = load_module("amf_aim60_checker_v2", VERIFIER_V2 / "check.py")


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii") + b"\n"


def trial_prime(n: int) -> bool:
    if n < 2:
        return False
    divisor = 2
    while divisor * divisor <= n:
        if n % divisor == 0:
            return False
        divisor += 1
    return True


class Aim60VerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.baseline_path = BASELINE / "baseline-certificate.json"
        cls.baseline = load_json(cls.baseline_path)

    def assert_rejected(self, value: object, reason: str) -> None:
        result = CHECKER.evaluate_document(
            value,
            expected_schema=CHECKER.BASELINE_SCHEMA,
            minimum_first_prime_x=CHECKER.BASELINE_FIRST_PRIME_X,
        )
        self.assertFalse(result["accepted"])
        self.assertEqual(result["reason_code"], reason)

    def test_registered_manifest_and_frozen_target_obey_contract(self) -> None:
        registry = validate_verifier_registry(
            load_json(ROOT / "data" / "verifiers.json"), root=ROOT
        )
        self.assertIn(CHECKER.VERIFIER_ID, registry)
        self.assertIn(CHECKER_V2.VERIFIER_ID, registry)
        manifest = registry[CHECKER.VERIFIER_ID]["manifest_value"]
        self.assertEqual(
            manifest["binds_verification_mode"],
            "integer_factor_and_primality_certificates",
        )
        self.assertFalse(manifest["network"])

        catalog = load_json(ROOT / "data" / "problems.json")
        problem = next(
            item for item in catalog["problems"]
            if item["id"] == "aim-60-first-prime"
        )
        self.assertEqual(problem["stage"], "curated")
        self.assertEqual(problem["recommendation"], "quarantine")
        self.assertEqual(problem["hard_gates"]["open_status"], "fail")
        card = validate_target_card(
            load_json(TARGET / "target-card.json"),
            root=ROOT,
            expected_problem_id=problem["id"],
            expected_problem_card_sha256=canonical_sha256(problem),
            expected_source_revision=problem["formalization"]["revision"],
        )
        self.assertEqual(card["verifier_id"], CHECKER_V2.VERIFIER_ID)
        self.assertEqual(card["claim_scope"], "FINITE_INSTANCE")
        self.assertIn("not global optimality or novelty", card["canonical_statement"])
        self.assertFalse((TARGET / "target-bundle.json").exists())
        for pattern in (
            "*receipt*.json",
            "review-*.json",
            "red-team-*.json",
            "budget-*.json",
        ):
            self.assertEqual(list(TARGET.rglob(pattern)), [])

    def test_v2_enforces_the_provisional_public_floor_and_rebrands_results(self) -> None:
        candidate = copy.deepcopy(self.baseline)
        candidate["schema"] = CHECKER_V2.CANDIDATE_SCHEMA
        candidate["first_prime_x"] = CHECKER_V2.PROVISIONAL_PUBLIC_BASELINE_X
        result = CHECKER_V2.evaluate_document(candidate)
        self.assertFalse(result["accepted"])
        self.assertEqual(result["reason_code"], "FIRST_PRIME_X_OUT_OF_RANGE")
        self.assertEqual(result["verifier_id"], CHECKER_V2.VERIFIER_ID)
        self.assertEqual(CHECKER_V2.MINIMUM_FIRST_PRIME_X, 1_455_091)

    def test_primary_source_metadata_freezes_only_the_public_example(self) -> None:
        metadata = load_json(BASELINE / "source-metadata.json")
        raw_certificate = self.baseline_path.read_bytes()
        self.assertEqual(len(raw_certificate), 15_067)
        self.assertEqual(
            hashlib.sha256(raw_certificate).hexdigest(),
            "07653108594d15748ce9bf11559a7cdeaf7d8e327615467dc55751f7075427e6",
        )
        self.assertEqual(
            metadata["sources"][0]["retrieved_sha256"],
            "4bf2321149bb0a7ad1eae4f6a767b23d7a2f7eceb73f49aee4832a4cff057a37",
        )
        self.assertEqual(metadata["frozen_example"]["a"], "488669")
        self.assertEqual(
            metadata["frozen_example"]["first_positive_prime_x"], 616980
        )
        self.assertIn("not a current-record", metadata["frozen_example"]["claim"])

    def test_baseline_certificate_is_exactly_accepted_in_baseline_mode(self) -> None:
        result = CHECKER.evaluate_document(
            self.baseline,
            expected_schema=CHECKER.BASELINE_SCHEMA,
            minimum_first_prime_x=CHECKER.BASELINE_FIRST_PRIME_X,
        )
        self.assertTrue(result["accepted"], result)
        prime_value = 616980**12 + 488669
        self.assertEqual(
            result["facts"],
            {
                "a": "488669",
                "composite_values_certified": 616979,
                "congruence_rule_count": 5,
                "explicit_factor_count": 225,
                "first_prime_x": 616980,
                "prime_value": str(prime_value),
                "prime_value_sha256": hashlib.sha256(
                    str(prime_value).encode("ascii")
                ).hexdigest(),
            },
        )

    def test_baseline_is_not_a_production_success_candidate(self) -> None:
        wrong_schema = CHECKER.evaluate_document(self.baseline)
        self.assertEqual(wrong_schema["reason_code"], "INVALID_SCHEMA")
        relabeled = copy.deepcopy(self.baseline)
        relabeled["schema"] = CHECKER.CANDIDATE_SCHEMA
        threshold = CHECKER.evaluate_document(relabeled)
        self.assertEqual(threshold["reason_code"], "FIRST_PRIME_X_OUT_OF_RANGE")

    def test_all_positive_indices_starting_at_one_are_accounted_for(self) -> None:
        a = int(self.baseline["a"])
        first = self.baseline["first_prime_x"]
        rules = [
            (int(rule["divisor"]), set(rule["residues"]))
            for rule in self.baseline["composite_cover_rules"]
        ]
        factors = {
            entry["x"]: int(entry["factor"])
            for entry in self.baseline["explicit_factors"]
        }
        self.assertEqual(sorted(factors), list(range(2730, first, 2730)))
        for x in range(1, first):
            value = x**12 + a
            congruence_witnesses = [
                divisor
                for divisor, residues in rules
                if x % divisor in residues and value % divisor == 0 and divisor < value
            ]
            if congruence_witnesses:
                continue
            self.assertIn(x, factors)
            self.assertEqual(value % factors[x], 0)
            self.assertGreater(factors[x], 1)
            self.assertLess(factors[x], value)
        self.assertTrue(any(1 % d in residues for d, residues in rules))

    def test_2730_filter_is_derived_and_not_a_hard_coded_exemption(self) -> None:
        rules = self.baseline["composite_cover_rules"]
        self.assertEqual([int(rule["divisor"]) for rule in rules], [2, 3, 5, 7, 13])
        self.assertEqual(
            [entry["x"] for entry in self.baseline["explicit_factors"]],
            list(range(2730, 616980, 2730)),
        )

        missing_rule = copy.deepcopy(self.baseline)
        missing_rule["composite_cover_rules"] = missing_rule["composite_cover_rules"][1:]
        self.assert_rejected(missing_rule, "INCOMPLETE_COMPOSITE_COVERAGE")

        false_rule = copy.deepcopy(self.baseline)
        false_rule["composite_cover_rules"][-1]["residues"][0] = 0
        self.assert_rejected(false_rule, "FALSE_CONGRUENCE_RULE")

    def test_factor_sequence_is_complete_canonical_and_exact(self) -> None:
        missing = copy.deepcopy(self.baseline)
        missing["explicit_factors"].pop()
        self.assert_rejected(missing, "INCOMPLETE_COMPOSITE_COVERAGE")

        swapped = copy.deepcopy(self.baseline)
        swapped["explicit_factors"][0], swapped["explicit_factors"][1] = (
            swapped["explicit_factors"][1],
            swapped["explicit_factors"][0],
        )
        self.assert_rejected(swapped, "NONCANONICAL_FACTOR_SEQUENCE")

        false_factor = copy.deepcopy(self.baseline)
        false_factor["explicit_factors"][0]["factor"] = "18"
        self.assert_rejected(false_factor, "FALSE_COMPOSITE_FACTOR")

    def test_ecpp_chain_and_mutations_are_checked_not_trusted(self) -> None:
        expected_prime = 616980**12 + 488669
        steps = self.baseline["primality_certificate"]["steps"]
        self.assertEqual(CHECKER.verify_ecpp(
            self.baseline["primality_certificate"], expected_prime
        ), 6)
        self.assertLess(
            (int(steps[-1]["n"]) + 1 - int(steps[-1]["trace"]))
            // int(steps[-1]["s"]),
            2**64,
        )

        wrong_target = copy.deepcopy(self.baseline)
        wrong_target["primality_certificate"]["steps"][0]["n"] = str(
            expected_prime + 2
        )
        self.assert_rejected(wrong_target, "ECPP_TARGET_MISMATCH")

        wrong_trace = copy.deepcopy(self.baseline)
        trace = int(wrong_trace["primality_certificate"]["steps"][1]["trace"])
        wrong_trace["primality_certificate"]["steps"][1]["trace"] = str(trace + 1)
        trace_result = CHECKER.evaluate_document(
            wrong_trace,
            expected_schema=CHECKER.BASELINE_SCHEMA,
            minimum_first_prime_x=CHECKER.BASELINE_FIRST_PRIME_X,
        )
        self.assertFalse(trace_result["accepted"])
        self.assertTrue(trace_result["reason_code"].startswith("ECPP_"))

        wrong_point = copy.deepcopy(self.baseline)
        # With a=0, the point (0,0) derives b=0 and hence the singular
        # discriminant zero.  This is a deterministic invalid-curve mutation;
        # an arbitrary coordinate perturbation could accidentally describe a
        # different valid certificate because b is derived from the point.
        wrong_point["primality_certificate"]["steps"][2]["point_x"] = "0"
        wrong_point["primality_certificate"]["steps"][2]["point_y"] = "0"
        result = CHECKER.evaluate_document(
            wrong_point,
            expected_schema=CHECKER.BASELINE_SCHEMA,
            minimum_first_prime_x=CHECKER.BASELINE_FIRST_PRIME_X,
        )
        self.assertFalse(result["accepted"])
        self.assertTrue(result["reason_code"].startswith("ECPP_"))

    def test_terminal_u64_primality_checker_matches_small_reference(self) -> None:
        for n in range(10_000):
            self.assertEqual(CHECKER._is_prime_u64(n), trial_prime(n), n)
        for composite in (
            341550071728321,
            3825123056546413051,
            2**64 - 1,
        ):
            self.assertFalse(CHECKER._is_prime_u64(composite))
        self.assertTrue(CHECKER._is_prime_u64(18446744073709551557))

    def test_affine_scalar_arithmetic_matches_repeated_addition_on_small_curves(self) -> None:
        # Independent tiny-domain property check of the scalar routine used by
        # ECPP.  Only nonsingular curves and actual points are sampled.
        for prime in (101, 103, 107):
            for curve_a in (0, 1, 7):
                for curve_b in (1, 2, 9):
                    if (4 * curve_a**3 + 27 * curve_b**2) % prime == 0:
                        continue
                    points = [
                        (x, y)
                        for x in range(prime)
                        for y in range(prime)
                        if (y * y - x**3 - curve_a * x - curve_b) % prime == 0
                    ][:4]
                    for point in points:
                        repeated = None
                        for multiplier in range(1, 20):
                            repeated = CHECKER._point_add(
                                repeated, point, prime, curve_a
                            )
                            self.assertEqual(
                                CHECKER._scalar_multiply(
                                    multiplier, point, prime, curve_a
                                ),
                                repeated,
                            )

    def test_parser_and_file_boundary_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            duplicate = directory / "duplicate.json"
            duplicate.write_bytes(b'{"schema":"x","schema":"y"}\n')
            self.assertEqual(
                CHECKER.evaluate_path(duplicate)["reason_code"],
                "DUPLICATE_JSON_KEY",
            )

            floating = directory / "float.json"
            floating.write_bytes(b'{"x":1.5}\n')
            self.assertEqual(
                CHECKER.evaluate_path(floating)["reason_code"],
                "NON_INTEGER_NUMBER",
            )

            huge_integer = directory / "huge.json"
            huge_integer.write_bytes(b'{"x":12345678901234567890}\n')
            self.assertEqual(
                CHECKER.evaluate_path(huge_integer)["reason_code"],
                "INTEGER_OUT_OF_RANGE",
            )

            link = directory / "link.json"
            link.symlink_to(self.baseline_path)
            self.assertEqual(
                CHECKER.evaluate_path(link)["reason_code"], "INPUT_NOT_REGULAR"
            )

            fifo = directory / "candidate.fifo"
            os.mkfifo(fifo)
            self.assertEqual(
                CHECKER.evaluate_path(fifo)["reason_code"], "INPUT_NOT_REGULAR"
            )

            oversize = directory / "oversize.json"
            with oversize.open("wb") as stream:
                stream.truncate(CHECKER.MAXIMUM_INPUT_BYTES + 1)
            self.assertEqual(
                CHECKER.evaluate_path(oversize)["reason_code"], "INPUT_TOO_LARGE"
            )

    def test_cli_has_stable_machine_result_and_no_stderr(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-I", str(VERIFIER / "check.py"), str(self.baseline_path)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=ROOT,
            env={
                "LANG": "C",
                "LC_ALL": "C",
                "PATH": "/usr/bin:/bin",
                "PYTHONHASHSEED": "0",
            },
            check=False,
            timeout=30,
        )
        self.assertEqual(completed.returncode, 1)
        self.assertFalse(completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(result["reason_code"], "INVALID_SCHEMA")
        self.assertEqual(result["verifier_id"], CHECKER.VERIFIER_ID)


if __name__ == "__main__":
    unittest.main()
