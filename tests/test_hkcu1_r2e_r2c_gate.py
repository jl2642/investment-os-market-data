from pipeline.hkcu1_r2e_r2c_gate import decide


def _accepted(date="2026-08-07"):
    return {
        "decision": "PASS_FORWARD_COMPLETE",
        "accepted_at": date,
        "ci_evidence": {"run_id": 31144272655},
        "r2c_scope_boundary": {
            "forward_complete_from_bootstrap": True,
            "r2c_layer_usable": True,
            "trade_authority": "NONE",
        },
    }


def test_live_r2c_pass_is_preferred():
    current = {
        "status": "PASS_FORWARD_COMPLETE",
        "forward_complete_from_bootstrap": True,
        "unresolved_effective_date_rows": 0,
        "future_effective_event_rows": 0,
    }
    result = decide(current, _accepted(), "2026-08-07")
    assert result["status"] == "PASS_LIVE_FORWARD_COMPLETE"
    assert result["r2c_operating_gate"] is True
    assert result["accepted_continuity_used"] is False


def test_same_day_degraded_refresh_can_use_previously_accepted_r2c():
    current = {
        "status": "DEGRADED",
        "bootstrap_date": "2026-08-07",
        "unresolved_effective_date_rows": 0,
        "future_effective_event_rows": 0,
        "blocked_channels": ["SH", "SZ"],
    }
    result = decide(current, _accepted(), "2026-08-07")
    assert result["status"] == "PASS_ACCEPTED_SAME_DATE_CONTINUITY"
    assert result["r2c_operating_gate"] is True
    assert result["accepted_continuity_used"] is True
    assert result["canonical_action"] == "KEEP_ACCEPTED_R2C_CANONICAL_UNCHANGED"


def test_old_acceptance_cannot_bridge_a_new_date():
    current = {
        "status": "DEGRADED",
        "bootstrap_date": "2026-08-08",
        "unresolved_effective_date_rows": 0,
        "future_effective_event_rows": 0,
    }
    result = decide(current, _accepted("2026-08-07"), "2026-08-08")
    assert result["status"] == "BLOCKED_R2C_OPERATING_GATE"
    assert result["r2c_operating_gate"] is False
