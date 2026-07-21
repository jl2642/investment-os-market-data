from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "scripts/run_fmdl5b2_issuer_semantics.py"
spec = importlib.util.spec_from_file_location("fmdl5b2", MODULE_PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_normalized_issuer_name_merges_only_explicit_suffixes() -> None:
    assert module.normalized_issuer_name("Swire Pacific Ltd. 'A'") == "Swire Pacific Ltd."
    assert module.normalized_issuer_name("Swire Pacific Ltd. 'B'") == "Swire Pacific Ltd."
    assert module.normalized_issuer_name("Alibaba Group Holding Ltd. - W") == "Alibaba Group Holding Ltd."
    assert module.normalized_issuer_name("ZTE Corporation - H Shares") == "ZTE Corporation"


def test_official_suffix_flags() -> None:
    assert module.official_suffix_flags("MEITUAN-W") == {
        "wvr_flag": True,
        "secondary_listing_flag": False,
        "biotech_chapter18a_flag": False,
    }
    assert module.official_suffix_flags("EXAMPLE-SW")["secondary_listing_flag"] is True
    assert module.official_suffix_flags("MABWELL-B")["biotech_chapter18a_flag"] is True


def test_security_type_uses_official_category() -> None:
    assert module.security_type("Equity", "Equity Securities (Main Board)") == "COMMON_EQUITY"
    assert module.security_type("Exchange Traded Products", "Exchange Traded Funds") == "ETF"
    assert module.security_type("Real Estate Investment Trusts", "") == "REIT"


def test_parse_di_html_uses_official_sid_and_name() -> None:
    html = b'<a href="NSAllSSList.aspx?sid=6893&corpn=Tencent+Holdings+Ltd.&sc=00700">report</a>'
    row = module.parse_di_html("00700", html, "https://example.test/?sc=00700")
    assert row["di_sid"] == "6893"
    assert row["official_issuer_name_en"] == "Tencent Holdings Ltd."
    assert len(row["response_sha256"]) == 64


def test_h_share_and_code_helpers() -> None:
    assert module.h_share_flag("ZTE Corporation - H Shares") is True
    assert module.h_share_flag("Tencent Holdings Ltd.") is False
    assert module.code5("700") == "00700"
    assert module.optional_code5(80700.0) == "80700"
