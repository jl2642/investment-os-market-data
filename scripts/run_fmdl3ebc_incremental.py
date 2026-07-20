from __future__ import annotations

import argparse
import json
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import akshare as ak
import pandas as pd

from scripts import fmdl3ebc_core as bc
from scripts import fmdl3b_core as statement_core
from scripts import fmdl3b_semantic_overrides as semantic
from scripts import run_fmdl3b2_canary as canary
from scripts import run_fmdl3b_pilot as pilot

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("Asia/Shanghai")
CONFIG = ROOT / "config/fmdl3ebc_incremental_refresh.json"

EVENT_COLUMNS = ["event_id", "event_type", "domain", "detected_at", "effective_at", "symbol", "name", "period_end", "title", "affected_scope", "source_reference", "pit_replay_required", "live_detected", "replay_kind", "authority", "trade_authority"]
VERSION_COLUMNS = ["event_id", "symbol", "period_end", "revision_sequence", "revision_id", "title", "available_from", "superseded_at", "structured_value_status", "source_reference", "version_preserved", "pit_eligible_at_target", "live_detected", "authority", "trade_authority"]
FACT_COLUMNS = ["event_id", "symbol", "period_end", "statement", "line_item_id", "baseline_value", "refreshed_value", "delta_value", "change_type", "baseline_revision_sequence", "refreshed_revision_sequence", "baseline_available_from", "refreshed_available_from", "pit_eligible_at_target", "live_detected", "authority", "trade_authority"]


def load_inputs(cfg: dict[str, Any]):
    entry = cfg["entry_gate"]
    pointer = bc.read_json(ROOT / entry["pointer_path"])
    baseline = bc.read_json(ROOT / entry["baseline_manifest"])
    symbols = pd.read_parquet(ROOT / entry["baseline_symbol_hashes"])
    catalog = pd.read_csv(ROOT / entry["delta_event_catalog"], encoding="utf-8-sig")
    return pointer, baseline, symbols, catalog


def baseline_hash_errors(baseline: dict[str, Any]) -> list[dict[str, Any]]:
    errors = []
    for item in baseline.get("files", []):
        path = ROOT / item["path"]
        observed = bc.sha256_file(path) if path.exists() else None
        if observed != item.get("sha256"):
            errors.append({"path": item["path"], "expected": item.get("sha256"), "observed": observed})
    return errors


def market_delta(cfg: dict[str, Any], baseline: dict[str, Any], mode: str):
    base = pd.read_parquet(ROOT / cfg["market"]["baseline_unified"])
    base["symbol"] = base["symbol"].astype(str)
    baseline_date = str(baseline["market_as_of_date"])
    if mode == "live":
        release = bc.read_json(ROOT / cfg["market"]["source_release"])
        if release.get("status") not in cfg["market"]["required_source_statuses"]:
            raise SystemExit(f"market source release not accepted: {release.get('status')}")
        snap = pd.read_csv(ROOT / cfg["market"]["source_snapshot"], encoding="utf-8-sig")
        target_date, source_ref = str(release["as_of_date"]), str(release.get("run_id"))
    else:
        target_date = (pd.Timestamp(baseline_date) + pd.offsets.BDay(1)).date().isoformat()
        source_ref = "DETERMINISTIC_PR_FIXTURE"
        snap = base[["symbol", "close"]].copy()
        snap["as_of_date"], snap["prev_close"] = target_date, snap["close"]
        snap["close"] = snap.apply(lambda r: float(r["close"]) * (1 + ((int(bc.stable_hash(r["symbol"])[:4], 16) % 201) - 100) / 10000) if pd.notna(r["close"]) else None, axis=1)
        snap["data_status"] = snap["close"].notna().map({True: "TRADED", False: "NO_DATA"})
        snap["record_quality"] = "VALID"
        snap["row_hash"] = snap.apply(lambda r: bc.stable_hash({"symbol": r["symbol"], "date": target_date, "close": r["close"]}), axis=1)
    snap["symbol"] = snap["symbol"].astype(str)
    cols = [c for c in ["symbol", "as_of_date", "close", "prev_close", "data_status", "record_quality", "row_hash"] if c in snap]
    delta = base[["symbol", "close", "row_hash"]].rename(columns={"close": "baseline_close", "row_hash": "baseline_unified_row_hash"}).merge(
        snap[cols].rename(columns={"close": "refreshed_close", "row_hash": "source_market_row_hash"}), on="symbol", how="left")
    delta["baseline_market_as_of_date"], delta["refreshed_market_as_of_date"] = baseline_date, target_date
    delta["refreshed_close"] = pd.to_numeric(delta["refreshed_close"], errors="coerce")
    delta["baseline_close"] = pd.to_numeric(delta["baseline_close"], errors="coerce")
    delta["close_delta"] = delta["refreshed_close"] - delta["baseline_close"]
    delta["close_pct_delta"] = delta["close_delta"] / delta["baseline_close"].replace(0, pd.NA)
    valid = delta["refreshed_close"].gt(0)
    delta["market_delta_state"] = "UPDATED"
    delta.loc[~valid, "market_delta_state"] = "SOURCE_ROW_MISSING_OR_NO_POSITIVE_CLOSE"
    delta.loc[valid & delta["refreshed_close"].eq(delta["baseline_close"]), "market_delta_state"] = "UNCHANGED_CLOSE"
    delta["event_type"], delta["affected"] = "MARKET_SESSION_ADVANCE", True
    delta["authority"], delta["trade_authority"] = cfg["authority"], "NONE"
    delta["delta_row_hash"] = delta.apply(lambda r: bc.stable_hash({"symbol": r["symbol"], "from": baseline_date, "to": target_date, "old": r["baseline_close"], "new": r["refreshed_close"], "source": r.get("source_market_row_hash")}), axis=1)
    event_id = bc.stable_hash({"event_type": "MARKET_SESSION_ADVANCE", "from": baseline_date, "to": target_date, "source": source_ref})
    event = {"event_id": event_id, "event_type": "MARKET_SESSION_ADVANCE", "domain": "MARKET", "detected_at": datetime.now(TZ).isoformat(timespec="seconds"), "effective_at": target_date, "symbol": None, "name": None, "period_end": None, "title": None, "affected_scope": "ALL_BASELINE_SYMBOLS_ON_NEW_COMPLETED_SESSION", "source_reference": source_ref, "pit_replay_required": False, "live_detected": mode == "live", "replay_kind": "LIVE_COMPLETED_SESSION" if mode == "live" else "DETERMINISTIC_MARKET_FIXTURE", "authority": cfg["authority"], "trade_authority": "NONE"}
    validation = {"baseline_date": baseline_date, "target_date": target_date, "strictly_later": pd.Timestamp(target_date) > pd.Timestamp(baseline_date), "baseline_symbol_count": len(base), "source_symbol_count": snap["symbol"].nunique(), "matched_positive_close_count": int(valid.sum()), "symbol_coverage_ratio": float(valid.mean()), "duplicate_symbol_count": int(delta["symbol"].duplicated().sum()), "source_reference": source_ref}
    return delta, event, validation


def notice_columns(frame: pd.DataFrame) -> dict[str, str | None]:
    return {name: bc.first_existing(frame.columns, candidates) for name, candidates in {
        "code": ["代码", "股票代码", "证券代码"], "name": ["名称", "股票简称", "简称"],
        "title": ["公告标题", "标题"], "date": ["公告日期", "公告时间", "日期"], "url": ["网址", "公告链接", "链接"]}.items()}


def live_notices(cfg: dict[str, Any], baseline_date: str, target_date: str, universe: set[str]) -> list[dict[str, Any]]:
    start, end = pd.Timestamp(baseline_date).date() + timedelta(days=1), pd.Timestamp(target_date).date()
    if end < start:
        return []
    start = max(start, end - timedelta(days=int(cfg["financial"]["maximum_notice_lookback_days"]) - 1))
    found: dict[str, dict[str, Any]] = {}
    for day in bc.daterange(start, end):
        for category in cfg["financial"]["live_notice_categories"]:
            try:
                frame = ak.stock_notice_report(symbol=category, date=day.strftime("%Y%m%d"))
            except Exception:
                continue
            if not isinstance(frame, pd.DataFrame) or frame.empty:
                continue
            cols = notice_columns(frame)
            if not cols["code"] or not cols["title"]:
                continue
            for _, row in frame.iterrows():
                symbol, title = bc.symbol_from_code(row.get(cols["code"])), str(row.get(cols["title"]) or "")
                if symbol not in universe or not bc.is_financial_report_title(title):
                    continue
                parsed = pd.to_datetime(row.get(cols["date"]), errors="coerce") if cols["date"] else pd.NaT
                effective = parsed.date().isoformat() if pd.notna(parsed) else day.isoformat()
                source = str(row.get(cols["url"]) if cols["url"] else "") or f"akshare.stock_notice_report:{category}:{day}"
                event_id = bc.stable_hash({"symbol": symbol, "title": title, "date": effective, "source": source})
                found[event_id] = {"event_id": event_id, "event_type": bc.classify_financial_title(title), "domain": "FINANCIAL", "detected_at": datetime.now(TZ).isoformat(timespec="seconds"), "effective_at": effective, "symbol": symbol, "name": str(row.get(cols["name"]) or symbol) if cols["name"] else symbol, "period_end": bc.period_end_from_title(title), "title": title, "affected_scope": "AFFECTED_SYMBOL_AND_DEPENDENT_PERIODS", "source_reference": source, "pit_replay_required": True, "live_detected": True, "replay_kind": "LIVE_POST_BASELINE_NOTICE", "authority": cfg["authority"], "trade_authority": "NONE"}
    ordered = sorted(found.values(), key=lambda x: (x["effective_at"], x["symbol"], x["event_id"]))
    return ordered[: int(cfg["financial"]["maximum_live_symbols"])]


def historical_events(cfg: dict[str, Any], catalog: pd.DataFrame):
    revisions = bc.load_parquet_paths(ROOT, bc.catalog_paths(catalog, "revision"))
    events = []
    for case in bc.pick_historical_replay_cases(revisions):
        event_id = bc.stable_hash({"historical_replay": case})
        events.append({"event_id": event_id, "event_type": case["event_type"], "domain": "FINANCIAL", "detected_at": datetime.now(TZ).isoformat(timespec="seconds"), "effective_at": case["effective_at"], "symbol": case["symbol"], "name": case["symbol"], "period_end": case["period_end"], "title": case["title"], "affected_scope": "AFFECTED_SYMBOL_AND_DEPENDENT_PERIODS", "source_reference": case["source_reference"], "pit_replay_required": True, "live_detected": False, "replay_kind": case["replay_kind"], "authority": cfg["authority"], "trade_authority": "NONE"})
    return events, bc.normalize_revision_columns(revisions)


def fetch_symbol(symbol: str, name: str, cfg: dict[str, Any]):
    sample = {"symbol": symbol, "name": name, "profile": "UNCLASSIFIED_INCREMENTAL_REFRESH", "board": canary.derive_board(symbol), "extended": False}
    field_index, payload = statement_core.load_registry(ROOT / cfg["financial"]["field_registry"])
    field_index, payload = semantic.apply_overrides(field_index, payload)
    raw, revisions, _, support = canary.extract_selected_facts(sample, {"canary": {"minimum_report_period_end": cfg["financial"]["minimum_report_period_end"], "maximum_periods_per_statement": cfg["financial"]["maximum_periods_per_statement"]}}, field_index, pilot.fetch_calendar())
    raw_frame = pd.DataFrame(raw)
    store_cfg = bc.read_json(ROOT / cfg["financial"]["statement_store_config"])
    normalized, _ = statement_core.select_normalized_facts(raw_frame, payload, store_cfg["normalization"]["material_conflict_relative_tolerance"], store_cfg["normalization"]["material_conflict_absolute_tolerance"])
    return normalized, bc.normalize_revision_columns(pd.DataFrame(revisions)), support


def financial_delta(cfg: dict[str, Any], baseline: dict[str, Any], mode: str, target_date: str, universe: set[str]):
    release = bc.read_json(ROOT / cfg["financial"]["statement_release"])
    catalog = pd.read_csv(ROOT / cfg["financial"]["statement_catalog"], encoding="utf-8-sig")
    history_events, revisions = historical_events(cfg, catalog)
    events = history_events + (live_notices(cfg, baseline["market_as_of_date"], target_date, universe) if mode == "live" else [])
    events = list({e["event_id"]: e for e in events}.values())
    event_frame = pd.DataFrame(events, columns=EVENT_COLUMNS)
    affected = set(event_frame["symbol"].dropna().astype(str))
    baseline_facts = bc.load_parquet_paths(ROOT, bc.catalog_paths(catalog, "statement_normalized"), affected)
    fetched: dict[str, tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]] = {}
    live_meta = {e["symbol"]: e["name"] for e in events if e["live_detected"]}
    if live_meta:
        with ThreadPoolExecutor(max_workers=min(4, len(live_meta))) as pool:
            futures = {pool.submit(fetch_symbol, symbol, name, cfg): symbol for symbol, name in live_meta.items()}
            for future in as_completed(futures):
                try:
                    fetched[futures[future]] = future.result()
                except Exception as exc:
                    fetched[futures[future]] = (pd.DataFrame(), pd.DataFrame(), {"statement_status": "FETCH_ERROR", "status_reason": f"{type(exc).__name__}:{str(exc)[:200]}"})
    version_rows, fact_rows, support_rows = [], [], []
    target_utc = pd.Timestamp(target_date, tz="Asia/Shanghai").tz_convert("UTC")
    for event in events:
        symbol, period = event["symbol"], event.get("period_end")
        refreshed, live_revisions, support = fetched.get(symbol, (pd.DataFrame(), pd.DataFrame(), {}))
        if support:
            support_rows.append({"symbol": symbol, **support})
        source_revisions = live_revisions if event["live_detected"] and len(live_revisions) else revisions
        if event["live_detected"] and not period and len(refreshed):
            eligible = refreshed[pd.to_datetime(refreshed["available_from"], errors="coerce", utc=True).le(target_utc)]
            if len(eligible):
                period = str(eligible.sort_values("period_end").iloc[-1]["period_end"])
                event["period_end"] = period
        version_group = source_revisions[(source_revisions["symbol"].astype(str) == symbol) & (source_revisions["period_end"].astype(str) == str(period))] if period and len(source_revisions) else pd.DataFrame()
        for _, row in version_group.iterrows():
            available = pd.to_datetime(row.get("available_from"), errors="coerce", utc=True)
            version_rows.append({"event_id": event["event_id"], "symbol": symbol, "period_end": period, "revision_sequence": int(row.get("revision_sequence", 1)), "revision_id": row.get("revision_id"), "title": row.get("title"), "available_from": row.get("available_from"), "superseded_at": row.get("superseded_at"), "structured_value_status": row.get("structured_value_status"), "source_reference": row.get("filing_link") or event["source_reference"], "version_preserved": True, "pit_eligible_at_target": bool(pd.notna(available) and available <= target_utc), "live_detected": event["live_detected"], "authority": cfg["authority"], "trade_authority": "NONE"})
        base_group = baseline_facts[(baseline_facts["symbol"].astype(str) == symbol) & (baseline_facts["period_end"].astype(str) == str(period))] if period and len(baseline_facts) else pd.DataFrame()
        new_group = refreshed[(refreshed["symbol"].astype(str) == symbol) & (refreshed["period_end"].astype(str) == str(period))] if period and len(refreshed) else pd.DataFrame()
        if event["live_detected"] and len(new_group):
            keys = ["statement", "line_item_id", "period_end"]
            old = base_group[keys + ["normalized_value", "revision_sequence", "available_from"]].rename(columns={"normalized_value": "baseline_value", "revision_sequence": "baseline_revision_sequence", "available_from": "baseline_available_from"}) if len(base_group) else pd.DataFrame(columns=keys + ["baseline_value", "baseline_revision_sequence", "baseline_available_from"])
            new = new_group[keys + ["normalized_value", "revision_sequence", "available_from"]].rename(columns={"normalized_value": "refreshed_value", "revision_sequence": "refreshed_revision_sequence", "available_from": "refreshed_available_from"})
            for _, row in old.merge(new, on=keys, how="outer").iterrows():
                old_value, new_value = row.get("baseline_value"), row.get("refreshed_value")
                change = "ADDED_FACT" if pd.isna(old_value) else "REMOVED_FROM_LATEST_PROVIDER_EXPORT" if pd.isna(new_value) else "VALUE_CHANGED" if float(old_value) != float(new_value) else "UNCHANGED_FACT"
                available = pd.to_datetime(row.get("refreshed_available_from"), errors="coerce", utc=True)
                fact_rows.append({"event_id": event["event_id"], "symbol": symbol, "period_end": row["period_end"], "statement": row["statement"], "line_item_id": row["line_item_id"], "baseline_value": old_value, "refreshed_value": new_value, "delta_value": float(new_value) - float(old_value) if pd.notna(old_value) and pd.notna(new_value) else None, "change_type": change, "baseline_revision_sequence": row.get("baseline_revision_sequence"), "refreshed_revision_sequence": row.get("refreshed_revision_sequence"), "baseline_available_from": row.get("baseline_available_from"), "refreshed_available_from": row.get("refreshed_available_from"), "pit_eligible_at_target": bool(pd.notna(available) and available <= target_utc), "live_detected": True, "authority": cfg["authority"], "trade_authority": "NONE"})
        else:
            effective = pd.to_datetime(event["effective_at"], errors="coerce", utc=True)
            fact_rows.append({"event_id": event["event_id"], "symbol": symbol, "period_end": period, "statement": "DOCUMENT_LINEAGE", "line_item_id": "__DOCUMENT_VERSION__", "baseline_value": None, "refreshed_value": None, "delta_value": None, "change_type": "PIT_DOCUMENT_VERSION_REPLAY", "baseline_revision_sequence": None, "refreshed_revision_sequence": None, "baseline_available_from": None, "refreshed_available_from": event["effective_at"], "pit_eligible_at_target": bool(pd.notna(effective) and effective <= target_utc), "live_detected": event["live_detected"], "authority": cfg["authority"], "trade_authority": "NONE"})
    event_frame = pd.DataFrame(events, columns=EVENT_COLUMNS)
    version_frame, fact_frame = pd.DataFrame(version_rows, columns=VERSION_COLUMNS), pd.DataFrame(fact_rows, columns=FACT_COLUMNS)
    selected_future = 0
    if len(version_frame):
        available = pd.to_datetime(version_frame["available_from"], errors="coerce", utc=True)
        selected_future += int((version_frame["pit_eligible_at_target"].astype(bool) & available.gt(target_utc)).sum())
    if len(fact_frame):
        available = pd.to_datetime(fact_frame["refreshed_available_from"], errors="coerce", utc=True)
        selected_future += int((fact_frame["pit_eligible_at_target"].astype(bool) & available.gt(target_utc)).sum())
    metrics = {"statement_release_id": release["release_id"], "financial_event_count": len(event_frame), "live_financial_event_count": int(event_frame["live_detected"].sum()), "historical_replay_event_count": int((~event_frame["live_detected"]).sum()), "first_disclosure_case_count": int(event_frame["event_type"].eq("FINANCIAL_DISCLOSURE_NEW").sum()), "revision_case_count": int(event_frame["event_type"].ne("FINANCIAL_DISCLOSURE_NEW").sum()), "affected_symbol_count": event_frame["symbol"].nunique(), "version_ledger_row_count": len(version_frame), "fact_delta_row_count": len(fact_frame), "numeric_changed_or_added_fact_count": int(fact_frame["change_type"].isin(["VALUE_CHANGED", "ADDED_FACT"]).sum()), "future_information_count": selected_future, "fetch_support_row_count": len(support_rows)}
    return event_frame, fact_frame, version_frame, metrics


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--mode", choices=["fixture", "live"], default="fixture")
    args = parser.parse_args()
    cfg = bc.read_json(args.config)
    pointer, baseline, baseline_symbols, event_catalog = load_inputs(cfg)
    candidate = ROOT / cfg["publication"]["candidate_root"]
    if candidate.exists():
        shutil.rmtree(candidate)
    candidate.mkdir(parents=True)
    started = time.monotonic()
    generated_at = datetime.now(TZ).isoformat(timespec="seconds")
    release_id = f"FMDL3EBC_{datetime.now(TZ).strftime('%Y%m%dT%H%M%S%z')}"
    source_errors = baseline_hash_errors(baseline)
    market, market_event, market_validation = market_delta(cfg, baseline, args.mode)
    financial_events, facts, versions, financial_metrics = financial_delta(cfg, baseline, args.mode, market_validation["target_date"], set(baseline_symbols["symbol"].astype(str)))
    events = pd.concat([pd.DataFrame([market_event]), financial_events], ignore_index=True, sort=False)
    scope_rows = [{"event_id": market_event["event_id"], "event_type": "MARKET_SESSION_ADVANCE", "domain": "MARKET", "symbol": None, "period_end": None, "affected_symbol_count": len(market), "recompute_targets": "CAPITALIZATION|VALUATION|SHAREHOLDER_RETURN|UNIFIED_CURRENT", "scope_basis": "ALL_BASELINE_SYMBOLS_ON_NEW_COMPLETED_SESSION", "authority": cfg["authority"], "trade_authority": "NONE"}]
    scope_rows += [{"event_id": e["event_id"], "event_type": e["event_type"], "domain": "FINANCIAL", "symbol": e["symbol"], "period_end": e["period_end"], "affected_symbol_count": 1, "recompute_targets": "STATEMENT_CURRENT|FINANCIAL_FACTORS|FINANCIAL_SCORE|VALUATION|UNIFIED_CURRENT", "scope_basis": "EXPLICIT_SYMBOL_AND_DEPENDENT_PERIODS", "authority": cfg["authority"], "trade_authority": "NONE"} for _, e in financial_events.iterrows()]
    scope = pd.DataFrame(scope_rows)
    market.to_parquet(candidate / "FMDL3EB_MARKET_DELTA.parquet", index=False, compression="zstd")
    financial_events.to_parquet(candidate / "FMDL3EC_FINANCIAL_EVENT_LEDGER.parquet", index=False, compression="zstd")
    facts.to_parquet(candidate / "FMDL3EC_FINANCIAL_FACT_DELTA.parquet", index=False, compression="zstd")
    versions.to_parquet(candidate / "FMDL3EC_FINANCIAL_VERSION_LEDGER.parquet", index=False, compression="zstd")
    events.to_parquet(candidate / "FMDL3EBC_DELTA_EVENT_LEDGER.parquet", index=False, compression="zstd")
    scope_path = candidate / "FMDL3EBC_AFFECTED_SCOPE.csv"
    scope.to_csv(scope_path, index=False, encoding="utf-8-sig")
    scope_replay = pd.read_csv(scope_path, encoding="utf-8-sig")
    for name, payload in [("FMDL3EB_MARKET_VALIDATION.json", market_validation), ("FMDL3EBC_SOURCE_HASH_ERRORS.json", source_errors), ("FMDL3EBC_ENTRY_POINTER_SNAPSHOT.json", pointer), ("FMDL3EBC_BASELINE_SNAPSHOT.json", baseline)]:
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
        "MARKET_DATE_STRICTLY_ADVANCED": market_validation["strictly_later"],
        "MARKET_SYMBOL_COVERAGE": market_validation["symbol_coverage_ratio"] >= cfg["market"]["minimum_symbol_coverage_ratio"],
        "MARKET_DUPLICATE_SYMBOL_ZERO": market_validation["duplicate_symbol_count"] == 0,
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
    market_keys = ["MARKET_EVENT_CATALOGUED", "MARKET_DATE_STRICTLY_ADVANCED", "MARKET_SYMBOL_COVERAGE", "MARKET_DUPLICATE_SYMBOL_ZERO"]
    financial_keys = ["FINANCIAL_EVENTS_CATALOGUED", "FINANCIAL_EVENT_MINIMUM", "FIRST_DISCLOSURE_CASE_PRESENT", "REVISION_CASE_PRESENT", "FINANCIAL_AFFECTED_SCOPE_WITHIN_THRESHOLD", "OLD_VERSION_PRESERVED", "FUTURE_INFORMATION_ZERO"]
    semantic_hashes = {"market_delta": bc.semantic_frame_hash(market), "financial_events": bc.semantic_frame_hash(financial_events), "financial_facts": bc.semantic_frame_hash(facts), "financial_versions": bc.semantic_frame_hash(versions), "affected_scope": bc.semantic_frame_hash(scope_replay)}
    metrics = {"mode": args.mode, "baseline_id": baseline["baseline_id"], "source_fmdl3d_release_id": baseline["source_fmdl3d_release_id"], "baseline_market_as_of_date": baseline["market_as_of_date"], "refreshed_market_as_of_date": market_validation["target_date"], "baseline_symbol_count": baseline["universe_symbol_count"], "market_delta_row_count": len(market), "market_symbol_coverage_ratio": market_validation["symbol_coverage_ratio"], "market_changed_close_count": int(market["market_delta_state"].eq("UPDATED").sum()), "market_missing_close_count": int(market["refreshed_close"].isna().sum()), "source_hash_error_count": len(source_errors), "duplicate_event_id_count": int(events["event_id"].duplicated().sum()), "financial_affected_symbol_ratio": affected_ratio, **financial_metrics, "elapsed_seconds": round(time.monotonic() - started, 4)}
    limitations = []
    if financial_metrics["live_financial_event_count"] == 0:
        limitations.append("NO_POST_BASELINE_LIVE_FINANCIAL_NOTICE_SELECTED; REAL_HISTORICAL_PIT_REVISION_CHAINS_USED_FOR_OPERATIONAL_REPLAY")
    if financial_metrics["numeric_changed_or_added_fact_count"] == 0:
        limitations.append("PRE_REVISION_STRUCTURED_VALUES_NOT_RETAINED_FOR_SELECTED_REPLAY_CASES; DOCUMENT_VERSION_PIT_REPLAY_REMAINS_AUDITABLE")
    limitations += ["FMDL-3E-BC_BUILDS_AND_VALIDATES_DELTA_ASSETS_ONLY; DOWNSTREAM_CURRENT_PROPAGATION_IS_FMDL-3E-DE", "NO_INVESTMENT_SCORE_TARGET_PRICE_PORTFOLIO_ACTION_OR_TRADE_PERMISSION"]
    decision = {"decision_version": "1.0.0", "release_id": release_id, "generated_at": generated_at, "program_id": "FMDL-3E-BC", "mode": args.mode, "status": cfg["exit_status"] if not failures else "FMDL3EBC_REMEDIATION_REQUIRED", "market_status": cfg["substatus"]["market_exit"] if all(checks[k] for k in market_keys) else "FMDL3EB_REMEDIATION_REQUIRED", "financial_status": cfg["substatus"]["financial_exit"] if all(checks[k] for k in financial_keys) else "FMDL3EC_REMEDIATION_REQUIRED", "hard_failures": failures, "checks": [{"check_id": name, "status": "PASS" if passed else "FAIL"} for name, passed in checks.items()], "metrics": metrics, "semantic_hashes": semantic_hashes, "controlled_limitations": limitations, "authority": cfg["authority"], "trade_authority": "NONE", "next_gate": cfg["next_gate"]}
    bc.write_json(candidate / "FMDL3EBC_DECISION.json", decision)
    bc.write_json(candidate / "FMDL3EBC_MANIFEST.json", bc.manifest_for_directory(candidate, release_id))
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
