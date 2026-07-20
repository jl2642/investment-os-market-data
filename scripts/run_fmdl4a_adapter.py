from __future__ import annotations

import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from scripts import fmdl4a_core as core

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("Asia/Shanghai")
CONFIG = ROOT / "config/fmdl4a_research_handoff_adapter.json"


def load_bound_state(cfg: dict) -> tuple[list[str], dict, dict]:
    errors: list[str] = []
    entry = cfg["entry_gate"]
    inputs = cfg["inputs"]
    required = [entry["pointer_path"], entry["release_path"], entry["contract_path"], *inputs.values()]
    missing = [path for path in required if not (ROOT / path).exists()]
    if missing:
        return [f"MISSING_INPUT:{path}" for path in missing], {}, {}

    architecture_pointer = core.read_json(ROOT / entry["pointer_path"])
    architecture_release = core.read_json(ROOT / entry["release_path"])
    architecture_contract = core.read_json(ROOT / entry["contract_path"])
    if architecture_pointer.get("status") != entry["required_status"]:
        errors.append("ARCHITECTURE_STATUS")
    if architecture_pointer.get("next_gate") != entry["required_next_gate"]:
        errors.append("ARCHITECTURE_NEXT_GATE")
    if architecture_pointer.get("release_id") != architecture_release.get("release_id"):
        errors.append("ARCHITECTURE_POINTER_RELEASE_MISMATCH")
    if architecture_release.get("trade_authority") != "NONE":
        errors.append("ARCHITECTURE_TRADE_AUTHORITY")

    external = architecture_contract.get("external_investment_os_baseline", {})
    cfg_external = cfg["external_canonical_base"]
    comparisons = {
        "canonical_package": "package_name",
        "release_sequence": "release_sequence",
        "run_id": "run_id",
        "asset_architecture_version": "asset_architecture_version",
        "runtime_schema_version": "runtime_schema_version",
        "package_sha256": "package_sha256",
        "status": "status",
    }
    for architecture_key, cfg_key in comparisons.items():
        if external.get(architecture_key) != cfg_external.get(cfg_key):
            errors.append(f"EXTERNAL_BASE_MISMATCH:{architecture_key}")

    fmdl2_release = core.read_json(ROOT / inputs["fmdl2_final_release"])
    screening_release = core.read_json(ROOT / inputs["screening_release"])
    financial_interface = core.read_json(ROOT / inputs["financial_interface"])
    financial_release = core.read_json(ROOT / inputs["financial_release"])
    fmdl3e_release = core.read_json(ROOT / inputs["fmdl3e_release"])

    if fmdl2_release.get("status") != "FMDL2_FINAL_ACCEPTED_WITH_CONTROLLED_LIMITATIONS":
        errors.append("FMDL2_STATUS")
    if screening_release.get("fmdl2d_release_id") != fmdl2_release.get("release_id"):
        errors.append("SCREENING_FMDL2_BINDING")
    if financial_interface.get("status") != "ACTIVE_RESEARCH_ONLY":
        errors.append("FINANCIAL_INTERFACE_STATUS")
    if financial_release.get("status") != "FMDL3CD_FINANCIAL_SCORE_AND_INVESTMENT_OS_INTERFACE_ACCEPTED":
        errors.append("FINANCIAL_RELEASE_STATUS")
    if financial_interface.get("source_release_id") != financial_release.get("source_hardening_release_id"):
        errors.append("FINANCIAL_SOURCE_RELEASE_BINDING")
    if fmdl3e_release.get("status") != "FMDL3E_UNIFIED_OPERATIONAL_ACCEPTANCE_AND_CANONICAL_CLOSURE_ACCEPTED":
        errors.append("FMDL3E_STATUS")

    for payload, label in [
        (fmdl2_release, "FMDL2"),
        (screening_release, "SCREENING"),
        (financial_interface, "FINANCIAL_INTERFACE"),
        (financial_release, "FINANCIAL_RELEASE"),
        (fmdl3e_release, "FMDL3E"),
    ]:
        authority = payload.get("trade_authority") or payload.get("downstream_handoff", {}).get("trade_authority")
        if authority != "NONE":
            errors.append(f"{label}_TRADE_AUTHORITY")

    releases = {
        "architecture_release_id": architecture_release.get("release_id"),
        "FMDL-2": fmdl2_release.get("release_id"),
        "screening_release_id": screening_release.get("release_id"),
        "FMDL-3C-D": financial_release.get("release_id"),
        "fmdl3cd_source_hardening_release_id": financial_release.get("source_hardening_release_id"),
        "FMDL-3E-FINAL": fmdl3e_release.get("release_id"),
        "fmdl3e_baseline_id": fmdl3e_release.get("baseline_id"),
    }
    source_state = {
        "architecture_pointer": architecture_pointer,
        "architecture_release": architecture_release,
        "architecture_contract": architecture_contract,
        "fmdl2_release": fmdl2_release,
        "screening_release": screening_release,
        "financial_interface": financial_interface,
        "financial_release": financial_release,
        "fmdl3e_release": fmdl3e_release,
    }
    return errors, releases, source_state


def flattened(records: list[dict]) -> pd.DataFrame:
    rows = []
    for record in records:
        rows.append({
            "evidence_id": record["evidence_id"],
            "symbol": record["symbol"],
            "name": record["name"],
            "as_of": record["as_of"],
            "source_release_ids_json": core.json_dumps(record["source_release_ids"]),
            "market_evidence_json": core.json_dumps(record["market_evidence"]),
            "financial_evidence_json": core.json_dumps(record["financial_evidence"]),
            "valuation_evidence_json": core.json_dumps(record["valuation_evidence"]),
            "shareholder_return_evidence_json": core.json_dumps(record["shareholder_return_evidence"]),
            "screening_evidence_json": core.json_dumps(record["screening_evidence"]),
            "quality_state": record["quality_state"],
            "controlled_limitations_json": core.json_dumps(record["controlled_limitations"]),
            "semantic_hash": record["semantic_hash"],
            "authority": record["authority"],
            "trade_authority": record["trade_authority"],
        })
    return pd.DataFrame(rows).sort_values("symbol").reset_index(drop=True)


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in sorted(records, key=lambda item: item["symbol"]):
            handle.write(core.json_dumps(record) + "\n")


def deterministic_zip(source_root: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(p for p in source_root.rglob("*") if p.is_file()):
            relative = path.relative_to(source_root).as_posix()
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def main() -> int:
    cfg = core.read_json(CONFIG)
    candidate = ROOT / cfg["publication"]["candidate_root"]
    if candidate.exists():
        shutil.rmtree(candidate)
    candidate.mkdir(parents=True)
    adapter_root = candidate / cfg["adapter"]["overlay_namespace"]
    core_static = adapter_root / "CORE_STATIC"
    evidence = adapter_root / "EVIDENCE"
    state_current = adapter_root / "STATE_CURRENT"
    for path in [core_static, evidence, state_current]:
        path.mkdir(parents=True, exist_ok=True)

    started = datetime.now(TZ)
    gate_errors, releases, source_state = load_bound_state(cfg)
    inputs = cfg["inputs"]
    if gate_errors and any(error.startswith("MISSING_INPUT") for error in gate_errors):
        decision = {
            "decision_version": "1.0.0",
            "program_id": "FMDL-4A",
            "status": "FMDL4A_RESEARCH_HANDOFF_AND_CANONICAL_ADAPTER_REJECTED",
            "hard_failures": gate_errors,
            "trade_authority": "NONE",
        }
        core.write_json(candidate / "FMDL4A_DECISION.json", decision)
        raise SystemExit("FMDL-4A missing required inputs")

    unified = pd.read_parquet(ROOT / inputs["fmdl3e_unified_current"]).sort_values("symbol").reset_index(drop=True)
    financial = pd.read_parquet(ROOT / inputs["financial_score"]).sort_values("symbol").reset_index(drop=True)
    longlist = pd.read_csv(ROOT / inputs["screening_longlist"], dtype={"symbol": str}).sort_values("overall_rank").reset_index(drop=True)

    duplicate_unified = int(unified["symbol"].duplicated().sum())
    duplicate_financial = int(financial["symbol"].duplicated().sum())
    duplicate_longlist = int(longlist["symbol"].duplicated().sum())
    unified_symbols = set(unified["symbol"].astype(str))
    financial_symbols = set(financial["symbol"].astype(str))
    longlist_symbols = set(longlist["symbol"].astype(str))
    missing_financial = sorted(unified_symbols - financial_symbols)
    unknown_longlist = sorted(longlist_symbols - unified_symbols)

    financial_index = financial.set_index("symbol").to_dict(orient="index")
    longlist_index = longlist.set_index("symbol").to_dict(orient="index")
    envelope_release_ids = {key: str(releases[key]) for key in ["FMDL-2", "FMDL-3C-D", "FMDL-3E-FINAL"]}
    records = [
        core.envelope_record(
            row.to_dict(),
            financial_index.get(str(row["symbol"]), {}),
            longlist_index.get(str(row["symbol"])),
            release_ids=envelope_release_ids,
            cfg=cfg,
        )
        for _, row in unified.iterrows()
    ]
    envelope_shape_errors = sum(bool(core.validate_envelope_shape(record)) for record in records)
    envelope_frame = flattened(records)
    evidence_by_symbol = envelope_frame.set_index("symbol")["evidence_id"].to_dict()

    research_registry = longlist.copy()
    research_registry["evidence_id"] = research_registry["symbol"].map(evidence_by_symbol)
    research_registry["lead_skill"] = cfg["public_equity_routing"]["default_lead_skill"]
    research_registry["route_json"] = research_registry["research_priority"].map(lambda value: core.json_dumps(core.route_for_priority(value, cfg)))
    research_registry["handoff_status"] = "HANDOFF_READY_RESEARCH_NOT_STARTED"
    research_registry["research_object_status"] = "NOT_CREATED_FMDL4B"
    research_registry["state_mutation_authorized"] = False
    research_registry["trade_authority"] = "NONE"

    routing_contract = {
        "contract_version": "1.0.0",
        "status": "ACTIVE_RESEARCH_ROUTING_ONLY",
        "source_release_ids": releases,
        **cfg["public_equity_routing"],
        "prohibited_actions": [
            "RAW_SCORE_AUTOMATIC_PROMOTION",
            "AUTOMATIC_SIMULATION_ADMISSION",
            "AUTOMATIC_REAL_ACCOUNT_ACTION",
            "ORDER_GENERATION",
            "BROKER_EXECUTION",
        ],
        "authority": "RESEARCH_ROUTING_ONLY_NO_INVESTMENT_STATE_MUTATION",
        "trade_authority": "NONE",
    }
    handoff_contract = {
        "contract_version": "1.0.0",
        "program_id": "FMDL-4A",
        "status": "ACTIVE_READ_ONLY_HANDOFF",
        "base_package": cfg["external_canonical_base"],
        "source_release_ids": releases,
        "canonical_objects": ["FMDL_EVIDENCE_ENVELOPE"],
        "research_object_owner": "FMDL-4B",
        "state_transition_owner": "FMDL-4C",
        "adapter_mode": cfg["adapter"]["mode"],
        "authority": cfg["authority"],
        "trade_authority": "NONE",
    }
    authority_firewall = {
        "firewall_version": "1.0.0",
        "allowed": ["CREATE_EVIDENCE_ENVELOPE", "CREATE_RESEARCH_PRIORITY_HANDOFF", "CREATE_RELEASE_BINDING", "CREATE_ADDITIVE_OVERLAY"],
        "prohibited": ["MUTATE_CANDIDATE_POOL", "MUTATE_SIMULATION", "MUTATE_REAL_ACCOUNT", "CREATE_ORDER", "EXECUTE_TRADE"],
        "base_state_mutation_count": 0,
        "existing_path_replacement_count": 0,
        "trade_authority": "NONE",
    }
    source_registry = {
        "registry_version": "1.0.0",
        "source_release_ids": releases,
        "source_paths": inputs,
        "external_canonical_base": cfg["external_canonical_base"],
        "authority": "DATA_AND_RESEARCH_EVIDENCE_ONLY",
        "trade_authority": "NONE",
    }
    limitation_register = {
        "register_version": "1.0.0",
        "limitations": cfg["controlled_limitations"],
        "trade_authority": "NONE",
    }
    binding_state = {
        "state_version": "1.0.0",
        "base_package": cfg["external_canonical_base"],
        "candidate_release_sequence": cfg["adapter"]["candidate_release_sequence"],
        "candidate_asset_architecture_version": cfg["adapter"]["candidate_asset_architecture_version"],
        "candidate_runtime_schema_version": cfg["adapter"]["candidate_runtime_schema_version"],
        "source_release_ids": releases,
        "adapter_mode": cfg["adapter"]["mode"],
        "unchanged_state_domains": ["REAL_ACCOUNT", "SIMULATION_LAB", "CANDIDATE_POOL", "TRADE_REGISTER", "POSITION_THESIS"],
        "base_state_mutation_count": 0,
        "existing_path_replacement_count": 0,
        "candidate_pool_mutation_count": 0,
        "simulation_mutation_count": 0,
        "real_account_mutation_count": 0,
        "trade_authority": "NONE",
    }

    core.write_json(core_static / "FMDL4A_RESEARCH_HANDOFF_CONTRACT.json", handoff_contract)
    core.write_json(core_static / "FMDL4A_PUBLIC_EQUITY_ROUTING_CONTRACT.json", routing_contract)
    core.write_json(core_static / "FMDL4A_AUTHORITY_FIREWALL.json", authority_firewall)
    envelope_frame.to_parquet(evidence / "FMDL4A_EVIDENCE_ENVELOPE_CURRENT.parquet", index=False)
    write_jsonl(evidence / "FMDL4A_EVIDENCE_ENVELOPE_CURRENT.jsonl", records)
    research_registry.to_csv(evidence / "FMDL4A_RESEARCH_PRIORITY_REGISTRY.csv", index=False)
    core.write_json(evidence / "FMDL4A_SOURCE_RELEASE_REGISTRY.json", source_registry)
    core.write_json(evidence / "FMDL4A_LIMITATION_REGISTER.json", limitation_register)
    core.write_json(state_current / "FMDL4A_BINDING_STATE.json", binding_state)

    package_files = []
    for path in sorted(p for p in adapter_root.rglob("*") if p.is_file()):
        relative = path.relative_to(adapter_root).as_posix()
        domain = relative.split("/", 1)[0]
        package_files.append({
            "package_path": f"{cfg['adapter']['overlay_namespace']}/{relative}",
            "source_path": str(path.relative_to(ROOT)),
            "sha256": core.sha256_file(path),
            "bytes": path.stat().st_size,
            "package_domain": domain,
        })
    overlay_manifest = {
        "manifest_version": "1.0.0",
        "candidate_release_sequence": cfg["adapter"]["candidate_release_sequence"],
        "candidate_status": "RELEASE5_ADAPTER_OVERLAY_CANDIDATE",
        "base_package": {
            "name": cfg["external_canonical_base"]["package_name"],
            "release_sequence": cfg["external_canonical_base"]["release_sequence"],
            "run_id": cfg["external_canonical_base"]["run_id"],
            "sha256": cfg["external_canonical_base"]["package_sha256"],
            "status": cfg["external_canonical_base"]["status"],
        },
        "overlay_mode": cfg["adapter"]["mode"],
        "overlay_namespace": cfg["adapter"]["overlay_namespace"],
        "files": package_files,
        "base_state_mutation_count": 0,
        "existing_path_replacement_count": 0,
        "aggregate_sha256": core.stable_hash(package_files),
        "authority": "READ_ONLY_ADDITIVE_PACKAGE_ADAPTER",
        "trade_authority": "NONE",
    }
    core.write_json(candidate / "FMDL4A_RELEASE5_OVERLAY_MANIFEST.json", overlay_manifest)
    deterministic_zip(adapter_root, candidate / "FMDL4A_RELEASE5_ADAPTER_OVERLAY.zip")

    envelope_semantic_hash = core.semantic_frame_hash(envelope_frame)
    registry_semantic_hash = core.semantic_frame_hash(research_registry, sort_by=("overall_rank", "symbol"))
    package_semantic_hash = core.stable_hash({
        "base_sha256": cfg["external_canonical_base"]["package_sha256"],
        "overlay_aggregate_sha256": overlay_manifest["aggregate_sha256"],
        "candidate_release_sequence": cfg["adapter"]["candidate_release_sequence"],
    })
    release_id = f"FMDL4A_{str(unified['market_as_of_date'].iloc[0]).replace('-', '')}_{package_semantic_hash[:12]}"

    hard_failures = list(gate_errors)
    metrics = {
        "universe_symbol_count": len(unified),
        "financial_symbol_count": len(financial),
        "longlist_symbol_count": len(longlist),
        "duplicate_unified_symbol_count": duplicate_unified,
        "duplicate_financial_symbol_count": duplicate_financial,
        "duplicate_longlist_symbol_count": duplicate_longlist,
        "missing_financial_symbol_count": len(missing_financial),
        "unknown_longlist_symbol_count": len(unknown_longlist),
        "envelope_shape_error_count": envelope_shape_errors,
        "trade_authority_error_count": int((envelope_frame["trade_authority"] != "NONE").sum()) + int((research_registry["trade_authority"] != "NONE").sum()),
        "decision_grade_count": int((envelope_frame["quality_state"] == "DECISION_GRADE").sum()),
        "research_usable_with_limitations_count": int((envelope_frame["quality_state"] == "RESEARCH_USABLE_WITH_LIMITATIONS").sum()),
        "review_only_count": int((envelope_frame["quality_state"] == "REVIEW_ONLY").sum()),
        "base_state_mutation_count": 0,
        "existing_path_replacement_count": 0,
        "overlay_file_count": len(package_files),
        "elapsed_seconds": round((datetime.now(TZ) - started).total_seconds(), 4),
    }
    acceptance = cfg["acceptance"]
    threshold_checks = {
        "UNIVERSE_SYMBOL_COUNT": metrics["universe_symbol_count"] == cfg["evidence_envelope"]["required_universe_symbol_count"],
        "LONGLIST_SYMBOL_COUNT": metrics["longlist_symbol_count"] == cfg["evidence_envelope"]["required_longlist_symbol_count"],
        "DUPLICATE_SYMBOLS": sum(metrics[key] for key in ["duplicate_unified_symbol_count", "duplicate_financial_symbol_count", "duplicate_longlist_symbol_count"]) == 0,
        "MISSING_ENVELOPE_SYMBOLS": metrics["missing_financial_symbol_count"] <= acceptance["maximum_missing_envelope_symbol_count"],
        "UNKNOWN_LONGLIST_SYMBOLS": metrics["unknown_longlist_symbol_count"] <= acceptance["maximum_unknown_longlist_symbol_count"],
        "ENVELOPE_SHAPE": metrics["envelope_shape_error_count"] == 0,
        "TRADE_AUTHORITY": metrics["trade_authority_error_count"] <= acceptance["maximum_trade_authority_error_count"],
        "BASE_STATE_MUTATION": metrics["base_state_mutation_count"] <= acceptance["maximum_base_state_mutation_count"],
        "EXISTING_PATH_REPLACEMENT": metrics["existing_path_replacement_count"] <= acceptance["maximum_existing_path_replacement_count"],
    }
    hard_failures.extend([check for check, passed in threshold_checks.items() if not passed])
    status = cfg["exit_status"] if not hard_failures else "FMDL4A_RESEARCH_HANDOFF_AND_CANONICAL_ADAPTER_REJECTED"
    decision = {
        "decision_version": "1.0.0",
        "release_id": release_id,
        "generated_at": started.isoformat(timespec="seconds"),
        "program_id": "FMDL-4A",
        "status": status,
        "hard_failures": hard_failures,
        "checks": [{"check_id": key, "status": "PASS" if value else "FAIL"} for key, value in threshold_checks.items()],
        "metrics": metrics,
        "source_release_ids": releases,
        "external_canonical_base": cfg["external_canonical_base"],
        "semantic_hashes": {
            "evidence_envelope": envelope_semantic_hash,
            "research_priority_registry": registry_semantic_hash,
            "release5_adapter_composition": package_semantic_hash,
            "overlay_zip": core.sha256_file(candidate / "FMDL4A_RELEASE5_ADAPTER_OVERLAY.zip"),
        },
        "controlled_limitations": cfg["controlled_limitations"],
        "authority": cfg["authority"],
        "trade_authority": "NONE",
        "next_gate": cfg["next_gate"],
    }
    core.write_json(candidate / "FMDL4A_DECISION.json", decision)
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    if hard_failures:
        raise SystemExit("FMDL-4A candidate rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
