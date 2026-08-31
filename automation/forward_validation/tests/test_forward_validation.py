from __future__ import annotations

import json
import subprocess
import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zoneinfo import ZoneInfo

from automation.forward_validation.build_forward_validation import regime_id
from automation.forward_validation.registered_evidence import (
    d2_semantic_identity,
    is_ancestor,
)
from automation.forward_validation.market_outcomes import (
    entry_date_for_checkpoint,
    factor_status,
    secid,
    update_checkpoint,
)
from automation.forward_validation.publish_forward_validation import (
    checkpoint_immutable_projection,
    materialize_baseline,
    write_transaction,
)


class P45ForwardValidationTests(unittest.TestCase):

    def test_historical_d2_commit_need_not_be_current_branch_ancestor(self):
        with TemporaryDirectory() as td:
            root=Path(td)
            subprocess.run(["git","init","-b","main"],cwd=root,check=True,capture_output=True)
            subprocess.run(["git","config","user.email","test@example.com"],cwd=root,check=True)
            subprocess.run(["git","config","user.name","test"],cwd=root,check=True)
            state=root/"investment_os_runtime/30_STATE_CURRENT/30_RESEARCH"
            state.mkdir(parents=True)
            artifact=root/"evidence/000719.json"
            artifact.parent.mkdir(parents=True)
            artifact.write_text(
                json.dumps({"security_id":"000719.SZ","fact":"governed"}),
                encoding="utf-8",
            )
            (state/"RESEARCH_QUEUE_D2_CURRENT.json").write_text(
                json.dumps({
                    "queue":[{
                        "security_id":"000719.SZ",
                        "semantic_artifact":"evidence/000719.json",
                    }]
                }),
                encoding="utf-8",
            )
            subprocess.run(["git","add","."],cwd=root,check=True)
            subprocess.run(["git","commit","-m","historical d2"],cwd=root,check=True,capture_output=True)
            historical=subprocess.check_output(
                ["git","rev-parse","HEAD"],cwd=root,text=True
            ).strip()

            subprocess.run(["git","checkout","--orphan","rewritten"],cwd=root,check=True,capture_output=True)
            subprocess.run(["git","rm","-rf","."],cwd=root,check=True,capture_output=True)
            (root/"README.md").write_text("rewritten branch\n",encoding="utf-8")
            subprocess.run(["git","add","README.md"],cwd=root,check=True)
            subprocess.run(["git","commit","-m","rewritten head"],cwd=root,check=True,capture_output=True)
            current=subprocess.check_output(
                ["git","rev-parse","HEAD"],cwd=root,text=True
            ).strip()

            self.assertFalse(is_ancestor(root,historical,current))
            identity=d2_semantic_identity(root,historical)
            self.assertEqual(identity["source_commit"],historical)
            self.assertEqual(
                identity["artifacts"][0]["security_id"],
                "000719.SZ",
            )

    def test_p45_workflow_does_not_require_d2_branch_ancestry(self):
        root=Path(__file__).resolve().parents[3]
        text=(root/".github/workflows/p4-5-forward-validation.yml").read_text(encoding="utf-8")
        self.assertNotIn(
            'git merge-base --is-ancestor "$D2_COMMIT" refs/remotes/origin/p4-5-d2',
            text,
        )
        self.assertIn("d2_semantic_identity", text)

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

    def test_collect_and_refresh_noop_preserves_current_pointer_semantics(self):
        cutoff="2026-08-28T06:08:10Z"
        current={
            "eligibility_cutoff_utc":cutoff,
            "phase4_forward_observation_count":0,
            "phase4_realized_outcome_read_count":0,
            "phase5_migration_allowed":False,
        }
        cycle={
            "mode":"COLLECT_AND_REFRESH",
            "cycle_action":"NO_NEW_ELIGIBLE_CHECKPOINT",
            "new_checkpoint_count":0,
            "observation_increment":0,
            "outcome_read_increment":0,
            "orders":0,
            "trade_authority":"NONE",
        }
        with TemporaryDirectory() as td:
            target=Path(td)/"forward_validation"
            target.mkdir(parents=True)
            (target/"FORWARD_BASELINE_CURRENT.json").write_text(
                json.dumps({"eligibility_cutoff_utc":cutoff}),
                encoding="utf-8",
            )
            with (
                patch("automation.forward_validation.publish_forward_validation.TARGET",target),
                patch(
                    "automation.forward_validation.publish_forward_validation.write_domain_receipt",
                    return_value=(False,"NON_PASS_DOES_NOT_ADVANCE"),
                ),
            ):
                result=write_transaction(
                    baseline_candidate_text=None,
                    current_text=json.dumps(current),
                    ledger_text="",
                    checkpoint_texts=[],
                    cycle_text=json.dumps(cycle),
                    source_workflow="P4-5 test",
                    source_run_id="1",
                    source_run_attempt=2,
                    source_branch="main",
                    source_commit="a"*40,
                )
            self.assertEqual(result["status"],"NO_OP")
            self.assertFalse(result["advanced"])
            self.assertEqual(result["eligibility_cutoff_utc"],cutoff)
            self.assertFalse((target/"FORWARD_VALIDATION_CURRENT.json").exists())

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
