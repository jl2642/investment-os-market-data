from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import jsonschema

from scripts.run_fmdl3a_benchmark_v6 import clean_title, next_trading_open, parse_period

ROOT = Path(__file__).resolve().parents[1]


def load_json(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_config_schema() -> None:
    config = load_json("config/fmdl3a_benchmark.json")
    schema = load_json("schemas/fmdl3a_benchmark.schema.json")
    jsonschema.validate(config, schema, format_checker=jsonschema.FormatChecker())


def test_sample_covers_profiles_and_boards() -> None:
    config = load_json("config/fmdl3a_benchmark.json")
    samples = config["sample_design"]["symbols"]
    assert set(config["sample_design"]["minimum_profiles"]) <= {item["profile"] for item in samples}
    assert set(config["sample_design"]["minimum_boards"]) <= {item["board"] for item in samples}
    assert len({item["symbol"] for item in samples}) == len(samples)
    assert len([item for item in samples if item["board"] == "BSE"]) == 2


def test_required_source_routes_present() -> None:
    config = load_json("config/fmdl3a_benchmark.json")
    source_ids = {item["source_id"] for item in config["source_candidates"]}
    assert {
        "CNINFO_OFFICIAL_DISCLOSURE",
        "EASTMONEY_NOTICE_FALLBACK",
        "EASTMONEY_STATEMENTS",
        "EASTMONEY_BSE_PERIODIC_STATEMENTS",
        "SINA_STATEMENTS",
        "FMDL1_ACCEPTED_CURRENT_PRICE",
        "EASTMONEY_EFFECTIVE_SHARE_CAPITAL",
        "COMPOSITE_CURRENT_CAPITALIZATION",
        "EASTMONEY_INDIVIDUAL_INFO",
        "XUEQIU_CURRENT_VALUATION",
        "EASTMONEY_CURRENT_VALUATION",
        "EASTMONEY_HISTORICAL_VALUATION",
        "EASTMONEY_SHARE_CAPITAL",
        "EASTMONEY_DIVIDENDS",
        "EASTMONEY_BUYBACKS",
    } <= source_ids


def test_support_and_quarantine_gates() -> None:
    config = load_json("config/fmdl3a_benchmark.json")
    policy = config["acceptance_policy"]
    samples = config["sample_design"]["symbols"]
    expected_bse_ratio = len([item for item in samples if item["board"] == "BSE"]) / len(samples)
    assert policy["minimum_sh_sz_statement_bundle_success_ratio"] >= 0.95
    assert policy["minimum_supported_universe_statement_bundle_success_ratio"] >= 0.95
    assert policy["maximum_full_sample_statement_quarantine_ratio"] >= expected_bse_ratio
    assert policy["maximum_full_sample_statement_quarantine_ratio"] <= 0.16
    assert policy["minimum_supported_universe_current_capitalization_coverage"] >= 0.95
    assert policy["require_all_symbols_supported_or_quarantined"] is True
    assert policy["require_bse_official_document_source"] is True
    assert policy["require_each_profile_supported_or_quarantined"] is True
    assert policy["require_each_board_supported_or_quarantined"] is True
    assert policy["require_zero_future_effective_share_count"] is True


def test_recomputed_valuation_and_capitalization_semantics() -> None:
    semantics = load_json("config/fmdl3a_benchmark.json")["valuation_semantics"]
    assert semantics["current_capitalization_rule"] == "FMDL1_ACCEPTED_CLOSE_MULTIPLIED_BY_LATEST_EFFECTIVE_SHARE_COUNT_NOT_LATER_THAN_PRICE_AS_OF_DATE"
    assert semantics["provider_pe_pb_role"] == "SUPPORT_ONLY_NOT_DECISION_GRADE"
    assert semantics["decision_grade_pe_pb_rule"] == "RECOMPUTE_IN_FMDL3D_USING_POINT_IN_TIME_FINANCIAL_DENOMINATORS"
    assert semantics["negative_or_invalid_denominator_rule"] == "PUBLISH_NOT_MEANINGFUL_STATUS_NOT_SYNTHETIC_RATIO"
    assert {"LATEST_COMPLETED_SESSION_CLOSE", "TOTAL_MARKET_CAP", "FLOAT_MARKET_CAP", "TOTAL_SHARES", "FLOAT_A_SHARES"} <= set(semantics["current_market_numerators"])
    assert (ROOT / "outputs/current/DAILY_MARKET_SNAPSHOT.csv").exists()


def test_point_in_time_policy_is_conservative() -> None:
    config = load_json("config/fmdl3a_benchmark.json")
    policy = config["availability_policy"]
    assert policy["resolution"] == "DAILY"
    assert policy["date_only_rule"] == "NEXT_TRADING_SESSION_OPEN"
    assert policy["timestamp_rule"] == "NEXT_TRADING_SESSION_OPEN"
    assert policy["period_end_never_implies_availability"] is True
    assert config["acceptance_policy"]["require_zero_future_availability"] is True


def test_title_period_parser_cleans_cninfo_highlight_html() -> None:
    assert clean_title("贵州茅台2025年年度<em>报告</em>") == "贵州茅台2025年年度报告"
    assert parse_period("贵州茅台2025年年度<em>报告</em>") == "2025-12-31"
    assert parse_period("平安银行2025年第一季度报告") == "2025-03-31"
    assert parse_period("中国平安2025年半年度报告（修订版）") == "2025-06-30"
    assert parse_period("中信证券2025年第三季度报告") == "2025-09-30"
    assert parse_period("贵州茅台2025年年度报告摘要") is None


def test_next_trading_open() -> None:
    calendar = [date(2026, 7, 16), date(2026, 7, 17), date(2026, 7, 20)]
    assert next_trading_open(date(2026, 7, 17), calendar, "09:30:00") == "2026-07-20T09:30:00+08:00"


def test_authority_boundary() -> None:
    config = load_json("config/fmdl3a_benchmark.json")
    assert config["authority"] == "DATA_AND_RESEARCH_EVIDENCE_ONLY"
    assert config["trade_authority"] == "NONE"
    assert config["acceptance_policy"]["trade_authority"] == "NONE"
