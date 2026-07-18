import json
from datetime import date
from pathlib import Path

import pandas as pd
from jsonschema import Draft202012Validator

from scripts import fmdl3b_core as core

ROOT = Path(__file__).resolve().parents[1]


def test_contract_schema():
    cfg = json.loads((ROOT / "config/fmdl3b_statement_store.json").read_text(encoding="utf-8"))
    schema = json.loads((ROOT / "schemas/fmdl3b_statement_store.schema.json").read_text(encoding="utf-8"))
    assert list(Draft202012Validator(schema).iter_errors(cfg)) == []
    assert cfg["trade_authority"] == "NONE"


def test_registry_unique_aliases():
    registry = json.loads((ROOT / "config/fmdl3b_field_registry.json").read_text(encoding="utf-8"))
    seen = set()
    for field in registry["fields"]:
        for alias in field["aliases"]:
            key = (field["statement"], core.normalize_alias(alias))
            assert key not in seen
            seen.add(key)


def test_period_labels_and_signs():
    assert core.fiscal_period_type("2025-03-31") == ("Q1", "ytd", "Q1-2025")
    assert core.fiscal_period_type("2025-12-31") == ("FY", "annual", "FY2025")
    assert core.apply_sign(10, "NEGATIVE_ABS") == -10
    assert core.apply_sign(-10, "POSITIVE_ABS") == 10


def test_next_trading_session_is_strictly_after_announcement():
    days = [date(2026, 7, 17), date(2026, 7, 20), date(2026, 7, 21)]
    assert core.next_trading_open("2026-07-17", days) == "2026-07-20T09:30:00+08:00"


def test_revision_intervals_do_not_overlap():
    filings = [
        {"symbol": "600000.SH", "report_period_end": "2025-12-31", "announcement_date": "2026-03-20", "announcement_timestamp_raw": "2026-03-20T00:00:00", "filing_title": "2025年报", "source_id": "SRC-1"},
        {"symbol": "600000.SH", "report_period_end": "2025-12-31", "announcement_date": "2026-04-01", "announcement_timestamp_raw": "2026-04-01T00:00:00", "filing_title": "2025年报修订版", "source_id": "SRC-1"},
    ]
    days = [date(2026, 3, 23), date(2026, 4, 2), date(2026, 4, 3)]
    rows = core.build_revision_intervals(filings, days, "09:30:00")
    assert rows[0]["superseded_at"] == rows[1]["available_from"]
    assert rows[1]["superseded_at"] is None


def test_normalization_prefers_primary_and_classifies_conflict():
    _, registry_payload = core.load_registry(ROOT / "config/fmdl3b_field_registry.json")
    raw = pd.DataFrame([
        {"symbol": "600000.SH", "entity": "X", "profile": "GENERAL_NON_FINANCIAL", "board": "SH_MAIN", "source_id": "SRC-EASTMONEY-1", "source_route_id": "EASTMONEY_STATEMENTS", "statement": "income_statement", "report_period_end": "2025-12-31", "canonical_field_id": "revenue", "canonical_field_name": "Revenue", "provider_field_name": "OPERATE_INCOME", "source_value": 100.0, "currency": "CNY", "source_location": "a", "evidence_label": "fact_provider_standardized", "confidence": "high", "announcement_date": "2026-03-01", "announcement_timestamp_raw": "2026-03-01", "available_from": "2026-03-02T09:30:00+08:00", "source_retrieved_at": "2026-07-18", "revision_sequence": 1, "effective_from": "2026-03-02T09:30:00+08:00", "superseded_at": None},
        {"symbol": "600000.SH", "entity": "X", "profile": "GENERAL_NON_FINANCIAL", "board": "SH_MAIN", "source_id": "SRC-SINA-1", "source_route_id": "SINA_STATEMENTS", "statement": "income_statement", "report_period_end": "2025-12-31", "canonical_field_id": "revenue", "canonical_field_name": "Revenue", "provider_field_name": "营业收入", "source_value": 101.0, "currency": "CNY", "source_location": "b", "evidence_label": "fact_provider_standardized", "confidence": "medium", "announcement_date": "2026-03-01", "announcement_timestamp_raw": "2026-03-01", "available_from": "2026-03-02T09:30:00+08:00", "source_retrieved_at": "2026-07-18", "revision_sequence": 1, "effective_from": "2026-03-02T09:30:00+08:00", "superseded_at": None},
    ])
    normalized, conflicts = core.select_normalized_facts(raw, registry_payload, 1e-6, 0.1)
    assert len(normalized) == 1
    assert len(conflicts) == 1
    assert normalized.iloc[0]["record_quality"] == "CONFLICTED_AUDIT_ONLY"
