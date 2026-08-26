import unittest

from strategy_kernel_v2.historical_feature_extractor import (
    _validate_registered_source,
    adapt_features_to_shared_observations,
    extract_model_neutral_features,
)
from strategy_kernel_v2.historical_replay import (
    _normalize_legacy_disposition,
    build_phase3c_replay,
    normalize_model_outcomes,
)


def evidence(eid, key, at="2026-01-01T00:00:00Z", path="x.json"):
    return {
        "evidence_id": eid,
        "evidence_key": key,
        "evidence_class": "RESEARCH",
        "security_ids": [],
        "evidence_as_of": "2026-01-01",
        "available_at": at,
        "availability_basis": "CANONICAL_MAIN_COMMIT",
        "authority_domain": "CANONICAL_MAIN",
        "source": {
            "repository": "jl2642/investment-os-market-data",
            "path": path,
            "commit_sha": "a" * 40,
            "provenance_status": "CANONICAL_MAIN",
        },
    }


def snapshot(records, opportunities=("000333.SZ",)):
    return {
        "decision_point_id": "CP",
        "at": "2026-01-02T00:00:00Z",
        "opportunity_security_ids": list(opportunities),
        "selected_evidence_ids": [r["evidence_id"] for r in records],
        "selected_evidence": records,
        "unavailable_required_evidence_keys": [],
    }


class Phase3CExtractionTests(unittest.TestCase):
    def test_rejects_bad_sha(self):
        record = evidence("E1", "CANDIDATE_STATE")
        record["source"]["commit_sha"] = "abc"
        with self.assertRaisesRegex(ValueError, "SHA40"):
            _validate_registered_source(record)

    def test_rejects_path_traversal(self):
        record = evidence("E1", "CANDIDATE_STATE", path="../secret.json")
        with self.assertRaisesRegex(ValueError, "REPOSITORY_RELATIVE"):
            _validate_registered_source(record)

    def test_candidate_core_extracts_legacy_disposition(self):
        record = evidence("E1", "CANDIDATE_STATE")
        data = {
            "candidate_core_members": [{
                "security_id": "000333.SZ",
                "security_name": "Midea",
                "core20_review_disposition": "WATCHLIST_RESEARCH_GAP",
                "buy_signal": "NO",
                "research_gap_count": 2,
            }],
            "historical_core20_archive": [],
        }
        layer = extract_model_neutral_features(snapshot([record]), source_loader=lambda _: data)
        row = layer["feature_rows"]["000333.SZ"]
        self.assertEqual(row["legacy_disposition"], "WATCHLIST_RESEARCH_GAP")
        self.assertEqual(row["provenance_evidence_ids"], ["E1"])

    def test_real_action_overrides_candidate(self):
        c = evidence("C", "CANDIDATE_STATE")
        r = evidence("R", "REAL_ACCOUNT_STATE")
        sources = {
            "C": {"candidate_core_members": [{
                "security_id": "000333.SZ",
                "core20_review_disposition": "WATCHLIST_RESEARCH_GAP",
            }]},
            "R": {"summary": {}, "holdings": [], "historical_action_records": [{
                "object_id": "000333",
                "decision": "HOLD",
                "current_weight": 0.1,
            }]},
        }
        layer = extract_model_neutral_features(
            snapshot([c, r]), source_loader=lambda rec: sources[rec["evidence_id"]]
        )
        self.assertEqual(layer["feature_rows"]["000333.SZ"]["legacy_disposition"], "HOLD")
        self.assertEqual(
            layer["feature_rows"]["000333.SZ"]["legacy_disposition_source"],
            "REAL_ACCOUNT_ACTION",
        )

    def test_wp5_scenarios_remain_unweighted(self):
        record = evidence("W", "RESEARCH_601138_P0")
        data = {"research_objects": {"601138.SH": {
            "security_id": "601138.SH",
            "conditional_portfolio_decision": {
                "action_posture": "HOLD_WITHIN_REVISED_BAND_NO_ADD",
                "base_case_expected_return": 0.08,
                "current_weight": 0.04,
                "base_case_hurdle_passed": False,
            },
            "driver_based_scenarios": {
                "cases": [
                    {"scenario": "BEAR", "return_vs_completed_close": -0.2},
                    {"scenario": "BASE", "return_vs_completed_close": 0.08},
                    {"scenario": "BULL", "return_vs_completed_close": 0.4},
                ]
            },
            "source_quality": {"source_count": 4, "all_primary_documents": True},
            "implementation_readiness": {"broker_verified": False, "implementation_ready": False},
        }}}
        layer = extract_model_neutral_features(
            snapshot([record], opportunities=("601138.SH",)), source_loader=lambda _: data
        )
        observations = adapt_features_to_shared_observations(layer)
        self.assertIn("wp5_unweighted_scenarios", observations["601138.SH"]["historical_features"])
        self.assertNotIn("phase2_inputs", observations["601138.SH"])
        self.assertEqual(layer["retrospective_probability_backfill_count"], 0)

    def test_00669_formal_plan_extracts_no_trade_state(self):
        record = evidence("D", "DECISION_00669_BUY_REVIEW")
        data = {
            "security_id": "HKEX:00669",
            "security_name": "TTI",
            "source_lineage": {"review_anchor_completed_close_hkd": 144.5},
            "valuation_review": {"current_interpretation": "FAIR_TO_FULL_NO_CHASE"},
            "portfolio_sizing_review": {
                "p5b_governed_research_weight": 0.01,
                "board_lot_sizing_mismatch": True,
            },
            "formal_plan": {
                "current_action": "WATCH_NO_TRADE_WAIT_FOR_PRICE_OR_POSITION_SIZING_GATE",
                "implementation_ready": False,
            },
        }
        layer = extract_model_neutral_features(
            snapshot([record], opportunities=("HKEX:00669",)), source_loader=lambda _: data
        )
        self.assertEqual(
            layer["feature_rows"]["HKEX:00669"]["legacy_disposition"],
            "WATCH_NO_TRADE_WAIT_FOR_PRICE_OR_POSITION_SIZING_GATE",
        )

    def test_d2_research_disposition_is_passthrough(self):
        record = evidence("D2", "RESEARCH_D2_000719")
        data = {
            "security_id": "000719.SZ",
            "research_disposition": "HOLD_RESEARCH_COMPLETE_NO_DECISION",
            "facts": {"x": 1},
            "sources": [{}, {}],
        }
        layer = extract_model_neutral_features(
            snapshot([record], opportunities=("000719.SZ",)), source_loader=lambda _: data
        )
        self.assertEqual(
            layer["feature_rows"]["000719.SZ"]["legacy_disposition"],
            "HOLD_RESEARCH_COMPLETE_NO_DECISION",
        )

    def test_adapter_requires_explicit_probability_inputs(self):
        layer = {
            "feature_rows": {
                "A": {
                    "security_name": "A",
                    "provenance_evidence_ids": ["E"],
                    "feature_provenance": {},
                    "features": {
                        "explicit_probability_scenarios": [
                            {"name": "B", "probability": 0.5, "annualized_total_return": -0.1},
                            {"name": "U", "probability": 0.5, "annualized_total_return": 0.2},
                        ],
                        "explicit_confidence": 0.7,
                        "explicit_portfolio_concentration_cost": 0.1,
                        "explicit_execution_friction": 0.2,
                    },
                }
            }
        }
        obs = adapt_features_to_shared_observations(layer)["A"]
        self.assertIn("phase2_inputs", obs)

    def test_adapter_requires_all_simple_inputs(self):
        layer = {
            "feature_rows": {
                "A": {
                    "security_name": "A",
                    "provenance_evidence_ids": ["E"],
                    "feature_provenance": {},
                    "features": {
                        "explicit_simple_return_proxy": 1,
                        "explicit_simple_downside_resilience": 2,
                        "explicit_simple_evidence_quality": 3,
                        "explicit_simple_concentration_cost": 4,
                    },
                }
            }
        }
        self.assertNotIn(
            "simple_pareto_inputs",
            adapt_features_to_shared_observations(layer)["A"],
        )


class Phase3CReplayTests(unittest.TestCase):
    def test_legacy_mapping_hold(self):
        self.assertEqual(_normalize_legacy_disposition("HOLD_NO_ADD"), "RETAINED")

    def test_legacy_mapping_watch(self):
        self.assertEqual(_normalize_legacy_disposition("WATCH_NO_TRADE"), "NO_ACTION")

    def test_legacy_mapping_reduce(self):
        self.assertEqual(_normalize_legacy_disposition("TRIM_POSITION"), "REDUCED")

    def test_legacy_mapping_add(self):
        self.assertEqual(_normalize_legacy_disposition("ADD_AFTER_REVIEW"), "ADMITTED")

    def test_legacy_no_add_is_not_admitted(self):
        self.assertNotEqual(_normalize_legacy_disposition("NO_ADD"), "ADMITTED")

    def test_normalize_candidate_frontier(self):
        output = {
            "model_form": "SIMPLE_NON_PROBABILISTIC_PARETO",
            "rows": {"A": {"pareto_status": "FRONTIER", "dominated_by": []}},
            "blocked": [],
        }
        self.assertEqual(normalize_model_outcomes(output)[0]["status"], "PRIORITIZED")

    def test_bounded_replay_preserves_zero_authority(self):
        rec = evidence("C", "CANDIDATE_STATE")
        registry = {
            "schema_version": "1",
            "records": [rec],
            "orders": 0,
            "trade_authority": "NONE",
        }
        points = {
            "schema_version": "1",
            "decision_points": [{
                "decision_point_id": "CP",
                "at": "2026-01-02T00:00:00Z",
                "opportunity_security_ids": ["000333.SZ"],
                "required_evidence_keys": ["CANDIDATE_STATE"],
            }],
            "orders": 0,
            "trade_authority": "NONE",
        }
        data = {"candidate_core_members": [{
            "security_id": "000333.SZ",
            "core20_review_disposition": "WATCHLIST_RESEARCH_GAP",
        }]}
        replay = build_phase3c_replay(registry, points, source_loader=lambda _: data)
        self.assertEqual(replay["controls"]["orders"], 0)
        self.assertEqual(replay["controls"]["trade_authority"], "NONE")
        self.assertFalse(replay["historical_performance_metrics_generated"])

    def test_bounded_replay_candidate_models_fail_closed_without_explicit_inputs(self):
        rec = evidence("C", "CANDIDATE_STATE")
        registry = {"records": [rec]}
        points = {"decision_points": [{
            "decision_point_id": "CP",
            "at": "2026-01-02T00:00:00Z",
            "opportunity_security_ids": ["000333.SZ"],
            "required_evidence_keys": ["CANDIDATE_STATE"],
        }]}
        data = {"candidate_core_members": [{
            "security_id": "000333.SZ",
            "core20_review_disposition": "WATCHLIST_RESEARCH_GAP",
        }]}
        replay = build_phase3c_replay(registry, points, source_loader=lambda _: data)
        self.assertEqual(replay["candidate_model_evaluable_security_instances"], 0)
        self.assertFalse(replay["comparative_candidate_replay_available"])
        self.assertGreater(
            replay["aggregate_by_model"]["LEGACY_POLICY_BASELINE"]["evaluable_security_instances"],
            0,
        )

    def test_model_checkpoint_count_matches(self):
        rec = evidence("C", "CANDIDATE_STATE")
        registry = {"records": [rec]}
        points = {"decision_points": [
            {
                "decision_point_id": "CP1",
                "at": "2026-01-02T00:00:00Z",
                "opportunity_security_ids": ["000333.SZ"],
                "required_evidence_keys": ["CANDIDATE_STATE"],
            },
            {
                "decision_point_id": "CP2",
                "at": "2026-01-03T00:00:00Z",
                "opportunity_security_ids": ["000333.SZ"],
                "required_evidence_keys": ["CANDIDATE_STATE"],
            },
        ]}
        data = {"candidate_core_members": [{
            "security_id": "000333.SZ",
            "core20_review_disposition": "WATCHLIST_RESEARCH_GAP",
        }]}
        replay = build_phase3c_replay(registry, points, source_loader=lambda _: data)
        self.assertEqual(replay["checkpoint_count"], 2)
        for state in replay["aggregate_by_model"].values():
            self.assertEqual(state["checkpoint_count"], 2)

    def test_no_subjective_fill_or_backfill(self):
        rec = evidence("C", "CANDIDATE_STATE")
        registry = {"records": [rec]}
        points = {"decision_points": [{
            "decision_point_id": "CP",
            "at": "2026-01-02T00:00:00Z",
            "opportunity_security_ids": ["000333.SZ"],
            "required_evidence_keys": ["CANDIDATE_STATE"],
        }]}
        data = {"candidate_core_members": [{
            "security_id": "000333.SZ",
            "core20_review_disposition": "WATCHLIST_RESEARCH_GAP",
        }]}
        replay = build_phase3c_replay(registry, points, source_loader=lambda _: data)
        self.assertEqual(replay["subjective_feature_fill_count"], 0)
        self.assertEqual(replay["retrospective_probability_backfill_count"], 0)
        self.assertEqual(replay["retrospective_scenario_backfill_count"], 0)
        self.assertEqual(replay["model_specific_evidence_fetches"], 0)


if __name__ == "__main__":
    unittest.main()
