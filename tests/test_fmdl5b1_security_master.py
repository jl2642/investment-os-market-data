from scripts.run_fmdl5b1_security_master import build_row, classify_security


def sample(**overrides):
    row = {
        "stock_code": "00700",
        "name_cn": "腾讯控股",
        "name_en": "TENCENT",
        "shanghai_connect": "True",
        "shenzhen_connect": "True",
        "eligibility_status": "BUY_AND_SELL_ELIGIBLE",
    }
    row.update(overrides)
    return row


def test_identity_is_deterministic():
    row = build_row(sample())
    assert row["security_id"] == "HKEX:00700"
    assert row["issuer_id"] == "HKISSUER-PROVISIONAL:00700"
    assert row["ticker_hk"] == "00700.HK"


def test_unknown_is_not_overclassified():
    security_type, status = classify_security("腾讯控股", "TENCENT")
    assert security_type == "UNKNOWN"
    assert status == "PENDING_SEMANTIC_ENRICHMENT"


def test_etf_marker_classification():
    assert classify_security("恒生科技ETF", "HSTECH ETF") == ("ETF", "NAME_MARKER_CLASSIFIED")


def test_reit_marker_classification():
    assert classify_security("某房产信托", "SAMPLE REIT") == ("REIT", "NAME_MARKER_CLASSIFIED")


def test_connect_flags_are_boolean():
    row = build_row(sample(shanghai_connect="true", shenzhen_connect="1"))
    assert row["shanghai_connect"] is True
    assert row["shenzhen_connect"] is True
