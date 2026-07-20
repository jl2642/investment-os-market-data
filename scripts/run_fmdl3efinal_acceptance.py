from __future__ import annotations

import json
import shutil
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from scripts import fmdl3efinal_core as core
from scripts import fmdl3ede_core as de_core

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fmdl3efinal_operational_closure.json"
TZ = ZoneInfo("Asia/Shanghai")


def main() -> int:
    cfg = core.read_json(CONFIG)
    candidate = ROOT / cfg["publication"]["candidate_root"]
    if candidate.exists():
        shutil.rmtree(candidate)
    candidate.mkdir(parents=True)
    started = time.monotonic()
    release_id = f"FMDL3E_FINAL_{datetime.now(TZ).strftime('%Y%m%dT%H%M%S%z')}"
    generated_at = datetime.now(TZ).isoformat(timespec="seconds")

    chain = {name: core.read_json(ROOT / path) for name, path in cfg["entry_chain"].items()}
    propagated = pd.read_parquet(ROOT / cfg["inputs"]["propagated_unified_current"])
    rebuilt = pd.read_parquet(ROOT / cfg["inputs"]["full_rebuild_reference"])
    resilience = core.read_json(ROOT / cfg["inputs"]["resilience_report"])

    errors = core.chain_errors(chain, cfg)
    de_release = chain["fmdl3ede_release"]
    de_decision = chain["fmdl3ede_decision"]
    de_validation = chain["fmdl3ede_validation"]
    bc_release_id = core.release_id(chain["fmdl3ebc_release"])
    de_release_id = core.release_id(de_release)

    if de_decision.get("hard_failures") != []:
        errors.append("FMDL3EDE_DECISION_HARD_FAILURE")
    if de_validation.get("status") != "PASS" or de_validation.get("hard_failures") != []:
        errors.append("FMDL3EDE_VALIDATION_NOT_PASS")

    metrics = de_release.get("metrics", {})
    if int(metrics.get("propagated_symbol_count", -1)) != cfg["acceptance"]["required_universe_symbol_count"]:
        errors.append("DE_RELEASE_UNIVERSE_COUNT")
    if int(metrics.get("full_rebuild_mismatch_count", -1)) > cfg["acceptance"]["maximum_full_rebuild_mismatch_count"]:
        errors.append("DE_FULL_REBUILD_MISMATCH")
    if int(metrics.get("idempotence_mismatch_count", -1)) > cfg["acceptance"]["maximum_idempotence_mismatch_count"]:
        errors.append("DE_IDEMPOTENCE_MISMATCH")
    if int(metrics.get("source_hash_error_count", -1)) > cfg["acceptance"]["maximum_source_hash_error_count"]:
        errors.append("DE_SOURCE_HASH_ERROR")
    if int(metrics.get("failure_injection_rejected_count", -1)) != int(metrics.get("failure_injection_case_count", -2)):
        errors.append("DE_FAILURE_INJECTION_NOT_REJECTED")
    if not resilience.get("rollback_lkg_preserved"):
        errors.append("DE_LKG_NOT_PRESERVED")
    lkg_before = resilience.get("rollback_lkg_before", {})
    lkg_after = resilience.get("rollback_lkg_after_failure", {})
    if not all(lkg_before.get(k) for k in ("current_release_sha256", "last_success_sha256")):
        errors.append("DE_LKG_HASH_NULL")
    if lkg_before != lkg_after:
        errors.append("DE_LKG_HASH_CHANGED")

    universe_count = len(propagated)
    duplicate_count = int(propagated["symbol"].duplicated().sum()) if "symbol" in propagated else universe_count
    trade_error_count = core.trade_authority_errors(propagated)
    lineage_error_count = core.component_lineage_errors(
        propagated, bc_release_id=bc_release_id, de_release_id=de_release_id
    )
    if universe_count != cfg["acceptance"]["required_universe_symbol_count"]:
        errors.append("UNIFIED_UNIVERSE_COUNT")
    if duplicate_count > cfg["acceptance"]["maximum_duplicate_symbol_count"]:
        errors.append("UNIFIED_DUPLICATE_SYMBOL")
    if trade_error_count:
        errors.append("UNIFIED_TRADE_AUTHORITY")
    if lineage_error_count:
        errors.append("UNIFIED_COMPONENT_LINEAGE")

    audit = de_core.comparison_audit(propagated, rebuilt)
    full_rebuild_mismatch_count = int(audit["mismatch_count"].sum())
    propagated_hash = core.semantic_frame_hash(propagated)
    rebuilt_hash = core.semantic_frame_hash(rebuilt)
    expected_hashes = de_release.get("semantic_hashes", {})
    if full_rebuild_mismatch_count:
        errors.append("INDEPENDENT_FULL_REBUILD_MISMATCH")
    if propagated_hash != rebuilt_hash:
        errors.append("INDEPENDENT_FULL_REBUILD_HASH_MISMATCH")
    if propagated_hash != expected_hashes.get("propagated_unified_current"):
        errors.append("DE_PROPAGATED_SEMANTIC_HASH")
    if rebuilt_hash != expected_hashes.get("full_rebuild_reference"):
        errors.append("DE_REBUILD_SEMANTIC_HASH")

    missing_entrypoints = [
        path for path in cfg["operational_entrypoints"].values() if not (ROOT / path).exists()
    ]
    if missing_entrypoints:
        errors.extend(f"MISSING_ENTRYPOINT:{path}" for path in missing_entrypoints)

    source_paths = list(cfg["entry_chain"].values()) + list(cfg["inputs"].values()) + list(cfg["operational_entrypoints"].values())
    source_hashes = {
        path: core.sha256_file(ROOT / path)
        for path in source_paths
        if (ROOT / path).exists() and (ROOT / path).is_file()
    }

    shutil.copy2(ROOT / cfg["inputs"]["propagated_unified_current"], candidate / "FMDL3EFINAL_UNIFIED_CURRENT.parquet")
    audit.to_csv(candidate / "FMDL3EFINAL_FULL_REBUILD_AUDIT.csv", index=False)

    limitations = [
        {
            "limitation_id": "POST_BASELINE_LIVE_MARKET_ADVANCE_PENDING",
            "status": "OPEN" if not bool(de_release.get("post_frozen_baseline_advance_observed")) else "CLOSED",
            "description": "The accepted operating proof uses a real completed-session replay until a completed session later than Baseline-0 is observed."
        },
        {
            "limitation_id": "FINANCIAL_PRE_REVISION_NUMERIC_HISTORY_NOT_RETAINED",
            "status": "OPEN",
            "description": "Selected historical financial correction cases prove document-version PIT lineage but do not fabricate unavailable pre-revision structured values."
        },
        {
            "limitation_id": "NO_ALPHA_OR_TRADE_AUTHORITY",
            "status": "PERMANENT_BOUNDARY",
            "description": "FMDL-3E is a data and research-evidence operating layer, not an investment recommendation or execution authority."
        }
    ]
    core.write_json(candidate / "FMDL3EFINAL_LIMITATION_REGISTER.json", {
        "register_version": "1.0.0",
        "release_id": release_id,
        "limitations": limitations,
        "authority": cfg["authority"],
        "trade_authority": "NONE",
    })

    state = {
        "state_version": "1.0.0",
        "release_id": release_id,
        "generated_at": generated_at,
        "program_id": cfg["program_id"],
        "status": cfg["exit_status"] if not errors else "FMDL3E_FINAL_REJECTED",
        "canonical_chain": {
            "FMDL-3D-FINAL": core.release_id(chain["fmdl3d_release"]),
            "FMDL-3E-A": core.release_id(chain["fmdl3ea_release"]),
            "FMDL-3E-BC": bc_release_id,
            "FMDL-3E-DE": de_release_id,
        },
        "baseline_id": de_release.get("baseline_id"),
        "market_watermark": {
            "baseline_date": chain["fmdl3ea_release"].get("market_as_of_date"),
            "target_date": metrics.get("target_market_as_of_date"),
            "acceptance_mode": de_release.get("market_acceptance_mode"),
            "post_frozen_baseline_advance_observed": de_release.get("post_frozen_baseline_advance_observed"),
        },
        "financial_watermark": {
            "event_count": metrics.get("financial_event_count"),
            "fact_delta_count": metrics.get("financial_fact_delta_count"),
            "version_count": metrics.get("financial_version_count"),
        },
        "operational_policy": {
            "same_input": "NO_OP_OR_SEMANTICALLY_IDEMPOTENT",
            "new_completed_market_session": "RUN_FMDL3E_BC_THEN_DE_THEN_FINAL",
            "failure": "REJECT_CANDIDATE_AND_PRESERVE_CURRENT_AND_LAST_SUCCESS",
            "manual_recovery": "WORKFLOW_DISPATCH_CAN_FORCE_OPERATIONAL_REFRESH",
            "scheduler": "WEEKDAYS_19_45_ASIA_SHANGHAI",
        },
        "entrypoints": cfg["operational_entrypoints"],
        "unified_current_semantic_hash": propagated_hash,
        "source_hashes": source_hashes,
        "controlled_limitations": limitations,
        "authority": cfg["authority"],
        "trade_authority": "NONE",
        "next_gate": cfg["next_gate"],
    }
    core.write_json(candidate / "FMDL3EFINAL_OPERATIONAL_STATE.json", state)

    measured = {
        "component_release_count": 4,
        "universe_symbol_count": universe_count,
        "duplicate_symbol_count": duplicate_count,
        "trade_authority_error_count": trade_error_count,
        "component_lineage_error_count": lineage_error_count,
        "full_rebuild_mismatch_count": full_rebuild_mismatch_count,
        "source_hash_count": len(source_hashes),
        "missing_entrypoint_count": len(missing_entrypoints),
        "open_controlled_limitation_count": sum(item["status"] == "OPEN" for item in limitations),
        "elapsed_seconds": round(time.monotonic() - started, 4),
    }
    checks = [
        {"check_id": "CANONICAL_RELEASE_CHAIN", "status": "PASS" if not core.chain_errors(chain, cfg) else "FAIL"},
        {"check_id": "DE_DECISION_AND_VALIDATION", "status": "PASS" if de_decision.get("hard_failures") == [] and de_validation.get("status") == "PASS" else "FAIL"},
        {"check_id": "UNIFIED_CURRENT", "status": "PASS" if universe_count == cfg["acceptance"]["required_universe_symbol_count"] and duplicate_count == 0 else "FAIL"},
        {"check_id": "FULL_REBUILD_EQUAL", "status": "PASS" if full_rebuild_mismatch_count == 0 and propagated_hash == rebuilt_hash else "FAIL"},
        {"check_id": "IDEMPOTENCE_AND_FAILURE_RECOVERY", "status": "PASS" if metrics.get("idempotence_mismatch_count") == 0 and resilience.get("rollback_lkg_preserved") and lkg_before == lkg_after else "FAIL"},
        {"check_id": "OPERATIONAL_ENTRYPOINTS", "status": "PASS" if not missing_entrypoints else "FAIL"},
        {"check_id": "ZERO_TRADE_AUTHORITY", "status": "PASS" if trade_error_count == 0 else "FAIL"},
    ]
    decision = {
        "decision_version": "1.0.0",
        "release_id": release_id,
        "generated_at": generated_at,
        "program_id": cfg["program_id"],
        "status": cfg["exit_status"] if not errors else "FMDL3E_FINAL_REJECTED",
        "hard_failures": sorted(set(errors)),
        "checks": checks,
        "metrics": measured,
        "canonical_chain": state["canonical_chain"],
        "baseline_id": state["baseline_id"],
        "market_watermark": state["market_watermark"],
        "semantic_hashes": {
            "unified_current": propagated_hash,
            "full_rebuild_reference": rebuilt_hash,
            "operational_state": core.stable_hash(state),
        },
        "controlled_limitations": limitations,
        "authority": cfg["authority"],
        "trade_authority": "NONE",
        "next_gate": cfg["next_gate"],
    }
    core.write_json(candidate / "FMDL3EFINAL_DECISION.json", decision)
    manifest = core.manifest_for_directory(candidate, excluded={"FMDL3EFINAL_MANIFEST.json", "FMDL3EFINAL_VALIDATION.json"})
    manifest["release_id"] = release_id
    core.write_json(candidate / "FMDL3EFINAL_MANIFEST.json", manifest)
    if errors:
        print(json.dumps(decision, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
