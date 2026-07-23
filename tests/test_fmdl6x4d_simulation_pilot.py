from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from fmdl6x4d_simulation_pilot import (
    EXIT_STATUS,
    build_candidate,
    load_json,
    publish,
    validate_candidate,
    validate_contract,
)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def write_shard_zip(path: Path, domains: dict[str, list[dict]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for domain, rows in domains.items():
            archive.writestr(f"{domain}/00.jsonl", "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows))


class Fmdl6x4dTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        source_contract = Path(__file__).parents[1] / "config" / "fmdl6x4d_simulation_pilot_contract.json"
        target_contract = self.root / "config" / source_contract.name
        target_contract.parent.mkdir(parents=True, exist_ok=True)
        target_contract.write_text(source_contract.read_text(encoding="utf-8"), encoding="utf-8")
        roadmap = self.root / "docs" / "FMDL-6X3_X4_DEVELOPMENT_ROADMAP.md"
        roadmap.parent.mkdir(parents=True, exist_ok=True)
        roadmap.write_text(
            "- 6X4-D — Simulation-only Pilot, Attribution & Failure Recovery\n"
            "- 6X4-E — Cross-market Comparability & Operating Runbook\n",
            encoding="utf-8",
        )
        write_json(self.root / "outputs/status/FMDL6X4C_LAST_SUCCESS.json", {
            "phase_id": "FMDL-6X4-C",
            "release_id": "FMDL6X4C_20260723_fe78ea8b7e74",
            "release_sequence": 44,
            "status": "FMDL6X4C_CANDIDATE_GRADUATION_DECISION_INTERFACE_AND_GUARDRAILS_ACCEPTED",
            "next_gate": "FMDL-6X4-FINAL_PUBLIC_EQUITY_INVESTING_INTEGRATION_RECONCILIATION_AND_OPERATIONAL_ACCEPTANCE",
            "manifest_sha256": "c" * 64,
            "trade_authority": "NONE",
        })
        croot = self.root / "outputs/fmdl6x4/current/candidate_graduation_guardrails"
        symbols = ["AAPL", "MSFT", "NVDA", "JPM", "BRK.B", "XOM", "QQQ"]
        interfaces = []
        for index, symbol in enumerate(symbols):
            reference = symbol == "QQQ"
            interfaces.append({
                "decision_interface_id": f"DI-{index}",
                "canonical_security_id": f"SEC-{index}",
                "canonical_issuer_id": f"ISS-{index}",
                "symbol": symbol,
                "candidate_graduation_status": "NOT_APPLICABLE_REFERENCE_INSTRUMENT" if reference else "BLOCKED_EVIDENCE_AND_DECISION_REQUIREMENTS_PENDING",
                "human_approval_status": "NOT_APPLICABLE_REFERENCE_INSTRUMENT" if reference else "NOT_REQUESTED_PREREQUISITES_INCOMPLETE",
                "blocking_codes": [] if reference else ["DECISION_GRADE_MARKET_DATA_MISSING"],
            })
        guardrails = [{"guardrail_id": f"G-{i}"} for i in range(16)]
        write_shard_zip(croot / "FMDL6X4C_GRADUATION_SHARDS.zip", {"DECISION_INTERFACE": interfaces, "GUARDRAIL_STATUS": guardrails})
        write_json(croot / "FMDL6X4C_DECISION.json", {
            "graduation_event_count": 0,
            "formal_candidate_promotion_count": 0,
            "simulation_gate": "CLOSED_NOT_AUTHORIZED_IN_FMDL6X4C",
        })
        write_json(croot / "FMDL6X4C_MANIFEST.json", {"release_id": "FMDL6X4C_20260723_fe78ea8b7e74"})
        write_json(croot / "FMDL6X4C_SOURCE_BINDING.json", {"market_data_grade": "NON_DECISION_GRADE_FALLBACK"})

        droot = self.root / "outputs/fmdl6x3/current/sector_peer_benchmark"
        horizons = [
            "PRICE_RETURN_21D_EXCESS_VS_QQQ",
            "PRICE_RETURN_63D_EXCESS_VS_QQQ",
            "PRICE_RETURN_126D_EXCESS_VS_QQQ",
            "PRICE_RETURN_252D_EXCESS_VS_QQQ",
            "PRICE_MOMENTUM_12M_EX_1M_EXCESS_VS_QQQ",
        ]
        factors = []
        for sidx, symbol in enumerate(["AAPL", "MSFT", "NVDA"]):
            for hidx, horizon in enumerate(horizons):
                benchmark = 0.01 * (hidx + 1)
                security = benchmark + 0.02 * (sidx - 1)
                factors.append({
                    "relative_factor_id": f"RF-{sidx}-{hidx}",
                    "canonical_security_id": f"SEC-{sidx}",
                    "canonical_issuer_id": f"ISS-{sidx}",
                    "symbol": symbol,
                    "factor_name": horizon,
                    "as_of_date": "2026-07-21",
                    "benchmark_symbol": "QQQ",
                    "benchmark_factor_value": benchmark,
                    "security_factor_value": security,
                    "relative_factor_value": security - benchmark,
                    "data_grade": "NON_DECISION_GRADE_FALLBACK",
                    "candidate_pool_status": "NOT_AUTHORIZED",
                    "trade_authority": "NONE",
                })
        write_shard_zip(droot / "FMDL6X3D_FRAMEWORK_SHARDS.zip", {"BENCHMARK_RELATIVE_FACTOR": factors})
        write_json(droot / "FMDL6X3D_MANIFEST.json", {"release_id": "D3"})

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_contract_accepts_legacy_c_gate_only_with_frozen_roadmap(self) -> None:
        _, errors = validate_contract(self.root)
        self.assertEqual(errors, [])

    def test_contract_rejects_missing_6x4e_roadmap(self) -> None:
        roadmap = self.root / "docs/FMDL-6X3_X4_DEVELOPMENT_ROADMAP.md"
        roadmap.write_text("- 6X4-D — Simulation-only Pilot, Attribution & Failure Recovery\n", encoding="utf-8")
        _, errors = validate_contract(self.root)
        self.assertIn("ROADMAP_REQUIRED_FOLLOWING_STAGE_TEXT", errors)

    def test_build_is_fail_closed_and_zero_exposure(self) -> None:
        candidate = Path("outputs/fmdl6x4d/candidate")
        build_candidate(self.root, candidate, "2026-07-23T05:00:00Z", "abc123")
        control = load_json(self.root / candidate / "FMDL6X4D_SIMULATION_CONTROL_REPORT.json")
        self.assertEqual(control["blocked_issuer_count"], 6)
        self.assertEqual(control["actual_position_count"], 0)
        self.assertFalse(control["simulation_book_mutation_authorized"])

    def test_shadow_attribution_ties_out_without_formal_performance_claim(self) -> None:
        candidate = Path("outputs/fmdl6x4d/candidate")
        build_candidate(self.root, candidate, "2026-07-23T05:00:00Z", "abc123")
        report = load_json(self.root / candidate / "FMDL6X4D_ATTRIBUTION_REPORT.json")
        self.assertEqual(report["shadow_attribution_observation_count"], 15)
        self.assertEqual(report["attribution_tie_out_count"], 5)
        self.assertFalse(report["formal_performance_claim"])
        for row in report["windows"]:
            self.assertAlmostEqual(row["shadow_excess_return"], row["security_contribution_sum"], places=12)

    def test_failure_recovery_scenarios_all_pass_and_mutate_nothing(self) -> None:
        candidate = Path("outputs/fmdl6x4d/candidate")
        build_candidate(self.root, candidate, "2026-07-23T05:00:00Z", "abc123")
        report = load_json(self.root / candidate / "FMDL6X4D_FAILURE_RECOVERY_REPORT.json")
        self.assertEqual(report["failure_recovery_scenario_count"], 10)
        self.assertEqual(report["failure_recovery_pass_count"], 10)
        for row in report["scenarios"]:
            self.assertEqual(row["simulation_book_mutations"], 0)
            self.assertEqual(row["orders"], 0)

    def test_same_input_replay_is_byte_identical(self) -> None:
        candidate = Path("outputs/fmdl6x4d/candidate")
        build_candidate(self.root, candidate, "2026-07-23T05:00:00Z", "abc123")
        acceptance = validate_candidate(
            self.root,
            candidate,
            "2026-07-23T05:00:00Z",
            "abc123",
            Path("outputs/fmdl6x4d/acceptance/result.json"),
        )
        self.assertTrue(acceptance["same_input_byte_replay"])

    def test_publish_creates_release_current_normalized_and_pointers(self) -> None:
        candidate = Path("outputs/fmdl6x4d/candidate")
        manifest = build_candidate(self.root, candidate, "2026-07-23T05:00:00Z", "abc123")
        pointer = publish(self.root, candidate, "2026-07-23T05:01:00Z", "abc123")
        self.assertEqual(pointer["status"], EXIT_STATUS)
        self.assertEqual(pointer["release_sequence"], 45)
        self.assertTrue((self.root / pointer["current_path"] / "FMDL6X4D_MANIFEST.json").is_file())
        self.assertTrue((self.root / pointer["release_path"] / "FMDL6X4D_MANIFEST.json").is_file())
        self.assertEqual(pointer["release_id"], manifest["release_id"])
        self.assertEqual(pointer["trade_authority"], "NONE")


if __name__ == "__main__":
    unittest.main()
