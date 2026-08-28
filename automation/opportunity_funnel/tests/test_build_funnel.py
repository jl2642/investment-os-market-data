from __future__ import annotations

import unittest
from datetime import datetime, timezone

from automation.opportunity_funnel.build_funnel import build, validate_payloads


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
        self.assertEqual(current["stages"][0]["output_count"], 5539)
        self.assertEqual(current["stages"][1]["output_count"], 4926)
        self.assertEqual(current["stages"][2]["output_count"], 133)
        self.assertEqual(current["stages"][3]["output_count"], 100)
        self.assertEqual(current["stages"][4]["output_count"], 33)
        self.assertEqual(len(work_queue["queue"]), 5)
        self.assertEqual(
            [row["security_id"] for row in work_queue["queue"]],
            ["000099.SZ", "000426.SZ", "000600.SZ", "000828.SZ", "000975.SZ"],
        )
        self.assertFalse(current["bounded_rotation"]["automatic_d2_promotion_from_work_queue"])
        self.assertGreater(len(near_miss["rows"]), 0)
        self.assertEqual(current["controls"]["candidate_membership_mutations"], 0)
        self.assertEqual(current["controls"]["real_account_mutations"], 0)
        self.assertEqual(current["controls"]["simulation_mutations"], 0)
        self.assertEqual(current["controls"]["orders"], 0)
        self.assertEqual(current["controls"]["trade_authority"], "NONE")

    def test_same_sources_same_semantics(self):
        first = build(now=datetime(2026, 8, 28, 4, 30, tzinfo=timezone.utc))
        second = build(now=datetime(2026, 8, 28, 5, 30, tzinfo=timezone.utc))
        self.assertEqual(first[0]["cycle_fingerprint"], second[0]["cycle_fingerprint"])
        self.assertEqual(first[0]["semantic_hash"], second[0]["semantic_hash"])
        self.assertEqual(first[2]["queue"], second[2]["queue"])


if __name__ == "__main__":
    unittest.main()
