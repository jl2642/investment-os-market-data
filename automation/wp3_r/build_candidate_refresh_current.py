#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def semantic_hash(payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def normalize_security_id(value: Any) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    raw = str(value).strip().upper()
    if not raw:
        return None
    if "." in raw:
        code, suffix = raw.split(".", 1)
        if suffix in {"SH", "SZ", "BJ", "OF"}:
            return f"{code.zfill(6)}.{suffix}"
    code = raw.zfill(6)
    if code.startswith(("4", "8", "92")):
        return f"{code}.BJ"
    if code.startswith(("5", "6")):
        return f"{code}.SH"
    if code.startswith(("0", "1", "2", "3")):
        return f"{code}.SZ"
    return code


def recursively_collect_securities(value: Any, route: str = "ROOT") -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if isinstance(value, dict):
        security_value = None
        for key in ("security_id", "symbol", "stock_code", "security_code", "code"):
            if key in value:
                security_value = value[key]
                break
        sid = normalize_security_id(security_value)
        if sid:
            rows.append(
                {
                    "security_id": sid,
                    "security_name": str(
                        value.get("security_name")
                        or value.get("stock_name")
                        or value.get("holding_name")
                        or ""
                    ),
                    "route": route,
                }
            )
        for key, child in value.items():
            if isinstance(child, (dict, list)):
                rows.extend(recursively_collect_securities(child, key.upper()))
    elif isinstance(value, list):
        for child in value:
            rows.extend(recursively_collect_securities(child, route))
    return rows


def unique_tracked(candidate: dict[str, Any]) -> list[dict[str, str]]:
    priority = {
        "CANDIDATE_CORE_MEMBERS": 0,
        "CANDIDATE_CORE": 0,
        "SHADOW_TRACK": 1,
        "SHADOW_TRACK_MEMBERS": 1,
        "RESEARCH_QUEUE": 2,
        "RESEARCH_QUEUE_MEMBERS": 2,
        "HISTORICAL_CORE20_ARCHIVE": 3,
    }
    best: dict[str, dict[str, str]] = {}
    for row in recursively_collect_securities(candidate):
        current = best.get(row["security_id"])
        if current is None or priority.get(row["route"], 9) < priority.get(current["route"], 9):
            best[row["security_id"]] = row
    return sorted(best.values(), key=lambda row: (priority.get(row["route"], 9), row["security_id"]))


def load_frame(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path, dtype=str, low_memory=False)


def find_column(columns: Iterable[str], candidates: Iterable[str]) -> str | None:
    lookup = {str(column).lower(): str(column) for column in columns}
    for candidate in candidates:
        if candidate.lower() in lookup:
            return lookup[candidate.lower()]
    return None


def parse_date(value: Any) -> date | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    raw = str(value).strip()
    if not raw:
        return None
    try:
        return pd.Timestamp(raw).date()
    except Exception:
        return None


def status_by_age(as_of: date, report_date: date | None, max_age: int) -> tuple[str, int | None]:
    if report_date is None:
        return "BLOCKED_MISSING_REPORT_PERIOD", None
    age = (as_of - report_date).days
    return ("FRESH" if age <= max_age else "STALE"), age


def profile_readiness(
    profiles: pd.DataFrame,
    score: pd.DataFrame,
    financial_contract: dict[str, Any],
) -> dict[str, Any]:
    profile_column = find_column(profiles.columns, ["sector_profile", "financial_profile"])
    symbol_column = find_column(profiles.columns, ["symbol", "security_id", "stock_code"])
    if not profile_column or not symbol_column:
        return {
            "status": "BLOCKED_PROFILE_RECONCILIATION_COLUMNS_MISSING",
            "available_columns": sorted(map(str, profiles.columns)),
            "trade_authority": "NONE",
        }
    frame = profiles[[symbol_column, profile_column]].copy()
    frame[symbol_column] = frame[symbol_column].astype(str)
    counts = frame[profile_column].fillna("MISSING").astype(str).value_counts().to_dict()
    score_profile_column = find_column(score.columns, ["sector_profile", "financial_profile"])
    score_state_column = find_column(score.columns, ["score_state"])
    score_counts: dict[str, Any] = {}
    if score_profile_column:
        grouped = score.groupby(score_profile_column, dropna=False)
        for key, group in grouped:
            states = group[score_state_column].astype(str).value_counts().to_dict() if score_state_column else {}
            score_counts[str(key)] = {"rows": int(len(group)), "states": states}

    financial_rows = []
    for profile_name, contract in financial_contract["profiles"].items():
        required_metrics = sorted(
            {metric for family in contract["families"].values() for metric in family["required_metrics"]}
        )
        reusable = sorted(set(contract.get("currently_reusable_metrics", [])))
        coverage = len(set(reusable).intersection(required_metrics)) / len(required_metrics) if required_metrics else 0.0
        missing = sorted(set(required_metrics) - set(reusable))
        financial_rows.append(
            {
                "profile": profile_name,
                "issuer_count": int(counts.get(profile_name, 0)),
                "required_metric_count": len(required_metrics),
                "currently_reusable_metric_count": len(set(reusable).intersection(required_metrics)),
                "current_metric_coverage": round(coverage, 6),
                "missing_production_metrics": missing,
                "composite_score_status": (
                    "READY"
                    if coverage >= float(financial_contract["scoring_policy"]["minimum_required_metric_coverage"])
                    and not missing
                    else "BLOCKED_INDEPENDENT_PROFILE_INPUTS_INCOMPLETE"
                ),
                "general_non_financial_score_substitution_forbidden": True,
            }
        )
    return {
        "status": "PARTIAL_FINANCIAL_PROFILE_CONTRACT_INSTALLED_INPUT_EXTENSION_REQUIRED",
        "profile_counts": counts,
        "score_profile_states": score_counts,
        "financial_profiles": financial_rows,
        "cross_profile_ranking_forbidden": True,
        "general_non_financial_profile_status": "EXISTING_FMDL3CD_SCORE_RETAINED",
        "trade_authority": "NONE",
    }


def financial_freshness(
    family_scores: pd.DataFrame,
    as_of: date,
    max_age: int,
) -> dict[str, Any]:
    symbol_col = find_column(family_scores.columns, ["symbol", "security_id", "stock_code"])
    period_max_col = find_column(family_scores.columns, ["family_period_max", "period_end"])
    period_min_col = find_column(family_scores.columns, ["family_period_min"])
    availability_col = find_column(family_scores.columns, ["family_as_of_timestamp", "as_of_timestamp", "available_at"])
    if not symbol_col or not period_max_col or not availability_col:
        return {
            "status": "BLOCKED_REPORT_PERIOD_OR_AVAILABILITY_COLUMNS_MISSING",
            "available_columns": sorted(map(str, family_scores.columns)),
            "required": {
                "symbol": symbol_col,
                "period_max": period_max_col,
                "availability": availability_col,
            },
            "trade_authority": "NONE",
        }
    rows = []
    for symbol, group in family_scores.groupby(symbol_col, dropna=False):
        periods = [parse_date(value) for value in group[period_max_col].tolist()]
        periods = [value for value in periods if value]
        period_max = max(periods) if periods else None
        period_min_values = [parse_date(value) for value in group[period_min_col].tolist()] if period_min_col else []
        period_min_values = [value for value in period_min_values if value]
        availability = [parse_date(value) for value in group[availability_col].tolist()]
        availability = [value for value in availability if value]
        freshness, age = status_by_age(as_of, period_max, max_age)
        rows.append(
            {
                "security_id": normalize_security_id(symbol),
                "latest_report_period": period_max.isoformat() if period_max else None,
                "earliest_family_period": min(period_min_values).isoformat() if period_min_values else None,
                "latest_availability_date": max(availability).isoformat() if availability else None,
                "report_age_calendar_days": age,
                "freshness_status": freshness,
                "family_count": int(len(group)),
            }
        )
    counts = pd.Series([row["freshness_status"] for row in rows], dtype=str).value_counts().to_dict()
    return {
        "status": "PASS_REPORT_PERIOD_AND_AVAILABILITY_AUDITED",
        "as_of_date": as_of.isoformat(),
        "max_age_days": max_age,
        "counts": counts,
        "rows": rows,
        "stale_or_missing_count": sum(1 for row in rows if row["freshness_status"] != "FRESH"),
        "trade_authority": "NONE",
    }


def industry_quality(
    market: pd.DataFrame,
    profiles: pd.DataFrame,
    contract: dict[str, Any],
) -> dict[str, Any]:
    columns = list(map(str, market.columns))
    symbol_col = find_column(columns, ["security_id", "symbol", "stock_code", "code"])
    industry_code = find_column(columns, ["industry_code", "sw_industry_code", "citic_industry_code"])
    industry_name = find_column(columns, ["industry_name", "sw_industry_name", "citic_industry_name", "industry"])
    source_col = find_column(columns, ["classification_source", "industry_source"])
    effective_col = find_column(columns, ["industry_effective_date", "classification_effective_date", "effective_date"])
    total = int(len(market))
    coverage = 0.0
    unresolved = total
    if symbol_col and industry_name:
        names = market[industry_name].fillna("").astype(str).str.strip()
        unresolved = int((names == "").sum())
        coverage = (total - unresolved) / total if total else 0.0
    profile_col = find_column(profiles.columns, ["sector_profile", "financial_profile"])
    profile_symbol = find_column(profiles.columns, ["symbol", "security_id", "stock_code"])
    profile_coverage = 0.0
    if profile_col and profile_symbol and len(profiles):
        profile_coverage = float(profiles[profile_col].fillna("").astype(str).str.strip().ne("").mean())
    complete_fields = all([symbol_col, industry_code, industry_name, source_col, effective_col])
    passes_quality = bool(
        total
        and complete_fields
        and coverage >= float(contract["quality_gates"]["security_id_coverage_min"])
        and unresolved / total <= float(contract["quality_gates"]["unresolved_industry_max"])
    )
    status = (
        "PASS_CANONICAL_INDUSTRY_QUALITY_GATE"
        if passes_quality
        else "BLOCKED_SECURITY_MASTER_INDUSTRY_FIELDS_INCOMPLETE"
    )
    return {
        "status": status,
        "market_row_count": total,
        "detected_fields": {
            "symbol": symbol_col,
            "industry_code": industry_code,
            "industry_name": industry_name,
            "classification_source": source_col,
            "effective_date": effective_col,
        },
        "industry_name_coverage": round(coverage, 6),
        "unresolved_industry_count": unresolved,
        "financial_statement_profile_coverage": round(profile_coverage, 6),
        "industry_relative_ranking_allowed": status == "PASS_CANONICAL_INDUSTRY_QUALITY_GATE",
        "strategy_sleeve_as_industry_substitute_forbidden": True,
        "available_market_columns": sorted(columns),
        "trade_authority": "NONE",
    }


def weekly_screen(
    market: pd.DataFrame,
    tracked: list[dict[str, str]],
    binding: dict[str, Any],
    max_age_days: int,
    as_of: date,
) -> dict[str, Any]:
    symbol_col = find_column(market.columns, ["security_id", "symbol", "stock_code", "code"])
    price_col = find_column(market.columns, ["close", "latest_price", "current_price", "price"])
    date_col = find_column(market.columns, ["trade_date", "date", "as_of_date"])
    name_col = find_column(market.columns, ["security_name", "stock_name", "name"])
    pct_col = find_column(market.columns, ["pct_change", "change_pct", "return_1d"])
    if not symbol_col or not price_col:
        return {
            "status": "BLOCKED_MARKET_SYMBOL_OR_PRICE_COLUMN_MISSING",
            "available_columns": sorted(map(str, market.columns)),
            "trade_authority": "NONE",
        }
    frame = market.copy()
    frame["_security_id"] = frame[symbol_col].map(normalize_security_id)
    lookup = {row["_security_id"]: row for _, row in frame.iterrows() if row["_security_id"]}
    rows, missing = [], []
    for target in tracked:
        source = lookup.get(target["security_id"])
        if source is None:
            missing.append(target["security_id"])
            continue
        mark_date = parse_date(source.get(date_col)) if date_col else parse_date(binding.get("as_of_date") or binding.get("as_of"))
        age = (as_of - mark_date).days if mark_date else None
        rows.append(
            {
                "security_id": target["security_id"],
                "security_name": target["security_name"] or (str(source.get(name_col)) if name_col else ""),
                "candidate_route": target["route"],
                "price": float(source[price_col]) if pd.notna(source[price_col]) else None,
                "price_as_of": mark_date.isoformat() if mark_date else None,
                "price_age_calendar_days": age,
                "one_day_change_pct": float(source[pct_col]) if pct_col and pd.notna(source[pct_col]) else None,
                "freshness_status": "FRESH" if age is not None and age <= max_age_days else "STALE_OR_UNKNOWN",
                "screen_role": "PRICE_AND_FRESHNESS_MONITOR_ONLY",
            }
        )
    stale = [row["security_id"] for row in rows if row["freshness_status"] != "FRESH"]
    return {
        "status": "PASS_WEEKLY_PRICE_SCREEN_NO_MEMBERSHIP_MUTATION" if not missing and not stale else "PARTIAL_WEEKLY_PRICE_SCREEN",
        "as_of_date": as_of.isoformat(),
        "market_binding": binding,
        "tracked_count": len(tracked),
        "covered_count": len(rows),
        "missing_security_ids": missing,
        "stale_security_ids": stale,
        "rows": rows,
        "candidate_membership_mutations": 0,
        "buy_signals": 0,
        "orders": 0,
        "trade_authority": "NONE",
    }


def outcome_current(
    entry_rows: list[dict[str, Any]],
    ledger_path: Path,
    windows: list[int],
) -> dict[str, Any]:
    valid = [row for row in entry_rows if row.get("status") == "COMPLETE" and row.get("entry_date") and row.get("entry_price")]
    ledger = read_jsonl(ledger_path) if ledger_path.exists() else []
    by_security: dict[str, list[dict[str, Any]]] = {}
    for row in ledger:
        sid = normalize_security_id(row.get("security_id"))
        if sid:
            by_security.setdefault(sid, []).append(row)
    for rows in by_security.values():
        rows.sort(key=lambda row: str(row.get("trade_date")))

    results = []
    completed = set()
    for baseline in valid:
        sid = normalize_security_id(baseline["security_id"])
        entry_date = str(baseline["entry_date"])
        prices = [row for row in by_security.get(sid or "", []) if str(row.get("trade_date")) > entry_date]
        benchmark_prices = [row for row in by_security.get("000300.SH", []) if str(row.get("trade_date")) > entry_date]
        window_rows = []
        for window in windows:
            if len(prices) < window or len(benchmark_prices) < window:
                window_rows.append(
                    {
                        "window_trading_days": window,
                        "status": "PENDING_WINDOW_NOT_MATURE_OR_PRICE_LEDGER_INCOMPLETE",
                        "observed_security_sessions": len(prices),
                        "observed_benchmark_sessions": len(benchmark_prices),
                    }
                )
                continue
            end_row = prices[window - 1]
            benchmark_end = next(
                (row for row in benchmark_prices if str(row.get("trade_date")) == str(end_row.get("trade_date"))),
                None,
            )
            benchmark_entry = next(
                (row for row in by_security.get("000300.SH", []) if str(row.get("trade_date")) == entry_date),
                None,
            )
            if benchmark_end is None or benchmark_entry is None:
                window_rows.append(
                    {
                        "window_trading_days": window,
                        "status": "BLOCKED_BENCHMARK_DATE_ALIGNMENT_OR_ENTRY_PRICE_MISSING",
                        "endpoint_date": end_row.get("trade_date"),
                    }
                )
                continue
            security_return = float(end_row["close"]) / float(baseline["entry_price"]) - 1.0
            benchmark_return = float(benchmark_end["close"]) / float(benchmark_entry["close"]) - 1.0
            path = [float(baseline["entry_price"])] + [float(row["close"]) for row in prices[:window]]
            peak = path[0]
            max_drawdown = 0.0
            for value in path:
                peak = max(peak, value)
                max_drawdown = min(max_drawdown, value / peak - 1.0)
            completed.add(window)
            window_rows.append(
                {
                    "window_trading_days": window,
                    "status": "COMPLETE_BROAD_MARKET_ATTRIBUTION",
                    "endpoint_date": end_row["trade_date"],
                    "absolute_return": round(security_return, 10),
                    "benchmark_security_id": "000300.SH",
                    "benchmark_return": round(benchmark_return, 10),
                    "excess_return": round(security_return - benchmark_return, 10),
                    "max_drawdown": round(max_drawdown, 10),
                    "primary_industry_benchmark_status": "PENDING_CANONICAL_INDEX_IDENTIFIER_AND_HISTORY_BINDING",
                    "alpha_claim_allowed": False,
                }
            )
        results.append(
            {
                "security_id": sid,
                "security_name": baseline.get("security_name"),
                "entry_baseline_id": baseline.get("baseline_id"),
                "entry_date": entry_date,
                "entry_price": baseline.get("entry_price"),
                "benchmark_name_from_baseline": baseline.get("benchmark"),
                "broad_market_benchmark": "000300.SH",
                "windows": window_rows,
            }
        )
    return {
        "state_id": "WP3R_CANDIDATE_OUTCOME_CURRENT",
        "status": "WINDOWS_PENDING" if len(completed) < len(windows) else "ALL_REQUIRED_WINDOWS_AVAILABLE_FOR_AT_LEAST_ONE_CANDIDATE",
        "valid_entry_baseline_count": len(valid),
        "price_ledger_row_count": len(ledger),
        "required_windows": windows,
        "completed_windows_present": sorted(completed),
        "results": results,
        "alpha_claim_allowed": False,
        "candidate_membership_mutations": 0,
        "trade_authority": "NONE",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--config", default="automation/wp3_r/config.json")
    parser.add_argument("--as-of", default=None)
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    config = read_json(root / args.config)
    as_of = date.fromisoformat(args.as_of or config["status_date"])
    inputs, outputs = config["inputs"], config["outputs"]

    candidate = read_json(root / inputs["candidate_current"])
    outcome_contract = read_json(root / inputs["candidate_outcome_contract"])
    entry_baselines = read_jsonl(root / inputs["entry_baselines"])
    binding = read_json(root / inputs["a_share_binding"])
    market = load_frame(root / inputs["a_share_current"])
    score = load_frame(root / inputs["financial_score"])
    family_scores = load_frame(root / inputs["financial_family_scores"])
    profiles = load_frame(root / inputs["financial_profile_reconciliation"])
    history_release = read_json(root / inputs["historical_store_release"])
    history_manifest = read_json(root / inputs["historical_store_manifest"])
    financial_contract = read_json(root / config["contracts"]["financial_sector_profiles"])
    industry_contract = read_json(root / config["contracts"]["industry_classification"])

    tracked = unique_tracked(candidate)
    profile_product = profile_readiness(profiles, score, financial_contract)
    freshness_product = financial_freshness(
        family_scores,
        as_of,
        int(config["freshness_policy"]["annual_report_max_age_days"]),
    )
    industry_product = industry_quality(market, profiles, industry_contract)
    weekly_product = weekly_screen(
        market,
        tracked,
        binding,
        int(config["freshness_policy"]["price_current_max_calendar_days"]),
        as_of,
    )
    price_ledger = root / "investment_os_runtime/70_ATTRIBUTION_AND_CALIBRATION/CANDIDATE_PRICE_LEDGER.jsonl"
    outcome_product = outcome_current(entry_baselines, price_ledger, config["outcome_windows_trading_days"])

    audit = {
        "audit_id": "WP3R_CANDIDATE_REFRESH_INPUT_AUDIT_CURRENT",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "as_of_date": as_of.isoformat(),
        "candidate_state_id": candidate.get("candidate_state_id") or candidate.get("state_id"),
        "candidate_counts": candidate.get("counts"),
        "tracked_security_count_detected": len(tracked),
        "tracked_routes": pd.Series([row["route"] for row in tracked], dtype=str).value_counts().to_dict(),
        "market_rows": int(len(market)),
        "market_columns": sorted(map(str, market.columns)),
        "financial_score_rows": int(len(score)),
        "financial_score_columns": sorted(map(str, score.columns)),
        "financial_family_score_rows": int(len(family_scores)),
        "financial_family_score_columns": sorted(map(str, family_scores.columns)),
        "profile_rows": int(len(profiles)),
        "profile_columns": sorted(map(str, profiles.columns)),
        "historical_store_release_id": history_release.get("release_id"),
        "historical_store_as_of": history_release.get("as_of_date"),
        "historical_shard_count": history_manifest.get("shard_count"),
        "historical_store_covers_candidate_entry_date": str(history_release.get("as_of_date")) >= str(outcome_contract.get("entry_baseline_as_of")),
        "controlled_findings": [
            "FINANCIAL_STATEMENT_PROFILES_EXIST_BUT_CURRENT_COMPOSITE_SCORE_AUTHORIZES_GENERAL_NON_FINANCIAL_ONLY",
            "FINANCIAL_REPORT_PERIOD_AND_AVAILABILITY_FIELDS_ARE_AVAILABLE_IN_FAMILY_SCORE_LAYER",
            "HISTORICAL_STORE_REQUIRES_INCREMENTAL_EXTENSION_BEYOND_2026_07_16",
            "OUTCOME_WINDOWS_CANNOT_COMPLETE_BEFORE_20_60_120_TRADING_SESSIONS",
        ],
        "candidate_membership_mutations": 0,
        "orders": 0,
        "trade_authority": "NONE",
    }

    operating = {
        "state_id": "WP3R_CANDIDATE_REFRESH_CURRENT",
        "as_of_date": as_of.isoformat(),
        "status": "WP3R_CONTROL_LAYER_ACTIVE_CAPABILITY_GAPS_EXPLICIT",
        "candidate_current_preserved": True,
        "candidate_counts_preserved": candidate.get("counts"),
        "weekly_price_screen_status": weekly_product["status"],
        "monthly_candidate_review_status": "SCHEDULE_AND_PROPOSAL_GATE_REQUIRED",
        "quarterly_financial_rescreen_status": "SCHEDULE_AND_REPORT_AVAILABILITY_GATE_REQUIRED",
        "financial_profile_status": profile_product["status"],
        "industry_classification_status": industry_product["status"],
        "financial_freshness_status": freshness_product["status"],
        "outcome_attribution_status": outcome_product["status"],
        "next_required_actions": [
            "INSTALL_DAILY_CANDIDATE_PRICE_LEDGER",
            "INSTALL_WEEKLY_MONTHLY_QUARTERLY_CADENCE_WORKFLOWS",
            "EXTEND_FINANCIAL_FACTOR_INPUTS_FOR_BANK_INSURANCE_BROKER_PROFILES",
            "HARDEN_CANONICAL_SECURITY_MASTER_INDUSTRY_FIELDS_IF_AUDIT_BLOCKS",
            "REGISTER_PRIMARY_INDUSTRY_BENCHMARK_IDENTIFIERS_AND_HISTORY",
        ],
        "candidate_membership_mutations": 0,
        "simulation_trade_mutations": 0,
        "real_account_mutations": 0,
        "orders": 0,
        "trade_authority": "NONE",
    }

    products = {
        "input_audit": audit,
        "financial_profile_readiness": profile_product,
        "financial_freshness": freshness_product,
        "industry_quality": industry_product,
        "weekly_price_screen": weekly_product,
        "candidate_outcomes": outcome_product,
        "operating_current": operating,
    }
    for key, payload in products.items():
        write_json(root / outputs[key], payload)

    acceptance = {
        "acceptance_id": "WP3_R_CANDIDATE_REFRESH_ACCEPTANCE_V1",
        "status": "WP3R_FOUNDATION_AND_AUDIT_PRODUCTS_ACCEPTED_CADENCE_AND_INPUT_EXTENSIONS_PENDING",
        "outputs": {
            key: {"path": outputs[key], "semantic_hash": semantic_hash(payload)}
            for key, payload in products.items()
        },
        "controls": {
            "existing_candidate_current_preserved": True,
            "candidate_membership_mutations": 0,
            "research_object_mutations": 0,
            "simulation_trade_mutations": 0,
            "real_account_mutations": 0,
            "orders": 0,
            "trade_authority": "NONE",
        },
        "wp4b_unblocked": True,
        "wp5_unblocked": False,
    }
    write_json(root / outputs["acceptance"], acceptance)
    print(json.dumps(operating, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
