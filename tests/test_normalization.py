from datetime import date

import pandas as pd

from ingestion.akshare.client import AkshareBundle, SourceCall
from pipeline.normalize import normalize_a_share_bundle


def _call(name: str, data: pd.DataFrame, *, volume_unit: str = "NOT_APPLICABLE") -> SourceCall:
    return SourceCall(function=name, data=data, volume_unit=volume_unit)


def _bundle(spot_call: SourceCall) -> AkshareBundle:
    return AkshareBundle(
        spot=spot_call,
        sh_main=_call("sh", pd.DataFrame([{"证券代码": "600000", "证券简称": "浦发银行", "上市日期": "1999-11-10"}])),
        sh_star=_call("star", pd.DataFrame()),
        sz_a=_call("sz", pd.DataFrame([{"A股代码": "300001", "A股简称": "特锐德", "A股上市日期": "2009-10-30", "所属行业": "电气机械"}])),
        bj_a=_call("bj", pd.DataFrame([{"证券代码": "832000", "证券简称": "北交样本", "上市日期": "2021-01-01", "所属行业": "制造业"}])),
        trade_calendar=_call("calendar", pd.DataFrame([{"trade_date": "2026-07-16"}])),
        adapter_version="test",
    )


def test_eastmoney_normalization_maps_markets_and_lots() -> None:
    spot = pd.DataFrame([
        {"代码": "600000", "名称": "浦发银行", "最新价": 10.0, "昨收": 9.9, "涨跌幅": 1.01, "成交量": 1000, "成交额": 1_000_000, "今开": 9.9, "最高": 10.1, "最低": 9.8, "振幅": 3.03, "换手率": 0.2, "总市值": 1e11, "流通市值": 9e10, "市盈率-动态": 6.0, "市净率": 0.6},
        {"代码": "300001", "名称": "特锐德", "最新价": 20.0, "昨收": 20.0, "涨跌幅": 0.0, "成交量": 10, "成交额": 20_000, "今开": 20.0, "最高": 20.0, "最低": 20.0, "振幅": 0.0, "换手率": 0.1, "总市值": 2e10, "流通市值": 1.8e10, "市盈率-动态": 20.0, "市净率": 2.0},
        {"代码": "832000", "名称": "北交样本", "最新价": None, "昨收": None, "涨跌幅": None, "成交量": None, "成交额": None},
    ])
    result = normalize_a_share_bundle(
        _bundle(_call("stock_zh_a_spot_em", spot, volume_unit="LOTS")),
        as_of_date=date(2026, 7, 16),
        source_timestamp="2026-07-16T17:30:00+08:00",
    )
    universe = result.universe.set_index("symbol")
    snapshot = result.snapshot.set_index("symbol")
    assert universe.loc["600000.SH", "board"] == "SH_MAIN"
    assert universe.loc["300001.SZ", "board"] == "CHINEXT"
    assert universe.loc["832000.BJ", "board"] == "BSE"
    assert snapshot.loc["600000.SH", "volume_shares"] == 100_000
    assert snapshot.loc["832000.BJ", "data_status"] == "NO_DATA"
    assert universe.loc["832000.BJ", "listing_status"] == "UNKNOWN"
    assert not universe.loc["832000.BJ", "is_suspended"]


def test_sina_normalization_strips_exchange_prefix_and_preserves_shares() -> None:
    spot = pd.DataFrame([
        {"代码": "sh600000", "名称": "浦发银行", "最新价": 10.0, "昨收": 9.9, "涨跌幅": 1.01, "成交量": 100_000, "成交额": 1_000_000, "今开": 9.9, "最高": 10.1, "最低": 9.8},
        {"代码": "sz300001", "名称": "特锐德", "最新价": 20.0, "昨收": 20.0, "涨跌幅": 0.0, "成交量": 1_000, "成交额": 20_000, "今开": 20.0, "最高": 20.0, "最低": 20.0},
    ])
    result = normalize_a_share_bundle(
        _bundle(_call("stock_zh_a_spot", spot, volume_unit="SHARES")),
        as_of_date=date(2026, 7, 16),
        source_timestamp="2026-07-16T17:30:00+08:00",
    )
    snapshot = result.snapshot.set_index("symbol")
    assert snapshot.loc["600000.SH", "volume_shares"] == 100_000
    assert snapshot.loc["600000.SH", "source_primary"] == "akshare.stock_zh_a_spot"
    assert snapshot.loc["832000.BJ", "data_status"] == "NO_DATA"
    assert pd.isna(snapshot.loc["832000.BJ", "close"])
    assert result.universe.set_index("symbol").loc["832000.BJ", "listing_status"] == "UNKNOWN"
    assert any("volume_unit_source=SHARES" in item for item in result.warnings)


def test_missing_zero_and_master_only_quotes_are_not_suspensions() -> None:
    spot = pd.DataFrame([
        {"代码": "600000", "名称": "浦发银行", "最新价": 10.0, "昨收": 10.0,
         "涨跌幅": 0.0, "成交量": 100, "成交额": 1000.0},
        {"代码": "300001", "名称": "特锐德", "最新价": 0.0, "昨收": 20.0,
         "涨跌幅": 0.0, "成交量": 0, "成交额": 0.0},
    ])
    result = normalize_a_share_bundle(
        _bundle(_call("stock_zh_a_spot", spot, volume_unit="SHARES")),
        as_of_date=date(2026, 7, 16),
        source_timestamp="2026-07-16T17:30:00+08:00",
    )
    u = result.universe.set_index("symbol")
    s = result.snapshot.set_index("symbol")
    for symbol in ("300001.SZ", "832000.BJ"):
        assert s.loc[symbol, "data_status"] == "NO_DATA"
        assert pd.isna(s.loc[symbol, "close"])
        assert u.loc[symbol, "listing_status"] == "UNKNOWN"
        assert not u.loc[symbol, "is_suspended"]
    assert s.loc["600000.SH", "data_status"] == "TRADED"


def test_price_coverage_gate_rejects_placeholder_rows() -> None:
    from pathlib import Path
    from pipeline.quality import evaluate_snapshot

    spot = pd.DataFrame([
        {"代码": "600000", "名称": "浦发银行", "最新价": 10.0, "昨收": 10.0,
         "涨跌幅": 0.0, "成交量": 100, "成交额": 1000.0},
        {"代码": "300001", "名称": "特锐德", "最新价": 20.0, "昨收": 20.0,
         "涨跌幅": 0.0, "成交量": 100, "成交额": 2000.0},
    ])
    result = normalize_a_share_bundle(
        _bundle(_call("stock_zh_a_spot", spot, volume_unit="SHARES")),
        as_of_date=date(2026, 7, 16),
        source_timestamp="2026-07-16T17:30:00+08:00",
    )
    root = Path(__file__).resolve().parents[1]
    quality = evaluate_snapshot(result.snapshot, universe=result.universe, root=root)
    assert quality.metrics["snapshot_symbol_coverage_ratio"] == 1.0
    assert quality.metrics["universe_coverage_ratio"] == 2 / 3
    assert quality.metrics["unpriced_universe_symbol_count"] == 1
    assert "minimum_active_universe_coverage" in quality.hard_failures
    # Even legacy inferred SUSPENDED labels must not disguise absent quotes.
    legacy = result.snapshot.copy()
    legacy.loc[legacy["symbol"] == "832000.BJ", "data_status"] = "SUSPENDED"
    quality = evaluate_snapshot(legacy, universe=result.universe, root=root)
    assert "minimum_active_universe_coverage" in quality.hard_failures

    spot.loc[len(spot)] = {"代码": "832000", "名称": "北交样本", "最新价": 10.0, "昨收": 10.0,
                         "涨跌幅": 0.0, "成交量": 100, "成交额": 1000.0}
    complete = normalize_a_share_bundle(
        _bundle(_call("stock_zh_a_spot", spot, volume_unit="SHARES")),
        as_of_date=date(2026, 7, 16),
        source_timestamp="2026-07-16T17:30:00+08:00",
    )
    quality = evaluate_snapshot(complete.snapshot, universe=complete.universe, root=root)
    assert quality.metrics["universe_coverage_ratio"] == 1.0
    assert "minimum_active_universe_coverage" not in quality.hard_failures


def test_explicit_rate_limit_uses_fallback_without_immediate_retry(monkeypatch) -> None:
    from ingestion.akshare import client

    class Push2RateLimitError(Exception):
        pass

    calls = {"primary": 0, "fallback": 0}

    def primary():
        calls["primary"] += 1
        raise Push2RateLimitError("temporary provider limit")

    def fallback():
        calls["fallback"] += 1
        return pd.DataFrame([{"代码": "sh600000"}])

    monkeypatch.setattr(client.ak, "stock_zh_a_spot_em", primary)
    monkeypatch.setattr(client.ak, "stock_zh_a_spot", fallback)
    monkeypatch.setattr(client.time, "sleep", lambda seconds: (_ for _ in ()).throw(AssertionError("rate limit must not sleep/retry")))
    result = client._fetch_market_wide_spot()
    assert calls == {"primary": 1, "fallback": 1}
    assert result.function == "stock_zh_a_spot"
    assert "explicit_rate_limit_no_immediate_retry" in result.warnings


def test_transient_error_retains_existing_retry(monkeypatch) -> None:
    from ingestion.akshare import client

    calls = []
    sleeps = []

    def source():
        calls.append(True)
        if len(calls) == 1:
            raise RuntimeError("transient")
        return pd.DataFrame([{"代码": "600000"}])

    monkeypatch.setattr(client.time, "sleep", sleeps.append)
    result = client._call_with_retry("test", source, attempts=2, base_sleep_seconds=2)
    assert len(calls) == 2
    assert sleeps == [2]
    assert result.retries == 1


def test_identity_continuity_rejects_replacement_with_equal_row_count():
    from pathlib import Path
    from pipeline.quality import evaluate_universe
    spot = pd.DataFrame([{"代码": "600000", "名称": "浦发银行", "最新价": 10.0,
                          "昨收": 10.0, "涨跌幅": 0.0, "成交量": 100, "成交额": 1000.0}])
    result = normalize_a_share_bundle(_bundle(_call("stock_zh_a_spot", spot, volume_unit="SHARES")),
        as_of_date=date(2026, 7, 16), source_timestamp="2026-07-16T17:30:00+08:00")
    prior = result.universe.copy()
    prior["symbol"] = ["000001.SZ", "000002.SZ", "000003.SZ"]
    q = evaluate_universe(result.universe, root=Path(__file__).resolve().parents[1], lkg_frame=prior)
    assert q.metrics["lkg_row_ratio"] == 1
    assert q.metrics["lkg_identity_retention"] == 0
    assert "minimum_lkg_row_ratio" in q.hard_failures


def test_incident_identity_reference_is_exact_and_fail_closed(tmp_path, monkeypatch):
    import hashlib
    import pytest
    from pipeline import build_candidate as mod

    root = tmp_path / "outputs/current"
    root.mkdir(parents=True)
    u = root / "A_SHARE_UNIVERSE.csv"
    s = root / "DAILY_MARKET_SNAPSHOT.csv"
    u.write_bytes(b"symbol,source_symbol,as_of_date\n600000.SH,600000,2026-11-25\n")
    s.write_bytes(b"bad snapshot")
    payload = b"symbol,source_symbol,as_of_date\n600000.SH,600000,2026-11-24\n"
    digest = lambda b: hashlib.sha256(b).hexdigest()
    monkeypatch.setattr(mod, "_R1_BAD_UNIVERSE_SHA", digest(u.read_bytes()))
    monkeypatch.setattr(mod, "_R1_BAD_SNAPSHOT_SHA", digest(s.read_bytes()))
    monkeypatch.setattr(mod, "_R1_PRIOR_UNIVERSE_SHA", digest(payload))
    monkeypatch.setattr(mod.subprocess, "check_output", lambda *a, **k: payload)
    prior, lineage = mod.resolve_identity_lkg(tmp_path)
    assert lineage["mode"] == "R1_QUALIFIED_IDENTITY_DENOMINATOR"
    assert prior.iloc[0]["as_of_date"] == "2026-11-24"
    s.write_bytes(b"wrong snapshot")
    with pytest.raises(RuntimeError, match="PAIR_MISMATCH"):
        mod.resolve_identity_lkg(tmp_path)
    s.write_bytes(b"bad snapshot")
    monkeypatch.setattr(mod.subprocess, "check_output", lambda *a, **k: b"wrong bytes")
    with pytest.raises(RuntimeError, match="HASH_MISMATCH"):
        mod.resolve_identity_lkg(tmp_path)
    u.write_bytes(payload)
    prior, lineage = mod.resolve_identity_lkg(tmp_path)
    assert lineage["mode"] == "CURRENT"
