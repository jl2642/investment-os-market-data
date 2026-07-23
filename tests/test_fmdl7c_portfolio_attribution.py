from __future__ import annotations

import filecmp
import shutil
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import fmdl7c_portfolio_attribution as fmdl7c  # noqa: E402


class FMDL7CPortfolioAttributionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract, self.errors, self.source_hashes = fmdl7c.validate_contract(ROOT)
        self.assertEqual([], self.errors)
        self.sources = fmdl7c.load_sources(ROOT, self.contract)

    def test_contract_and_authority_boundaries(self) -> None:
        self.assertEqual("FMDL-7C", self.contract["phase_id"])
        self.assertEqual("NONE", self.contract["trade_authority"])
        self.assertFalse(self.contract["scope"]["live_trade_recommendation_authorized"])
        self.assertFalse(self.contract["scope"]["candidate_pool_mutation_authorized"])
        self.assertFalse(self.contract["scope"]["simulation_book_mutation_authorized"])
        self.assertFalse(self.contract["scope"]["real_account_mutation_authorized"])
        self.assertFalse(self.contract["scope"]["rule_mutation_authorized"])
        self.assertEqual(6, len(self.contract["source_bindings"]))
        self.assertEqual(8, len(self.contract["rule_calibration_proposals"]))
        self.assertEqual(8, len(self.contract["failure_injections"]))

    def test_real_account_attribution_reconciles(self) -> None:
        records, summary = fmdl7c.build_real_account(self.sources, self.contract)
        self.assertEqual(7, len(records))
        self.assertEqual(4, summary["stock_etf_count"])
        self.assertEqual(3, summary["bond_fund_count"])
        self.assertEqual(Decimal("448831.42"), summary["total_assets"])
        self.assertEqual(Decimal("452382.98"), summary["invested_cost_estimate"])
        self.assertEqual(Decimal("-3672.05"), summary["mark_to_cost_pnl_estimate"])
        self.assertEqual(Decimal("-7036.60"), summary["stock_etf_pnl_estimate"])
        self.assertEqual(Decimal("3364.55"), summary["bond_fund_pnl_estimate"])
        self.assertEqual(Decimal("0.00"), summary["snapshot_reconciliation_difference"])
        self.assertFalse(summary["total_return_claimed"])

    def test_simulation_attribution_and_pnl_bridge(self) -> None:
        records, summary = fmdl7c.build_simulation(self.sources, self.contract)
        self.assertEqual(16, len(records))
        self.assertEqual(Decimal("782180.60"), summary["market_value"])
        self.assertEqual(Decimal("219533.98"), summary["available_cash"])
        self.assertEqual(Decimal("1001714.58"), summary["total_assets"])
        self.assertEqual(Decimal("1714.58"), summary["account_total_pnl"])
        self.assertEqual(Decimal("10165.00"), summary["open_position_unrealized_pnl"])
        self.assertEqual(Decimal("-8450.42"), summary["closed_fee_other_residual"])
        self.assertEqual(Decimal("0.00"), summary["pnl_bridge_check"])
        self.assertEqual(10, summary["positive_position_count"])
        self.assertEqual(6, summary["negative_position_count"])
        self.assertEqual(Decimal("48647.00"), summary["positive_contribution"])
        self.assertEqual(Decimal("-38482.00"), summary["negative_contribution"])
        self.assertEqual(4, summary["no_add_count"])
        self.assertEqual(2, summary["hard_review_count"])
        self.assertEqual(13, summary["candidate_core_overlap_count"])

    def test_candidate_triggers_and_overlap(self) -> None:
        simulation_records, _ = fmdl7c.build_simulation(self.sources, self.contract)
        records, summary = fmdl7c.build_candidate_review(self.sources, simulation_records, self.contract)
        self.assertEqual(20, len(records))
        self.assertEqual(6, summary["active_memo_count"])
        self.assertEqual(0, summary["active_memo_trigger_met_count"])
        self.assertEqual(13, summary["simulation_overlap_count"])
        self.assertEqual(0, summary["formal_membership_change_count"])
        self.assertFalse(summary["candidate_alpha_claimed"])

    def test_failure_injections_fail_closed(self) -> None:
        simulation_records, simulation_summary = fmdl7c.build_simulation(self.sources, self.contract)
        _, candidate_summary = fmdl7c.build_candidate_review(self.sources, simulation_records, self.contract)
        results = fmdl7c.run_failure_injections(simulation_summary, candidate_summary, self.contract)
        self.assertEqual(8, len(results))
        self.assertTrue(all(row["status"] == "REJECTED_AS_REQUIRED" for row in results))
        self.assertTrue(all(row["current_replacement_authorized"] is False for row in results))
        self.assertTrue(all(row["lkg_replacement_authorized"] is False for row in results))
        self.assertTrue(all(row["trade_authority"] == "NONE" for row in results))

    def test_build_and_same_input_byte_replay(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "first"
            second = root / "second"
            generated_at = "2026-07-23T08:00:00Z"
            source_commit = "0123456789abcdef"
            first_decision = fmdl7c.build_candidate(ROOT, first, generated_at, source_commit)
            second_decision = fmdl7c.build_candidate(ROOT, second, generated_at, source_commit)
            self.assertEqual(first_decision["release_id"], second_decision["release_id"])
            self.assertEqual(fmdl7c.EXIT_STATUS, first_decision["status"])
            self.assertEqual([], fmdl7c.validate_candidate(first, self.contract))
            comparison = filecmp.dircmp(first, second)
            self.assertEqual([], comparison.left_only)
            self.assertEqual([], comparison.right_only)
            self.assertEqual([], comparison.diff_files)
            for path in first.iterdir():
                if path.is_file():
                    self.assertEqual(path.read_bytes(), (second / path.name).read_bytes(), path.name)
            quality = fmdl7c.read_json(first / "FMDL7C_QUALITY_REPORT.json")
            self.assertEqual("PASS", quality["quality_status"])
            self.assertEqual(24, quality["acceptance_gate_pass_count"])
            self.assertEqual(448, quality["logical_shard_count"])
            self.assertEqual(0, quality["investment_recommendation_count"])
            self.assertEqual(0, quality["rule_mutations"])
            self.assertEqual("NONE", quality["trade_authority"])

    def tearDown(self) -> None:
        build_root = ROOT / "build" / "fmdl7c_test"
        if build_root.exists():
            shutil.rmtree(build_root)


if __name__ == "__main__":
    unittest.main()
