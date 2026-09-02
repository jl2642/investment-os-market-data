import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class Phase4FinalProductClosureTest(unittest.TestCase):
    def test_final_system_authority(self):
        p = json.loads((ROOT / "investment_os_runtime/00_CONTROL/SYSTEM_CURRENT.json").read_text(encoding="utf-8"))
        closure = p["final_product_closure"]
        self.assertEqual(closure["plan_version"], "FINAL_PRODUCT_CLOSURE_20260902_V1")
        self.assertTrue(closure["product_definition_frozen"])
        for n in range(5):
            self.assertEqual(closure[f"phase_{n}"]["status"], "COMPLETE")
        self.assertEqual(closure["phases_remaining"], [])
        self.assertTrue(closure["completion_claim_allowed"])
        self.assertTrue(p["acceptance"]["development_closed"])
        self.assertEqual(p["orders"], 0)
        self.assertEqual(p["trade_authority"], "NONE")

    def test_ten_capabilities_frozen(self):
        p = json.loads((ROOT / "investment_os_runtime/00_CONTROL/SYSTEM_CURRENT.json").read_text(encoding="utf-8"))
        caps = p["final_product_closure"]["phase_4"]["core_capabilities"]
        self.assertEqual(len(caps), 10)
        self.assertTrue(all(x["status"] == "PASS" for x in caps))
        self.assertEqual(p["final_product_closure"]["phase_4"]["current_holding_monitoring_coverage"], "22/22")

    def test_runtime_registry_is_final(self):
        p = json.loads((ROOT / "investment_os_runtime/00_CONTROL/ACTIVE_WORKFLOW_REGISTRY.json").read_text(encoding="utf-8"))
        self.assertEqual(p["phase3_status"], "COMPLETE_ON_MAIN_RUNTIME")
        self.assertEqual(p["phase4_status"], "COMPLETE_FINAL_PRODUCT_FROZEN")
        self.assertEqual(p["orders"], 0)
        self.assertEqual(p["trade_authority"], "NONE")

    def test_capability_matrix_declares_scope_and_human_boundary(self):
        text = (ROOT / "investment_os_runtime/00_CONTROL/FINAL_PRODUCT_CAPABILITY_MATRIX_CURRENT.md").read_text(encoding="utf-8")
        self.assertEqual(text.count("| PASS |"), 10)
        self.assertIn("22/22", text)
        self.assertIn("trade_authority", text)
        self.assertIn("human", text.lower())

if __name__ == "__main__":
    unittest.main()
