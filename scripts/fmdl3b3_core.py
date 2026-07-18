from __future__ import annotations

import hashlib
import json
import re
from typing import Any

import pandas as pd

CORRECTION_FULL_PATTERNS = ("更正后", "修订后", "更新后", "修正版", "重述后")
CORRECTION_NOTICE_PATTERNS = ("更正公告", "修订公告", "补充更正", "会计差错更正", "前期差错更正")
ANCILLARY_PATTERNS = (
    "提示性公告", "披露提示", "披露时间", "预约披露", "业绩说明", "说明会", "问询函", "问询回复",
    "回复公告", "监管工作函", "持续督导", "保荐", "摘要", "英文版", "审计报告", "财务报告", "专项说明",
    "预告公告", "活动公告", "投资者关系", "取消", "延期回复", "提前披露",
)
PERIODIC_PATTERNS = ("年度报告", "半年度报告", "季度报告", "一季度报告", "三季度报告")


def stable_hash(payload: dict[str, Any]) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def clean_title(value: Any) -> str:
    text = re.sub(r"<[^>]+>", "", str(value or ""))
    return re.sub(r"\s+", "", text)


def classify_document(title: Any, is_revision: Any = False) -> str:
    text = clean_title(title)
    if any(token in text for token in CORRECTION_FULL_PATTERNS):
        return "PERIODIC_REPORT_CORRECTED_FULL"
    if any(token in text for token in CORRECTION_NOTICE_PATTERNS):
        return "PERIODIC_REPORT_CORRECTION_NOTICE"
    if any(token in text for token in ANCILLARY_PATTERNS):
        return "ANCILLARY_DISCLOSURE"
    if any(token in text for token in PERIODIC_PATTERNS):
        return "PERIODIC_REPORT_FULL"
    if bool(is_revision):
        return "REVISION_INDICATED_UNCLASSIFIED"
    return "OTHER_DISCLOSURE"


def build_authoritative_revision_lineage(revisions: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    required = {"symbol", "report_period_end", "announcement_date", "filing_title", "revision_id"}
    missing = required - set(revisions.columns)
    if missing:
        raise ValueError(f"revision ledger missing columns: {sorted(missing)}")
    docs = revisions.copy().reset_index(drop=True)
    docs["document_class"] = [classify_document(t, r) for t, r in zip(docs["filing_title"], docs.get("is_revision", False))]
    docs["is_canonical_periodic_document"] = docs["document_class"].isin({"PERIODIC_REPORT_FULL", "PERIODIC_REPORT_CORRECTED_FULL"})
    docs["is_correction_notice"] = docs["document_class"].eq("PERIODIC_REPORT_CORRECTION_NOTICE")
    keys = ["symbol", "report_period_end"]
    canonical = docs[docs["is_canonical_periodic_document"]].copy()
    canonical = canonical.sort_values(keys + ["announcement_date", "announcement_timestamp_raw", "filing_title"], na_position="last")
    canonical["canonical_revision_sequence"] = canonical.groupby(keys).cumcount() + 1
    canonical["canonical_document_count"] = canonical.groupby(keys)["revision_id"].transform("size")
    canonical["canonical_superseded_at"] = canonical.groupby(keys)["available_from"].shift(-1)
    canonical["canonical_available_from"] = canonical["available_from"]
    canonical["canonical_revision_status"] = canonical["canonical_superseded_at"].notna().map({True: "SUPERSEDED_CANONICAL_REVISION", False: "LATEST_CANONICAL_REVISION"})
    canonical["structured_history_status"] = canonical["canonical_superseded_at"].notna().map({True: "DOCUMENT_ONLY_NO_HISTORICAL_STRUCTURED_VALUE", False: "CURRENT_PROVIDER_VALUE_AVAILABLE"})
    enrich_cols = ["canonical_revision_sequence", "canonical_available_from", "canonical_superseded_at", "canonical_revision_status", "structured_history_status"]
    docs = docs.join(canonical[enrich_cols], how="left")
    docs["canonical_revision_status"] = docs["canonical_revision_status"].fillna("NON_CANONICAL_DISCLOSURE")
    docs["structured_history_status"] = docs["structured_history_status"].fillna("NOT_APPLICABLE")

    all_periods = docs[keys].drop_duplicates()
    if len(canonical):
        latest = canonical.groupby(keys, as_index=False).tail(1)
        period_status = latest[keys + ["canonical_document_count", "revision_id", "canonical_available_from", "document_class"]].rename(columns={
            "revision_id": "latest_canonical_revision_id", "canonical_available_from": "authoritative_available_from"
        })
    else:
        period_status = pd.DataFrame(columns=keys + ["canonical_document_count", "latest_canonical_revision_id", "authoritative_available_from", "document_class"])
    notice_counts = docs.groupby(keys)["is_correction_notice"].sum().rename("correction_notice_count").reset_index()
    periods = all_periods.merge(period_status, on=keys, how="left").merge(notice_counts, on=keys, how="left")
    periods["canonical_document_count"] = periods["canonical_document_count"].fillna(0).astype(int)
    periods["correction_notice_count"] = periods["correction_notice_count"].fillna(0).astype(int)
    no_doc = periods["canonical_document_count"].eq(0)
    restated = periods["canonical_document_count"].gt(1) | periods["document_class"].eq("PERIODIC_REPORT_CORRECTED_FULL") | periods["correction_notice_count"].gt(0)
    periods["restatement_status"] = "ORIGINAL_ONLY"
    periods.loc[restated, "restatement_status"] = "RESTATED_OR_CORRECTED"
    periods.loc[no_doc, "restatement_status"] = "UNRESOLVED_NO_CANONICAL_PERIODIC_DOCUMENT"
    periods["historical_replay_status"] = "FULL_CURRENT_SOURCE_REPLAY_AVAILABLE"
    periods.loc[restated & ~no_doc, "historical_replay_status"] = "LATEST_ONLY_PRE_RESTATEMENT_NUMERIC_REPLAY_BLOCKED"
    periods.loc[no_doc, "historical_replay_status"] = "BLOCKED_NO_CANONICAL_PERIODIC_DOCUMENT"
    periods = periods.drop(columns=["document_class"])
    docs["trade_authority"] = "NONE"
    periods["trade_authority"] = "NONE"
    return docs, periods


def build_fact_overlay(normalized: pd.DataFrame, period_status: pd.DataFrame) -> pd.DataFrame:
    overlay_cols = [
        "normalized_fact_id", "symbol", "statement", "line_item_id", "period_end", "fiscal_period_type", "basis",
        "line_item_original", "source_route_id", "currency", "units", "decision_grade_eligible", "record_quality",
        "revision_sequence", "available_from", "trade_authority",
    ]
    missing = set(overlay_cols) - set(normalized.columns)
    if missing:
        raise ValueError(f"normalized shard missing columns: {sorted(missing)}")
    result = normalized[overlay_cols].copy()
    result = result.merge(
        period_status[["symbol", "report_period_end", "canonical_document_count", "restatement_status", "latest_canonical_revision_id", "authoritative_available_from", "historical_replay_status"]],
        left_on=["symbol", "period_end"], right_on=["symbol", "report_period_end"], how="left", validate="many_to_one"
    )
    result["comparability_evidence_status"] = "CURRENT_VALID"
    no_doc = result["canonical_document_count"].fillna(0).eq(0)
    restated = result["restatement_status"].eq("RESTATED_OR_CORRECTED")
    result.loc[no_doc, "comparability_evidence_status"] = "QUARANTINED_NO_CANONICAL_PERIODIC_DOCUMENT"
    result.loc[~no_doc & restated, "comparability_evidence_status"] = "CURRENT_VALID_PRE_RESTATEMENT_REPLAY_BLOCKED"
    result["fmdl3b3_decision_grade_eligible"] = result["decision_grade_eligible"].astype(bool) & ~no_doc
    result["fmdl3b3_available_from"] = result["authoritative_available_from"].where(~no_doc, result["available_from"])
    result["fmdl3b3_revision_id"] = result["latest_canonical_revision_id"]
    result["trade_authority"] = "NONE"
    return result.drop(columns=["report_period_end"])


def build_comparability_bridge(overlay: pd.DataFrame) -> pd.DataFrame:
    import numpy as np
    group_cols = ["symbol", "statement", "line_item_id", "fiscal_period_type"]
    ordered = overlay.sort_values(group_cols + ["period_end"]).copy()
    prior_fields = [
        "normalized_fact_id", "period_end", "fmdl3b3_decision_grade_eligible", "currency", "units", "basis",
        "line_item_original", "source_route_id", "restatement_status", "fmdl3b3_available_from"
    ]
    grouped = ordered.groupby(group_cols, dropna=False, sort=False)
    for field in prior_fields:
        ordered[f"prior_{field}"] = grouped[field].shift(1)
    out = ordered[ordered["prior_normalized_fact_id"].notna()].copy()
    if out.empty:
        return pd.DataFrame(columns=["comparison_id", "symbol", "statement", "line_item_id", "fiscal_period_type", "current_period", "prior_period", "current_fact_id", "prior_fact_id", "comparison_status", "reason_codes", "model_treatment", "current_available_from", "prior_available_from", "current_restatement_status", "prior_restatement_status", "trade_authority"])
    reason_columns: list[tuple[str, pd.Series]] = []
    reason_columns.append(("NON_DECISION_GRADE_INPUT", ~out["fmdl3b3_decision_grade_eligible"].astype(bool) | ~out["prior_fmdl3b3_decision_grade_eligible"].astype("boolean").fillna(False).astype(bool)))
    reason_columns.append(("CURRENCY_CHANGED", out["currency"].astype(str) != out["prior_currency"].astype(str)))
    reason_columns.append(("UNITS_CHANGED", out["units"].astype(str) != out["prior_units"].astype(str)))
    reason_columns.append(("BASIS_CHANGED", out["basis"].astype(str) != out["prior_basis"].astype(str)))
    reason_columns.append(("PROVIDER_LINE_RENAMED_OR_REGROUPED", out["line_item_original"].astype(str) != out["prior_line_item_original"].astype(str)))
    reason_columns.append(("SOURCE_ROUTE_CHANGED", out["source_route_id"].astype(str) != out["prior_source_route_id"].astype(str)))
    reason_columns.append(("RESTATEMENT_LATEST_ONLY_HISTORY", out["restatement_status"].eq("RESTATED_OR_CORRECTED") | out["prior_restatement_status"].eq("RESTATED_OR_CORRECTED")))
    current_year = pd.to_datetime(out["period_end"], errors="coerce").dt.year
    prior_year = pd.to_datetime(out["prior_period_end"], errors="coerce").dt.year
    reason_columns.append(("NON_CONSECUTIVE_FISCAL_YEAR", (current_year - prior_year).ne(1)))
    codes = pd.Series("", index=out.index, dtype="object")
    hard_mask = pd.Series(False, index=out.index)
    hard_reasons = {"NON_DECISION_GRADE_INPUT", "CURRENCY_CHANGED", "UNITS_CHANGED", "BASIS_CHANGED"}
    any_mask = pd.Series(False, index=out.index)
    for code, mask in reason_columns:
        mask = mask.fillna(True) if code == "NON_CONSECUTIVE_FISCAL_YEAR" else mask.fillna(False)
        codes = codes.where(~mask, codes + np.where(codes.eq(""), "", "|") + code)
        any_mask |= mask
        if code in hard_reasons:
            hard_mask |= mask
    out["reason_codes"] = codes.mask(codes.eq(""), "NONE")
    out["comparison_status"] = np.where(hard_mask, "NOT_COMPARABLE", np.where(any_mask, "COMPARABLE_WITH_WARNING", "COMPARABLE"))
    out["model_treatment"] = np.where(hard_mask, "BLOCK_YOY_AND_TREND", np.where(any_mask, "LOADABLE_WITH_EXPLICIT_WARNING", "LOADABLE_YOY_AND_TREND"))
    result = pd.DataFrame({
        "symbol": out["symbol"], "statement": out["statement"], "line_item_id": out["line_item_id"], "fiscal_period_type": out["fiscal_period_type"],
        "current_period": out["period_end"], "prior_period": out["prior_period_end"],
        "current_fact_id": out["normalized_fact_id"], "prior_fact_id": out["prior_normalized_fact_id"],
        "comparison_status": out["comparison_status"], "reason_codes": out["reason_codes"], "model_treatment": out["model_treatment"],
        "current_available_from": out["fmdl3b3_available_from"], "prior_available_from": out["prior_fmdl3b3_available_from"],
        "current_restatement_status": out["restatement_status"], "prior_restatement_status": out["prior_restatement_status"],
        "trade_authority": "NONE",
    })
    result.insert(0, "comparison_id", [stable_hash({"symbol": a, "statement": b, "line": c, "type": d, "current": e, "prior": f}) for a,b,c,d,e,f in zip(result["symbol"], result["statement"], result["line_item_id"], result["fiscal_period_type"], result["current_period"], result["prior_period"])])
    return result.reset_index(drop=True)
