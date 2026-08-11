from __future__ import annotations

import json
from pathlib import Path

from automation.wp3_2a import acquire_universe


def test_eastmoney_uses_benchmark_timestamp_when_row_timestamps_missing(monkeypatch, tmp_path: Path) -> None:
    clist = {
        "data": {
            "total": 1,
            "diff": [
                {
                    "f2": 10.0,
                    "f3": 0.0,
                    "f4": 0.0,
                    "f5": 100,
                    "f6": 1000,
                    "f12": "600000",
                    "f13": 1,
                    "f14": "浦发银行",
                    "f124": None,
                }
            ],
        }
    }
    probe = {"data": {"f57": "000001", "f58": "上证指数", "f86": 1786345200}}

    def fake_request(url: str, params: dict[str, str], timeout: int):
        if "clist/get" in url:
            return json.dumps(clist).encode("utf-8"), "https://example.test/clist"
        if "stock/get" in url:
            return json.dumps(probe).encode("utf-8"), "https://example.test/probe"
        raise AssertionError(url)

    monkeypatch.setattr(acquire_universe, "request_bytes", fake_request)
    rows, meta = acquire_universe.eastmoney(tmp_path, page_size=500, timeout=5)

    assert meta["derived_session"] == "2026-08-10"
    assert meta["derived_session_ratio"] == 1.0
    assert meta["freshness_authority"] == "PROVIDER_BENCHMARK_TIMESTAMP_F86"
    assert meta["session_probe"]["status"] == "PASS"
    assert rows[0]["provider_session_date"] == "2026-08-10"
