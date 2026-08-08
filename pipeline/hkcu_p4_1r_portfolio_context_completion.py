#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from pathlib import Path
from typing import Any, Callable

import akshare as ak
import numpy as np
import pandas as pd

PROGRAM_ID = "HKCU-P4-1R"
TRADE_AUTHORITY = "NONE"
ACCOUNTS = ("REAL", "SIMULATION")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def code5(v: Any) -> str:
    s = str(v or "").strip().upper().replace("HKEX:", "").replace(".HK", "")
    return s.zfill(5) if s.isdigit() and len(s) <= 5 else s


def finite(v: Any) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def retry(fn: Callable[[], Any], attempts: int = 3, pause: float = 1.0) -> Any:
    last: Exception | None = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as exc:  # upstream public vendor failures are recorded, not hidden
            last = exc
            if i + 1 < attempts:
                time.sleep(pause * (i + 1))
    raise RuntimeError(str(last))


def kv_lookup(df: pd.DataFrame, key: str) -> str:
    if df is None or df.empty:
        return ""
    for _, row in df.iterrows():
        vals = [str(x).strip() for x in row.tolist()]
        for i, v in enumerate(vals):
            if v == key or key in v:
                for j, candidate in enumerate(vals):
                    if j != i and candidate and candidate.lower() not in {"nan", "none"}:
                        return candidate
    return ""


def normalize_ah(df: pd.DataFrame) -> pd.DataFrame:
    aliases = {
        "h_code": ["H股代码", "H股代碼", "H代码", "H代碼"],
        "a_code": ["A股代码", "A股代碼", "A代码", "A代碼"],
        "name": ["名称", "名稱", "股票名称", "股票名稱"],
    }
    found: dict[str, str] = {}
    for target, candidates in aliases.items():
        for c in candidates:
            if c in df.columns:
                found[target] = c
                break
    if "h_code" not in found or "a_code" not in found:
        raise RuntimeError("AH_SOURCE_SCHEMA_MISSING_CODE_COLUMNS:" + ",".join(map(str, df.columns)))
    out = pd.DataFrame({
        "h_code": df[found["h_code"]].map(code5),
        "a_code": df[found["a_code"]].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(6),
        "name": df[found["name"]].astype(str) if "name" in found else "",
    })
    return out.drop_duplicates(["h_code", "a_code"]).reset_index(drop=True)


def history_frame(df: pd.DataFrame) -> pd.Series:
    if df is None or df.empty:
        return pd.Series(dtype=float)
    date_candidates = [c for c in df.columns if str(c).lower() in {"date", "trade_date", "日期", "净值日期", "淨值日期"}]
    price_candidates = [c for c in df.columns if str(c).lower() in {"adjusted_close", "adj_close", "close", "收盘", "收盤", "单位净值", "單位淨值"}]
    if not date_candidates:
        date_candidates = [c for c in df.columns if "date" in str(c).lower() or "日期" in str(c)]
    if not price_candidates:
        price_candidates = [c for c in df.columns if "close" in str(c).lower() or "收盘" in str(c) or "净值" in str(c)]
    if not date_candidates or not price_candidates:
        return pd.Series(dtype=float)
    x = pd.DataFrame({"date": pd.to_datetime(df[date_candidates[0]], errors="coerce"), "price": pd.to_numeric(df[price_candidates[0]], errors="coerce")})
    x = x.dropna().drop_duplicates("date").sort_values("date")
    x = x[x["price"] > 0]
    return pd.Series(x["price"].values, index=x["date"], dtype=float)


def load_hk_histories(path: Path) -> tuple[dict[str, pd.Series], str, str]:
    df = pd.read_parquet(path)
    sid_col = next((c for c in ["security_id", "stock_code_5d", "symbol", "code"] if c in df.columns), None)
    date_col = next((c for c in ["date", "trade_date", "market_date"] if c in df.columns), None)
    price_col = next((c for c in ["adjusted_close", "adj_close", "close", "latest_close"] if c in df.columns), None)
    if not sid_col or not date_col or not price_col:
        raise RuntimeError("FMDL5C_HISTORY_SCHEMA_UNSUPPORTED:" + ",".join(map(str, df.columns)))
    out: dict[str, pd.Series] = {}
    for key, g in df.groupby(sid_col):
        k = str(key)
        sid = k if k.startswith("HKEX:") else "HKEX:" + code5(k)
        x = pd.DataFrame({"date": pd.to_datetime(g[date_col], errors="coerce"), "price": pd.to_numeric(g[price_col], errors="coerce")}).dropna()
        x = x[x["price"] > 0].drop_duplicates("date").sort_values("date")
        out[sid] = pd.Series(x["price"].values, index=x["date"], dtype=float)
    min_date = str(pd.to_datetime(df[date_col], errors="coerce").min().date())
    max_date = str(pd.to_datetime(df[date_col], errors="coerce").max().date())
    return out, min_date, max_date


def fetch_holding_history(h: dict[str, Any], as_of: str) -> pd.Series:
    code = str(h.get("code") or "").strip()
    sid = str(h.get("security_id") or "")
    asset = str(h.get("asset_class") or "").upper()
    name = str(h.get("security_name") or "").upper()
    start = (pd.Timestamp(as_of) - pd.Timedelta(days=420)).strftime("%Y%m%d")
    end = pd.Timestamp(as_of).strftime("%Y%m%d")
    if sid.endswith(".OF") or "BOND_FUND" in asset:
        df = retry(lambda: ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势"))
        return history_frame(df)
    if "ETF" in asset or "ETF" in name or code in {"510500", "159352", "159612", "159655"}:
        df = retry(lambda: ak.fund_etf_hist_em(symbol=code, period="daily", start_date=start, end_date=end, adjust="qfq"))
        return history_frame(df)
    if sid.endswith((".SH", ".SZ")):
        df = retry(lambda: ak.stock_zh_a_hist(symbol=code, period="daily", start_date=start, end_date=end, adjust="qfq"))
        return history_frame(df)
    return pd.Series(dtype=float)


def candidate_style(sleeve: str, style_map: dict[str, str]) -> str:
    return style_map.get(sleeve, "UNRESOLVED")


def holding_context(h: dict[str, Any], account: str, industry: str) -> dict[str, Any]:
    asset = str(h.get("asset_class") or "").upper()
    name = str(h.get("security_name") or "")
    code = str(h.get("code") or "")
    pooled = "ETF" in asset or "ETF" in name.upper() or code in {"510500", "159352", "159612", "159655"}
    fixed = "BOND_FUND" in asset or str(h.get("security_id") or "").endswith(".OF")
    if fixed:
        econ, style, classification = "FIXED_INCOME", "DEFENSIVE", "ASSET_CLASS_EXACT"
    elif pooled:
        econ, style, classification = "MULTI_SECTOR_EQUITY", "BROAD_MARKET", "POOLED_EXPOSURE_EXPLICIT"
    else:
        econ, style, classification = industry or "UNRESOLVED", str(h.get("portfolio_bucket") or "UNMAPPED").upper().replace("/", "_"), "SECONDARY_INDUSTRY_CLASSIFICATION" if industry else "UNRESOLVED"
    return {
        "account": account,
        "security_id": h.get("security_id"),
        "code": code,
        "security_name": name,
        "asset_class": asset,
        "market_value": finite(h.get("market_value")) or 0.0,
        "economic_sector_industry": econ,
        "sector_classification_status": classification,
        "style_exposure": style,
        "pooled_exposure": pooled,
        "fixed_income_exposure": fixed,
        "source_portfolio_bucket": str(h.get("portfolio_bucket") or ""),
        "trade_authority": TRADE_AUTHORITY,
    }


def valuation_anchor(row: pd.Series) -> float | None:
    ey, dy = finite(row.get("earnings_yield")), finite(row.get("dividend_yield_365d"))
    if ey is not None and ey > 0:
        return ey
    if dy is not None and dy > 0:
        return dy
    return None


def risk_label(corr: float | None, down_corr: float | None, cand_vol: float | None, port_vol: float | None, policy: dict[str, Any]) -> str:
    if corr is None or down_corr is None:
        return "UNRESOLVED"
    if corr <= policy["low_correlation_threshold"] and down_corr <= policy["low_downside_correlation_threshold"]:
        if cand_vol is not None and port_vol is not None and cand_vol > 1.35 * port_vol:
            return "DIVERSIFIES_RETURN_STREAM_BUT_RAISES_RISK_BUDGET"
        return "IMPROVES_DIVERSIFICATION"
    if corr >= policy["high_correlation_threshold"] or down_corr >= policy["high_downside_correlation_threshold"]:
        return "ADDS_CORRELATED_RISK"
    return "MIXED_RISK_CONTRIBUTION"


def build(root: Path, out: Path) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    contract_path = root / "config/hkcu_p4_1r_portfolio_context_completion_contract.json"
    c = read_json(contract_path)
    a = c["authoritative_inputs"]
    candidates = pd.read_csv(root / a["candidate_current"], dtype={"stock_code_5d": str}, keep_default_na=False, encoding="utf-8-sig")
    hkcu = pd.read_csv(root / a["hkcu_current"], dtype={"stock_code_5d": str}, keep_default_na=False, encoding="utf-8-sig")
    real = read_json(root / a["real_positions_current"])
    sim = read_json(root / a["simulation_positions_current"])
    f5c = read_json(root / a["fmdl5c_decision"])
    failures: list[str] = []
    residual: list[dict[str, Any]] = []

    if len(candidates) != 70: failures.append(f"CANDIDATE_COUNT:{len(candidates)}")
    if real.get("trade_authority") != TRADE_AUTHORITY or sim.get("trade_authority") != TRADE_AUTHORITY: failures.append("ACCOUNT_AUTHORITY")
    if f5c.get("status") != "FMDL5C_PRICE_VOLUME_CORPORATE_ACTION_AND_FX_STORE_ACCEPTED": failures.append("FMDL5C_STATUS")

    hkcu_idx = hkcu.set_index("security_id", drop=False)
    try:
        ah_raw = retry(lambda: ak.stock_zh_ah_spot_em(), attempts=4, pause=2.0)
        ah = normalize_ah(ah_raw)
        ah_raw.to_csv(out / "HKCU_P4_1R_AH_SOURCE_SNAPSHOT.csv", index=False)
    except Exception as exc:
        ah = pd.DataFrame(columns=["h_code", "a_code", "name"])
        residual.append({"context_id":"EXACT_AH_IDENTITY_SOURCE","scope":"GLOBAL","reason":str(exc)})

    candidate_rows: list[dict[str, Any]] = []
    for r in candidates.sort_values("p2a_overall_rank").itertuples(index=False):
        sid, code = str(r.security_id), code5(r.stock_code_5d)
        h = hkcu_idx.loc[sid] if sid in hkcu_idx.index else pd.Series(dtype=object)
        if isinstance(h, pd.DataFrame): h = h.iloc[0]
        industry, industry_error = "", ""
        try:
            prof = retry(lambda code=code: ak.stock_hk_company_profile_em(symbol=code), attempts=3, pause=1.0)
            industry = kv_lookup(prof, "所属行业")
            if not industry:
                industry_error = "INDUSTRY_FIELD_NOT_FOUND"
        except Exception as exc:
            industry_error = str(exc)
        true_ah = str(r.ah_pair_status).startswith("TRUE_AH_PAIR")
        pairs = ah[ah["h_code"].eq(code)] if not ah.empty else ah
        a_code = str(pairs.iloc[0]["a_code"]) if len(pairs) == 1 else ""
        if true_ah and not a_code:
            residual.append({"context_id":"EXACT_AH_IDENTITY","scope":sid,"reason":"TRUE_AH_PAIR_WITHOUT_EXACT_A_CODE"})
        if not industry:
            residual.append({"context_id":"CTX_SECTOR_INDUSTRY","scope":sid,"reason":industry_error or "MISSING_INDUSTRY"})
        candidate_rows.append({
            "p2a_overall_rank": int(r.p2a_overall_rank), "security_id": sid, "stock_code_5d": code,
            "security_name": str(r.security_name), "candidate_tier": str(r.candidate_tier), "primary_sleeve": str(r.primary_sleeve),
            "portfolio_style": candidate_style(str(r.primary_sleeve), c["style_taxonomy"]),
            "economic_sector_industry": industry, "industry_evidence_status": "SECONDARY_RESEARCH_CLASSIFICATION" if industry else "MISSING",
            "true_ah_pair": true_ah, "a_share_code_6d": a_code, "ah_identity_status": "EXACT_CODE_CONFIRMED" if a_code else ("NOT_APPLICABLE" if not true_ah else "MISSING"),
            "valuation_anchor": valuation_anchor(h), "return_120d": finite(h.get("return_120d")), "max_drawdown_120d": finite(h.get("max_drawdown_120d")),
            "volatility_60d": finite(h.get("volatility_60d")), "trade_authority": TRADE_AUTHORITY,
        })
    cand = pd.DataFrame(candidate_rows).sort_values("p2a_overall_rank").reset_index(drop=True)

    holding_rows: list[dict[str, Any]] = []
    holding_hist: dict[tuple[str, str], pd.Series] = {}
    for account, state in (("REAL", real), ("SIMULATION", sim)):
        for h in state.get("holdings", []):
            sid = str(h.get("security_id") or "")
            asset = str(h.get("asset_class") or "").upper()
            name = str(h.get("security_name") or "").upper()
            pooled = "ETF" in asset or "ETF" in name or str(h.get("code") or "") in {"510500", "159352", "159612", "159655"}
            fixed = "BOND_FUND" in asset or sid.endswith(".OF")
            industry, err = "", ""
            if not pooled and not fixed and sid.endswith((".SH", ".SZ")):
                try:
                    info = retry(lambda code=str(h.get("code") or ""): ak.stock_individual_info_em(symbol=code), attempts=3, pause=1.0)
                    industry = kv_lookup(info, "行业")
                    if not industry: err = "INDUSTRY_FIELD_NOT_FOUND"
                except Exception as exc: err = str(exc)
                if not industry:
                    residual.append({"context_id":"CTX_SECTOR_INDUSTRY","scope":f"{account}:{sid}","reason":err or "MISSING_HOLDING_INDUSTRY"})
            row = holding_context(h, account, industry)
            holding_rows.append(row)
            try:
                s = fetch_holding_history(h, c["as_of_date"])
            except Exception as exc:
                s = pd.Series(dtype=float)
                row["history_error"] = str(exc)
            holding_hist[(account, sid)] = s
            row["history_observations"] = int(len(s))
            row["history_start"] = str(s.index.min().date()) if len(s) else ""
            row["history_end"] = str(s.index.max().date()) if len(s) else ""
    holdings = pd.DataFrame(holding_rows)

    try:
        hk_hist, hist_min, hist_max = load_hk_histories(root / a["fmdl5c_daily_price_volume"])
    except Exception as exc:
        hk_hist, hist_min, hist_max = {}, "", ""
        residual.append({"context_id":"CTX_MARGINAL_RISK","scope":"GLOBAL_FMDL5C","reason":str(exc)})

    # Build market-value weighted account return histories with coverage threshold.
    account_returns: dict[str, pd.Series] = {}
    account_history_coverage: dict[str, float] = {}
    for account, state in (("REAL", real), ("SIMULATION", sim)):
        hs = [x for x in state.get("holdings", []) if (finite(x.get("market_value")) or 0) > 0]
        total_mv = sum(finite(x.get("market_value")) or 0 for x in hs)
        series, weights, covered = [], [], 0.0
        for h in hs:
            sid = str(h.get("security_id") or "")
            p = holding_hist.get((account, sid), pd.Series(dtype=float))
            if len(p) >= c["risk_policy"]["minimum_common_observations"] + 1:
                mv = finite(h.get("market_value")) or 0.0
                series.append(p.pct_change().dropna().rename(sid)); weights.append(mv); covered += mv
        account_history_coverage[account] = covered / total_mv if total_mv else 0.0
        if series:
            frame = pd.concat(series, axis=1).sort_index()
            w = np.asarray(weights, dtype=float); w = w / w.sum()
            # Renormalize only among histories present on each date; no zero-return fill.
            valid = frame.notna().astype(float)
            weighted = frame.fillna(0).mul(w, axis=1).sum(axis=1)
            denom = valid.mul(w, axis=1).sum(axis=1)
            ret = (weighted / denom.replace(0, np.nan)).dropna()
            account_returns[account] = ret
        else:
            account_returns[account] = pd.Series(dtype=float)
        if account_history_coverage[account] < c["risk_policy"]["minimum_account_history_market_value_coverage"]:
            residual.append({"context_id":"CTX_MARGINAL_RISK","scope":account,"reason":f"HISTORY_MV_COVERAGE={account_history_coverage[account]:.6f}"})

    # Pareto opportunity-cost context among all 70 Candidates; no weighted score and no top-N.
    pareto_counts: dict[str, int] = {}
    comparable = cand.dropna(subset=["valuation_anchor", "return_120d", "max_drawdown_120d"]).copy()
    for r in cand.itertuples(index=False):
        va, ret, dd = finite(r.valuation_anchor), finite(r.return_120d), finite(r.max_drawdown_120d)
        if None in {va, ret, dd}:
            pareto_counts[r.security_id] = -1
            continue
        dom = comparable[(comparable["security_id"] != r.security_id) & (comparable["valuation_anchor"] >= va) & (comparable["return_120d"] >= ret) & (comparable["max_drawdown_120d"] >= dd)]
        strict = dom[(dom["valuation_anchor"] > va) | (dom["return_120d"] > ret) | (dom["max_drawdown_120d"] > dd)]
        pareto_counts[r.security_id] = int(len(strict))
    valid_counts = [v for v in pareto_counts.values() if v >= 0]
    q1, q2 = (np.quantile(valid_counts, c["opportunity_cost_policy"]["quantile_buckets"]) if valid_counts else (np.nan, np.nan))

    account_security_rows: list[dict[str, Any]] = []
    for r in cand.itertuples(index=False):
        cp = hk_hist.get(str(r.security_id), pd.Series(dtype=float))
        cr = cp.pct_change().dropna() if len(cp) else pd.Series(dtype=float)
        for account in ACCOUNTS:
            state = real if account == "REAL" else sim
            hs = state.get("holdings", [])
            direct = [str(h.get("security_id")) for h in hs if str(h.get("code") or "").zfill(5) == str(r.stock_code_5d)]
            ah_overlap = [str(h.get("security_id")) for h in hs if r.a_share_code_6d and str(h.get("code") or "").zfill(6) == r.a_share_code_6d]
            ah_status = "EXACT_AH_OVERLAP" if ah_overlap else ("EXACT_AH_NO_OVERLAP" if r.true_ah_pair and r.a_share_code_6d else "NOT_APPLICABLE")
            hctx = holdings[holdings["account"].eq(account)]
            total_mv = float(hctx["market_value"].sum()) if len(hctx) else 0.0
            same_sector_mv = float(hctx.loc[hctx["economic_sector_industry"].eq(r.economic_sector_industry), "market_value"].sum()) if r.economic_sector_industry else 0.0
            same_sector_weight = same_sector_mv / total_mv if total_mv else 0.0
            sector_state = "INCREASES_EXISTING_DIRECT_SECTOR" if same_sector_weight > 0 else "ADDS_NEW_DIRECT_SECTOR_EXPOSURE"
            style_mv = float(hctx.loc[hctx["style_exposure"].eq(r.portfolio_style), "market_value"].sum()) if r.portfolio_style else 0.0
            style_weight = style_mv / total_mv if total_mv else 0.0
            style_state = "INCREASES_EXISTING_STYLE" if style_weight > 0 else "ADDS_DISTINCT_STYLE_EXPOSURE"
            ar = account_returns.get(account, pd.Series(dtype=float))
            joined = pd.concat([cr.rename("candidate"), ar.rename("portfolio")], axis=1).dropna()
            corr = finite(joined["candidate"].corr(joined["portfolio"])) if len(joined) >= 2 else None
            downside = joined[(joined["candidate"] < 0) | (joined["portfolio"] < 0)]
            down_corr = finite(downside["candidate"].corr(downside["portfolio"])) if len(downside) >= 2 else None
            cand_vol = finite(joined["candidate"].std() * np.sqrt(252)) if len(joined) >= 2 else None
            port_vol = finite(joined["portfolio"].std() * np.sqrt(252)) if len(joined) >= 2 else None
            obs = int(len(joined))
            risk = risk_label(corr, down_corr, cand_vol, port_vol, c["risk_policy"])
            if obs < c["risk_policy"]["minimum_common_observations"] or risk == "UNRESOLVED":
                residual.append({"context_id":"CTX_MARGINAL_RISK","scope":f"{account}:{r.security_id}","reason":f"COMMON_OBS={obs};RISK={risk}"})
            pc = pareto_counts.get(r.security_id, -1)
            if pc < 0:
                opp = "UNRESOLVED"
                residual.append({"context_id":"CTX_EXPECTED_RETURN_OPPORTUNITY_COST","scope":r.security_id,"reason":"PARETO_INPUT_MISSING"})
            elif pc <= q1: opp = "LOW_RELATIVE_OPPORTUNITY_COST"
            elif pc <= q2: opp = "MODERATE_RELATIVE_OPPORTUNITY_COST"
            else: opp = "HIGH_RELATIVE_OPPORTUNITY_COST"
            account_security_rows.append({
                "p2a_overall_rank": r.p2a_overall_rank, "security_id": r.security_id, "stock_code_5d": r.stock_code_5d,
                "security_name": r.security_name, "candidate_tier": r.candidate_tier, "account": account,
                "economic_sector_industry": r.economic_sector_industry, "sector_impact_state": sector_state,
                "existing_same_sector_weight": same_sector_weight, "portfolio_style": r.portfolio_style,
                "style_impact_state": style_state, "existing_same_style_weight": style_weight,
                "direct_overlap_security_ids": "|".join(direct), "ah_overlap_security_ids": "|".join(ah_overlap), "ah_overlap_state": ah_status,
                "pooled_exposure_present": bool(hctx["pooled_exposure"].astype(bool).any()) if len(hctx) else False,
                "portfolio_history_mv_coverage": account_history_coverage.get(account, 0.0), "common_return_observations": obs,
                "candidate_portfolio_correlation": corr, "downside_correlation": down_corr, "candidate_annualized_volatility": cand_vol,
                "portfolio_annualized_volatility": port_vol, "marginal_risk_state": risk,
                "valuation_anchor": r.valuation_anchor, "return_120d": r.return_120d, "max_drawdown_120d": r.max_drawdown_120d,
                "pareto_dominator_count": pc, "opportunity_cost_state": opp,
                "expected_return_semantics": "NO_POINT_FORECAST_TRAILING_RETURN_IS_CONTEXT_ONLY",
                "context_ready": bool(r.economic_sector_industry and r.portfolio_style != "UNRESOLVED" and risk != "UNRESOLVED" and opp != "UNRESOLVED" and (not r.true_ah_pair or r.a_share_code_6d)),
                "portfolio_mutation": False, "orders_created": 0, "trade_authority": TRADE_AUTHORITY,
            })
    account_security = pd.DataFrame(account_security_rows).sort_values(["p2a_overall_rank", "account"]).reset_index(drop=True)

    # Deduplicate residual evidence gaps; structural failures remain separate.
    residual_df = pd.DataFrame(residual, columns=["context_id", "scope", "reason"]).drop_duplicates().reset_index(drop=True)
    if len(cand) != c["acceptance"]["candidate_context_count"]: failures.append("CANDIDATE_CONTEXT_COUNT")
    if len(holdings) != c["acceptance"]["account_holding_context_count"]: failures.append(f"HOLDING_CONTEXT_COUNT:{len(holdings)}")
    if len(account_security) != c["acceptance"]["account_security_context_count"]: failures.append("ACCOUNT_SECURITY_CONTEXT_COUNT")
    if account_security.duplicated(["security_id", "account"]).any(): failures.append("DUPLICATE_ACCOUNT_SECURITY_CONTEXT")

    cand_file = out / "HKCU_P4_1R_CANDIDATE_CONTEXT.csv"
    holding_file = out / "HKCU_P4_1R_ACCOUNT_HOLDING_CONTEXT.csv"
    as_file = out / "HKCU_P4_1R_ACCOUNT_SECURITY_CONTEXT.csv"
    gap_file = out / "HKCU_P4_1R_RESIDUAL_GAPS.csv"
    cand.to_csv(cand_file, index=False); holdings.to_csv(holding_file, index=False); account_security.to_csv(as_file, index=False); residual_df.to_csv(gap_file, index=False)

    status = c["acceptance"]["pass_status"] if not failures and residual_df.empty else c["acceptance"]["blocked_status"]
    next_gate = c["acceptance"]["next_gate_on_pass"] if status == c["acceptance"]["pass_status"] else None
    decision = {
        "program_id": PROGRAM_ID, "phase": c["phase"], "as_of_date": c["as_of_date"], "status": status,
        "candidate_context_count": len(cand), "account_holding_context_count": len(holdings), "account_security_context_count": len(account_security),
        "true_ah_candidate_count": int(cand["true_ah_pair"].astype(bool).sum()), "exact_ah_mapped_count": int(cand["a_share_code_6d"].astype(str).str.len().gt(0).sum()),
        "candidate_industry_coverage": float(cand["economic_sector_industry"].astype(str).str.len().gt(0).mean()),
        "context_ready_account_security_count": int(account_security["context_ready"].astype(bool).sum()),
        "residual_decision_critical_gap_count": len(residual_df), "residual_gap_counts": residual_df["context_id"].value_counts().astype(int).to_dict() if len(residual_df) else {},
        "fmdl5c_history_min_date": hist_min, "fmdl5c_history_max_date": hist_max, "account_history_mv_coverage": account_history_coverage,
        "candidate_pool_mutations": 0, "simulation_mutations": 0, "real_account_mutations": 0, "portfolio_allocations": 0, "orders_created": 0,
        "next_gate": next_gate, "trade_authority": TRADE_AUTHORITY,
    }
    quality = {
        "program_id": PROGRAM_ID, "status": "PASS" if not failures and residual_df.empty else ("PASS_STRUCTURE_WITH_RESIDUAL_CONTEXT" if not failures else "FAIL"),
        "hard_failures": sorted(set(failures)), "fuzzy_identity_matching": False, "sector_neutral_fill": False,
        "pooled_fund_single_industry_inference": False, "ticker_count_diversification_inference": False,
        "weighted_opportunity_score": False, "fixed_top_n": False, "trailing_return_called_expected_return": False,
        "portfolio_mutations": 0, "orders_created": 0, "trade_authority": TRADE_AUTHORITY,
    }
    decision_file = out / "HKCU_P4_1R_DECISION.json"; quality_file = out / "HKCU_P4_1R_QUALITY_REPORT.json"
    write_json(decision_file, decision); write_json(quality_file, quality)
    manifest = {"program_id": PROGRAM_ID, "contract_sha256": sha256_file(contract_path), "files": {}, "trade_authority": TRADE_AUTHORITY}
    for p in [cand_file, holding_file, as_file, gap_file, decision_file, quality_file]:
        manifest["files"][p.name] = {"sha256": sha256_file(p), "bytes": p.stat().st_size}
    source_snapshot = out / "HKCU_P4_1R_AH_SOURCE_SNAPSHOT.csv"
    if source_snapshot.exists(): manifest["files"][source_snapshot.name] = {"sha256": sha256_file(source_snapshot), "bytes": source_snapshot.stat().st_size}
    write_json(out / "HKCU_P4_1R_MANIFEST.json", manifest)
    if failures:
        raise SystemExit("P4_1R_BUILD_INTEGRITY_FAILED:" + "|".join(sorted(set(failures))))
    print(json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True))
    return decision


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    build(Path(args.repo_root).resolve(), Path(args.output).resolve())


if __name__ == "__main__":
    main()
