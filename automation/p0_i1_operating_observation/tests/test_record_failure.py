from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class RecordFailureTests(unittest.TestCase):
    def test_minimal_failure_evidence_is_validated_by_observer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            error_log = root / "build.log"
            error_log.write_text("ValueError: CANDIDATE_COUNT_MISMATCH", encoding="utf-8")
            script = Path(__file__).resolve().parents[1] / "record_failure.py"
            observe = Path(__file__).resolve().parents[1] / "observe.py"
            subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--output-root", str(root),
                    "--upstream-workflow", "R2 WP2-R Market Marks Refresh",
                    "--upstream-run-id", "12345",
                    "--upstream-run-attempt", "1",
                    "--upstream-conclusion", "failure",
                    "--upstream-started-at", "2026-08-05T14:45:00Z",
                    "--upstream-completed-at", "2026-08-05T14:46:00Z",
                    "--source-commit", "abc123",
                    "--trigger-type", "workflow_run",
                    "--observed-at", "2026-08-05T14:47:00Z",
                    "--error-file", str(error_log),
                ],
                check=True,
            )
            subprocess.run(
                [sys.executable, str(observe), "validate", "--output-root", str(root)],
                check=True,
            )
            ledger = json.loads(
                (root / "investment_os_runtime/80_PRODUCTION_ACCEPTANCE/P0_I1/OPERATING_RUN_LEDGER_CURRENT.json").read_text(encoding="utf-8")
            )
            latest = ledger["entries"][-1]
            self.assertEqual(latest["status"], "FAIL")
            self.assertEqual(latest["snapshot_ids"], {})
            self.assertIn("OBSERVATION_BUILD_FAILED", latest["exceptions"])
            self.assertEqual(latest["trade_authority"], "NONE")


if __name__ == "__main__":
    unittest.main()
