from __future__ import annotations

from collections import deque
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
VERIFIER = ROOT / "verifiers" / "amf.dd39.exact.v1"
TARGET = ROOT / "targets" / "degree-diameter-3-9-record"
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


PRIMARY = load_module("amf_dd39_primary", VERIFIER / "primary.py")
SECONDARY = load_module("amf_dd39_secondary", VERIFIER / "secondary.py")
DISPATCH = load_module("amf_dd39_dispatch", VERIFIER / "dispatch.py")
CONVERTER = load_module("amf_dd39_converter", BASELINE / "convert_implicit.py")


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii") + b"\n"


def candidate(n: int, edges: list[list[int]]) -> dict[str, object]:
    return {"edges": edges, "n": n, "schema": PRIMARY.CANDIDATE_SCHEMA}


def bounded_binary_tree(order: int) -> list[list[int]]:
    """A prefix of the infinite rooted binary tree, in canonical edge form."""

    return [[(vertex - 1) // 2, vertex] for vertex in range(1, order)]


def synthetic_prism_source() -> bytes:
    """Repository-authored 600-vertex cubic fixture in the source format."""

    cycle = 300
    rows: list[str] = []
    for vertex in range(600):
        layer = vertex // cycle
        offset = vertex % cycle
        base = layer * cycle
        neighbors = {
            base + (offset - 1) % cycle,
            base + (offset + 1) % cycle,
            (1 - layer) * cycle + offset,
        }
        rows.append(" ".join(str(item) for item in sorted(neighbors)))
    return ("\n".join(rows) + "\n").encode("ascii")


def independent_metrics(
    n: int, edges: list[list[int]],
) -> tuple[int, bool, int | None, int | None]:
    """Small third-reference checker using Floyd--Warshall."""

    degrees = [0] * n
    infinity = n + 1
    distances = [[infinity] * n for _ in range(n)]
    for vertex in range(n):
        distances[vertex][vertex] = 0
    for left, right in edges:
        degrees[left] += 1
        degrees[right] += 1
        distances[left][right] = 1
        distances[right][left] = 1
    for middle in range(n):
        for left in range(n):
            through = distances[left][middle]
            for right in range(n):
                alternative = through + distances[middle][right]
                if alternative < distances[left][right]:
                    distances[left][right] = alternative
    connected = all(value < infinity for row in distances for value in row)
    if not connected:
        return max(degrees, default=0), False, None, None
    eccentricities = [max(row) for row in distances]
    return max(degrees, default=0), True, max(eccentricities), min(eccentricities)


class DegreeDiameterVerifierTests(unittest.TestCase):
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

    def assert_core_agreement(self, value: object) -> dict[str, object]:
        primary = PRIMARY.evaluate_document(value)
        secondary = SECONDARY.evaluate_document(value)
        self.assertEqual(self.normalized(primary), self.normalized(secondary))
        return primary

    def test_registered_manifest_and_active_target_card_obey_contract(self) -> None:
        registry = validate_verifier_registry(load_json(ROOT / "data" / "verifiers.json"), root=ROOT)
        self.assertIn("amf.dd39.exact.v1", registry)
        manifest = registry["amf.dd39.exact.v1"]["manifest_value"]
        self.assertEqual(
            manifest["binds_verification_mode"],
            "exact_degree_connectivity_and_bfs_diameter_checker",
        )

        catalog = load_json(ROOT / "data" / "problems.json")
        problem = next(
            item for item in catalog["problems"]
            if item["id"] == "degree-diameter-3-9-record"
        )
        self.assertEqual(problem["stage"], "active")
        card = validate_target_card(
            load_json(TARGET / "target-card.json"),
            root=ROOT,
            expected_problem_id=problem["id"],
            expected_problem_card_sha256=canonical_sha256(problem),
            expected_source_revision=problem["formalization"]["revision"],
        )
        self.assertEqual(card["verifier_id"], "amf.dd39.exact.v1")

    def test_frozen_baseline_metadata_excludes_third_party_graph_bytes(self) -> None:
        metadata = load_json(BASELINE / "source-metadata.json")
        self.assertEqual(metadata["schema"], "AMF_DD39_SOURCE_EVIDENCE_2")
        self.assertEqual(
            metadata["versioned_dataset"]["member_sha256"],
            "12de7e2c303955f57196888a0eecae17d7e872616a638d6f7772b09f77f34106",
        )
        self.assertFalse(metadata["redistribution_policy"]["raw_member_in_repository"])
        self.assertFalse(
            metadata["redistribution_policy"]["complete_normalized_graph_in_repository"]
        )
        self.assertFalse((BASELINE / "Exoo_600.txt").exists())
        self.assertFalse((BASELINE / "Exoo_600.normalized.json").exists())

    def test_converter_and_both_cores_use_owned_synthetic_cubic_fixture(self) -> None:
        graph = CONVERTER.convert(synthetic_prism_source())
        self.assertEqual(graph["schema"], PRIMARY.BASELINE_SCHEMA)
        expected_facts = {
            "connected": True,
            "diameter": 151,
            "edge_count": 900,
            "max_degree": 3,
            "n": 600,
        }
        for checker in (PRIMARY, SECONDARY):
            with self.subTest(checker=checker.CHECKER_ID):
                result = checker.evaluate_document(
                    graph,
                    minimum_order=1,
                    expected_schema=checker.BASELINE_SCHEMA,
                )
                self.assertFalse(result["accepted"])
                self.assertEqual(result["reason_code"], "DIAMETER_LIMIT")
                self.assertEqual(result["facts"], expected_facts)

    def test_production_threshold_rejects_the_600_vertex_baseline_by_order(self) -> None:
        graph = CONVERTER.convert(synthetic_prism_source())
        graph["schema"] = PRIMARY.CANDIDATE_SCHEMA
        result = self.assert_core_agreement(graph)
        self.assertEqual(result["reason_code"], "ORDER_OUT_OF_RANGE")
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_candidate(Path(temporary), graph)
            dispatched, infrastructure_failure = DISPATCH.dispatch_path(path)
        self.assertFalse(infrastructure_failure)
        self.assertFalse(dispatched["accepted"])
        self.assertEqual(dispatched["reason_code"], "ORDER_OUT_OF_RANGE")

    @unittest.skipUnless(
        os.environ.get("AMF_DD39_BASELINE_SOURCE"),
        "set AMF_DD39_BASELINE_SOURCE to an externally obtained exact source file",
    )
    def test_opt_in_external_baseline_hash_conversion_and_metrics(self) -> None:
        source = Path(os.environ["AMF_DD39_BASELINE_SOURCE"])
        raw = CONVERTER.read_source(source)
        self.assertEqual(
            hashlib.sha256(raw).hexdigest(),
            "12de7e2c303955f57196888a0eecae17d7e872616a638d6f7772b09f77f34106",
        )
        graph = CONVERTER.convert(raw)
        self.assertEqual(
            hashlib.sha256(canonical_bytes(graph)).hexdigest(),
            "efa7763007d3f1771c547d47b1ab8280ecf8f42b854850bc3e814a26b47ef5ae",
        )
        for checker in (PRIMARY, SECONDARY):
            result = checker.evaluate_document(
                graph,
                minimum_order=1,
                expected_schema=checker.BASELINE_SCHEMA,
            )
            self.assertTrue(result["accepted"])
            self.assertEqual(result["facts"]["diameter"], 9)

    def test_maximum_degree_semantics_do_not_require_cubic_regularity(self) -> None:
        # P_10 has maximum degree 2 and diameter exactly 9.
        graph = candidate(10, [[vertex, vertex + 1] for vertex in range(9)])
        for checker in (PRIMARY, SECONDARY):
            result = checker.evaluate_document(graph, minimum_order=1)
            self.assertTrue(result["accepted"])
            self.assertEqual(result["facts"]["max_degree"], 2)
            self.assertEqual(result["facts"]["diameter"], 9)

    def test_radius_nine_is_not_confused_with_diameter_nine(self) -> None:
        graph = candidate(601, bounded_binary_tree(601))
        root_eccentricity = max((vertex + 1).bit_length() - 1 for vertex in range(601))
        self.assertEqual(root_eccentricity, 9)
        max_degree, connected, diameter, radius = independent_metrics(127, bounded_binary_tree(127))
        self.assertEqual(max_degree, 3)
        self.assertTrue(connected)
        self.assertLessEqual(radius, 9)
        self.assertGreater(diameter, 9)

        result = self.assert_core_agreement(graph)
        self.assertEqual(result["reason_code"], "DIAMETER_LIMIT")
        self.assertTrue(result["facts"]["connected"])
        self.assertLessEqual(result["facts"]["max_degree"], 3)
        self.assertGreater(result["facts"]["diameter"], 9)

    def test_isolated_vertex_and_hidden_fourth_edge_are_rejected(self) -> None:
        isolated = self.assert_core_agreement(candidate(601, []))
        self.assertEqual(isolated["reason_code"], "DISCONNECTED")

        fourth_edge = self.assert_core_agreement(
            candidate(601, [[0, 1], [0, 2], [0, 3], [0, 4]])
        )
        self.assertEqual(fourth_edge["reason_code"], "DEGREE_LIMIT")
        self.assertEqual(fourth_edge["facts"]["max_degree"], 4)

    def test_duplicate_and_reverse_oriented_edges_are_rejected(self) -> None:
        duplicate = self.assert_core_agreement(candidate(601, [[0, 1], [0, 1]]))
        self.assertEqual(duplicate["reason_code"], "DUPLICATE_EDGE")

        reverse = self.assert_core_agreement(candidate(601, [[1, 0]]))
        self.assertEqual(reverse["reason_code"], "NONCANONICAL_EDGE")

        asymmetric_adjacency = {
            "schema": PRIMARY.CANDIDATE_SCHEMA,
            "n": 601,
            "adjacency": {"0": [1], "1": []},
        }
        alternate = self.assert_core_agreement(asymmetric_adjacency)
        self.assertEqual(alternate["reason_code"], "INVALID_DOCUMENT")

    def test_random_small_graphs_agree_with_independent_floyd_reference(self) -> None:
        generator = random.Random(0xDD39)
        for case_number in range(160):
            n = generator.randint(1, 10)
            edges = [
                [left, right]
                for left in range(n)
                for right in range(left + 1, n)
                if generator.random() < 0.22
            ]
            graph = candidate(n, edges)
            primary = PRIMARY.evaluate_document(graph, minimum_order=1)
            secondary = SECONDARY.evaluate_document(graph, minimum_order=1)
            self.assertEqual(
                self.normalized(primary), self.normalized(secondary),
                f"checker mismatch in randomized case {case_number}",
            )
            maximum_degree, connected, diameter, _radius = independent_metrics(n, edges)
            facts = primary["facts"]
            self.assertEqual(facts["max_degree"], maximum_degree)
            if maximum_degree <= 3:
                self.assertEqual(facts["connected"], connected)
                if connected:
                    self.assertEqual(facts["diameter"], diameter)

    def test_huge_order_deep_json_and_huge_integer_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            huge_order = self.write_candidate(directory, candidate(1_000_000_000, []), "huge-n.json")
            result, infrastructure = DISPATCH.dispatch_path(huge_order)
            self.assertFalse(infrastructure)
            self.assertEqual(result["reason_code"], "ORDER_OUT_OF_RANGE")

            deep = directory / "deep.json"
            deep.write_bytes(
                b'{"schema":"AMF_DD39_CANDIDATE_1","n":601,"edges":'
                + b"[" * 1_500 + b"0" + b"]" * 1_500 + b"}\n"
            )
            result, infrastructure = DISPATCH.dispatch_path(deep)
            self.assertFalse(infrastructure)
            self.assertEqual(result["reason_code"], "INVALID_JSON")

            huge_integer = directory / "huge-integer.json"
            huge_integer.write_bytes(
                b'{"schema":"AMF_DD39_CANDIDATE_1","n":'
                + b"9" * 10_000 + b',"edges":[]}\n'
            )
            result, infrastructure = DISPATCH.dispatch_path(huge_integer)
            self.assertFalse(infrastructure)
            self.assertEqual(result["reason_code"], "INTEGER_OUT_OF_RANGE")

    def test_symlink_fifo_and_oversize_are_rejected_before_checker_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            ordinary = self.write_candidate(directory, candidate(601, []), "ordinary.json")

            symlink = directory / "candidate-link.json"
            symlink.symlink_to(ordinary)
            result, infrastructure = DISPATCH.dispatch_path(symlink)
            self.assertTrue(infrastructure)
            self.assertEqual(result["reason_code"], "INPUT_NOT_REGULAR")

            if hasattr(os, "mkfifo"):
                fifo = directory / "candidate.fifo"
                os.mkfifo(fifo)
                result, infrastructure = DISPATCH.dispatch_path(fifo)
                self.assertTrue(infrastructure)
                self.assertEqual(result["reason_code"], "INPUT_NOT_REGULAR")

            oversized = directory / "oversized.json"
            with oversized.open("wb") as stream:
                stream.truncate(DISPATCH.MAXIMUM_INPUT_BYTES + 1)
            result, infrastructure = DISPATCH.dispatch_path(oversized)
            self.assertTrue(infrastructure)
            self.assertEqual(result["reason_code"], "INPUT_TOO_LARGE")

    def test_checker_disagreement_is_an_infrastructure_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            path = self.write_candidate(directory, candidate(601, []))
            fake = directory / "fake-secondary.py"
            fake.write_text(
                "import json,sys\n"
                "r={'accepted':False,'checker':'SECONDARY_BITSET_WAVEFRONT',"
                "'facts':{'connected':None,'diameter':None,'edge_count':0,"
                "'max_degree':4,'n':601},'reason_code':'DEGREE_LIMIT',"
                "'schema':'AMF_VERIFIER_RESULT_1','verifier_id':'amf.dd39.exact.v1'}\n"
                "print(json.dumps(r,sort_keys=True,separators=(',',':')))\n"
                "sys.exit(1)\n",
                encoding="utf-8",
            )
            result, infrastructure = DISPATCH.dispatch_path(path, secondary_path=fake)
            self.assertTrue(infrastructure)
            self.assertFalse(result["accepted"])
            self.assertEqual(result["reason_code"], "CHECKER_DISAGREEMENT")

    def test_dispatcher_cli_does_not_allow_candidate_selected_checker_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_candidate(Path(temporary), candidate(601, []))
            completed = subprocess.run(
                [
                    sys.executable,
                    str(VERIFIER / "dispatch.py"),
                    "--candidate",
                    str(path),
                    "--secondary",
                    "/tmp/attacker.py",
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(completed.returncode, 2)


if __name__ == "__main__":
    unittest.main()
