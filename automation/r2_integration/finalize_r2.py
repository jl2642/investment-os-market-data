#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


WP2_ACCEPTANCE = "investment_os_runtime/00_CONTROL/WP2_R_PORTFOLIO_CURRENT_ACCEPTANCE_RECORD.json"
WP3_ACCEPTANCE = "investment_os_runtime/00_CONTROL/WP3_R_CANDIDATE_REFRESH_ACCEPTANCE_RECORD.json"
WP4B_ACCEPTANCE = "investment_os_runtime/00_CONTROL/WP4_B_CORE2_HARDENING_ACCEPTANCE_RECORD.json"
R2_ACCEPTANCE = "investment_os_runtime/00_CONTROL/R2_PRODUCT_CAPABILITY_ACCEPTANCE_CURRENT.json"
R2_STATUS = "investment_os_runtime/00_CONTROL/R2_STATUS_CURRENT.md"
EXECUTION_REGISTER = "investment_os_runtime/00_CONTROL/EXECUTION_REGISTER_CURRENT.json"
ASSET_REGISTRY = "investment_os_runtime/00_CONTROL/AUTHORITATIVE_ASSET_REGISTRY.json"
GAP_REGISTER = "investment_os_runtime/00_CONTROL/WP2_WP4_CAPABILITY_GAP_REGISTER_CURRENT.json"


def read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def digest(payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def canonical_asset_id(key: str) -> str:
    return key.upper()


def add_asset(registry: dict[str, Any], key: str, path: str, role: str, state: str) -> None:
    """Upsert an R2 asset without changing the Canonical Registry container shape."""
    assets = registry.setdefault("assets", [])
    if isinstance(assets, list):
        asset_id = canonical_asset_id(key)
        record = {
            "asset_id": asset_id,
            "location": path,
            "role": role,
            "status": state,
            "format": Path(path).suffix.lstrip(".").upper() or "DIRECTORY",
            "authority": "CANONICAL_CURRENT",
            "trade_authority": "NONE",
        }
        for index, existing in enumerate(assets):
            if isinstance(existing, dict) and existing.get("asset_id") == asset_id:
                preserved = dict(existing)
                preserved.update(record)
                assets[index] = preserved
                return
        assets.append(record)
        return
    if isinstance(assets, dict):
        assets[key] = {
            "path": path,
            "role": role,
            "state": state,
            "format": Path(path).suffix.lstrip(".").upper() or "DIRECTORY",
            "authority": "CANONICAL_CURRENT",
            "trade_authority": "NONE",
        }
        return
    raise SystemExit(f"AUTHORITATIVE_ASSET_REGISTRY_ASSETS_UNSUPPORTED_TYPE:{type(assets).__name__}")


def validate_acceptances(root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    wp2, wp3, wp4b = read(root / WP2_ACCEPTANCE), read(root / WP3_ACCEPTANCE), read(root / WP4B_ACCEPTANCE)
    if wp2.get("status") != "WP2R_RECURRING_PORTFOLIO_CURRENT_READY":
        raise SystemExit(f"WP2R_NOT_READY:{wp2.get('status')}")
    if wp3.get("status") != "WP3R_CONTINUOUS_CANDIDATE_ENGINE_CAPABILITY_ACCEPTED":
        raise SystemExit(f"WP3R_NOT_READY:{wp3.get('status')}")
    if not wp3.get("continuous_candidate_engine_complete"):
        raise SystemExit("WP3R_CONTINUOUS_ENGINE_FLAG_FALSE")
    if wp4b.get("status") != "WP4B_CORE2_RESEARCH_HARDENING_ACCEPTED_RESEARCH_ONLY":
        raise SystemExit(f"WP4B_NOT_READY:{wp4b.get('status')}")
    for name, payload in (("WP2R", wp2), ("WP3R", wp3), ("WP4B", wp4b)):
        controls = payload.get("controls", {})
        if controls.get("orders", payload.get("orders", 0)) != 0:
            raise SystemExit(f"{name}_ORDER_BOUNDARY_VIOLATION")
        if controls.get("trade_authority", payload.get("trade_authority")) != "NONE":
            raise SystemExit(f"{name}_TRADE_AUTHORITY_VIOLATION")
    return wp2, wp3, wp4b


def gap_r2_status(gap: dict[str, Any]) -> str:
    package = str(gap.get("work_package", ""))
    limitation = str(gap.get("limitation", ""))
    if package == "WP2":
        return "CLOSED_OR_NON_BLOCKING_DISCLOSED_BY_WP2_R"
    if package == "WP3":
        if limitation == "CANDIDATE_20_60_120_DAY_OUTCOME_WINDOWS_INCOMPLETE":
            return "EXPLICITLY_GATED_PROSPECTIVE_WINDOWS_MATURING"
        if limitation == "ALPHA_CLAIM_NOT_ALLOWED":
            return "EXPLICITLY_GATED_NO_ALPHA_CLAIM_UNTIL_OUTCOME_WINDOWS_MATURE"
        return "CLOSED_OR_EXPLICITLY_GATED_BY_WP3_R"
    if package == "WP4":
        if limitation == "READY_FOR_USER_DECISION_COUNT_ZERO":
            return "ROUTED_TO_SEPARATE_GOVERNED_WP5_DECISION_PHASE"
        return "CLOSED_BY_WP4_B_RESEARCH_HARDENING"
    return "RETAINED_NON_BLOCKING_LEGACY_GAP"


def update_gap_register(register: dict[str, Any], mode: str) -> dict[str, Any]:
    post_merge = mode == "post-merge"
    register["status"] = (
        "R2_PRODUCT_CAPABILITY_HARDENING_ACCEPTED_ON_MAIN"
        if post_merge
        else "R2_PRODUCT_CAPABILITY_HARDENING_ACCEPTED_ON_BRANCH_PENDING_MERGE"
    )
    register["next_task"] = (
        "EXPLICITLY_START_WP5_PORTFOLIO_DECISION_PHASE"
        if post_merge
        else "USER_MERGE_PR_145_TO_MAIN"
    )
    register["wp5_gate"] = (
        "READY_PENDING_EXPLICIT_WP5_START"
        if post_merge
        else "BLOCKED_PENDING_R2_MERGE"
    )
    register["r2_closure"] = {
        "wp2_r_portfolio_current": "CLOSED_RECURRING_PORTFOLIO_CURRENT_READY",
        "wp3_r_candidate_refresh": "CLOSED_CONTINUOUS_CANDIDATE_ENGINE_READY",
        "wp4_b_core2_research": "CLOSED_CORE2_RESEARCH_HARDENING_READY_RESEARCH_ONLY",
        "wp5": (
            "READY_PENDING_EXPLICIT_WP5_START"
            if post_merge
            else "BLOCKED_PENDING_R2_MERGE"
        ),
        "legacy_r1_gaps_blocking_wp5": 0,
        "automatic_real_account_mutations": 0,
        "automatic_simulation_mutations": 0,
        "candidate_membership_mutations": 0,
        "orders": 0,
        "trade_authority": "NONE",
    }
    for gap in register.get("gaps", []):
        if not isinstance(gap, dict):
            continue
        gap["r2_status"] = gap_r2_status(gap)
        gap["blocks_wp5"] = False
        gap["resolution_route"] = (
            "R2_ACCEPTED_ON_MAIN_RETAIN_AS_OPERATING_LIMIT_OR_WP5_INPUT"
            if post_merge
            else "R2_ACCEPTED_ON_BRANCH_PENDING_USER_MERGE"
        )
    return register


def update_execution_register(
    register: dict[str, Any],
    *,
    mode: str,
    pr_number: int,
    merge_sha: str | None,
    acceptance_hash: str,
) -> dict[str, Any]:
    post_merge = mode == "post-merge"
    register["current_step"] = (
        "R2_PRODUCT_CAPABILITY_HARDENING_ACCEPTED_ON_MAIN"
        if post_merge
        else "R2_PRODUCT_CAPABILITY_HARDENING_ACCEPTED_ON_BRANCH_PENDING_USER_MERGE"
    )
    register["next_task"] = (
        "EXPLICITLY_START_WP5_PORTFOLIO_DECISION_PHASE"
        if post_merge
        else "USER_MERGE_PR_145_TO_MAIN"
    )
    register["overall_status"] = (
        "R2_ACCEPTED_ON_MAIN_WP5_READY_PENDING_EXPLICIT_START"
        if post_merge
        else "R2_ACCEPTED_ON_BRANCH_PENDING_USER_MERGE_WP5_BLOCKED"
    )
    if post_merge and merge_sha:
        register["latest_governed_merge_sha"] = merge_sha
        register["github_merge_sha"] = merge_sha
    register["r2"] = {
        "program": "R2_PRODUCT_CAPABILITY_HARDENING",
        "workstreams": ["WP2-R", "WP3-R", "WP4-B"],
        "pr_number": pr_number,
        "branch": "agent/r2-product-capability-hardening",
        "merge_sha": merge_sha,
        "status": (
            "R2_PRODUCT_CAPABILITY_HARDENING_ACCEPTED_ON_MAIN"
            if post_merge
            else "R2_ACCEPTED_ON_BRANCH_PENDING_USER_MERGE"
        ),
        "acceptance_path": R2_ACCEPTANCE,
        "acceptance_semantic_hash": acceptance_hash,
        "wp5_status": (
            "READY_PENDING_EXPLICIT_WP5_START"
            if post_merge
            else "BLOCKED_PENDING_R2_MERGE"
        ),
        "economic_mutations": {
            "real_account": 0,
            "simulation": 0,
            "candidate_membership": 0,
            "orders": 0,
        },
        "trade_authority": "NONE",
    }
    return register


def render_status(mode: str, merge_sha: str | None) -> str:
    phase = "ACCEPTED_ON_MAIN" if mode == "post-merge" else "ACCEPTED_ON_BRANCH_PENDING_USER_MERGE"
    wp5 = "READY_PENDING_EXPLICIT_WP5_START" if mode == "post-merge" else "BLOCKED_PENDING_R2_MERGE"
    next_task = "EXPLICITLY_START_WP5_PORTFOLIO_DECISION_PHASE" if mode == "post-merge" else "USER_MERGE_PR_145_TO_MAIN"
    return f"""# R2 Product Capability Status Current

- R2 status: `{phase}`
- PR: `#145`
- Merge SHA: `{merge_sha or 'PENDING'}`
- WP2-R: `RECURRING_PORTFOLIO_CURRENT_READY`
- WP3-R: `CONTINUOUS_CANDIDATE_ENGINE_CAPABILITY_ACCEPTED`
- WP4-B: `CORE2_RESEARCH_HARDENING_ACCEPTED_RESEARCH_ONLY`
- WP5: `{wp5}`
- Next task: `{next_task}`
- Real-account mutations: `0`
- Simulation economic mutations: `0`
- Candidate membership mutations: `0`
- Orders: `0`
- Trade authority: `NONE`

R2 adds product capability without rerunning WP2-WP4 screening or changing accepted portfolio and Candidate economic states. WP5 remains a separate governed portfolio-decision phase.
"""


def with_stable_generated_at(path: Path, acceptance_without_timestamp: dict[str, Any]) -> dict[str, Any]:
    """Preserve generated_at when the acceptance content is otherwise identical."""
    generated_at = datetime.now(timezone.utc).isoformat()
    if path.exists():
        existing = read(path)
        comparable_existing = dict(existing)
        existing_generated_at = comparable_existing.pop("generated_at", None)
        if comparable_existing == acceptance_without_timestamp and existing_generated_at:
            generated_at = str(existing_generated_at)
    result = dict(acceptance_without_timestamp)
    result["generated_at"] = generated_at
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--mode", choices=["branch", "post-merge"], default="branch")
    parser.add_argument("--pr-number", type=int, default=145)
    parser.add_argument("--merge-sha", default=None)
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    if args.mode == "post-merge" and not args.merge_sha:
        raise SystemExit("POST_MERGE_REQUIRES_MERGE_SHA")

    wp2, wp3, wp4b = validate_acceptances(root)
    acceptance_without_timestamp = {
        "acceptance_id": "R2_PRODUCT_CAPABILITY_ACCEPTANCE_V1",
        "status": (
            "R2_PRODUCT_CAPABILITY_HARDENING_ACCEPTED_ON_MAIN"
            if args.mode == "post-merge"
            else "R2_PRODUCT_CAPABILITY_HARDENING_ACCEPTED_ON_BRANCH_PENDING_MERGE"
        ),
        "pr_number": args.pr_number,
        "merge_sha": args.merge_sha,
        "workstreams": {
            "wp2_r": {"status": wp2["status"], "path": WP2_ACCEPTANCE, "semantic_hash": digest(wp2)},
            "wp3_r": {"status": wp3["status"], "path": WP3_ACCEPTANCE, "semantic_hash": digest(wp3)},
            "wp4_b": {"status": wp4b["status"], "path": WP4B_ACCEPTANCE, "semantic_hash": digest(wp4b)},
        },
        "capabilities": {
            "recurring_portfolio_current": True,
            "user_transaction_delta_only": True,
            "automatic_price_and_nav_refresh": True,
            "broker_verification_separate": True,
            "weekly_candidate_price_screen": True,
            "monthly_candidate_review": True,
            "report_watermark_quarterly_rescreen": True,
            "financial_sector_independent_screening": True,
            "industry_security_master": True,
            "candidate_20_60_120_outcome_engine": True,
            "core2_hardened_research": True,
            "driver_based_scenarios": True,
            "position_level_portfolio_fit": True,
            "event_monitoring": True,
        },
        "prospective_or_gated_items": {
            "candidate_20_60_120_windows_mature_over_time": True,
            "specialized_financial_research_grade_metrics_remain_required": True,
            "wp5_requires_separate_explicit_start": True,
        },
        "economic_mutations": {
            "real_account": 0,
            "simulation": 0,
            "candidate_membership": 0,
            "orders": 0,
        },
        "wp5_status": (
            "READY_PENDING_EXPLICIT_WP5_START"
            if args.mode == "post-merge"
            else "BLOCKED_PENDING_R2_MERGE"
        ),
        "trade_authority": "NONE",
    }
    acceptance = with_stable_generated_at(root / R2_ACCEPTANCE, acceptance_without_timestamp)
    write(root / R2_ACCEPTANCE, acceptance)

    execution = update_execution_register(
        read(root / EXECUTION_REGISTER),
        mode=args.mode,
        pr_number=args.pr_number,
        merge_sha=args.merge_sha,
        acceptance_hash=digest(acceptance),
    )
    write(root / EXECUTION_REGISTER, execution)

    registry = read(root / ASSET_REGISTRY)
    registry["registry_status"] = (
        "R2_CAPABILITY_ASSETS_ACCEPTED_ON_MAIN"
        if args.mode == "post-merge"
        else "R2_CAPABILITY_ASSETS_ACCEPTED_PENDING_MERGE"
    )
    if args.mode == "post-merge" and args.merge_sha:
        registry["latest_governed_merge_sha"] = args.merge_sha
        registry["github_merge_sha"] = args.merge_sha
    assets = {
        "real_account_positions_current": ("investment_os_runtime/30_STATE_CURRENT/10_REAL_ACCOUNT/REAL_ACCOUNT_POSITIONS_CURRENT.json", "WP2-R real-account Position Current", "CURRENT"),
        "simulation_positions_current": ("investment_os_runtime/30_STATE_CURRENT/20_SIMULATION/SIMULATION_POSITIONS_CURRENT.json", "WP2-R simulation Position Current", "CURRENT"),
        "portfolio_marks_current": ("investment_os_runtime/30_STATE_CURRENT/25_PORTFOLIO_MARKS/PORTFOLIO_MARKS_CURRENT.json", "WP2-R tracked marks Current", "CURRENT"),
        "wp2_r_acceptance": (WP2_ACCEPTANCE, "WP2-R acceptance", "ACCEPTED"),
        "candidate_refresh_current": ("investment_os_runtime/30_STATE_CURRENT/45_CANDIDATE_OPERATIONS/CANDIDATE_REFRESH_CURRENT.json", "WP3-R continuous Candidate operating Current", "CURRENT"),
        "security_industry_master_current": ("investment_os_runtime/40_EVIDENCE_AND_LINEAGE/WP3_R/INDUSTRY_MASTER/SECURITY_INDUSTRY_MASTER_CURRENT.json", "WP3-R A-share industry Security Master", "CURRENT"),
        "financial_sector_screening_current": ("investment_os_runtime/40_EVIDENCE_AND_LINEAGE/WP3_R/FINANCIAL_SECTOR_SCREENING/FINANCIAL_SECTOR_SCREENING_SCORE_CURRENT.json", "WP3-R independent financial-sector screening", "CURRENT_RESEARCH_LIMITED"),
        "candidate_outcome_current": ("investment_os_runtime/70_ATTRIBUTION_AND_CALIBRATION/CANDIDATE_OUTCOME_CURRENT.json", "WP3-R prospective 20/60/120 Candidate outcomes", "CURRENT_PROSPECTIVE"),
        "wp3_r_acceptance": (WP3_ACCEPTANCE, "WP3-R acceptance", "ACCEPTED"),
        "wp4b_core2_current": ("investment_os_runtime/30_STATE_CURRENT/30_RESEARCH/WP4B_CORE2_RESEARCH_CURRENT.json", "WP4-B hardened Core2 research Current", "CURRENT_RESEARCH_ONLY"),
        "wp4b_acceptance": (WP4B_ACCEPTANCE, "WP4-B acceptance", "ACCEPTED_RESEARCH_ONLY"),
        "r2_acceptance": (R2_ACCEPTANCE, "Integrated R2 product-capability acceptance", "ACCEPTED"),
        "r2_status_current": (R2_STATUS, "Human-readable R2 status pointer", "CURRENT"),
    }
    for key, (path, role, state) in assets.items():
        add_asset(registry, key, path, role, state)
    write(root / ASSET_REGISTRY, registry)

    gaps = update_gap_register(read(root / GAP_REGISTER), args.mode)
    write(root / GAP_REGISTER, gaps)
    (root / R2_STATUS).write_text(render_status(args.mode, args.merge_sha), encoding="utf-8")

    print(json.dumps({
        "status": acceptance["status"],
        "wp5_status": acceptance["wp5_status"],
        "next_task": execution["next_task"],
        "pr_number": args.pr_number,
        "merge_sha": args.merge_sha,
        "real_account_mutations": 0,
        "simulation_mutations": 0,
        "candidate_membership_mutations": 0,
        "orders": 0,
        "trade_authority": "NONE",
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
