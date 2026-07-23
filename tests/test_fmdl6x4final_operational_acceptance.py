from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fmdl6x4final_operational_acceptance import (
    EXIT_STATUS,
    NEXT_GATE,
    build_candidate,
    load_json,
    publish,
    validate_candidate,
    validate_contract,
)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")


class Fmdl6x4FinalTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        source_contract = Path(__file__).parents[1] / "config" / "fmdl6x4final_operational_acceptance_contract.json"
        target_contract = self.root / "config" / source_contract.name
        target_contract.parent.mkdir(parents=True, exist_ok=True)
        target_contract.write_text(source_contract.read_text(encoding="utf-8"), encoding="utf-8")
        roadmap = self.root / "docs" / "FMDL-6X3_X4_DEVELOPMENT_ROADMAP.md"
        roadmap.parent.mkdir(parents=True, exist_ok=True)
        roadmap.write_text(
            "- **6X4-FINAL** — US Research Adapter Operational Acceptance & FMDL-6 Freeze\n"
            "FMDL-6 is complete only after 6X4-FINAL accepts X1–X4 and freezes the US research adapter.\n"
            "FMDL-7 then performs cross-market and full-system final operational acceptance.\n",
            encoding="utf-8",
        )
        contract = load_json(target_contract)
        for spec in contract["component_pointers"]:
            write_json(self.root / spec["path"], {
                "phase_id": spec["required_phase_id"],
                "release_id": spec["required_release_id"],
                "release_sequence": spec["required_release_sequence"],
                "status": spec["required_status"],
                "manifest_sha256": (str(spec["required_release_sequence"]) * 64)[:64],
                "current_path": f"outputs/current/{spec['component_id']}",
                "release_path": f"datasets/releases/{spec['required_release_id']}",
                "formal_workflow_execution_count": 0,
                "formal_candidate_promotion_count": 0,
                "graduation_event_count": 0,
                "investment_recommendation_count": 0,
                "registered_workflow_output_count": 0,
                "zero_mutation_proof": {
                    "candidate_pool_mutations": 0,
                    "simulation_book_mutations": 0,
                    "real_account_mutations": 0,
                    "orders": 0,
                },
                "trade_authority": "NONE",
            })

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_contract_binds_all_x1_to_x4_components(self) -> None:
        _, components, errors = validate_contract(self.root)
        self.assertEqual(errors, [])
        self.assertEqual(len(components), 8)
        self.assertIn("FMDL-6X4-E", components)

    def test_contract_rejects_missing_component_pointer(self) -> None:
        (self.root / "outputs/status/FMDL6X4D_LAST_SUCCESS.json").unlink()
        _, _, errors = validate_contract(self.root)
        self.assertIn("COMPONENT_POINTER_MISSING:FMDL-6X4-D", errors)

    def test_contract_rejects_trade_authority_escalation(self) -> None:
        path = self.root / "outputs/status/FMDL6X4C_LAST_SUCCESS.json"
        pointer = load_json(path)
        pointer["trade_authority"] = "ORDER"
        write_json(path, pointer)
        _, _, errors = validate_contract(self.root)
        self.assertIn("FMDL-6X4-C:TRADE_AUTHORITY_MISMATCH", errors)

    def test_build_freezes_adapter_and_opens_only_fmdl7(self) -> None:
        candidate = Path("outputs/fmdl6x4final/candidate")
        build_candidate(self.root, candidate, "2026-07-23T07:00:00Z", "abc123")
        decision = load_json(self.root / candidate / "FMDL6X4FINAL_DECISION.json")
        quality = load_json(self.root / candidate / "FMDL6X4FINAL_QUALITY_REPORT.json")
        self.assertEqual(decision["status"], EXIT_STATUS)
        self.assertEqual(decision["next_gate"], NEXT_GATE)
        self.assertEqual(decision["fmdl6_status"], "COMPLETE_AND_FROZEN")
        self.assertEqual(quality["quality_status"], "PASS")
        self.assertEqual(quality["acceptance_gate_actual"]["component_count"], 8)
        self.assertEqual(quality["acceptance_gate_actual"]["logical_shard_count"], 384)

    def test_no_candidate_simulation_real_account_or_order_mutation(self) -> None:
        candidate = Path("outputs/fmdl6x4final/candidate")
        build_candidate(self.root, candidate, "2026-07-23T07:00:00Z", "abc123")
        quality = load_json(self.root / candidate / "FMDL6X4FINAL_QUALITY_REPORT.json")
        self.assertEqual(quality["zero_mutation_proof"], {
            "candidate_pool_mutations": 0,
            "simulation_book_mutations": 0,
            "real_account_mutations": 0,
            "orders": 0,
        })
        self.assertEqual(quality["trade_authority"], "NONE")

    def test_same_input_replay_is_byte_identical(self) -> None:
        candidate = Path("outputs/fmdl6x4final/candidate")
        build_candidate(self.root, candidate, "2026-07-23T07:00:00Z", "abc123")
        result = validate_candidate(
            self.root,
            candidate,
            "2026-07-23T07:00:00Z",
            "abc123",
            Path("outputs/fmdl6x4final/acceptance/result.json"),
        )
        self.assertTrue(result["same_input_byte_replay"])

    def test_publish_creates_release_current_normalized_and_pointers(self) -> None:
        candidate = Path("outputs/fmdl6x4final/candidate")
        manifest = build_candidate(self.root, candidate, "2026-07-23T07:00:00Z", "abc123")
        pointer = publish(self.root, candidate, "2026-07-23T07:01:00Z", "abc123")
        self.assertEqual(pointer["status"], EXIT_STATUS)
        self.assertEqual(pointer["release_sequence"], 47)
        self.assertEqual(pointer["release_id"], manifest["release_id"])
        self.assertTrue((self.root / pointer["current_path"] / "FMDL6X4FINAL_MANIFEST.json").is_file())
        self.assertTrue((self.root / pointer["release_path"] / "FMDL6X4FINAL_MANIFEST.json").is_file())
        self.assertTrue((self.root / "outputs/status/FMDL6X4FINAL_LAST_SUCCESS.json").is_file())
        self.assertTrue((self.root / "outputs/status/FMDL6_US_RESEARCH_ADAPTER_FINAL_LKG.json").is_file())


if __name__ == "__main__":
    unittest.main()
