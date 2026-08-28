from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from automation.recommendations.build_recommendations import (
    build,
    route_state,
    validate_payloads,
)


class P43RecommendationTests(unittest.TestCase):
    def write_json(self, root: Path, name: str, payload: dict) -> Path:
        path = root / name
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return path

    def fixture_build(self, prior: dict | None = None):
        td = tempfile.TemporaryDirectory()
        root = Path(td.name)
        source_commit = "a" * 40

        funnel = {
            "cycle_fingerprint": "funnel-fingerprint",
            "generated_at_utc": "2026-08-28T04:31:54+00:00",
            "overall_status": "PARTIAL_STALE_UPSTREAM",
            "source_snapshot": {"D2": {"source_identity": source_commit}},
        }
        d2 = {
            "as_of": "2026-08-28T04:29:05+00:00",
            "status": "PARTIAL",
            "queue": [
                {
                    "security_id": "000719.SZ",
                    "security_name": "中原传媒",
                    "archetype": "DEFENSIVE_VALUE_CASH_RICH",
                    "status": "D2_RESEARCH_COMPLETE",
                    "research_disposition": "HOLD_RESEARCH_COMPLETE_NO_DECISION",
                    "first_rejection_test": "NOT_TRIGGERED_ON_CURRENT_EVIDENCE",
                    "next_gate": "MONITOR_TAX; MONITOR_GOVERNANCE; NO_DECISION_PROMOTION",
                    "last_attempt_at": "2026-08-28T04:29:05+00:00",
                },
                {
                    "security_id": "002039.SZ",
                    "security_name": "黔源电力",
                    "archetype": "DEFENSIVE_HYDRO_CASHFLOW",
                    "status": "D2_RESEARCH_COMPLETE",
                    "research_disposition": "HOLD_RESEARCH_COMPLETE_NO_DECISION",
                    "first_rejection_test": "NOT_TRIGGERED_BUT_NORMALIZATION_GATES_ACTIVE",
                    "next_gate": "MONITOR_HYDROLOGY; MONITOR_LEVERAGE; NO_DECISION_PROMOTION",
                    "last_attempt_at": "2026-08-28T04:29:05+00:00",
                },
                {
                    "security_id": "301215.SZ",
                    "security_name": "中汽股份",
                    "archetype": "QUALITY_GROWTH_TESTING_INFRASTRUCTURE",
                    "status": "D2_RESEARCH_HOLD_EVIDENCE_GAP",
                    "research_disposition": "HOLD_NOT_DECISION_GRADE",
                    "evidence_gap": "Project utilization and mature ROIC missing",
                    "first_rejection_test": "NOT_FORMALLY_TRIGGERED",
                    "next_gate": "AUTO_REVISIT_ON_NEXT_PRIMARY_DISCLOSURE",
                    "last_attempt_at": "2026-08-28T04:29:05+00:00",
                },
            ],
        }
        comparison = {
            "generated_at": "2026-08-28T00:00:00+00:00",
            "mode": "NO_COMPARISON",
            "eligible_non_reference_count": 0,
            "blocked": [
                {
                    "security_id": "000719.SZ",
                    "gate_state": "BLOCKED_REFRESH_REQUIRED",
                    "reason_codes": ["FRESH_VALUATION_BINDING_ABSENT"],
                    "missing_requirements": ["fresh valuation binding"],
                },
                {
                    "security_id": "002039.SZ",
                    "gate_state": "BLOCKED_REFRESH_REQUIRED",
                    "reason_codes": ["FRESH_NORMALIZED_VALUATION_ABSENT"],
                    "missing_requirements": ["fresh normalized valuation"],
                },
                {
                    "security_id": "301215.SZ",
                    "gate_state": "BLOCKED_MATERIAL_EVIDENCE",
                    "reason_codes": ["MATERIAL_EVIDENCE_GAP_EXPLICITLY_RECONFIRMED"],
                    "missing_requirements": ["project utilization", "mature ROIC"],
                },
            ],
            "controls": {"orders": 0, "trade_authority": "NONE"},
        }
        empty_positions = {
            "state_id": "POSITIONS",
            "status": "POSITION_CURRENT_MARKS_FRESH_BROKER_UNVERIFIED_RESEARCH_ONLY",
            "position_watermark": "2026-08-06",
            "mark_watermark": "2026-08-14",
            "holdings": [],
        }

        funnel_path = self.write_json(root, "funnel.json", funnel)
        d2_path = self.write_json(root, "d2.json", d2)
        comparison_path = self.write_json(root, "comparison.json", comparison)
        real_path = self.write_json(root, "real.json", empty_positions)
        sim_path = self.write_json(root, "sim.json", empty_positions)
        prior_path = None
        if prior is not None:
            prior_path = self.write_json(root, "prior.json", prior)

        result = build(
            funnel_path=funnel_path,
            d2_path=d2_path,
            comparison_context_path=comparison_path,
            d2_source_commit=source_commit,
            comparison_context_source_id="contract-head",
            prior_current_path=prior_path,
            real_positions_path=real_path,
            simulation_positions_path=sim_path,
            now=datetime(2026, 8, 28, 5, 0, tzinfo=timezone.utc),
        )
        return td, result

    def test_current_realistic_routes_are_conservative(self):
        td, (current, explain, receipt) = self.fixture_build()
        self.addCleanup(td.cleanup)
        self.assertEqual(validate_payloads(current, explain, receipt), [])
        states = {x["security_id"]: x["recommendation_state"] for x in current["records"]}
        self.assertEqual(states["000719.SZ"], "WATCH_NORMAL")
        self.assertEqual(states["002039.SZ"], "WATCH_NORMAL")
        self.assertEqual(states["301215.SZ"], "WATCH_HIGH_PRIORITY")
        self.assertEqual(current["summary"]["buy_now_count"], 0)
        self.assertEqual(current["summary"]["ready_for_user_decision_count"], 0)
        self.assertEqual(
            {x["market"] for x in current["market_coverage"]},
            {"A_SHARE", "H_SHARE", "US_SHARE"},
        )
        self.assertEqual(current["controls"]["orders"], 0)
        self.assertEqual(current["controls"]["trade_authority"], "NONE")

    def test_same_sources_fail_closed_to_no_op(self):
        td1, first = self.fixture_build()
        self.addCleanup(td1.cleanup)
        td2, second = self.fixture_build(prior=first[0])
        self.addCleanup(td2.cleanup)
        self.assertEqual(
            first[0]["recommendation_fingerprint"],
            second[0]["recommendation_fingerprint"],
        )
        self.assertEqual(second[0]["cycle_action"], "NO_OP_SAME_SOURCE_FINGERPRINT")
        self.assertEqual(
            second[0]["overall_status"],
            "NO_NEW_SOURCE_FINGERPRINT_CURRENT_PRESERVED",
        )
        self.assertEqual(first[0]["semantic_hash"], second[0]["semantic_hash"])

    def test_buy_now_requires_explicit_full_gate(self):
        d2 = {
            "status": "D2_RESEARCH_COMPLETE",
            "research_disposition": "READY",
            "first_rejection_test": "NOT_TRIGGERED",
            "current_entry_basis_established": True,
            "entry_trigger_satisfied": True,
            "portfolio_fit_acceptable": True,
            "capital_comparison_available": True,
        }
        state, _ = route_state(
            d2=d2,
            material_gap=False,
            comparison=None,
            verified_existing_position=False,
            portfolio_fit_status_value="CURRENT_PORTFOLIO_FIT_ACCEPTABLE",
        )
        self.assertEqual(state, "BUY_NOW")

        d2["capital_comparison_available"] = False
        state, _ = route_state(
            d2=d2,
            material_gap=False,
            comparison=None,
            verified_existing_position=False,
            portfolio_fit_status_value="CURRENT_PORTFOLIO_FIT_ACCEPTABLE",
        )
        self.assertEqual(state, "WATCH_NORMAL")

    def test_rejection_routes_avoid_or_exit_review(self):
        d2 = {
            "status": "D2_RESEARCH_COMPLETE",
            "research_disposition": "READY",
            "first_rejection_test": "TRIGGERED_MATERIAL_INVALIDATION",
        }
        state, _ = route_state(
            d2=d2,
            material_gap=False,
            comparison=None,
            verified_existing_position=False,
            portfolio_fit_status_value="NOT_ESTABLISHED",
        )
        self.assertEqual(state, "AVOID")

        state, _ = route_state(
            d2=d2,
            material_gap=False,
            comparison=None,
            verified_existing_position=True,
            portfolio_fit_status_value="CURRENT_POSITION_CONTEXT_VERIFIED",
        )
        self.assertEqual(state, "EXIT_REVIEW")


if __name__ == "__main__":
    unittest.main()
