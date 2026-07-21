from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "scripts/fmdl5c_apply_hkex_current_actions.py"
spec = importlib.util.spec_from_file_location("fmdl5c_actions", MODULE_PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_parse_hkex_current_action_table() -> None:
    html = b"""
    <html><body><table>
      <thead><tr><th>Date of Listing / Traded</th><th>Stock Short Name</th><th>Stock Code</th><th>Board Lot</th><th>Remarks</th><th>Corresponding Corporate Action</th><th>Related Stock Code</th></tr></thead>
      <tbody><tr><td>20/07/2026</td><td>DT CAPITAL</td><td>02990</td><td>2000</td><td>S</td><td>Share Consolidation</td><td>00356</td></tr></tbody>
    </table></body></html>
    """
    rows = module.parse_hkex_action_html(
        html,
        {"00356"},
        "2026-07-21T00:00:00+00:00",
        "a" * 64,
    )
    assert len(rows) == 1
    assert rows[0]["security_id"] == "HKEX:00356"
    assert rows[0]["related_stock_code"] == "02990"
    assert rows[0]["source_tier"] == "OFFICIAL_CURRENT_EVENT"


def test_new_listing_without_corporate_action_is_excluded() -> None:
    html = b"""
    <table><tr><th>Date</th><th>Name</th><th>Stock Code</th><th>Lot</th><th>Corresponding Corporate Action</th><th>Related Stock Code</th></tr>
    <tr><td>20/07/2026</td><td>EXAMPLE</td><td>02990</td><td>2000</td><td>New Listing</td><td></td></tr></table>
    """
    rows = module.parse_hkex_action_html(html, {"02990"}, "2026-07-21T00:00:00+00:00", "b" * 64)
    assert rows == []
