import pandas as pd
import pytest
from scripts.run_occ_r2a_exact_continuation import build_capitalization


def inputs():
    u=pd.DataFrame([{"symbol":s,"name":s,"exchange":"SH","board":"SH_MAIN","as_of_date":"2026-11-26"} for s in ["600000.SH","600001.SH","600002.SH"]])
    s=u[["symbol","as_of_date"]].copy()
    s["close"]=[20,None,30]
    s["data_status"]=["TRADED","NO_DATA","TRADED"]
    s["record_quality"]=["VALID","PARTIAL","VALID"]
    s["row_hash"]=["p1","p2","p3"]
    ledger=pd.DataFrame([{"symbol":"600000.SH","source_effective_date":d,"source_row_hash":h,"total_shares":t,"float_a_shares":f,"source_id":"existing","trade_authority":"NONE"} for d,h,t,f in [("2026-11-18","a",100,90),("2026-11-24","b",200,180),("2026-11-27","c",400,360)]])
    release={"as_of_date":"2026-11-26","run_id":"accepted","dataset_versions":{"a_share_universe":"u","daily_market_snapshot":"s"}}
    return u,s,ledger,release,{"contract_version":"1.0.0"}


def test_exact_candidate_keeps_all_symbols_and_known_effective_shares():
    c=build_capitalization(*inputs()).set_index("symbol")
    assert len(c)==3
    assert c.loc["600000.SH","total_market_cap_cny"]==4000
    assert c.loc["600000.SH","share_source_row_hash"]=="b"
    assert c.loc["600001.SH","capitalization_state"]=="PRICE_UNAVAILABLE"
    assert c.loc["600002.SH","capitalization_state"]=="NO_EFFECTIVE_SHARE_ROW"
    assert pd.isna(c.loc["600002.SH","total_market_cap_cny"])
    assert set(c.trade_authority)=={"NONE"}


def test_candidate_rejects_duplicate_market_and_ledger_keys():
    u,s,l,r,c=inputs()
    with pytest.raises(ValueError,match="MARKET_MEMBERSHIP"):
        build_capitalization(u,pd.concat([s,s]),l,r,c)
    with pytest.raises(ValueError,match="DUPLICATE_LEDGER"):
        build_capitalization(u,s,pd.concat([l,l]),r,c)
