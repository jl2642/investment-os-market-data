from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("fmdl7_0_master_plan", ROOT / "scripts/fmdl7_0_master_plan.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class FMDL70MasterPlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract_path = ROOT / "config/fmdl7_0_master_plan_contract.json"
        self.contract = json.loads(self.contract_path.read_text(encoding="utf-8"))

    def test_contract_and_all_authoritative_assets_validate(self) -> None:
        errors, records = MODULE.validate_contract(ROOT, self.contract)
        self.assertEqual(errors, [])
        self.assertEqual(len(records), 7)
        self.assertTrue(all(record["status"] == "PASS" for record in records))

    def test_stage_order_and_round_cap_are_frozen(self) -> None:
        self.assertEqual([row["stage_id"] for row in self.contract["stage_plan"]], MODULE.STAGE_ORDER)
        self.assertEqual(self.contract["round_budget"]["formal_rounds"], 7)
        self.assertEqual(self.contract["round_budget"]["targeted_repair_rounds"], 2)
        self.assertEqual(self.contract["round_budget"]["hard_maximum_rounds"], 9)

    def test_scope_is_fail_closed(self) -> None:
        scope = self.contract["scope"]
        self.assertFalse(scope["new_market_data_refresh_authorized"])
        self.assertFalse(scope["research_workflow_execution_authorized"])
        self.assertFalse(scope["candidate_pool_mutation_authorized"])
        self.assertFalse(scope["simulation_book_mutation_authorized"])
        self.assertFalse(scope["real_account_mutation_authorized"])
        self.assertFalse(scope["rule_mutation_authorized"])
        self.assertFalse(scope["brokerage_or_order_authorized"])
        self.assertEqual(self.contract["trade_authority"], "NONE")

    def test_same_input_build_is_byte_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            first_path = Path(first)
            second_path = Path(second)
            kwargs = {
                "repo_root": ROOT,
                "generated_at": "2026-07-23T07:00:00Z",
                "source_commit": "0123456789abcdef0123456789abcdef01234567",
            }
            first_decision = MODULE.build_candidate(output_dir=first_path, **kwargs)
            second_decision = MODULE.build_candidate(output_dir=second_path, **kwargs)
            self.assertEqual(first_decision, second_decision)
            first_files = sorted(path.name for path in first_path.iterdir())
            second_files = sorted(path.name for path in second_path.iterdir())
            self.assertEqual(first_files, second_files)
            for filename in first_files:
                self.assertEqual((first_path / filename).read_bytes(), (second_path / filename).read_bytes())
            MODULE.verify_manifest(first_path)

    def test_mutation_or_phase_expansion_is_rejected(self) -> None:
        changed = json.loads(json.dumps(self.contract))
        changed["scope"]["candidate_pool_mutation_authorized"] = True
        changed["stage_plan"].append({
            "stage_id": "FMDL-7F",
            "title": "Unauthorized expansion",
            "exit_status": "UNAUTHORIZED",
        })
        errors, _ = MODULE.validate_contract(ROOT, changed)
        self.assertIn("SCOPE_NOT_FAIL_CLOSED:candidate_pool_mutation_authorized", errors)
        self.assertIn("STAGE_ORDER", errors)


if __name__ == "__main__":
    unittest.main()
