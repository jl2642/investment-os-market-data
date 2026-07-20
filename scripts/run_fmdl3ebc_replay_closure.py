from __future__ import annotations

import json
import shutil
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from scripts import fmdl3ebc_core as bc
from scripts import run_fmdl3ebc_incremental as live
from scripts import run_fmdl3b_pilot as pilot

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("Asia/Shanghai")
CONFIG = ROOT / "config/fmdl3ebc_incremental_refresh.json"


def previous_completed_session(target_date: str) -> str:
    target = pd.Timestamp(target_date).date()
    try:
        eligible = [value for value in pilot.fetch_calendar() if value < target]
        if eligible:
            return max(eligible).isoformat()
    except Exception:
        pass
    return (pd.Timestamp(target_date) - pd.offsets.BDay(1)).date().isoformat()


def build_real_market_replay(cfg: dict, baseline: dict):
    release = bc.read_json(ROOT / cfg["market"]["source_release"])
    if release.get("status") not in cfg["market"]["required_source_statuses"]:
        raise SystemExit(f"market source release not accepted: {release.get('status')}")
    target_date = str(release["as_of_date"])
    from_date = previous_completed_session(target_date)
    frozen = pd.read_parquet(ROOT / cfg["market"]["baseline_unified"])
    frozen["symbol"] = frozen["symbol"].astype(str)
    snap = pd.read_csv(ROOT / cfg["market"]["source_snapshot"], encoding="utf-8-sig")
    snap["symbol"] = snap["symbol"].astype(str)
    required = {"symbol", "close", "prev_close"}
    if not required.issubset(snap.columns):
        raise SystemExit(f"market replay requires columns: {sorted(required)}")
    columns = [column for column in ["symbol", "close", "prev_close", "data_status", "record_quality", "row_hash"] if column in snap.columns]
    delta = frozen[["symbol", "row_hash"]].rename(columns={"row_hash": "frozen_baseline_row_hash"}).merge(
        snap[columns].rename(columns={"prev_close": "baseline_close", "close": "refreshed_close", "row_hash": "source_market_row_hash"}),
        on="symbol",
        how="left",
    )
    delta["baseline_market_as_of_date"] = from_date
    delta["refreshed_market_as_of_date"] = target_date
    delta["frozen_baseline_market_as_of_date"] = str(baseline["market_as_of_date"])
    delta["baseline_close"] = pd.to_numeric(delta["baseline_close"], errors="coerce")
    delta["refreshed_close"] = pd.to_numeric(delta["refreshed_close"], errors="coerce")
    delta["close_delta"] = delta["refreshed_close"] - delta["baseline_close"]
    delta["close_pct_delta"] = delta["close_delta"] / delta["baseline_close"].replace(0, pd.NA)
    valid = delta["baseline_close"].gt(0) & delta["refreshed_close"].gt(0)
    delta["market_delta_state"] = "UPDATED"
    delta.loc[~valid, "market_delta_state"] = "SOURCE_ROW_MISSING_OR_NONPOSITIVE_PRICE"
    delta.loc[valid & delta["refreshed_close"].eq(delta["baseline_close"]), "market_delta_state"] = "UNCHANGED_CLOSE"
    delta["event_type"] = "MARKET_SESSION_ADVANCE"
    delta["affected"] = True
    delta["authority"] = cfg["authority"]
    delta["trade_authority"] = "NONE"
    source_ref = str(release.get("run_id"))
    delta["delta_row_hash"] = delta.apply(
        lambda row: bc.stable_hash({
            "symbol": row["symbol"],
            "from": from_date,
            "to": target_date,
            "old": row["baseline_close"],
            "new": row["refreshed_close"],
            "source": row.get("source_market_row_hash"),
        }),
        axis=1,
    )
    event_id = bc.stable_hash({"event_type": "MARKET_SESSION_ADVANCE", "from": from_date, "to": target_date, "source": source_ref, "mode": "REAL_COMPLETED_SESSION_REPLAY"})
    event = {
        "event_id": event_id,
        "event_type": "MARKET_SESSION_ADVANCE",
        "domain": "MARKET",
        "detected_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "effective_at": target_date,
        "symbol": None,
        "name": None,
        "period_end": None,
        "title": None,
        "affected_scope": "ALL_FROZEN_BASELINE_SYMBOLS_IN_REAL_COMPLETED_SESSION_REPLAY",
        "source_reference": source_ref,
        "pit_replay_required": True,
        "live_detected": False,
        "replay_kind": "REAL_COMPLETED_SESSION_REPLAY",
        "authority": cfg["authority"],
        "trade_authority": "NONE",
    }
    validation = {
        "acceptance_mode": "REAL_COMPLETED_SESSION_REPLAY",
        "frozen_baseline_date": str(baseline["market_as_of_date"]),
        "baseline_date": from_date,
        "target_date": target_date,
        "strictly_later": pd.Timestamp(target_date) > pd.Timestamp(from_date),
        "post_frozen_baseline_advance_observed": pd.Timestamp(target_date) > pd.Timestamp(str(baseline["market_as_of_date"])),
        "baseline_symbol_count": len(frozen),
        "source_symbol_count": snap["symbol"].nunique(),
        "matched_positive_close_count": int(valid.sum()),
        "symbol_coverage_ratio": float(valid.mean()),
        "duplicate_symbol_count": int(delta["symbol"].duplicated().sum()),
        "source_reference": source_ref,
    }
    return delta, event, validation


def main() -> int:
    cfg = bc.read_json(CONFIG)
    pointer, baseline, baseline_symbols, event_catalog = live.load_inputs(cfg)
    candidate = ROOT / cfg["publication"]["candidate_root"]
    if candidate.exists():
        shutil.rmtree(candidate)
    candidate.mkdir(parents=True)
    started = time.monotonic()
    generated_at = datetime.now(TZ).isoformat(timespec="seconds")
    release_id = f"FMDL3EBC_{datetime.now(TZ).strftime('%Y%m%dT%H%M%S%z')}"
    source_errors = live.baseline_hash_errors(baseline)
    market, market_event, market_validation = build_real_market_replay(cfg, baseline)
    target_date = market_validation["target_date"]
    financial_events, facts, versions, financial_metrics = live.financial_delta(
        cfg,
        baseline,
        "fixture",
        target_date,
        set(baseline_symbols["symbol"].astype(str)),
    )
    events = pd.concat([pd.DataFrame([market_event]), financial_events], ignore_index=True, sort=False)
    scope_rows = [{
        "event_id": market_event["event_id"],
        "event_type": "MARKET_SESSION_ADVANCE",
        "domain": "MARKET",
        "symbol": None,
        "period_end": None,
        "affected_symbol_count": len(market),
        "recompute_targets": "CAPITALIZATION|VALUATION|SHAREHOLDER_RETURN|UNIFIED_CURRENT",
        "scope_basis": "REAL_COMPLETED_SESSION_REPLAY_OVER_FROZEN_SYMBOL_SET",
        "authority": cfg["authority"],
        "trade_authority": "NONE",
    }]
    scope_rows += [{
        "event_id": row["event_id"],
        "event_type": row["event_type"],
        "domain": "FINANCIAL",
        "symbol": row["symbol"],
        "period_end": row["period_end"],
        "affected_symbol_count": 1,
        "recompute_targets": "STATEMENT_CURRENT|FINANCIAL_FACTORS|FINANCIAL_SCORE|VALUATION|UNIFIED_CURRENT",
        "scope_basis": "EXPLICIT_SYMBOL_AND_DEPENDENT_PERIODS",
        "authority": cfg["authority"],
        "trade_authority": "NONE",
    } for _, row in financial_events.iterrows()]
    scope = pd.DataFrame(scope_rows)
    market.to_parquet(candidate / "FMDL3EB_MARKET_DELTA.parquet", index=False, compression="zstd")
    financial_events.to_parquet(candidate / "FMDL3EC_FINANCIAL_EVENT_LEDGER.parquet", index=False, compression="zstd")
    facts.to_parquet(candidate / "FMDL3EC_FINANCIAL_FACT_DELTA.parquet", index=False, compression="zstd")
    versions.to_parquet(candidate / "FMDL3EC_FINANCIAL_VERSION_LEDGER.parquet", index=False, compression="zstd")
    events.to_parquet(candidate / "FMDL3EBC_DELTA_EVENT_LEDGER.parquet", index=False, compression="zstd")
    scope_path = candidate / "FMDL3EBC_AFFECTED_SCOPE.csv"
    scope.to_csv(scope_path, index=False, encoding="utf-8-sig")
    scope_replay = pd.read_csv(scope_path, encoding="utf-8-sig")
    for name, payload in [
        ("FMDL3EB_MARKET_VALIDATION.json", market_validation),
        ("FMDL3EBC_SOURCE_HASH_ERRORS.json", source_errors),
        ("FMDL3EBC_ENTRY_POINTER_SNAPSHOT.json", pointer),
        ("FMDL3EBC_BASELINE_SNAPSHOT.json", baseline),
    ]:
        bc.write_json(candidate / name, payload)
    catalogued = set(event_catalog["event_type"].astype(str))
    revision_ids = set(financial_events.loc[financial_events["event_type"].ne("FINANCIAL_DISCLOSURE_NEW"), "event_id"].astype(str))
    old_preserved = bool(revision_ids) and any(str(event_id) in revision_ids and len(group) >= 2 for event_id, group in versions.groupby("event_id"))
    affected_ratio = financial_metrics["affected_symbol_count"] / max(1, int(baseline["universe_symbol_count"]))
    checks = {
        "ENTRY_POINTER_ACCEPTED": pointer.get("status") == cfg["entry_gate"]["required_status"],
        "ENTRY_NEXT_GATE_ALIGNED": pointer.get("next_gate") == cfg["entry_gate"]["required_next_gate"],
        "BASELINE_ID_ALIGNED": pointer.get("baseline_id") == baseline.get("baseline_id"),
        "BASELINE_SOURCE_HASHES_UNCHANGED": not source_errors,
        "MARKET_EVENT_CATALOGUED": market_event["event_type"] in catalogued,
        "MARKET_REAL_COMPLETED_SESSION_REPLAY": market_validation["acceptance_mode"] == "REAL_COMPLETED_SESSION_REPLAY",
        "MARKET_DATE_STRICTLY_ADVANCED": market_validation["strictly_later"],
        "MARKET_SYMBOL_COVERAGE": market_validation["symbol_coverage_ratio"] >= cfg["market"]["minimum_symbol_coverage_ratio"],
        "MARKET_DUPLICATE_SYMBOL_ZERO": market_validation["duplicate_symbol_count"] == 0,
        "FROZEN_BASELINE_UNCHANGED_DURING_REPLAY": str(baseline["market_as_of_date"]) == pointer.get("market_as_of_date"),
        "FINANCIAL_EVENTS_CATALOGUED": bool(len(financial_events)) and set(financial_events["event_type"]).issubset(catalogued),
        "FINANCIAL_EVENT_MINIMUM": financial_metrics["financial_event_count"] >= cfg["financial"]["minimum_financial_event_count"],
        "FIRST_DISCLOSURE_CASE_PRESENT": financial_metrics["first_disclosure_case_count"] >= 1,
        "REVISION_CASE_PRESENT": financial_metrics["revision_case_count"] >= 1,
        "FINANCIAL_AFFECTED_SCOPE_WITHIN_THRESHOLD": affected_ratio <= cfg["financial"]["maximum_affected_symbol_ratio"],
        "OLD_VERSION_PRESERVED": old_preserved,
        "FUTURE_INFORMATION_ZERO": financial_metrics["future_information_count"] == 0,
        "DUPLICATE_EVENT_ID_ZERO": not events["event_id"].duplicated().any(),
        "EXPLICIT_AFFECTED_SCOPE": len(scope) == len(events),
        "ZERO_TRADE_AUTHORITY": set(events["trade_authority"]) == {"NONE"} and set(market["trade_authority"]) == {"NONE"},
    }
    failures = [name for name, passed in checks.items() if not bool(passed)]
    market_keys = [
        "MARKET_EVENT_CATALOGUED",
        "MARKET_REAL_COMPLETED_SESSION_REPLAY",
        "MARKET_DATE_STRICTLY_ADVANCED",
        "MARKET_SYMBOL_COVERAGE",
        "MARKET_DUPLICATE_SYMBOL_ZERO",
        "FROZEN_BASELINE_UNCHANGED_DURING_REPLAY",
    ]
    financial_keys = [
        "FINANCIAL_EVENTS_CATALOGUED",
        "FINANCIAL_EVENT_MINIMUM",
        "FIRST_DISCLOSURE_CASE_PRESENT",
        "REVISION_CASE_PRESENT",
        "FINANCIAL_AFFECTED_SCOPE_WITHIN_THRESHOLD",
        "OLD_VERSION_PRESERVED",
        "FUTURE_INFORMATION_ZERO",
    ]
    semantic_hashes = {
        "market_delta": bc.semantic_frame_hash(market),
        "financial_events": bc.semantic_frame_hash(financial_events),
        "financial_facts": bc.semantic_frame_hash(facts),
        "financial_versions": bc.semantic_frame_hash(versions),
        "affected_scope": bc.semantic_frame_hash(scope_replay),
    }
    metrics = {
        "mode": "real_completed_session_replay",
        "market_acceptance_mode": market_validation["acceptance_mode"],
        "baseline_id": baseline["baseline_id"],
        "source_fmdl3d_release_id": baseline["source_fmdl3d_release_id"],
        "baseline_market_as_of_date": baseline["market_as_of_date"],
        "refreshed_market_as_of_date": target_date,
        "market_replay_from_date": market_validation["baseline_date"],
        "market_replay_to_date": target_date,
        "post_frozen_baseline_advance_observed": market_validation["post_frozen_baseline_advance_observed"],
        "baseline_symbol_count": baseline["universe_symbol_count"],
        "market_delta_row_count": len(market),
        "market_symbol_coverage_ratio": market_validation["symbol_coverage_ratio"],
        "market_changed_close_count": int(market["market_delta_state"].eq("UPDATED").sum()),
        "market_missing_close_count": int(market["refreshed_close"].isna().sum()),
        "source_hash_error_count": len(source_errors),
        "duplicate_event_id_count": int(events["event_id"].duplicated().sum()),
        "financial_affected_symbol_ratio": affected_ratio,
        **financial_metrics,
        "elapsed_seconds": round(time.monotonic() - started, 4),
    }
    limitations = [
        "POST_FROZEN_BASELINE_LIVE_MARKET_ADVANCE_NOT_YET_OBSERVED; REAL_COMPLETED_SESSION_REPLAY_USED_FOR_ACCEPTANCE",
        "NO_POST_BASELINE_LIVE_FINANCIAL_NOTICE_SELECTED; REAL_HISTORICAL_PIT_REVISION_CHAINS_USED_FOR_OPERATIONAL_REPLAY",
    ]
    if financial_metrics["numeric_changed_or_added_fact_count"] == 0:
        limitations.append("PRE_REVISION_STRUCTURED_VALUES_NOT_RETAINED_FOR_SELECTED_REPLAY_CASES; DOCUMENT_VERSION_PIT_REPLAY_REMAINS_AUDITABLE")
    limitations += [
        "FMDL-3E-BC_BUILDS_AND_VALIDATES_DELTA_ASSETS_ONLY; DOWNSTREAM_CURRENT_PROPAGATION_IS_FMDL-3E-DE",
        "NO_INVESTMENT_SCORE_TARGET_PRICE_PORTFOLIO_ACTION_OR_TRADE_PERMISSION",
    ]
    decision = {
        "decision_version": "1.1.0",
        "release_id": release_id,
        "generated_at": generated_at,
        "program_id": "FMDL-3E-BC",
        "mode": "real_completed_session_replay",
        "status": cfg["exit_status"] if not failures else "FMDL3EBC_REMEDIATION_REQUIRED",
        "market_status": cfg["substatus"]["market_exit"] if all(checks[key] for key in market_keys) else "FMDL3EB_REMEDIATION_REQUIRED",
        "financial_status": cfg["substatus"]["financial_exit"] if all(checks[key] for key in financial_keys) else "FMDL3EC_REMEDIATION_REQUIRED",
        "hard_failures": failures,
        "checks": [{"check_id": name, "status": "PASS" if passed else "FAIL"} for name, passed in checks.items()],
        "metrics": metrics,
        "semantic_hashes": semantic_hashes,
        "controlled_limitations": limitations,
        "authority": cfg["authority"],
        "trade_authority": "NONE",
        "next_gate": cfg["next_gate"],
    }
    bc.write_json(candidate / "FMDL3EBC_DECISION.json", decision)
    bc.write_json(candidate / "FMDL3EBC_MANIFEST.json", bc.manifest_for_directory(candidate, release_id))
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
