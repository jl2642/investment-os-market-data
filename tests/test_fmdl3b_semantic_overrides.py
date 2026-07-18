from pathlib import Path

import pandas as pd

from scripts import fmdl3b_core as core
from scripts import fmdl3b_semantic_overrides as semantic

ROOT = Path(__file__).resolve().parents[1]


def test_cash_and_cash_equivalents_are_distinct():
    index, payload = core.load_registry(ROOT / "config/fmdl3b_field_registry.json")
    index, payload = semantic.apply_overrides(index, payload)
    assert core.map_field("cash_flow", "BEGIN_CCE", index)["line_item_id"] == "beginning_cash"
    assert core.map_field("cash_flow", "BEGIN_CASH", index)["line_item_id"] == "beginning_cash_balance"
    assert core.map_field("cash_flow", "END_CCE", index)["line_item_id"] == "ending_cash"
    assert core.map_field("cash_flow", "END_CASH", index)["line_item_id"] == "ending_cash_balance"


def test_cash_balance_signs_preserve_reported_values_and_rollforward():
    index, payload = core.load_registry(ROOT / "config/fmdl3b_field_registry.json")
    index, payload = semantic.apply_overrides(index, payload)

    for alias in ["BEGIN_CCE", "BEGIN_CASH", "END_CCE", "END_CASH"]:
        assert core.map_field("cash_flow", alias, index)["sign_rule"] == "AS_REPORTED"

    beginning = core.apply_sign(
        14_060_550.25,
        core.map_field("cash_flow", "BEGIN_CCE", index)["sign_rule"],
    )
    net_change = -31_375_995.60
    ending = core.apply_sign(
        -17_315_445.35,
        core.map_field("cash_flow", "END_CCE", index)["sign_rule"],
    )

    assert ending == -17_315_445.35
    assert beginning + net_change == ending


def test_combined_distribution_line_is_not_pure_dividends():
    index, payload = core.load_registry(ROOT / "config/fmdl3b_field_registry.json")
    index, payload = semantic.apply_overrides(index, payload)
    field = core.map_field("cash_flow", "分配股利、利润或偿付利息支付的现金", index)
    assert field["line_item_id"] == "distribution_profit_interest_cash_paid"
    assert field["line_item_id"] != "dividends"


def test_ambiguous_mapping_detector():
    frame = pd.DataFrame([
        {"symbol": "600000.SH", "statement": "cash_flow", "report_period_end": "2025-12-31", "canonical_field_id": "ending_cash", "source_route_id": "EASTMONEY_STATEMENTS"},
        {"symbol": "600000.SH", "statement": "cash_flow", "report_period_end": "2025-12-31", "canonical_field_id": "ending_cash", "source_route_id": "EASTMONEY_STATEMENTS"},
    ])
    assert len(semantic.ambiguous_source_mapping_groups(frame)) == 1
