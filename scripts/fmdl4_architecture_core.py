from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_hash(payload: Any) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def validate_contract_shape(cfg: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if cfg.get("program_id") != "FMDL-4":
        errors.append("PROGRAM_ID")
    if cfg.get("architecture_state") != "FROZEN_FOR_FMDL4A_EXECUTION":
        errors.append("ARCHITECTURE_STATE")
    if cfg.get("exit_status") != "FMDL4_ARCHITECTURE_ACCEPTED":
        errors.append("EXIT_STATUS")
    if cfg.get("next_gate") != "FMDL-4A_RESEARCH_HANDOFF_AND_CANONICAL_STATE_PACKAGE_ADAPTER":
        errors.append("NEXT_GATE")
    if cfg.get("trade_authority") != "NONE":
        errors.append("TRADE_AUTHORITY")

    expected_phases = ["FMDL-4A", "FMDL-4B", "FMDL-4C", "FMDL-4D", "FMDL-4-FINAL"]
    phases = cfg.get("phase_sequence", [])
    if [phase.get("phase_id") for phase in phases] != expected_phases:
        errors.append("PHASE_SEQUENCE")
    expected_chain = [
        ("FMDL4_ARCHITECTURE_ACCEPTED", "FMDL4A_RESEARCH_HANDOFF_AND_CANONICAL_ADAPTER_ACCEPTED"),
        ("FMDL4A_RESEARCH_HANDOFF_AND_CANONICAL_ADAPTER_ACCEPTED", "FMDL4B_CANDIDATE_RESEARCH_AND_GRADUATION_ACCEPTED"),
        ("FMDL4B_CANDIDATE_RESEARCH_AND_GRADUATION_ACCEPTED", "FMDL4C_INVESTMENT_OS_REENTRY_AND_STATE_CONTROLS_ACCEPTED"),
        ("FMDL4C_INVESTMENT_OS_REENTRY_AND_STATE_CONTROLS_ACCEPTED", "FMDL4D_THESIS_ATTRIBUTION_AND_FEEDBACK_ACCEPTED"),
        ("FMDL4D_THESIS_ATTRIBUTION_AND_FEEDBACK_ACCEPTED", "FMDL4_PUBLIC_EQUITY_INVESTING_AND_INVESTMENT_OS_INTEGRATION_ACCEPTED"),
    ]
    if [(phase.get("entry_gate"), phase.get("exit_gate")) for phase in phases] != expected_chain:
        errors.append("PHASE_GATE_CHAIN")

    layers = cfg.get("layer_model", [])
    if [layer.get("layer_id") for layer in layers] != ["EVIDENCE_LAYER", "RESEARCH_JUDGMENT_LAYER", "INVESTMENT_STATE_LAYER"]:
        errors.append("LAYER_MODEL")
    mutating = [layer.get("layer_id") for layer in layers if layer.get("may_mutate_investment_state")]
    if mutating != ["INVESTMENT_STATE_LAYER"]:
        errors.append("STATE_MUTATION_OWNERSHIP")

    object_ids = {item.get("object_id") for item in cfg.get("canonical_objects", [])}
    required_objects = {
        "FMDL_EVIDENCE_ENVELOPE",
        "PUBLIC_EQUITY_RESEARCH_OBJECT",
        "INVESTMENT_OS_STATE_TRANSITION",
        "THESIS_AND_ATTRIBUTION_RECORD",
    }
    if object_ids != required_objects:
        errors.append("CANONICAL_OBJECTS")

    mapping = cfg.get("investment_os_package_mapping", {})
    if not {"CORE_STATIC", "EVIDENCE", "STATE_CURRENT", "storage_policy"}.issubset(mapping):
        errors.append("PACKAGE_MAPPING")
    if "PROJECT_SOURCES_NOT_REQUIRED" not in str(mapping.get("storage_policy", "")):
        errors.append("STORAGE_POLICY")

    baseline = cfg.get("external_investment_os_baseline", {})
    if baseline.get("status") != "ACTIVE_CANONICAL":
        errors.append("EXTERNAL_BASELINE_STATUS")
    if int(baseline.get("release_sequence", 0)) < 4:
        errors.append("EXTERNAL_BASELINE_SEQUENCE")
    if len(str(baseline.get("package_sha256", ""))) != 64:
        errors.append("EXTERNAL_BASELINE_SHA")
    if baseline.get("project_sources_required") is not False:
        errors.append("PROJECT_SOURCES_REQUIRED")

    required_gates = {
        "ZERO_RAW_SCORE_TO_PORTFOLIO_ACTION",
        "ZERO_CANDIDATE_SIMULATION_REAL_ACCOUNT_STATE_CROSSOVER",
        "ZERO_STATE_MUTATION_WITHOUT_VERSIONED_DIFF",
        "ZERO_RESEARCH_CONCLUSION_WITHOUT_EVIDENCE_LINEAGE",
        "ZERO_STALE_OR_QUARANTINED_EVIDENCE_USED_AS_CURRENT",
        "ZERO_FAILED_PACKAGE_REPLACING_CURRENT",
        "ZERO_AUTOMATIC_REAL_ACCOUNT_ACTION",
        "ZERO_ORDER_EXECUTION",
        "ZERO_TRADE_AUTHORITY",
    }
    if set(cfg.get("global_hard_gates", [])) != required_gates:
        errors.append("GLOBAL_HARD_GATES")

    real_chain = cfg.get("role_separation", {}).get("real_account", {}).get("required_chain", [])
    if real_chain[-1:] != ["USER_CONFIRMATION"] or "RCM_GATE" not in real_chain or "PRE_TRADE_MEMO" not in real_chain:
        errors.append("REAL_ACCOUNT_GATE_CHAIN")
    return errors


def validate_bound_state(root: Path, cfg: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    paths = cfg["bound_inputs"]
    entry = cfg["entry_gate"]

    required_paths = [entry["pointer_path"], entry["release_path"], *paths.values()]
    missing = sorted({path for path in required_paths if not (root / path).exists()})
    if missing:
        return [f"MISSING_BOUND_INPUT:{path}" for path in missing], {"missing_paths": missing}

    fmdl3e_pointer = read_json(root / entry["pointer_path"])
    fmdl3e_release = read_json(root / entry["release_path"])
    if fmdl3e_pointer.get("status") != entry["required_status"]:
        errors.append("FMDL3E_ENTRY_STATUS")
    if fmdl3e_pointer.get("next_gate") != entry["required_next_gate"]:
        errors.append("FMDL3E_ENTRY_NEXT_GATE")
    if fmdl3e_pointer.get("release_id") != fmdl3e_release.get("release_id"):
        errors.append("FMDL3E_POINTER_RELEASE_MISMATCH")
    if fmdl3e_pointer.get("trade_authority") != "NONE" or fmdl3e_release.get("trade_authority") != "NONE":
        errors.append("FMDL3E_TRADE_AUTHORITY")

    fmdl2_pointer = read_json(root / paths["fmdl2_final_pointer"])
    fmdl2_release = read_json(root / paths["fmdl2_final_release"])
    expected_fmdl2 = "FMDL2_FINAL_ACCEPTED_WITH_CONTROLLED_LIMITATIONS"
    if fmdl2_pointer.get("status") != expected_fmdl2 or fmdl2_release.get("status") != expected_fmdl2:
        errors.append("FMDL2_STATUS")
    if fmdl2_pointer.get("release_id") != fmdl2_release.get("release_id"):
        errors.append("FMDL2_POINTER_RELEASE_MISMATCH")
    if fmdl2_release.get("trade_authority") != "NONE":
        errors.append("FMDL2_TRADE_AUTHORITY")

    financial_pointer = read_json(root / paths["fmdl3cd_financial_interface_pointer"])
    financial_interface = read_json(root / paths["fmdl3cd_financial_interface"])
    expected_financial = "FMDL3CD_FINANCIAL_SCORE_AND_INVESTMENT_OS_INTERFACE_ACCEPTED"
    if financial_pointer.get("status") != expected_financial:
        errors.append("FMDL3CD_STATUS")
    if financial_interface.get("status") != "ACTIVE_RESEARCH_ONLY":
        errors.append("FMDL3CD_INTERFACE_STATUS")
    if financial_interface.get("source_release_id") != financial_pointer.get("release_id"):
        errors.append("FMDL3CD_INTERFACE_RELEASE_MISMATCH")
    if financial_interface.get("trade_authority") != "NONE":
        errors.append("FMDL3CD_TRADE_AUTHORITY")

    market_interface = read_json(root / paths["fmdl1_market_interface"])
    if market_interface.get("status") != "ACTIVE":
        errors.append("FMDL1_INTERFACE_STATUS")
    if market_interface.get("downstream_handoff", {}).get("trade_authority") != "NONE":
        errors.append("FMDL1_TRADE_AUTHORITY")

    canonical_pointer = read_json(root / paths["fmdl3e_canonical_pointer"])
    operational_release = read_json(root / paths["fmdl3e_operational_release"])
    if canonical_pointer.get("release_id") != operational_release.get("release_id"):
        errors.append("FMDL3E_CANONICAL_RELEASE_MISMATCH")
    if canonical_pointer.get("status") != entry["required_status"]:
        errors.append("FMDL3E_CANONICAL_STATUS")

    bindings = {
        "fmdl1_interface_id": market_interface.get("interface_id"),
        "fmdl1_current_run_id": market_interface.get("current_release", {}).get("run_id"),
        "fmdl2_release_id": fmdl2_release.get("release_id"),
        "fmdl3cd_release_id": financial_pointer.get("release_id"),
        "fmdl3e_release_id": operational_release.get("release_id"),
        "fmdl3e_baseline_id": operational_release.get("baseline_id"),
        "fmdl3e_universe_symbol_count": operational_release.get("metrics", {}).get("universe_symbol_count"),
    }
    if bindings["fmdl3e_universe_symbol_count"] != 5528:
        errors.append("FMDL3E_UNIVERSE_COUNT")
    return errors, bindings


def manifest(root: Path, files: list[Path]) -> dict[str, Any]:
    return {
        "manifest_version": "1.0.0",
        "files": [
            {
                "path": str(path.relative_to(root)),
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
            for path in sorted(files)
        ],
    }
