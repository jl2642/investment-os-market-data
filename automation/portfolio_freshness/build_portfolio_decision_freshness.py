#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def require_none_authority(label: str, payload: Any) -> None:
    values: list[Any] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key == "trade_authority":
                    values.append(item)
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(payload)
    if values and set(values) != {"NONE"}:
        raise ValueError(f"{label}_TRADE_AUTHORITY_VIOLATION:{values}")


def parse_dt(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"TIMESTAMP_REQUIRES_TIMEZONE:{value}")
    return parsed


def holding_ids(payload: dict[str, Any]) -> set[str]:
    return {
        str(row.get("security_id") or "").strip()
        for row in payload.get("holdings", [])
        if str(row.get("security_id") or "").strip()
    }


def build_context(
    *,
    marks_domain: dict[str, Any],
    recommendation_domain: dict[str, Any],
    marks: dict[str, Any],
    real_positions: dict[str, Any],
    simulation_positions: dict[str, Any],
    recommendation: dict[str, Any],
    legacy_decision: dict[str, Any],
) -> dict[str, Any]:
    for label, payload in {
        "marks_domain": marks_domain,
        "recommendation_domain": recommendation_domain,
        "marks": marks,
        "real_positions": real_positions,
        "simulation_positions": simulation_positions,
        "recommendation": recommendation,
        "legacy_decision": legacy_decision,
    }.items():
        require_none_authority(label, payload)

    if marks_domain.get("status") != "PASS":
        raise ValueError("PORTFOLIO_MARKS_OPERATING_CURRENT_NOT_PASS")
    if recommendation_domain.get("status") != "PASS":
        raise ValueError("RECOMMENDATION_OPERATING_CURRENT_NOT_PASS")
    if marks.get("status") != "CURRENT_COMPLETE":
        raise ValueError("PORTFOLIO_MARKS_NOT_CURRENT_COMPLETE")

    mark_date = str((marks.get("data_watermark") or {}).get("latest_mark_date") or "")
    if not mark_date:
        raise ValueError("PORTFOLIO_MARK_DATE_MISSING")
    if str(marks_domain.get("data_watermark") or "") != mark_date:
        raise ValueError("PORTFOLIO_MARK_DOMAIN_WATERMARK_MISMATCH")

    required_ids = holding_ids(real_positions) | holding_ids(simulation_positions)
    mark_rows = {
        str(row.get("security_id") or ""): row
        for row in marks.get("marks", [])
        if str(row.get("security_id") or "")
    }
    if required_ids - set(mark_rows):
        raise ValueError("PORTFOLIO_REQUIRED_MARKS_MISSING")
    bad_freshness = sorted(
        sid
        for sid in required_ids
        if mark_rows[sid].get("freshness_status") not in {"FRESH", "ACCEPTABLE_LAG"}
    )
    if bad_freshness:
        raise ValueError("PORTFOLIO_MARKS_STALE:" + ",".join(bad_freshness))

    for label, positions in {
        "REAL": real_positions,
        "SIMULATION": simulation_positions,
    }.items():
        watermark = positions.get("mark_watermark") or {}
        if str(watermark.get("latest_mark_date") or "") != mark_date:
            raise ValueError(f"{label}_POSITION_MARK_WATERMARK_MISMATCH")
        if watermark.get("all_positions_marked") is not True:
            raise ValueError(f"{label}_POSITIONS_NOT_FULLY_MARKED")

    recommendation_generated = str(recommendation.get("generated_at_utc") or "")
    if not recommendation_generated:
        raise ValueError("RECOMMENDATION_GENERATED_AT_MISSING")
    parse_dt(recommendation_generated)

    legacy_generated = str(legacy_decision.get("generated_at") or "")
    if not legacy_generated:
        raise ValueError("LEGACY_PORTFOLIO_DECISION_GENERATED_AT_MISSING")
    legacy_dt = parse_dt(legacy_generated)
    mark_dt = datetime.fromisoformat(mark_date + "T23:59:59+00:00")
    legacy_stale = legacy_dt < mark_dt
    if not legacy_stale:
        raise ValueError("LEGACY_PORTFOLIO_DECISION_NOT_PROVEN_STALE")

    portfolio_ids = required_ids
    recommendation_records = recommendation.get("records") or []
    recommendation_ids = {
        str(row.get("security_id") or "").strip()
        for row in recommendation_records
        if str(row.get("security_id") or "").strip()
    }
    overlap = sorted(portfolio_ids & recommendation_ids)
    ready_count = sum(bool(row.get("ready_for_user_decision")) for row in recommendation_records)
    buy_count = sum(
        str(row.get("recommendation_state") or "").startswith("BUY")
        for row in recommendation_records
    )

    portfolio_action_state = (
        "BLOCKED_FRESH_RECOMMENDATION_OVERLAP_REQUIRES_SEPARATE_GOVERNED_PORTFOLIO_REVIEW"
        if overlap
        else "BLOCKED_NO_CURRENT_RECOMMENDATION_OVERLAP_AND_LEGACY_ACTION_MATRIX_STALE"
    )

    identity_payload = {
        "mark_date": mark_date,
        "marks_source_commit": marks_domain.get("source_commit_sha"),
        "recommendation_source_commit": recommendation_domain.get("source_commit_sha"),
        "recommendation_fingerprint": recommendation.get("recommendation_fingerprint"),
        "legacy_generated_at": legacy_generated,
        "overlap": overlap,
    }
    identity = hashlib.sha256(
        json.dumps(identity_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    return {
        "schema_version": "1.0.0",
        "context_id": f"OCC_R4_PORTFOLIO_DECISION_FRESHNESS_{identity[:16]}",
        "status": "PASS_PORTFOLIO_DECISION_FRESHNESS_ALIGNED",
        "qc_status": "PASS_FRESH_INPUTS_BOUND_STALE_LEGACY_DECISION_BLOCKED",
        "as_of_date": mark_date,
        "source_bindings": {
            "portfolio_marks": {
                "domain_id": "PORTFOLIO_MARKS",
                "watermark": mark_date,
                "source_workflow": marks_domain.get("source_workflow"),
                "source_run_id": marks_domain.get("source_run_id"),
                "source_branch": marks_domain.get("source_branch"),
                "source_commit": marks_domain.get("source_commit_sha"),
            },
            "recommendation": {
                "domain_id": "RECOMMENDATION",
                "watermark": recommendation_domain.get("data_watermark"),
                "source_workflow": recommendation_domain.get("source_workflow"),
                "source_run_id": recommendation_domain.get("source_run_id"),
                "source_branch": recommendation_domain.get("source_branch"),
                "source_commit": recommendation_domain.get("source_commit_sha"),
                "recommendation_fingerprint": recommendation.get("recommendation_fingerprint"),
            },
            "legacy_portfolio_decision": {
                "state_id": legacy_decision.get("state_id"),
                "generated_at": legacy_generated,
                "status": legacy_decision.get("status"),
                "stale_against_current_marks": True,
            },
        },
        "portfolio_current": {
            "real_holding_count": len(real_positions.get("holdings", [])),
            "simulation_holding_count": len(simulation_positions.get("holdings", [])),
            "required_mark_count": len(required_ids),
            "all_required_marks_fresh_or_acceptable": True,
            "portfolio_fit_input_fresh": True,
            "broker_verification_separate": True,
        },
        "recommendation_current": {
            "overall_status": recommendation.get("overall_status"),
            "record_count": len(recommendation_records),
            "ready_for_user_decision_count": ready_count,
            "buy_state_count": buy_count,
            "portfolio_overlap_security_ids": overlap,
            "portfolio_overlap_count": len(overlap),
        },
        "decision_freshness": {
            "fresh_input_surface": True,
            "legacy_action_matrix_current": False,
            "legacy_action_matrix_stale_reason": (
                f"LEGACY_DECISION_GENERATED_{legacy_generated[:10]}_BEFORE_MARKS_{mark_date}"
            ),
            "portfolio_action_state": portfolio_action_state,
            "implementation_ready": False,
            "ready_for_user_decision": False,
            "automatic_rebalance_allowed": False,
            "automatic_position_change_allowed": False,
        },
        "controls": {
            "candidate_membership_mutations": 0,
            "real_account_mutations": 0,
            "simulation_mutations": 0,
            "target_portfolio_writebacks": 0,
            "orders": 0,
            "trade_authority": "NONE",
        },
        "trade_authority": "NONE",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--marks-domain", required=True)
    parser.add_argument("--recommendation-domain", required=True)
    parser.add_argument("--marks", required=True)
    parser.add_argument("--real-positions", required=True)
    parser.add_argument("--simulation-positions", required=True)
    parser.add_argument("--recommendation", required=True)
    parser.add_argument("--legacy-decision", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    result = build_context(
        marks_domain=read_json(Path(args.marks_domain)),
        recommendation_domain=read_json(Path(args.recommendation_domain)),
        marks=read_json(Path(args.marks)),
        real_positions=read_json(Path(args.real_positions)),
        simulation_positions=read_json(Path(args.simulation_positions)),
        recommendation=read_json(Path(args.recommendation)),
        legacy_decision=read_json(Path(args.legacy_decision)),
    )
    write_json(Path(args.output), result)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
