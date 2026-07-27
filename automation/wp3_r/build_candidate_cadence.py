#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


def read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def digest(payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def monthly_review(root: Path, cfg: dict[str, Any], as_of: date) -> dict[str, Any]:
    outputs = cfg["outputs"]
    candidate = read(root / cfg["inputs"]["candidate_current"])
    weekly = read(root / outputs["weekly_price_screen"])
    freshness = read(root / outputs["financial_freshness"])
    profiles = read(root / outputs["financial_profile_readiness"])
    industry = read(root / outputs["industry_quality"])
    outcomes = read(root / outputs["candidate_outcomes"])
    operating = read(root / outputs["operating_current"])
    path = root / "investment_os_runtime/30_STATE_CURRENT/45_CANDIDATE_OPERATIONS/MONTHLY_CANDIDATE_REVIEW_CURRENT.json"
    prior = read(path) if path.exists() else {}
    review_month = as_of.strftime("%Y-%m")
    same_month = prior.get("review_month") == review_month
    core_rows = [row for row in weekly.get("rows", []) if row.get("candidate_route") == "CANDIDATE_CORE_MEMBERS"]
    issues = []
    if weekly.get("status") != "PASS_WEEKLY_PRICE_SCREEN_NO_MEMBERSHIP_MUTATION":
        issues.append("WEEKLY_PRICE_SCREEN_INCOMPLETE")
    if industry.get("status") != "PASS_CANONICAL_INDUSTRY_QUALITY_GATE":
        issues.append("INDUSTRY_CLASSIFICATION_REVIEW_REQUIRED")
    if freshness.get("stale_or_missing_count", 0):
        issues.append("STALE_OR_MISSING_FINANCIAL_REPORT_PERIODS_PRESENT")
    if profiles.get("status") != "INDEPENDENT_FINANCIAL_SCREENING_PROFILE_ACTIVE_RESEARCH_GRADE_INPUTS_PENDING":
        issues.append("FINANCIAL_PROFILE_SCREENING_NOT_ACTIVE")
    if outcomes.get("status") == "WINDOWS_PENDING":
        issues.append("CORE_OUTCOME_WINDOWS_NOT_MATURE")
    payload = {
        "state_id": "WP3R_MONTHLY_CANDIDATE_REVIEW_CURRENT",
        "review_month": review_month,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "NOOP_ALREADY_REVIEWED_THIS_MONTH" if same_month else "MONTHLY_REVIEW_COMPLETE_NO_AUTOMATIC_MEMBERSHIP_CHANGE",
        "candidate_state_id": candidate.get("candidate_state_id") or candidate.get("state_id"),
        "candidate_counts": candidate.get("counts"),
        "core_price_and_valuation_snapshot": core_rows,
        "weekly_screen_status": weekly.get("status"),
        "industry_status": industry.get("status"),
        "financial_freshness_status": freshness.get("status"),
        "financial_stale_or_missing_count": freshness.get("stale_or_missing_count"),
        "financial_profile_status": profiles.get("status"),
        "outcome_status": outcomes.get("status"),
        "outcome_completed_windows_present": outcomes.get("completed_windows_present"),
        "operating_status": operating.get("status"),
        "review_issues": issues,
        "human_review_required_for_membership_change": True,
        "automatic_candidate_membership_mutations": 0,
        "automatic_research_object_mutations": 0,
        "portfolio_mutations": 0,
        "orders": 0,
        "trade_authority": "NONE",
    }
    write(path, payload)
    return payload


def quarterly_gate(root: Path, cfg: dict[str, Any], as_of: date) -> dict[str, Any]:
    freshness = read(root / cfg["outputs"]["financial_freshness"])
    periods = sorted(
        {
            row.get("latest_report_period")
            for row in freshness.get("rows", [])
            if row.get("latest_report_period")
        }
    )
    latest_period = periods[-1] if periods else None
    path = root / "investment_os_runtime/30_STATE_CURRENT/45_CANDIDATE_OPERATIONS/QUARTERLY_FINANCIAL_RESCREEN_CURRENT.json"
    prior = read(path) if path.exists() else {}
    last_consumed = prior.get("last_consumed_report_period")
    first_install = not prior
    new_period = bool(latest_period and last_consumed and latest_period > last_consumed)
    payload = {
        "state_id": "WP3R_QUARTERLY_FINANCIAL_RESCREEN_CURRENT",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "as_of_date": as_of.isoformat(),
        "latest_report_period_observed": latest_period,
        "last_consumed_report_period": latest_period if first_install else last_consumed,
        "first_install_baseline_only": first_install,
        "new_report_period_detected": new_period,
        "run_full_rescreen_proposal": new_period,
        "status": (
            "BASELINE_INSTALLED_NO_RETROACTIVE_RERUN"
            if first_install
            else "READY_FOR_QUARTERLY_FULL_RESCREEN_PROPOSAL"
            if new_period
            else "NO_NEW_FINANCIAL_WATERMARK_NO_RERUN"
        ),
        "last_proposal_path": prior.get("last_proposal_path"),
        "last_proposal_generated_at": prior.get("last_proposal_generated_at"),
        "candidate_membership_mutations": 0,
        "research_object_mutations": 0,
        "portfolio_mutations": 0,
        "orders": 0,
        "trade_authority": "NONE",
    }
    write(path, payload)
    return payload


def quarterly_complete(root: Path, proposal_dir: str, as_of: date) -> dict[str, Any]:
    path = root / "investment_os_runtime/30_STATE_CURRENT/45_CANDIDATE_OPERATIONS/QUARTERLY_FINANCIAL_RESCREEN_CURRENT.json"
    state = read(path)
    if not state.get("run_full_rescreen_proposal"):
        raise SystemExit("QUARTERLY_RESCREEN_NOT_AUTHORIZED_BY_NEW_REPORT_WATERMARK")
    proposal_path = root / proposal_dir
    manifest = proposal_path / "WP3_3_4_MANIFEST.json"
    if not manifest.exists():
        raise SystemExit("QUARTERLY_PROPOSAL_MANIFEST_MISSING")
    manifest_payload = read(manifest)
    state.update(
        {
            "status": "QUARTERLY_FULL_RESCREEN_PROPOSAL_COMPLETE_HUMAN_MERGE_REQUIRED",
            "last_consumed_report_period": state["latest_report_period_observed"],
            "run_full_rescreen_proposal": False,
            "last_proposal_path": proposal_dir,
            "last_proposal_generated_at": datetime.now(timezone.utc).isoformat(),
            "last_proposal_manifest_hash": digest(manifest_payload),
            "candidate_membership_mutations": 0,
            "research_object_mutations": 0,
            "portfolio_mutations": 0,
            "orders": 0,
            "trade_authority": "NONE",
        }
    )
    write(path, state)
    return state


def finalize_acceptance(root: Path, cfg: dict[str, Any], cadence_registry: dict[str, Any]) -> dict[str, Any]:
    outputs = cfg["outputs"]
    weekly = read(root / outputs["weekly_price_screen"])
    industry = read(root / outputs["industry_quality"])
    profiles = read(root / outputs["financial_profile_readiness"])
    outcomes = read(root / outputs["candidate_outcomes"])
    monthly_path = root / "investment_os_runtime/30_STATE_CURRENT/45_CANDIDATE_OPERATIONS/MONTHLY_CANDIDATE_REVIEW_CURRENT.json"
    quarterly_path = root / "investment_os_runtime/30_STATE_CURRENT/45_CANDIDATE_OPERATIONS/QUARTERLY_FINANCIAL_RESCREEN_CURRENT.json"
    monthly = read(monthly_path)
    quarterly = read(quarterly_path)
    acceptance = read(root / outputs["acceptance"])
    capability_ready = (
        weekly.get("status") == "PASS_WEEKLY_PRICE_SCREEN_NO_MEMBERSHIP_MUTATION"
        and weekly.get("covered_count") == 73
        and industry.get("status") == "PASS_CANONICAL_INDUSTRY_QUALITY_GATE"
        and profiles.get("status") == "INDEPENDENT_FINANCIAL_SCREENING_PROFILE_ACTIVE_RESEARCH_GRADE_INPUTS_PENDING"
        and outcomes.get("valid_entry_baseline_count") == 2
        and cadence_registry.get("status") == "WP3R_CADENCE_REGISTRY_ACTIVE"
    )
    acceptance.update(
        {
            "status": "WP3R_CONTINUOUS_CANDIDATE_ENGINE_CAPABILITY_ACCEPTED" if capability_ready else "WP3R_CAPABILITY_BLOCKED",
            "capability_readiness": {
                "weekly_price_screen": weekly.get("status"),
                "monthly_candidate_review": monthly.get("status"),
                "quarterly_financial_rescreen_gate": quarterly.get("status"),
                "financial_screening_profiles": profiles.get("status"),
                "financial_research_grade_profiles": "BLOCKED_SPECIALIZED_METRICS_INCOMPLETE",
                "industry_classification": industry.get("status"),
                "outcome_attribution_engine": "ACTIVE_WINDOWS_MATURE_PROSPECTIVELY",
                "outcome_current_status": outcomes.get("status"),
                "cadence_registry": cadence_registry.get("status"),
            },
            "continuous_candidate_engine_complete": capability_ready,
            "candidate_outcome_windows_complete": False,
            "candidate_membership_mutations": 0,
            "research_object_mutations": 0,
            "portfolio_mutations": 0,
            "orders": 0,
            "trade_authority": "NONE",
            "wp4b_unblocked": capability_ready,
            "wp5_unblocked": False,
        }
    )
    write(root / outputs["acceptance"], acceptance)
    return acceptance


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--config", default="automation/wp3_r/config.json")
    parser.add_argument("--mode", required=True, choices=["monthly", "quarterly-gate", "quarterly-complete", "finalize-acceptance"])
    parser.add_argument("--as-of", default=None)
    parser.add_argument("--proposal-dir", default=None)
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    cfg = read(root / args.config)
    as_of = date.fromisoformat(args.as_of or date.today().isoformat())
    if args.mode == "monthly":
        payload = monthly_review(root, cfg, as_of)
    elif args.mode == "quarterly-gate":
        payload = quarterly_gate(root, cfg, as_of)
    elif args.mode == "quarterly-complete":
        if not args.proposal_dir:
            raise SystemExit("--proposal-dir required")
        payload = quarterly_complete(root, args.proposal_dir, as_of)
    else:
        registry = read(root / "investment_os_runtime/60_OPERATIONS_AND_EVENT/WP3_R_CADENCE_REGISTRY_CURRENT.json")
        payload = finalize_acceptance(root, cfg, registry)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
