from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from contracts import canonical_json_bytes, load_json  # noqa: E402
from export_experimental import build_experimental_portfolio  # noqa: E402


class ExperimentalPortfolioTests(unittest.TestCase):
    def test_exactly_all_machine_addressable_problems_are_exported(self) -> None:
        catalog = load_json(ROOT / "data" / "problems.json")
        expected = sorted(
            problem["id"]
            for problem in catalog["problems"]
            if problem["formalization"]["level"] in {"proof_assistant", "executable_spec"}
        )
        portfolio = build_experimental_portfolio(ROOT)
        self.assertEqual(len(expected), 14)
        self.assertEqual(
            [target["problem_id"] for target in portfolio["targets"]],
            expected,
        )
        self.assertEqual(
            portfolio["summary"],
            {
                "audited_active": 3,
                "experimental_active": 11,
                "total": 14,
                "verifier_regression_only": 0,
            },
        )

    def test_canonical_export_is_current(self) -> None:
        portfolio = build_experimental_portfolio(ROOT)
        self.assertEqual(portfolio["schema"], "AMF_EXPERIMENTAL_PORTFOLIO_1")
        self.assertEqual(
            (ROOT / "data" / "experimental-portfolio.json").read_bytes(),
            canonical_json_bytes(portfolio) + b"\n",
        )

    def test_every_target_card_and_verifier_is_a_real_bound_file(self) -> None:
        portfolio = build_experimental_portfolio(ROOT)
        registry = json.loads((ROOT / "data" / "verifiers.json").read_text())
        registered = {entry["verifier_id"] for entry in registry["verifiers"]}
        self.assertEqual(len(registered), 15)
        for target in portfolio["targets"]:
            self.assertIn(target["verifier_id"], registered)
            self.assertTrue((ROOT / target["target_card"]["path"]).is_file())

    def test_aim_v2_is_experimental_while_its_failed_open_gate_stays_visible(self) -> None:
        portfolio = build_experimental_portfolio(ROOT)
        aim = next(
            target for target in portfolio["targets"]
            if target["problem_id"] == "aim-60-first-prime"
        )
        self.assertEqual(aim["role"], "experimental_active")
        self.assertEqual(aim["verifier_id"], "amf.aim60.certificate.v2")
        self.assertEqual(aim["strict_stage"], "curated")
        self.assertEqual(aim["hard_gates"]["open_status"], "fail")


if __name__ == "__main__":
    unittest.main()
