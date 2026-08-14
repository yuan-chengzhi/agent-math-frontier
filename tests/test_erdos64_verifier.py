from __future__ import annotations

from itertools import combinations, permutations
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "verifiers" / "amf.erdos64.counterexample.v1"
TARGET = ROOT / "targets" / "erdos-64"
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


CHECKER = load_module("amf_erdos64_checker", VERIFIER / "checker.py")


def candidate(n: int, edges: list[list[int]]) -> dict[str, object]:
    return {
        "edges": edges,
        "kind": "graph_counterexample",
        "n": n,
        "schema": CHECKER.CANDIDATE_SCHEMA,
    }


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii") + b"\n"


def adjacency_of(n: int, edges: list[list[int]]) -> list[tuple[int, ...]]:
    rows = [[] for _ in range(n)]
    for left, right in edges:
        rows[left].append(right)
        rows[right].append(left)
    return [tuple(sorted(row)) for row in rows]


def reference_cycle(n: int, edges: list[list[int]], length: int) -> list[int] | None:
    """Independent brute-force reference for small property tests."""

    edge_set = {tuple(edge) for edge in edges}

    def adjacent(left: int, right: int) -> bool:
        return (min(left, right), max(left, right)) in edge_set

    for vertices in combinations(range(n), length):
        start = vertices[0]
        for tail in permutations(vertices[1:]):
            path = (start,) + tail
            if all(adjacent(path[index], path[(index + 1) % length]) for index in range(length)):
                return list(path)
    return None


class Erdos64VerifierTests(unittest.TestCase):
    def write_candidate(self, directory: Path, value: object) -> Path:
        path = directory / "candidate.json"
        path.write_bytes(canonical_bytes(value))
        return path

    def test_registered_manifest_and_frozen_target_obey_contract(self) -> None:
        registry = validate_verifier_registry(
            load_json(ROOT / "data" / "verifiers.json"), root=ROOT
        )
        self.assertIn(CHECKER.VERIFIER_ID, registry)
        manifest = registry[CHECKER.VERIFIER_ID]["manifest_value"]
        self.assertEqual(
            manifest["binds_verification_mode"],
            "exact_bounded_graph_counterexample_checker",
        )

        catalog = load_json(ROOT / "data" / "problems.json")
        problem = next(item for item in catalog["problems"] if item["id"] == "erdos-64")
        self.assertEqual(problem["stage"], "active")
        self.assertEqual(problem["verification"]["mode"], manifest["binds_verification_mode"])
        card = validate_target_card(
            load_json(TARGET / "target-card.json"),
            root=ROOT,
            expected_problem_id=problem["id"],
            expected_problem_card_sha256=canonical_sha256(problem),
            expected_source_revision=problem["formalization"]["revision"],
        )
        self.assertEqual(card["claim_scope"], "FULL_PROBLEM")
        self.assertEqual(card["verifier_id"], CHECKER.VERIFIER_ID)

    def test_formal_statement_snapshot_and_route_baseline_are_exactly_pinned(self) -> None:
        source = TARGET / "evidence" / "sources" / "FormalConjectures-Erdos64-b33d8678.lean"
        raw = source.read_bytes()
        self.assertEqual(len(raw), 1177)
        self.assertEqual(
            hashlib.sha256(raw).hexdigest(),
            "36b7a400cd21197e602deb279c771cbf7b6e13ce3d070c6276848b23d00b981a",
        )
        metadata = load_json(TARGET / "evidence" / "baseline" / "source-metadata.json")
        self.assertEqual(
            metadata["formal_statement"]["revision"],
            "b33d8678a28118c95d8d4f60b11faaf39ccff1e6",
        )
        self.assertEqual(metadata["formal_statement"]["local_snapshot_bytes"], len(raw))
        self.assertEqual(
            metadata["formal_statement"]["local_snapshot_sha256"],
            hashlib.sha256(raw).hexdigest(),
        )
        baseline_ids = {item["id"] for item in metadata["known_route_baselines"]}
        self.assertEqual(
            baseline_ids,
            {
                "p13-free-v2",
                "minimal-counterexample-structure-v1",
                "finite-sat-through-31",
                "cubic-bipartite-through-58-v1",
                "p13-free-code",
            },
        )

    def test_known_small_cubic_graphs_are_rejected_with_real_cycle_witnesses(self) -> None:
        k4_edges = [[left, right] for left in range(4) for right in range(left + 1, 4)]
        k4 = CHECKER.evaluate_document(candidate(4, k4_edges))
        self.assertFalse(k4["accepted"])
        self.assertEqual(k4["reason_code"], "POWER_OF_TWO_CYCLE_FOUND")
        self.assertEqual(len(k4["facts"]["cycle_witness"]), 4)

        # Petersen graph: outer 5-cycle, inner pentagram, and five spokes.
        petersen_edges = [
            [0, 1], [0, 4], [0, 5], [1, 2], [1, 6], [2, 3], [2, 7],
            [3, 4], [3, 8], [4, 9], [5, 7], [5, 8], [6, 8], [6, 9], [7, 9],
        ]
        petersen = CHECKER.evaluate_document(candidate(10, petersen_edges))
        self.assertFalse(petersen["accepted"])
        self.assertEqual(petersen["reason_code"], "POWER_OF_TWO_CYCLE_FOUND")
        witness = petersen["facts"]["cycle_witness"]
        self.assertIn(len(witness), (4, 8))
        self.assertIsNotNone(reference_cycle(10, petersen_edges, len(witness)))

    def test_acceptance_path_is_exercised_only_through_an_explicit_test_seam(self) -> None:
        # C5 has no 4-cycle, so it exercises exhaustive acceptance when the
        # production degree threshold is deliberately relaxed inside this test.
        edges = [[vertex, (vertex + 1) % 5] for vertex in range(4)] + [[0, 4]]
        edges = [sorted(edge) for edge in edges]
        edges.sort()
        result = CHECKER.evaluate_document(
            candidate(5, edges),
            minimum_order=3,
            required_minimum_degree=2,
        )
        self.assertTrue(result["accepted"])
        self.assertEqual(result["facts"]["checked_lengths"], [4])
        self.assertEqual(result["reason_code"], "ACCEPTED")

    def test_exhaustive_all_graphs_on_five_vertices_match_brute_force_for_c4(self) -> None:
        all_edges = list(combinations(range(5), 2))
        for mask in range(1 << len(all_edges)):
            edges = [list(edge) for index, edge in enumerate(all_edges) if mask & (1 << index)]
            adjacency = adjacency_of(5, edges)
            observed = CHECKER.find_simple_cycle_of_length(
                adjacency, 4, CHECKER.SearchBudget(100_000)
            )
            expected = reference_cycle(5, edges, 4)
            self.assertEqual(observed is not None, expected is not None, f"mask={mask}")

    def test_random_small_graphs_match_independent_reference_at_all_relevant_lengths(self) -> None:
        generator = random.Random(0xE640)
        for case_number in range(48):
            n = generator.randint(4, 8)
            edges = [
                [left, right]
                for left in range(n)
                for right in range(left + 1, n)
                if generator.random() < 0.34
            ]
            adjacency = adjacency_of(n, edges)
            for length in CHECKER.power_of_two_cycle_lengths(n):
                observed = CHECKER.find_simple_cycle_of_length(
                    adjacency, length, CHECKER.SearchBudget(1_000_000)
                )
                expected = reference_cycle(n, edges, length)
                self.assertEqual(
                    observed is not None,
                    expected is not None,
                    f"case={case_number}, n={n}, length={length}",
                )

    def test_exact_power_lengths_include_and_detect_the_upper_boundary(self) -> None:
        self.assertEqual(
            CHECKER.power_of_two_cycle_lengths(64),
            [4, 8, 16, 32, 64],
        )
        for length in (4, 8, 16, 32, 64):
            edges = [[vertex, vertex + 1] for vertex in range(length - 1)]
            edges.append([0, length - 1])
            witness = CHECKER.find_simple_cycle_of_length(
                adjacency_of(length, edges),
                length,
                CHECKER.SearchBudget(1_000_000),
            )
            self.assertIsNotNone(witness)
            self.assertEqual(len(witness), length)

    def test_search_ceiling_is_inconclusive_not_mathematical_rejection(self) -> None:
        # A branching tree has no cycles, but a tiny artificial budget prevents
        # the exact absence search from completing.
        edges = [[(vertex - 1) // 2, vertex] for vertex in range(1, 63)]
        adjacency = adjacency_of(63, edges)
        with self.assertRaisesRegex(CHECKER.ApparatusFailure, "SEARCH_STEP_LIMIT"):
            CHECKER.find_simple_cycle_of_length(
                adjacency, 16, CHECKER.SearchBudget(10)
            )

        k4_edges = [[left, right] for left in range(4) for right in range(left + 1, 4)]
        with self.assertRaisesRegex(CHECKER.ApparatusFailure, "SEARCH_STEP_LIMIT"):
            CHECKER.evaluate_document(candidate(4, k4_edges), search_step_limit=1)

    def test_graph_format_and_degree_fail_closed_before_expensive_search(self) -> None:
        cases = [
            (candidate(4, [[0, 0]]), "SELF_LOOP"),
            (candidate(4, [[0, 1], [0, 1]]), "DUPLICATE_EDGE"),
            (candidate(4, [[1, 0]]), "NONCANONICAL_EDGE"),
            (candidate(4, [[0, 4]]), "VERTEX_OUT_OF_RANGE"),
            (candidate(4, [[0, True]]), "INVALID_EDGE"),
            (candidate(4, []), "MINIMUM_DEGREE"),
            (candidate(65, []), "ORDER_OUT_OF_RANGE"),
            ({**candidate(4, []), "certificate": []}, "INVALID_DOCUMENT"),
        ]
        for value, reason in cases:
            with self.subTest(reason=reason):
                result = CHECKER.evaluate_document(value)
                self.assertFalse(result["accepted"])
                self.assertEqual(result["reason_code"], reason)

    def test_deep_json_huge_integer_oversize_symlink_and_fifo_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            deep = root / "deep.json"
            deep.write_text("[" * 1500 + "]" * 1500, encoding="ascii")
            huge = root / "huge.json"
            huge.write_text('{"schema":"x","n":' + "9" * 1000 + "}", encoding="ascii")
            oversize = root / "oversize.json"
            with oversize.open("wb") as stream:
                stream.truncate(CHECKER.MAXIMUM_INPUT_BYTES + 1)
            regular = self.write_candidate(root, candidate(4, []))
            link = root / "link.json"
            link.symlink_to(regular)
            fifo = root / "candidate.fifo"
            os.mkfifo(fifo)

            for path, expected_code in (
                (deep, 1),
                (huge, 1),
                (oversize, 1),
                (link, 2),
                (fifo, 2),
            ):
                completed = subprocess.run(
                    [str(VERIFIER / "checker.py"), "--candidate", str(path)],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                    timeout=5,
                )
                self.assertEqual(completed.returncode, expected_code, path.name)
                self.assertFalse(completed.stderr)
                output = json.loads(completed.stdout)
                self.assertFalse(output["accepted"])

    def test_cli_rejection_has_protocol_shape_and_exit_one(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_candidate(Path(temporary), candidate(4, []))
            completed = subprocess.run(
                [str(VERIFIER / "checker.py"), "--candidate", str(path)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=5,
            )
        self.assertEqual(completed.returncode, 1)
        self.assertFalse(completed.stderr)
        output = json.loads(completed.stdout)
        self.assertEqual(output["schema"], "AMF_VERIFIER_RESULT_1")
        self.assertEqual(output["verifier_id"], CHECKER.VERIFIER_ID)
        self.assertFalse(output["accepted"])
        self.assertEqual(output["reason_code"], "MINIMUM_DEGREE")


if __name__ == "__main__":
    unittest.main()
