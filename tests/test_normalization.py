from datetime import date

import pandas as pd

from ingestion.akshare.client import AkshareBundle, SourceCall
from pipeline.normalize import normalize_a_share_bundle


def _call(name: str, data: pd.DataFrame) -> SourceCall:
    return SourceCall(function=name, data=data)


def test_normalization_maps_markets_and_units() -> None:
    spot = pd.DataFrame([
        {"代码": "600000", "名称": "浦发银行", "最新价": 10.0, "昨收": 9.9, "涨跌幅": 1.01, "成交量": 1000, "成交额": 1_000_000, "今开": 9.9, "最高": 10.1, "最低": 9.8, "振幅": 3.03, "换手率": 0.2, "总市值": 1e11, "流通市值": 9e10, "市盈率-动态": 6.0, "市净率": 0.6},
        {"代码": "300001", "名称": "特锐德", "最新价": 20.0, "昨收": 20.0, "涨跌幅": 0.0, "成交量": 10, "成交额": 20_000, "今开": 20.0, "最高": 20.0, "最低": 20.0, "振幅": 0.0, "换手率": 0.1, "总市值": 2e10, "流通市值": 1.8e10, "市盈率-动态": 20.0, "市净率": 2.0},
        {"代码": "832000", "名称": "北交样本", "最新价": None, "昨收": None, "涨跌幅": None, "成交量": None, "成交额": None},
    ])
    bundle = AkshareBundle(
        spot=_call("stock_zh_a_spot_em", spot),
        sh_main=_call("sh", pd.DataFrame([{"证券代码": "600000", "证券简称": "浦发银行", "上市日期": "1999-11-10"}])),
        sh_star=_call("star", pd.DataFrame()),
        sz_a=_call("sz", pd.DataFrame([{"A股代码": "300001", "A股简称": "特锐德", "A股上市日期": "2009-10-30", "所属行业": "电气机械"}])),
        bj_a=_call("bj", pd.DataFrame([{"证券代码": "832000", "证券简称": "北交样本", "上市日期": "2021-01-01", "所属行业": "制造业"}])),
        trade_calendar=_call("calendar", pd.DataFrame([{"trade_date": "2026-07-16"}])),
        adapter_version="test",
    )
    result = normalize_a_share_bundle(bundle, as_of_date=date(2026, 7, 16), source_timestamp="2026-07-16T17:30:00+08:00")
    universe = result.universe.set_index("symbol")
    snapshot = result.snapshot.set_index("symbol")
    assert universe.loc["600000.SH", "board"] == "SH_MAIN"
    assert universe.loc["300001.SZ", "board"] == "CHINEXT"
    assert universe.loc["832000.BJ", "board"] == "BSE"
    assert snapshot.loc["600000.SH", "volume_shares"] == 100_000
    assert snapshot.loc["832000.BJ", "data_status"] == "SUSPENDED"
