from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from sync_sources import parse_erdos, parse_formal_open, retrieval_date  # noqa: E402


class SyncTests(unittest.TestCase):
    def test_extracts_only_research_open_declarations(self) -> None:
        source = """
@[category research open, AMS 5]
theorem wanted : True := by trivial

@[category research solved, AMS 5]
theorem ignored : True := by trivial

@[category research open]
noncomputable def wantedToo : Nat := 1
"""
        result = parse_formal_open([("FormalConjectures/Test.lean", source)], "abc123", "2026-08-14")
        self.assertEqual([item["declaration"] for item in result["declarations"]], ["wanted", "wantedToo"])
        self.assertEqual(result["declaration_count"], 2)
        self.assertIn("/blob/abc123/", result["declarations"][0]["artifact_url"])

    def test_erdos_index_omits_statement_text(self) -> None:
        raw = b"""- number: \"1\"\n  status: {state: open}\n  statement: do not copy me\n  tags: [number theory]\n"""
        result = parse_erdos(raw, "deadbeef", "2026-08-14")
        self.assertEqual(result["problem_count"], 1)
        self.assertNotIn("statement", result["problems"][0])
        self.assertEqual(result["problems"][0]["problem_url"], "https://www.erdosproblems.com/1")

    def test_retrieval_date_stays_stable_without_revision_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "index.json"
            path.write_text(
                json.dumps({"upstream_revision": "same", "retrieved_at": "2026-08-14"}),
                encoding="utf-8",
            )
            self.assertEqual(retrieval_date(path, "same", None), "2026-08-14")
            self.assertEqual(retrieval_date(path, "same", "2026-09-01"), "2026-09-01")


if __name__ == "__main__":
    unittest.main()
