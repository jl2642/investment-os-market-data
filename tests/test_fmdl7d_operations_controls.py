from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts/fmdl7d_operations_controls.py"
SPEC = importlib.util.spec_from_file_location("fmdl7d_operations_controls", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FMDL7DOperationsControlsTests(unittest.TestCase):
    def test_contract_and_sources_validate(self) -> None:
        contract, errors, source_hashes = MODULE.validate_contract(REPO_ROOT)
        self.assertEqual([], errors)
        self.assertEqual("FMDL-7D", contract["phase_id"])
        self.assertEqual(8, len(source_hashes))
        self.assertEqual("NONE", contract["trade_authority"])

    def test_record_counts_and_fail_closed_boundaries(self) -> None:
        contract, errors, source_hashes = MODULE.validate_contract(REPO_ROOT)
        self.assertEqual([], errors)
        records = MODULE.rows_from_contract(contract)
        self.assertEqual(6, len(records["CADENCE"]))
        self.assertEqual(18, len(records["RUNBOOK_STEP"]))
        self.assertEqual(16, len(records["MONITORING_CONTROL"]))
        self.assertEqual(12, len(records["STALENESS_POLICY"]))
        self.assertEqual(6, len(records["COST_CONTROL"]))
        self.assertEqual(12, len(records["REPLAY_SCENARIO"]))
        self.assertEqual(12, len(records["ESCALATION_RULE"]))
        self.assertEqual(10, len(records["FAILURE_INJECTION"]))
        self.assertTrue(all(row["trade_authority"] == "NONE" for rows in records.values() for row in rows))
        gates = MODULE.gate_matrix(contract, source_hashes, records)
        self.assertEqual(28, len(gates))
        self.assertTrue(all(row["status"] == "PASS" for row in gates))

    def test_same_input_build_is_byte_identical(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "first"
            second = root / "second"
            MODULE.build_candidate(REPO_ROOT, first, "2026-07-23T08:30:00Z", "TEST-COMMIT")
            MODULE.build_candidate(REPO_ROOT, second, "2026-07-23T08:30:00Z", "TEST-COMMIT")
            self.assertEqual(MODULE.directory_digest(first), MODULE.directory_digest(second))

            quality = json.loads((first / "FMDL7D_QUALITY_REPORT.json").read_text(encoding="utf-8"))
            decision = json.loads((first / "FMDL7D_DECISION.json").read_text(encoding="utf-8"))
            manifest = json.loads((first / "FMDL7D_MANIFEST.json").read_text(encoding="utf-8"))
            self.assertEqual("PASS", quality["quality_status"])
            self.assertEqual(512, quality["logical_shard_count"])
            self.assertEqual(MODULE.EXIT_STATUS, decision["status"])
            self.assertEqual(MODULE.NEXT_GATE, decision["next_gate"])
            self.assertEqual(512, len(manifest["logical_shards"]))
            self.assertEqual("NONE", decision["trade_authority"])

    def test_failure_injections_are_rejected(self) -> None:
        contract, errors, _ = MODULE.validate_contract(REPO_ROOT)
        self.assertEqual([], errors)
        records = MODULE.rows_from_contract(contract)
        failures = records["FAILURE_INJECTION"]
        self.assertEqual(10, len(failures))
        self.assertTrue(all(row["status"] == "REJECTED_AS_REQUIRED" for row in failures))
        self.assertTrue(all(row["current_replacement_authorized"] is False for row in failures))
        self.assertTrue(all(row["lkg_replacement_authorized"] is False for row in failures))
        self.assertTrue(all(row["state_mutation_authorized"] is False for row in failures))


if __name__ == "__main__":
    unittest.main()
