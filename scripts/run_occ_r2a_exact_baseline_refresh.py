from __future__ import annotations

import argparse
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from scripts.fmdl3dc_core import AUTHORITY, TRADE_AUTHORITY, VALID_STATES, stable_hash

METRIC_DENOMINATORS = {
    "VAL_PE_TTM": ("net_income_parent_ttm",),
    "VAL_EARNINGS_YIELD_TTM": ("net_income_parent_ttm",),
    "VAL_PB": ("parent_equity",),
    "VAL_PS_TTM": ("revenue_ttm",),
    "VAL_FCF_YIELD_TTM": ("cfo_ttm", "capex_ttm"),
    "VAL_EV_SALES_TTM": (
        "short_term_debt", "long_term_debt", "bonds_payable",
        "cash_equivalents", "revenue_ttm",
    ),
    "VAL_EV_OPERATING_INCOME_TTM": (
        "short_term_debt", "long_term_debt", "bonds_payable",
        "cash_equivalents", "operating_income_ttm",
    ),
}


def _json_map(value: object) -> dict:
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(str(value or "{}"))
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _positive(value: object) -> float | None:
    number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(number) or float(number) <= 0:
        return None
    return float(number)


def _metric_value(metric_id: str, market_cap: float, values: dict) -> float | None:
    def num(key: str) -> float | None:
        value = pd.to_numeric(pd.Series([values.get(key)]), errors="coerce").iloc[0]
        return None if pd.isna(value) else float(value)

    if metric_id in {"VAL_PE_TTM", "VAL_EARNINGS_YIELD_TTM"}:
        earnings = num("net_income_parent_ttm")
        if earnings is None or earnings <= 0:
            return None
        return market_cap / earnings if metric_id == "VAL_PE_TTM" else earnings / market_cap
    if metric_id == "VAL_PB":
        equity = num("parent_equity")
        return market_cap / equity if equity is not None and equity > 0 else None
    if metric_id == "VAL_PS_TTM":
        revenue = num("revenue_ttm")
        return market_cap / revenue if revenue is not None and revenue > 0 else None
    if metric_id == "VAL_FCF_YIELD_TTM":
        cfo, capex = num("cfo_ttm"), num("capex_ttm")
        return (cfo + capex) / market_cap if cfo is not None and capex is not None else None
    if metric_id in {"VAL_EV_SALES_TTM", "VAL_EV_OPERATING_INCOME_TTM"}:
        required = ["short_term_debt", "long_term_debt", "bonds_payable", "cash_equivalents"]
        debt = [num(key) for key in required]
        if any(value is None for value in debt):
            return None
        enterprise_value = market_cap + debt[0] + debt[1] + debt[2] - debt[3]
        if enterprise_value <= 0:
            return None
        denom_key = "revenue_ttm" if metric_id == "VAL_EV_SALES_TTM" else "operating_income_ttm"
        denominator = num(denom_key)
        return enterprise_value / denominator if denominator is not None and denominator > 0 else None
    raise ValueError(f"UNSUPPORTED_METRIC:{metric_id}")


def refresh_exact_detail(
    exact_detail: pd.DataFrame,
    base_market: pd.DataFrame,
    target_market: pd.DataFrame,
    *,
    target_date: str,
    target_market_release_id: str,
    exact_release_id: str,
) -> tuple[pd.DataFrame, dict]:
    base = base_market[["symbol", "close"]].copy()
    target = target_market[["symbol", "close"]].copy()
    base["symbol"] = base["symbol"].astype(str)
    target["symbol"] = target["symbol"].astype(str)
    if base["symbol"].duplicated().any() or target["symbol"].duplicated().any():
        raise RuntimeError("DUPLICATE_MARKET_SYMBOL")
    base_close = dict(zip(base["symbol"], pd.to_numeric(base["close"], errors="coerce")))
    target_close = dict(zip(target["symbol"], pd.to_numeric(target["close"], errors="coerce")))

    cutoff = pd.Timestamp(f"{target_date} 15:00:00", tz=ZoneInfo("Asia/Shanghai")).isoformat()
    rows = []
    refreshed_symbols: set[str] = set()
    quarantined_symbols: set[str] = set()

    for original in exact_detail.to_dict("records"):
        row = dict(original)
        symbol = str(row.get("symbol") or "")
        metric_id = str(row.get("metric_id") or "")
        base_px = _positive(base_close.get(symbol))
        target_px = _positive(target_close.get(symbol))
        base_cap = _positive(row.get("total_market_cap_cny"))
        if base_px is None or target_px is None or base_cap is None:
            row["market_as_of_date"] = target_date
            row["market_cutoff_timestamp"] = cutoff
            row["metric_value"] = None
            row["quality_state"] = "CONTROLLED_CAPITALIZATION_QUARANTINE"
            row["decision_grade"] = False
            row["warning_codes"] = "MARKET_PRICE_UNAVAILABLE_FOR_EXACT_BASELINE_REFRESH"
            quarantined_symbols.add(symbol)
        else:
            ratio = target_px / base_px
            target_cap = base_cap * ratio
            values = _json_map(row.get("input_values_json"))
            states = _json_map(row.get("input_states_json"))
            available = _json_map(row.get("input_available_from_json"))
            values["total_market_cap_cny"] = target_cap
            states["total_market_cap_cny"] = "VALID"
            available["total_market_cap_cny"] = cutoff
            row["market_as_of_date"] = target_date
            row["market_cutoff_timestamp"] = cutoff
            row["total_market_cap_cny"] = target_cap
            row["input_values_json"] = json.dumps(values, ensure_ascii=False, sort_keys=True, default=str)
            row["input_states_json"] = json.dumps(states, ensure_ascii=False, sort_keys=True, default=str)
            row["input_available_from_json"] = json.dumps(available, ensure_ascii=False, sort_keys=True, default=str)
            row["capitalization_lineage_id"] = stable_hash({
                "baseline_capitalization_lineage_id": original.get("capitalization_lineage_id"),
                "exact_release_id": exact_release_id,
                "target_market_release_id": target_market_release_id,
                "target_date": target_date,
                "symbol": symbol,
            })
            if str(original.get("quality_state")) in VALID_STATES:
                value = _metric_value(metric_id, target_cap, values)
                if value is None:
                    row["metric_value"] = None
                    row["decision_grade"] = False
                    row["quality_state"] = str(original.get("quality_state") or "MISSING_REQUIRED_INPUT")
                else:
                    row["metric_value"] = float(value)
                    row["decision_grade"] = True
            refreshed_symbols.add(symbol)

        row["metric_lineage_id"] = stable_hash({
            "symbol": symbol,
            "metric_id": metric_id,
            "market_as_of_date": target_date,
            "capitalization_lineage_id": row.get("capitalization_lineage_id"),
            "denominator_period_end": row.get("denominator_period_end"),
            "denominator_available_from": row.get("denominator_available_from"),
            "input_fact_ids_json": row.get("input_fact_ids_json"),
            "quality_state": row.get("quality_state"),
            "valuation_version": row.get("valuation_version"),
            "exact_baseline_release_id": exact_release_id,
        })
        row["authority"] = AUTHORITY
        row["trade_authority"] = TRADE_AUTHORITY
        rows.append(row)

    out = pd.DataFrame(rows).sort_values(["symbol", "metric_id"]).reset_index(drop=True)
    universe = int(out["symbol"].nunique()) if len(out) else 0
    metrics = {
        "universe_symbol_count": universe,
        "refreshed_symbol_count": len(refreshed_symbols),
        "quarantined_symbol_count": len(quarantined_symbols),
        "market_coverage_ratio": (len(refreshed_symbols) / universe) if universe else 0.0,
        "detail_row_count": int(len(out)),
        "decision_grade_metric_count": int(out["decision_grade"].fillna(False).astype(bool).sum()),
    }
    return out, metrics


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exact-detail", required=True)
    parser.add_argument("--exact-release", required=True)
    parser.add_argument("--base-market", required=True)
    parser.add_argument("--target-market", required=True)
    parser.add_argument("--target-market-release", required=True)
    parser.add_argument("--exact-baseline-receipt", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    exact_release = json.loads(Path(args.exact_release).read_text(encoding="utf-8"))
    target_release = json.loads(Path(args.target_market_release).read_text(encoding="utf-8"))
    receipt = json.loads(Path(args.exact_baseline_receipt).read_text(encoding="utf-8"))
    if receipt.get("qc_status") != "PASS_EXACT_VALUATION_REBUILT":
        raise SystemExit("EXACT_BASELINE_RECEIPT_NOT_EXACT")
    if receipt.get("status") != "PASS" or receipt.get("trade_authority") != "NONE":
        raise SystemExit("EXACT_BASELINE_RECEIPT_NOT_ACCEPTED")
    if exact_release.get("status") != "FMDL3DC_VALUATION_ENGINE_CURRENT_ACCEPTED":
        raise SystemExit("EXACT_BASELINE_RELEASE_NOT_ACCEPTED")

    base_date = str(exact_release.get("source_releases", {}).get("market_as_of_date") or "")
    target_date = str(target_release.get("as_of_date") or "")
    if not base_date or not target_date or target_date < base_date:
        raise SystemExit(f"INVALID_MARKET_WATERMARK:{base_date}:{target_date}")

    detail = pd.read_parquet(args.exact_detail)
    base_market = pd.read_csv(args.base_market, encoding="utf-8-sig")
    target_market = pd.read_csv(args.target_market, encoding="utf-8-sig")
    refreshed, metrics = refresh_exact_detail(
        detail, base_market, target_market,
        target_date=target_date,
        target_market_release_id=str(target_release.get("run_id") or ""),
        exact_release_id=str(exact_release.get("release_id") or ""),
    )
    hard_failures = []
    if metrics["market_coverage_ratio"] < 0.99:
        hard_failures.append("MARKET_COVERAGE_BELOW_0_99")
    if set(refreshed["trade_authority"].astype(str)) != {"NONE"}:
        hard_failures.append("TRADE_AUTHORITY_PRESENT")

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    refreshed.to_parquet(out / "FMDL3DC_MARKET_REFRESH_DETAIL.parquet", index=False, compression="zstd")
    release = {
        "release_version": "1.0.0",
        "release_id": f"OCC_R2A_EXACT_BASELINE_MARKET_REFRESH_{target_date.replace('-', '')}",
        "status": "FMDL3DC_VALUATION_ENGINE_CURRENT_ACCEPTED",
        "qc_status": "PASS_MARKET_VALUATION_REFRESH_EXACT_DENOMINATOR_LKG" if not hard_failures else "FAIL",
        "source_releases": {
            **dict(exact_release.get("source_releases") or {}),
            "market_source_release_id": target_release.get("run_id"),
            "market_as_of_date": target_date,
            "exact_baseline_valuation_release_id": exact_release.get("release_id"),
            "exact_baseline_market_as_of_date": base_date,
        },
        "metrics": {
            **metrics,
            "exact_baseline_source_branch": receipt.get("source_branch"),
            "exact_baseline_source_commit": receipt.get("source_commit_sha"),
            "exact_baseline_financial_event_propagation": "COMPLETE",
        },
        "controlled_limitations": [
            "FINANCIAL_DENOMINATORS_ARE_LKG_FROM_LATEST_ACCEPTED_EXACT_R2B2_BASELINE",
            "MARKET_CAPITALIZATION_IS_PROPAGATED_FROM_EXACT_BASELINE_BY_COMPLETED_CLOSE_PRICE_RATIO",
            "SHARE_COUNT_CHANGES_AFTER_EXACT_BASELINE_REQUIRE_NEXT_EXACT_R2B2_REBUILD",
            "NO_RECOMMENDATION_PORTFOLIO_ACTION_OR_TRADE_AUTHORITY",
        ],
        "authority": AUTHORITY,
        "trade_authority": TRADE_AUTHORITY,
    }
    (out / "FMDL3DC_MARKET_REFRESH_RELEASE.json").write_text(
        json.dumps(release, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    decision = {
        "schema_version": "2.0.0",
        "release_id": release["release_id"],
        "status": "PASS" if not hard_failures else "FAIL",
        "qc_status": release["qc_status"],
        "market_as_of_date": target_date,
        "exact_baseline_market_as_of_date": base_date,
        "exact_baseline": {
            "source_branch": receipt.get("source_branch"),
            "source_commit_sha": receipt.get("source_commit_sha"),
            "valuation_release_id": exact_release.get("release_id"),
        },
        "financial_denominator": {
            "status": "EXACT_LKG_FROM_ACCEPTED_R2B2_BASELINE",
            "financial_factor_release_id": exact_release.get("source_releases", {}).get("factor_engine_release_id"),
            "financial_event_propagation": "COMPLETE_AS_OF_EXACT_BASELINE",
        },
        "universe": {
            **metrics,
            "valuation_context_row_count": metrics["universe_symbol_count"],
            "coverage_scope": "LATEST_ACCEPTED_EXACT_R2B2_UNIVERSE",
        },
        "hard_failures": hard_failures,
        "authority": AUTHORITY,
        "trade_authority": TRADE_AUTHORITY,
    }
    validation = {
        "schema_version": "2.0.0",
        "status": "PASS" if not hard_failures else "FAIL",
        "hard_failures": hard_failures,
        "market_as_of_date": target_date,
        "exact_baseline_market_as_of_date": base_date,
        "market_coverage_ratio": metrics["market_coverage_ratio"],
        "trade_authority": TRADE_AUTHORITY,
    }
    (out / "VALUATION_CONTEXT_DECISION.json").write_text(
        json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out / "VALUATION_CONTEXT_VALIDATION.json").write_text(
        json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": decision["status"],
        "qc_status": decision["qc_status"],
        "market_as_of_date": target_date,
        "exact_baseline_market_as_of_date": base_date,
        "market_coverage_ratio": metrics["market_coverage_ratio"],
        "trade_authority": "NONE",
    }, ensure_ascii=False, sort_keys=True))
    return 0 if not hard_failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
