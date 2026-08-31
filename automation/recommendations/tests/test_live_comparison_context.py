from __future__ import annotations

import unittest

from automation.recommendations.build_live_comparison_context import merge_live_context


class LiveComparisonContextTests(unittest.TestCase):
    def setUp(self):
        self.phase2c = {
            "eligible_non_reference_count": 0,
            "blocked_non_reference_count": 3,
            "blocked": [
                {
                    "security_id": "000719.SZ",
                    "gate_state": "BLOCKED_REFRESH_REQUIRED",
                    "reason_codes": [
                        "FRESH_VALUATION_BINDING_ABSENT",
                        "GOVERNANCE_GATE_ACTIVE",
                        "SCENARIO_PROBABILITIES_ABSENT",
                    ],
                    "missing_requirements": [
                        "fresh completed-close price/multiple bound to research object",
                        "probability-weighted valuation scenarios",
                    ],
                },
                {
                    "security_id": "002039.SZ",
                    "gate_state": "BLOCKED_REFRESH_REQUIRED",
                    "reason_codes": [
                        "FRESH_NORMALIZED_VALUATION_ABSENT",
                        "SCENARIO_PROBABILITIES_ABSENT",
                    ],
                    "missing_requirements": [
                        "fresh normalized P/E",
                        "probability-weighted valuation scenarios",
                    ],
                },
                {
                    "security_id": "301215.SZ",
                    "gate_state": "BLOCKED_MATERIAL_EVIDENCE",
                    "reason_codes": [
                        "PHASE1C_NOT_READY",
                        "MATERIAL_EVIDENCE_GAP_EXPLICITLY_RECONFIRMED",
                    ],
                    "missing_requirements": ["project-level realized utilization"],
                },
            ],
        }
        self.release = {
            "release_id": "FMDL3DC_TEST",
            "status": "FMDL3DC_VALUATION_ENGINE_CURRENT_ACCEPTED",
            "source_releases": {"market_as_of_date": "2026-08-28"},
        }
        self.domain = {
            "domain_id": "FINANCIAL_VALUATION_CONTEXT",
            "status": "PASS",
            "qc_status": "PASS_EXACT_VALUATION_REBUILT",
            "data_watermark": "2026-08-28",
            "published_at_utc": "2026-08-31T11:28:59Z",
            "source_branch": "automation/r2b2",
            "source_commit_sha": "a" * 40,
            "trade_authority": "NONE",
        }
        self.rows = [
            {
                "symbol": "000719.SZ",
                "metric_id": "VAL_PE_TTM",
                "quality_state": "VALID",
                "metric_value": 12.3,
                "decision_grade": True,
                "market_as_of_date": "2026-08-28",
            },
            {
                "symbol": "002039.SZ",
                "metric_id": "VAL_PE_TTM",
                "quality_state": "VALID",
                "metric_value": 15.2,
                "decision_grade": True,
                "market_as_of_date": "2026-08-28",
            },
            {
                "symbol": "301215.SZ",
                "metric_id": "VAL_PS_TTM",
                "quality_state": "VALID",
                "metric_value": 8.1,
                "decision_grade": True,
                "market_as_of_date": "2026-08-28",
            },
        ]

    def test_fresh_generic_valuation_blocker_is_removed_only_when_proven(self):
        out = merge_live_context(
            self.phase2c, self.rows, self.release, self.domain,
            {"000719.SZ", "002039.SZ", "301215.SZ"}, "phase2c"
        )
        rows = {x["security_id"]: x for x in out["blocked"]}
        self.assertNotIn(
            "FRESH_VALUATION_BINDING_ABSENT", rows["000719.SZ"]["reason_codes"]
        )
        self.assertIn("GOVERNANCE_GATE_ACTIVE", rows["000719.SZ"]["reason_codes"])
        self.assertIn(
            "SCENARIO_PROBABILITIES_ABSENT", rows["000719.SZ"]["reason_codes"]
        )
        self.assertTrue(
            rows["000719.SZ"]["valuation_context"]["live_exact_valuation_bound"]
        )

    def test_normalized_pe_blocker_is_not_silently_cured_by_ttm_pe(self):
        out = merge_live_context(
            self.phase2c, self.rows, self.release, self.domain,
            {"000719.SZ", "002039.SZ", "301215.SZ"}, "phase2c"
        )
        rows = {x["security_id"]: x for x in out["blocked"]}
        self.assertIn(
            "FRESH_NORMALIZED_VALUATION_ABSENT", rows["002039.SZ"]["reason_codes"]
        )
        self.assertIn(
            "LIVE_EXACT_PE_TTM_BOUND_NORMALIZED_PE_NOT_PROVEN",
            rows["002039.SZ"]["valuation_context"]["evidence_codes"],
        )

    def test_material_evidence_blocker_is_preserved(self):
        out = merge_live_context(
            self.phase2c, self.rows, self.release, self.domain,
            {"000719.SZ", "002039.SZ", "301215.SZ"}, "phase2c"
        )
        rows = {x["security_id"]: x for x in out["blocked"]}
        self.assertEqual(
            rows["301215.SZ"]["gate_state"], "BLOCKED_MATERIAL_EVIDENCE"
        )
        self.assertIn(
            "MATERIAL_EVIDENCE_GAP_EXPLICITLY_RECONFIRMED",
            rows["301215.SZ"]["reason_codes"],
        )
        self.assertTrue(out["live_operating_authority"])
        self.assertEqual(out["controls"]["orders"], 0)
        self.assertEqual(out["controls"]["trade_authority"], "NONE")


if __name__ == "__main__":
    unittest.main()
