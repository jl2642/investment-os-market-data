from __future__ import annotations

from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    path = root / "automation/wp3_2a/tests/test_operating_closure_and_wp3_2b.py"
    text = path.read_text(encoding="utf-8")
    token = 'elif step == "R3_POSITION_ACTION_MATRIX_AND_USER_DECISION_PACK_CURRENT_IF_PRESENT_ON_MAIN"'
    if token in text:
        return 0
    needle = '''    elif step == "R2_PORTFOLIO_CONSTRUCTION_SYNTHESIS_CURRENT_IF_PRESENT_ON_MAIN":
        assert register["trade_authority"] == "NONE"
        assert register["development_roadmap"]["R1"]["status"] == "COMPLETED_ON_MAIN"
        assert register["development_roadmap"]["R2"]["status"] == "CURRENT_IF_PRESENT_ON_MAIN"
        assert register["development_roadmap"]["R3"]["status"] == "NOT_STARTED"
        assert register["wp5"]["formal_plan"] == "WP5_1_TO_WP5_5"
        assert register["wp5"]["portfolio_construction_synthesis_complete"] is True
        assert register["wp5"]["position_action_matrix_complete"] is False
        assert register["wp5"]["user_decision_pack_complete"] is False
        assert register["next_task"] == "R3_POSITION_ACTION_MATRIX_AND_USER_DECISION_PACK_AFTER_R2_PRESENT_ON_MAIN"
    else:
'''
    replacement = needle[:-10] + '''    elif step == "R3_POSITION_ACTION_MATRIX_AND_USER_DECISION_PACK_CURRENT_IF_PRESENT_ON_MAIN":
        assert register["trade_authority"] == "NONE"
        assert register["development_roadmap"]["R2"]["status"] == "COMPLETED_ON_MAIN"
        assert register["development_roadmap"]["R3"]["status"] == "CURRENT_IF_PRESENT_ON_MAIN"
        assert register["development_roadmap"]["R4"]["status"] == "NOT_STARTED"
        assert register["wp5"]["formal_plan"] == "WP5_1_TO_WP5_5"
        assert register["wp5"]["portfolio_construction_synthesis_complete"] is True
        assert register["wp5"]["position_action_matrix_complete"] is True
        assert register["wp5"]["user_decision_pack_complete"] is True
        assert register["wp5"]["ready_for_user_decision_count"] == 7
        assert register["wp5"]["implementation_ready_count"] == 0
        assert register["next_task"] == "USER_REVIEW_R3_DECISION_PACK_BEFORE_ANY_IMPLEMENTATION_PROPOSAL"
    else:
'''
    if needle not in text:
        raise SystemExit("R3_LINEAGE_PATCH_NEEDLE_NOT_FOUND")
    path.write_text(text.replace(needle, replacement, 1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
