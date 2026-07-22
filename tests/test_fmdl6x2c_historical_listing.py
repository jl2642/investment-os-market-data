from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(MODULE_ROOT))

from fmdl6x2c_candidate import build_candidate, publish, validate_candidate
from fmdl6x2c_common import deterministic_gzip, deterministic_zip, load_json, validate_contract


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def line(obs_date, issuer, security, listing, venue, symbol, name):
    return {
        "observation_date": obs_date,
        "canonical_issuer_id": issuer,
        "canonical_security_id": security,
        "canonical_listing_id": listing,
        "venue": venue,
        "symbol": symbol,
        "official_security_name": name,
        "source_row_id": "ROW-" + listing,
        "source_snapshot_id": "SNAP-" + obs_date,
        "source_authority": "NASDAQ_OFFICIAL",
        "trade_authority": "NONE",
    }


class TestFMDL6X2C(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        shutil.copytree(Path(__file__).resolve().parents[1] / "config", self.tmp / "config")
        current_release = "FMDL6X2B_20260722_9159b4ed7f17"
        write_json(self.tmp / "outputs/status/FMDL6X2B_LAST_SUCCESS.json", {
            "phase_id": "FMDL-6X2-B",
            "release_id": current_release,
            "release_sequence": 31,
            "status": "FMDL6X2B_IDENTITY_CLASSIFICATION_AND_REVIEW_QUEUES_ACCEPTED",
            "next_gate": "FMDL-6X2-C_HISTORICAL_LISTING_AND_LIFECYCLE_BACKFILL",
            "listing_records": 2,
            "trade_authority": "NONE",
        })
        write_json(self.tmp / "outputs/status/FMDL6X2_IDENTITY_LKG.json", {"release_id": current_release})
        self._release("FMDL6X2B_20260721_FIXTURE", "2026-07-21", "2026-07-21T12:00:00Z", [
            line("2026-07-21", "I1", "S1", "L1", "XNAS", "AAA", "Alpha Common Stock"),
            line("2026-07-21", "I2", "S2", "L2", "XNYS", "BBB", "Beta Common Stock"),
        ])
        self._release(current_release, "2026-07-22", "2026-07-22T13:07:07Z", [
            line("2026-07-22", "I1", "S1", "L3", "XNAS", "AAB", "Alpha Common Stock"),
            line("2026-07-22", "I3", "S3", "L4", "XASE", "CCC", "Gamma Common Stock"),
        ], current=True)
        self.candidate = self.tmp / "outputs/fmdl6x2c/candidate"
        build_candidate(self.tmp, self.candidate, "2026-07-22T14:00:00Z", "TESTSHA")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _release(self, release_id, obs, accepted, rows, current=False):
        root = self.tmp / f"datasets/fmdl6x2/releases/{release_id}/identity"
        root.mkdir(parents=True, exist_ok=True)
        write_json(root / "FMDL6X2B_DECISION.json", {
            "phase_id": "FMDL-6X2-B",
            "status": "FMDL6X2B_IDENTITY_CLASSIFICATION_AND_REVIEW_QUEUES_ACCEPTED",
            "release_id": release_id,
            "release_sequence": 31,
            "observation_date": obs,
            "accepted_at": accepted,
            "input_release_id": "A-" + obs,
            "listing_records": len(rows),
            "trade_authority": "NONE",
        })
        write_json(root / "FMDL6X2B_QUALITY_REPORT.json", {"quality_status": "PASS"})
        write_json(root / "FMDL6X2B_MANIFEST.json", {"release_id": release_id, "files": {}})
        (root / "FMDL6X2B_IDENTITY_LINEAGE.jsonl.gz").write_bytes(deterministic_gzip(rows))
        quarantine = [{"symbol": "MTEST", "reason": "UNKNOWN_EXCHANGE"}] if current else []
        (root / "FMDL6X2B_REVIEW_QUEUES.zip").write_bytes(deterministic_zip({
            "INHERITED_SOURCE_SCOPE_QUARANTINE.jsonl": (
                "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in quarantine)
            ).encode()
        }))
        if current:
            out = self.tmp / "outputs/fmdl6x2/current/identity"
            shutil.copytree(root, out)

    def test_01_contract(self):
        _, errors = validate_contract(self.tmp)
        self.assertEqual(errors, [])

    def test_02_snapshot_and_interval_counts(self):
        summary = load_json(self.candidate / "FMDL6X2C_BACKFILL_SUMMARY.json")
        self.assertEqual(summary["snapshot_count"], 2)
        self.assertEqual(summary["listing_observation_records"], 4)
        self.assertEqual(summary["effective_listing_intervals"], 4)

    def test_03_symbol_change_and_disappearance_candidates(self):
        summary = load_json(self.candidate / "FMDL6X2C_BACKFILL_SUMMARY.json")
        self.assertEqual(summary["event_type_counts"]["SYMBOL_CHANGE_CANDIDATE"], 1)
        self.assertEqual(summary["event_type_counts"]["LISTING_DISAPPEARANCE_CANDIDATE"], 1)

    def test_04_no_fabricated_effective_dates(self):
        quality = load_json(self.candidate / "FMDL6X2C_QUALITY_REPORT.json")
        self.assertEqual(quality["fabricated_effective_dates"], 0)
        self.assertEqual(quality["exact_effective_date_event_count"], 0)

    def test_05_coverage_gap_disclosed(self):
        coverage = load_json(self.candidate / "FMDL6X2C_COVERAGE_REPORT.json")
        self.assertFalse(coverage["historical_completion_claimed"])
        self.assertEqual(coverage["coverage_intervals"][0]["start_date"], "2005-01-01")

    def test_06_queues_and_inherited_quarantine(self):
        summary = load_json(self.candidate / "FMDL6X2C_BACKFILL_SUMMARY.json")
        self.assertEqual(summary["review_queue_counts"]["INHERITED_SOURCE_SCOPE_QUARANTINE"], 1)
        self.assertGreater(summary["review_queue_counts"]["HISTORICAL_EFFECTIVE_DATE_CONFIDENCE_QUEUE"], 0)

    def test_07_shard_count(self):
        quality = load_json(self.candidate / "FMDL6X2C_QUALITY_REPORT.json")
        self.assertEqual(quality["manifested_shard_count"], 384)

    def test_08_same_input_replay(self):
        result = validate_candidate(
            self.tmp,
            self.candidate,
            "2026-07-22T14:00:00Z",
            "TESTSHA",
            self.tmp / "acceptance.json",
        )
        self.assertEqual(result["status"], "PASS")

    def test_09_publish_and_collision(self):
        pointer = publish(self.tmp, self.candidate, "2026-07-22T14:01:00Z", "TESTSHA")
        self.assertTrue((self.tmp / pointer["current_path"]).is_dir())
        self.assertTrue((self.tmp / pointer["release_path"]).is_dir())
        with self.assertRaises(RuntimeError):
            publish(self.tmp, self.candidate, "2026-07-22T14:02:00Z", "TESTSHA")


if __name__ == "__main__":
    unittest.main()
