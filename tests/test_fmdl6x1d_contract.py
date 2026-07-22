from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, "scripts")
from validate_fmdl6x1d_contract import CONTRACT_PATH, load_json, publish, validate_contract, validate_publication  # noqa: E402


class Fmdl6x1dContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Path(__file__).resolve().parents[1]
        self.contract = load_json(self.repo / CONTRACT_PATH)

    def test_contract_passes(self) -> None:
        checks, errors = validate_contract(self.repo)
        self.assertGreater(len(checks), 40)
        self.assertEqual(errors, [])

    def test_exact_six_phase_handoff(self) -> None:
        self.assertEqual(
            [item["phase_id"] for item in self.contract["fmdl6x2_fixed_execution_plan"]],
            ["FMDL-6X2-A", "FMDL-6X2-B", "FMDL-6X2-C", "FMDL-6X2-D", "FMDL-6X2-E", "FMDL-6X2-FINAL"],
        )

    def test_final_gate_precedes_fmdl6x2(self) -> None:
        self.assertEqual(self.contract["phase_exit"]["next_gate"], "FMDL-6X1-FINAL_OPERATIONAL_ACCEPTANCE")
        self.assertIn("FMDL6X1_FINAL_ACCEPTED", self.contract["fmdl6x2_entry_gates"]["program_entry_requires"])

    def test_sec_proxy_forbidden_and_executor_proof_required(self) -> None:
        sec = self.contract["source_execution_contract"]["sec_official_ingestion"]
        self.assertFalse(sec["third_party_sec_proxy_authorized"])
        self.assertTrue(self.contract["fmdl6x2_entry_gates"]["phase_e_requires_sec_official_executor_proof"])

    def test_history_cannot_invent_dates(self) -> None:
        historical = self.contract["source_execution_contract"]["historical_listing_and_lifecycle"]
        self.assertFalse(historical["observation_only_may_be_represented_as_exact_effective_date"])
        self.assertIn("NO_CURRENT_ONLY_SURVIVORSHIP_BACKFILL", self.contract["quality_gates"]["point_in_time"])

    def test_partial_shard_cannot_promote(self) -> None:
        self.assertFalse(self.contract["storage_and_sharding"]["partial_shard_may_replace_current"])
        self.assertFalse(self.contract["publication_and_recovery"]["failed_run_may_replace_lkg"])

    def test_paid_route_not_authorized(self) -> None:
        cost = self.contract["cost_and_runtime_policy"]
        self.assertEqual(cost["paid_subscription_budget_usd"], 0)
        self.assertTrue(cost["paid_api_or_dataset_activation_requires_user_approval"])

    def test_negative_scope_mutation_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir) / "repo"
            shutil.copytree(self.repo, temp, dirs_exist_ok=True)
            path = temp / CONTRACT_PATH
            contract = load_json(path)
            contract["scope"]["live_security_master_build_authorized"] = True
            path.write_text(json.dumps(contract), encoding="utf-8")
            _, errors = validate_contract(temp)
            self.assertIn("SCOPE_FALSE:live_security_master_build_authorized", errors)

    def test_publication_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir) / "repo"
            shutil.copytree(self.repo, temp, dirs_exist_ok=True)
            pointer = publish(temp, "TEST_COMMIT")
            self.assertEqual(pointer["status"], "FMDL6X1D_FULL_BUILD_CONTRACT_AND_FMDL6X2_HANDOFF_ACCEPTED")
            checks, errors = validate_publication(temp)
            self.assertGreater(len(checks), 10)
            self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
