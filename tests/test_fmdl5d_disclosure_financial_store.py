from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from fmdl5d_core import (  # noqa: E402
    assign_filing_periods,
    classify_filing,
    latest_filing_map,
    load_field_registry,
    map_line_item,
    next_trading_open,
    normalize_raw_facts,
    parse_period_end_from_title,
)


def test_title_classification_and_period_parsing() -> None:
    title = "INTERIM RESULTS FOR THE SIX MONTHS ENDED 30 JUNE 2025 (UPDATED)"
    filing_type, revised = classify_filing(title)
    assert filing_type == "INTERIM_RESULTS"
    assert revised is True
    assert parse_period_end_from_title(title) == "2025-06-30"
    assert parse_period_end_from_title("ANNUAL RESULTS FOR YEAR ENDED DECEMBER 31 2025") == "2025-12-31"


def test_next_trading_open_is_strictly_later() -> None:
    days = [date(2025, 6, 30), date(2025, 7, 2), date(2025, 7, 3)]
    assert next_trading_open("2025-06-30", days) == "2025-07-02T09:30:00+08:00"
    assert next_trading_open("2025-07-03", days) is None


def test_exact_alias_mapping() -> None:
    registry, _ = load_field_registry(ROOT / "config/fmdl5d_hk_financial_field_registry.json")
    mapped = map_line_item("income_statement", "", "本公司拥有人应占溢利", registry)
    assert mapped and mapped["field_id"] == "net_income_parent"
    assert map_line_item("income_statement", "", "unsupported item", registry) is None


def test_filing_assignment_revision_chain_and_normalized_lineage() -> None:
    filings = [
        {
            "news_id": "1",
            "stock_code_5d": "00700",
            "title": "ANNUAL RESULTS FOR THE YEAR ENDED 31 DECEMBER 2025",
            "category": "Announcements and Notices - [Final Results]",
            "release_timestamp": "2026-03-20T17:00:00+08:00",
            "filing_url": "https://example/1.pdf",
        },
        {
            "news_id": "2",
            "stock_code_5d": "00700",
            "title": "SUPPLEMENTAL ANNUAL RESULTS FOR THE YEAR ENDED 31 DECEMBER 2025",
            "category": "Announcements and Notices - [Final Results]",
            "release_timestamp": "2026-03-25T17:00:00+08:00",
            "filing_url": "https://example/2.pdf",
        },
    ]
    assigned = assign_filing_periods(
        filings,
        {"00700": ["2025-12-31", "2025-06-30"]},
        {"00700": "12-31"},
        [date(2026, 3, 20), date(2026, 3, 23), date(2026, 3, 25), date(2026, 3, 26)],
    )
    assert [row["revision_sequence"] for row in assigned] == [1, 2]
    assert assigned[0]["superseded_at"] == "2026-03-26T09:30:00+08:00"
    latest = latest_filing_map(assigned)
    raw = [
        {
            "raw_fact_id": "raw",
            "security_id": "HKEX:00700",
            "issuer_id": "HKEX-ISSUER:test",
            "stock_code_5d": "00700",
            "official_security_name_en": "TENCENT",
            "official_issuer_name_en": "Tencent Holdings Ltd.",
            "profile": "GENERAL_NON_FINANCIAL",
            "statement": "income_statement",
            "period_end": "2025-12-31",
            "field_id": "revenue",
            "field_name": "Revenue",
            "source_item_code": "",
            "source_item_name": "收入",
            "source_value": 100.0,
            "currency": "CNY",
            "units": "CNY_ONES",
            "sign_rule": "AS_REPORTED",
            "mapping_status": "MAPPED_EXACT_NORMALIZED_ALIAS",
            "mapping_priority": 1,
            "source_id": "EASTMONEY_HK_FINANCIAL_REPORT",
            "source_tier": "UNOFFICIAL_FREE_VENDOR_STRUCTURED",
            "source_adapter": "test",
            "source_location": "test",
            "source_response_sha256": "a" * 64,
            "source_retrieved_at": "2026-03-26T00:00:00+00:00",
            "trade_authority": "NONE",
        }
    ]
    normalized = normalize_raw_facts(raw, latest)
    assert normalized[0]["official_filing_url"] == "https://example/2.pdf"
    assert normalized[0]["revision_sequence"] == 2
    assert normalized[0]["decision_grade_eligible"] is True
    assert normalized[0]["trade_authority"] == "NONE"


def test_contract_has_zero_state_mutation_and_no_trade_authority() -> None:
    contract = json.loads((ROOT / "config/fmdl5d_hkex_disclosure_financial_contract.json").read_text(encoding="utf-8"))
    acceptance = contract["acceptance"]
    assert acceptance["candidate_pool_mutation_count"] == 0
    assert acceptance["simulation_mutation_count"] == 0
    assert acceptance["real_account_mutation_count"] == 0
    assert acceptance["order_generation_count"] == 0
    assert acceptance["trade_authority"] == "NONE"
