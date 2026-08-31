from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from scripts import fmdl3ede_core as core

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("Asia/Shanghai")
CANDIDATE = ROOT / "outputs/occ_r2/valuation/candidate"
BASELINE_PATH = ROOT / "outputs/fmdl3d/final/current/FMDL3D_UNIFIED_CURRENT.parquet"
BASELINE_MANIFEST = ROOT / "outputs/fmdl3e/contract/current/FMDL3EA_BASELINE_MANIFEST.json"
MARKET_RELEASE = ROOT / "outputs/current/CURRENT_RELEASE.json"
MARKET_SNAPSHOT = ROOT / "outputs/current/DAILY_MARKET_SNAPSHOT.csv"
STATEMENT_RELEASE = ROOT / "outputs/financials/statements/current/FMDL3B4_RELEASE.json"
FACTOR_RELEASE = ROOT / "outputs/financial_factors/engine/current/FMDL3CB_RELEASE.json"
SCORE_RELEASE = ROOT / "outputs/financial_factors/score/current/FMDL3CD_RELEASE.json"
PROPAGATION_CONFIG = ROOT / "config/fmdl3ede_propagation_resilience.json"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_market_delta(baseline: pd.DataFrame, snapshot: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    base = baseline[["symbol", "close"]].copy()
    base["symbol"] = base["symbol"].astype(str)
    snap = snapshot.copy()
    snap["symbol"] = snap["symbol"].astype(str)
    snap["close"] = pd.to_numeric(snap["close"], errors="coerce")
    if snap["symbol"].duplicated().any():
        raise ValueError("DUPLICATE_MARKET_SYMBOL")
    merged = base.rename(columns={"close": "baseline_close"}).merge(
        snap[["symbol", "close"]].rename(columns={"close": "refreshed_close"}),
        on="symbol",
        how="left",
    )
    positive = pd.to_numeric(merged["refreshed_close"], errors="coerce").gt(0)
    overlap = int(merged["refreshed_close"].notna().sum())
    metrics = {
        "baseline_symbol_count": int(base["symbol"].nunique()),
        "source_symbol_count": int(snap["symbol"].nunique()),
        "matched_symbol_count": overlap,
        "matched_positive_close_count": int(positive.sum()),
        "market_coverage_ratio": float(positive.mean()) if len(merged) else 0.0,
        "source_symbols_outside_financial_baseline": int(
            len(set(snap["symbol"]) - set(base["symbol"]))
        ),
        "financial_baseline_symbols_missing_from_source": int(
            len(set(base["symbol"]) - set(snap["symbol"]))
        ),
    }
    return merged, metrics



def sanitize_market_only_metrics(frame: pd.DataFrame, baseline: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    base = baseline.set_index("symbol")
    # Completed buyback and issuance dilution yields are effective share-change
    # ratios, not price yields. They must remain unchanged when market price moves.
    for field in ("completed_buyback_yield_ttm", "completed_issuance_dilution_yield_ttm"):
        if field in out.columns and field in baseline.columns:
            out[field] = out["symbol"].map(base[field])

    # Cash dividend yield is price-sensitive, while the completed share-change
    # components are not. Recompute the composite with the canonical sign rule.
    required_shareholder = {
        "dividend_yield_ttm",
        "completed_buyback_yield_ttm",
        "completed_issuance_dilution_yield_ttm",
        "shareholder_yield_ttm",
    }
    if required_shareholder.issubset(out.columns):
        complete = out[
            ["dividend_yield_ttm", "completed_buyback_yield_ttm", "completed_issuance_dilution_yield_ttm"]
        ].notna().all(axis=1)
        out.loc[complete, "shareholder_yield_ttm"] = (
            pd.to_numeric(out.loc[complete, "dividend_yield_ttm"], errors="coerce")
            + pd.to_numeric(out.loc[complete, "completed_buyback_yield_ttm"], errors="coerce")
            - pd.to_numeric(out.loc[complete, "completed_issuance_dilution_yield_ttm"], errors="coerce")
        )

    # EV multiples cannot be exactly refreshed from the unified consumer table
    # because net-debt components are intentionally not carried in that table.
    # Fail closed rather than scale EV multiples by the equity-price ratio.
    for value_col, state_col in (
        ("ev_sales_ttm", "ev_sales_ttm_state"),
        ("ev_operating_income_ttm", "ev_operating_income_ttm_state"),
    ):
        if value_col in out:
            out[value_col] = pd.NA
        if state_col in out:
            out[state_col] = "BLOCKED_STALE_EV_COMPONENTS_PENDING_OCC_R2B"

    valid_states = {"VALID", "VALID_WITH_WARNING"}
    state_columns = [
        "pe_ttm_state", "earnings_yield_ttm_state", "pb_state", "ps_ttm_state",
        "fcf_yield_ttm_state", "ev_sales_ttm_state", "ev_operating_income_ttm_state",
    ]
    available_states = [column for column in state_columns if column in out]
    if available_states:
        counts = out[available_states].apply(
            lambda row: sum(str(value) in valid_states for value in row), axis=1
        )
        if "valuation_valid_metric_count" in out:
            out["valuation_valid_metric_count"] = counts
        if "valuation_decision_grade_metric_count" in out:
            out["valuation_decision_grade_metric_count"] = counts

    if "valuation_row_hash" in out:
        out["valuation_row_hash"] = out.apply(
            lambda row: core.stable_hash({
                "symbol": row.get("symbol"), "pe_ttm": row.get("pe_ttm"),
                "pb": row.get("pb"), "ps_ttm": row.get("ps_ttm"),
                "fcf_yield_ttm": row.get("fcf_yield_ttm"),
                "ev_sales_ttm": row.get("ev_sales_ttm"),
                "ev_operating_income_ttm": row.get("ev_operating_income_ttm"),
                "market_as_of_date": row.get("market_as_of_date"),
            }), axis=1
        )
    if "row_hash" in out:
        out["row_hash"] = out.apply(core.row_hash, axis=1)
    return out

def main() -> int:
    cfg = read_json(PROPAGATION_CONFIG)
    baseline_manifest = read_json(BASELINE_MANIFEST)
    market_release = read_json(MARKET_RELEASE)
    statement_release = read_json(STATEMENT_RELEASE)
    factor_release = read_json(FACTOR_RELEASE)
    score_release = read_json(SCORE_RELEASE)

    baseline_date = str(baseline_manifest["market_as_of_date"])
    target_date = str(market_release.get("as_of_date") or "")
    if market_release.get("status") not in {"PUBLISHED", "PUBLISHED_WITH_WARNINGS"}:
        raise SystemExit("MARKET_CURRENT_NOT_ACCEPTED")
    if not target_date or target_date <= baseline_date:
        raise SystemExit(f"MARKET_DATE_NOT_LATER_THAN_FINANCIAL_BASELINE:{target_date}:{baseline_date}")

    baseline = pd.read_parquet(BASELINE_PATH)
    snapshot = pd.read_csv(MARKET_SNAPSHOT, encoding="utf-8-sig")
    delta, metrics = build_market_delta(baseline, snapshot)

    generated_at = datetime.now(TZ).isoformat(timespec="seconds")
    release_id = f"OCC_R2A_VALUATION_{datetime.now(TZ).strftime('%Y%m%dT%H%M%S%z')}"
    propagated = core.incremental_propagate(
        baseline,
        delta,
        cfg=cfg,
        release_id=release_id,
        incremental_release_id="OCC_R2A_MARKET_ONLY",
        target_date=target_date,
    )
    rebuilt = core.full_rebuild(
        baseline,
        delta,
        cfg=cfg,
        release_id=release_id,
        incremental_release_id="OCC_R2A_MARKET_ONLY",
        target_date=target_date,
    )
    propagated = sanitize_market_only_metrics(propagated, baseline)
    rebuilt = sanitize_market_only_metrics(rebuilt, baseline)
    audit = core.comparison_audit(propagated, rebuilt)
    mismatch_count = int(audit["mismatch_count"].sum())
    trade_values = set(propagated["trade_authority"].dropna().astype(str))
    required_count = int(cfg["propagation"]["required_universe_symbol_count"])
    required_coverage = float(cfg["propagation"]["required_market_coverage_ratio"])

    checks = {
        "MARKET_DATE_ADVANCED": target_date > baseline_date,
        "FINANCIAL_BASELINE_UNIVERSE_FROZEN": len(propagated) == required_count,
        "MARKET_COVERAGE": metrics["market_coverage_ratio"] >= required_coverage,
        "FULL_REBUILD_EQUAL": mismatch_count == 0,
        "DUPLICATE_SYMBOL_ZERO": not propagated["symbol"].duplicated().any(),
        "ZERO_TRADE_AUTHORITY": trade_values == {"NONE"},
        "FINANCIAL_DENOMINATOR_EXPLICIT_LKG": bool(statement_release.get("release_id")),
    }
    failures = [name for name, passed in checks.items() if not passed]

    if CANDIDATE.exists():
        shutil.rmtree(CANDIDATE)
    CANDIDATE.mkdir(parents=True)
    propagated.to_parquet(CANDIDATE / "VALUATION_CONTEXT_CURRENT.parquet", index=False, compression="zstd")
    delta.to_parquet(CANDIDATE / "MARKET_DELTA.parquet", index=False, compression="zstd")
    audit.to_csv(CANDIDATE / "FULL_REBUILD_AUDIT.csv", index=False)

    decision = {
        "schema_version": "1.0.0",
        "release_id": release_id,
        "generated_at": generated_at,
        "status": "PASS" if not failures else "FAIL",
        "qc_status": "PASS_MARKET_VALUATION_REFRESH_FINANCIAL_DENOMINATOR_LKG" if not failures else "FAIL",
        "market_as_of_date": target_date,
        "financial_baseline_market_as_of_date": baseline_date,
        "financial_denominator": {
            "status": "LKG_NOT_REFRESHED_BY_R2A",
            "statement_release_id": statement_release.get("release_id"),
            "statement_published_at": statement_release.get("published_at"),
            "financial_factor_release_id": factor_release.get("release_id"),
            "financial_score_release_id": score_release.get("release_id"),
            "financial_event_propagation": "PENDING_OCC_R2B",
        },
        "universe": {
            **metrics,
            "valuation_context_row_count": int(len(propagated)),
            "required_financial_baseline_symbol_count": required_count,
            "coverage_scope": "FROZEN_FMDL3_FINANCIAL_BASELINE_ONLY",
        },
        "valuation_fields_updated_by_market": {
            "exact_price_multiple_fields": ["pe_ttm", "pb", "ps_ttm"],
            "exact_inverse_price_fields": [
                "earnings_yield_ttm", "fcf_yield_ttm", "dividend_yield_ttm"
            ],
            "price_invariant_share_change_fields": [
                "completed_buyback_yield_ttm", "completed_issuance_dilution_yield_ttm"
            ],
            "blocked_until_r2b": ["ev_sales_ttm", "ev_operating_income_ttm"],
            "market_cap_fields": ["total_market_cap_cny", "float_market_cap_cny"],
        },
        "checks": checks,
        "hard_failures": failures,
        "controlled_limitations": [
            "FINANCIAL_FACT_DENOMINATORS_REMAIN_LAST_KNOWN_GOOD_PENDING_OCC_R2B",
            "FINANCIAL_BASELINE_UNIVERSE_IS_5528_AND_DOES_NOT_AUTO_ADMIT_NEWER_MARKET_SYMBOLS",
            "EV_MULTIPLES_ARE_BLOCKED_IN_R2A_BECAUSE_EXACT_NET_DEBT_COMPONENTS_ARE_NOT_IN_THE_UNIFIED_CONSUMER_TABLE",
            "BUYBACK_AND_ISSUANCE_DILUTION_YIELDS_ARE_SHARE_CHANGE_RATIOS_AND_REMAIN_PRICE_INVARIANT",
            "SPECIALIZED_FINANCIAL_SECTOR_METRICS_REMAIN_CONTROLLED_BY_EXISTING_PROFILE_GATES",
            "NO_RECOMMENDATION_PORTFOLIO_ACTION_OR_TRADE_AUTHORITY",
        ],
        "authority": "DATA_AND_RESEARCH_EVIDENCE_ONLY",
        "trade_authority": "NONE",
    }
    validation = {
        "schema_version": "1.0.0",
        "status": "PASS" if not failures else "FAIL",
        "hard_failures": failures,
        "market_as_of_date": target_date,
        "financial_denominator_status": "LKG_NOT_REFRESHED_BY_R2A",
        "full_rebuild_mismatch_count": mismatch_count,
        "metrics": metrics,
        "trade_authority": "NONE",
    }
    (CANDIDATE / "VALUATION_CONTEXT_DECISION.json").write_text(
        json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (CANDIDATE / "VALUATION_CONTEXT_VALIDATION.json").write_text(
        json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(decision, ensure_ascii=False, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
