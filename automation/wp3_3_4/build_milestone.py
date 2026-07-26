#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd


FAMILIES = {
    "PROFITABILITY_RETURNS": "profitability_returns_score",
    "GROWTH_MOMENTUM": "growth_momentum_score",
    "CASH_EARNINGS_QUALITY": "cash_earnings_quality_score",
    "BALANCE_SHEET_EFFICIENCY": "balance_sheet_efficiency_score",
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def clean_scalar(value: Any) -> Any:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        try:
            value = value.item()
        except (AttributeError, ValueError):
            pass
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return round(value, 10)
    return value


def normalize_code(value: Any) -> str:
    text = str(value or "").strip().upper()
    match = re.search(r"(?<!\d)(\d{6})(?!\d)", text)
    if match:
        return match.group(1)
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits[-6:].zfill(6) if digits else ""


def read_csv(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype=str, encoding="utf-8-sig")
    for column in frame.columns:
        if column in {
            "last_price", "volume", "turnover_amount", "total_market_cap",
            "avg_turnover_cny_20d", "return_20d", "return_60d", "return_120d",
            "return_250d", "distance_52w_high", "volatility_60d",
            "max_drawdown_120d", "aggregate_score", "overall_rank",
        }:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def normalize_symbol_column(frame: pd.DataFrame, candidates: Iterable[str]) -> pd.DataFrame:
    result = frame.copy()
    source = next((name for name in candidates if name in result.columns), None)
    if source is None:
        raise ValueError(f"symbol column missing; candidates={list(candidates)}")
    result["security_code"] = result[source].map(normalize_code)
    if result["security_code"].eq("").any():
        raise ValueError(f"blank normalized security codes from {source}")
    return result


def require_unique(frame: pd.DataFrame, key: str, label: str) -> None:
    duplicates = frame.loc[frame[key].duplicated(keep=False), key].astype(str).tolist()
    if duplicates:
        raise ValueError(f"{label} duplicate {key}: {duplicates[:10]}")


def numeric(frame: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    result = frame.copy()
    for column in columns:
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce")
    return result


def column_or_nan(frame: pd.DataFrame, column: str) -> pd.Series:
    if column in frame.columns:
        return pd.to_numeric(frame[column], errors="coerce")
    return pd.Series(np.nan, index=frame.index, dtype=float)


def percentile_score(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    return values.rank(method="average", pct=True) * 100.0


def valuation_context(row: pd.Series, cfg: dict[str, Any]) -> tuple[str, float | None, list[str]]:
    valid_count = clean_scalar(row.get("valuation_valid_metric_count"))
    pe = clean_scalar(row.get("pe_ttm"))
    fcf_yield = clean_scalar(row.get("fcf_yield_ttm"))
    shareholder_yield = clean_scalar(row.get("shareholder_yield_ttm"))
    minimum_count = int(cfg["valuation_context"]["minimum_valid_metric_count"])
    notes: list[str] = []
    if valid_count is None or int(valid_count) < minimum_count:
        return "VALUATION_EVIDENCE_INSUFFICIENT", None, ["VALUATION_VALID_METRICS_BELOW_MINIMUM"]

    components: list[float] = []
    if pe is not None:
        pe_value = float(pe)
        if 0 < pe_value <= 35:
            components.append(85.0)
        elif pe_value <= float(cfg["valuation_context"]["moderate_pe_ttm_max"]):
            components.append(65.0)
        elif pe_value >= float(cfg["valuation_context"]["high_expectation_pe_ttm_min"]):
            components.append(25.0)
            notes.append("HIGH_EXPECTATION_PE")
        elif pe_value > 0:
            components.append(45.0)
        else:
            notes.append("NON_POSITIVE_OR_NOT_MEANINGFUL_PE")
    if fcf_yield is not None:
        components.append(75.0 if float(fcf_yield) > 0 else 30.0)
        if float(fcf_yield) <= 0:
            notes.append("NON_POSITIVE_FCF_YIELD")
    if shareholder_yield is not None:
        components.append(70.0 if float(shareholder_yield) > 0 else 45.0)
    if not components:
        return "VALUATION_EVIDENCE_INSUFFICIENT", None, notes + ["NO_USABLE_VALUATION_COMPONENT"]

    score = float(np.mean(components))
    if score >= 70:
        state = "VALUATION_SUPPORTIVE_FOR_RESEARCH"
    elif score >= 45:
        state = "VALUATION_NEUTRAL_OR_MIXED"
    else:
        state = "VALUATION_HIGH_EXPECTATION_OR_WEAK_CASH_SUPPORT"
    return state, score, notes


def weighted_available_score(row: pd.Series, cfg: dict[str, Any]) -> tuple[float | None, float]:
    mapping = {
        "financial_score": "financial_score",
        "profitability_returns": "profitability_returns_score",
        "growth_momentum": "growth_momentum_score",
        "cash_earnings_quality": "cash_earnings_quality_score",
        "balance_sheet_efficiency": "balance_sheet_efficiency_score",
        "valuation_context": "valuation_context_score",
        "historical_factor_evidence": "historical_factor_score",
        "current_liquidity": "current_liquidity_percentile",
    }
    numerator = 0.0
    denominator = 0.0
    for weight_key, column in mapping.items():
        value = clean_scalar(row.get(column))
        if value is None:
            continue
        weight = float(cfg["research_priority_weights"][weight_key])
        numerator += float(value) * weight
        denominator += weight
    if denominator <= 0:
        return None, 0.0
    return numerator / denominator, denominator


def financial_gate(row: pd.Series, cfg: dict[str, Any]) -> tuple[bool, list[str]]:
    gate = cfg["financial_gate"]
    reasons: list[str] = []
    score_state = str(row.get("score_state") or "")
    confidence = str(row.get("score_confidence") or "")
    score = clean_scalar(row.get("financial_score"))
    family_count = clean_scalar(row.get("available_family_count"))
    checks = [
        ("FINANCIAL_SCORE", score, float(gate["minimum_financial_score"])),
        ("PROFITABILITY", clean_scalar(row.get("profitability_returns_score")), float(gate["minimum_profitability_score"])),
        ("GROWTH", clean_scalar(row.get("growth_momentum_score")), float(gate["minimum_growth_score"])),
        ("CASH_QUALITY", clean_scalar(row.get("cash_earnings_quality_score")), float(gate["minimum_cash_quality_score"])),
        ("BALANCE_SHEET", clean_scalar(row.get("balance_sheet_efficiency_score")), float(gate["minimum_balance_sheet_score"])),
    ]
    if not score_state.startswith("SCORE_ACCEPTED"):
        reasons.append("FINANCIAL_SCORE_NOT_ACCEPTED")
    if confidence not in set(gate["allowed_confidence"]):
        reasons.append("FINANCIAL_CONFIDENCE_NOT_HIGH_OR_MEDIUM")
    if family_count is None or int(family_count) < int(gate["minimum_available_family_count"]):
        reasons.append("FINANCIAL_FAMILY_COVERAGE_BELOW_MINIMUM")
    for label, value, minimum in checks:
        if value is None:
            reasons.append(f"{label}_MISSING")
        elif float(value) < minimum:
            reasons.append(f"{label}_BELOW_GATE")
    return not reasons, reasons


def parse_core20(path: Path) -> pd.DataFrame:
    payload = read_json(path)
    rows = []
    for item in payload["symbols"]:
        if "CANDIDATE_CORE_20" in item.get("roles", []):
            rows.append(
                {
                    "security_code": normalize_code(item["symbol"]),
                    "historical_core20_name": item["name"],
                    "historical_core20": True,
                }
            )
    result = pd.DataFrame(rows)
    require_unique(result, "security_code", "historical Core20")
    if len(result) != 20:
        raise ValueError(f"historical Core20 expected 20, got {len(result)}")
    return result


def load_data(root: Path, cfg: dict[str, Any]) -> dict[str, pd.DataFrame]:
    paths = {key: root / value for key, value in cfg["inputs"].items()}
    binding = read_json(paths["accepted_current_binding"])
    if binding["status"] != "ACCEPTED_ON_MAIN" or binding["as_of_date"] != cfg["as_of_date"]:
        raise ValueError("accepted Current binding mismatch")
    if binding["trade_authority"] != "NONE":
        raise ValueError("trade authority escalation")

    eligible = normalize_symbol_column(read_csv(paths["wp3_2b_eligible_universe"]), ["security_code", "symbol"])
    queue = normalize_symbol_column(read_csv(paths["wp3_2b_workload_queue"]), ["security_code", "symbol"])
    current = normalize_symbol_column(read_csv(paths["current_universe"]), ["security_code", "symbol"])
    screen = normalize_symbol_column(pd.read_parquet(paths["fmdl2_screening_universe"]), ["symbol", "security_code"])
    old_longlist = normalize_symbol_column(read_csv(paths["fmdl2_longlist"]), ["symbol", "security_code"])
    financial = normalize_symbol_column(pd.read_parquet(paths["financial_score"]), ["symbol", "security_code"])
    family = normalize_symbol_column(pd.read_parquet(paths["financial_family_scores"]), ["symbol", "security_code"])
    unified = normalize_symbol_column(pd.read_parquet(paths["fmdl3_unified_current"]), ["symbol", "security_code"])
    decisions = normalize_symbol_column(read_csv(paths["fmdl4b_graduation_decisions"]), ["symbol", "security_code"])
    core20 = parse_core20(paths["historical_core20"])

    for label, frame in {
        "eligible": eligible,
        "current": current,
        "screen": screen,
        "old_longlist": old_longlist,
        "financial": financial,
        "unified": unified,
        "decisions": decisions,
        "core20": core20,
    }.items():
        require_unique(frame, "security_code", label)

    return {
        "eligible": eligible,
        "queue": queue,
        "current": current,
        "screen": screen,
        "old_longlist": old_longlist,
        "financial": financial,
        "family": family,
        "unified": unified,
        "decisions": decisions,
        "core20": core20,
    }


def build_assessment(data: dict[str, pd.DataFrame], cfg: dict[str, Any]) -> pd.DataFrame:
    eligible = data["eligible"].copy()
    if len(eligible) != 5525:
        raise ValueError(f"WP3-2B eligible universe expected 5525, got {len(eligible)}")

    if "security_name" not in eligible.columns and "name" in eligible.columns:
        eligible["security_name"] = eligible["name"]
    base_columns = [
        "security_code", "security_name", "exchange", "market_data_readiness",
        "eligibility_reason", "last_price", "volume", "turnover_amount", "total_market_cap",
    ]
    base = eligible[[column for column in base_columns if column in eligible.columns]].copy()
    base = numeric(base, ["last_price", "volume", "turnover_amount", "total_market_cap"])

    screen = data["screen"].copy()
    screen_columns = [
        "security_code", "board", "industry_name", "listing_status", "factor_record_quality",
        "confidence_grade", "avg_turnover_cny_20d", "return_20d", "return_60d",
        "return_120d", "return_250d", "distance_52w_high", "volatility_60d",
        "max_drawdown_120d",
    ]
    screen = screen[[column for column in screen_columns if column in screen.columns]].copy()

    financial = data["financial"].copy()
    financial_columns = [
        "security_code", "sector_profile", "financial_score", "score_band", "score_confidence",
        "score_confidence_numeric", "available_family_count", "available_family_weight",
        "global_factor_weight_coverage", "conditional_weight_share", "ranking_eligible", "score_state",
    ]
    financial = financial[[column for column in financial_columns if column in financial.columns]].copy()
    financial = numeric(
        financial,
        ["financial_score", "score_confidence_numeric", "available_family_count", "available_family_weight", "global_factor_weight_coverage", "conditional_weight_share"],
    )

    family = data["family"].copy()
    family["family_score"] = pd.to_numeric(family.get("family_score"), errors="coerce")
    available = family[family.get("family_state", "").astype(str).eq("FAMILY_SCORE_AVAILABLE")].copy()
    family_pivot = available.pivot_table(index="security_code", columns="family_id", values="family_score", aggfunc="first")
    family_pivot = family_pivot.rename(columns=FAMILIES).reset_index()

    unified = data["unified"].copy()
    valuation_columns = [
        "security_code", "market_as_of_date", "close", "total_market_cap_cny", "float_market_cap_cny",
        "pe_ttm", "pb", "ps_ttm", "fcf_yield_ttm", "ev_sales_ttm", "ev_operating_income_ttm",
        "valuation_valid_metric_count", "valuation_decision_grade_metric_count", "shareholder_yield_ttm",
        "dividend_yield_ttm", "shareholder_return_state", "capitalization_state",
    ]
    unified = unified[[column for column in valuation_columns if column in unified.columns]].copy()
    unified = numeric(
        unified,
        ["close", "total_market_cap_cny", "float_market_cap_cny", "pe_ttm", "pb", "ps_ttm", "fcf_yield_ttm", "ev_sales_ttm", "ev_operating_income_ttm", "valuation_valid_metric_count", "valuation_decision_grade_metric_count", "shareholder_yield_ttm", "dividend_yield_ttm"],
    )

    old_longlist = data["old_longlist"].copy()
    old_columns = [
        "security_code", "overall_rank", "research_priority", "primary_sleeve", "sleeves",
        "aggregate_score", "factor_record_quality", "confidence_grade",
    ]
    old_longlist = old_longlist[[column for column in old_columns if column in old_longlist.columns]].copy()
    old_longlist = old_longlist.rename(
        columns={
            "overall_rank": "historical_longlist_rank",
            "research_priority": "historical_research_priority",
            "primary_sleeve": "historical_primary_sleeve",
            "sleeves": "historical_sleeves",
            "aggregate_score": "historical_aggregate_score",
            "factor_record_quality": "historical_factor_record_quality",
            "confidence_grade": "historical_confidence_grade",
        }
    )
    old_longlist = numeric(old_longlist, ["historical_longlist_rank", "historical_aggregate_score"])
    if len(old_longlist):
        old_longlist["historical_factor_score"] = 100.0 * (
            len(old_longlist) - old_longlist["historical_longlist_rank"] + 1
        ) / len(old_longlist)

    decisions = data["decisions"].copy()
    decision_columns = [
        "security_code", "research_stage", "graduation_decision", "decision_reason_codes_json",
        "formal_research_object_created", "research_status", "next_workflow",
    ]
    decisions = decisions[[column for column in decision_columns if column in decisions.columns]].copy()
    decisions = decisions.rename(
        columns={
            "research_stage": "prior_research_stage",
            "graduation_decision": "prior_graduation_decision",
            "decision_reason_codes_json": "prior_decision_reason_codes_json",
            "formal_research_object_created": "prior_formal_research_object_created",
            "research_status": "prior_research_status",
            "next_workflow": "prior_next_workflow",
        }
    )

    queue = data["queue"].copy()
    queue_columns = ["security_code", "workload_priority_rank"]
    queue = queue[[column for column in queue_columns if column in queue.columns]].copy()
    queue = numeric(queue, ["workload_priority_rank"])
    queue["wp3_2b_queue_member"] = True

    assessment = base
    for frame in [screen, financial, family_pivot, unified, old_longlist, decisions, queue, data["core20"]]:
        assessment = assessment.merge(frame, on="security_code", how="left", validate="one_to_one")

    assessment["historical_core20"] = assessment["historical_core20"].fillna(False).astype(bool)
    assessment["wp3_2b_queue_member"] = assessment["wp3_2b_queue_member"].fillna(False).astype(bool)
    assessment["industry_bucket"] = assessment.get("industry_name", pd.Series(index=assessment.index, dtype=object)).fillna("")
    assessment.loc[assessment["industry_bucket"].eq(""), "industry_bucket"] = assessment.get("sector_profile", "UNKNOWN")
    assessment["industry_bucket"] = assessment["industry_bucket"].replace("", "UNKNOWN")
    assessment["board"] = assessment.get("board", pd.Series("UNKNOWN", index=assessment.index)).fillna("UNKNOWN")

    assessment["current_liquidity_percentile"] = percentile_score(assessment["turnover_amount"])
    valuation_records = assessment.apply(lambda row: valuation_context(row, cfg), axis=1)
    assessment["valuation_context_state"] = [item[0] for item in valuation_records]
    assessment["valuation_context_score"] = [item[1] for item in valuation_records]
    assessment["valuation_context_notes"] = ["|".join(item[2]) for item in valuation_records]

    gate_results = assessment.apply(lambda row: financial_gate(row, cfg), axis=1)
    assessment["financial_gate_pass"] = [item[0] for item in gate_results]
    assessment["financial_gate_reasons"] = ["|".join(item[1]) for item in gate_results]

    risk_flags: list[str] = []
    for row in assessment.itertuples(index=False):
        flags: list[str] = []
        volatility = clean_scalar(getattr(row, "volatility_60d", None))
        drawdown = clean_scalar(getattr(row, "max_drawdown_120d", None))
        if volatility is not None and float(volatility) > 0.80:
            flags.append("HIGH_60D_VOLATILITY")
        if drawdown is not None and float(drawdown) < -0.40:
            flags.append("DEEP_120D_DRAWDOWN")
        if str(getattr(row, "prior_graduation_decision", "")) == "REJECTED":
            flags.append("PRIOR_RESEARCH_REJECTION_REQUIRES_NEW_EVIDENCE")
        risk_flags.append("|".join(flags))
    assessment["research_risk_flags"] = risk_flags

    scores = assessment.apply(lambda row: weighted_available_score(row, cfg), axis=1)
    assessment["research_priority_score"] = [item[0] for item in scores]
    assessment["research_priority_weight_coverage"] = [item[1] for item in scores]

    dispositions: list[str] = []
    for row in assessment.itertuples(index=False):
        score_state = str(getattr(row, "score_state", ""))
        gate_pass = bool(getattr(row, "financial_gate_pass", False))
        valuation_state = str(getattr(row, "valuation_context_state", ""))
        risk = str(getattr(row, "research_risk_flags", ""))
        if score_state == "CONTROLLED_PROFILE_EXCLUSION":
            disposition = "SEPARATE_PROFILE_REVIEW_REQUIRED"
        elif gate_pass and "PRIOR_RESEARCH_REJECTION" not in risk and valuation_state == "VALUATION_SUPPORTIVE_FOR_RESEARCH":
            disposition = "MULTIDIMENSIONAL_ELIGIBLE"
        elif gate_pass and "PRIOR_RESEARCH_REJECTION" not in risk:
            disposition = "ELIGIBLE_WITH_VALUATION_OR_RISK_REVIEW"
        elif str(getattr(row, "score_state", "")).startswith("SCORE_ACCEPTED"):
            disposition = "DEFER_BELOW_STABLE_GROWTH_GATE"
        else:
            disposition = "DEFER_FINANCIAL_EVIDENCE_OR_PROFILE"
        dispositions.append(disposition)
    assessment["multidimensional_disposition"] = dispositions
    assessment["investment_ranking"] = False
    assessment["candidate_admission_authority"] = False
    assessment["trade_authority"] = "NONE"
    return assessment.sort_values(["research_priority_score", "financial_score", "security_code"], ascending=[False, False, True], na_position="last").reset_index(drop=True)


def select_longlist(assessment: pd.DataFrame, cfg: dict[str, Any]) -> pd.DataFrame:
    eligible = assessment[
        assessment["multidimensional_disposition"].isin(
            ["MULTIDIMENSIONAL_ELIGIBLE", "ELIGIBLE_WITH_VALUATION_OR_RISK_REVIEW"]
        )
    ].copy()
    eligible = eligible[~eligible["research_risk_flags"].str.contains("PRIOR_RESEARCH_REJECTION", na=False)]
    eligible = eligible.sort_values(
        ["research_priority_score", "financial_score", "score_confidence_numeric", "current_liquidity_percentile", "security_code"],
        ascending=[False, False, False, False, True],
        na_position="last",
    )

    max_rows = int(cfg["longlist"]["maximum_rows"])
    max_industry = int(cfg["longlist"]["maximum_per_industry"])
    max_board = int(cfg["longlist"]["maximum_per_board"])
    industry_counts: dict[str, int] = {}
    board_counts: dict[str, int] = {}
    selected: list[pd.Series] = []
    for _, row in eligible.iterrows():
        industry = str(row.get("industry_bucket") or "UNKNOWN")
        board = str(row.get("board") or "UNKNOWN")
        if industry_counts.get(industry, 0) >= max_industry:
            continue
        if board_counts.get(board, 0) >= max_board:
            continue
        selected.append(row)
        industry_counts[industry] = industry_counts.get(industry, 0) + 1
        board_counts[board] = board_counts.get(board, 0) + 1
        if len(selected) >= max_rows:
            break

    longlist = pd.DataFrame(selected).reset_index(drop=True)
    if len(longlist):
        longlist.insert(0, "research_longlist_rank", range(1, len(longlist) + 1))
        longlist["research_bucket"] = longlist["research_longlist_rank"].map(
            lambda rank: "A_DEEP_DIVE" if rank <= 20 else "B_STRUCTURED_RESEARCH" if rank <= 40 else "C_WATCH_AND_EVIDENCE_FILL"
        )
        longlist["proposed_next_step"] = longlist["research_bucket"].map(
            {
                "A_DEEP_DIVE": "FULL_RESEARCH_OBJECT_AND_VALUATION_SCENARIO",
                "B_STRUCTURED_RESEARCH": "COMPANY_TEARSHEET_AND_EARNINGS_QUALITY_REVIEW",
                "C_WATCH_AND_EVIDENCE_FILL": "EVIDENCE_FILL_AND_TRIGGER_MONITORING",
            }
        )
        longlist["candidate_membership_mutation"] = 0
        longlist["trade_authority"] = "NONE"
    return longlist


def core20_review(assessment: pd.DataFrame, cfg: dict[str, Any]) -> pd.DataFrame:
    review = assessment[assessment["historical_core20"]].copy()
    if len(review) != int(cfg["longlist"]["historical_core20_review_count"]):
        raise ValueError(f"historical Core20 review expected 20, got {len(review)}")
    dispositions: list[str] = []
    reasons: list[str] = []
    for row in review.itertuples(index=False):
        score_state = str(getattr(row, "score_state", ""))
        gate_pass = bool(getattr(row, "financial_gate_pass", False))
        valuation = str(getattr(row, "valuation_context_state", ""))
        prior = str(getattr(row, "prior_graduation_decision", ""))
        score = clean_scalar(getattr(row, "financial_score", None))
        if score_state == "CONTROLLED_PROFILE_EXCLUSION":
            disposition = "SEPARATE_PROFILE_REVIEW_REQUIRED"
            reason = "GENERAL_NON_FINANCIAL_SCORE_NOT_APPLICABLE"
        elif gate_pass and prior == "GRADUATED":
            disposition = "READMISSION_REVIEW_PRIORITY"
            reason = "CURRENT_MULTIDIMENSIONAL_GATE_PASS_AND_PRIOR_RESEARCH_GRADUATED"
        elif gate_pass and valuation == "VALUATION_SUPPORTIVE_FOR_RESEARCH":
            disposition = "READMISSION_REVIEW"
            reason = "CURRENT_MULTIDIMENSIONAL_GATE_PASS"
        elif gate_pass:
            disposition = "WATCHLIST_VALUATION_OR_RISK_REVIEW"
            reason = "FINANCIAL_GATE_PASS_BUT_VALUATION_OR_RISK_REVIEW_REQUIRED"
        elif score is not None and float(score) >= 50:
            disposition = "WATCHLIST_RESEARCH_GAP"
            reason = "FINANCIAL_EVIDENCE_NOT_YET_AT_STABLE_GROWTH_GATE"
        else:
            disposition = "DEPRIORITIZE_PENDING_THESIS_REBUILD"
            reason = "CURRENT_EVIDENCE_BELOW_GATE_OR_INCOMPLETE"
        dispositions.append(disposition)
        reasons.append(reason)
    review.insert(0, "core20_review_order", range(1, len(review) + 1))
    review["core20_review_disposition"] = dispositions
    review["core20_review_reason"] = reasons
    review["automatic_removal"] = False
    review["automatic_readmission"] = False
    review["candidate_membership_mutation"] = 0
    review["trade_authority"] = "NONE"
    return review.sort_values(
        ["core20_review_disposition", "research_priority_score", "security_code"],
        ascending=[True, False, True],
        na_position="last",
    ).reset_index(drop=True)


def comparison_table(longlist: pd.DataFrame, core_review: pd.DataFrame) -> pd.DataFrame:
    new_codes = set(longlist["security_code"].astype(str)) if len(longlist) else set()
    old_codes = set(core_review["security_code"].astype(str))
    combined = sorted(new_codes | old_codes)
    long_index = longlist.set_index("security_code") if len(longlist) else pd.DataFrame()
    core_index = core_review.set_index("security_code")
    rows = []
    for code in combined:
        in_new = code in new_codes
        in_old = code in old_codes
        new_row = long_index.loc[code] if in_new else None
        old_row = core_index.loc[code] if in_old else None
        name = clean_scalar(new_row.get("security_name")) if in_new else clean_scalar(old_row.get("security_name"))
        if in_new and in_old:
            route = "CORE20_READMISSION_REVIEW_PRIORITY"
        elif in_new:
            route = "NEW_RESEARCH_LONGLIST"
        else:
            route = str(old_row.get("core20_review_disposition"))
        rows.append(
            {
                "security_code": code,
                "security_name": name,
                "historical_core20": in_old,
                "new_research_longlist": in_new,
                "overlap": in_old and in_new,
                "new_longlist_rank": int(new_row.get("research_longlist_rank")) if in_new else None,
                "core20_review_disposition": str(old_row.get("core20_review_disposition")) if in_old else None,
                "proposed_route": route,
                "candidate_membership_mutation": 0,
                "trade_authority": "NONE",
            }
        )
    return pd.DataFrame(rows)


def executive_review(
    assessment: pd.DataFrame,
    longlist: pd.DataFrame,
    core_review: pd.DataFrame,
    comparison: pd.DataFrame,
    cfg: dict[str, Any],
) -> str:
    disposition_counts = assessment["multidimensional_disposition"].value_counts().to_dict()
    core_counts = core_review["core20_review_disposition"].value_counts().to_dict()
    industry_count = int(longlist["industry_bucket"].nunique()) if len(longlist) else 0
    overlap = int(comparison["overlap"].sum()) if len(comparison) else 0
    top_rows = []
    for row in longlist.head(20).itertuples(index=False):
        top_rows.append(
            f"| {int(row.research_longlist_rank)} | {row.security_code} | {row.security_name} | "
            f"{row.industry_bucket} | {clean_scalar(row.financial_score)} | "
            f"{clean_scalar(row.research_priority_score)} | {row.valuation_context_state} |"
        )
    top_table = "\n".join(top_rows)
    return f"""# WP3-3 + WP3-4｜多维筛选、行业Longlist与历史Core20重审

- 数据基准：{cfg['as_of_date']}已接受普通A股Current
- WP3-2B Eligible Universe：{len(assessment)}
- 多维研究Longlist：{len(longlist)}
- Longlist行业桶：{industry_count}
- 历史Core20重审：{len(core_review)}
- 新Longlist与历史Core20重合：{overlap}
- 投资排名：否
- Candidate、Research Object、真实账户、模拟盘和订单变更：0
- trade_authority：NONE

## 1. 本轮含义

本轮把WP3-2B的“数据与流动性合格”推进为质量、成长、现金质量、资产负债表、估值语境、历史因子和当前流动性的多维研究优先级。`research_priority_score`仅用于安排研究工作，不是投资吸引力评分，也不构成Candidate准入、仓位或交易建议。

## 2. 全市场分层

```json
{json.dumps(disposition_counts, ensure_ascii=False, indent=2, sort_keys=True)}
```

金融及其他被通用非金融评分包排除的公司进入`SEPARATE_PROFILE_REVIEW_REQUIRED`，不以零分处理，不与一般非金融公司强行比较。

## 3. 历史Core20重审

```json
{json.dumps(core_counts, ensure_ascii=False, indent=2, sort_keys=True)}
```

历史Core20不享受祖父条款。`READMISSION_REVIEW`仍只是进入下一轮研究与Entry Baseline补齐，不代表自动留在Candidate；`DEPRIORITIZE`也不是自动删除。

## 4. Longlist前20个研究任务

| Rank | Code | Name | Industry | Financial score | Research priority | Valuation context |
|---:|---|---|---|---:|---:|---|
{top_table}

## 5. 下一步门禁

WP3-5 + WP3-6应基于本Longlist和Core20重审结果完成正式Research Object、Entry Baseline、Candidate Core / Shadow / Ready-to-Buy建议。任何Candidate成员变更必须另行形成受治理Proposal并由用户批准。
"""


def build_outputs(root: Path, output_dir: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    data = load_data(root, cfg)
    assessment = build_assessment(data, cfg)
    longlist = select_longlist(assessment, cfg)
    core_review = core20_review(assessment, cfg)
    comparison = comparison_table(longlist, core_review)
    gaps = assessment[
        assessment["multidimensional_disposition"].isin(
            ["SEPARATE_PROFILE_REVIEW_REQUIRED", "DEFER_FINANCIAL_EVIDENCE_OR_PROFILE"]
        )
        | assessment["historical_core20"]
    ].copy()

    output_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "full_market_assessment": output_dir / "WP3_3_4_FULL_MARKET_ASSESSMENT.csv",
        "eligible_research_universe": output_dir / "WP3_3_4_ELIGIBLE_RESEARCH_UNIVERSE.csv",
        "industry_longlist": output_dir / "WP3_3_INDUSTRY_LONGLIST.csv",
        "historical_core20_review": output_dir / "WP3_4_HISTORICAL_CORE20_REVIEW.csv",
        "new_vs_old_comparison": output_dir / "WP3_4_NEW_VS_OLD_CANDIDATE_COMPARISON.csv",
        "research_gap_queue": output_dir / "WP3_3_4_RESEARCH_GAP_QUEUE.csv",
        "executive_review": output_dir / "WP3_3_4_EXECUTIVE_REVIEW.md",
    }
    assessment.to_csv(files["full_market_assessment"], index=False, encoding="utf-8-sig")
    assessment[
        assessment["multidimensional_disposition"].isin(
            ["MULTIDIMENSIONAL_ELIGIBLE", "ELIGIBLE_WITH_VALUATION_OR_RISK_REVIEW"]
        )
    ].to_csv(files["eligible_research_universe"], index=False, encoding="utf-8-sig")
    longlist.to_csv(files["industry_longlist"], index=False, encoding="utf-8-sig")
    core_review.to_csv(files["historical_core20_review"], index=False, encoding="utf-8-sig")
    comparison.to_csv(files["new_vs_old_comparison"], index=False, encoding="utf-8-sig")
    gaps.to_csv(files["research_gap_queue"], index=False, encoding="utf-8-sig")
    files["executive_review"].write_text(
        executive_review(assessment, longlist, core_review, comparison, cfg),
        encoding="utf-8",
    )

    metrics = {
        "full_market_rows": int(len(assessment)),
        "multidimensional_eligible_rows": int(
            assessment["multidimensional_disposition"].isin(
                ["MULTIDIMENSIONAL_ELIGIBLE", "ELIGIBLE_WITH_VALUATION_OR_RISK_REVIEW"]
            ).sum()
        ),
        "industry_longlist_rows": int(len(longlist)),
        "industry_bucket_count": int(longlist["industry_bucket"].nunique()) if len(longlist) else 0,
        "historical_core20_review_rows": int(len(core_review)),
        "core20_longlist_overlap": int(comparison["overlap"].sum()),
        "separate_profile_review_rows": int(
            assessment["multidimensional_disposition"].eq("SEPARATE_PROFILE_REVIEW_REQUIRED").sum()
        ),
        "candidate_membership_mutations": 0,
        "research_object_mutations": 0,
        "simulation_trade_mutations": 0,
        "real_account_mutations": 0,
        "orders": 0,
    }
    manifest = {
        "program_id": cfg["program_id"],
        "contract_version": cfg["contract_version"],
        "status": "PROPOSAL_ONLY_PENDING_HUMAN_REVIEW",
        "as_of_date": cfg["as_of_date"],
        "method": "MULTIDIMENSIONAL_RESEARCH_PRIORITY_NOT_INVESTMENT_RANKING",
        "metrics": metrics,
        "authority": cfg["authority"],
        "files": {
            key: {"path": str(path.relative_to(root)), "sha256": sha256_file(path)}
            for key, path in files.items()
        },
        "next_gate": "WP3-5_WP3-6_RESEARCH_OBJECT_ENTRY_BASELINE_AND_CANDIDATE_REBUILD_PROPOSAL",
        "trade_authority": "NONE",
    }
    manifest_path = output_dir / "WP3_3_4_MANIFEST.json"
    write_json(manifest_path, manifest)
    manifest["files"]["manifest"] = {
        "path": str(manifest_path.relative_to(root)),
        "sha256": sha256_file(manifest_path),
    }
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--config", default="automation/wp3_3_4/config.json")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    cfg = read_json(root / args.config)
    manifest = build_outputs(root, root / args.output_dir, cfg)
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
