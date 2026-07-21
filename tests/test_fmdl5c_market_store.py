from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "scripts/run_fmdl5c_market_store.py"
spec = importlib.util.spec_from_file_location("fmdl5c", MODULE_PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_yahoo_symbol_uses_four_digit_hk_code() -> None:
    assert module.yahoo_symbol("00005") == "0005.HK"
    assert module.yahoo_symbol("00700") == "0700.HK"
    assert module.yahoo_symbol("09988") == "9988.HK"


def test_parse_yahoo_payload_preserves_raw_and_adjusted_price() -> None:
    payload = {
        "chart": {
            "result": [
                {
                    "meta": {"currency": "HKD"},
                    "timestamp": [1784511000],
                    "indicators": {
                        "quote": [{"open": [10.0], "high": [11.0], "low": [9.5], "close": [10.5], "volume": [1000]}],
                        "adjclose": [{"adjclose": [10.2]}],
                    },
                    "events": {
                        "dividends": {"1": {"date": 1784511000, "amount": 0.5, "formatted_date": "2026-07-20"}},
                        "splits": {},
                    },
                }
            ],
            "error": None,
        }
    }
    rows, actions, summary = module.parse_yahoo_payload(
        security_id="HKEX:00700",
        code="00700",
        payload=payload,
        response_sha256="a" * 64,
        retrieved_at_utc="2026-07-21T00:00:00+00:00",
    )
    assert rows[0]["close"] == 10.5
    assert rows[0]["adj_close"] == 10.2
    assert rows[0]["provider_ticker"] == "0700.HK"
    assert actions[0]["action_type"] == "CASH_DIVIDEND"
    assert summary["row_count"] == 1


def test_parse_eastmoney_klines() -> None:
    payload = {"data": {"klines": ["2026-07-20,10.0,10.5,11.0,9.5,1000,10500,1.0,5.0,0.5,0.2"]}}
    rows, summary = module.parse_eastmoney_klines(
        security_id="HKEX:00700",
        code="00700",
        payload=payload,
        response_sha256="b" * 64,
        retrieved_at_utc="2026-07-21T00:00:00+00:00",
    )
    assert rows[0]["open"] == 10.0
    assert rows[0]["close"] == 10.5
    assert rows[0]["provider"] == "EASTMONEY_PUSH2HIS"
    assert summary["latest_date"] == "2026-07-20"


def test_code_and_numeric_helpers() -> None:
    assert module.code5("700") == "00700"
    assert module.finite_number("1.25") == 1.25
    assert module.finite_number("nan") is None


def test_publisher_boundaries_are_zero_mutation_constants() -> None:
    contract = module.json.loads((Path(__file__).parents[1] / "config/fmdl5c_price_volume_corporate_action_fx_contract.json").read_text())
    acceptance = contract["acceptance"]
    assert acceptance["candidate_pool_mutation_count"] == 0
    assert acceptance["simulation_mutation_count"] == 0
    assert acceptance["real_account_mutation_count"] == 0
    assert acceptance["order_generation_count"] == 0
    assert acceptance["trade_authority"] == "NONE"
