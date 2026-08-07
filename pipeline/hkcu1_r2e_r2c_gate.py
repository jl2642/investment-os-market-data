#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def decide(current: dict, accepted: dict, as_of_date: str) -> dict:
    if (
        current.get("status") == "PASS_FORWARD_COMPLETE"
        and current.get("forward_complete_from_bootstrap") is True
        and int(current.get("unresolved_effective_date_rows", 0)) == 0
        and int(current.get("future_effective_event_rows", 0)) == 0
    ):
        return {
            "status": "PASS_LIVE_FORWARD_COMPLETE",
            "current_event_refresh_passed": True,
            "accepted_continuity_used": False,
            "r2c_operating_gate": True,
            "canonical_action": "CURRENT_R2C_EVIDENCE_USABLE",
            "trade_authority": "NONE",
        }

    scope = accepted.get("r2c_scope_boundary") or {}
    accepted_same_day = (
        current.get("status") == "DEGRADED"
        and str(current.get("bootstrap_date") or "") == as_of_date
        and int(current.get("unresolved_effective_date_rows", 0)) == 0
        and int(current.get("future_effective_event_rows", 0)) == 0
        and accepted.get("decision") == "PASS_FORWARD_COMPLETE"
        and str(accepted.get("accepted_at") or "") == as_of_date
        and scope.get("forward_complete_from_bootstrap") is True
        and scope.get("r2c_layer_usable") is True
        and scope.get("trade_authority") == "NONE"
    )
    if accepted_same_day:
        return {
            "status": "PASS_ACCEPTED_SAME_DATE_CONTINUITY",
            "current_event_refresh_passed": False,
            "accepted_continuity_used": True,
            "accepted_r2c_run_id": (accepted.get("ci_evidence") or {}).get("run_id"),
            "accepted_at": accepted.get("accepted_at"),
            "current_refresh_status": current.get("status"),
            "current_blocked_channels": current.get("blocked_channels", []),
            "r2c_operating_gate": True,
            "canonical_action": "KEEP_ACCEPTED_R2C_CANONICAL_UNCHANGED",
            "trade_authority": "NONE",
        }

    return {
        "status": "BLOCKED_R2C_OPERATING_GATE",
        "current_event_refresh_passed": False,
        "accepted_continuity_used": False,
        "r2c_operating_gate": False,
        "current_refresh_status": current.get("status"),
        "accepted_decision": accepted.get("decision"),
        "accepted_at": accepted.get("accepted_at"),
        "canonical_action": "KEEP_PREVIOUS_CANONICAL_UNCHANGED",
        "trade_authority": "NONE",
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--current-decision", type=Path, required=True)
    p.add_argument("--accepted-r2c", type=Path, required=True)
    p.add_argument("--as-of-date", required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    result = decide(_read(a.current_decision), _read(a.accepted_r2c), a.as_of_date)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["r2c_operating_gate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
