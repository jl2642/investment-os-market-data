import json
from pathlib import Path
import unittest

from strategy_kernel_v2.point_in_time_ledger import build_point_in_time_ledger


def evidence(
    evidence_id,
    evidence_key,
    available_at,
    *,
    security_ids=None,
    authority_domain="CANONICAL_MAIN",
    provenance_status=None,
):
    if provenance_status is None:
        provenance_status = authority_domain
    return {
        "evidence_id": evidence_id,
        "evidence_key": evidence_key,
        "evidence_class": "RESEARCH",
        "security_ids": security_ids or ["A"],
        "evidence_as_of": available_at[:10],
        "available_at": available_at,
        "availability_basis": (
            "CANONICAL_MAIN_COMMIT"
            if authority_domain == "CANONICAL_MAIN"
            else "GOVERNED_NON_CANONICAL_COMMIT"
        ),
        "authority_domain": authority_domain,
        "source": {
            "repository": "o/r",
            "path": "x.json",
            "commit_sha": "a" * 40,
            "provenance_status": provenance_status,
        },
    }


def point(at, required=None, security_ids=None, point_id="P"):
    return {
        "decision_point_id": point_id,
        "at": at,
        "checkpoint_type": "TEST",
        "opportunity_security_ids": security_ids or ["A"],
        "required_evidence_keys": required or [],
    }


class Phase3AEvidenceLedgerTest(unittest.TestCase):
    def test_future_evidence_excluded(self):
        out = build_point_in_time_ledger(
            [evidence("E1", "K1", "2026-01-02T00:00:00Z")],
            [point("2026-01-01T00:00:00Z")],
        )
        snap = out["snapshots"][0]
        self.assertEqual(snap["selected_evidence_ids"], [])
        self.assertEqual(snap["future_evidence_ids"], ["E1"])

    def test_boundary_time_included(self):
        at = "2026-01-01T00:00:00Z"
        out = build_point_in_time_ledger([evidence("E1", "K1", at)], [point(at)])
        self.assertEqual(out["snapshots"][0]["selected_evidence_ids"], ["E1"])

    def test_latest_available_version_per_key(self):
        out = build_point_in_time_ledger(
            [
                evidence("OLD", "K1", "2026-01-01T00:00:00Z"),
                evidence("NEW", "K1", "2026-01-02T00:00:00Z"),
            ],
            [point("2026-01-03T00:00:00Z")],
        )
        snap = out["snapshots"][0]
        self.assertEqual(snap["selected_evidence_ids"], ["NEW"])
        self.assertEqual(snap["superseded_evidence_ids"], ["OLD"])

    def test_later_version_does_not_replace_past_version(self):
        out = build_point_in_time_ledger(
            [
                evidence("OLD", "K1", "2026-01-01T00:00:00Z"),
                evidence("NEW", "K1", "2026-01-03T00:00:00Z"),
            ],
            [point("2026-01-02T00:00:00Z")],
        )
        snap = out["snapshots"][0]
        self.assertEqual(snap["selected_evidence_ids"], ["OLD"])
        self.assertEqual(snap["future_evidence_ids"], ["NEW"])

    def test_missing_requirement_explicit(self):
        out = build_point_in_time_ledger(
            [evidence("E1", "K1", "2026-01-01T00:00:00Z")],
            [point("2026-01-02T00:00:00Z", required=["K1", "K2"])],
        )
        snap = out["snapshots"][0]
        self.assertEqual(snap["unavailable_required_evidence_keys"], ["K2"])
        self.assertFalse(snap["snapshot_complete_for_declared_requirements"])

    def test_security_scope_excludes_other_security(self):
        out = build_point_in_time_ledger(
            [evidence("E1", "K1", "2026-01-01T00:00:00Z", security_ids=["B"])],
            [point("2026-01-02T00:00:00Z", security_ids=["A"])],
        )
        self.assertEqual(out["snapshots"][0]["selected_evidence_ids"], [])

    def test_global_scope_included(self):
        e = evidence("E1", "K1", "2026-01-01T00:00:00Z")
        e["security_ids"] = []
        out = build_point_in_time_ledger(
            [e],
            [point("2026-01-02T00:00:00Z", security_ids=["A"])],
        )
        self.assertEqual(out["snapshots"][0]["selected_evidence_ids"], ["E1"])

    def test_noncanonical_excluded_by_default(self):
        out = build_point_in_time_ledger(
            [
                evidence(
                    "E1",
                    "K1",
                    "2026-01-01T00:00:00Z",
                    authority_domain="GOVERNED_NON_CANONICAL",
                )
            ],
            [point("2026-01-02T00:00:00Z")],
        )
        self.assertEqual(out["snapshots"][0]["selected_evidence_ids"], [])

    def test_noncanonical_can_be_explicitly_enabled(self):
        out = build_point_in_time_ledger(
            [
                evidence(
                    "E1",
                    "K1",
                    "2026-01-01T00:00:00Z",
                    authority_domain="GOVERNED_NON_CANONICAL",
                )
            ],
            [point("2026-01-02T00:00:00Z")],
            allowed_authority_domains=("CANONICAL_MAIN", "GOVERNED_NON_CANONICAL"),
        )
        self.assertEqual(out["snapshots"][0]["selected_evidence_ids"], ["E1"])

    def test_naive_timestamp_rejected(self):
        with self.assertRaisesRegex(ValueError, "OFFSET_AWARE_TIMESTAMP_REQUIRED"):
            build_point_in_time_ledger(
                [evidence("E1", "K1", "2026-01-01T00:00:00Z")],
                [point("2026-01-02T00:00:00")],
            )

    def test_duplicate_evidence_id_rejected(self):
        with self.assertRaisesRegex(ValueError, "DUPLICATE_EVIDENCE_ID"):
            build_point_in_time_ledger(
                [
                    evidence("E1", "K1", "2026-01-01T00:00:00Z"),
                    evidence("E1", "K2", "2026-01-01T00:00:00Z"),
                ],
                [point("2026-01-02T00:00:00Z")],
            )

    def test_invalid_commit_sha_rejected(self):
        e = evidence("E1", "K1", "2026-01-01T00:00:00Z")
        e["source"]["commit_sha"] = "bad"
        with self.assertRaisesRegex(ValueError, "INVALID_SOURCE_COMMIT_SHA"):
            build_point_in_time_ledger([e], [point("2026-01-02T00:00:00Z")])

    def test_canonical_record_requires_canonical_provenance(self):
        e = evidence(
            "E1",
            "K1",
            "2026-01-01T00:00:00Z",
            provenance_status="GOVERNED_NON_CANONICAL",
        )
        with self.assertRaisesRegex(ValueError, "CANONICAL_SOURCE_STATUS_REQUIRED"):
            build_point_in_time_ledger([e], [point("2026-01-02T00:00:00Z")])

    def test_no_model_or_investment_output(self):
        out = build_point_in_time_ledger([], [point("2026-01-02T00:00:00Z")])
        self.assertFalse(out["model_output_generated"])
        self.assertFalse(out["investment_recommendation_generated"])
        self.assertFalse(out["user_decision_generated"])

    def test_authority_controls_remain_disabled(self):
        out = build_point_in_time_ledger([], [point("2026-01-02T00:00:00Z")])
        controls = out["controls"]
        self.assertEqual(controls["orders"], 0)
        self.assertEqual(controls["trade_authority"], "NONE")
        self.assertFalse(controls["hindsight_allowed"])
        self.assertFalse(controls["retrospective_probability_backfill_allowed"])
        self.assertFalse(controls["retrospective_scenario_backfill_allowed"])

    def test_deterministic_checkpoint_order(self):
        out = build_point_in_time_ledger(
            [],
            [
                point("2026-01-02T00:00:00Z", point_id="P2"),
                point("2026-01-01T00:00:00Z", point_id="P1"),
            ],
        )
        self.assertEqual(
            [x["decision_point_id"] for x in out["snapshots"]],
            ["P1", "P2"],
        )


class Phase3ARealRegistryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.registry = json.loads((root / "PHASE3A_EVIDENCE_REGISTRY.json").read_text(encoding="utf-8"))
        cls.points = json.loads((root / "PHASE3A_DECISION_POINTS.json").read_text(encoding="utf-8"))
        cls.out = build_point_in_time_ledger(
            cls.registry["records"],
            cls.points["decision_points"],
            allowed_authority_domains=("CANONICAL_MAIN",),
        )

    def snapshot(self, point_id):
        return next(x for x in self.out["snapshots"] if x["decision_point_id"] == point_id)

    def test_real_registry_counts(self):
        self.assertEqual(self.out["evidence_record_count"], 29)
        self.assertEqual(self.out["decision_point_count"], 7)

    def test_every_declared_checkpoint_requirement_is_reproducible(self):
        self.assertTrue(
            all(x["snapshot_complete_for_declared_requirements"] for x in self.out["snapshots"])
        )
        self.assertTrue(
            all(not x["unavailable_required_evidence_keys"] for x in self.out["snapshots"])
        )

    def test_registry_is_canonical_only(self):
        self.assertEqual(
            {x["authority_domain"] for x in self.registry["records"]},
            {"CANONICAL_MAIN"},
        )

    def test_d2_r2_cannot_leak_into_r1_checkpoint(self):
        r1 = self.snapshot("CP_20260813_D2_R1")
        self.assertIn("RESEARCH_D2_000719_R1_20260813", r1["selected_evidence_ids"])
        self.assertIn("RESEARCH_D2_301215_R1_20260813", r1["selected_evidence_ids"])
        self.assertNotIn("RESEARCH_D2_000719_R2_20260818", r1["selected_evidence_ids"])
        self.assertNotIn("RESEARCH_D2_301215_R2_20260818", r1["selected_evidence_ids"])
        self.assertIn("RESEARCH_D2_000719_R2_20260818", r1["future_evidence_ids"])
        self.assertIn("RESEARCH_D2_301215_R2_20260818", r1["future_evidence_ids"])

    def test_d2_r2_selected_only_after_canonical_merge(self):
        r2 = self.snapshot("CP_20260818_D2_R2")
        self.assertIn("RESEARCH_D2_000719_R2_20260818", r2["selected_evidence_ids"])
        self.assertIn("RESEARCH_D2_301215_R2_20260818", r2["selected_evidence_ids"])
        self.assertIn("RESEARCH_D2_000719_R1_20260813", r2["superseded_evidence_ids"])
        self.assertIn("RESEARCH_D2_301215_R1_20260813", r2["superseded_evidence_ids"])
        self.assertEqual(r2["future_evidence_ids"], [])

    def test_earliest_core2_checkpoint_does_not_see_unrelated_future_assets(self):
        first = self.snapshot("CP_20260726_WP4_AUDIT")
        self.assertEqual(
            first["selected_evidence_ids"],
            ["CANDIDATE_STATE_20260726", "RESEARCH_CORE2_WP4_20260726"],
        )
        self.assertNotIn("RESEARCH_00669_VALUATION_P5C_20260808", first["future_evidence_ids"])
        self.assertNotIn("RESEARCH_601138_P0_20260727", first["future_evidence_ids"])

    def test_as_of_and_availability_are_explicitly_distinct(self):
        valuation = next(
            x for x in self.registry["records"]
            if x["evidence_id"] == "RESEARCH_00669_VALUATION_P5C_20260808"
        )
        self.assertEqual(valuation["evidence_as_of"], "2026-08-07")
        self.assertEqual(valuation["available_at"], "2026-08-08T14:17:09Z")

    def test_no_phase3a_economic_or_decision_authority(self):
        self.assertFalse(self.out["model_output_generated"])
        self.assertFalse(self.out["investment_recommendation_generated"])
        self.assertFalse(self.out["user_decision_generated"])
        self.assertEqual(self.out["controls"]["orders"], 0)
        self.assertEqual(self.out["controls"]["trade_authority"], "NONE")


if __name__ == "__main__":
    unittest.main()
