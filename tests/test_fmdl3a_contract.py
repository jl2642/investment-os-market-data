from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import jsonschema

from scripts.run_fmdl3a_benchmark import next_open, parse_period

ROOT = Path(__file__).resolve().parents[1]


def load_json(path: str) -> dict:
    with (ROOT / path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def test_config_schema() -> None:
    config = load_json("config/fmdl3a_benchmark.json")
    schema = load_json("schemas/fmdl3a_benchmark.schema.json")
    jsonschema.validate(config, schema)


def test_sample_covers_profiles_and_boards() -> None:
    config = load_json("config/fmdl3a_benchmark.json")
    samples = config["sample_design"]["symbols"]
    profiles = {item["profile"] for item in samples}
    boards = {item["board"] for item in samples}
    assert set(config["sample_design"]["minimum_profiles"]) <= profiles
    assert set(config["sample_design"]["minimum_boards"]) <= boards
    assert len({item["symbol"] for item in samples}) == len(samples)


def test_required_source_families_present() -> None:
    config = load_json("config/fmdl3a_benchmark.json")
    source_ids = {item["source_id"] for item in config["source_candidates"]}
    assert {
        "CNINFO_OFFICIAL_DISCLOSURE",
        "EASTMONEY_NOTICE_FALLBACK",
        "EASTMONEY_STATEMENTS",
        "SINA_STATEMENTS",
        "EASTMONEY_CURRENT_VALUATION",
        "EASTMONEY_HISTORICAL_VALUATION",
        "EASTMONEY_SHARE_CAPITAL",
        "EASTMONEY_DIVIDENDS",
        "EASTMONEY_BUYBACKS",
    } <= source_ids


def test_point_in_time_policy_is_conservative() -> None:
    config = load_json("config/fmdl3a_benchmark.json")
    policy = config["availability_policy"]
    assert policy["resolution"] == "DAILY"
    assert policy["date_only_rule"] == "NEXT_TRADING_SESSION_OPEN"
    assert policy["timestamp_rule"] == "NEXT_TRADING_SESSION_OPEN"
    assert policy["period_end_never_implies_availability"] is True
    assert config["acceptance_policy"]["require_zero_future_availability"] is True


def test_title_period_parser() -> None:
    assert parse_period("贵州茅台2025年年度报告") == "2025-12-31"
    assert parse_period("平安银行2025年第一季度报告") == "2025-03-31"
    assert parse_period("中国平安2025年半年度报告（修订版）") == "2025-06-30"
    assert parse_period("中信证券2025年第三季度报告") == "2025-09-30"
    assert parse_period("贵州茅台2025年年度报告摘要") is None


def test_next_trading_open() -> None:
    calendar = [date(2026, 7, 16), date(2026, 7, 17), date(2026, 7, 20)]
    assert next_open(date(2026, 7, 17), calendar, "09:30:00") == "2026-07-20T09:30:00+08:00"


def test_authority_boundary() -> None:
    config = load_json("config/fmdl3a_benchmark.json")
    assert config["authority"] == "DATA_AND_RESEARCH_EVIDENCE_ONLY"
    assert config["trade_authority"] == "NONE"
    assert config["acceptance_policy"]["trade_authority"] == "NONE"
