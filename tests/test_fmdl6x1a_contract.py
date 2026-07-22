from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_fmdl6x1a_contract.py"
CONFIG = ROOT / "config" / "fmdl6x1a_existing_pilot_audit_dual_activation_contract.json"

spec = importlib.util.spec_from_file_location("fmdl6x1a_validator", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


class FMDL6X1AContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = json.loads(CONFIG.read_text(encoding="utf-8"))

    def test_candidate_contract_passes(self) -> None:
        self.assertEqual(module.validate(self.contract), [])

    def test_brokerage_gate_cannot_open_without_channel(self) -> None:
        mutated = json.loads(json.dumps(self.contract))
        mutated["dual_activation"]["brokerage_real_account_gate"]["status"] = "OPEN"
        self.assertIn("brokerage gate must remain closed", module.validate(mutated))

    def test_trade_authority_escalation_is_rejected(self) -> None:
        mutated = json.loads(json.dumps(self.contract))
        mutated["trade_authority"] = "EXECUTE"
        self.assertIn("trade authority must remain NONE", module.validate(mutated))

    def test_unbounded_phase_growth_is_rejected(self) -> None:
        mutated = json.loads(json.dumps(self.contract))
        mutated["fixed_execution_plan"]["planned_subphases"].append("FMDL-6X1-E_UNPLANNED")
        self.assertIn("fixed phase sequence mismatch", module.validate(mutated))

    def test_portfolio_mutation_is_rejected(self) -> None:
        mutated = json.loads(json.dumps(self.contract))
        mutated["zero_mutation_proof"]["simulation_mutations"] = 1
        self.assertIn("simulation_mutations must equal zero", module.validate(mutated))


if __name__ == "__main__":
    unittest.main()
