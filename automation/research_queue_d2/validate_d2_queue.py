from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
D2_CURRENT = ROOT / "investment_os_runtime/30_STATE_CURRENT/30_RESEARCH/RESEARCH_QUEUE_D2_CURRENT.json"
D2_LIVENESS = ROOT / "investment_os_runtime/30_STATE_CURRENT/30_RESEARCH/RESEARCH_QUEUE_D2_LIVENESS_CURRENT.json"


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
    assert state["summary"]["pending_count"] + state["summary"]["completed_count"] == len(queue)
    assert state["summary"]["blocked_count"] <= state["summary"]["pending_count"]

    print({
        "d2_routes": len(queue),
        "pending": state["summary"]["pending_count"],
        "blocked": state["summary"]["blocked_count"],
        "manual_trigger_required": False,
        "orders": 0,
        "trade_authority": "NONE",
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
