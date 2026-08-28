import unittest

from strategy_kernel_v2.phase4_p4_1_forward_census import build


class Phase4P41ForwardCensusTests(unittest.TestCase):
    def test_first_census_is_fail_closed(self):
        result = build()
        self.assertEqual(result["counted_phase4_forward_observation_count"], 0)
        self.assertFalse(result["phase4_started"])
        self.assertEqual(result["phase4_realized_outcome_read_count"], 0)
        self.assertEqual(result["orders"], 0)
        self.assertEqual(result["trade_authority"], "NONE")
        for row in result["candidate_commits"]:
            self.assertFalse(row["counts_as_phase4_observation"])
            self.assertEqual(
                row["classification"],
                "CANDIDATE_COMMIT_REQUIRES_SUBSTANTIVE_AND_SHARED_PACKET_GATES",
            )


if __name__ == "__main__":
    unittest.main()
