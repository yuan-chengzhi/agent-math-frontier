from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from contracts import (  # noqa: E402
    BASELINE_RECEIPT_SCHEMA,
    BUDGET_RECEIPT_SCHEMA,
    ContractError,
    MAX_BOUND_FILE_BYTES,
    MAX_JSON_BYTES,
    RED_TEAM_RECEIPT_SCHEMA,
    REVIEW_ATTESTATION_SCOPE,
    REVIEW_RECEIPT_SCHEMA,
    TARGET_BUNDLE_SCHEMA,
    TARGET_CARD_SCHEMA,
    VERIFIER_MANIFEST_SCHEMA,
    canonical_json_bytes,
    canonical_sha256,
    load_json,
    make_file_binding,
    validate_file_binding,
    validate_problem_card,
    validate_problem_catalog,
    validate_review_receipt,
)
from export_active import build_active_portfolio  # noqa: E402


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value) + b"\n")


class ContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = load_json(ROOT / "data" / "problems.json")

    def test_canonical_json_and_hash_ignore_object_insertion_order(self) -> None:
        left = {"z": [3, {"b": 2, "a": 1}], "a": "数学"}
        right = {"a": "数学", "z": [3, {"a": 1, "b": 2}]}
        self.assertEqual(canonical_json_bytes(left), canonical_json_bytes(right))
        self.assertEqual(canonical_sha256(left), canonical_sha256(right))

    def test_problem_card_schema_rejects_extra_fields(self) -> None:
        problem = copy.deepcopy(self.catalog["problems"][0])
        problem["score"] = 99
        with self.assertRaisesRegex(ContractError, "exact fields"):
            validate_problem_card(problem)

    def test_unknown_problem_catalog_version_is_rejected(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        catalog["schema_version"] = 2
        with self.assertRaisesRegex(ContractError, "unsupported version"):
            validate_problem_catalog(catalog)

    def test_any_conditional_active_problem_is_rejected(self) -> None:
        problem = copy.deepcopy(next(
            item for item in self.catalog["problems"]
            if item["id"] == "frontier-stretched-lr"
        ))
        problem["stage"] = "active"
        problem["hard_gates"]["reproducibility"] = "conditional"
        self.assertEqual(problem["hard_gates"]["reproducibility"], "conditional")
        with self.assertRaisesRegex(ContractError, "requires every hard gate to pass"):
            validate_problem_card(problem)

    def test_current_repository_exports_the_three_reviewed_active_targets(self) -> None:
        portfolio = build_active_portfolio(ROOT)
        self.assertEqual(portfolio["schema"], "AMF_ACTIVE_PORTFOLIO_1")
        self.assertEqual(
            [item["problem_id"] for item in portfolio["targets"]],
            [
                "degree-diameter-3-9-record",
                "erdos-64",
                "frontier-stretched-lr",
            ],
        )
        self.assertEqual(
            (ROOT / "data" / "active-portfolio.json").read_bytes(),
            canonical_json_bytes(portfolio) + b"\n",
        )

    def _write_active_catalog(self, root: Path, *, verification_mode: str) -> dict:
        catalog = copy.deepcopy(self.catalog)
        for item in catalog["problems"]:
            item["stage"] = "curated"
        selected = next(
            item for item in catalog["problems"]
            if item["id"] == "cage-cubic-g13-record"
        )
        selected["stage"] = "active"
        selected["verification"]["mode"] = verification_mode
        for key in selected["hard_gates"]:
            selected["hard_gates"][key] = "pass"
        write_json(root / "data" / "problems.json", catalog)
        return selected

    def test_unregistered_fake_verifier_blocks_active_export(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._complete_fixture(root)
            write_json(root / "data" / "verifiers.json", {
                "schema": "AMF_VERIFIER_REGISTRY_1",
                "verifiers": [],
            })
            with self.assertRaisesRegex(ContractError, "unregistered verifier"):
                build_active_portfolio(root)

    def _complete_fixture(
        self,
        root: Path,
        *,
        verifier_id: str = "test-exact-graph-verifier.v1",
        manifest_mode: str | None = None,
        manifest_version: str = "v1",
    ) -> tuple[dict, Path]:
        verification_mode = "exact_graph_regularity_and_girth_checker"
        problem = self._write_active_catalog(root, verification_mode=verification_mode)
        target_dir = root / "targets" / problem["id"]

        verifier_source = root / "verifiers" / "test_checker.py"
        verifier_source.parent.mkdir(parents=True, exist_ok=True)
        verifier_source.write_text("raise SystemExit(0)\n", encoding="utf-8")
        source_binding = make_file_binding(verifier_source, root=root)
        verifier_manifest = {
            "schema": VERIFIER_MANIFEST_SCHEMA,
            "verifier_id": verifier_id,
            "binds_verification_mode": manifest_mode or verification_mode,
            "version": manifest_version,
            "command": [source_binding["path"], "--candidate"],
            "working_directory": ".",
            "timeout_seconds": 30,
            "maximum_output_bytes": 65536,
            "network": False,
            "source_artifacts": [source_binding],
        }
        manifest_path = root / "verifiers" / "test-manifest.json"
        write_json(manifest_path, verifier_manifest)
        manifest_binding = make_file_binding(manifest_path, root=root)
        write_json(root / "data" / "verifiers.json", {
            "schema": "AMF_VERIFIER_REGISTRY_1",
            "verifiers": [{
                "verifier_id": verifier_id,
                "protocol": "AMF_VERIFIER_PROTOCOL_1",
                "manifest": manifest_binding,
            }],
        })

        candidate_schema_path = target_dir / "candidate.schema.json"
        write_json(candidate_schema_path, {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "additionalProperties": False,
            "properties": {"edges": {"type": "array"}},
            "required": ["edges"],
            "type": "object",
        })
        problem_hash = canonical_sha256(problem)
        target_card = {
            "schema": TARGET_CARD_SCHEMA,
            "problem_id": problem["id"],
            "problem_card_sha256": problem_hash,
            "canonical_statement": "Produce a simple connected cubic graph with fewer than 272 vertices and girth at least 13.",
            "source_revision": problem["formalization"]["revision"],
            "claim_scope": "RECORD_IMPROVEMENT",
            "success_criterion": "Both independent exact checkers accept the graph and the frozen baseline is 272.",
            "partial_progress_criterion": "A reproducible improvement inside a frozen construction family.",
            "stop_conditions": ["budget exhausted", "record status changed"],
            "candidate_schema": make_file_binding(candidate_schema_path, root=root),
            "verifier_id": verifier_id,
        }
        target_path = target_dir / "target-card.json"
        write_json(target_path, target_card)
        target_binding = make_file_binding(target_path, root=root)
        target_sha = target_binding["sha256"]

        baseline_artifact = target_dir / "baseline.txt"
        baseline_artifact.write_text("frozen baseline: 272\n", encoding="utf-8")
        baseline_receipt_path = target_dir / "baseline-receipt.json"
        write_json(baseline_receipt_path, {
            "schema": BASELINE_RECEIPT_SCHEMA,
            "problem_id": problem["id"],
            "target_card_sha256": target_sha,
            "baseline_id": "cubic-g13-272",
            "description": "Synthetic test baseline; never a repository research receipt.",
            "source_revision": problem["formalization"]["revision"],
            "checked_at": "2026-08-14",
            "artifacts": [make_file_binding(baseline_artifact, root=root)],
        })

        review_paths = []
        for number, axis in enumerate(("STATEMENT_FIDELITY", "OPEN_STATUS_AND_NOVELTY"), start=1):
            review_report_path = target_dir / f"review-{number}-report.md"
            reviewer_authority_path = target_dir / f"review-{number}-authority.json"
            review_session_path = target_dir / f"review-{number}-session.json"
            review_report_path.write_text(
                f"# Synthetic review {number}\n\nAxis: {axis}\nVerdict: PASS\n",
                encoding="utf-8",
            )
            write_json(reviewer_authority_path, {
                "authority_kind": "SYNTHETIC_TEST_FIXTURE",
                "reviewer_id": f"synthetic-reviewer-{number}",
            })
            write_json(review_session_path, {
                "session_id": f"synthetic-session-{number}",
                "transcript_ref": f"offline-test-fixture-{number}",
            })
            review_path = target_dir / f"review-{number}.json"
            write_json(review_path, {
                "schema": REVIEW_RECEIPT_SCHEMA,
                "problem_id": problem["id"],
                "target_card_sha256": target_sha,
                "review_id": f"synthetic-review-{number}",
                "reviewer_id": f"synthetic-reviewer-{number}",
                "axis": axis,
                "verdict": "PASS",
                "independent_from_solver": True,
                "source_revision": problem["formalization"]["revision"],
                "report": make_file_binding(review_report_path, root=root),
                "reviewer_authority": make_file_binding(reviewer_authority_path, root=root),
                "review_session_evidence": make_file_binding(review_session_path, root=root),
                "attestation_scope": REVIEW_ATTESTATION_SCOPE,
                "checked_at": "2026-08-14",
            })
            review_paths.append(review_path)

        corpus_path = target_dir / "red-team-corpus.json"
        report_path = target_dir / "red-team-report.txt"
        write_json(corpus_path, {"cases": ["reject-loop", "reject-girth-12"]})
        report_path.write_text("2/2 synthetic cases passed\n", encoding="utf-8")
        red_path = target_dir / "red-team-receipt.json"
        write_json(red_path, {
            "schema": RED_TEAM_RECEIPT_SCHEMA,
            "problem_id": problem["id"],
            "target_card_sha256": target_sha,
            "verifier_id": verifier_id,
            "verifier_manifest_sha256": manifest_binding["sha256"],
            "reviewer_id": "synthetic-red-team-reviewer",
            "corpus": make_file_binding(corpus_path, root=root),
            "report": make_file_binding(report_path, root=root),
            "case_count": 2,
            "passed": True,
            "checked_at": "2026-08-14",
        })

        budget_path = target_dir / "budget-receipt.json"
        write_json(budget_path, {
            "schema": BUDGET_RECEIPT_SCHEMA,
            "problem_id": problem["id"],
            "target_card_sha256": target_sha,
            "limits": {
                "context_tokens": 1000,
                "host_context_steers": 1,
                "host_phase_prompts": 1,
                "input_tokens_per_provider_request": 1000,
                "output_tokens_per_provider_request": 1000,
                "provider_request_attempts": 2,
                "tool_calls": 1,
                "verifier_calls": 1,
                "wall_ms": 1000,
            },
            "maximum_artifact_bytes": 1000000,
            "retain_failures": True,
            "stop_conditions": ["budget exhausted"],
            "checked_at": "2026-08-14",
        })

        bundle_path = target_dir / "target-bundle.json"
        write_json(bundle_path, {
            "schema": TARGET_BUNDLE_SCHEMA,
            "problem_id": problem["id"],
            "problem_card_sha256": problem_hash,
            "target_card": target_binding,
            "baseline_receipts": [make_file_binding(baseline_receipt_path, root=root)],
            "review_receipts": [make_file_binding(path, root=root) for path in review_paths],
            "red_team_receipt": make_file_binding(red_path, root=root),
            "budget_receipt": make_file_binding(budget_path, root=root),
        })
        return problem, review_paths[0]

    def test_complete_hash_bound_fixture_exports(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            problem, _review_path = self._complete_fixture(root)
            portfolio = build_active_portfolio(root)
            self.assertEqual([item["problem_id"] for item in portfolio["targets"]], [problem["id"]])
            self.assertEqual(portfolio["targets"][0]["claim_scope"], "RECORD_IMPROVEMENT")
            self.assertEqual(
                portfolio["targets"][0]["verification_mode"],
                problem["verification"]["mode"],
            )
            self.assertEqual(
                portfolio["targets"][0]["verifier_id"],
                "test-exact-graph-verifier.v1",
            )

    def test_verifier_manifest_must_bind_problem_verification_mode(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._complete_fixture(root, manifest_mode="different_semantic_mode")
            with self.assertRaisesRegex(ContractError, "binds_verification_mode"):
                build_active_portfolio(root)

    def test_verifier_id_must_be_versioned(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._complete_fixture(root, verifier_id="unversioned-verifier")
            with self.assertRaisesRegex(ContractError, "text does not match its grammar"):
                build_active_portfolio(root)

    def test_manifest_version_must_match_verifier_id_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._complete_fixture(root, manifest_version="v2")
            with self.assertRaisesRegex(ContractError, "must match the verifier_id version suffix"):
                build_active_portfolio(root)

    def test_hash_drift_in_bound_review_blocks_export(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _problem, review_path = self._complete_fixture(root)
            with review_path.open("ab") as stream:
                stream.write(b" ")
            with self.assertRaisesRegex(ContractError, "file binding .*mismatch"):
                build_active_portfolio(root)

    def test_hash_drift_in_complete_review_report_blocks_export(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _problem, review_path = self._complete_fixture(root)
            report_path = review_path.with_name("review-1-report.md")
            with report_path.open("ab") as stream:
                stream.write(b"tampered\n")
            with self.assertRaisesRegex(ContractError, "review_receipt.report: file binding .*mismatch"):
                build_active_portfolio(root)

    def test_hash_drift_in_review_authority_or_session_evidence_blocks_export(self) -> None:
        for filename, label in (
            ("review-1-authority.json", "reviewer_authority"),
            ("review-1-session.json", "review_session_evidence"),
        ):
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                _problem, review_path = self._complete_fixture(root)
                with review_path.with_name(filename).open("ab") as stream:
                    stream.write(b"tampered\n")
                with self.assertRaisesRegex(
                    ContractError,
                    rf"review_receipt\.{label}: file binding .*mismatch",
                ):
                    build_active_portfolio(root)

    def test_review_receipt_requires_bound_report_and_authority(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            problem, review_path = self._complete_fixture(root)
            original = load_json(review_path)
            for field in ("report", "reviewer_authority"):
                with self.subTest(field=field):
                    receipt = copy.deepcopy(original)
                    receipt.pop(field)
                    with self.assertRaisesRegex(ContractError, "expected exact fields"):
                        validate_review_receipt(
                            receipt,
                            root=root,
                            problem_id=problem["id"],
                            target_card_sha256=receipt["target_card_sha256"],
                            source_revision=problem["formalization"]["revision"],
                        )

    def test_review_receipt_requires_session_evidence_and_source_revision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            problem, review_path = self._complete_fixture(root)
            original = load_json(review_path)

            missing_session = copy.deepcopy(original)
            missing_session.pop("review_session_evidence")
            with self.assertRaisesRegex(ContractError, "expected exact fields"):
                validate_review_receipt(
                    missing_session,
                    root=root,
                    problem_id=problem["id"],
                    target_card_sha256=missing_session["target_card_sha256"],
                    source_revision=problem["formalization"]["revision"],
                )

            wrong_revision = copy.deepcopy(original)
            wrong_revision["source_revision"] = "wrong-revision"
            with self.assertRaisesRegex(ContractError, "does not bind the target source revision"):
                validate_review_receipt(
                    wrong_revision,
                    root=root,
                    problem_id=problem["id"],
                    target_card_sha256=wrong_revision["target_card_sha256"],
                    source_revision=problem["formalization"]["revision"],
                )

    def test_review_evidence_files_must_be_nonempty(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            problem, review_path = self._complete_fixture(root)
            original = load_json(review_path)
            for field in ("report", "reviewer_authority", "review_session_evidence"):
                with self.subTest(field=field):
                    empty_path = root / f"empty-{field}.txt"
                    empty_path.touch()
                    receipt = copy.deepcopy(original)
                    receipt[field] = make_file_binding(empty_path, root=root)
                    with self.assertRaisesRegex(ContractError, "must bind a non-empty artifact"):
                        validate_review_receipt(
                            receipt,
                            root=root,
                            problem_id=problem["id"],
                            target_card_sha256=receipt["target_card_sha256"],
                            source_revision=problem["formalization"]["revision"],
                        )

    def test_review_receipt_scope_disclaims_truth_and_signature(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            problem, review_path = self._complete_fixture(root)
            receipt = load_json(review_path)
            receipt["attestation_scope"] = "MATHEMATICAL_TRUTH"
            with self.assertRaisesRegex(ContractError, "must disclaim"):
                validate_review_receipt(
                    receipt,
                    root=root,
                    problem_id=problem["id"],
                    target_card_sha256=receipt["target_card_sha256"],
                    source_revision=problem["formalization"]["revision"],
                )

    def test_missing_bound_budget_receipt_blocks_export(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            problem, _review_path = self._complete_fixture(root)
            (root / "targets" / problem["id"] / "budget-receipt.json").unlink()
            with self.assertRaisesRegex(ContractError, "unavailable or escapes"):
                build_active_portfolio(root)

    def test_file_binding_rejects_special_and_oversized_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            special = root / "special"
            special.mkdir()
            with self.assertRaisesRegex(ContractError, "regular non-symlink"):
                validate_file_binding(
                    {"path": "special", "bytes": 0, "sha256": "0" * 64},
                    root=root,
                    label="special_binding",
                )

            oversized = root / "oversized.bin"
            with oversized.open("wb") as stream:
                stream.truncate(MAX_BOUND_FILE_BYTES + 1)
            with self.assertRaisesRegex(ContractError, "exceeds maximum"):
                validate_file_binding(
                    {
                        "path": "oversized.bin",
                        "bytes": MAX_BOUND_FILE_BYTES,
                        "sha256": "0" * 64,
                    },
                    root=root,
                    label="oversized_binding",
                )

    def test_json_loader_rejects_duplicate_keys_special_files_and_oversize(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            duplicate = root / "duplicate.json"
            duplicate.write_bytes(b'{"schema":"first","schema":"second"}')
            with self.assertRaisesRegex(ContractError, "duplicate key"):
                load_json(duplicate)

            special = root / "special.json"
            special.mkdir()
            with self.assertRaisesRegex(ContractError, "regular non-symlink"):
                load_json(special)

            oversized = root / "oversized.json"
            with oversized.open("wb") as stream:
                stream.truncate(MAX_JSON_BYTES + 1)
            with self.assertRaisesRegex(ContractError, "JSON input exceeds maximum"):
                load_json(oversized)

    def test_versioned_schema_documents_are_strict_json_objects(self) -> None:
        for path in sorted((ROOT / "schemas").glob("*.json")):
            value = load_json(path)
            self.assertEqual(value["$schema"], "https://json-schema.org/draft/2020-12/schema")
            if value.get("type") == "object":
                self.assertIs(value.get("additionalProperties"), False)


if __name__ == "__main__":
    unittest.main()
