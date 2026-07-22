from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import fmdl6x2final_reconcile as r

REPO_CONTRACT = Path("config/fmdl6x2final_full_store_reconciliation_contract.json")


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


class ReconcileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "config").mkdir()
        shutil.copy(REPO_CONTRACT, self.tmp / r.CONTRACT_PATH)
        self._make_domains()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp)

    def _make_domains(self) -> None:
        data = {
            "security_master": {"included_security_records": 8807},
            "identity": {"listing_records": 8807, "security_records": 8785, "issuer_records": 7419, "canonical_id_status": "PROVISIONAL_DIRECTORY_DERIVED_MERGEABLE", "sec_identity_status": "PENDING_OFFICIAL_SEC_EVIDENCE"},
            "listing_history": {"effective_listing_intervals": 8807, "accepted_snapshot_count": 1, "historical_completion_claimed": False, "history_status": "PARTIAL_OFFICIAL_EVIDENCE_BASELINE_WITH_DAILY_ACCUMULATION"},
            "market_reference": {"accepted_dual_route_securities": 64, "full_universe_market_history_claimed": False, "market_data_grade": "NON_DECISION_GRADE_FALLBACK", "market_store_status": "PARTIAL_NON_DECISION_GRADE_BASELINE_WITH_SHARDED_BACKFILL_QUEUE"},
            "sec_filings_facts": {"filing_count": 6, "fact_count": 33, "backfill_queue_count": 7413, "full_universe_sec_store_claimed": False, "sec_store_status": "PARTIAL_OFFICIAL_SEC_EVIDENCE_BASELINE_WITH_EXTERNAL_BACKFILL_QUEUE"},
        }
        for name, spec in r.DOMAIN_SPECS.items():
            current = self.tmp / f"outputs/domain/{name}"
            release = self.tmp / f"datasets/release/{name}"
            decision = {"phase_id": spec["phase_id"], "status": spec["status"], "trade_authority": "NONE"}
            quality = {"quality_status": "PASS"}
            if name == "market_reference":
                quality["universe_accounted"] = 8785
            if name == "sec_filings_facts":
                quality["universe_accounted"] = 7419
            manifest = {"phase_id": spec["phase_id"], "release_sequence": spec["sequence"]}
            for root in (current, release):
                write_json(root / spec["decision"], decision)
                write_json(root / spec["manifest"], manifest)
            write_json(current / spec["quality"], quality)
            pointer = {
                "phase_id": spec["phase_id"], "status": spec["status"], "release_sequence": spec["sequence"],
                "release_id": f"R{spec['sequence']}", "current_path": str(current.relative_to(self.tmp)),
                "release_path": str(release.relative_to(self.tmp)), "normalized_path": f"normalized/{name}",
                "manifest_sha256": r.sha256_path(current / spec["manifest"]), "trade_authority": "NONE",
                "brokerage_real_account_gate": "CLOSED_NO_CHANNEL", **data[name]
            }
            write_json(self.tmp / spec["pointer"], pointer)

    def test_contract(self) -> None:
        self.assertEqual(r.validate_contract(self.tmp)["phase_id"], r.PHASE_ID)

    def test_build_reconciles_all_domains(self) -> None:
        decision = r.build(self.tmp, self.tmp / "candidate", "2026-07-22T16:00:00Z", "abc")
        self.assertEqual(decision["status"], r.STATUS)
        quality = r.read_json(self.tmp / "candidate/FMDL6X2_FINAL_QUALITY_REPORT.json")
        self.assertEqual(quality["domain_count_accepted"], 5)
        self.assertEqual(quality["quality_status"], "PASS")

    def test_manifest_tamper_fails(self) -> None:
        spec = r.DOMAIN_SPECS["identity"]
        (self.tmp / "outputs/domain/identity" / spec["manifest"]).write_text("{}\n", encoding="utf-8")
        with self.assertRaises(RuntimeError):
            r.build(self.tmp, self.tmp / "candidate", "2026-07-22T16:00:00Z", "abc")

    def test_count_mismatch_fails(self) -> None:
        p = self.tmp / r.DOMAIN_SPECS["identity"]["pointer"]
        value = r.read_json(p)
        value["security_records"] = 8784
        write_json(p, value)
        with self.assertRaises(RuntimeError):
            r.build(self.tmp, self.tmp / "candidate", "2026-07-22T16:00:00Z", "abc")

    def test_coverage_boundaries_preserved(self) -> None:
        r.build(self.tmp, self.tmp / "candidate", "2026-07-22T16:00:00Z", "abc")
        boundaries = r.read_json(self.tmp / "candidate/FMDL6X2_FINAL_COVERAGE_BOUNDARIES.json")
        self.assertFalse(boundaries["global_full_data_completion_claimed"])
        self.assertEqual(boundaries["market_reference"]["grade"], "NON_DECISION_GRADE_FALLBACK")

    def test_handoff_fixes_x3_x4_and_completion_rule(self) -> None:
        plan = r.handoff_plan()
        self.assertEqual(len(plan["fmdl6x3"]["stages"]), 6)
        self.assertEqual(len(plan["fmdl6x4"]["stages"]), 6)
        self.assertIn("FMDL-6X4-FINAL", plan["fmdl6_completion_rule"])

    def test_deterministic_replay(self) -> None:
        r.build(self.tmp, self.tmp / "candidate", "2026-07-22T16:00:00Z", "abc")
        r.validate_candidate(self.tmp, self.tmp / "candidate", "2026-07-22T16:00:00Z", "abc", self.tmp / "acceptance.json")
        self.assertEqual(r.read_json(self.tmp / "acceptance.json")["status"], "PASS")

    def test_publish_parity_and_pointers(self) -> None:
        r.build(self.tmp, self.tmp / "candidate", "2026-07-22T16:00:00Z", "abc")
        pointer = r.publish(self.tmp, self.tmp / "candidate", "2026-07-22T16:01:00Z", "abc")
        self.assertEqual(pointer["release_sequence"], 35)
        current = self.tmp / pointer["current_path"]
        release = self.tmp / pointer["release_path"]
        self.assertEqual((current / "FMDL6X2_FINAL_MANIFEST.json").read_bytes(), (release / "FMDL6X2_FINAL_MANIFEST.json").read_bytes())
        self.assertTrue((self.tmp / "outputs/status/FMDL6X2_FULL_STORE_LKG.json").exists())

    def test_failed_build_does_not_replace_lkg(self) -> None:
        r.build(self.tmp, self.tmp / "candidate", "2026-07-22T16:00:00Z", "abc")
        r.publish(self.tmp, self.tmp / "candidate", "2026-07-22T16:01:00Z", "abc")
        lkg = (self.tmp / "outputs/status/FMDL6X2_FULL_STORE_LKG.json").read_bytes()
        p = self.tmp / r.DOMAIN_SPECS["listing_history"]["pointer"]
        value = r.read_json(p)
        value["historical_completion_claimed"] = True
        write_json(p, value)
        with self.assertRaises(RuntimeError):
            r.build(self.tmp, self.tmp / "bad", "2026-07-22T16:02:00Z", "def")
        self.assertEqual(lkg, (self.tmp / "outputs/status/FMDL6X2_FULL_STORE_LKG.json").read_bytes())


if __name__ == "__main__":
    unittest.main()
