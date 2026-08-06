from __future__ import annotations

import csv
import json
import sys
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from automation.wp3_r.build_candidate_dynamic_loop import run
from automation.wp3_r.validate_candidate_dynamic_pr import validate


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def candidate_state() -> dict:
    def row(security_id: str, route: str, dynamic: bool = False) -> dict:
        payload = {
            "security_id": security_id,
            "security_code": security_id.split(".")[0],
            "security_name": security_id,
            "buy_signal": "NO",
            "candidate_state_change_requires_human_merge": True,
            "ready_for_user_decision": False,
            "real_account_permission": False,
            "simulation_admission_permission": False,
            "research_decision_grade": False,
            "trade_authority": "NONE",
            "proposed_candidate_route": route,
        }
        if dynamic:
            payload["dynamic_candidate_source"] = "FULL_MARKET_SCREEN"
        return payload

    research = [row(f"30{i:04d}.SZ", "RESEARCH_QUEUE_STRUCTURED") for i in range(25)]
    return {
        "candidate_core_members": [row("000333.SZ", "CANDIDATE_CORE_PROPOSED")],
        "shadow_track_members": [row("600000.SH", "SHADOW_TRACK")],
        "research_queue_members": research,
        "ready_for_user_decision_members": [],
        "counts": {"candidate_core": 1, "shadow_track": 1, "research_queue": 25, "ready_for_user_decision": 0},
        "continuous_candidate_engine_complete": False,
        "semantic_hash": "baseline",
    }


def policy() -> dict:
    return {
        "screening": {
            "admission_rank_ceiling": 30,
            "promotion_review_rank_ceiling": 10,
            "allowed_research_priorities": ["A_IMMEDIATE_RESEARCH", "B_SCHEDULED_RESEARCH"],
            "allowed_investability_statuses": ["ELIGIBLE_CORE"],
            "allowed_factor_record_quality": ["VALID"],
            "allowed_confidence_grades": ["A", "B"],
        },
        "hysteresis": {
            "minimum_consecutive_longlist_appearances": 2,
            "dynamic_exit_absence_streak": 3,
            "legacy_exit_review_absence_streak": 4,
            "completed_weekly_cycles_for_production_acceptance": 3,
        },
        "capacity": {
            "maximum_research_queue_size": 40,
            "minimum_research_queue_size": 25,
            "maximum_weekly_admissions": 3,
            "maximum_weekly_dynamic_exits": 3,
            "maximum_admissions_per_primary_sleeve": 1,
        },
        "authority": {"orders": 0, "trade_authority": "NONE"},
    }


def install(root: Path, as_of: str, symbols: list[tuple[str, str, str]]) -> None:
    write_json(root / "automation/wp3_r/candidate_dynamic_policy.json", policy())
    write_json(root / "outputs/screens/current/SCREENING_MANIFEST.json", {"as_of_date": as_of})
    write_json(root / "investment_os_runtime/30_STATE_CURRENT/40_CANDIDATE/CANDIDATE_CURRENT.json", candidate_state())
    path = root / "outputs/screens/current/SCREENING_LONGLIST.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "as_of_date", "overall_rank", "research_priority", "symbol", "name", "primary_sleeve",
        "investability_status", "factor_record_quality", "confidence_grade", "aggregate_score", "longlist_row_hash"
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for rank, (symbol, name, sleeve) in enumerate(symbols, 1):
            writer.writerow({
                "as_of_date": as_of,
                "overall_rank": rank,
                "research_priority": "A_IMMEDIATE_RESEARCH",
                "symbol": symbol,
                "name": name,
                "primary_sleeve": sleeve,
                "investability_status": "ELIGIBLE_CORE",
                "factor_record_quality": "VALID",
                "confidence_grade": "A",
                "aggregate_score": 1.0 - rank / 1000,
                "longlist_row_hash": f"hash-{as_of}-{symbol}",
            })


def test_two_week_hysteresis_and_protected_routes(tmp_path: Path) -> None:
    symbols = [("688001.SH", "A", "TREND"), ("688002.SH", "B", "VALUE")]
    install(tmp_path, "2026-08-07", symbols)
    first = run(tmp_path, Path("automation/wp3_r/candidate_dynamic_policy.json"), force_weekly=True)
    assert first["admission_count"] == 0
    first_candidate = json.loads((tmp_path / "investment_os_runtime/30_STATE_CURRENT/40_CANDIDATE/CANDIDATE_CURRENT.json").read_text())
    protected = {key: deepcopy(first_candidate[key]) for key in ("candidate_core_members", "shadow_track_members", "ready_for_user_decision_members")}

    write_json(tmp_path / "outputs/screens/current/SCREENING_MANIFEST.json", {"as_of_date": "2026-08-14"})
    csv_path = tmp_path / "outputs/screens/current/SCREENING_LONGLIST.csv"
    rows = list(csv.DictReader(csv_path.open(encoding="utf-8")))
    for row in rows:
        row["as_of_date"] = "2026-08-14"
        row["longlist_row_hash"] = "second-" + row["symbol"]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    second = run(tmp_path, Path("automation/wp3_r/candidate_dynamic_policy.json"), force_weekly=True)
    assert second["admission_count"] == 2
    head = json.loads((tmp_path / "investment_os_runtime/30_STATE_CURRENT/40_CANDIDATE/CANDIDATE_CURRENT.json").read_text())
    assert len(head["research_queue_members"]) == 27
    assert {key: head[key] for key in protected} == protected
    assert all(row.get("dynamic_candidate_source") == "FULL_MARKET_SCREEN" for row in head["research_queue_members"][-2:])
    result = validate(first_candidate, head, policy())
    assert result["added"] == ["688001.SH", "688002.SH"]
    assert result["unchanged_research_queue_rows"] == 25


def test_validator_blocks_legacy_exit_and_core_change() -> None:
    base = candidate_state()
    head = deepcopy(base)
    head["candidate_core_members"] = []
    try:
        validate(base, head, policy())
    except SystemExit as exc:
        assert "candidate_core_members" in str(exc)
    else:
        raise AssertionError("core mutation must fail")

    head = deepcopy(base)
    head["research_queue_members"] = head["research_queue_members"][1:]
    head["counts"]["research_queue"] = 24
    try:
        validate(base, head, policy())
    except SystemExit as exc:
        assert "MINIMUM" in str(exc) or "LEGACY" in str(exc)
    else:
        raise AssertionError("legacy automatic exit must fail")


def test_validator_blocks_existing_row_rewrite_and_cross_route_duplicate() -> None:
    base = candidate_state()
    head = deepcopy(base)
    head["research_queue_members"][0]["security_name"] = "tampered"
    try:
        validate(base, head, policy())
    except SystemExit as exc:
        assert "EXISTING_RESEARCH_QUEUE_ROW_MUTATION_FORBIDDEN" in str(exc)
    else:
        raise AssertionError("existing Research Queue row rewrite must fail")

    head = deepcopy(base)
    duplicate = deepcopy(head["candidate_core_members"][0])
    duplicate["proposed_candidate_route"] = "RESEARCH_QUEUE_STRUCTURED"
    head["research_queue_members"].append(duplicate)
    head["counts"]["research_queue"] = 26
    try:
        validate(base, head, policy())
    except SystemExit as exc:
        assert "CROSS_ROUTE_CANDIDATE_DUPLICATION" in str(exc)
    else:
        raise AssertionError("cross-route duplicate must fail")
