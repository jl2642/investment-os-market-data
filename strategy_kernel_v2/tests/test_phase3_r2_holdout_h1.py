from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import unittest

import strategy_kernel_v2.phase3_r2_holdout_h1 as h1

ROOT = Path(__file__).resolve().parents[1]


class HoldoutH1Tests(unittest.TestCase):
    def setUp(self):
        self.contract = h1._load_json(ROOT / "PHASE3_R2_HOLDOUT_SELECTION_CONTRACT.json")
        self.registry = h1._load_json(ROOT / "PHASE3A_EVIDENCE_REGISTRY.json")

    def test_family_catalog_is_frozen_from_phase3a_registry(self):
        catalog = h1.build_family_catalog(self.registry, self.contract)
        expected = set(self.contract["frozen_evidence_families"]["required_base_families"])
        expected.update(self.contract["frozen_evidence_families"]["context_families"])
        expected.update(self.contract["frozen_evidence_families"]["research_or_decision_families"])
        self.assertEqual(set(catalog), expected)
        self.assertEqual(len(catalog), 10)
        self.assertEqual(
            sorted(self.registry["scope_security_ids"]),
            ["000333.SZ","000719.SZ","002039.SZ","301215.SZ","600900.SH","601138.SH","605090.SH","HKEX:00669"],
        )

    def test_sufficiency_gate_is_conjunctive(self):
        checkpoints = []
        dates = [
            ("2026-07-26T11:58:08+00:00", "2026-07-26", "2026-W30", "R0"),
            ("2026-07-27T02:32:31+00:00", "2026-07-27", "2026-W31", "R1"),
            ("2026-08-05T02:00:15+00:00", "2026-08-05", "2026-W32", "R2"),
            ("2026-08-05T07:22:50+00:00", "2026-08-05", "2026-W32", "R2"),
            ("2026-08-06T03:33:20+00:00", "2026-08-06", "2026-W32", "R2"),
            ("2026-08-08T03:32:45+00:00", "2026-08-08", "2026-W32", "R2"),
            ("2026-08-08T13:15:01+00:00", "2026-08-08", "2026-W32", "R3"),
            ("2026-08-11T01:45:57+00:00", "2026-08-11", "2026-W33", "R3"),
            ("2026-08-12T05:14:17+00:00", "2026-08-12", "2026-W33", "R4"),
            ("2026-08-13T01:53:04+00:00", "2026-08-13", "2026-W33", "R5"),
            ("2026-08-14T15:29:03+00:00", "2026-08-14", "2026-W33", "R6"),
            ("2026-08-18T01:41:24+00:00", "2026-08-18", "2026-W34", "R7"),
        ]
        scope = sorted(self.registry["scope_security_ids"])
        for i, (at, utc_date, iso_week, regime) in enumerate(dates):
            checkpoints.append({
                "checkpoint_id": f"T{i}",
                "at": at,
                "utc_date": utc_date,
                "iso_week": iso_week,
                "evidence_regime_signature": regime,
                "opportunity_security_ids": scope,
            })
        result = h1._evaluate_sufficiency(checkpoints, self.contract)
        self.assertTrue(result["all_thresholds_passed"])
        self.assertTrue(all(result["checks"].values()))

    def test_outside_seed_gate_fails_when_no_checkpoint_expands_time_span(self):
        scope = sorted(self.registry["scope_security_ids"])
        checkpoints = []
        for i in range(12):
            day = 1 + i
            checkpoints.append({
                "checkpoint_id": f"T{i}",
                "at": f"2026-08-{day:02d}T01:00:00+00:00",
                "utc_date": f"2026-08-{day:02d}",
                "iso_week": f"2026-W{31 + i // 3:02d}",
                "evidence_regime_signature": f"R{i % 4}",
                "opportunity_security_ids": scope,
            })
        result = h1._evaluate_sufficiency(checkpoints, self.contract)
        self.assertFalse(result["checks"]["minimum_checkpoints_strictly_outside_seed_time_span"])
        self.assertFalse(result["all_thresholds_passed"])

    def test_controls_forbid_model_and_outcome_use(self):
        for key in (
            "realized_outcomes_read",
            "phase3d_results_read",
            "r2_profile_values_computed",
            "r2_pareto_replay_executed",
            "r2_replayability_used_for_selection",
            "future_returns_used_for_selection",
            "regret_or_calibration_used_for_selection",
            "discretionary_subsampling_used",
            "random_sampling_used",
            "manual_cherry_pick_used",
        ):
            self.assertFalse(h1.FALSE_CONTROLS[key], key)
        self.assertEqual(h1.FALSE_CONTROLS["orders"], 0)
        self.assertEqual(h1.FALSE_CONTROLS["trade_authority"], "NONE")

    def test_module_does_not_import_r2_replay_or_phase3d_outcome_modules(self):
        source = (ROOT / "phase3_r2_holdout_h1.py").read_text(encoding="utf-8")
        forbidden_imports = [
            "from strategy_kernel_v2.phase3c_r2b_replay import",
            "from strategy_kernel_v2.phase3c_r2a_reconstruction import",
            "from strategy_kernel_v2.phase3d",
            "import strategy_kernel_v2.phase3d",
        ]
        for token in forbidden_imports:
            self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
