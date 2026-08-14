from __future__ import annotations

import copy
import importlib.util
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "verifiers" / "amf.aim60.certificate.v1"
TARGET = ROOT / "targets" / "aim-60-first-prime"
BASELINE_PATH = TARGET / "evidence" / "baseline" / "baseline-certificate.json"

sys.path.insert(0, str(ROOT / "scripts"))
from contracts import ContractError, load_json, validate_verifier_manifest  # noqa: E402


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CHECKER = load_module("red_aim60", VERIFIER / "check.py")


class Aim60RedTeamTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.baseline = load_json(BASELINE_PATH)

    def baseline_result(self, value: object) -> tuple[dict[str, object], bool]:
        return CHECKER.evaluate_document_with_status(
            value,
            expected_schema=CHECKER.BASELINE_SCHEMA,
            minimum_first_prime_x=CHECKER.BASELINE_FIRST_PRIME_X,
        )

    def test_corpus_is_target_bound_and_case_ids_are_unique(self) -> None:
        corpus = load_json(
            TARGET / "evidence" / "red-team" / "corpus-codex-2026-08-14.json"
        )
        self.assertEqual(corpus["problem_id"], "aim-60-first-prime")
        ids = [case["id"] for case in corpus["cases"]]
        self.assertEqual(len(ids), 15)
        self.assertEqual(len(ids), len(set(ids)))

    def test_cover_requires_a_strictly_smaller_divisor(self) -> None:
        covered, count = CHECKER._validate_cover_rules(
            [{"divisor": "16", "residues": [1]}],
            a=15,
            first_prime_x=18,
        )
        self.assertEqual(count, 1)
        self.assertEqual(covered[1], 0)  # 1^12+15 equals 16: not composite evidence.
        self.assertEqual(covered[17], 1)
        self.assertEqual((17**12 + 15) % 16, 0)
        self.assertLess(16, 17**12 + 15)

    def test_residue_zero_never_introduces_x_zero(self) -> None:
        covered, _ = CHECKER._validate_cover_rules(
            [{"divisor": "2", "residues": [0]}],
            a=2,
            first_prime_x=8,
        )
        self.assertEqual(covered[0], 0)
        self.assertEqual([index for index in range(1, 8) if covered[index]], [2, 4, 6])

    def test_overlap_does_not_change_exact_uncovered_set(self) -> None:
        a = int(self.baseline["a"])
        first = 1_000
        rules = self.baseline["composite_cover_rules"]
        covered, _ = CHECKER._validate_cover_rules(rules, a=a, first_prime_x=first)
        expected = []
        for x in range(1, first):
            witnesses = [
                int(rule["divisor"])
                for rule in rules
                if x % int(rule["divisor"]) in rule["residues"]
                and (x**12 + a) % int(rule["divisor"]) == 0
                and int(rule["divisor"]) < x**12 + a
            ]
            self.assertEqual(bool(covered[x]), bool(witnesses), x)
            if not witnesses:
                expected.append(x)
        self.assertEqual(expected, [x for x in range(1, first) if not covered[x]])

    def test_explicit_factor_must_be_nontrivial_and_proper(self) -> None:
        uncovered = bytearray(2)
        self.assertEqual(
            CHECKER._validate_explicit_factors(
                [{"x": 1, "factor": "2"}], a=3, first_prime_x=2, covered=uncovered
            ),
            1,
        )
        for factor in ("1", "4"):
            with self.subTest(factor=factor), self.assertRaisesRegex(
                CHECKER.CheckFailure, "FALSE_COMPOSITE_FACTOR"
            ):
                CHECKER._validate_explicit_factors(
                    [{"x": 1, "factor": factor}],
                    a=3,
                    first_prime_x=2,
                    covered=uncovered,
                )

    def test_noncanonical_decimal_and_bool_attacks_fail_closed(self) -> None:
        mutations = []
        leading_zero = copy.deepcopy(self.baseline)
        leading_zero["a"] = "0488669"
        mutations.append(leading_zero)
        plus_factor = copy.deepcopy(self.baseline)
        plus_factor["explicit_factors"][0]["factor"] = "+17"
        mutations.append(plus_factor)
        negative_zero_trace = copy.deepcopy(self.baseline)
        negative_zero_trace["primality_certificate"]["steps"][0]["trace"] = "-0"
        mutations.append(negative_zero_trace)
        boolean_index = copy.deepcopy(self.baseline)
        boolean_index["first_prime_x"] = True
        mutations.append(boolean_index)
        for value in mutations:
            result, infrastructure = self.baseline_result(value)
            self.assertFalse(infrastructure)
            self.assertFalse(result["accepted"])

    def test_ecpp_chain_q_bound_and_nonunit_attacks(self) -> None:
        broken = copy.deepcopy(self.baseline["primality_certificate"])
        broken["steps"][1]["n"] = str(int(broken["steps"][1]["n"]) + 2)
        with self.assertRaisesRegex(CHECKER.CheckFailure, "ECPP_CHAIN_MISMATCH"):
            CHECKER.verify_ecpp(
                broken, 616980**12 + 488669
            )

        n = 2**64 + 13
        order = n + 1
        too_small_q = {
            "kind": "ATKIN_MORAIN_ECPP_1",
            "steps": [{
                "n": str(n),
                "trace": "0",
                "s": str(order),
                "curve_a": "0",
                "point_x": "0",
                "point_y": "1",
            }],
        }
        with self.assertRaisesRegex(CHECKER.CheckFailure, "ECPP_Q_BOUND"):
            CHECKER.verify_ecpp(too_small_q, n)

        with self.assertRaisesRegex(CHECKER.CheckFailure, "ECPP_NONUNIT_ARITHMETIC"):
            CHECKER._point_add((0, 1), (5, 2), 15, 0)

    def test_terminal_primality_rejects_known_strong_pseudoprimes(self) -> None:
        for composite in (
            3_474_749_660_383,
            341_550_071_728_321,
            3_825_123_056_546_413_051,
            2**64 - 1,
        ):
            self.assertFalse(CHECKER._is_prime_u64(composite), composite)
        self.assertTrue(CHECKER._is_prime_u64(18_446_744_073_709_551_557))

    def test_memory_and_cover_ceiling_are_apparatus_not_rejections(self) -> None:
        with mock.patch.object(
            CHECKER, "_validate_cover_rules", side_effect=MemoryError
        ):
            result, infrastructure = self.baseline_result(self.baseline)
        self.assertTrue(infrastructure)
        self.assertEqual(result["reason_code"], "RESOURCE_FAILURE")

        with mock.patch.object(CHECKER, "MAXIMUM_COVER_OPERATIONS", 0):
            result, infrastructure = self.baseline_result(self.baseline)
        self.assertTrue(infrastructure)
        self.assertEqual(result["reason_code"], "COVER_OPERATION_LIMIT")

    def test_cli_emits_exit_two_for_operation_ceiling(self) -> None:
        attack = copy.deepcopy(self.baseline)
        attack["schema"] = CHECKER.CANDIDATE_SCHEMA
        attack["first_prime_x"] = CHECKER.MINIMUM_IMPROVEMENT_X
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "candidate.json"
            path.write_text(json.dumps(attack), encoding="ascii")
            script = (
                "import importlib.util,sys\n"
                f"p={str(VERIFIER / 'check.py')!r}\n"
                "s=importlib.util.spec_from_file_location('aim_cli_red',p)\n"
                "m=importlib.util.module_from_spec(s);s.loader.exec_module(m)\n"
                "m.MAXIMUM_COVER_OPERATIONS=0\n"
                f"raise SystemExit(m.main(['check.py',{str(path)!r}]))\n"
            )
            completed = subprocess.run(
                [sys.executable, "-I", "-c", script],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=10,
            )
        self.assertEqual(completed.returncode, 2)
        self.assertFalse(completed.stderr)
        output = json.loads(completed.stdout)
        self.assertFalse(output["accepted"])
        self.assertEqual(output["reason_code"], "COVER_OPERATION_LIMIT")

    def test_manifest_detects_source_drift_and_symlink_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            copied = root / "verifiers" / "amf.aim60.certificate.v1"
            copied.parent.mkdir(parents=True)
            shutil.copytree(VERIFIER, copied)
            manifest = load_json(copied / "manifest.json")
            validate_verifier_manifest(
                manifest, root=root, expected_verifier_id=CHECKER.VERIFIER_ID
            )
            checker = copied / "check.py"
            checker.write_bytes(checker.read_bytes() + b"\n")
            with self.assertRaisesRegex(ContractError, "binding .*mismatch"):
                validate_verifier_manifest(
                    manifest, root=root, expected_verifier_id=CHECKER.VERIFIER_ID
                )
            checker.unlink()
            checker.symlink_to(copied / "manifest.json")
            with self.assertRaisesRegex(ContractError, "non-symlink"):
                validate_verifier_manifest(
                    manifest, root=root, expected_verifier_id=CHECKER.VERIFIER_ID
                )


if __name__ == "__main__":
    unittest.main()
