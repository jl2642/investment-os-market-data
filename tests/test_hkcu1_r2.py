from __future__ import annotations

from io import BytesIO

import pandas as pd
import pytest

from pipeline.hkcu1_fetch_official_lists import parse_sse_excel
from pipeline.hkcu1_reconstruct_eligibility import reconstruct


def _xlsx(rows: list[dict]) -> bytes:
    buf = BytesIO()
    pd.DataFrame(rows).to_excel(buf, index=False)
    return buf.getvalue()


def test_sse_parser_rejects_html():
    with pytest.raises(ValueError, match="XLS/XLSX"):
        parse_sse_excel(b"<!doctype html><html></html>", 50)


def test_sse_parser_rejects_implausibly_small_list():
    payload = _xlsx([{"证券代码": "00001", "证券简称": "A"}, {"证券代码": "00002", "证券简称": "B"}])
    with pytest.raises(ValueError, match="implausibly small"):
        parse_sse_excel(payload, 50)


def test_sse_parser_standardises_codes():
    payload = _xlsx([{"证券代码": str(i), "证券简称": f"S{i}"} for i in range(1, 61)])
    result = parse_sse_excel(payload, 50)
    assert len(result) == 60
    assert result.iloc[0]["security_code"] == "00001"


def test_point_in_time_applies_only_effective_events():
    snapshot = pd.DataFrame([
        {"security_code": "700", "channel": "SH", "eligibility_side": "BUY_SELL", "effective_from": "2026-07-01", "source_id": "s", "source_sha256": "a"},
        {"security_code": "700", "channel": "SZ", "eligibility_side": "BUY_SELL", "effective_from": "2026-07-01", "source_id": "z", "source_sha256": "b"},
        {"security_code": "5", "channel": "SH", "eligibility_side": "SELL_ONLY", "effective_from": "2026-07-01", "source_id": "s", "source_sha256": "a"},
    ])
    events = pd.DataFrame([
        {"security_code": "700", "channel": "SH", "direction": "OUT", "effective_from": "2026-08-01", "source_id": "e1", "source_sha256": "c"},
        {"security_code": "700", "channel": "SZ", "direction": "OUT", "effective_from": "2026-08-10", "source_id": "future", "source_sha256": "d"},
    ])
    result = reconstruct(snapshot, events, "2026-08-06").set_index("security_code")
    assert result.loc["00700", "combined_status"] == "BUY_ELIGIBLE_SZ_ONLY"
    assert result.loc["00005", "combined_status"] == "SELL_ONLY"


def test_missing_channel_fails_closed_not_false_negative():
    snapshot = pd.DataFrame([
        {"security_code": "700", "channel": "SH", "eligibility_side": "BUY_SELL", "effective_from": "2026-07-01"},
    ])
    result = reconstruct(snapshot, pd.DataFrame(), "2026-08-06").iloc[0]
    assert result["sh_status"] == "BUY_ELIGIBLE"
    assert result["sz_status"] == "UNKNOWN_BLOCKED"
    assert result["combined_status"] == "BUY_ELIGIBLE_SH_ONLY"
