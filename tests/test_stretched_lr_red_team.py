from __future__ import annotations

from fractions import Fraction
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "verifiers" / "amf.stretched-lr.exact.v1"
TARGET = ROOT / "targets" / "frontier-stretched-lr"

import sys

sys.path.insert(0, str(ROOT / "scripts"))
from contracts import ContractError, load_json, validate_verifier_manifest  # noqa: E402


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PRIMARY = load_module("red_lr_primary", VERIFIER / "primary.py")
SECONDARY = load_module("red_lr_secondary", VERIFIER / "secondary.py")
DISPATCH = load_module("red_lr_dispatch", VERIFIER / "dispatch.py")


def partitions(total: int, largest: int | None = None):
    if total == 0:
        yield ()
        return
    ceiling = min(total, largest if largest is not None else total)
    for first in range(ceiling, 0, -1):
        for rest in partitions(total - first, first):
            yield (first,) + rest


def brute_lr(
    outer: tuple[int, ...],
    inner: tuple[int, ...],
    content: tuple[int, ...],
) -> int:
    """Independent cell-by-cell LR tableau enumeration for small cases."""

    rows = max(len(outer), len(inner))
    padded_outer = outer + (0,) * (rows - len(outer))
    padded_inner = inner + (0,) * (rows - len(inner))
    if (
        any(padded_inner[row] > padded_outer[row] for row in range(rows))
        or sum(padded_outer) - sum(padded_inner) != sum(content)
    ):
        return 0
    cells = [
        (row, column)
        for row in range(rows)
        for column in range(padded_outer[row] - 1, padded_inner[row] - 1, -1)
    ]
    tableau: dict[tuple[int, int], int] = {}
    used = [0] * len(content)
    answer = 0

    def visit(index: int) -> None:
        nonlocal answer
        if index == len(cells):
            answer += int(tuple(used) == content)
            return
        row, column = cells[index]
        right = tableau.get((row, column + 1))
        above = tableau.get((row - 1, column))
        for entry in range(1, len(content) + 1):
            slot = entry - 1
            if used[slot] >= content[slot]:
                continue
            if right is not None and entry > right:
                continue
            if above is not None and entry <= above:
                continue
            used[slot] += 1
            if all(used[position] >= used[position + 1] for position in range(len(used) - 1)):
                tableau[(row, column)] = entry
                visit(index + 1)
                del tableau[(row, column)]
            used[slot] -= 1

    visit(0)
    return answer


def rational_documents(coefficients: list[int]) -> list[dict[str, int]]:
    return [{"numerator": value, "denominator": 1} for value in coefficients]


def candidate(coefficients: list[int], values: list[int]) -> dict[str, object]:
    return {
        "schema": PRIMARY.CANDIDATE_SCHEMA,
        "lr_convention": PRIMARY.LR_CONVENTION,
        "polynomial_basis": PRIMARY.POLYNOMIAL_BASIS,
        "sample_domain": PRIMARY.SAMPLE_DOMAIN,
        "lambda": [3, 2, 1],
        "mu": [2, 1],
        "nu": [2, 1],
        "coefficients": rational_documents(coefficients),
        "values_t_1_through_29": values,
    }


def fake_checker(path: Path, checker: str, output: dict[str, object], code: int) -> None:
    payload = {**output, "checker": checker}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    path.write_text(
        f"print({encoded!r})\nraise SystemExit({code})\n", encoding="ascii"
    )


class StretchedLRRedTeamTests(unittest.TestCase):
    def test_corpus_is_target_bound_and_case_ids_are_unique(self) -> None:
        corpus = load_json(
            TARGET / "evidence" / "red-team" / "corpus-codex-2026-08-14.json"
        )
        self.assertEqual(corpus["problem_id"], "frontier-stretched-lr")
        ids = [case["id"] for case in corpus["cases"]]
        self.assertEqual(len(ids), 14)
        self.assertEqual(len(ids), len(set(ids)))

    def test_4993_small_triples_match_third_cell_enumerator(self) -> None:
        checked = 0
        for outer_size in range(2, 9):
            for outer in partitions(outer_size):
                for inner_size in range(1, outer_size):
                    for inner in partitions(inner_size):
                        for content in partitions(outer_size - inner_size):
                            expected = brute_lr(outer, inner, content)
                            primary = PRIMARY.lr_coefficient_tableaux(
                                outer,
                                inner,
                                content,
                                budget=PRIMARY.WorkBudget(200_000),
                            )
                            secondary = SECONDARY.lr_coefficient_jacobi_trudi_pieri(
                                outer,
                                inner,
                                content,
                                budget=SECONDARY.Counter(200_000),
                            )
                            self.assertEqual((primary, secondary), (expected, expected))
                            checked += 1
        self.assertEqual(checked, 4_993)

    def test_role_order_and_non_skew_shapes_do_not_false_accept(self) -> None:
        valid = ((3, 2, 1), (2, 1), (2, 1))
        wrong = ((2, 1), (3, 2, 1), (2, 1))
        self.assertEqual(brute_lr(*valid), 2)
        self.assertEqual(brute_lr(*wrong), 0)
        for checker, budget in (
            (PRIMARY.lr_coefficient_tableaux, PRIMARY.WorkBudget(50_000)),
            (SECONDARY.lr_coefficient_jacobi_trudi_pieri, SECONDARY.Counter(50_000)),
        ):
            self.assertEqual(checker(*valid, budget=budget), 2)

    def test_degree_29_vanishing_alias_is_rejected_before_oracle_work(self) -> None:
        # Q(t)=prod(t-i), i=1..29, vanishes at every supplied sample.  Thus
        # t+1+Q(t) aliases t+1 on the sample domain and has negative terms,
        # but its degree 29 is outside the frozen degree-at-most-28 envelope.
        vanishing = [1]
        for root in range(1, 30):
            next_coefficients = [0] * (len(vanishing) + 1)
            for degree, coefficient in enumerate(vanishing):
                next_coefficients[degree] -= root * coefficient
                next_coefficients[degree + 1] += coefficient
            vanishing = next_coefficients
        vanishing[0] += 1
        vanishing[1] += 1
        self.assertEqual(len(vanishing), 30)
        self.assertTrue(any(value < 0 for value in vanishing))
        self.assertEqual(
            [sum(c * t**d for d, c in enumerate(vanishing)) for t in range(1, 30)],
            list(range(2, 31)),
        )
        attack = candidate(vanishing, list(range(2, 31)))
        for checker in (PRIMARY, SECONDARY):
            result, infrastructure = checker.evaluate_document_with_status(attack)
            self.assertFalse(infrastructure)
            self.assertFalse(result["accepted"])
            self.assertEqual(result["reason_code"], "INVALID_DOCUMENT")

    def test_rational_and_polynomial_canonicalization_attacks(self) -> None:
        base = candidate([-1, 1], list(range(29)))
        mutations = []
        unreduced = json.loads(json.dumps(base))
        unreduced["coefficients"][0] = {"numerator": -2, "denominator": 2}
        mutations.append((unreduced, "NONCANONICAL_RATIONAL"))
        trailing = json.loads(json.dumps(base))
        trailing["coefficients"].append({"numerator": 0, "denominator": 1})
        mutations.append((trailing, "NONCANONICAL_POLYNOMIAL"))
        negative_sample = json.loads(json.dumps(base))
        negative_sample["values_t_1_through_29"][0] = -1
        mutations.append((negative_sample, "INVALID_DOCUMENT"))
        wrong_size = json.loads(json.dumps(base))
        wrong_size["nu"] = [1]
        mutations.append((wrong_size, "SIZE_RELATION"))
        for value, reason in mutations:
            for checker in (PRIMARY, SECONDARY):
                result = checker.evaluate_document(value)
                self.assertEqual(result["reason_code"], reason)

    def test_duplicate_and_noninteger_json_fail_closed(self) -> None:
        payloads = (
            b'{"schema":"x","schema":"y"}\n',
            b'{"schema":"x","values_t_1_through_29":[1.0]}\n',
        )
        with tempfile.TemporaryDirectory() as directory:
            for index, payload in enumerate(payloads):
                path = Path(directory) / f"attack-{index}.json"
                path.write_bytes(payload)
                result, infrastructure = DISPATCH.dispatch_path(path)
                self.assertFalse(infrastructure)
                self.assertFalse(result["accepted"])
                self.assertEqual(result["reason_code"], "INVALID_JSON")

    def test_operation_ceiling_and_checker_exit_two_remain_inconclusive(self) -> None:
        forged = candidate([-1, 1], list(range(29)))
        for checker in (PRIMARY, SECONDARY):
            result, infrastructure = checker.evaluate_document_with_status(
                forged, operation_limit=1
            )
            self.assertTrue(infrastructure)
            self.assertEqual(result["reason_code"], "COMPUTATION_LIMIT")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "candidate.json"
            path.write_bytes(json.dumps(forged).encode() + b"\n")
            blank = DISPATCH._result(False, "COMPUTATION_LIMIT")
            first = root / "first.py"
            second = root / "second.py"
            fake_checker(first, DISPATCH.PRIMARY_ID, blank, 2)
            fake_checker(second, DISPATCH.SECONDARY_ID, blank, 2)
            result, infrastructure = DISPATCH.dispatch_path(
                path, primary_path=first, secondary_path=second
            )
        self.assertTrue(infrastructure)
        self.assertEqual(result["reason_code"], "CHECKER_INFRASTRUCTURE_FAILURE")

    def test_forged_accepted_facts_are_rejected_by_output_protocol(self) -> None:
        forged = candidate([-1, 1], list(range(29)))
        facts = {
            "coefficients_sha256": "A" * 64,
            "degree_bound": 6,
            "first_negative_degree": 0,
            "interpolation_points": 29,
            "lambda": [3, 2, 1],
            "lambda_size": 6,
            "mu": [2, 1],
            "mu_size": 3,
            "nu": [2, 1],
            "nu_size": 3,
            "sample_values_sha256": "0" * 64,
        }
        output = DISPATCH._result(True, "ACCEPTED", facts)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "candidate.json"
            path.write_bytes(json.dumps(forged).encode() + b"\n")
            first = root / "first.py"
            second = root / "second.py"
            fake_checker(first, DISPATCH.PRIMARY_ID, output, 0)
            fake_checker(second, DISPATCH.SECONDARY_ID, output, 0)
            result, infrastructure = DISPATCH.dispatch_path(
                path, primary_path=first, secondary_path=second
            )
        self.assertTrue(infrastructure)
        self.assertEqual(result["reason_code"], "CHECKER_INVALID_OUTPUT")

    def test_manifest_detects_source_drift_and_symlink_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            copied = root / "verifiers" / "amf.stretched-lr.exact.v1"
            copied.parent.mkdir(parents=True)
            shutil.copytree(VERIFIER, copied)
            manifest = load_json(copied / "manifest.json")
            validate_verifier_manifest(
                manifest, root=root, expected_verifier_id=DISPATCH.VERIFIER_ID
            )
            primary = copied / "primary.py"
            primary.write_bytes(primary.read_bytes() + b"\n")
            with self.assertRaisesRegex(ContractError, "binding .*mismatch"):
                validate_verifier_manifest(
                    manifest, root=root, expected_verifier_id=DISPATCH.VERIFIER_ID
                )
            shutil.copy2(VERIFIER / "primary.py", primary)
            primary.unlink()
            primary.symlink_to(copied / "secondary.py")
            with self.assertRaisesRegex(ContractError, "non-symlink"):
                validate_verifier_manifest(
                    manifest, root=root, expected_verifier_id=DISPATCH.VERIFIER_ID
                )


if __name__ == "__main__":
    unittest.main()
