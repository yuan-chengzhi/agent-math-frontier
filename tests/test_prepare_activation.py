from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from contracts import (  # noqa: E402
    ContractError,
    canonical_json_bytes,
    canonical_sha256,
    load_json,
    raw_sha256,
)
from prepare_activation import (  # noqa: E402
    ALLOWED_TARGETS,
    AUTHORITY_SCHEMA,
    BRIEF_SCHEMA,
    CHECKED_AT,
    EXACT_LIMITS,
    EXACT_MAXIMUM_ARTIFACT_BYTES,
    EXACT_STOP_CONDITIONS,
    OPEN_STATUS_REVIEWER,
    SESSION_SCHEMA,
    STATEMENT_REVIEWER,
    ActivationError,
    check_outputs,
    prepare_activation,
    validate_agent_brief,
    validate_plan,
    write_outputs,
)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value) + b"\n")


def copy_activation_fixture(destination: Path) -> Path:
    root = destination / "repo"
    root.mkdir()
    for relative in ("activation", "schemas", "scripts", "targets", "tests", "verifiers"):
        ignored = (
            shutil.ignore_patterns("__pycache__", "target-bundle.json", "receipts", "process")
            if relative == "targets"
            else shutil.ignore_patterns("__pycache__")
        )
        shutil.copytree(ROOT / relative, root / relative, ignore=ignored)
    (root / "data").mkdir()
    for filename in ("problems.json", "verifiers.json"):
        shutil.copy2(ROOT / "data" / filename, root / "data" / filename)
    return root


def materialize_process_evidence(root: Path) -> None:
    plan = load_json(root / "activation/pmw-frontier-choice-2026-08-14.json")
    catalog = load_json(root / "data/problems.json")
    problems = {problem["id"]: problem for problem in catalog["problems"]}
    for target in plan["targets"]:
        problem_id = target["problem_id"]
        target_path = root / f"targets/{problem_id}/target-card.json"
        target_sha = raw_sha256(target_path)
        problem_sha = canonical_sha256(problems[problem_id])
        for kind in ("statement", "open_status"):
            review = target["reviews"][kind]
            authority = {
                "schema": AUTHORITY_SCHEMA,
                "reviewer_id": review["reviewer_id"],
                "authority_kind": "HOST_ASSIGNED_CODEX_SUBAGENT_ROLE",
                "reviewer_task_path": review["reviewer_task_path"],
                "problem_id": problem_id,
                "axis": review["axis"],
                "solver_role": False,
                "domain_expert_claimed": False,
                "external_identity_verified": False,
                "cryptographic_signature_present": False,
                "attestation_scope": "PROCESS_PROVENANCE_ONLY_NOT_MATHEMATICAL_TRUTH",
                "recorded_at": "2026-08-14T00:00:00+08:00",
                "limitations": [
                    "Conversation-local host assignment only; no external identity, domain-expert credential, mathematical-truth attestation, or signature is claimed."
                ],
            }
            session = {
                "schema": SESSION_SCHEMA,
                "reviewer_id": review["reviewer_id"],
                "reviewer_task_path": review["reviewer_task_path"],
                "problem_id": problem_id,
                "axis": review["axis"],
                "verdict": review["verdict"],
                "report_path": review["report"],
                "report_sha256": raw_sha256(root / review["report"]),
                "reviewed_problem_card_sha256": problem_sha,
                "reviewed_target_card_sha256": target_sha,
                "solver_lives_started_at_review": 0,
                "completion_observed_by_host": True,
                "session_reference_kind": "CONVERSATION_LOCAL_TASK_PATH",
                "provider_session_id": None,
                "transcript_ref": None,
                "recorded_at": "2026-08-14T00:00:01+08:00",
                "limitations": [
                    "The host observed conversation-local task completion; no portable transcript, provider session identity, cryptographic signature, or mathematical-truth guarantee is asserted."
                ],
            }
            write_json(root / review["reviewer_authority"], authority)
            write_json(root / review["review_session_evidence"], session)


class PrepareActivationTests(unittest.TestCase):
    def test_checked_plan_is_exactly_three_allowed_targets_and_exact_budget(self) -> None:
        plan = validate_plan(load_json(ROOT / "activation/pmw-frontier-choice-2026-08-14.json"))
        self.assertEqual([item["problem_id"] for item in plan["targets"]], list(ALLOWED_TARGETS))
        self.assertEqual(plan["budget"]["limits"], EXACT_LIMITS)
        self.assertEqual(plan["budget"]["maximum_artifact_bytes"], EXACT_MAXIMUM_ARTIFACT_BYTES)
        self.assertEqual(plan["budget"]["stop_conditions"], list(EXACT_STOP_CONDITIONS))
        self.assertEqual(
            plan["targets"][0]["reviews"]["statement"]["reviewer_id"],
            STATEMENT_REVIEWER["reviewer_id"],
        )
        self.assertEqual(
            plan["targets"][0]["reviews"]["open_status"]["reviewer_id"],
            OPEN_STATUS_REVIEWER["reviewer_id"],
        )

    def test_plan_rejects_extra_target_aim_and_budget_drift(self) -> None:
        original = load_json(ROOT / "activation/pmw-frontier-choice-2026-08-14.json")
        extra = copy.deepcopy(original)
        aim = copy.deepcopy(extra["targets"][0])
        aim["problem_id"] = "aim-60-first-prime"
        extra["targets"].append(aim)
        with self.assertRaisesRegex(ActivationError, "exactly the sorted, unique allowlist"):
            validate_plan(extra)
        drift = copy.deepcopy(original)
        drift["budget"]["limits"]["verifier_calls"] = 64
        with self.assertRaisesRegex(ActivationError, "frozen runtime caps"):
            validate_plan(drift)
        reordered = copy.deepcopy(original)
        reordered["budget"]["stop_conditions"].reverse()
        with self.assertRaisesRegex(ActivationError, "eight frozen conditions"):
            validate_plan(reordered)

    def test_strict_json_rejects_duplicate_plan_keys(self) -> None:
        body = (ROOT / "activation/pmw-frontier-choice-2026-08-14.json").read_text(encoding="utf-8")
        body = body.replace(
            '  "schema": "AMF_ACTIVATION_PLAN_1",',
            '  "schema": "AMF_ACTIVATION_PLAN_1",\n  "schema": "AMF_ACTIVATION_PLAN_1",',
            1,
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.json"
            path.write_text(body, encoding="utf-8")
            with self.assertRaisesRegex(ContractError, "duplicate key"):
                load_json(path)

    def test_agent_brief_is_neutral_strict_and_route_ids_are_unique_https(self) -> None:
        for problem_id in ALLOWED_TARGETS:
            with self.subTest(problem_id=problem_id):
                brief = load_json(ROOT / f"targets/{problem_id}/evidence/baseline/agent-brief.json")
                route_ids = validate_agent_brief(brief, problem_id=problem_id, checked_at=CHECKED_AT)
                self.assertEqual(len(route_ids), len(brief["known_route_baselines"]))
                self.assertEqual(brief["schema"], BRIEF_SCHEMA)
        sample = load_json(ROOT / "targets/erdos-64/evidence/baseline/agent-brief.json")
        polluted = copy.deepcopy(sample)
        polluted["recommendation"] = "choose me"
        with self.assertRaisesRegex(ActivationError, "expected exact fields"):
            validate_agent_brief(polluted, problem_id="erdos-64", checked_at=CHECKED_AT)
        duplicate = copy.deepcopy(sample)
        duplicate["known_route_baselines"].append(copy.deepcopy(duplicate["known_route_baselines"][0]))
        with self.assertRaisesRegex(ActivationError, "grammatical and unique"):
            validate_agent_brief(duplicate, problem_id="erdos-64", checked_at=CHECKED_AT)
        insecure = copy.deepcopy(sample)
        insecure["known_route_baselines"][0]["source"] = "http://example.com/not-https"
        with self.assertRaisesRegex(ActivationError, "HTTPS"):
            validate_agent_brief(insecure, problem_id="erdos-64", checked_at=CHECKED_AT)

    def test_missing_process_evidence_fails_without_inference(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = copy_activation_fixture(Path(directory))
            with self.assertRaisesRegex(ContractError, "unavailable|invalid JSON"):
                prepare_activation(root=root, test_runner=lambda *_args: None)

    def test_end_to_end_build_write_check_and_identical_replay(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = copy_activation_fixture(Path(directory))
            materialize_process_evidence(root)
            calls: list[tuple[str, tuple[str, str], int]] = []

            def runner(_root: Path, problem_id: str, modules: tuple[str, str], timeout: int) -> None:
                calls.append((problem_id, modules, timeout))

            prepared = prepare_activation(root=root, test_runner=runner)
            self.assertEqual([call[0] for call in calls], list(ALLOWED_TARGETS))
            self.assertEqual(len(prepared.outputs), 19)
            for path in prepared.outputs:
                self.assertNotIn("aim-60-first-prime", path)
            created = write_outputs(root, prepared)
            self.assertEqual(len(created), 19)
            check_outputs(root, prepared)
            self.assertEqual(write_outputs(root, prepared), ())
            budget_path = root / (
                "targets/erdos-64/evidence/receipts/"
                "budget-pmw-frontier-choice-2026-08-14.json"
            )
            budget = load_json(budget_path)
            self.assertEqual(budget["limits"], EXACT_LIMITS)
            self.assertEqual(budget["stop_conditions"], list(EXACT_STOP_CONDITIONS))
            dd_baseline = load_json(
                root / "targets/degree-diameter-3-9-record/evidence/receipts/"
                "baseline-pmw-frontier-choice-2026-08-14.json"
            )
            names = {Path(binding["path"]).name for binding in dd_baseline["artifacts"]}
            self.assertFalse({"Exoo_600.txt", "Exoo_600.normalized.json"}.intersection(names))

    def test_stale_output_blocks_all_writes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = copy_activation_fixture(Path(directory))
            materialize_process_evidence(root)
            prepared = prepare_activation(root=root, test_runner=lambda *_args: None)
            write_json(root / "data/active-portfolio.json", {"stale": True})
            with self.assertRaisesRegex(ActivationError, "refusing to overwrite"):
                write_outputs(root, prepared)
            self.assertFalse(any((root / f"targets/{problem_id}/evidence/receipts").exists() for problem_id in ALLOWED_TARGETS))

    def test_changed_process_binding_and_manifest_drift_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = copy_activation_fixture(Path(directory))
            materialize_process_evidence(root)
            plan = load_json(root / "activation/pmw-frontier-choice-2026-08-14.json")
            session_path = root / plan["targets"][0]["reviews"]["statement"]["review_session_evidence"]
            session = load_json(session_path)
            session["report_sha256"] = "0" * 64
            write_json(session_path, session)
            with self.assertRaisesRegex(ActivationError, "completed review process"):
                prepare_activation(root=root, test_runner=lambda *_args: None)

        with tempfile.TemporaryDirectory() as directory:
            root = copy_activation_fixture(Path(directory))
            materialize_process_evidence(root)
            changed = False

            def drifting_runner(_root: Path, _problem_id: str, _modules: tuple[str, str], _timeout: int) -> None:
                nonlocal changed
                if not changed:
                    with (_root / "scripts/contracts.py").open("ab") as stream:
                        stream.write(b"\n")
                    changed = True

            with self.assertRaisesRegex(ActivationError, "changed while frozen tests"):
                prepare_activation(root=root, test_runner=drifting_runner)


if __name__ == "__main__":
    unittest.main()
