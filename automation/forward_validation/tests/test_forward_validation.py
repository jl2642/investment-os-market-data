from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from automation.forward_validation.build_forward_validation import regime_id
from automation.forward_validation.market_outcomes import (
    entry_date_for_checkpoint,
    factor_status,
    secid,
    update_checkpoint,
)
from automation.forward_validation.publish_forward_validation import (
    checkpoint_immutable_projection,
    materialize_baseline,
)


class P45ForwardValidationTests(unittest.TestCase):
    def test_materialize_baseline_uses_exact_publication_cutoff(self):
        candidate={
            "eligibility_cutoff_utc":None,
            "phase4_forward_observation_count":0,
            "phase4_realized_outcome_read_count":0,
            "registered_family_baselines":{"RESEARCH_D2":{}},
        }
        current={
            "phase4_forward_observation_count":0,
            "phase4_realized_outcome_read_count":0,
            "phase5_migration_allowed":False,
        }
        baseline,out=materialize_baseline(
            candidate,current,
            published_at="2026-08-28T06:00:00Z",
            source_commit="a"*40,
        )
        self.assertEqual(baseline["eligibility_cutoff_utc"],"2026-08-28T06:00:00Z")
        self.assertEqual(baseline["protected_main_sha_at_acceptance"],"a"*40)
        self.assertTrue(baseline["phase4_effective_forward_observation_start_allowed"])
        self.assertEqual(out["phase4_forward_observation_count"],0)
        self.assertEqual(out["phase4_realized_outcome_read_count"],0)
        self.assertFalse(out["phase5_migration_allowed"])

    def test_checkpoint_immutable_projection_ignores_only_measurement_fields(self):
        base={
            "schema_version":"1.1.0","checkpoint_id":"C1",
            "checkpoint_available_at_utc":"2026-08-28T06:00:00+00:00",
            "trigger_event":{"family_id":"RESEARCH_D2"},
            "global_forward_evidence_state_fingerprint":"g",
            "evidence_regime_id":"r","shared_packet":{"x":1},
            "parallel_outputs":{"r2":{"model_version":"R2.0.1_RESEARCH"}},
            "audit_context":{},"evaluation_eligibility":"POST_CLEAN_CUTOFF_FORWARD_EVIDENCE",
            "controls":{"orders":0,"trade_authority":"NONE"},
            "outcomes":{},"economically_mature":False,
        }
        matured={**base,"outcomes":{"x":1},"economically_mature":True}
        self.assertEqual(
            checkpoint_immutable_projection(base),
            checkpoint_immutable_projection(matured),
        )
        drift={**matured,"evidence_regime_id":"changed"}
        self.assertNotEqual(
            checkpoint_immutable_projection(base),
            checkpoint_immutable_projection(drift),
        )

    def test_regime_identity_is_result_independent(self):
        packet={"contributing_registered_family_ids":["RESEARCH_D2","CANDIDATE_STATE"]}
        parallel={"r2":{"profiles":[
            {
                "security_id":"000001.SZ",
                "comparison_signature_sha256":"sig1",
                "missing_rule_ids":["A","B"],
                "comparison_contract_evaluable":True,
            },
            {
                "security_id":"000002.SZ",
                "comparison_signature_sha256":"sig2",
                "missing_rule_ids":["C"],
                "comparison_contract_evaluable":False,
            },
        ]}}
        left=regime_id(packet,parallel)
        parallel2={"r2":{"profiles":[dict(x) for x in parallel["r2"]["profiles"]]}}
        parallel2["r2"]["profiles"][0]["pareto_status"]="DOMINATED"
        parallel2["r2"]["profiles"][0]["future_return"]=999
        self.assertEqual(left,regime_id(packet,parallel2))

    def test_a_share_session_entry_semantics(self):
        cal=["2026-08-27","2026-08-28","2026-08-31","2026-09-01","2026-09-02"]
        self.assertEqual(
            entry_date_for_checkpoint("2026-08-28T08:00:00+00:00",cal),
            "2026-08-28",
        )
        self.assertEqual(
            entry_date_for_checkpoint("2026-08-28T06:00:00+00:00",cal),
            "2026-08-27",
        )

    def test_a_share_secid_and_ca_status(self):
        self.assertEqual(secid("000719.SZ"),"0.000719")
        self.assertEqual(secid("600036.SH"),"1.600036")
        ca=factor_status(
            {"2026-08-28":10.0,"2026-08-31":10.5},
            {"2026-08-28":9.0,"2026-08-31":9.45},
            ["2026-08-28","2026-08-31"],
        )
        self.assertEqual(ca["status"],"NO_ADJUSTMENT_FACTOR_CHANGE_OBSERVED")

    @patch("automation.forward_validation.market_outcomes.fetch_daily")
    @patch("automation.forward_validation.market_outcomes.fetch_calendar")
    def test_unsupported_market_is_explicit_not_substituted(self,calendar,daily):
        calendar.return_value=[
            "2026-08-27","2026-08-28","2026-08-31","2026-09-01",
            "2026-09-02","2026-09-03","2026-09-04"
        ]
        daily.return_value={
            "2026-08-28":10.0,"2026-08-31":10.1,"2026-09-01":10.2,
            "2026-09-02":10.3,"2026-09-03":10.4,"2026-09-04":10.5,
        }
        cp={
            "checkpoint_id":"C1",
            "checkpoint_available_at_utc":"2026-08-28T08:00:00+00:00",
            "shared_packet":{"opportunity_security_ids":["000719.SZ","HKEX:00669"]},
            "parallel_outputs":{"r2":{"dominance_edges":[]}},
            "outcomes":{},
        }
        updated,reads=update_checkpoint(
            cp,
            now=datetime(2026,9,5,tzinfo=ZoneInfo("UTC")),
            allow_outcome_reads=False,
        )
        self.assertEqual(reads,0)
        self.assertIn("HKEX:00669",updated["outcome_provider_pending_security_ids"])
        self.assertFalse(updated["entry_binding_complete"])
        self.assertFalse(updated["economically_mature"])


if __name__=="__main__":
    unittest.main()
