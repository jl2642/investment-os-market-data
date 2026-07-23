from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.fmdl7b_lineage_acceptance import (
    EXIT_STATUS,
    build_candidate,
    read_json,
    validate_contract,
)


class FMDL7BLineageAcceptanceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parents[1]

    def test_contract_and_bound_sources(self) -> None:
        contract, errors = validate_contract(self.repo_root)
        self.assertEqual([], errors)
        self.assertEqual("FMDL-7B", contract["phase_id"])
        self.assertEqual(3, contract["acceptance_gates"]["market_count"])
        self.assertEqual(19, contract["acceptance_gates"]["cross_market_lineage_count"])
        self.assertEqual("NONE", contract["trade_authority"])

    def test_build_and_same_input_byte_replay(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "first"
            second = root / "second"
            kwargs = {
                "repo_root": self.repo_root,
                "generated_at": "2026-07-23T08:00:00Z",
                "source_commit": "TEST_SOURCE_COMMIT",
            }
            decision_a = build_candidate(output_dir=first, **kwargs)
            decision_b = build_candidate(output_dir=second, **kwargs)
            self.assertEqual(EXIT_STATUS, decision_a["status"])
            self.assertEqual(decision_a, decision_b)
            first_files = sorted(path.name for path in first.iterdir() if path.is_file())
            second_files = sorted(path.name for path in second.iterdir() if path.is_file())
            self.assertEqual(first_files, second_files)
            for name in first_files:
                self.assertEqual((first / name).read_bytes(), (second / name).read_bytes(), name)

            quality = read_json(first / "FMDL7B_QUALITY_REPORT.json")
            self.assertEqual("PASS", quality["quality_status"])
            self.assertEqual(19, quality["cross_market_lineage_count"])
            self.assertEqual(19, quality["lineage_pass_count"])
            self.assertEqual(0, quality["orphan_lineage_count"])
            self.assertEqual(0, quality["duplicate_lineage_identity_count"])
            self.assertEqual(0, quality["automatic_candidate_promotion_count"])
            self.assertEqual(0, quality["investment_recommendation_count"])
            self.assertEqual(7, quality["failure_injection_count"])
            self.assertEqual(384, quality["logical_shard_count"])
            self.assertEqual("NONE", quality["trade_authority"])

            failures = read_json(first / "FMDL7B_FAILURE_INJECTION_RESULTS.json")
            self.assertTrue(failures["all_rejected_as_required"])
            self.assertEqual(7, len(failures["results"]))
            self.assertTrue(all(row["status"] == "REJECTED_AS_REQUIRED" for row in failures["results"]))


if __name__ == "__main__":
    unittest.main()
