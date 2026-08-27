import unittest

from strategy_kernel_v2.phase3d_r2_outcome_evidence import (
    corporate_action_status,
    derive_observation_dates,
    load_contract,
    validate_contract,
)


class Phase3DR2OutcomeEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.calendar = [
            "2026-07-24", "2026-07-27", "2026-07-28", "2026-07-29",
            "2026-07-30", "2026-07-31", "2026-08-03", "2026-08-04",
            "2026-08-05", "2026-08-06", "2026-08-07", "2026-08-10",
            "2026-08-11", "2026-08-12", "2026-08-13", "2026-08-14",
            "2026-08-17", "2026-08-18", "2026-08-19", "2026-08-20",
            "2026-08-21", "2026-08-24",
        ]

    def test_contract_frozen_before_returns(self):
        contract = load_contract()
        self.assertEqual(validate_contract(contract), [])
        self.assertEqual(contract["acquisition_runtime_policy"]["per_call_attempts"], 2)
        self.assertEqual(contract["acquisition_runtime_policy"]["per_attempt_timeout_seconds"], 15)

    def test_weekend_checkpoint_uses_prior_settled_close(self):
        row = derive_observation_dates("2026-07-26T17:29:01+08:00", self.calendar)
        self.assertEqual(row["entry_date"], "2026-07-24")
        self.assertEqual(row["horizon_1_date"], "2026-07-27")
        self.assertEqual(row["horizon_3_date"], "2026-07-29")
        self.assertEqual(row["horizon_5_date"], "2026-07-31")

    def test_150026_checkpoint_stays_on_prior_close_under_settled_policy(self):
        row = derive_observation_dates("2026-07-27T15:00:26+08:00", self.calendar)
        self.assertEqual(row["entry_date"], "2026-07-24")
        self.assertEqual(row["horizon_1_date"], "2026-07-28")

    def test_after_1530_checkpoint_can_use_same_day_close(self):
        row = derive_observation_dates("2026-08-05T15:35:41+08:00", self.calendar)
        self.assertEqual(row["entry_date"], "2026-08-05")
        self.assertEqual(row["horizon_1_date"], "2026-08-06")
        self.assertEqual(row["horizon_5_date"], "2026-08-12")

    def test_intraday_checkpoint_uses_prior_close_and_next_day_horizon(self):
        row = derive_observation_dates("2026-08-17T09:47:15+08:00", self.calendar)
        self.assertEqual(row["entry_date"], "2026-08-14")
        self.assertEqual(row["horizon_1_date"], "2026-08-18")
        self.assertEqual(row["horizon_5_date"], "2026-08-24")

    def test_adjustment_factor_constant_means_no_observed_action(self):
        raw = {"2026-08-10": 10.0, "2026-08-11": 11.0}
        qfq = {"2026-08-10": 9.0, "2026-08-11": 9.9}
        result = corporate_action_status(raw, qfq, ["2026-08-10", "2026-08-11"], relative_range_tolerance=0.0005)
        self.assertEqual(result["status"], "NO_ADJUSTMENT_FACTOR_CHANGE_OBSERVED")

    def test_adjustment_factor_change_is_explicit(self):
        raw = {"2026-08-10": 10.0, "2026-08-11": 10.0}
        qfq = {"2026-08-10": 9.0, "2026-08-11": 9.5}
        result = corporate_action_status(raw, qfq, ["2026-08-10", "2026-08-11"], relative_range_tolerance=0.0005)
        self.assertEqual(result["status"], "ADJUSTMENT_FACTOR_CHANGE_OBSERVED")

    def test_missing_companion_data_blocks_corporate_action_status(self):
        raw = {"2026-08-10": 10.0, "2026-08-11": 11.0}
        qfq = {"2026-08-10": 9.0}
        result = corporate_action_status(raw, qfq, ["2026-08-10", "2026-08-11"], relative_range_tolerance=0.0005)
        self.assertEqual(result["status"], "CORPORATE_ACTION_STATUS_UNRESOLVED")


if __name__ == "__main__":
    unittest.main()
