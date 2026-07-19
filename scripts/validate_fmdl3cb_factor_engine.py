from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fmdl3cb_engine.json"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    cfg = load_json(CONFIG)
    root = ROOT / cfg["publication"]["candidate_root"]
    decision = load_json(root / "FMDL3CB_DECISION.json")
    manifest = load_json(root / "FMDL3CB_MANIFEST.json")
    dictionary = pd.read_csv(ROOT / cfg["inputs"]["factor_dictionary"], encoding="utf-8-sig")
    universe = pd.read_csv(ROOT / cfg["inputs"]["universe"], encoding="utf-8-sig", usecols=["symbol"])
    universe_symbols = sorted(set(universe["symbol"].dropna().astype(str)))
    profiles = pd.read_csv(root / "FMDL3CB_SECTOR_PROFILES.csv", encoding="utf-8-sig")
    latest = pd.read_parquet(root / "FMDL3CB_LATEST_FACTOR_CURRENT.parquet")
    history_paths = sorted((root / "factor_history").glob("shard-*.parquet"))
    derived_paths = sorted((root / "derived_inputs").glob("shard-*.parquet"))

    hash_errors = []
    for entry in manifest["files"]:
        path = root / entry["path"]
        if not path.exists() or sha256(path) != entry["sha256"] or path.stat().st_size != int(entry["bytes"]):
            hash_errors.append(entry["path"])

    history_count = 0
    valid_value_errors = 0
    invalid_value_errors = 0
    duplicate_history_keys = 0
    history_factor_ids: set[str] = set()
    history_trade_authority: set[str] = set()
    allowed_states = set(cfg["engine"]["allowed_quality_states"])
    uncontrolled_states: set[str] = set()
    for path in history_paths:
        frame = pd.read_parquet(path)
        history_count += len(frame)
        if len(frame):
            duplicate_history_keys += int(frame.duplicated(["symbol", "factor_id", "period_end", "factor_version"]).sum())
            valid = frame["quality_state"].isin(["VALID", "VALID_WITH_WARNING"])
            valid_value_errors += int(frame.loc[valid, "factor_value"].isna().sum())
            invalid_value_errors += int(frame.loc[~valid, "factor_value"].notna().sum())
            history_factor_ids.update(frame["factor_id"].dropna().astype(str))
            history_trade_authority.update(frame["trade_authority"].dropna().astype(str))
            uncontrolled_states.update(set(frame["quality_state"].dropna().astype(str)) - allowed_states)

    derived_count = sum(len(pd.read_parquet(path, columns=["symbol"])) for path in derived_paths)
    latest_pairs = set(map(tuple, latest[["symbol", "factor_id"]].astype(str).itertuples(index=False, name=None)))
    expected_pairs = {(symbol, factor) for symbol in universe_symbols for factor in dictionary["factor_id"].astype(str)}
    valid_latest = latest["quality_state"].isin(["VALID", "VALID_WITH_WARNING"])
    finite_latest = pd.to_numeric(latest.loc[valid_latest, "factor_value"], errors="coerce")

    checks = {
        "DECISION_ACCEPTED": decision.get("status") == cfg["exit_status"],
        "DECISION_HARD_FAILURES_EMPTY": decision.get("hard_failures") == [],
        "MANIFEST_FILES_PRESENT": all((root / x["path"]).exists() for x in manifest["files"]),
        "MANIFEST_HASHES_MATCH": not hash_errors,
        "EXACT_32_HISTORY_SHARDS": len(history_paths) == int(cfg["engine"]["expected_statement_shards"]),
        "EXACT_32_DERIVED_INPUT_SHARDS": len(derived_paths) == int(cfg["engine"]["expected_statement_shards"]),
        "LATEST_CURRENT_EXACT_UNIVERSE_FACTOR_CARTESIAN": latest_pairs == expected_pairs,
        "LATEST_CURRENT_KEYS_UNIQUE": not latest.duplicated(["symbol", "factor_id"]).any(),
        "PROFILES_EXACT_UNIVERSE": set(profiles["symbol"].astype(str)) == set(universe_symbols) and not profiles["symbol"].duplicated().any(),
        "PROFILES_CONTROLLED": set(profiles["sector_profile"]).issubset(set(cfg["engine"]["allowed_sector_profiles"])),
        "HISTORY_FACTOR_IDS_EXACT": history_factor_ids == set(dictionary["factor_id"].astype(str)),
        "HISTORY_KEYS_UNIQUE_WITHIN_SHARDS": duplicate_history_keys == 0,
        "QUALITY_STATES_CONTROLLED": not uncontrolled_states and set(latest["quality_state"]).issubset(allowed_states),
        "VALID_HISTORY_ROWS_HAVE_VALUES": valid_value_errors == 0,
        "INVALID_HISTORY_ROWS_HAVE_NO_VALUES": invalid_value_errors == 0,
        "VALID_LATEST_VALUES_FINITE": finite_latest.notna().all() and np.isfinite(finite_latest.astype(float)).all(),
        "INVALID_LATEST_ROWS_HAVE_NO_VALUES": latest.loc[~valid_latest, "factor_value"].isna().all(),
        "RANK_ELIGIBILITY_FAILS_CLOSED": set(latest.loc[~valid_latest, "rank_eligibility"].dropna()) <= {"INELIGIBLE"},
        "LINEAGE_PRESENT_FOR_VALID_ROWS": latest.loc[valid_latest, "lineage_id"].notna().all() and latest.loc[valid_latest, "input_fact_ids_json"].notna().all(),
        "METRICS_REPLAY": int(decision["metrics"]["factor_history_row_count"]) == history_count and int(decision["metrics"]["derived_input_row_count"]) == derived_count and int(decision["metrics"]["latest_factor_current_row_count"]) == len(latest),
        "ZERO_TRADE_AUTHORITY": history_trade_authority.issubset({"NONE"}) and set(latest["trade_authority"].dropna()).issubset({"NONE"}) and set(profiles["trade_authority"].dropna()).issubset({"NONE"}),
        "NO_SCORE_OR_SIGNAL_COLUMNS": not ({"score", "composite_score", "investment_signal", "trade_signal", "target_weight"} & set(latest.columns)),
        "NEXT_GATE_FMDL3C_C": decision.get("next_gate") == cfg["next_gate"],
    }
    failures = [name for name, passed in checks.items() if not bool(passed)]
    validation = {
        "validation_version": "1.0.0",
        "release_id": decision["release_id"],
        "status": "PASS" if not failures else "FAIL",
        "hard_failures": failures,
        "checks": [{"check_id": k, "status": "PASS" if bool(v) else "FAIL"} for k, v in checks.items()],
        "metrics": {
            **decision["metrics"],
            "manifest_hash_error_count": len(hash_errors),
            "duplicate_history_key_count": duplicate_history_keys,
            "valid_history_value_error_count": valid_value_errors,
            "invalid_history_value_error_count": invalid_value_errors,
            "uncontrolled_quality_state_count": len(uncontrolled_states),
        },
        "manifest_hash_errors": hash_errors,
        "uncontrolled_quality_states": sorted(uncontrolled_states),
        "authority": cfg["authority"],
        "trade_authority": "NONE",
        "next_gate": cfg["next_gate"],
    }
    write_json(root / "FMDL3CB_VALIDATION.json", validation)
    print(json.dumps(validation, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
