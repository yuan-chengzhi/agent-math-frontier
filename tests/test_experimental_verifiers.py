from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = ROOT / "verifiers" / "amf.experimental-finite.v1" / "check.py"
SPEC = importlib.util.spec_from_file_location("amf_experimental_checker", CHECKER_PATH)
assert SPEC is not None and SPEC.loader is not None
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)


class ExperimentalVerifierTests(unittest.TestCase):
    def result(self, profile: str, document: object) -> dict[str, object]:
        result, apparatus = CHECKER.evaluate_document(profile, document)
        self.assertFalse(apparatus)
        return result

    def test_profiles_match_the_ten_new_verifiers(self) -> None:
        self.assertEqual(
            set(CHECKER.CHECKERS),
            {
                "book-range100",
                "cage3g13",
                "costas32",
                "diophantine-eq1",
                "erdos23-oddcycle",
                "erdos307",
                "erdos7-cover",
                "erdos835-k10",
                "r55-graph43",
                "srg692075",
            },
        )
        for profile in CHECKER.CHECKERS:
            result = self.result(profile, {})
            self.assertFalse(result["accepted"], profile)
            self.assertEqual(result["reason_code"], "INVALID_DOCUMENT", profile)

    def test_strict_json_rejects_duplicates_and_floats(self) -> None:
        with self.assertRaisesRegex(CHECKER.CandidateFailure, "DUPLICATE_JSON_KEY"):
            CHECKER.decode_document(b'{"schema":"x","schema":"y"}')
        with self.assertRaisesRegex(CHECKER.CandidateFailure, "NON_INTEGER_NUMBER"):
            CHECKER.decode_document(b'{"x":1.0}')

    def test_deterministic_u64_primality_rejects_a_strong_pseudoprime(self) -> None:
        self.assertTrue(CHECKER._is_prime_u64(18_446_744_073_709_551_557))
        self.assertFalse(CHECKER._is_prime_u64(341_550_071_728_321))

    def test_erdos307_checks_primality_before_the_exact_identity(self) -> None:
        composite = self.result("erdos307", {
            "schema": "AMF_ERDOS307_RECIPROCAL_PRIMES_1",
            "P": ["4"],
            "Q": ["2"],
            "prime_certificates": [],
        })
        self.assertEqual(composite["reason_code"], "NONPRIME_ENTRY")
        false_identity = self.result("erdos307", {
            "schema": "AMF_ERDOS307_RECIPROCAL_PRIMES_1",
            "P": ["2"],
            "Q": ["2"],
            "prime_certificates": [],
        })
        self.assertEqual(false_identity["reason_code"], "RATIONAL_IDENTITY_FALSE")

    def test_erdos835_rejects_a_monochromatic_complete_table(self) -> None:
        result = self.result("erdos835-k10", {
            "schema": "AMF_ERDOS835_K10_COLORING_1",
            "k": 10,
            "colors": [0] * 184_756,
        })
        self.assertEqual(result["reason_code"], "MISSING_COLOR_IN_11_SUBSET")

    def test_erdos23_rejects_reusing_one_cycle_as_two_certificates(self) -> None:
        cycle_edges = [[0, 1], [1, 2], [2, 3], [3, 4], [0, 4]]
        result = self.result("erdos23-oddcycle", {
            "schema": "AMF_ERDOS23_ODD_CYCLE_COUNTEREXAMPLE_1",
            "n_parameter": 1,
            "edges": cycle_edges,
            "odd_cycles": [[0, 1, 2, 3, 4], [0, 1, 2, 3, 4]],
        })
        self.assertEqual(result["reason_code"], "ODD_CYCLES_NOT_EDGE_DISJOINT")

    def test_erdos7_rejects_an_uncovered_residue(self) -> None:
        result = self.result("erdos7-cover", {
            "schema": "AMF_ERDOS7_ODD_COVER_1",
            "classes": [
                {"residue": 0, "modulus": 3},
                {"residue": 1, "modulus": 5},
            ],
        })
        self.assertEqual(result["reason_code"], "UNCOVERED_RESIDUE")

    def test_r55_checks_the_complement(self) -> None:
        result = self.result("r55-graph43", {
            "schema": "AMF_R55_GRAPH43_1",
            "n": 43,
            "edges": [],
        })
        self.assertEqual(result["reason_code"], "FIVE_INDEPENDENT_SET_FOUND")

    def test_book_adjacency_order_matches_the_published_example(self) -> None:
        adjacency = CHECKER._adjacency_from_column_major("011010", 4)
        observed = {
            (left, right)
            for right in range(1, 4)
            for left in range(right)
            if adjacency[left] & (1 << right)
        }
        self.assertEqual(observed, {(0, 2), (1, 2), (1, 3)})

    def test_diophantine_uses_exact_big_integer_substitution(self) -> None:
        huge = str(10**51)
        result = self.result("diophantine-eq1", {
            "schema": "AMF_SMALL_DIOPHANTINE_EQ1_1",
            "equation_id": "z2+y2z+x3-2",
            "solutions": [
                {"x": huge, "y": "0", "z": "0"},
                {"x": str(10**51 + 1), "y": "0", "z": "0"},
                {"x": str(10**51 + 2), "y": "0", "z": "0"},
            ],
        })
        self.assertEqual(result["reason_code"], "EQUATION_FALSE")

    def test_cage_girth_helper_detects_the_boundary(self) -> None:
        cycle13 = [0] * 13
        for vertex in range(13):
            neighbor = (vertex + 1) % 13
            cycle13[vertex] |= 1 << neighbor
            cycle13[neighbor] |= 1 << vertex
        self.assertEqual(CHECKER._girth(cycle13, cutoff=13), 13)
        cycle12 = [0] * 12
        for vertex in range(12):
            neighbor = (vertex + 1) % 12
            cycle12[vertex] |= 1 << neighbor
            cycle12[neighbor] |= 1 << vertex
        self.assertEqual(CHECKER._girth(cycle12, cutoff=13), 12)

    def test_srg_rejects_wrong_degree_and_costas_rejects_identity(self) -> None:
        srg = self.result("srg692075", {
            "schema": "AMF_SRG_69_20_7_5_GRAPH_1",
            "n": 69,
            "edges": [],
        })
        self.assertEqual(srg["reason_code"], "INVALID_DEGREE")
        costas = self.result("costas32", {
            "schema": "AMF_COSTAS32_PERMUTATION_1",
            "order": 32,
            "permutation": list(range(1, 33)),
        })
        self.assertEqual(costas["reason_code"], "DUPLICATE_DISPLACEMENT")


if __name__ == "__main__":
    unittest.main()
