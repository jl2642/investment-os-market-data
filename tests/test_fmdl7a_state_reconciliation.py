from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts/fmdl7a_state_reconciliation.py"
SPEC = importlib.util.spec_from_file_location("fmdl7a_state_reconciliation", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FMDL7AStateReconciliationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = MODULE.read_json(REPO_ROOT / MODULE.CONTRACT_PATH)

    def test_frozen_contract_and_sources_validate(self) -> None:
        errors, source_hashes = MODULE.validate_contract(REPO_ROOT, self.contract)
        self.assertEqual(errors, [])
        self.assertEqual(len(self.contract["source_bindings"]), 7)
        self.assertEqual(len(source_hashes), 8)
        self.assertEqual(self.contract["trade_authority"], "NONE")

    def test_same_input_build_is_byte_identical(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "first"
            second = Path(tmp) / "second"
            MODULE.build_candidate(REPO_ROOT, first, "2026-07-23T07:00:00Z", "test-source-commit")
            MODULE.build_candidate(REPO_ROOT, second, "2026-07-23T07:00:00Z", "test-source-commit")
            self.assertEqual(MODULE.directory_digest(first), MODULE.directory_digest(second))
            self.assertEqual(sorted(path.name for path in first.iterdir()), sorted(path.name for path in second.iterdir()))

    def test_decision_fails_closed_on_new_decision_and_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "candidate"
            result = MODULE.build_candidate(REPO_ROOT, output, "2026-07-23T07:00:00Z", "test-source-commit")
            decision = MODULE.read_json(output / "FMDL7A_DECISION.json")
            quality = MODULE.read_json(output / "FMDL7A_QUALITY_REPORT.json")
            self.assertEqual(decision["status"], MODULE.EXIT_STATUS)
            self.assertEqual(decision["next_gate"], MODULE.NEXT_GATE)
            self.assertEqual(decision["a_share_new_decision_state"], "BLOCKED_PENDING_REFRESH")
            self.assertIn("LAST_KNOWN_GOOD", decision["investment_state_posture"])
            self.assertEqual(decision["trade_authority"], "NONE")
            self.assertEqual(sum(decision["zero_mutation_proof"].values()), 0)
            self.assertEqual(quality["quality_status"], "PASS")
            self.assertEqual(quality["acceptance_gate_count"], 16)
            self.assertEqual(result["release_id"], decision["release_id"])

    def test_state_and_duplication_registries_are_complete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "candidate"
            MODULE.build_candidate(REPO_ROOT, output, "2026-07-23T07:00:00Z", "test-source-commit")
            state = MODULE.read_json(output / "FMDL7A_STATE_DOMAIN_REGISTRY.json")
            duplication_rows = MODULE.read_csv(output / "FMDL7A_CROSS_MARKET_DUPLICATION_REGISTRY.csv")
            self.assertEqual(len(state["real_account"]["holdings"]), 7)
            self.assertEqual(len(state["simulation_book"]["holdings"]), 16)
            self.assertEqual(len(state["candidate_pool"]["core_members"]), 20)
            self.assertTrue(state["post_as_of_user_confirmation_required"])
            self.assertEqual(len(duplication_rows), 3)
            self.assertEqual(duplication_rows[0]["security_ids"], "159612|159655")
            self.assertEqual(sorted(row["security_ids"] for row in duplication_rows[1:]), ["HKEX:00300", "HKEX:02359"])

    def test_authority_breach_is_rejected(self) -> None:
        bad = copy.deepcopy(self.contract)
        bad["scope"]["candidate_pool_mutation_authorized"] = True
        errors, _ = MODULE.validate_contract(REPO_ROOT, bad)
        self.assertIn("SCOPE_NOT_FAIL_CLOSED:candidate_pool_mutation_authorized", errors)

    def test_file_library_observation_does_not_overclaim_binary_verification(self) -> None:
        observation = self.contract["file_library_observation"]
        self.assertEqual(observation["pointer_status"], "DISCOVERABLE_AND_CONTENT_READABLE")
        self.assertTrue(observation["canonical_zip_status"].startswith("NOT_INDEPENDENTLY_RETRIEVABLE"))
        self.assertFalse(observation["conversation_memory_authoritative"])


if __name__ == "__main__":
    unittest.main()
