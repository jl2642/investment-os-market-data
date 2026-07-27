from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TRADE_AUTHORITY = "NONE"
SOURCE_PR = 151
SOURCE_BRANCH = "agent/wp5-g-real-account-structure"
WP5_F_PR = 150
WP5_F_MERGE_SHA = "467280d54e4dbe58204e0137e4f9639550c72dca"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def upsert_asset(registry: dict, asset: dict) -> None:
    assets = registry.setdefault("assets", [])
    for index, row in enumerate(assets):
        if row.get("asset_id") == asset["asset_id"]:
            assets[index] = {**row, **asset}
            return
    assets.append(asset)


def identity(payload: dict) -> list[dict]:
    return [
        {
            "security_id": row["security_id"],
            "quantity": row["quantity"],
            "available_quantity": row["available_quantity"],
            "unit_cost": row["unit_cost"],
            "cost_basis": row["cost_basis"],
        }
        for row in payload["holdings"]
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--source-head-sha", required=True)
    args = parser.parse_args()

    root = Path(args.repo_root)
    control = root / "investment_os_runtime/00_CONTROL"
    decisions = root / "investment_os_runtime/30_STATE_CURRENT/60_DECISIONS"
    evidence = root / "investment_os_runtime/40_EVIDENCE_AND_LINEAGE/WP5/REAL_ACCOUNT_LOOKTHROUGH"

    real_path = root / "investment_os_runtime/30_STATE_CURRENT/10_REAL_ACCOUNT/REAL_ACCOUNT_POSITIONS_CURRENT.json"
    sim_path = root / "investment_os_runtime/30_STATE_CURRENT/20_SIMULATION/SIMULATION_POSITIONS_CURRENT.json"
    candidate_path = root / "investment_os_runtime/30_STATE_CURRENT/40_CANDIDATE/CANDIDATE_CURRENT.json"
    legacy_decision_path = decisions / "DECISION_PROPOSALS_CURRENT.json"
    execution_path = control / "EXECUTION_REGISTER_CURRENT.json"
    registry_path = control / "AUTHORITATIVE_ASSET_REGISTRY.json"
    wp5f_acceptance_path = control / "WP5_F_POSITION_CONTINUITY_INTERFACE_ACCEPTANCE_RECORD.json"
    semantics_path = control / "CANONICAL_PROMOTION_SEMANTICS_V2.json"
    lookthrough_path = evidence / "WP5_REAL_ACCOUNT_LOOKTHROUGH_CURRENT.json"
    review_path = decisions / "WP5_REAL_ACCOUNT_STRUCTURE_REVIEW_CURRENT.json"
    acceptance_path = control / "WP5_G_REAL_ACCOUNT_STRUCTURE_ACCEPTANCE_RECORD.json"

    real = read_json(real_path)
    sim = read_json(sim_path)
    execution = read_json(execution_path)
    registry = read_json(registry_path)
    wp5f = read_json(wp5f_acceptance_path)
    semantics = read_json(semantics_path)
    lookthrough = read_json(lookthrough_path)
    review = read_json(review_path)

    if len(real["holdings"]) != 7:
        raise ValueError("Expected seven Real-account holdings")
    if len(lookthrough["products"]) != 7:
        raise ValueError("Expected seven product look-through records")
    real_ids = {row["security_id"] for row in real["holdings"]}
    evidence_ids = {row["security_id"] for row in lookthrough["products"]}
    if real_ids != evidence_ids:
        raise ValueError(f"Look-through mismatch: {sorted(real_ids ^ evidence_ids)}")

    total_assets = float(real["summary"]["account_total_assets"])
    aggregate_weight = sum(float(row["account_weight"]) for row in lookthrough["aggregate_exposures"].values())
    if abs(aggregate_weight - 1.0) > 0.0001:
        raise ValueError(f"Aggregate sleeve weights do not sum to one: {aggregate_weight}")
    if abs(float(lookthrough["account_total_assets_rmb"]) - total_assets) > 0.01:
        raise ValueError("Account total mismatch")
    if review["recommendation_summary"]["implementation_ready_count"] != 0:
        raise ValueError("WP5-G must not be implementation ready")
    if review["recommendation_summary"]["immediate_real_account_trade"] != "NONE":
        raise ValueError("WP5-G must not create a Real-account trade")

    protected_hashes = {
        "real_identity_sha256": hashlib.sha256(json.dumps(identity(real), sort_keys=True).encode()).hexdigest(),
        "simulation_identity_sha256": hashlib.sha256(json.dumps(identity(sim), sort_keys=True).encode()).hexdigest(),
        "candidate_sha256": hashlib.sha256(candidate_path.read_bytes()).hexdigest(),
        "legacy_decisions_sha256": hashlib.sha256(legacy_decision_path.read_bytes()).hexdigest(),
    }

    now = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
    source_head_sha = str(args.source_head_sha)

    wp5f.update(
        {
            "accepted_on_main": True,
            "accepted_pr": WP5_F_PR,
            "wp5_f_merge_sha": WP5_F_MERGE_SHA,
            "status": "WP5_F_ACCEPTED_ON_MAIN",
            "promotion_evidence": "MERGED_PR_AND_FILE_PRESENCE",
            "trade_authority": TRADE_AUTHORITY,
        }
    )
    write_json(wp5f_acceptance_path, wp5f)

    execution.update(
        {
            "current_step": "WP5_G_REAL_ACCOUNT_STRUCTURE_REVIEW_CURRENT_IF_PRESENT_ON_MAIN",
            "github_merge_sha": WP5_F_MERGE_SHA,
            "latest_governed_merge_sha": WP5_F_MERGE_SHA,
            "next_task": "WP5_H_SIMULATION_NON_P0_RESEARCH_TRIAGE_AFTER_WP5_G_PRESENT_ON_MAIN",
            "overall_status": "WP5_G_CONDITIONAL_CURRENT_IF_PRESENT_ON_MAIN_NO_ACTION",
            "status_date": now[:10],
            "trade_authority": TRADE_AUTHORITY,
        }
    )
    wp5 = execution.setdefault("wp5", {})
    wp5.update(
        {
            "branch": SOURCE_BRANCH,
            "status": "REAL_ACCOUNT_STRUCTURE_REVIEW_CURRENT_IF_PRESENT_ON_MAIN",
            "source_pr": SOURCE_PR,
            "source_head_sha": source_head_sha,
            "promotion_evidence": "GIT_HISTORY_ON_MAIN",
            "canonical_promotion_semantics_v2": True,
            "position_continuity_interface_accepted_on_main": True,
            "position_continuity_interface_merge_sha": WP5_F_MERGE_SHA,
            "real_account_lookthrough_complete": True,
            "real_account_lookthrough_path": str(lookthrough_path.relative_to(root)),
            "real_account_structure_review_complete": True,
            "real_account_structure_review_path": str(review_path.relative_to(root)),
            "bond_fund_lookthrough_complete": False,
            "sp500_duplicate_exposure_identified": True,
            "a_share_core_satellite_role_defined": True,
            "ready_for_user_decision_count": 0,
            "position_mutation_allowed": False,
            "order_execution_allowed": False,
            "trade_authority": TRADE_AUTHORITY,
        }
    )
    write_json(execution_path, execution)

    registry["active_branch_candidate"] = SOURCE_BRANCH
    registry["github_merge_sha"] = WP5_F_MERGE_SHA
    registry["latest_governed_merge_sha"] = WP5_F_MERGE_SHA
    registry["date"] = now[:10]
    registry["registry_status"] = "WP5_G_CURRENT_IF_PRESENT_ON_MAIN"
    registry["status"] = "GITHUB_CURRENT_IF_PR151_MERGED_FILE_LIBRARY_PENDING"
    for asset in (
        {
            "asset_id": "CANONICAL_PROMOTION_SEMANTICS_V2",
            "authority": "CANONICAL_CURRENT_IF_PRESENT_ON_MAIN",
            "format": "JSON",
            "location": str(semantics_path.relative_to(root)),
            "role": "Durable merged-PR and file-presence Canonical promotion contract",
        },
        {
            "asset_id": "WP5_REAL_ACCOUNT_LOOKTHROUGH_CURRENT",
            "authority": "CANONICAL_CURRENT_IF_PRESENT_ON_MAIN",
            "format": "JSON",
            "location": str(lookthrough_path.relative_to(root)),
            "role": "Official-source product and exposure look-through for all Real-account holdings",
        },
        {
            "asset_id": "WP5_REAL_ACCOUNT_STRUCTURE_REVIEW_CURRENT",
            "authority": "CANONICAL_CURRENT_IF_PRESENT_ON_MAIN",
            "format": "JSON",
            "location": str(review_path.relative_to(root)),
            "role": "Conditional Real-account structural decision review with zero implementation-ready actions",
        },
        {
            "asset_id": "WP5_G_REAL_ACCOUNT_STRUCTURE_ACCEPTANCE",
            "authority": "CANONICAL_CURRENT_IF_PRESENT_ON_MAIN",
            "format": "JSON",
            "location": str(acceptance_path.relative_to(root)),
            "role": "WP5-G lineage, evidence, portfolio-structure and zero-mutation acceptance",
        },
    ):
        upsert_asset(
            registry,
            {
                **asset,
                "source_pr": SOURCE_PR,
                "source_head_sha": source_head_sha,
                "promotion_evidence": "MERGED_PR_AND_FILE_PRESENCE",
                "status": "CURRENT_IF_PRESENT_ON_MAIN",
                "trade_authority": TRADE_AUTHORITY,
            },
        )
    write_json(registry_path, registry)

    acceptance = {
        "schema_version": "1.0.0",
        "acceptance_id": "WP5_G_REAL_ACCOUNT_STRUCTURE_ACCEPTANCE_V1",
        "generated_at": now,
        "status": "CURRENT_IF_PRESENT_ON_MAIN",
        "source_pr": SOURCE_PR,
        "source_branch": SOURCE_BRANCH,
        "source_head_sha": source_head_sha,
        "promotion_evidence": "MERGED_PR_AND_FILE_PRESENCE",
        "wp5_f_pr": WP5_F_PR,
        "wp5_f_merge_sha": WP5_F_MERGE_SHA,
        "real_holding_count": 7,
        "lookthrough_record_count": 7,
        "structural_finding_count": len(review["structural_findings"]),
        "decision_queue_count": len(review["decision_queue"]),
        "ready_for_user_decision_count": 0,
        "implementation_ready_count": 0,
        "protected_state_hashes": protected_hashes,
        "evidence_limitations": [
            "110017.OF current Q2 holdings and risk decomposition were not retrievable through the official public route used in this run.",
            "Three-bond-fund security-level overlap, duration, leverage and convertible beta remain incomplete.",
            "S&P500 single-vehicle selection requires a same-session execution-quality comparison."
        ],
        "economic_mutations": {
            "real_account": 0,
            "simulation": 0,
            "candidate_membership": 0,
            "orders": 0,
        },
        "trade_authority": TRADE_AUTHORITY,
    }
    write_json(acceptance_path, acceptance)

    print(
        json.dumps(
            {
                "source_pr": SOURCE_PR,
                "source_head_sha": source_head_sha,
                "real_holdings": 7,
                "structural_findings": len(review["structural_findings"]),
                "ready": 0,
                "mutations": 0,
                "orders": 0,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
