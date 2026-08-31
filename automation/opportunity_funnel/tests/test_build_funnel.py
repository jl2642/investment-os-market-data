from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from automation.opportunity_funnel.build_funnel import build, validate_payloads

ROOT = Path(__file__).resolve().parents[3]
SCREENING_REPORT = ROOT / "outputs/screens/current/FMDL2C_RUN_REPORT.json"


class P42OpportunityFunnelTests(unittest.TestCase):
    def test_expected_funnel_and_bounded_rotation(self):
        current, near_miss, work_queue, receipt = build(
            now=datetime(2026, 8, 28, 4, 30, tzinfo=timezone.utc)
        )
        self.assertEqual(validate_payloads(current, near_miss, work_queue, receipt), [])
        self.assertEqual(
            [row["stage_id"] for row in current["stages"]],
            [
                "UNIVERSE",
                "ELIGIBILITY_AND_EXCLUSIONS",
                "MULTI_DIMENSIONAL_SCREEN",
                "RESEARCH_LONGLIST",
                "RESEARCH_QUEUE",
                "D1",
                "D2",
                "CANDIDATE_CORE_CONTEXT",
                "READY_FOR_USER_DECISION_CONTEXT",
            ],
        )

        screening = json.loads(SCREENING_REPORT.read_text(encoding="utf-8-sig"))
        metrics = screening["metrics"]
        self.assertEqual(current["stages"][0]["output_count"], metrics["universe_symbols"])
        self.assertEqual(current["stages"][1]["output_count"], metrics["core_investable"])
        self.assertEqual(
            current["stages"][2]["output_count"],
            metrics["distinct_sleeve_candidates"],
        )
        self.assertEqual(current["stages"][3]["output_count"], metrics["longlist_symbols"])

        self.assertLessEqual(len(work_queue["queue"]), 5)
        self.assertEqual(len(work_queue["queue"]), 5)
        queue_ids = [row["security_id"] for row in work_queue["queue"]]
        self.assertEqual(len(queue_ids), len(set(queue_ids)))
        self.assertTrue(all(queue_ids))
        self.assertFalse(current["bounded_rotation"]["automatic_d2_promotion_from_work_queue"])
        self.assertGreater(len(near_miss["rows"]), 0)
        self.assertEqual(current["controls"]["candidate_membership_mutations"], 0)
        self.assertEqual(current["controls"]["real_account_mutations"], 0)
        self.assertEqual(current["controls"]["simulation_mutations"], 0)
        self.assertEqual(current["controls"]["orders"], 0)
        self.assertEqual(current["controls"]["trade_authority"], "NONE")
        self.assertEqual(current["cycle_action"], "ADVANCE_NEW_SOURCE_FINGERPRINT")

    def test_same_sources_with_prior_current_fail_closed_to_no_op(self):
        first = build(now=datetime(2026, 8, 28, 4, 30, tzinfo=timezone.utc))
        with tempfile.TemporaryDirectory() as tmp:
            prior = Path(tmp) / "prior.json"
            prior.write_text(json.dumps(first[0], ensure_ascii=False), encoding="utf-8")
            second = build(
                prior_current_path=prior,
                now=datetime(2026, 8, 28, 5, 30, tzinfo=timezone.utc),
            )
        self.assertEqual(second[0]["cycle_action"], "NO_OP_SAME_SOURCE_FINGERPRINT")
        self.assertEqual(second[0]["overall_status"], "NO_NEW_THROUGHPUT_EXPLICITLY_EXPLAINED")
        self.assertEqual(second[0]["cycle_fingerprint"], first[0]["cycle_fingerprint"])

    def test_same_sources_same_semantics(self):
        first = build(now=datetime(2026, 8, 28, 4, 30, tzinfo=timezone.utc))
        second = build(now=datetime(2026, 8, 28, 5, 30, tzinfo=timezone.utc))
        self.assertEqual(first[0]["cycle_fingerprint"], second[0]["cycle_fingerprint"])
        self.assertEqual(first[0]["semantic_hash"], second[0]["semantic_hash"])
        self.assertEqual(first[2]["queue"], second[2]["queue"])


if __name__ == "__main__":
    unittest.main()
