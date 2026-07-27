from __future__ import annotations

from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    path = root / "automation/wp3_2a/tests/test_operating_closure_and_wp3_2b.py"
    text = path.read_text(encoding="utf-8")
    token = 'elif step == "R4_OPERATING_PRODUCTS_DEVELOPMENT_COMPLETE_CURRENT_IF_PRESENT_ON_MAIN"'
    if token in text:
        return 0
    needle = '''    elif step == "R3_POSITION_ACTION_MATRIX_AND_USER_DECISION_PACK_CURRENT_IF_PRESENT_ON_MAIN":
        assert register["trade_authority"] == "NONE"
        assert register["development_roadmap"]["R2"]["status"] == "COMPLETED_ON_MAIN"
        assert register["development_roadmap"]["R3"]["status"] == "DEVELOPMENT_PRODUCT_COMPLETE_ON_MAIN"
        assert register["development_roadmap"]["R4"]["status"] == "NOT_STARTED_NEXT_AUTHORIZED_STAGE"
        assert register["wp5"]["formal_plan"] == "WP5_1_TO_WP5_5"
        assert register["wp5"]["portfolio_construction_synthesis_complete"] is True
        assert register["wp5"]["position_action_matrix_complete"] is True
        assert register["wp5"]["user_decision_pack_complete"] is True
        assert register["wp5"]["development_decision_scenario_count"] == 7
        assert register["wp5"]["ready_for_user_decision_count"] == 0
        assert register["wp5"]["implementation_ready_count"] == 0
        assert register["wp5"]["operating_activation"] is False
        assert register["next_task"] == "R4_OPERATING_PRODUCTS_DEVELOPMENT"
    else:
'''
    replacement = needle[:-10] + '''    elif step == "R4_OPERATING_PRODUCTS_DEVELOPMENT_COMPLETE_CURRENT_IF_PRESENT_ON_MAIN":
        assert register["trade_authority"] == "NONE"
        assert register["development_roadmap"]["R3"]["status"] == "DEVELOPMENT_PRODUCT_COMPLETE_ON_MAIN"
        assert register["development_roadmap"]["R4"]["status"] == "CURRENT_IF_PRESENT_ON_MAIN"
        assert register["development_roadmap"]["R5"]["status"] == "NOT_STARTED_NEXT_AUTHORIZED_STAGE"
        assert register["development_roadmap"]["R6"]["status"] == "NOT_STARTED"
        assert register["operating_products_r4"]["product_count"] == 7
        assert register["operating_products_r4"]["development_samples"] == 7
        assert register["operating_products_r4"]["operating_activation"] is False
        assert register["operating_products_r4"]["schedule_activation_count"] == 0
        assert register["ready_for_user_decision_count"] == 0
        assert register["implementation_ready_count"] == 0
        assert register["next_task"] == "R5_ATTRIBUTION_AND_CALIBRATION_DEVELOPMENT_AFTER_R4_PRESENT_ON_MAIN"
    else:
'''
    if needle not in text:
        raise SystemExit("R4_LINEAGE_PATCH_NEEDLE_NOT_FOUND")
    path.write_text(text.replace(needle, replacement, 1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
