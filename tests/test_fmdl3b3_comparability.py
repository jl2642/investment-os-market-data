from __future__ import annotations

import pandas as pd

from scripts import fmdl3b3_core as core


def test_document_classification_excludes_ancillary_disclosures():
    assert core.classify_document("2024年年度报告") == "PERIODIC_REPORT_FULL"
    assert core.classify_document("2024年年度报告（更正后）", True) == "PERIODIC_REPORT_CORRECTED_FULL"
    assert core.classify_document("关于2024年年度报告的更正公告", True) == "PERIODIC_REPORT_CORRECTION_NOTICE"
    assert core.classify_document("2024年年度报告业绩说明会预告公告") == "ANCILLARY_DISCLOSURE"
    assert core.classify_document("保荐机构关于2024年度持续督导年度报告书") == "ANCILLARY_DISCLOSURE"


def test_authoritative_revision_chain_ignores_ancillary_and_blocks_pre_restatement_replay():
    frame = pd.DataFrame([
        {"symbol": "000001.SZ", "report_period_end": "2024-12-31", "announcement_date": "2025-03-20", "announcement_timestamp_raw": "2025-03-20T00:00:00", "filing_title": "2024年年度报告", "revision_id": "r1", "available_from": "2025-03-21T09:30:00+08:00", "is_revision": False},
        {"symbol": "000001.SZ", "report_period_end": "2024-12-31", "announcement_date": "2025-03-25", "announcement_timestamp_raw": "2025-03-25T00:00:00", "filing_title": "2024年年度报告业绩说明会预告公告", "revision_id": "a1", "available_from": "2025-03-26T09:30:00+08:00", "is_revision": False},
        {"symbol": "000001.SZ", "report_period_end": "2024-12-31", "announcement_date": "2025-04-01", "announcement_timestamp_raw": "2025-04-01T00:00:00", "filing_title": "2024年年度报告（更正后）", "revision_id": "r2", "available_from": "2025-04-02T09:30:00+08:00", "is_revision": True}
    ])
    docs, periods = core.build_authoritative_revision_lineage(frame)
    canonical = docs[docs["is_canonical_periodic_document"]]
    assert list(canonical["revision_id"]) == ["r1", "r2"]
    assert list(canonical["canonical_revision_sequence"].astype(int)) == [1, 2]
    status = periods.iloc[0]
    assert status["restatement_status"] == "RESTATED_OR_CORRECTED"
    assert status["latest_canonical_revision_id"] == "r2"
    assert status["historical_replay_status"] == "LATEST_ONLY_PRE_RESTATEMENT_NUMERIC_REPLAY_BLOCKED"


def _overlay_row(fact_id: str, period: str, restatement: str = "ORIGINAL_ONLY", eligible: bool = True):
    return {
        "normalized_fact_id": fact_id,
        "symbol": "000001.SZ",
        "statement": "income_statement",
        "line_item_id": "revenue",
        "period_end": period,
        "fiscal_period_type": "FY",
        "basis": "reported_annual",
        "line_item_original": "OPERATE_INCOME",
        "source_route_id": "EASTMONEY_STATEMENTS",
        "currency": "CNY",
        "units": "CNY_ONES",
        "fmdl3b3_decision_grade_eligible": eligible,
        "restatement_status": restatement,
        "fmdl3b3_available_from": f"{int(period[:4])+1}-04-01T09:30:00+08:00"
    }


def test_comparison_default_and_restatement_warning_and_block():
    comparable = core.build_comparability_bridge(pd.DataFrame([
        _overlay_row("a", "2023-12-31"), _overlay_row("b", "2024-12-31")
    ]))
    assert comparable.iloc[0]["comparison_status"] == "COMPARABLE"
    warning = core.build_comparability_bridge(pd.DataFrame([
        _overlay_row("a", "2023-12-31"), _overlay_row("b", "2024-12-31", "RESTATED_OR_CORRECTED")
    ]))
    assert warning.iloc[0]["comparison_status"] == "COMPARABLE_WITH_WARNING"
    assert "RESTATEMENT_LATEST_ONLY_HISTORY" in warning.iloc[0]["reason_codes"]
    blocked = core.build_comparability_bridge(pd.DataFrame([
        _overlay_row("a", "2023-12-31"), _overlay_row("b", "2024-12-31", eligible=False)
    ]))
    assert blocked.iloc[0]["comparison_status"] == "NOT_COMPARABLE"
    assert blocked.iloc[0]["model_treatment"] == "BLOCK_YOY_AND_TREND"
