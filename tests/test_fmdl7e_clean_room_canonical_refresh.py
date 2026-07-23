from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "fmdl7e",
    REPO / "scripts/fmdl7e_clean_room_canonical_refresh.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def digest_tree(root: Path) -> dict[str, str]:
    result = {}
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        result[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


class FMDL7ETest(unittest.TestCase):
    def test_contract_and_authoritative_bindings(self) -> None:
        contract, errors = MODULE.validate_contract(REPO)
        self.assertEqual(errors, [])
        self.assertEqual(contract["phase_id"], "FMDL-7E")
        self.assertEqual(contract["storage_contract"]["release_sequence"], 53)
        self.assertEqual(contract["canonical_refresh_contract"]["new_canonical_release_sequence"], 9)
        self.assertEqual([x["required_release_sequence"] for x in contract["authoritative_release_bindings"] if x["binding_id"].startswith("FMDL7")], [48, 49, 50, 51, 52])
        self.assertEqual(contract["trade_authority"], "NONE")

    def test_deterministic_package_and_candidate_replay(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            first = root / "first"
            second = root / "second"
            generated_at = "2026-07-23T12:00:00Z"
            source_commit = "a" * 40
            decision_one = MODULE.build(REPO, first, generated_at, source_commit)
            decision_two = MODULE.build(REPO, second, generated_at, source_commit)
            self.assertEqual(decision_one, decision_two)
            self.assertEqual(digest_tree(first), digest_tree(second))
            self.assertEqual(decision_one["release_sequence"], 53)
            self.assertEqual(decision_one["canonical_release_sequence"], 9)
            self.assertEqual(decision_one["trade_authority"], "NONE")
            self.assertFalse(decision_one["active_file_library_canonical"])
            self.assertEqual(decision_one["zero_mutation_proof"], {
                "candidate_pool_mutations": 0,
                "simulation_book_mutations": 0,
                "real_account_mutations": 0,
                "rule_mutations": 0,
                "orders": 0,
            })

    def test_package_members_manifest_and_identity(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "candidate"
            decision = MODULE.build(REPO, output, "2026-07-23T12:30:00Z", "b" * 40)
            package = output / "股票投资助手_CURRENT.zip"
            self.assertTrue(package.exists())
            contract = json.loads((REPO / "config/fmdl7e_clean_room_canonical_refresh_contract.json").read_text(encoding="utf-8"))
            result = MODULE.validate_package(package, contract["required_package_members"])
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["package_sha256"], decision["package_sha256"])
            with zipfile.ZipFile(package, "r") as zf:
                names = zf.namelist()
                self.assertEqual(len(names), len(set(names)))
                self.assertTrue(all(MODULE.safe_member(name) for name in names))
                pointer = json.loads(zf.read("00_CONTROL/CURRENT_POINTER.json"))
                self.assertEqual(pointer["canonical_release_sequence"], 9)
                self.assertEqual(pointer["trade_authority"], "NONE")
                self.assertEqual(pointer["state_posture"], "LAST_KNOWN_GOOD_NOT_CONFIRMED_CURRENT_AFTER_AS_OF")

    def test_failure_injections_fail_closed(self) -> None:
        contract = json.loads((REPO / "config/fmdl7e_clean_room_canonical_refresh_contract.json").read_text(encoding="utf-8"))
        report = MODULE.failure_report(contract, "FMDL7E_TEST")
        self.assertTrue(report["all_rejected_as_required"])
        self.assertEqual(len(report["results"]), 12)
        for row in report["results"]:
            self.assertEqual(row["status"], "REJECTED_AS_REQUIRED")
            self.assertFalse(row["current_replacement_authorized"])
            self.assertFalse(row["lkg_replacement_authorized"])
            self.assertFalse(row["state_mutation_authorized"])
            self.assertEqual(row["trade_authority"], "NONE")

    def test_unsafe_package_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "unsafe.zip"
            with zipfile.ZipFile(path, "w") as zf:
                zf.writestr("../escape.json", "{}")
            result = MODULE.validate_package(path, [])
            self.assertEqual(result["status"], "FAIL")
            self.assertTrue(any(code.startswith("UNSAFE_PACKAGE_PATH") for code in result["errors"]))


if __name__ == "__main__":
    unittest.main()
