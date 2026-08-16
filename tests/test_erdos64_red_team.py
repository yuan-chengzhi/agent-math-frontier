from __future__ import annotations

from itertools import combinations
import importlib.util
import json
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "verifiers" / "amf.erdos64.counterexample.v1"
TARGET = ROOT / "targets" / "erdos-64"

sys.path.insert(0, str(ROOT / "scripts"))
from contracts import ContractError, load_json, validate_verifier_manifest  # noqa: E402


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CHECKER = load_module("red_erdos64", VERIFIER / "checker.py")


def candidate(n: int, edges: list[list[int]]) -> dict[str, object]:
    return {
        "schema": CHECKER.CANDIDATE_SCHEMA,
        "kind": "graph_counterexample",
        "n": n,
        "edges": edges,
    }


def adjacency(n: int, edges: list[list[int]]) -> list[tuple[int, ...]]:
    rows = [[] for _ in range(n)]
    for left, right in edges:
        rows[left].append(right)
        rows[right].append(left)
    return [tuple(sorted(row)) for row in rows]


def reference_cycle(rows: list[tuple[int, ...]], length: int) -> bool:
    """Unpruned oriented simple-path reference search."""

    n = len(rows)
    for start in range(n):
        path = [start]
        used = {start}

        def visit(current: int) -> bool:
            if len(path) == length:
                return start in rows[current]
            for neighbor in rows[current]:
                if neighbor in used:
                    continue
                used.add(neighbor)
                path.append(neighbor)
                if visit(neighbor):
                    return True
                path.pop()
                used.remove(neighbor)
            return False

        if visit(start):
            return True
    return False


def has_c4_by_common_neighbors(rows: list[tuple[int, ...]]) -> bool:
    neighbor_sets = [set(row) for row in rows]
    return any(
        len(neighbor_sets[left] & neighbor_sets[right]) >= 2
        for left in range(len(rows))
        for right in range(left + 1, len(rows))
    )


class Erdos64RedTeamTests(unittest.TestCase):
    def test_corpus_is_target_bound_and_case_ids_are_unique(self) -> None:
        corpus = load_json(
            TARGET / "evidence" / "red-team" / "corpus-codex-2026-08-14.json"
        )
        self.assertEqual(corpus["problem_id"], "erdos-64")
        ids = [case["id"] for case in corpus["cases"]]
        self.assertEqual(len(ids), 14)
        self.assertEqual(len(ids), len(set(ids)))

    def test_all_32768_graphs_on_six_vertices_match_c4_characterization(self) -> None:
        possible = list(combinations(range(6), 2))
        for mask in range(1 << len(possible)):
            edges = [
                list(edge)
                for index, edge in enumerate(possible)
                if mask & (1 << index)
            ]
            rows = adjacency(6, edges)
            observed = CHECKER.find_simple_cycle_of_length(
                rows, 4, CHECKER.SearchBudget(100_000)
            )
            self.assertEqual(
                observed is not None,
                has_c4_by_common_neighbors(rows),
                mask,
            )

    def test_random_c4_and_c8_search_matches_unpruned_reference(self) -> None:
        generator = random.Random(0xE640C0DE)
        for case_number in range(80):
            n = generator.randint(4, 10)
            edges = [
                [left, right]
                for left in range(n)
                for right in range(left + 1, n)
                if generator.random() < 0.24
            ]
            rows = adjacency(n, edges)
            for length in (4, 8):
                if length > n:
                    continue
                observed = CHECKER.find_simple_cycle_of_length(
                    rows, length, CHECKER.SearchBudget(5_000_000)
                )
                self.assertEqual(
                    observed is not None,
                    reference_cycle(rows, length),
                    (case_number, n, length),
                )

    def test_cycle_with_chords_is_not_mistaken_for_induced_cycle(self) -> None:
        edges = [[0, 1], [1, 2], [2, 3], [0, 3], [0, 2], [1, 3]]
        witness = CHECKER.find_simple_cycle_of_length(
            adjacency(4, edges), 4, CHECKER.SearchBudget(10_000)
        )
        self.assertIsNotNone(witness)
        self.assertEqual(len(set(witness)), 4)

    def test_orientation_reduction_returns_a_real_canonical_witness(self) -> None:
        length = 8
        edges = [[vertex, vertex + 1] for vertex in range(length - 1)]
        edges.append([0, length - 1])
        rows = adjacency(length, edges)
        witness = CHECKER.find_simple_cycle_of_length(
            rows, length, CHECKER.SearchBudget(100_000)
        )
        self.assertIsNotNone(witness)
        assert witness is not None
        self.assertEqual(witness[0], min(witness))
        self.assertLess(witness[1], witness[-1])
        self.assertEqual(len(witness), len(set(witness)))
        for index, vertex in enumerate(witness):
            self.assertIn(witness[(index + 1) % length], rows[vertex])

    def test_connectivity_is_not_added_and_degree_threshold_is_exact(self) -> None:
        # Two disjoint 5-cycles have no C4 or C8. The relaxed degree seam
        # accepts them, proving that the checker does not silently require
        # connectivity; production still rejects degree two.
        edges = []
        for offset in (0, 5):
            for index in range(5):
                edge = sorted((offset + index, offset + (index + 1) % 5))
                if edge not in edges:
                    edges.append(edge)
        edges.sort()
        production = CHECKER.evaluate_document(candidate(10, edges))
        relaxed = CHECKER.evaluate_document(
            candidate(10, edges), required_minimum_degree=2
        )
        self.assertEqual(production["reason_code"], "MINIMUM_DEGREE")
        self.assertTrue(relaxed["accepted"])
        self.assertEqual(relaxed["facts"]["checked_lengths"], [4, 8])

    def test_upper_cycle_length_64_is_included_and_detected(self) -> None:
        self.assertEqual(
            CHECKER.power_of_two_cycle_lengths(64), [4, 8, 16, 32, 64]
        )
        edges = [[vertex, vertex + 1] for vertex in range(63)] + [[0, 63]]
        witness = CHECKER.find_simple_cycle_of_length(
            adjacency(64, edges), 64, CHECKER.SearchBudget(1_000_000)
        )
        self.assertIsNotNone(witness)
        self.assertEqual(len(witness), 64)

    def test_json_type_canonicalization_and_duplicate_key_attacks(self) -> None:
        cases = [
            (candidate(4, [[0, True]]), "INVALID_EDGE"),
            (candidate(4, [[1, 0]]), "NONCANONICAL_EDGE"),
            (candidate(4, [[0, 1], [0, 1]]), "DUPLICATE_EDGE"),
        ]
        for value, reason in cases:
            result = CHECKER.evaluate_document(value)
            self.assertEqual(result["reason_code"], reason)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.json"
            path.write_bytes(
                b'{"schema":"AMF_ERDOS64_GRAPH_COUNTEREXAMPLE_1",'
                b'"kind":"graph_counterexample","n":4,"edges":[],"edges":[]}\n'
            )
            result, infrastructure = CHECKER.evaluate_path(path)
        self.assertFalse(infrastructure)
        self.assertEqual(result["reason_code"], "DUPLICATE_JSON_KEY")

    def test_step_ceiling_and_memory_error_are_apparatus_failures(self) -> None:
        k4_edges = [[left, right] for left in range(4) for right in range(left + 1, 4)]
        with self.assertRaisesRegex(CHECKER.ApparatusFailure, "SEARCH_STEP_LIMIT"):
            CHECKER.evaluate_document(
                candidate(4, k4_edges), search_step_limit=1
            )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "candidate.json"
            path.write_text(json.dumps(candidate(4, k4_edges)), encoding="ascii")
            with mock.patch.object(CHECKER, "evaluate_document", side_effect=MemoryError):
                result, infrastructure = CHECKER.evaluate_path(path)
        self.assertTrue(infrastructure)
        self.assertEqual(result["reason_code"], "RESOURCE_FAILURE")

    def test_cli_emits_exit_two_for_search_ceiling(self) -> None:
        edges = [[left, right] for left in range(4) for right in range(left + 1, 4)]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "candidate.json"
            path.write_text(json.dumps(candidate(4, edges)), encoding="ascii")
            script = (
                "import importlib.util,sys\n"
                f"p={str(VERIFIER / 'checker.py')!r}\n"
                "s=importlib.util.spec_from_file_location('e64_cli_red',p)\n"
                "m=importlib.util.module_from_spec(s);s.loader.exec_module(m)\n"
                "old=m.evaluate_document\n"
                "m.evaluate_document=lambda value: old(value,search_step_limit=1)\n"
                f"raise SystemExit(m.main(['checker.py','--candidate',{str(path)!r}]))\n"
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
        self.assertEqual(output["reason_code"], "SEARCH_STEP_LIMIT")

    def test_manifest_detects_source_drift_and_symlink_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            copied = root / "verifiers" / "amf.erdos64.counterexample.v1"
            copied.parent.mkdir(parents=True)
            shutil.copytree(VERIFIER, copied)
            manifest = load_json(copied / "manifest.json")
            validate_verifier_manifest(
                manifest, root=root, expected_verifier_id=CHECKER.VERIFIER_ID
            )
            checker = copied / "checker.py"
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
