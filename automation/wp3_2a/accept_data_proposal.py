from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


INVESTMENT_OBJECTS = {
    "real_account": "investment_os_runtime/30_STATE_CURRENT/10_REAL_ACCOUNT/REAL_ACCOUNT_CURRENT.json",
    "simulation": "investment_os_runtime/30_STATE_CURRENT/20_SIMULATION/SIMULATION_LEDGER_CURRENT.json",
    "research": "investment_os_runtime/30_STATE_CURRENT/30_RESEARCH/RESEARCH_OBJECTS_CURRENT.json",
    "thesis": "investment_os_runtime/30_STATE_CURRENT/31_RESEARCH/THESIS_CURRENT.json",
    "candidate": "investment_os_runtime/30_STATE_CURRENT/40_CANDIDATE/CANDIDATE_CURRENT.json",
}


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_security_codes(path: Path) -> set[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return {
            str(row.get("security_code") or "").strip()
            for row in csv.DictReader(handle)
            if str(row.get("security_code") or "").strip()
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--proposal-path", required=True)
    parser.add_argument("--confirmation", required=True)
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    if args.confirmation != "ACCEPT_UNIVERSE_PROPOSAL":
        raise SystemExit("confirmation mismatch")

    repo = Path(args.repo_root)
    proposal = (repo / args.proposal_path).resolve()
    if repo.resolve() not in proposal.parents:
        raise SystemExit("proposal outside repository")

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    manifest = json.loads((proposal / "PROPOSAL_MANIFEST.json").read_text(encoding="utf-8"))
    lineage = json.loads((proposal / "LINEAGE_ACCEPTANCE.json").read_text(encoding="utf-8"))
    if lineage.get("status") != "PASS":
        raise SystemExit("proposal lineage not PASS")

    data = proposal / "A_SHARE_FULL_UNIVERSE.csv"
    if sha(data) != manifest["data_sha256"]:
        raise SystemExit("proposal data hash mismatch")

    scope = config.get("ordinary_a_share_scope") or {}
    scope_exceptions = list(scope.get("scope_exceptions") or [])
    proposal_codes = read_security_codes(data)
    exception_codes = {
        str(item.get("security_code") or "").strip()
        for item in scope_exceptions
        if str(item.get("security_code") or "").strip()
    }
    unexpected_special_securities = sorted(proposal_codes & exception_codes)
    if unexpected_special_securities:
        raise SystemExit(
            "special securities present in ordinary A-share universe: "
            + ",".join(unexpected_special_securities)
        )

    before = {key: sha(repo / value) for key, value in INVESTMENT_OBJECTS.items()}

    current = repo / config["current_root"]
    if current.exists():
        shutil.rmtree(current)
    current.mkdir(parents=True)
    for name in [
        "A_SHARE_FULL_UNIVERSE.csv",
        "ACQUISITION_MANIFEST.json",
        "LINEAGE_ACCEPTANCE.json",
        "PROPOSAL_MANIFEST.json",
        "ZERO_INVESTMENT_MUTATION_PROOF.json",
    ]:
        shutil.copy2(proposal / name, current / name)
    if (proposal / "RAW").exists():
        shutil.copytree(proposal / "RAW", current / "RAW")

    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    current_hash = sha(current / "A_SHARE_FULL_UNIVERSE.csv")
    session_compact = manifest["session"].replace("-", "")

    binding_path = repo / "investment_os_runtime/50_MARKET_CAPABILITY_BINDINGS/A_SHARE_CURRENT.json"
    binding = json.loads(binding_path.read_text(encoding="utf-8"))
    binding.pop("accepted_merge_sha", None)
    binding.pop("accepted_at", None)
    binding.update(
        {
            "binding_id": "MARKET_BINDING_A_SHARE_WP3_2A_CURRENT",
            "run_id": "WP3_2A_UNIVERSE_CURRENT_" + session_compact,
            "status": "ACCEPTED_ON_MAIN",
            "as_of_date": manifest["session"],
            "generated_at": generated_at,
            "source_provider": manifest["provider"],
            "authority": "DATA_EVIDENCE_RESEARCH_PRIORITY_ONLY",
            "promotion_authority": "HUMAN_MERGE_TO_MAIN",
            "promotion_evidence": "GIT_HISTORY",
            "live_action_scope": "RESEARCH_AND_PROPOSAL_ONLY_CURRENT_ACCEPTED_NO_AUTOMATIC_ADMISSION_OR_ORDER_EXECUTION",
            "trade_authority": "NONE",
        }
    )
    binding.setdefault("datasets", {})["universe"] = {
        "path": str((current / "A_SHARE_FULL_UNIVERSE.csv").relative_to(repo)),
        "rows": manifest["rows"],
        "sha256": current_hash,
        "maximum_age_calendar_days": 7,
        "stale_behavior": "LABEL_AND_RESTRICT",
    }
    binding["datasets"]["daily_market_snapshot"] = {
        "path": str((current / "A_SHARE_FULL_UNIVERSE.csv").relative_to(repo)),
        "rows": manifest["rows"],
        "sha256": current_hash,
        "maximum_age_calendar_days": 3,
        "requires_latest_completed_session": True,
        "stale_behavior": "BLOCK",
    }
    binding.setdefault("capability_summary", {})["full_market_universe"] = manifest["rows"]

    scope_record = repo / "investment_os_runtime/00_CONTROL/WP3_2A_UNIVERSE_SCOPE_EXCEPTIONS_CURRENT.json"
    scope_record.write_text(
        json.dumps(
            {
                "record_id": "WP3_2A_UNIVERSE_SCOPE_EXCEPTIONS_" + session_compact,
                "status": "ACCEPTED_ON_MAIN",
                "session": manifest["session"],
                "promotion_authority": "HUMAN_MERGE_TO_MAIN",
                "promotion_evidence": "GIT_HISTORY",
                "universe_classification": "ORDINARY_A_SHARES",
                "includes": scope.get("includes", []),
                "excludes": scope.get("excludes", []),
                "scope_exceptions": scope_exceptions,
                "interpretation_rule": "A scope exception must not be interpreted as a delisting or automatic Candidate removal.",
                "candidate_membership_mutations": 0,
                "orders": 0,
                "trade_authority": "NONE",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    binding["universe_scope"] = {
        "classification": "ORDINARY_A_SHARES",
        "includes": scope.get("includes", []),
        "excludes": scope.get("excludes", []),
        "scope_exception_count": len(scope_exceptions),
        "scope_exception_record": str(scope_record.relative_to(repo)),
    }
    binding["wp3_2a_lineage"] = {
        "proposal_id": manifest["proposal_id"],
        "lineage_status": "PASS",
        "lineage_path": str((current / "LINEAGE_ACCEPTANCE.json").relative_to(repo)),
        "provider_change_reviewed_by_merge": True,
        "scope_exceptions_reviewed_by_merge": True,
        "automatic_candidate_admission": False,
        "orders": 0,
    }
    binding_path.write_text(
        json.dumps(binding, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    record = repo / "investment_os_runtime/00_CONTROL/WP3_2A_UNIVERSE_ACCEPTANCE_RECORD.json"
    record.write_text(
        json.dumps(
            {
                "record_id": "WP3_2A_UNIVERSE_ACCEPTANCE_" + session_compact,
                "status": "ACCEPTED_ON_MAIN",
                "proposal_id": manifest["proposal_id"],
                "session": manifest["session"],
                "provider": manifest["provider"],
                "rows": manifest["rows"],
                "data_sha256": current_hash,
                "promotion_authority": "HUMAN_MERGE_TO_MAIN",
                "promotion_evidence": "GIT_HISTORY",
                "universe_classification": "ORDINARY_A_SHARES",
                "scope_exception_count": len(scope_exceptions),
                "candidate_membership_mutations": 0,
                "research_object_mutations": 0,
                "simulation_trade_mutations": 0,
                "real_account_mutations": 0,
                "orders": 0,
                "trade_authority": "NONE",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    execution_path = repo / "investment_os_runtime/00_CONTROL/EXECUTION_REGISTER_CURRENT.json"
    execution = json.loads(execution_path.read_text(encoding="utf-8"))
    execution.pop("github_merge_sha", None)
    execution.update(
        {
            "register_id": "INVESTMENT_ASSISTANT_EXECUTION_REGISTER_V3_2B_READY",
            "status_date": manifest["session"],
            "overall_status": "WP3_IN_PROGRESS_WP3_2A_CLOSED_WP3_2B_READY",
            "current_step": "WP3-2B_GOVERNED_SCREENING",
            "release_id": "INVESTMENT_OS_CURRENT_" + session_compact,
            "release_sequence": int(execution.get("release_sequence", 0)) + 1,
            "trade_authority": "NONE",
        }
    )
    execution["wp3_status"] = {
        "WP3-1": "COMPLETED_STRATEGY_AND_REBUILD_PREPARATION",
        "WP3-2A": "COMPLETED_ACCEPTED_CURRENT",
        "WP3-2B": "READY_FOR_PROTECTED_PROPOSAL_ONLY_SCREENING",
        "WP3-3": "PLANNED_AFTER_WP3_2B_REVIEW",
        "WP3-4": "PLANNED",
    }
    execution["wp3_2a"] = {
        "status": "COMPLETED_ACCEPTED_CURRENT",
        "accepted_session": manifest["session"],
        "accepted_rows": manifest["rows"],
        "accepted_provider": manifest["provider"],
        "accepted_data_sha256": current_hash,
        "scheduled_acquisition": True,
        "idempotent_refresh_noop": True,
        "proposal_pr_stage": True,
        "protected_acceptance_stage": True,
        "lineage_gate_v3": True,
        "bot_pr_required_check_dispatch": True,
        "candidate_membership_mutations": 0,
        "research_object_mutations": 0,
        "simulation_trade_mutations": 0,
        "real_account_mutations": 0,
        "orders": 0,
        "trade_authority": "NONE",
        "next_gate": "WP3_2B_PROTECTED_PROPOSAL_ONLY_SCREENING",
    }
    execution["wp3_2b"] = {
        "status": "READY_FOR_PROTECTED_PROPOSAL_ONLY_SCREENING",
        "input_current_session": manifest["session"],
        "input_current_rows": manifest["rows"],
        "protected_environment": "wp3-2a-screening-approval",
        "confirmation": "RUN_PROPOSAL_ONLY_SCREENING",
        "default_research_queue_limit": 100,
        "method": "DATA_READINESS_AND_LIQUIDITY_ONLY",
        "investment_ranking": False,
        "research_objects_created": 0,
        "candidate_membership_mutations": 0,
        "simulation_trade_mutations": 0,
        "real_account_mutations": 0,
        "orders": 0,
        "trade_authority": "NONE",
    }
    execution["next_task"] = "RUN_WP3_2B_GOVERNED_SCREENING_PROPOSAL"
    execution_path.write_text(
        json.dumps(execution, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    after = {key: sha(repo / value) for key, value in INVESTMENT_OBJECTS.items()}
    changed = [key for key in before if before[key] != after[key]]
    if changed:
        raise RuntimeError(f"investment objects changed: {changed}")

    print(
        json.dumps(
            {
                "session": manifest["session"],
                "proposal_id": manifest["proposal_id"],
                "universe_classification": "ORDINARY_A_SHARES",
                "scope_exception_count": len(scope_exceptions),
                "changed_investment_objects": changed,
                "next_task": "RUN_WP3_2B_GOVERNED_SCREENING_PROPOSAL",
                "trade_authority": "NONE",
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
