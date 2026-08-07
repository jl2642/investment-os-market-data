from pipeline.hkcu1_hkex_crosscheck import parse_hkex_page, validate


def _contract():
    return {
        "hkex_page": {"required_heading": "All Eligible Securities", "max_page_update_lag_days": 3},
        "required_links": {
            "SH": {
                "label_contains": "List of Eligible Securities for Southbound Trading under Shanghai Connect",
                "expected_authority": "SSE",
                "expected_domains": ["sse.com.cn", "sseinfo.com"],
                "expected_landing_url": "https://www.sse.com.cn/services/hkexsc/disclo/eligible/",
            },
            "SZ": {
                "label_contains": "List of Eligible Securities for Southbound Trading under Shenzhen Connect",
                "expected_authority": "SZSE",
                "expected_domains": ["szse.cn"],
                "expected_landing_url": "https://www.szse.cn/szhk/hkbussiness/underlylist/",
            },
        },
    }


def test_hkex_structural_crosscheck_passes_without_claiming_third_row_list():
    html = """
    <html><body>
      <h2>All Eligible Securities</h2>
      <a href="https://www.sse.com.cn/services/hkexsc/disclo/eligible/">List of Eligible Securities for Southbound Trading under Shanghai Connect (stocks eligible for both buy and sell)</a>
      <a href="https://www.szse.cn/szhk/hkbussiness/underlylist/">List of Eligible Securities for Southbound Trading under Shenzhen Connect (stocks eligible for both buy and sell)</a>
      <footer>Updated 06 Aug 2026</footer>
    </body></html>
    """
    parsed = parse_hkex_page(html, "https://www.hkex.com.hk/example", _contract())
    result = validate(parsed, _contract(), "2026-08-07")
    assert result["status"] == "PASS_REFERENCE_CONSISTENT"
    assert result["publication_allowed"] is True
    assert result["security_level_independent_row_list_expected"] is False
    assert result["primary_authority_unchanged"] is True
    assert result["hkex_page_update_lag_days"] == 1


def test_missing_shenzhen_southbound_reference_fails_closed():
    html = """
    <html><body>
      <h2>All Eligible Securities</h2>
      <a href="https://www.sse.com.cn/services/hkexsc/disclo/eligible/">List of Eligible Securities for Southbound Trading under Shanghai Connect</a>
      <footer>Updated 06 Aug 2026</footer>
    </body></html>
    """
    result = validate(parse_hkex_page(html, "https://www.hkex.com.hk/example", _contract()), _contract(), "2026-08-07")
    assert result["status"] == "BLOCKED_CROSSCHECK"
    assert "MISSING_SZ_SOUTHBOUND_LINK" in result["errors"]
    assert result["publication_allowed"] is False


def test_non_official_target_fails_closed():
    html = """
    <html><body>
      <h2>All Eligible Securities</h2>
      <a href="https://broker.example.com/sh">List of Eligible Securities for Southbound Trading under Shanghai Connect</a>
      <a href="https://www.szse.cn/szhk/hkbussiness/underlylist/">List of Eligible Securities for Southbound Trading under Shenzhen Connect</a>
      <footer>Updated 06 Aug 2026</footer>
    </body></html>
    """
    result = validate(parse_hkex_page(html, "https://www.hkex.com.hk/example", _contract()), _contract(), "2026-08-07")
    assert result["status"] == "BLOCKED_CROSSCHECK"
    assert "SH_LINK_NOT_ON_PRIMARY_OFFICIAL_DOMAIN" in result["errors"]


def test_stale_hkex_page_fails_closed():
    html = """
    <html><body>
      <h2>All Eligible Securities</h2>
      <a href="https://www.sse.com.cn/services/hkexsc/disclo/eligible/">List of Eligible Securities for Southbound Trading under Shanghai Connect</a>
      <a href="https://www.szse.cn/szhk/hkbussiness/underlylist/">List of Eligible Securities for Southbound Trading under Shenzhen Connect</a>
      <footer>Updated 01 Aug 2026</footer>
    </body></html>
    """
    result = validate(parse_hkex_page(html, "https://www.hkex.com.hk/example", _contract()), _contract(), "2026-08-07")
    assert result["status"] == "BLOCKED_CROSSCHECK"
    assert "HKEX_PAGE_TOO_STALE" in result["errors"]


def test_future_dated_hkex_page_fails_closed():
    html = """
    <html><body>
      <h2>All Eligible Securities</h2>
      <a href="https://www.sse.com.cn/services/hkexsc/disclo/eligible/">List of Eligible Securities for Southbound Trading under Shanghai Connect</a>
      <a href="https://www.szse.cn/szhk/hkbussiness/underlylist/">List of Eligible Securities for Southbound Trading under Shenzhen Connect</a>
      <footer>Updated 08 Aug 2026</footer>
    </body></html>
    """
    result = validate(parse_hkex_page(html, "https://www.hkex.com.hk/example", _contract()), _contract(), "2026-08-07")
    assert "HKEX_PAGE_UPDATE_DATE_IN_FUTURE" in result["errors"]
    assert result["publication_allowed"] is False
