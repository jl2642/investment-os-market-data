#!/usr/bin/env python3
from __future__ import annotations

import argparse, hashlib, json, math, shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

PROGRAM_ID = "FMDL-5E"
ACCEPTED_STATUS = "FMDL5E_HONG_KONG_FACTOR_AND_SCREENING_ADAPTER_ACCEPTED"
CONTRACT_PATH = Path("config/fmdl5e_hk_factor_screening_contract.json")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def safe_divide(a: Any, b: Any, *, positive_denominator: bool = False) -> float | None:
    x, y = finite(a), finite(b)
    if x is None or y is None or y == 0 or (positive_denominator and y <= 0):
        return None
    value = x / y
    return value if math.isfinite(value) else None


def as_bool(value: Any) -> bool:
    return value is True or str(value).strip().lower() in {"1", "true", "yes", "y"}


def currency_key(value: Any) -> str:
    code = str(value or "").strip().upper()
    return "CNY" if code in {"CNY", "CNH", "RMB"} else code


def convert_to_hkd(amount: Any, currency: Any, hkd_per_usd: Any, hkd_per_cny: Any) -> float | None:
    value = finite(amount)
    if value is None:
        return None
    code = currency_key(currency)
    rate = 1.0 if code == "HKD" else finite(hkd_per_cny) if code == "CNY" else finite(hkd_per_usd) if code == "USD" else None
    return value * rate if rate and rate > 0 else None


def convert_hkd_to_currency(amount: Any, currency: Any, hkd_per_usd: Any, hkd_per_cny: Any) -> float | None:
    value = finite(amount)
    if value is None:
        return None
    code = currency_key(currency)
    rate = 1.0 if code == "HKD" else finite(hkd_per_cny) if code == "CNY" else finite(hkd_per_usd) if code == "USD" else None
    return value / rate if rate and rate > 0 else None


def window_return(prices: pd.Series, sessions: int) -> float | None:
    values = pd.to_numeric(prices, errors="coerce").dropna()
    if len(values) < sessions + 1:
        return None
    start, end = finite(values.iloc[-sessions - 1]), finite(values.iloc[-1])
    return end / start - 1 if start and start > 0 and end is not None else None


def annualized_volatility(returns: pd.Series, sessions: int) -> float | None:
    values = pd.to_numeric(returns, errors="coerce").dropna().tail(sessions)
    return finite(values.std(ddof=1) * math.sqrt(252)) if len(values) >= max(10, sessions // 2) else None


def downside_volatility(returns: pd.Series, sessions: int) -> float | None:
    values = pd.to_numeric(returns, errors="coerce").dropna().tail(sessions)
    negative = values[values < 0]
    return finite(negative.std(ddof=1) * math.sqrt(252)) if len(negative) >= 2 else None


def max_drawdown(prices: pd.Series, sessions: int) -> float | None:
    values = pd.to_numeric(prices, errors="coerce").dropna().tail(sessions)
    if len(values) < max(10, sessions // 2):
        return None
    return finite((values / values.cummax() - 1).min())


def positive_month_ratio(prices: pd.Series, dates: pd.Series) -> float | None:
    frame = pd.DataFrame({"date": pd.to_datetime(dates, errors="coerce"), "price": pd.to_numeric(prices, errors="coerce")}).dropna()
    monthly = frame.sort_values("date").set_index("date")["price"].resample("ME").last().dropna().tail(13)
    changes = monthly.pct_change(fill_method=None).dropna().tail(12)
    return float((changes > 0).mean()) if len(changes) >= 6 else None


def percentile_rank(values: pd.Series, direction: str) -> pd.Series:
    return pd.to_numeric(values, errors="coerce").rank(pct=True, method="average", ascending=direction == "HIGH")


def same_period_yoy(facts: pd.DataFrame, field_id: str, positive: bool) -> dict[str, float | None]:
    subset = facts[(facts["field_id"].astype(str) == field_id) & facts["decision_grade_eligible"].map(as_bool)].copy()
    subset["period_end"] = pd.to_datetime(subset["period_end"], errors="coerce")
    subset["normalized_value"] = pd.to_numeric(subset["normalized_value"], errors="coerce")
    result: dict[str, float | None] = {}
    for security_id, group in subset.dropna(subset=["period_end", "normalized_value"]).groupby("security_id"):
        group = group.sort_values("period_end")
        latest = group.iloc[-1]
        prior = group[(group["period_end"].dt.month == latest["period_end"].month) & (group["period_end"].dt.day == latest["period_end"].day) & (group["period_end"] < latest["period_end"])]
        if prior.empty:
            result[str(security_id)] = None
            continue
        previous = prior.iloc[-1]
        gap = (latest["period_end"] - previous["period_end"]).days
        base, current = finite(previous["normalized_value"]), finite(latest["normalized_value"])
        result[str(security_id)] = current / abs(base) - 1 if 300 <= gap <= 430 and base and current is not None and (not positive or (base > 0 and current > 0)) else None
    return result


def load_inputs(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    contract = read_json(root / CONTRACT_PATH)
    p = contract["inputs"]
    market_decision, financial_decision = read_json(root / p["market_decision"]), read_json(root / p["financial_decision"])
    errors = []
    if market_decision.get("status") != "FMDL5C_PRICE_VOLUME_CORPORATE_ACTION_AND_FX_STORE_ACCEPTED": errors.append("FMDL5C_NOT_ACCEPTED")
    if financial_decision.get("status") != "FMDL5D_HKEX_DISCLOSURE_AND_FINANCIAL_NORMALIZATION_ACCEPTED_WITH_CONTROLLED_QUARANTINE": errors.append("FMDL5D_NOT_ACCEPTED")
    if market_decision.get("release_id") != contract["source_release_ids"]["fmdl5c"]: errors.append("FMDL5C_RELEASE_MISMATCH")
    if financial_decision.get("release_id") != contract["source_release_ids"]["fmdl5d"]: errors.append("FMDL5D_RELEASE_MISMATCH")
    if market_decision.get("hard_failures") or financial_decision.get("hard_failures"): errors.append("UPSTREAM_HARD_FAILURE")
    if market_decision.get("trade_authority") != "NONE" or financial_decision.get("trade_authority") != "NONE": errors.append("UPSTREAM_TRADE_AUTHORITY")
    if errors: raise RuntimeError(";".join(errors))
    data = {
        "overlay": pd.read_csv(root / p["security_overlay"], dtype={"stock_code_5d": str}, encoding="utf-8-sig"),
        "prices": pd.read_parquet(root / p["daily_price_volume"]),
        "latest": pd.read_csv(root / p["latest_price_snapshot"], dtype={"stock_code_5d": str}, encoding="utf-8-sig"),
        "actions": pd.read_csv(root / p["corporate_actions"], dtype={"stock_code_5d": str}, encoding="utf-8-sig"),
        "fx": pd.read_csv(root / p["fx_daily"], encoding="utf-8-sig"),
        "financial": pd.read_csv(root / p["financial_current"], dtype={"stock_code_5d": str}, encoding="utf-8-sig"),
        "facts": pd.read_parquet(root / p["normalized_financial_facts"]),
        "market_decision": market_decision,
        "financial_decision": financial_decision,
        "source_registry": {"program_id": PROGRAM_ID, "source_release_ids": contract["source_release_ids"], "inputs": {k: {"path": v, "sha256": sha256_file(root / v)} for k, v in p.items()}, "trade_authority": "NONE"},
    }
    return contract, data


def prepare_fx(fx: pd.DataFrame, as_of: pd.Timestamp) -> tuple[pd.DataFrame, dict[str, float]]:
    frame = fx.copy()
    frame["observation_date"] = pd.to_datetime(frame["observation_date"], errors="coerce")
    frame = frame.dropna(subset=["observation_date"])[lambda x: x["observation_date"] <= as_of].sort_values("observation_date")
    if frame.empty: raise RuntimeError("NO_NON_FUTURE_FX")
    row = frame.iloc[-1]
    return frame, {"hkd_per_usd": float(row["hkd_per_usd"]), "hkd_per_cny": float(row["hkd_per_cny"]), "fx_date": row["observation_date"].date().isoformat()}


def market_factors(prices: pd.DataFrame, overlay: pd.DataFrame, fx: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    frame = prices.copy()
    frame["observation_date"] = pd.to_datetime(frame["observation_date"], errors="coerce")
    frame = frame.dropna(subset=["observation_date"])[lambda x: x["observation_date"] <= as_of].sort_values("observation_date")
    rates = fx[["observation_date", "hkd_per_usd", "hkd_per_cny"]].drop_duplicates("observation_date").sort_values("observation_date")
    frame = pd.merge_asof(frame, rates, on="observation_date", direction="backward")
    frame["factor_price"] = pd.to_numeric(frame["adj_close"], errors="coerce").fillna(pd.to_numeric(frame["close"], errors="coerce"))
    frame["quote_turnover"] = pd.to_numeric(frame["turnover"], errors="coerce").fillna(pd.to_numeric(frame["close"], errors="coerce") * pd.to_numeric(frame["volume"], errors="coerce"))
    frame["price_hkd"] = frame.apply(lambda r: convert_to_hkd(r["close"], r["currency"], r["hkd_per_usd"], r["hkd_per_cny"]), axis=1)
    frame["turnover_hkd"] = frame.apply(lambda r: convert_to_hkd(r["quote_turnover"], r["currency"], r["hkd_per_usd"], r["hkd_per_cny"]), axis=1)
    rows = []
    for security_id, g in frame.groupby("security_id", sort=True):
        g = g.sort_values("observation_date").drop_duplicates("observation_date", keep="last")
        price, volume = pd.to_numeric(g["factor_price"], errors="coerce"), pd.to_numeric(g["volume"], errors="coerce")
        returns, valid = price.pct_change(fill_method=None), price.dropna()
        momentum = valid.iloc[-21] / valid.iloc[-251] - 1 if len(valid) >= 251 and valid.iloc[-251] > 0 else None
        last, high = (finite(valid.iloc[-1]), finite(valid.tail(250).max())) if len(valid) else (None, None)
        r60 = returns.dropna().tail(60)
        rows.append({
            "security_id": str(security_id), "market_latest_date": g["observation_date"].max().date().isoformat(), "market_row_count": len(g),
            "history_coverage_ratio_250": min(1.0, price.notna().sum() / 250), "return_20d": window_return(price, 20), "return_60d": window_return(price, 60),
            "return_120d": window_return(price, 120), "return_250d": window_return(price, 250), "momentum_250_20d": finite(momentum),
            "distance_52w_high": last / high - 1 if last is not None and high and high > 0 else None,
            "trend_consistency_60d": float((r60 > 0).mean()) if len(r60) >= 30 else None, "positive_month_ratio_12m": positive_month_ratio(price, g["observation_date"]),
            "volatility_20d": annualized_volatility(returns, 20), "volatility_60d": annualized_volatility(returns, 60), "downside_volatility_60d": downside_volatility(returns, 60),
            "max_drawdown_120d": max_drawdown(price, 120), "worst_day_120d": finite(returns.dropna().tail(120).min()) if len(returns.dropna().tail(120)) >= 30 else None,
            "avg_turnover_hkd_20d": finite(pd.to_numeric(g["turnover_hkd"], errors="coerce").tail(20).mean()), "active_trade_ratio_60d": float((volume.tail(60).fillna(0) > 0).mean()) if len(volume.tail(60)) >= 30 else None,
            "zero_volume_days_20d": int((volume.tail(20).fillna(0) <= 0).sum()), "volume_ratio_20_60d": safe_divide(volume.tail(20).mean(), volume.tail(60).mean(), positive_denominator=True),
            "latest_price_hkd": finite(g["price_hkd"].iloc[-1]), "latest_quote_currency": str(g["currency"].iloc[-1]), "latest_close": finite(g["close"].iloc[-1]),
        })
    return overlay.merge(pd.DataFrame(rows), on="security_id", how="left", validate="one_to_one")


def financial_factors(current: pd.DataFrame, facts: pd.DataFrame) -> pd.DataFrame:
    frame = current.copy()
    for c in ["revenue", "gross_profit", "operating_profit", "net_income_parent", "total_assets", "total_equity", "total_liabilities", "cash_equivalents", "total_current_assets", "total_current_liabilities", "eps_basic"]:
        if c in frame: frame[c] = pd.to_numeric(frame[c], errors="coerce")
    revenue_yoy, income_yoy = same_period_yoy(facts, "revenue", True), same_period_yoy(facts, "net_income_parent", True)
    rows = []
    for _, r in frame.iterrows():
        sid = str(r["security_id"])
        rows.append({"security_id": sid, "financial_period_end": str(r.get("period_end") or ""), "financial_available_from": str(r.get("available_from") or ""),
            "financial_currency": currency_key(r.get("currency")), "profile": str(r.get("profile") or "UNKNOWN"), "financial_decision_grade": True,
            "roe": safe_divide(r.get("net_income_parent"), r.get("total_equity"), positive_denominator=True), "roa": safe_divide(r.get("net_income_parent"), r.get("total_assets"), positive_denominator=True),
            "gross_margin": safe_divide(r.get("gross_profit"), r.get("revenue"), positive_denominator=True), "operating_margin": safe_divide(r.get("operating_profit"), r.get("revenue"), positive_denominator=True),
            "net_margin": safe_divide(r.get("net_income_parent"), r.get("revenue"), positive_denominator=True), "cash_to_assets": safe_divide(r.get("cash_equivalents"), r.get("total_assets"), positive_denominator=True),
            "liabilities_to_assets": safe_divide(r.get("total_liabilities"), r.get("total_assets"), positive_denominator=True), "current_ratio": safe_divide(r.get("total_current_assets"), r.get("total_current_liabilities"), positive_denominator=True),
            "eps_basic": finite(r.get("eps_basic")), "revenue_yoy": revenue_yoy.get(sid), "net_income_yoy": income_yoy.get(sid)})
    return pd.DataFrame(rows)


def dividend_factors(actions: pd.DataFrame, fx: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    if actions.empty: return pd.DataFrame(columns=["security_id", "dividend_cash_hkd_365d", "corporate_action_count_365d"])
    a = actions.copy(); a["action_date"] = pd.to_datetime(a["action_date"], errors="coerce")
    a = a.dropna(subset=["action_date"])[lambda x: (x["action_date"] <= as_of) & (x["action_date"] > as_of - pd.Timedelta(days=365))]
    rates = fx[["observation_date", "hkd_per_usd", "hkd_per_cny"]].rename(columns={"observation_date": "action_date"}).sort_values("action_date")
    a = pd.merge_asof(a.sort_values("action_date"), rates, on="action_date", direction="backward")
    a["cash_hkd"] = a.apply(lambda r: convert_to_hkd(r.get("cash_amount"), r.get("currency"), r.get("hkd_per_usd"), r.get("hkd_per_cny")) if str(r.get("action_type")) == "CASH_DIVIDEND" else None, axis=1)
    return a.groupby("security_id", as_index=False).agg(dividend_cash_hkd_365d=("cash_hkd", "sum"), corporate_action_count_365d=("action_type", "count"))


def enrich(frame: pd.DataFrame, dividends: pd.DataFrame, latest_fx: dict[str, float], dictionary: list[dict[str, Any]]) -> pd.DataFrame:
    x = frame.merge(dividends, on="security_id", how="left", validate="one_to_one")
    x["dividend_cash_hkd_365d"] = pd.to_numeric(x["dividend_cash_hkd_365d"], errors="coerce").fillna(0.0)
    x["corporate_action_count_365d"] = pd.to_numeric(x["corporate_action_count_365d"], errors="coerce").fillna(0).astype(int)
    x["dividend_yield_365d"] = x.apply(lambda r: safe_divide(r["dividend_cash_hkd_365d"], r.get("latest_price_hkd"), positive_denominator=True), axis=1)
    x["price_in_financial_currency"] = x.apply(lambda r: convert_hkd_to_currency(r.get("latest_price_hkd"), r.get("financial_currency"), latest_fx["hkd_per_usd"], latest_fx["hkd_per_cny"]), axis=1)
    x["earnings_yield"] = x.apply(lambda r: safe_divide(r.get("eps_basic"), r.get("price_in_financial_currency"), positive_denominator=True) if (finite(r.get("eps_basic")) or 0) > 0 else None, axis=1)
    x["pe_ratio"] = x["earnings_yield"].map(lambda v: 1 / v if (finite(v) or 0) > 0 else None)
    for item in dictionary:
        factor = item["factor_id"]
        if factor not in x: x[factor] = np.nan
        if item["percentile_group"] == "PROFILE": x[f"{factor}__pct"] = x.groupby("profile", dropna=False)[factor].transform(lambda s: percentile_rank(s, item["direction"]))
        else: x[f"{factor}__pct"] = percentile_rank(x[factor], item["direction"])
    return x


def classify(row: pd.Series, contract: dict[str, Any], as_of: pd.Timestamp) -> tuple[str, str]:
    r = contract["investability"]
    if str(row.get("security_type")) not in r["allowed_security_types"]: return "EXCLUDED_CONTROLLED_NON_EQUITY", "SECURITY_TYPE"
    latest = pd.to_datetime(row.get("market_latest_date"), errors="coerce")
    if pd.isna(latest): return "EXCLUDED_NO_MARKET_DATA", "NO_MARKET_DATE"
    if (as_of.normalize() - latest.normalize()).days > r["maximum_price_age_calendar_days"]: return "REVIEW_ONLY", "STALE_PRICE"
    coverage, turnover, active = finite(row.get("history_coverage_ratio_250")) or 0, finite(row.get("avg_turnover_hkd_20d")) or 0, finite(row.get("active_trade_ratio_60d")) or 0
    if coverage < r["minimum_history_coverage_watch"] or turnover < r["minimum_avg_turnover_hkd_20d_watch"] or active < r["minimum_active_trade_ratio_60d"]: return "REVIEW_ONLY", "WATCH_GATE_FAIL"
    if coverage >= r["minimum_history_coverage_core"] and turnover >= r["minimum_avg_turnover_hkd_20d_core"] and (not r["core_financial_decision_grade_required"] or as_bool(row.get("financial_decision_grade"))): return "ELIGIBLE_CORE", "PASS_CORE"
    return "ELIGIBLE_WATCH", "PASS_WATCH"


def quality_grade(row: pd.Series, dictionary: list[dict[str, Any]]) -> tuple[str, str]:
    if str(row.get("security_type")) != "COMMON_EQUITY": return "BLOCKED_CONTROLLED_NON_EQUITY", "D"
    market = [d["factor_id"] for d in dictionary if d["family"].startswith("MARKET") or d["family"] == "LIQUIDITY"]
    financial = [d["factor_id"] for d in dictionary if d["family"] not in {"MARKET_TREND", "MARKET_RISK", "LIQUIDITY"}]
    mc, fc = sum(finite(row.get(f)) is not None for f in market), sum(finite(row.get(f)) is not None for f in financial)
    if mc < 8: return "PARTIAL_MARKET", "C"
    if not as_bool(row.get("financial_decision_grade")): return "PARTIAL_MARKET_ONLY", "C"
    return ("VALID", "A") if (finite(row.get("history_coverage_ratio_250")) or 0) >= .95 and fc >= 6 else ("VALID_WITH_CONTROLLED_NULLS", "B")


def evaluate_sleeve(frame: pd.DataFrame, sleeve_id: str, sleeve: dict[str, Any]) -> pd.DataFrame:
    allowed = {"ELIGIBLE_CORE"} if sleeve["route"] == "CORE" else {"ELIGIBLE_CORE", "ELIGIBLE_WATCH"}
    x = frame[frame["investability_status"].isin(allowed)].copy(); weights = sleeve["weights"]
    if abs(sum(weights.values()) - 1) > 1e-9: raise RuntimeError(f"SLEEVE_WEIGHT_SUM:{sleeve_id}")
    pct_cols = [f"{f}__pct" for f in weights]
    x["component_count"] = x[pct_cols].notna().sum(axis=1)
    x["component_weight"] = sum(np.where(x[f"{f}__pct"].notna(), w, 0.0) for f, w in weights.items())
    x = x[x["component_count"] >= sleeve["minimum_components"]].copy()
    if x.empty: return x
    weighted = sum(pd.to_numeric(x[f"{f}__pct"], errors="coerce").fillna(0) * w for f, w in weights.items())
    x["sleeve_score"] = weighted / x["component_weight"] * (0.85 + 0.15 * x["component_weight"])
    x = x[x["sleeve_score"] >= sleeve["minimum_score"]].sort_values(["sleeve_score", "avg_turnover_hkd_20d", "security_id"], ascending=[False, False, True]).head(sleeve["maximum_candidates"])
    x["sleeve_rank"] = range(1, len(x) + 1); x["sleeve_population"] = len(x); x["sleeve_rank_percentile"] = (len(x) - x["sleeve_rank"] + 1) / max(1, len(x)); x["sleeve_id"] = sleeve_id; x["sleeve_route"] = sleeve["route"]
    x["component_score_json"] = x.apply(lambda r: json.dumps({f: {"percentile": finite(r.get(f"{f}__pct")), "weight": w} for f, w in weights.items() if finite(r.get(f"{f}__pct")) is not None}, sort_keys=True), axis=1)
    keep = ["as_of_date", "security_id", "stock_code_5d", "official_security_name_en", "official_issuer_name_en", "profile", "investability_status", "factor_record_quality", "confidence_grade", "sleeve_id", "sleeve_route", "sleeve_rank", "sleeve_population", "sleeve_rank_percentile", "sleeve_score", "component_count", "component_weight", "component_score_json", "avg_turnover_hkd_20d", "return_20d", "return_60d", "return_120d", "dividend_yield_365d", "earnings_yield", "roe", "wvr_flag", "h_share_flag", "a_share_class_exists", "dual_counter_flag", "biotech_chapter18a_flag", "secondary_listing_flag", "corporate_action_count_365d"]
    return x[[c for c in keep if c in x]]


def base_score(frame: pd.DataFrame) -> pd.Series:
    factors = ["return_60d", "return_120d", "distance_52w_high", "volatility_60d", "avg_turnover_hkd_20d", "roe", "operating_margin", "earnings_yield", "dividend_yield_365d", "max_drawdown_120d"]
    columns = [f"{f}__pct" for f in factors]
    return frame[columns].mean(axis=1, skipna=True).where(frame[columns].notna().sum(axis=1) >= 5)


def build_longlist(frame: pd.DataFrame, detail: pd.DataFrame, contract: dict[str, Any]) -> pd.DataFrame:
    funnel = contract["funnel"]; eligible = frame[frame["investability_status"].isin({"ELIGIBLE_CORE", "ELIGIBLE_WATCH"})].copy(); eligible["baseline_score"] = base_score(eligible)
    rows = []
    if not detail.empty:
        for sid, g in detail.groupby("security_id"):
            g = g.sort_values(["sleeve_rank_percentile", "sleeve_score", "sleeve_id"], ascending=[False, False, True]); best = g.iloc[0]; sleeves = g["sleeve_id"].astype(str).tolist(); bonus = min(funnel["cross_sleeve_bonus_maximum"], max(0, len(sleeves)-1) * funnel["cross_sleeve_bonus_per_extra_sleeve"])
            rows.append({"security_id": sid, "primary_sleeve": best["sleeve_id"], "sleeves": "|".join(sleeves), "sleeve_count": len(sleeves), "best_sleeve_score": best["sleeve_score"], "normalized_primary_score": best["sleeve_rank_percentile"], "cross_sleeve_bonus": bonus, "aggregate_score": best["sleeve_rank_percentile"] + .25 * best["sleeve_score"] + bonus})
    ranked = pd.DataFrame(rows).merge(eligible, on="security_id", how="left", validate="one_to_one") if rows else eligible.iloc[0:0].copy()
    used = set(ranked["security_id"]) if not ranked.empty else set(); fill = eligible[~eligible["security_id"].isin(used) & eligible["baseline_score"].notna()].copy()
    if not fill.empty:
        fill["primary_sleeve"] = fill["sleeves"] = "BALANCED_FALLBACK"; fill["sleeve_count"] = 1; fill["best_sleeve_score"] = fill["baseline_score"]; fill["normalized_primary_score"] = percentile_rank(fill["baseline_score"], "HIGH"); fill["cross_sleeve_bonus"] = 0.0; fill["aggregate_score"] = fill["normalized_primary_score"] + .2 * fill["baseline_score"]; ranked = pd.concat([ranked, fill], ignore_index=True, sort=False)
    ranked = ranked.sort_values(["aggregate_score", "normalized_primary_score", "best_sleeve_score", "avg_turnover_hkd_20d", "security_id"], ascending=[False, False, False, False, True]).drop_duplicates("security_id").head(funnel["longlist_count"]).reset_index(drop=True)
    ranked["overall_rank"] = range(1, len(ranked)+1); a = funnel["priority_bucket_counts"]["A_IMMEDIATE_RESEARCH"]; b = a + funnel["priority_bucket_counts"]["B_WATCH_OR_TRIGGER"]
    ranked["research_priority"] = ranked["overall_rank"].map(lambda r: "A_IMMEDIATE_RESEARCH" if r <= a else "B_WATCH_OR_TRIGGER" if r <= b else "C_SCREEN_FLAG_ONLY"); ranked["next_workflow"] = funnel["next_workflow"]; ranked["authority"] = contract["authority"]; ranked["trade_authority"] = "NONE"
    order = ["as_of_date", "overall_rank", "research_priority", "security_id", "stock_code_5d", "official_security_name_en", "official_issuer_name_en", "primary_sleeve", "sleeves", "sleeve_count", "aggregate_score", "normalized_primary_score", "best_sleeve_score", "cross_sleeve_bonus", "investability_status", "factor_record_quality", "confidence_grade", "profile", "latest_close", "latest_quote_currency", "avg_turnover_hkd_20d", "return_20d", "return_60d", "return_120d", "return_250d", "volatility_60d", "max_drawdown_120d", "roe", "roa", "operating_margin", "revenue_yoy", "net_income_yoy", "earnings_yield", "pe_ratio", "dividend_yield_365d", "corporate_action_count_365d", "a_share_class_exists", "h_share_flag", "wvr_flag", "dual_counter_flag", "secondary_listing_flag", "biotech_chapter18a_flag", "next_workflow", "authority", "trade_authority"]
    return ranked[[c for c in order if c in ranked]]


def case_coverage(frame: pd.DataFrame, contract: dict[str, Any]) -> pd.DataFrame:
    x = frame[frame["investability_status"].isin({"ELIGIBLE_CORE", "ELIGIBLE_WATCH"})].copy(); x["baseline_score"] = base_score(x); limit = contract["funnel"]["case_coverage_per_type"]
    cases = {"A_SHARE_CLASS": x["a_share_class_exists"].map(as_bool), "H_SHARE": x["h_share_flag"].map(as_bool), "WVR": x["wvr_flag"].map(as_bool), "DUAL_COUNTER": x["dual_counter_flag"].map(as_bool), "SECONDARY_LISTING": x["secondary_listing_flag"].map(as_bool), "CHAPTER_18A": x["biotech_chapter18a_flag"].map(as_bool), "HIGH_DIVIDEND": pd.to_numeric(x["dividend_yield_365d"], errors="coerce") >= .04, "CORPORATE_ACTION": x["corporate_action_count_365d"] > 0}
    parts = []
    for name, mask in cases.items():
        s = x[mask].sort_values(["baseline_score", "avg_turnover_hkd_20d", "security_id"], ascending=[False, False, True]).head(limit).copy()
        if not s.empty: s["case_type"] = name; s["case_rank"] = range(1, len(s)+1); parts.append(s)
    if not parts: return pd.DataFrame(columns=["case_type", "case_rank", "security_id"])
    out = pd.concat(parts, ignore_index=True); keep = ["as_of_date", "case_type", "case_rank", "security_id", "stock_code_5d", "official_security_name_en", "official_issuer_name_en", "investability_status", "baseline_score", "dividend_yield_365d", "corporate_action_count_365d", "a_share_class_exists", "h_share_flag", "wvr_flag", "dual_counter_flag", "secondary_listing_flag", "biotech_chapter18a_flag"]
    return out[[c for c in keep if c in out]]


def factor_detail(frame: pd.DataFrame, dictionary: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame([{"as_of_date": r["as_of_date"], "security_id": r["security_id"], "stock_code_5d": r["stock_code_5d"], "factor_id": d["factor_id"], "factor_family": d["family"], "direction": d["direction"], "percentile_group": d["percentile_group"], "factor_value": finite(r.get(d["factor_id"])), "factor_percentile": finite(r.get(f"{d['factor_id']}__pct")), "available": finite(r.get(d["factor_id"])) is not None, "factor_record_quality": r["factor_record_quality"], "trade_authority": "NONE"} for _, r in frame.iterrows() for d in dictionary])


def quality(frame: pd.DataFrame, detail: pd.DataFrame, longlist: pd.DataFrame, cases: pd.DataFrame, contract: dict[str, Any], data: dict[str, Any], as_of: pd.Timestamp) -> dict[str, Any]:
    a = contract["acceptance"]; dictionary = contract["factor_dictionary"]; factor_cols = [d["factor_id"] for d in dictionary]; market_cols = [d["factor_id"] for d in dictionary if d["family"].startswith("MARKET") or d["family"] == "LIQUIDITY"]
    invalid = int(np.isinf(frame[factor_cols].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)).sum()); market_count = int((frame[market_cols].notna().sum(axis=1) >= 8).sum()); financial_count = int(frame["financial_decision_grade"].map(as_bool).sum()); equity_count = int((frame["security_type"] == "COMMON_EQUITY").sum())
    future_price = int((pd.to_datetime(data["prices"]["observation_date"], errors="coerce") > as_of).sum()); future_action = int((pd.to_datetime(data["actions"]["action_date"], errors="coerce") > as_of).sum()) if not data["actions"].empty else 0
    available = pd.to_datetime(data["financial"]["available_from"], errors="coerce", utc=True); cutoff = (pd.Timestamp(as_of.date()).tz_localize("Asia/Hong_Kong") + pd.Timedelta(hours=23, minutes=59)).tz_convert("UTC"); future_financial = int((available > cutoff).sum())
    priorities = longlist["research_priority"].value_counts().astype(int).to_dict() if not longlist.empty else {}; sleeves = longlist["primary_sleeve"].value_counts().astype(int).to_dict() if not longlist.empty else {}; case_counts = cases["case_type"].value_counts().astype(int).to_dict() if not cases.empty else {}
    failures = []
    if len(frame) != a["source_security_count"]: failures.append("SOURCE_SECURITY_COUNT")
    if equity_count < a["minimum_equity_security_count"]: failures.append("EQUITY_SECURITY_COUNT")
    if market_count < a["minimum_market_factor_security_count"]: failures.append("MARKET_FACTOR_COVERAGE")
    if financial_count < a["minimum_decision_grade_financial_security_count"]: failures.append("FINANCIAL_COVERAGE")
    if len(longlist) != a["required_longlist_count"]: failures.append("LONGLIST_COUNT")
    if longlist["security_id"].duplicated().sum() > a["maximum_duplicate_security_count"]: failures.append("DUPLICATE_LONGLIST")
    if priorities != a["required_priority_bucket_counts"]: failures.append("PRIORITY_BUCKET_COUNTS")
    if len({s for s in sleeves if s != "BALANCED_FALLBACK"}) < a["minimum_distinct_primary_sleeves"]: failures.append("SLEEVE_DIVERSITY")
    if future_price + future_action + future_financial > a["maximum_future_input_row_count"]: failures.append("FUTURE_INPUT")
    if invalid > a["maximum_invalid_numeric_factor_count"]: failures.append("INVALID_NUMERIC")
    metrics = {"source_security_count": len(frame), "equity_security_count": equity_count, "controlled_non_equity_count": len(frame)-equity_count, "market_factor_security_count": market_count, "decision_grade_financial_security_count": financial_count, "factor_count": len(dictionary), "factor_detail_row_count": len(frame)*len(dictionary), "eligible_core_count": int((frame["investability_status"] == "ELIGIBLE_CORE").sum()), "eligible_watch_count": int((frame["investability_status"] == "ELIGIBLE_WATCH").sum()), "longlist_count": len(longlist), "priority_bucket_counts": priorities, "primary_sleeve_counts": sleeves, "sleeve_hit_counts": detail["sleeve_id"].value_counts().astype(int).to_dict() if not detail.empty else {}, "case_coverage_counts": case_counts, "future_price_row_count": future_price, "future_action_row_count": future_action, "future_financial_row_count": future_financial, "invalid_numeric_factor_count": invalid, "duplicate_factor_security_count": int(frame["security_id"].duplicated().sum()), "duplicate_longlist_security_count": int(longlist["security_id"].duplicated().sum()) if not longlist.empty else 0}
    return {"program_id": PROGRAM_ID, "status": "PASS" if not failures else "FAIL", "hard_failures": failures, "controlled_warnings": [], "as_of_date": as_of.date().isoformat(), "metrics": metrics, "candidate_pool_mutation_count": 0, "simulation_mutation_count": 0, "real_account_mutation_count": 0, "order_generation_count": 0, "trade_authority": "NONE"}


def run(root: Path, output: Path) -> dict[str, Any]:
    contract, data = load_inputs(root)
    if output.exists(): shutil.rmtree(output)
    output.mkdir(parents=True)
    dates = pd.to_datetime(data["prices"]["observation_date"], errors="coerce"); as_of = dates.max()
    if pd.isna(as_of): raise RuntimeError("NO_PRICE_AS_OF")
    fx, latest_fx = prepare_fx(data["fx"], as_of)
    frame = market_factors(data["prices"], data["overlay"], fx, as_of).merge(financial_factors(data["financial"], data["facts"]), on="security_id", how="left", validate="one_to_one")
    frame["financial_decision_grade"] = frame["financial_decision_grade"].fillna(False); frame["profile"] = frame["profile"].fillna("CONTROLLED_NON_FINANCIAL")
    frame = enrich(frame, dividend_factors(data["actions"], fx, as_of), latest_fx, contract["factor_dictionary"]); frame["as_of_date"] = as_of.date().isoformat()
    classes = frame.apply(lambda r: classify(r, contract, as_of), axis=1); frame["investability_status"] = [x[0] for x in classes]; frame["investability_reason"] = [x[1] for x in classes]
    grades = frame.apply(lambda r: quality_grade(r, contract["factor_dictionary"]), axis=1); frame["factor_record_quality"] = [x[0] for x in grades]; frame["confidence_grade"] = [x[1] for x in grades]; frame["trade_authority"] = "NONE"
    parts = [evaluate_sleeve(frame, sid, sleeve) for sid, sleeve in contract["sleeves"].items()]; sleeve_detail = pd.concat([p for p in parts if not p.empty], ignore_index=True) if any(not p.empty for p in parts) else pd.DataFrame()
    longlist = build_longlist(frame, sleeve_detail, contract); cases = case_coverage(frame, contract); detail = factor_detail(frame, contract["factor_dictionary"]); q = quality(frame, sleeve_detail, longlist, cases, contract, data, as_of)
    funnel = pd.DataFrame([{"stage":"SOURCE_SECURITIES","count":len(frame)}, {"stage":"COMMON_EQUITIES","count":int((frame["security_type"]=="COMMON_EQUITY").sum())}, {"stage":"ELIGIBLE_CORE","count":int((frame["investability_status"]=="ELIGIBLE_CORE").sum())}, {"stage":"ELIGIBLE_WATCH","count":int((frame["investability_status"]=="ELIGIBLE_WATCH").sum())}, {"stage":"SLEEVE_HITS","count":len(sleeve_detail)}, {"stage":"DISTINCT_SLEEVE_SECURITIES","count":int(sleeve_detail["security_id"].nunique()) if not sleeve_detail.empty else 0}, {"stage":"RESEARCH_LONGLIST","count":len(longlist)}])
    dictionary = {"program_id": PROGRAM_ID, "contract_version": contract["contract_version"], "as_of_date": as_of.date().isoformat(), "factor_policy": contract["factor_policy"], "factors": contract["factor_dictionary"], "trade_authority": "NONE"}; data["source_registry"]["as_of_date"] = as_of.date().isoformat(); data["source_registry"]["latest_fx"] = latest_fx
    outputs = {"FMDL5E_FACTOR_DICTIONARY.json": dictionary, "FMDL5E_SOURCE_REGISTRY.json": data["source_registry"], "FMDL5E_QUALITY_REPORT.json": q}
    for name, payload in outputs.items(): (output/name).write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    frame.to_parquet(output/"FMDL5E_FACTOR_TABLE.parquet", index=False); detail.to_parquet(output/"FMDL5E_FACTOR_DETAIL.parquet", index=False); frame.to_csv(output/"FMDL5E_SCREENING_UNIVERSE.csv", index=False, encoding="utf-8-sig"); sleeve_detail.to_csv(output/"FMDL5E_SLEEVE_DETAIL.csv", index=False, encoding="utf-8-sig"); longlist.to_csv(output/"FMDL5E_RESEARCH_LONGLIST.csv", index=False, encoding="utf-8-sig"); cases.to_csv(output/"FMDL5E_CASE_COVERAGE.csv", index=False, encoding="utf-8-sig"); funnel.to_csv(output/"FMDL5E_FUNNEL_COUNTS.csv", index=False, encoding="utf-8-sig")
    base = [p for p in output.iterdir() if p.is_file()]; base_hashes = {p.name:{"sha256":sha256_file(p),"size_bytes":p.stat().st_size} for p in base}; canonical = stable_hash(base_hashes); release_id = f"FMDL5E_{as_of.strftime('%Y%m%d')}_{canonical[:12]}"
    decision = {"program_id":PROGRAM_ID,"status":ACCEPTED_STATUS if not q["hard_failures"] else "FMDL5E_REJECTED","release_id":release_id,"release_sequence":contract["release_sequence"],"source_release_ids":contract["source_release_ids"],"as_of_date":as_of.date().isoformat(),"generated_at_utc":datetime.now(timezone.utc).isoformat(timespec="seconds"),"canonical_sha256":canonical,"hard_failures":q["hard_failures"],"controlled_warnings":q["controlled_warnings"],"metrics":q["metrics"],"candidate_pool_mutation_count":0,"simulation_mutation_count":0,"real_account_mutation_count":0,"order_generation_count":0,"authority":contract["authority"],"trade_authority":"NONE","next_gate":contract["next_gate"]}
    (output/"FMDL5E_DECISION.json").write_text(json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True)+"\n", encoding="utf-8"); files = [p for p in output.iterdir() if p.is_file()]; manifest = {"program_id":PROGRAM_ID,"release_id":release_id,"release_sequence":contract["release_sequence"],"source_release_ids":contract["source_release_ids"],"as_of_date":as_of.date().isoformat(),"canonical_sha256":canonical,"files":{p.name:{"sha256":sha256_file(p),"size_bytes":p.stat().st_size} for p in files}}; (output/"FMDL5E_MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    print(json.dumps(decision, ensure_ascii=False, indent=2)); return decision


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--repo-root", default="."); parser.add_argument("--output", default="outputs/fmdl5e/candidate"); args = parser.parse_args(); root = Path(args.repo_root).resolve(); decision = run(root, root/args.output); return 0 if decision["status"] == ACCEPTED_STATUS else 1


if __name__ == "__main__": raise SystemExit(main())
