from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from scripts import fmdl3cb_core as core

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("Asia/Shanghai")
CONFIG = ROOT / "config/fmdl3cb_engine.json"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def recursive_manifest(root: Path, release_id: str) -> dict:
    files = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "FMDL3CB_MANIFEST.json":
            files.append({"path": str(path.relative_to(root)), "sha256": sha256(path), "bytes": path.stat().st_size})
    return {"manifest_version": "1.0.0", "release_id": release_id, "files": files, "authority": "DATA_AND_RESEARCH_EVIDENCE_ONLY", "trade_authority": "NONE"}


def main() -> int:
    cfg = load_json(CONFIG)
    statement_pointer = load_json(ROOT / cfg["entry_gates"]["statement_current_pointer"])
    contract_pointer = load_json(ROOT / cfg["entry_gates"]["factor_contract_pointer"])
    if statement_pointer.get("status") != cfg["entry_gates"]["statement_current_status"]:
        raise SystemExit("FMDL-3B-4 entry gate not satisfied")
    if contract_pointer.get("status") != cfg["entry_gates"]["factor_contract_status"]:
        raise SystemExit("FMDL-3C-A entry gate not satisfied")

    dictionary = pd.read_csv(ROOT / cfg["inputs"]["factor_dictionary"], encoding="utf-8-sig")
    universe = pd.read_csv(ROOT / cfg["inputs"]["universe"], encoding="utf-8-sig", usecols=["symbol"])
    universe_symbols = sorted(set(universe["symbol"].dropna().astype(str)))
    catalog = pd.read_csv(ROOT / cfg["inputs"]["statement_catalog"], encoding="utf-8-sig")
    normalized_paths = [ROOT / p for p in catalog.loc[catalog["dataset_role"].eq("statement_normalized"), "path"].astype(str)]
    period_paths = [ROOT / p for p in catalog.loc[catalog["dataset_role"].eq("comparability_period_status"), "path"].astype(str)]
    bridge_paths = [ROOT / p for p in catalog.loc[catalog["dataset_role"].eq("comparability_bridge"), "path"].astype(str)]
    if len(normalized_paths) != int(cfg["engine"]["expected_statement_shards"]):
        raise SystemExit(f"expected 32 normalized shards, got {len(normalized_paths)}")
    if len(period_paths) != 1 or len(bridge_paths) != 1:
        raise SystemExit("expected one comparability period-status and one bridge asset")
    period_status = pd.read_parquet(period_paths[0])
    period_status["symbol"] = period_status["symbol"].astype(str)
    period_groups = {symbol: frame for symbol, frame in period_status.groupby("symbol", sort=False)}
    comparison_bridge = pd.read_parquet(bridge_paths[0])
    if len(comparison_bridge):
        comparison_bridge["symbol"] = comparison_bridge["symbol"].astype(str)
        bridge_groups = {symbol: frame for symbol, frame in comparison_bridge.groupby("symbol", sort=False)}
    else:
        bridge_groups = {}
    factor_records = dictionary.to_dict("records")

    candidate = ROOT / cfg["publication"]["candidate_root"]
    if candidate.exists():
        shutil.rmtree(candidate)
    history_root = candidate / "factor_history"
    derived_root = candidate / "derived_inputs"
    history_root.mkdir(parents=True)
    derived_root.mkdir(parents=True)

    release_id = f"FMDL3CB_{datetime.now(TZ).strftime('%Y%m%dT%H%M%S%z')}"
    profile_rows: list[dict] = []
    latest_parts: list[pd.DataFrame] = []
    derived_count = 0
    period_count = 0
    history_count = 0
    valid_history_count = 0

    for shard_id, path in enumerate(normalized_paths):
        normalized = pd.read_parquet(path)
        shard_history: list[pd.DataFrame] = []
        shard_derived: list[pd.DataFrame] = []
        if len(normalized):
            for symbol, symbol_facts in normalized.groupby("symbol", sort=False):
                symbol = str(symbol)
                profile = core.infer_sector_profile(symbol_facts)
                status = period_groups.get(symbol, period_status.iloc[0:0])
                symbol_bridge = bridge_groups.get(symbol, comparison_bridge.iloc[0:0])
                derived = core.build_period_inputs(
                    symbol_facts,
                    status,
                    cfg["engine"]["flow_inputs"],
                    cfg["engine"]["balance_inputs"],
                    symbol_bridge,
                )
                profile_rows.append({
                    "symbol": symbol,
                    "sector_profile": profile,
                    "normalized_fact_count": len(symbol_facts),
                    "factor_period_count": len(derived),
                    "profile_basis": "STATEMENT_FIELD_SIGNATURE",
                    "authority": cfg["authority"],
                    "trade_authority": "NONE",
                })
                if len(derived):
                    derived.insert(3, "sector_profile", profile)
                    derived.insert(4, "factor_version", cfg["engine"]["factor_version"])
                    derived["authority"] = cfg["authority"]
                    derived["trade_authority"] = "NONE"
                    shard_derived.append(derived)
                    period_count += len(derived)
                    for _, period_row in derived.iterrows():
                        shard_history.append(core.evaluate_factors_for_period(period_row, factor_records, profile, cfg["engine"]["factor_version"]))
        derived_frame = pd.concat(shard_derived, ignore_index=True) if shard_derived else pd.DataFrame()
        history_frame = pd.concat(shard_history, ignore_index=True) if shard_history else pd.DataFrame()
        derived_frame.to_parquet(derived_root / f"shard-{shard_id:02d}.parquet", index=False, compression="zstd")
        history_frame.to_parquet(history_root / f"shard-{shard_id:02d}.parquet", index=False, compression="zstd")
        derived_count += len(derived_frame)
        history_count += len(history_frame)
        if len(history_frame):
            valid_history_count += int(history_frame["quality_state"].isin(["VALID", "VALID_WITH_WARNING"]).sum())
            shard_latest = history_frame.sort_values(["symbol", "factor_id", "period_end", "as_of_timestamp"], na_position="last").groupby(["symbol", "factor_id"], as_index=False).tail(1)
            latest_parts.append(shard_latest)

    profiles = pd.DataFrame(profile_rows).drop_duplicates("symbol") if profile_rows else pd.DataFrame(columns=["symbol", "sector_profile", "normalized_fact_count", "factor_period_count", "profile_basis", "authority", "trade_authority"])
    missing_symbols = sorted(set(universe_symbols) - set(profiles["symbol"].astype(str)))
    if missing_symbols:
        missing_profiles = pd.DataFrame({
            "symbol": missing_symbols,
            "sector_profile": "UNRESOLVED",
            "normalized_fact_count": 0,
            "factor_period_count": 0,
            "profile_basis": "NO_DECISION_GRADE_STATEMENT_FACTS",
            "authority": cfg["authority"],
            "trade_authority": "NONE",
        })
        profiles = pd.concat([profiles, missing_profiles], ignore_index=True)
    profiles = profiles.sort_values("symbol")
    profiles.to_csv(candidate / "FMDL3CB_SECTOR_PROFILES.csv", index=False, encoding="utf-8-sig")

    latest = pd.concat(latest_parts, ignore_index=True) if latest_parts else pd.DataFrame()
    expected_pairs = pd.MultiIndex.from_product([universe_symbols, dictionary["factor_id"].astype(str).tolist()], names=["symbol", "factor_id"]).to_frame(index=False)
    latest = expected_pairs.merge(latest, on=["symbol", "factor_id"], how="left", validate="one_to_one", suffixes=("", "_history"))
    factor_meta = dictionary.set_index("factor_id")
    profile_index = profiles.set_index("symbol")
    for idx, row in latest[latest["factor_name"].isna()].iterrows():
        meta = factor_meta.loc[row["factor_id"]]
        latest.at[idx, "factor_name"] = meta["factor_name"]
        latest.at[idx, "family_id"] = meta["family_id"]
        latest.at[idx, "factor_version"] = cfg["engine"]["factor_version"]
        latest.at[idx, "output_unit"] = meta["output_unit"]
        latest.at[idx, "economic_direction"] = meta["economic_direction"]
        latest.at[idx, "sector_profile"] = profile_index.loc[row["symbol"], "sector_profile"]
        latest.at[idx, "quality_state"] = "QUARANTINED_INPUT"
        latest.at[idx, "rank_eligibility"] = "INELIGIBLE"
        latest.at[idx, "build_state"] = meta["build_state"]
        latest.at[idx, "warning_codes"] = "NO_STATEMENT_PERIOD_AVAILABLE"
        latest.at[idx, "required_inputs"] = meta["required_inputs"]
        latest.at[idx, "input_fact_ids_json"] = "[]"
        latest.at[idx, "lineage_id"] = core.stable_hash({"symbol": row["symbol"], "factor_id": row["factor_id"], "state": "NO_STATEMENT_PERIOD_AVAILABLE"})
        latest.at[idx, "factor_row_id"] = core.stable_hash({"symbol": row["symbol"], "factor_id": row["factor_id"], "current": "NO_HISTORY"})
        latest.at[idx, "authority"] = cfg["authority"]
        latest.at[idx, "trade_authority"] = "NONE"
    latest.to_parquet(candidate / "FMDL3CB_LATEST_FACTOR_CURRENT.parquet", index=False, compression="zstd")

    quality_summary = latest.groupby(["build_state", "family_id", "quality_state", "rank_eligibility"], dropna=False).size().reset_index(name="row_count")
    quality_summary.to_csv(candidate / "FMDL3CB_QUALITY_SUMMARY.csv", index=False, encoding="utf-8-sig")
    coverage_summary = latest.groupby(["factor_id", "quality_state"], dropna=False).size().reset_index(name="symbol_count")
    coverage_summary.to_csv(candidate / "FMDL3CB_FACTOR_COVERAGE.csv", index=False, encoding="utf-8-sig")

    factor_count = len(dictionary)
    current_valid_count = int(latest["quality_state"].isin(["VALID", "VALID_WITH_WARNING"]).sum())
    tests = {
        "ENTRY_STATEMENT_CURRENT_ACCEPTED": statement_pointer.get("status") == cfg["entry_gates"]["statement_current_status"],
        "ENTRY_FACTOR_CONTRACT_ACCEPTED": contract_pointer.get("status") == cfg["entry_gates"]["factor_contract_status"],
        "EXACT_32_INPUT_SHARDS": len(normalized_paths) == int(cfg["engine"]["expected_statement_shards"]),
        "EXACT_FACTOR_COUNT": factor_count == int(cfg["engine"]["expected_factor_count"]),
        "EXACT_MVP_REQUIRED_FACTOR_COUNT": int(dictionary["build_state"].eq("MVP_REQUIRED").sum()) == int(cfg["engine"]["expected_mvp_required_factor_count"]),
        "ALL_UNIVERSE_SYMBOLS_PROFILED": set(profiles["symbol"].astype(str)) == set(universe_symbols),
        "ALL_PROFILES_CONTROLLED": set(profiles["sector_profile"]).issubset(set(cfg["engine"]["allowed_sector_profiles"])),
        "HISTORY_COMPLETE_BY_PERIOD_FACTOR": history_count == period_count * factor_count,
        "LATEST_CURRENT_COMPLETE": len(latest) == len(universe_symbols) * factor_count,
        "LATEST_CURRENT_UNIQUE": not latest.duplicated(["symbol", "factor_id"]).any(),
        "QUALITY_STATES_CONTROLLED": set(latest["quality_state"]).issubset(set(cfg["engine"]["allowed_quality_states"])),
        "VALID_ROWS_HAVE_VALUES": latest.loc[latest["quality_state"].isin(["VALID", "VALID_WITH_WARNING"]), "factor_value"].notna().all(),
        "INVALID_ROWS_HAVE_NO_VALUES": latest.loc[~latest["quality_state"].isin(["VALID", "VALID_WITH_WARNING"]), "factor_value"].isna().all(),
        "ZERO_TRADE_AUTHORITY": set(latest["trade_authority"].dropna()).issubset({"NONE"}) and set(profiles["trade_authority"].dropna()).issubset({"NONE"}),
    }
    failures = [name for name, passed in tests.items() if not bool(passed)]
    metrics = {
        "statement_current_release_id": statement_pointer["release_id"],
        "factor_contract_release_id": contract_pointer["release_id"],
        "universe_symbol_count": len(universe_symbols),
        "sector_profile_count": len(profiles),
        "factor_count": factor_count,
        "mvp_required_factor_count": int(dictionary["build_state"].eq("MVP_REQUIRED").sum()),
        "diagnostic_factor_count": int(dictionary["build_state"].eq("MVP_DIAGNOSTIC").sum()),
        "factor_period_count": period_count,
        "derived_input_row_count": derived_count,
        "factor_history_row_count": history_count,
        "valid_or_warning_history_row_count": valid_history_count,
        "latest_factor_current_row_count": len(latest),
        "latest_valid_or_warning_row_count": current_valid_count,
        "latest_ineligible_row_count": int((latest["rank_eligibility"] == "INELIGIBLE").sum()),
        "general_non_financial_symbol_count": int(profiles["sector_profile"].eq("GENERAL_NON_FINANCIAL").sum()),
        "bank_symbol_count": int(profiles["sector_profile"].eq("BANK").sum()),
        "insurance_symbol_count": int(profiles["sector_profile"].eq("INSURANCE").sum()),
        "securities_symbol_count": int(profiles["sector_profile"].eq("SECURITIES_AND_BROKERAGE").sum()),
        "unresolved_sector_symbol_count": int(profiles["sector_profile"].eq("UNRESOLVED").sum()),
    }
    decision = {
        "decision_version": "1.0.0",
        "release_id": release_id,
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "program_id": "FMDL-3C-B",
        "status": cfg["exit_status"] if not failures else "FMDL3CB_REMEDIATION_REQUIRED",
        "hard_failures": failures,
        "checks": [{"check_id": k, "status": "PASS" if bool(v) else "FAIL"} for k, v in tests.items()],
        "metrics": metrics,
        "controlled_limitations": [
            "SECTOR_PROFILES_ARE_INFERRED_FROM_ACCEPTED_STATEMENT_FIELD_SIGNATURES_PENDING_INDUSTRY_MASTER_HARDENING",
            "RESTATED_PERIOD_FACTORS_ARE_AVAILABLE_ONLY_FROM_THE_LATEST_AUTHORITATIVE_REVISION_TIMESTAMP",
            "MISSING_DEBT_CASH_GOODWILL_OR_OTHER_COMPONENTS_ARE_NEVER_ZERO_FILLED",
            "RAW_FACTOR_VALUES_ARE_NOT_WINSORIZED_OR_COMBINED_INTO_A_SCORE",
        ],
        "authority": cfg["authority"],
        "trade_authority": "NONE",
        "next_gate": cfg["next_gate"],
    }
    write_json(candidate / "FMDL3CB_DECISION.json", decision)
    write_json(candidate / "FMDL3CB_STATEMENT_CURRENT_POINTER.json", statement_pointer)
    write_json(candidate / "FMDL3CB_FACTOR_CONTRACT_POINTER.json", contract_pointer)

    manifest = recursive_manifest(candidate, release_id)
    write_json(candidate / "FMDL3CB_MANIFEST.json", manifest)
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
