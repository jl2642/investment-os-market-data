from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fmdl6x4e_cross_market_runbook import (
    EXIT_STATUS,
    build_candidate,
    load_json,
    publish,
    validate_candidate,
    validate_contract,
)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")


class Fmdl6x4eTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        source_contract = Path(__file__).parents[1] / "config" / "fmdl6x4e_cross_market_runbook_contract.json"
        target_contract = self.root / "config" / source_contract.name
        target_contract.parent.mkdir(parents=True, exist_ok=True)
        target_contract.write_text(source_contract.read_text(encoding="utf-8"), encoding="utf-8")

        roadmap = self.root / "docs/FMDL-6X3_X4_DEVELOPMENT_ROADMAP.md"
        roadmap.parent.mkdir(parents=True, exist_ok=True)
        roadmap.write_text(
            "- 6X4-E — Cross-market Comparability & Operating Runbook\n"
            "- 6X4-FINAL — US Research Adapter Operational Acceptance & FMDL-6 Freeze\n",
            encoding="utf-8",
        )

        write_json(self.root / "config/post_fmdl4_release8_publication.json", {
            "release_id": "INVESTMENT_OS_R8_20260720_501345e84562",
            "release_sequence": 8,
            "status": "INVESTMENT_OS_CANONICAL_REFRESH_AND_STATE_RECONCILIATION_ACCEPTED",
            "metrics": {"candidate_core_count": 20},
            "trade_authority": "NONE",
        })
        write_json(self.root / "outputs/status/FMDL5_FINAL_LAST_SUCCESS.json", {
            "release_id": "FMDL5FINAL_20260721_a43285d1ee25",
            "release_sequence": 18,
            "status": "FMDL5_HONG_KONG_STOCK_CONNECT_OPERATIONAL_ACCEPTANCE_ACCEPTED",
            "southbound_security_count": 644,
            "common_equity_count": 613,
            "longlist_count": 100,
            "formal_research_object_count": 20,
            "shadow_track_count": 2,
            "trade_authority": "NONE",
        })
        write_json(self.root / "config/fmdl5_final_operational_acceptance.json", {
            "acceptance": {"required_factor_count": 28, "required_graduated_count": 4},
            "capability_matrix": [
                ["A_SHARE_FULL_MARKET_DATA", "OPERATIONAL", "5,528-symbol accepted A-share market and financial evidence chain"],
                ["A_SHARE_SCREENING_AND_RESEARCH", "OPERATIONAL", "100-name research Longlist and governed state routing"],
            ],
        })
        write_json(self.root / "outputs/status/FMDL6X3FINAL_LAST_SUCCESS.json", {
            "phase_id": "FMDL-6X3-FINAL",
            "release_id": "FMDL6X3FINAL_20260723_c9dff24a71f0",
            "release_sequence": 41,
            "status": "FMDL6X3_FINAL_RESEARCH_PRODUCTION_RECONCILIATION_AND_OPERATIONAL_ACCEPTANCE_ACCEPTED",
            "security_universe_count": 8785,
            "benchmark_pool_member_count": 7,
            "formal_candidate_promotion_count": 0,
            "trade_authority": "NONE",
        })
        write_json(self.root / "outputs/status/FMDL6X4D_LAST_SUCCESS.json", {
            "phase_id": "FMDL-6X4-D",
            "release_id": "FMDL6X4D_20260723_1b325920f2b5",
            "release_sequence": 45,
            "status": "FMDL6X4D_SIMULATION_ONLY_PILOT_ATTRIBUTION_AND_FAILURE_RECOVERY_ACCEPTED",
            "next_gate": "FMDL-6X4-E_CROSS_MARKET_COMPARABILITY_AND_OPERATING_RUNBOOK",
            "manifest_sha256": "d" * 64,
            "trade_authority": "NONE",
        })

        droot = self.root / "outputs/fmdl6x4/current/simulation_pilot_attribution_recovery"
        write_json(droot / "FMDL6X4D_DECISION.json", {
            "status": "FMDL6X4D_SIMULATION_ONLY_PILOT_ATTRIBUTION_AND_FAILURE_RECOVERY_ACCEPTED",
            "next_gate": "FMDL-6X4-E_CROSS_MARKET_COMPARABILITY_AND_OPERATING_RUNBOOK",
            "trade_authority": "NONE",
        })
        write_json(droot / "FMDL6X4D_COVERAGE_REPORT.json", {
            "security_control_count": 7,
            "shadow_security_count": 3,
            "shadow_attribution_observation_count": 15,
            "shadow_portfolio_window_count": 5,
        })
        write_json(droot / "FMDL6X4D_ATTRIBUTION_REPORT.json", {
            "market_data_grade": "NON_DECISION_GRADE_FALLBACK",
            "formal_performance_claim": False,
        })
        write_json(droot / "FMDL6X4D_FAILURE_RECOVERY_REPORT.json", {
            "failure_recovery_scenario_count": 10,
            "failure_recovery_pass_count": 10,
            "recovery_checkpoint_count": 4,
        })
        write_json(droot / "FMDL6X4D_FMDL6X4E_HANDOFF.json", {
            "next_gate": "FMDL-6X4-E_CROSS_MARKET_COMPARABILITY_AND_OPERATING_RUNBOOK",
            "trade_authority": "NONE",
        })
        write_json(droot / "FMDL6X4D_MANIFEST.json", {
            "release_id": "FMDL6X4D_20260723_1b325920f2b5",
            "quality_status": "PASS",
            "trade_authority": "NONE",
        })

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_contract_binds_three_markets_and_fmdl6x4d(self) -> None:
        contract, errors = validate_contract(self.root)
        self.assertEqual(errors, [])
        self.assertEqual(set(contract["source_bindings"]), {"A_SHARE", "HONG_KONG_CONNECT", "US_EQUITY"})

    def test_contract_rejects_forced_common_score_authority(self) -> None:
        path = self.root / "config/fmdl6x4e_cross_market_runbook_contract.json"
        contract = load_json(path)
        contract["scope"]["forced_common_factor_score_authorized"] = True
        write_json(path, contract)
        _, errors = validate_contract(self.root)
        self.assertIn("SCOPE_FORCED_COMMON_FACTOR_SCORE_AUTHORIZED", errors)

    def test_build_produces_dimension_level_matrix_without_global_rank(self) -> None:
        candidate = Path("outputs/fmdl6x4e/candidate")
        build_candidate(self.root, candidate, "2026-07-23T06:00:00Z", "abc123")
        matrix = load_json(self.root / candidate / "FMDL6X4E_COMPARABILITY_MATRIX.json")
        self.assertEqual(matrix["comparability_dimension_count"], 14)
        self.assertEqual(matrix["market_dimension_assessment_count"], 42)
        self.assertEqual(matrix["forced_common_factor_score_count"], 0)
        self.assertEqual(matrix["cross_market_security_rank_count"], 0)
        self.assertGreater(matrix["not_comparable_fail_closed_count"], 0)

    def test_market_capabilities_preserve_operational_boundaries(self) -> None:
        candidate = Path("outputs/fmdl6x4e/candidate")
        build_candidate(self.root, candidate, "2026-07-23T06:00:00Z", "abc123")
        report = load_json(self.root / candidate / "FMDL6X4E_CROSS_MARKET_CAPABILITY_REPORT.json")
        markets = {row["market_code"]: row for row in report["markets"]}
        self.assertEqual(markets["A_SHARE"]["security_universe_count"], 5528)
        self.assertEqual(markets["HONG_KONG_CONNECT"]["security_universe_count"], 644)
        self.assertEqual(markets["US_EQUITY"]["security_universe_count"], 8785)
        self.assertEqual(markets["US_EQUITY"]["formal_candidate_or_graduated_count"], 0)
        self.assertFalse(report["cross_market_security_rank_authorized"])

    def test_runbook_and_final_gates_are_complete_and_zero_mutation(self) -> None:
        candidate = Path("outputs/fmdl6x4e/candidate")
        build_candidate(self.root, candidate, "2026-07-23T06:00:00Z", "abc123")
        runbook = load_json(self.root / candidate / "FMDL6X4E_OPERATING_RUNBOOK.json")
        final = load_json(self.root / candidate / "FMDL6X4E_FINAL_GATE_REPORT.json")
        quality = load_json(self.root / candidate / "FMDL6X4E_QUALITY_REPORT.json")
        self.assertEqual(runbook["runbook_step_count"], 12)
        self.assertEqual(runbook["cadence_control_count"], 5)
        self.assertTrue(final["all_final_gates_pass"])
        self.assertEqual(final["final_gate_count"], 8)
        self.assertEqual(quality["actual_shard_count"], 448)
        self.assertEqual(quality["zero_mutation_proof"], {
            "candidate_pool_mutations": 0,
            "simulation_book_mutations": 0,
            "real_account_mutations": 0,
            "orders": 0,
        })

    def test_same_input_replay_is_byte_identical(self) -> None:
        candidate = Path("outputs/fmdl6x4e/candidate")
        build_candidate(self.root, candidate, "2026-07-23T06:00:00Z", "abc123")
        result = validate_candidate(
            self.root,
            candidate,
            "2026-07-23T06:00:00Z",
            "abc123",
            Path("outputs/fmdl6x4e/acceptance/result.json"),
        )
        self.assertTrue(result["same_input_byte_replay"])

    def test_publish_creates_release_current_normalized_and_pointers(self) -> None:
        candidate = Path("outputs/fmdl6x4e/candidate")
        manifest = build_candidate(self.root, candidate, "2026-07-23T06:00:00Z", "abc123")
        pointer = publish(self.root, candidate, "2026-07-23T06:01:00Z", "abc123")
        self.assertEqual(pointer["status"], EXIT_STATUS)
        self.assertEqual(pointer["release_sequence"], 46)
        self.assertEqual(pointer["release_id"], manifest["release_id"])
        self.assertTrue((self.root / pointer["current_path"] / "FMDL6X4E_MANIFEST.json").is_file())
        self.assertTrue((self.root / pointer["release_path"] / "FMDL6X4E_MANIFEST.json").is_file())
        self.assertEqual(pointer["trade_authority"], "NONE")


if __name__ == "__main__":
    unittest.main()
