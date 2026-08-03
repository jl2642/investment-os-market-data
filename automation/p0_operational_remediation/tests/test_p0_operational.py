import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "p0_operational.py"


class P0Tests(unittest.TestCase):
    def run_cli(self, *args, cwd=None):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *map(str, args)],
            cwd=cwd,
            text=True,
            capture_output=True,
        )

    def make_repo(self, root: Path, authority="NONE"):
        control = root / "investment_os_runtime/00_CONTROL"
        schemas = root / "investment_os_runtime/20_SCHEMAS_AND_INTERFACES"
        production = root / "investment_os_runtime/80_PRODUCTION_ACCEPTANCE"
        state = root / "investment_os_runtime/30_STATE_CURRENT"

        control.mkdir(parents=True)
        schemas.mkdir(parents=True)
        production.mkdir(parents=True)
        (state / "10_REAL_ACCOUNT").mkdir(parents=True)
        (state / "20_SIMULATION").mkdir()
        (state / "40_CANDIDATE").mkdir()

        source_root = Path(__file__).resolve().parents[3]
        contract_names = [
            "CORE_STATIC_CONSTITUTION_CURRENT.md",
            "CORE_RULE_CATALOG_CURRENT.json",
            "CANONICAL_IO_CONTRACT_CURRENT.json",
            "MARKET_DATA_EOD_CONTRACT_CURRENT.json",
            "PORTFOLIO_SNAPSHOT_CONTRACT_CURRENT.json",
            "PERFORMANCE_ATTRIBUTION_CONTRACT_CURRENT.json",
            "REPORTING_MANIFEST_CONTRACT_CURRENT.json",
            "RESEARCH_FUNNEL_CONTRACT_CURRENT.json",
            "OBSERVABILITY_CONTRACT_CURRENT.json",
            "P0_ACCEPTANCE_REGISTER_CURRENT.json",
            "R6_P0_ACCEPTANCE_CHECKLIST_CURRENT.md",
        ]
        for name in contract_names:
            (control / name).write_bytes(
                (source_root / "investment_os_runtime/00_CONTROL" / name).read_bytes()
            )

        schema_names = [
            "canonical_run_manifest.schema.json",
            "report_manifest.schema.json",
            "p0_acceptance_register.schema.json",
        ]
        for name in schema_names:
            (schemas / name).write_bytes(
                (
                    source_root
                    / "investment_os_runtime/20_SCHEMAS_AND_INTERFACES"
                    / name
                ).read_bytes()
            )

        def dump(path, payload):
            path.write_text(json.dumps(payload), encoding="utf-8")

        dump(control / "EXECUTION_REGISTER_CURRENT.json", {"trade_authority": authority})
        dump(
            control / "R4_OPERATING_PRODUCT_CONTRACT_CURRENT.json",
            {"development_mode": True, "trade_authority": "NONE"},
        )
        dump(
            control / "R5_ATTRIBUTION_CONTRACT_CURRENT.json",
            {"layers": [{"status": "BLOCKED"}], "trade_authority": "NONE"},
        )
        dump(
            control / "R6_PRODUCTION_ACCEPTANCE_CONTRACT_CURRENT.json",
            {
                "production_completion_definition": {"full_month_complete": False},
                "trade_authority": "NONE",
            },
        )
        dump(
            production / "R6_OBSERVATION_LEDGER_CURRENT.json",
            {
                "checkpoint_passed": 1,
                "checkpoint_total": 10,
                "trade_authority": "NONE",
            },
        )
        dump(
            state / "10_REAL_ACCOUNT/REAL_ACCOUNT_POSITIONS_CURRENT.json",
            {"holdings": [], "trade_authority": "NONE"},
        )
        dump(
            state / "20_SIMULATION/SIMULATION_POSITIONS_CURRENT.json",
            {"holdings": [{"security_id": "SIM-1"}], "trade_authority": "NONE"},
        )
        dump(
            state / "40_CANDIDATE/CANDIDATE_CURRENT.json",
            {
                "counts": {
                    "candidate_core": 1,
                    "research_queue": 2,
                    "shadow_track": 1,
                    "ready_for_user_decision": 0,
                },
                "candidate_core_members": [
                    {"security_id": "CORE-1", "trade_authority": "NONE"}
                ],
                "research_queue_members": [
                    {"security_id": "RQ-1", "trade_authority": "NONE"},
                    {"security_id": "RQ-2", "trade_authority": "NONE"},
                ],
                "shadow_track_members": [
                    {"security_id": "SH-1", "trade_authority": "NONE"}
                ],
                "ready_for_user_decision_members": [],
            },
        )

    def test_validate_pass_with_blockers_and_variable_counts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            self.make_repo(Path(temp_dir))
            process = self.run_cli("validate", "--repo-root", temp_dir)
            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
            payload = json.loads(process.stdout)
            self.assertEqual(payload["status"], "PASS_WITH_BLOCKERS")
            self.assertEqual(payload["facts"]["real"], 0)
            self.assertEqual(payload["facts"]["candidate_core"], 1)

    def test_authority_violation_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            self.make_repo(Path(temp_dir), "FULL")
            process = self.run_cli("validate", "--repo-root", temp_dir)
            self.assertNotEqual(process.returncode, 0)
            self.assertIn("TRADE_AUTHORITY", process.stdout)

    def test_missing_authority_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.make_repo(root)
            path = root / "investment_os_runtime/00_CONTROL/EXECUTION_REGISTER_CURRENT.json"
            path.write_text("{}", encoding="utf-8")
            process = self.run_cli("validate", "--repo-root", temp_dir)
            self.assertNotEqual(process.returncode, 0)
            self.assertIn("TRADE_AUTHORITY_MISSING", process.stdout)

    def test_candidate_count_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.make_repo(root)
            path = (
                root
                / "investment_os_runtime/30_STATE_CURRENT/40_CANDIDATE/CANDIDATE_CURRENT.json"
            )
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["counts"]["candidate_core"] = 2
            path.write_text(json.dumps(payload), encoding="utf-8")
            process = self.run_cli("validate", "--repo-root", temp_dir)
            self.assertNotEqual(process.returncode, 0)
            self.assertIn("CANDIDATE_COUNT_MISMATCH", process.stdout)

    def test_run_manifest_is_deterministic(self):
        args = [
            "build-run-manifest",
            "--workflow-name",
            "x",
            "--trigger-type",
            "manual",
            "--started-at",
            "2026-08-03T00:00:00Z",
            "--completed-at",
            "2026-08-03T00:01:00Z",
            "--commit-before",
            "abcdef0",
            "--commit-after",
            "abcdef0",
            "--idempotency-key",
            "k",
            "--status",
            "NO_OP",
        ]
        first = self.run_cli(*args)
        second = self.run_cli(*args)
        self.assertEqual(
            json.loads(first.stdout)["run_id"],
            json.loads(second.stdout)["run_id"],
        )

    def test_report_manifest_blocks_low_completeness(self):
        process = self.run_cli(
            "build-report-manifest",
            "--report-type",
            "MONTHLY",
            "--period-start",
            "2026-07-01",
            "--period-end",
            "2026-07-31",
            "--commit",
            "abcdef0",
            "--completeness",
            "0.4",
        )
        self.assertEqual(
            json.loads(process.stdout)["publication_status"],
            "BLOCKED",
        )

    def test_report_manifest_requires_watermarks_for_formal_status(self):
        process = self.run_cli(
            "build-report-manifest",
            "--report-type",
            "MONTHLY",
            "--period-start",
            "2026-07-01",
            "--period-end",
            "2026-07-31",
            "--commit",
            "abcdef0",
            "--completeness",
            "1",
        )
        payload = json.loads(process.stdout)
        self.assertEqual(payload["publication_status"], "BLOCKED")
        self.assertIn("MISSING_MARKET_DATA_WATERMARK", payload["exceptions"])


if __name__ == "__main__":
    unittest.main()
