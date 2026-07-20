from pathlib import Path

from scripts import fmdl4c_core as core


def cfg():
    return {
        "reentry_routes": {
            "600900.SH": {
                "name": "长江电力",
                "queue_state": "CANDIDATE_POOL_REENTRY_REVIEW_READY",
                "route_class": "DEFENSIVE_INFRASTRUCTURE_QUALITY",
                "priority": 1,
                "required_follow_on": "initiating-coverage",
                "open_gates": ["ENTRY_VALUATION", "PORTFOLIO_FIT"],
            },
            "300308.SZ": {
                "name": "中际旭创",
                "queue_state": "SHADOW_TRACK_REENTRY_REVIEW_READY",
                "route_class": "HIGH_GROWTH_EXPECTATIONS_GATED",
                "priority": 2,
                "required_follow_on": "scenario-sensitivity-generator",
                "open_gates": ["ENTRY_VALUATION", "DOWNSIDE_SCENARIO"],
            },
        },
        "state_domains": {"overlay_reentry_queue": "FMDL4C_REENTRY_REVIEW_QUEUE"},
        "authority": "INVESTMENT_OS_REENTRY_GOVERNANCE_AND_VERSIONED_OVERLAY_STATE_ONLY",
    }


def test_route_for_symbol_exact():
    assert core.route_for_symbol("600900.SH", cfg())["queue_state"] == "CANDIDATE_POOL_REENTRY_REVIEW_READY"
    assert core.route_for_symbol("300308.SZ", cfg())["queue_state"] == "SHADOW_TRACK_REENTRY_REVIEW_READY"


def test_build_transition_is_deterministic_and_valid():
    row = {
        "symbol": "600900.SH",
        "research_id": "FMDL4B-RSCH-600900.SH-abcdef0123456789",
        "decision_reason_codes_json": '["DURABLE_ASSET_BASE", "CASH_YIELD_SUPPORT"]',
    }
    research = {"evidence_ids_json": '["FMDL4A-EV-600900.SH-abcdef0123456789"]'}
    first = core.build_transition(row, research, cfg(), created_at="2026-07-20T14:00:00+08:00", research_version="RV1")
    second = core.build_transition(row, research, cfg(), created_at="2026-07-20T14:00:00+08:00", research_version="RV1")
    assert first == second
    assert core.validate_transition(first, cfg()) == []
    assert first["approval_state"] == "ACCEPTED_TO_REENTRY_REVIEW_QUEUE_ONLY"
    assert first["trade_authority"] == "NONE"


def test_transition_changes_when_route_changes():
    row = {
        "symbol": "300308.SZ",
        "research_id": "FMDL4B-RSCH-300308.SZ-abcdef0123456789",
        "decision_reason_codes_json": '["EXPOSURE_PROVEN", "VALUATION_EXPECTATIONS_GATED"]',
    }
    research = {"evidence_ids_json": '["FMDL4A-EV-300308.SZ-abcdef0123456789"]'}
    first = core.build_transition(row, research, cfg(), created_at="2026-07-20T14:00:00+08:00", research_version="RV1")
    local = cfg()
    local["reentry_routes"]["300308.SZ"]["queue_state"] = "CANDIDATE_POOL_REENTRY_REVIEW_READY"
    second = core.build_transition(row, research, local, created_at="2026-07-20T14:00:00+08:00", research_version="RV1")
    assert first["semantic_hash"] != second["semantic_hash"]
    assert first["transition_id"] != second["transition_id"]


def test_gate_results_block_simulation_and_real_account():
    gates = core.build_gate_results(cfg()["reentry_routes"]["600900.SH"])
    assert gates["SIMULATION_ADMISSION"] == "BLOCKED"
    assert gates["REAL_ACCOUNT_RCM"] == "BLOCKED"
    assert gates["RELEASE4_BASE_BYTE_ACCESS"] == "PENDING_CONTROLLED_LIMITATION"


def test_empty_to_six_state_hash_is_rollbackable():
    before = core.stable_hash([])
    after = core.stable_hash([{"symbol": "600900.SH", "queue_state": "CANDIDATE_POOL_REENTRY_REVIEW_READY"}])
    assert before != after
    assert before == core.stable_hash([])


def test_deterministic_zip(tmp_path: Path):
    root = tmp_path / "overlay"
    (root / "STATE_CURRENT").mkdir(parents=True)
    (root / "CORE_STATIC").mkdir(parents=True)
    (root / "STATE_CURRENT/queue.csv").write_text("symbol,state\n600900.SH,READY\n", encoding="utf-8")
    (root / "CORE_STATIC/contract.json").write_text('{"trade_authority":"NONE"}\n', encoding="utf-8")
    first = tmp_path / "first.zip"
    second = tmp_path / "second.zip"
    core.deterministic_zip(root, first)
    core.deterministic_zip(root, second)
    assert core.sha256_file(first) == core.sha256_file(second)
