from __future__ import annotations

import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("fmdl7final", ROOT / "scripts/fmdl7_final_operational_acceptance.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


class FMDL7FinalTests(unittest.TestCase):
    def test_contract_and_authoritative_bindings(self) -> None:
        contract, errors, hashes = MODULE.validate_contract(ROOT)
        self.assertEqual(errors, [])
        self.assertEqual(contract["phase_id"], "FMDL-7-FINAL")
        self.assertEqual(contract["trade_authority"], "NONE")
        self.assertEqual(contract["acceptance_gates"]["strict_fmdl7_release_sequence"], [48, 49, 50, 51, 52, 53])
        self.assertIn("canonical_package", hashes)
        self.assertIn("handoff", hashes)

    def test_market_asymmetry_and_authority_boundaries(self) -> None:
        contract, errors, _ = MODULE.validate_contract(ROOT)
        self.assertEqual(errors, [])
        markets = {row["market"]: row for row in contract["market_component_bindings"]}
        self.assertIn("FULL_MARKET", markets["A_SHARE"]["research_scope"])
        self.assertEqual(markets["HONG_KONG_STOCK_CONNECT"]["candidate_scope"], "GRADUATION_REQUIRES_HUMAN_REENTRY_REVIEW")
        self.assertTrue(markets["US_EQUITY"]["simulation_scope"].startswith("FORMAL_SIMULATION_CLOSED"))
        self.assertTrue(markets["US_EQUITY"]["real_account_scope"].startswith("BROKERAGE"))
        controls = contract["cross_market_controls"]
        self.assertFalse(controls["forced_common_factor_score"])
        self.assertFalse(controls["global_cross_market_stock_rank"])
        self.assertTrue(controls["human_user_is_only_investment_authority"])

    def test_same_input_byte_replay_and_final_decision(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            one = base / "one"
            two = base / "two"
            generated_at = "2026-07-23T12:00:00Z"
            source_commit = "0" * 40
            first = MODULE.build_candidate(ROOT, one, generated_at, source_commit)
            second = MODULE.build_candidate(ROOT, two, generated_at, source_commit)
            self.assertEqual(first, second)
            self.assertEqual(tree_digest(one), tree_digest(two))
            self.assertEqual(MODULE.validate_candidate(one), [])
            self.assertEqual(first["status"], "FMDL7_CROSS_MARKET_AND_FULL_SYSTEM_FINAL_OPERATIONAL_ACCEPTANCE_ACCEPTED")
            self.assertEqual(first["fmdl7_status"], "COMPLETE_AND_FROZEN")
            self.assertIsNone(first["open_development_gate"])
            self.assertEqual(first["trade_authority"], "NONE")
            self.assertFalse(any(first["zero_mutation_proof"].values()))

    def test_failure_injections_fail_closed(self) -> None:
        contract, errors, _ = MODULE.validate_contract(ROOT)
        self.assertEqual(errors, [])
        rows = MODULE.failure_results(contract)
        self.assertEqual(len(rows), 14)
        self.assertTrue(all(row["status"] == "REJECTED_AS_REQUIRED" for row in rows))
        self.assertTrue(all(row["trade_authority"] == "NONE" for row in rows))
        self.assertTrue(all(not row["state_mutation_authorized"] for row in rows))


if __name__ == "__main__":
    unittest.main()
