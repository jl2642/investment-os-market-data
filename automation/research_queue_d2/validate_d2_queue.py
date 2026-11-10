from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
D2_CURRENT = ROOT / "investment_os_runtime/30_STATE_CURRENT/30_RESEARCH/RESEARCH_QUEUE_D2_CURRENT.json"
D2_LIVENESS = ROOT / "investment_os_runtime/30_STATE_CURRENT/30_RESEARCH/RESEARCH_QUEUE_D2_LIVENESS_CURRENT.json"

ACTIVE_PENDING_STATUSES = {
    "PENDING_AUTO_RESEARCH",
    "PRIMARY_EVIDENCE_DISCOVERED_SEMANTIC_RESEARCH_PENDING",
    "AUTO_RESEARCH_BLOCKED_PRIMARY_SOURCE_DISCOVERY",
    "D2_UNDERWRITING_PENDING",
}
SEMANTIC_TERMINAL_STATUSES = {
    "D2_RESEARCH_COMPLETE",
    "D2_RESEARCH_HOLD_EVIDENCE_GAP",
}


def underwriting_complete(row: dict) -> bool:
    """Require decision-grade economics, not merely three scenario labels."""
    import math

    uw = row.get("underwriting")
    if not isinstance(uw, dict):
        return False
    try:
        price = float(uw["current_price"])
        entry = float(uw["entry_price"])
        weighted = float(uw["probability_weighted_value"])
        expected_return = float(uw["expected_return"])
        scenarios = uw["scenarios"]
        if not all(math.isfinite(v) for v in (price, entry, weighted, expected_return)):
            return False
        if price <= 0 or entry <= 0 or weighted < 0:
            return False
        if not uw.get("price_as_of") or not uw.get("normalized_earnings_basis"):
            return False
        if str(uw.get("confidence") or "").upper() not in {
            "HIGH", "MEDIUM", "MEDIUM_HIGH", "HIGH_MEDIUM"
        }:
            return False
        if uw.get("action") not in {
            "BUY", "BUY_BELOW", "WATCH_FOR_EVIDENCE", "WATCH", "AVOID",
            "ADD", "HOLD", "TRIM", "EXIT",
        }:
            return False
        if not uw.get("kill_thesis") or not uw.get("catalysts"):
            return False
        if not isinstance(scenarios, list) or len(scenarios) != 3:
            return False
        by_name = {str(s["name"]).upper(): s for s in scenarios}
        if set(by_name) != {"BEAR", "BASE", "BULL"}:
            return False
        probabilities = [float(s["probability"]) for s in scenarios]
        values = [float(s["value_per_share"]) for s in scenarios]
        if not all(math.isfinite(v) for v in probabilities + values):
            return False
        if any(p < 0 or p > 1 for p in probabilities) or any(v < 0 for v in values):
            return False
        if abs(sum(probabilities) - 1) > 1e-6:
            return False
        calc_weighted = sum(p * value for p, value in zip(probabilities, values))
        if abs(calc_weighted - weighted) > max(0.01, calc_weighted * 0.001):
            return False
        if abs((weighted / price - 1) - expected_return) > 0.001:
            return False
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return False
    return True


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    state = load(D2_CURRENT)
    liveness = load(D2_LIVENESS)

    assert state["consumer_policy"]["bounded_batch_size"] == 3
    assert state["consumer_policy"]["manual_dispatch"] == "BREAK_GLASS_ONLY"
    assert state["summary"]["manual_trigger_required"] is False
    assert liveness["manual_trigger_required"] is False

    queue = state["queue"]
    assert len({row["security_id"] for row in queue}) == len(queue)
    for row in queue:
        assert row["d2_questions"]
        status = row["status"]
        assert status in ACTIVE_PENDING_STATUSES | SEMANTIC_TERMINAL_STATUSES
        if status == "D2_RESEARCH_COMPLETE":
            assert row["semantic_research_required"] is False
            assert underwriting_complete(row), row
        else:
            assert row["semantic_research_required"] is True
        assert row["candidate_membership_mutation_authorized"] is False
        assert row["real_account_mutation_authorized"] is False
        assert row["simulation_mutation_authorized"] is False
        assert row["decision_mutation_authorized"] is False
        assert row["order_generation_authorized"] is False
        assert row["trade_authority"] == "NONE"

    controls = state["controls"]
    assert controls == {
        "candidate_membership_mutations": 0,
        "real_account_mutations": 0,
        "simulation_mutations": 0,
        "decision_mutations": 0,
        "orders": 0,
        "trade_authority": "NONE",
    }
    assert liveness["trade_authority"] == "NONE"

    active_pending = [row for row in queue if row["status"] in ACTIVE_PENDING_STATUSES]
    completed = [row for row in queue if row["status"] == "D2_RESEARCH_COMPLETE"]
    holds = [row for row in queue if row["status"] == "D2_RESEARCH_HOLD_EVIDENCE_GAP"]
    blocked = [
        row for row in queue
        if row["status"].startswith("AUTO_RESEARCH_BLOCKED")
        or row["status"] == "D2_RESEARCH_HOLD_EVIDENCE_GAP"
    ]

    assert state["summary"]["pending_count"] == len(active_pending)
    assert state["summary"]["completed_count"] == len(completed)
    assert state["summary"].get("hold_evidence_gap_count", len(holds)) == len(holds)
    assert state["summary"]["blocked_count"] == len(blocked)
    assert len(active_pending) + len(completed) + len(holds) == len(queue)

    assert liveness["d2_pending_count"] == len(active_pending)
    assert liveness["d2_completed_count"] == len(completed)
    if "d2_hold_evidence_gap_count" in liveness:
        assert liveness["d2_hold_evidence_gap_count"] == len(holds)
    assert liveness["d2_blocked_count"] == len(blocked)

    print({
        "d2_routes": len(queue),
        "pending": len(active_pending),
        "completed": len(completed),
        "holds": len(holds),
        "blocked": len(blocked),
        "manual_trigger_required": False,
        "orders": 0,
        "trade_authority": "NONE",
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
