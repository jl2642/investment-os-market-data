from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "observe.py"


class ObserveTests(unittest.TestCase):
    def dump(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def make_repo(self, root: Path, *, continuity: str = "2026-08-03", mark_date: str = "2026-08-03", real_total: float = 121.0, bad_authority: bool = False) -> None:
        trade = "FULL" if bad_authority else "NONE"
        holdings_real = [{"security_id": "000001.SZ", "security_name": "A", "asset_class": "A_SHARE_STOCK", "quantity": 10, "available_quantity": 10, "cost_basis": 100, "unit_cost": 10, "mark": 12, "mark_as_of": mark_date, "market_value": 120, "unrealized_pnl": 20, "mark_freshness_status": "FRESH", "position_source_as_of": "2026-08-01_CLOSE"}]
        holdings_sim = [{"security_id": "000002.SZ", "security_name": "B", "asset_class": "A_SHARE_STOCK", "quantity": 20, "available_quantity": 20, "cost_basis": 180, "unit_cost": 9, "mark": 10, "mark_as_of": mark_date, "market_value": 200, "unrealized_pnl": 20, "mark_freshness_status": "FRESH", "position_source_as_of": "2026-08-01_CLOSE"}]
        self.dump(root / "investment_os_runtime/30_STATE_CURRENT/10_REAL_ACCOUNT/REAL_ACCOUNT_POSITIONS_CURRENT.json", {"account": "REAL", "holdings": holdings_real, "summary": {"execution_cash_balance": 1, "account_total_assets": real_total}, "trade_authority": trade})
        self.dump(root / "investment_os_runtime/30_STATE_CURRENT/20_SIMULATION/SIMULATION_POSITIONS_CURRENT.json", {"account": "SIMULATION", "holdings": holdings_sim, "summary": {"execution_cash_balance": 50, "account_total_assets": 250}, "trade_authority": "NONE"})
        self.dump(root / "investment_os_runtime/30_STATE_CURRENT/40_CANDIDATE/CANDIDATE_CURRENT.json", {"as_of": "2026-08-03_CLOSE", "counts": {"candidate_core": 1, "research_queue": 1, "shadow_track": 1, "ready_for_user_decision": 0}, "candidate_core_members": [{"security_id": "A", "trade_authority": "NONE"}], "research_queue_members": [{"security_id": "B", "trade_authority": "NONE"}], "shadow_track_members": [{"security_id": "C", "trade_authority": "NONE"}], "ready_for_user_decision_members": []})
        self.dump(root / "investment_os_runtime/30_STATE_CURRENT/25_PORTFOLIO_MARKS/PORTFOLIO_MARKS_CURRENT.json", {"status": "CURRENT_COMPLETE", "data_watermark": {"latest_mark_date": mark_date}, "marks": [], "trade_authority": "NONE"})
        self.dump(root / "investment_os_runtime/30_STATE_CURRENT/15_PORTFOLIO_INPUT/USER_TRANSACTION_DELTA_LEDGER_CURRENT.json", {"continuity_confirmed_through": continuity, "applied_delta_count": 0, "pending_user_confirmation_count": 0, "orders": 0, "trade_authority": "NONE"})

    def run_build(self, repo: Path, output: Path, conclusion: str = "success") -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(SCRIPT), "build", "--repo-root", str(repo), "--output-root", str(output), "--upstream-workflow", "R2 WP2-R Market Marks Refresh", "--upstream-run-id", "123", "--upstream-run-attempt", "1", "--upstream-conclusion", conclusion, "--upstream-started-at", "2026-08-03T14:45:00Z", "--upstream-completed-at", "2026-08-03T14:50:00Z", "--source-commit", "abcdef0123456789", "--trigger-type", "workflow_run", "--observed-at", "2026-08-03T14:51:00Z"], text=True, capture_output=True)

    def test_success_builds_snapshots_reports_and_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as repo_td, tempfile.TemporaryDirectory() as out_td:
            repo, out = Path(repo_td), Path(out_td)
            self.make_repo(repo)
            result = self.run_build(repo, out)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            ledger = json.loads((out / "investment_os_runtime/80_PRODUCTION_ACCEPTANCE/P0_I1/OPERATING_RUN_LEDGER_CURRENT.json").read_text())
            self.assertEqual(ledger["run_count"], 1)
            self.assertEqual(ledger["success_count"], 1)
            self.assertEqual(len(ledger["entries"][0]["snapshot_ids"]), 2)
            self.assertEqual(ledger["trade_authority"], "NONE")
            validate = subprocess.run([sys.executable, str(SCRIPT), "validate", "--output-root", str(out)], text=True, capture_output=True)
            self.assertEqual(validate.returncode, 0, validate.stdout + validate.stderr)

    def test_continuity_lag_is_provisional_not_silent_pass(self) -> None:
        with tempfile.TemporaryDirectory() as repo_td, tempfile.TemporaryDirectory() as out_td:
            repo, out = Path(repo_td), Path(out_td)
            self.make_repo(repo, continuity="2026-08-02", mark_date="2026-08-03")
            result = self.run_build(repo, out)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            status = json.loads((out / "investment_os_runtime/50_OPERATING_PRODUCTS/OBSERVATION/STATUS_CURRENT.json").read_text())
            self.assertIn("POSITION_CONTINUITY_LAGS_MARK_WATERMARK", status["blockers"])
            self.assertEqual(status["status"], "OBSERVATION_PROVISIONAL")

    def test_tie_out_failure_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as repo_td, tempfile.TemporaryDirectory() as out_td:
            repo, out = Path(repo_td), Path(out_td)
            self.make_repo(repo, real_total=150)
            result = self.run_build(repo, out)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            daily = json.loads((out / "investment_os_runtime/50_OPERATING_PRODUCTS/OBSERVATION/DAILY_CURRENT.json").read_text())
            self.assertIn("ASSET_TIE_OUT_FAILED", daily["blockers"])
            manifest_files = list((out / "investment_os_runtime/80_PRODUCTION_ACCEPTANCE/P0_I1/REPORT_MANIFESTS").glob("DAILY_*.json"))
            manifest = json.loads(manifest_files[0].read_text())
            self.assertEqual(manifest["publication_status"], "BLOCKED")

    def test_failed_upstream_records_failure_without_snapshots(self) -> None:
        with tempfile.TemporaryDirectory() as repo_td, tempfile.TemporaryDirectory() as out_td:
            repo, out = Path(repo_td), Path(out_td)
            self.make_repo(repo)
            result = self.run_build(repo, out, conclusion="failure")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            ledger = json.loads((out / "investment_os_runtime/80_PRODUCTION_ACCEPTANCE/P0_I1/OPERATING_RUN_LEDGER_CURRENT.json").read_text())
            self.assertEqual(ledger["failure_count"], 1)
            self.assertEqual(ledger["entries"][0]["snapshot_ids"], {})
            self.assertFalse((out / "investment_os_runtime/80_PRODUCTION_ACCEPTANCE/P0_I1/EOD_SNAPSHOTS").exists())

    def test_duplicate_run_replaces_not_appends(self) -> None:
        with tempfile.TemporaryDirectory() as repo_td, tempfile.TemporaryDirectory() as out_td:
            repo, out = Path(repo_td), Path(out_td)
            self.make_repo(repo)
            self.assertEqual(self.run_build(repo, out).returncode, 0)
            self.assertEqual(self.run_build(repo, out).returncode, 0)
            ledger = json.loads((out / "investment_os_runtime/80_PRODUCTION_ACCEPTANCE/P0_I1/OPERATING_RUN_LEDGER_CURRENT.json").read_text())
            self.assertEqual(ledger["run_count"], 1)
            self.assertTrue(ledger["duplicate_replaced_on_latest_build"])

    def test_trade_authority_violation_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as repo_td, tempfile.TemporaryDirectory() as out_td:
            repo, out = Path(repo_td), Path(out_td)
            self.make_repo(repo, bad_authority=True)
            result = self.run_build(repo, out)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("TRADE_AUTHORITY_VIOLATION", result.stderr)

    def test_candidate_declared_count_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as repo_td, tempfile.TemporaryDirectory() as out_td:
            repo, out = Path(repo_td), Path(out_td)
            self.make_repo(repo)
            path = repo / "investment_os_runtime/30_STATE_CURRENT/40_CANDIDATE/CANDIDATE_CURRENT.json"
            payload = json.loads(path.read_text())
            payload["counts"]["candidate_core"] = 2
            path.write_text(json.dumps(payload))
            result = self.run_build(repo, out)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("CANDIDATE_COUNT_MISMATCH", result.stderr)


if __name__ == "__main__":
    unittest.main()
