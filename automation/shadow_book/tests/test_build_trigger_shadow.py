from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from automation.shadow_book.build_trigger_shadow import build, validate_payloads


class P44TriggerShadowTests(unittest.TestCase):
    def setUp(self):
        self.td=tempfile.TemporaryDirectory()
        self.root=Path(self.td.name)

    def tearDown(self):
        self.td.cleanup()

    def write_json(self,name,payload):
        p=self.root/name
        p.write_text(json.dumps(payload,ensure_ascii=False),encoding="utf-8")
        return p

    def write_jsonl(self,name,rows):
        p=self.root/name
        p.write_text("".join(json.dumps(x,ensure_ascii=False)+"\n" for x in rows),encoding="utf-8")
        return p

    def recommendation(self,fingerprint="rec-1",state0="WATCH_NORMAL"):
        return {
            "recommendation_fingerprint":fingerprint,
            "records":[
                {
                    "security_id":"000719.SZ","security_name":"中原传媒","market":"A_SHARE",
                    "recommendation_state":state0,
                    "triggers":["T1","T2","T3","T4"],
                    "invalidation_conditions":["I1","I2"],
                },
                {
                    "security_id":"002039.SZ","security_name":"黔源电力","market":"A_SHARE",
                    "recommendation_state":"WATCH_NORMAL",
                    "triggers":["T5","T6"],
                    "invalidation_conditions":["I3","I4"],
                },
                {
                    "security_id":"301215.SZ","security_name":"中汽股份","market":"A_SHARE",
                    "recommendation_state":"WATCH_HIGH_PRIORITY",
                    "triggers":["T7"],
                    "invalidation_conditions":["I5","I6"],
                },
            ],
        }

    def domain(self,published_at="2026-08-28T04:49:50Z"):
        return {
            "domain_id":"RECOMMENDATION",
            "status":"PASS",
            "source_commit_sha":"a"*40,
            "published_at_utc":published_at,
            "trade_authority":"NONE",
        }

    def run_build(self,rec,domain,prior=None,mark_packet=None):
        recp=self.write_json("rec.json",rec)
        domp=self.write_json("domain.json",domain)
        kwargs={}
        if prior:
            kwargs={
                "prior_trigger_current_path":self.write_json("prior_trigger.json",prior[1]),
                "prior_shadow_current_path":self.write_json("prior_shadow.json",prior[3]),
                "prior_trigger_event_ledger_path":self.write_jsonl("prior_trigger_events.jsonl",prior[2]),
                "prior_action_ledger_path":self.write_jsonl("prior_actions.jsonl",prior[4]),
            }
        if mark_packet is not None:
            kwargs["mark_packet_path"]=self.write_json("mark_packet.json",mark_packet)
        result=build(
            recommendation_path=recp,
            recommendation_domain_path=domp,
            now=datetime(2026,8,28,5,0,tzinfo=timezone.utc),
            **kwargs,
        )
        self.assertEqual(validate_payloads(*result),[])
        return result

    def test_live_current_registers_all_clauses_and_zero_actions(self):
        out=self.run_build(self.recommendation(),self.domain())
        registry,monitor,events,shadow,actions,request,receipt=out
        self.assertEqual(registry["subject_count"],3)
        self.assertEqual(registry["trigger_clause_count"],7)
        self.assertEqual(registry["invalidation_clause_count"],6)
        self.assertEqual(len(registry["clauses"]),13)
        self.assertTrue(all(x["monitorability"]=="SEMANTIC_EVIDENCE_REQUIRED" for x in registry["clauses"]))
        self.assertTrue(all(x["keyword_inference_authorized"] is False for x in registry["clauses"]))
        self.assertEqual(shadow["summary"]["open_position_count"],0)
        self.assertEqual(shadow["summary"]["action_signal_count_this_cycle"],0)
        self.assertEqual(request["request_count"],0)
        self.assertEqual(actions,[])
        self.assertEqual(receipt["phase4_forward_observation_increment"],0)
        self.assertEqual(receipt["phase4_realized_outcome_increment"],0)

    def test_watch_to_buy_now_is_single_pending_entry_and_idempotent(self):
        first=self.run_build(self.recommendation(),self.domain())
        buy=self.run_build(
            self.recommendation("rec-2","BUY_NOW"),
            self.domain("2026-08-28T05:10:00Z"),
            prior=first,
        )
        subject=next(x for x in buy[3]["subjects"] if x["security_id"]=="000719.SZ")
        self.assertEqual(subject["position_state"],"ENTRY_PENDING_MARK")
        self.assertEqual(buy[3]["summary"]["action_signal_count_this_cycle"],1)
        self.assertEqual(buy[5]["request_count"],1)
        entry_events=[x for x in buy[4] if x["event_type"]=="ENTRY_SIGNAL"]
        self.assertEqual(len(entry_events),1)

        repeated=self.run_build(
            self.recommendation("rec-2","BUY_NOW"),
            self.domain("2026-08-28T05:10:00Z"),
            prior=buy,
        )
        entry_events2=[x for x in repeated[4] if x["event_type"]=="ENTRY_SIGNAL"]
        self.assertEqual(len(entry_events2),1)
        self.assertEqual(repeated[3]["summary"]["action_signal_count_this_cycle"],0)
        self.assertEqual(repeated[1]["cycle_action"],"NO_OP_SAME_SOURCE_FINGERPRINT")

    def test_future_completed_mark_opens_and_earlier_mark_cannot_fill(self):
        first=self.run_build(self.recommendation(),self.domain())
        buy=self.run_build(
            self.recommendation("rec-2","BUY_NOW"),
            self.domain("2026-08-28T05:10:00Z"),
            prior=first,
        )
        action=next(x for x in buy[4] if x["event_type"]=="ENTRY_SIGNAL")
        too_early={
            "packet_id":"mark-early","status":"PASS_COMPLETE",
            "marks":[{
                "action_id":action["action_id"],"security_id":"000719.SZ",
                "market_session":"2026-08-28","mark":10.0,"provider":"TEST",
                "completed_session":True,"available_at_utc":"2026-08-28T05:00:00Z",
                "mark_identity":"m-early",
            }],
        }
        blocked=self.run_build(
            self.recommendation("rec-2","BUY_NOW"),
            self.domain("2026-08-28T05:10:00Z"),
            prior=buy,mark_packet=too_early,
        )
        subject=next(x for x in blocked[3]["subjects"] if x["security_id"]=="000719.SZ")
        self.assertEqual(subject["position_state"],"ENTRY_PENDING_MARK")

        future={
            "packet_id":"mark-future","status":"PASS_COMPLETE",
            "marks":[{
                "action_id":action["action_id"],"security_id":"000719.SZ",
                "market_session":"2026-08-28","mark":10.5,"provider":"TEST",
                "completed_session":True,"available_at_utc":"2026-08-28T07:05:00Z",
                "mark_identity":"m-future",
            }],
        }
        opened=self.run_build(
            self.recommendation("rec-2","BUY_NOW"),
            self.domain("2026-08-28T05:10:00Z"),
            prior=buy,mark_packet=future,
        )
        subject=next(x for x in opened[3]["subjects"] if x["security_id"]=="000719.SZ")
        self.assertEqual(subject["position_state"],"OPEN")
        self.assertEqual(subject["normalized_research_units"],1.0)
        self.assertEqual(subject["entry"]["mark"],10.5)
        self.assertEqual(opened[3]["summary"]["fill_count_this_cycle"],1)

    def test_buy_to_avoid_pending_exit_then_future_mark_closes(self):
        first=self.run_build(self.recommendation(),self.domain())
        buy=self.run_build(
            self.recommendation("rec-2","BUY_NOW"),
            self.domain("2026-08-28T05:10:00Z"),
            prior=first,
        )
        entry=next(x for x in buy[4] if x["event_type"]=="ENTRY_SIGNAL")
        opened=self.run_build(
            self.recommendation("rec-2","BUY_NOW"),
            self.domain("2026-08-28T05:10:00Z"),
            prior=buy,
            mark_packet={"packet_id":"entry-mark","status":"PASS_COMPLETE","marks":[{
                "action_id":entry["action_id"],"security_id":"000719.SZ",
                "market_session":"2026-08-28","mark":10.5,"provider":"TEST",
                "completed_session":True,"available_at_utc":"2026-08-28T07:05:00Z",
                "mark_identity":"entry-id",
            }]},
        )
        avoid=self.run_build(
            self.recommendation("rec-3","AVOID"),
            self.domain("2026-08-31T01:00:00Z"),
            prior=opened,
        )
        subject=next(x for x in avoid[3]["subjects"] if x["security_id"]=="000719.SZ")
        self.assertEqual(subject["position_state"],"EXIT_PENDING_MARK")
        exit_action=next(x for x in avoid[4] if x["event_type"]=="EXIT_SIGNAL")
        closed=self.run_build(
            self.recommendation("rec-3","AVOID"),
            self.domain("2026-08-31T01:00:00Z"),
            prior=avoid,
            mark_packet={"packet_id":"exit-mark","status":"PASS_COMPLETE","marks":[{
                "action_id":exit_action["action_id"],"security_id":"000719.SZ",
                "market_session":"2026-08-31","mark":11.0,"provider":"TEST",
                "completed_session":True,"available_at_utc":"2026-08-31T07:05:00Z",
                "mark_identity":"exit-id",
            }]},
        )
        subject=next(x for x in closed[3]["subjects"] if x["security_id"]=="000719.SZ")
        self.assertEqual(subject["position_state"],"CLOSED")
        self.assertEqual(subject["normalized_research_units"],0.0)
        self.assertEqual(subject["exit"]["mark"],11.0)

    def test_out_of_order_recommendation_is_rejected(self):
        later=self.run_build(
            self.recommendation("rec-later"),
            self.domain("2026-08-28T06:00:00Z"),
        )
        with self.assertRaisesRegex(ValueError,"P44_OUT_OF_ORDER_RECOMMENDATION_SOURCE"):
            self.run_build(
                self.recommendation("rec-older"),
                self.domain("2026-08-28T05:00:00Z"),
                prior=later,
            )


if __name__=="__main__":
    unittest.main()
