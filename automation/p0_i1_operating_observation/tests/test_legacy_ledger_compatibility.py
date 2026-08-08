from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from automation.p0_i1_operating_observation.observe import PROD, build, validate_output


ROOT = Path(__file__).resolve().parents[3]
CANONICAL_LEDGER = ROOT / PROD / "OPERATING_RUN_LEDGER_CURRENT.json"


class LegacyLedgerCompatibilityTest(unittest.TestCase):
    def test_canonical_legacy_row_can_accept_and_validate_new_observation(self) -> None:
        canonical = json.loads(CANONICAL_LEDGER.read_text(encoding="utf-8"))
        self.assertTrue(canonical.get("entries"))
        for row in canonical["entries"]:
            self.assertTrue(row.get("observed_at"), row)
            manifest = row.get("run_manifest")
            self.assertTrue(manifest, row)
            self.assertTrue((ROOT / manifest).exists(), manifest)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_root = Path(tmpdir)
            ledger_path = output_root / PROD / "OPERATING_RUN_LEDGER_CURRENT.json"
            ledger_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(CANONICAL_LEDGER, ledger_path)

            args = argparse.Namespace(
                repo_root=str(ROOT),
                output_root=str(output_root),
                upstream_workflow="R2 WP2-R Market Marks Refresh",
                upstream_run_id="legacy-ledger-regression",
                upstream_run_attempt=1,
                upstream_conclusion="success",
                upstream_started_at="2026-08-08T03:00:00Z",
                upstream_completed_at="2026-08-08T03:01:00Z",
                upstream_run_url="https://github.com/jl2642/investment-os-market-data/actions/runs/test",
                source_commit="legacy-ledger-regression-source",
                trigger_type="pull_request",
                observed_at="2026-08-08T03:02:00Z",
                summary_output=None,
            )
            summary = build(args)
            self.assertIn(summary["status"], {"PASS", "PASS_WITH_EXCEPTIONS"})

            result = validate_output(argparse.Namespace(output_root=str(output_root)))
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["run_count"], len(canonical["entries"]) + 1)
            self.assertEqual(result["orders"], 0)
            self.assertEqual(result["trade_authority"], "NONE")

            updated = json.loads(ledger_path.read_text(encoding="utf-8"))
            latest = updated["entries"][-1]
            self.assertEqual(latest["upstream_run_id"], "legacy-ledger-regression")
            self.assertTrue(latest.get("run_manifest"))


if __name__ == "__main__":
    unittest.main()
