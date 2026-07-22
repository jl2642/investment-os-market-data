from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, "scripts")
from validate_fmdl6x1_final import (CONTRACT_PATH, build_candidate, collect_model, compare_candidate_trees, evaluate_model, load_json, run_clean_room_restore, run_failure_injections, validate_contract)


class Fmdl6x1FinalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Path(__file__).resolve().parents[1]
        self.contract = load_json(self.repo / CONTRACT_PATH)
        self.accepted_at = "2026-07-22T12:00:00Z"
        self.source_commit = "test-source-commit"

    def test_contract_chain_and_clean_restore(self) -> None:
        checks, errors = validate_contract(self.repo)
        self.assertGreater(len(checks), 10)
        self.assertEqual(errors, [])
        restored = run_clean_room_restore(self.repo, self.contract)
        self.assertEqual(restored["status"], "PASS")
        self.assertGreater(restored["restored_file_count"], 10)

    def test_all_nine_failure_injections_are_detected(self) -> None:
        result = run_failure_injections(self.repo, self.contract)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["scenario_count"], 9)
        self.assertEqual(result["detected_count"], 9)

    def test_candidate_and_replay_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            left = Path(tmp) / "left"
            right = Path(tmp) / "right"
            decision = build_candidate(self.repo, left, self.accepted_at, self.source_commit)
            build_candidate(self.repo, right, self.accepted_at, self.source_commit)
            same, errors = compare_candidate_trees(left, right)
            self.assertEqual(decision["status"], "FMDL6X1_FINAL_ACCEPTED")
            self.assertTrue(same, errors)
            required = set(self.contract["fmdl6x2_entry"]["required_handoff_assets"])
            self.assertTrue(required <= {path.name for path in left.iterdir()})

    def test_dual_gate_and_zero_authority(self) -> None:
        gates = self.contract["dual_gate_final_state"]
        self.assertEqual(gates["research_production_gate"], "OPEN_FOR_FMDL6X2_DATA_PRODUCTION")
        self.assertEqual(gates["brokerage_real_account_gate"], "CLOSED_NO_CHANNEL")
        self.assertEqual(self.contract["trade_authority"], "NONE")
        self.assertTrue(all(value == 0 for value in self.contract["zero_mutation_gate"].values()))

    def test_fixed_six_phase_sequence(self) -> None:
        self.assertEqual(self.contract["fmdl6x2_entry"]["required_phase_sequence"], ["FMDL-6X2-A", "FMDL-6X2-B", "FMDL-6X2-C", "FMDL-6X2-D", "FMDL-6X2-E", "FMDL-6X2-FINAL"])

    def test_open_brokerage_gate_is_rejected(self) -> None:
        model = collect_model(self.repo, self.contract)
        mutated = copy.deepcopy(model)
        mutated["assets"]["FMDL-6X1-A"]["dual_activation"]["brokerage_real_account_gate"]["status"] = "OPEN"
        self.assertIn("BROKERAGE_GATE_NOT_CLOSED", evaluate_model(self.contract, mutated))


if __name__ == "__main__":
    unittest.main()
