from __future__ import annotations

from collections import deque
import importlib.util
import json
from itertools import combinations
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "verifiers" / "amf.dd39.exact.v1"
TARGET = ROOT / "targets" / "degree-diameter-3-9-record"

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


PRIMARY = load_module("red_dd_primary", VERIFIER / "primary.py")
SECONDARY = load_module("red_dd_secondary", VERIFIER / "secondary.py")
DISPATCH = load_module("red_dd_dispatch", VERIFIER / "dispatch.py")


def graph(n: int, edges: list[list[int]]) -> dict[str, object]:
    return {"schema": PRIMARY.CANDIDATE_SCHEMA, "n": n, "edges": edges}


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode() + b"\n"


def reference(n: int, edges: list[list[int]]) -> tuple[int, bool, int | None]:
    adjacency = [[] for _ in range(n)]
    for left, right in edges:
        adjacency[left].append(right)
        adjacency[right].append(left)
    maximum_degree = max(map(len, adjacency), default=0)
    diameter = 0
    for source in range(n):
        distances = [-1] * n
        distances[source] = 0
        queue = deque([source])
        while queue:
            vertex = queue.popleft()
            for neighbor in adjacency[vertex]:
                if distances[neighbor] < 0:
                    distances[neighbor] = distances[vertex] + 1
                    queue.append(neighbor)
        if -1 in distances:
            return maximum_degree, False, None
        diameter = max(diameter, max(distances))
    return maximum_degree, True, diameter


def fake_checker(path: Path, checker: str, result: dict[str, object], exit_code: int) -> None:
    payload = {**result, "checker": checker}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    path.write_text(
        f"print({encoded!r})\nraise SystemExit({exit_code})\n",
        encoding="ascii",
    )


class DD39RedTeamTests(unittest.TestCase):
    def test_corpus_is_target_bound_and_case_ids_are_unique(self) -> None:
        corpus = load_json(
            TARGET / "evidence" / "red-team" / "corpus-codex-2026-08-14.json"
        )
        self.assertEqual(corpus["problem_id"], "degree-diameter-3-9-record")
        ids = [case["id"] for case in corpus["cases"]]
        self.assertEqual(len(ids), 14)
        self.assertEqual(len(ids), len(set(ids)))

    def test_exhaustive_all_labelled_graphs_through_five_vertices(self) -> None:
        for n in range(1, 6):
            possible = list(combinations(range(n), 2))
            for mask in range(1 << len(possible)):
                edges = [
                    list(edge)
                    for index, edge in enumerate(possible)
                    if mask & (1 << index)
                ]
                value = graph(n, edges)
                first = PRIMARY.evaluate_document(value, minimum_order=1)
                second = SECONDARY.evaluate_document(value, minimum_order=1)
                self.assertEqual(
                    (first["accepted"], first["reason_code"], first["facts"]),
                    (second["accepted"], second["reason_code"], second["facts"]),
                    (n, mask),
                )
                maximum_degree, connected, diameter = reference(n, edges)
                self.assertEqual(first["facts"]["max_degree"], maximum_degree)
                if maximum_degree > 3:
                    self.assertEqual(first["reason_code"], "DEGREE_LIMIT")
                elif not connected:
                    self.assertEqual(first["reason_code"], "DISCONNECTED")
                else:
                    self.assertTrue(first["accepted"])
                    self.assertEqual(first["facts"]["diameter"], diameter)

    def test_diameter_and_maximum_degree_semantic_boundaries(self) -> None:
        p10 = graph(10, [[vertex, vertex + 1] for vertex in range(9)])
        p11 = graph(11, [[vertex, vertex + 1] for vertex in range(10)])
        for checker in (PRIMARY, SECONDARY):
            accepted = checker.evaluate_document(p10, minimum_order=1)
            rejected = checker.evaluate_document(p11, minimum_order=1)
            self.assertTrue(accepted["accepted"])
            self.assertEqual(accepted["facts"]["max_degree"], 2)
            self.assertEqual(accepted["facts"]["diameter"], 9)
            self.assertEqual(rejected["reason_code"], "DIAMETER_LIMIT")

    def test_json_type_and_canonical_edge_attacks_fail_closed(self) -> None:
        cases = [
            graph(601, [[0, True]]),
            graph(601, [[0, 1.0]]),
            graph(601, [[1, 0]]),
            graph(601, [[0, 1], [0, 1]]),
        ]
        for value in cases:
            for checker in (PRIMARY, SECONDARY):
                self.assertFalse(checker.evaluate_document(value)["accepted"])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.json"
            path.write_bytes(
                b'{"schema":"AMF_DD39_CANDIDATE_1","n":601,'
                b'"edges":[[0,1]],"edges":[]}\n'
            )
            result, infrastructure = DISPATCH.dispatch_path(path)
        self.assertFalse(infrastructure)
        self.assertEqual(result["reason_code"], "DUPLICATE_JSON_KEY")

    def test_core_resource_exceptions_are_explicit_apparatus_failures(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "candidate.json"
            path.write_bytes(canonical(graph(601, [])))
            for checker in (PRIMARY, SECONDARY):
                with self.subTest(checker=checker.CHECKER_ID), mock.patch.object(
                    checker, "evaluate_document", side_effect=MemoryError
                ):
                    result, infrastructure = checker.evaluate_path_with_status(path)
                    self.assertTrue(infrastructure)
                    self.assertEqual(result["reason_code"], "RESOURCE_FAILURE")

    def test_dispatcher_preserves_exit_two_and_rejects_exit_one_resource_claims(self) -> None:
        blank = DISPATCH._result(False, "RESOURCE_FAILURE")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = root / "candidate.json"
            candidate.write_bytes(canonical(graph(601, [])))
            for exit_code in (2, 1):
                first = root / f"first-{exit_code}.py"
                second = root / f"second-{exit_code}.py"
                fake_checker(first, DISPATCH.PRIMARY_ID, blank, exit_code)
                fake_checker(second, DISPATCH.SECONDARY_ID, blank, exit_code)
                result, infrastructure = DISPATCH.dispatch_path(
                    candidate, primary_path=first, secondary_path=second
                )
                self.assertTrue(infrastructure)
                self.assertFalse(result["accepted"])
                self.assertIn(
                    result["reason_code"],
                    {"CHECKER_INFRASTRUCTURE_FAILURE", "CHECKER_INVALID_OUTPUT"},
                )

    def test_implausible_accepted_facts_cannot_cross_dispatch_boundary(self) -> None:
        bogus = DISPATCH._result(
            True,
            "ACCEPTED",
            {
                "connected": False,
                "diameter": 99,
                "edge_count": 0,
                "max_degree": 0,
                "n": 601,
            },
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = root / "candidate.json"
            candidate.write_bytes(canonical(graph(601, [])))
            first = root / "first.py"
            second = root / "second.py"
            fake_checker(first, DISPATCH.PRIMARY_ID, bogus, 0)
            fake_checker(second, DISPATCH.SECONDARY_ID, bogus, 0)
            result, infrastructure = DISPATCH.dispatch_path(
                candidate, primary_path=first, secondary_path=second
            )
        self.assertTrue(infrastructure)
        self.assertEqual(result["reason_code"], "CHECKER_INVALID_OUTPUT")

    def test_checker_timeout_and_output_ceiling_are_apparatus_failures(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = root / "candidate.json"
            candidate.write_bytes(canonical(graph(601, [])))
            sleeper = root / "sleeper.py"
            sleeper.write_text("import time\ntime.sleep(5)\n", encoding="ascii")
            with mock.patch.object(DISPATCH, "CHECKER_TIMEOUT_SECONDS", 0.02):
                result, infrastructure = DISPATCH.dispatch_path(
                    candidate, primary_path=sleeper
                )
            self.assertTrue(infrastructure)
            self.assertEqual(result["reason_code"], "CHECKER_TIMEOUT")

            noisy = root / "noisy.py"
            noisy.write_text(
                f"print('x' * {DISPATCH.MAXIMUM_CHECKER_OUTPUT_BYTES + 1})\n",
                encoding="ascii",
            )
            result, infrastructure = DISPATCH.dispatch_path(
                candidate, primary_path=noisy
            )
            self.assertTrue(infrastructure)
            self.assertEqual(result["reason_code"], "CHECKER_OUTPUT_LIMIT")

    def test_manifest_detects_source_drift_and_symlink_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            copied = root / "verifiers" / "amf.dd39.exact.v1"
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
