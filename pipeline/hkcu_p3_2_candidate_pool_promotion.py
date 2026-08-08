#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pandas as pd

PROGRAM_ID = "HKCU-P3-2"
TRADE_AUTHORITY = "NONE"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def as_bool(value: Any) -> bool:
    return value is True or str(value).strip().lower() in {"1", "true", "yes", "y"}


def rebuild_p3_1(root: Path, out: Path, contract: dict[str, Any]) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    upstream = contract["authoritative_inputs"]
    subprocess.run(
        [
            sys.executable,
            str(root / upstream["p3_1_builder"]),
            "--repo-root",
            str(root),
            "--output",
            str(out),
        ],
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            str(root / upstream["p3_1_validator"]),
            "--repo-root",
            str(root),
            "--output",
            str(out),
        ],
        check=True,
    )
    return out


def verify_accepted_p3_1(p3_1_dir: Path, contract: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, Any]]:
    failures: list[str] = []
    upstream = contract["authoritative_inputs"]
    security_path = p3_1_dir / "HKCU_P3_1_SECURITY_ASSESSMENT.csv"
    rules_path = p3_1_dir / "HKCU_P3_1_RULE_ASSESSMENT.csv"
    decision_path = p3_1_dir / "HKCU_P3_1_DECISION.json"
    for p in (security_path, rules_path, decision_path):
        if not p.exists():
            failures.append(f"MISSING_P3_1_FILE:{p.name}")
    if failures:
        raise SystemExit("P3_2_UPSTREAM_FAILED:" + "|".join(failures))

    expected_hashes = {
        security_path: upstream["accepted_p3_1_security_assessment_sha256"],
        rules_path: upstream["accepted_p3_1_rule_assessment_sha256"],
        decision_path: upstream["accepted_p3_1_decision_sha256"],
    }
    for p, expected in expected_hashes.items():
        observed = sha256_file(p)
        if observed != expected:
            failures.append(f"P3_1_HASH_MISMATCH:{p.name}:{observed}:{expected}")

    decision = read_json(decision_path)
    entry = contract["entry_contract"]
    if decision.get("program_id") != entry["required_p3_1_program_id"]:
        failures.append("P3_1_PROGRAM_ID")
    if decision.get("status") != entry["required_p3_1_pass_status"]:
        failures.append("P3_1_STATUS")
    if decision.get("next_gate") != entry["required_p3_1_next_gate"]:
        failures.append("P3_1_NEXT_GATE")
    if int(decision.get("security_assessment_count", -1)) != int(entry["entry_security_count"]):
        failures.append("P3_1_SECURITY_COUNT")
    if decision.get("proposal_state_counts") != entry["proposal_state_counts"]:
        failures.append("P3_1_PROPOSAL_COUNTS")
    if decision.get("trade_authority") != TRADE_AUTHORITY:
        failures.append("P3_1_TRADE_AUTHORITY")

    assessment = pd.read_csv(security_path, dtype={"stock_code_5d": str}, keep_default_na=False)
    assessment["stock_code_5d"] = assessment["stock_code_5d"].astype(str).str.zfill(5)
    if len(assessment) != int(entry["entry_security_count"]):
        failures.append(f"P3_1_ASSESSMENT_COUNT:{len(assessment)}")
    if assessment["security_id"].duplicated().any():
        failures.append("P3_1_DUPLICATE_SECURITY")
    if assessment["formal_candidate_graduation"].map(as_bool).any():
        failures.append("P3_1_PREMATURE_FORMAL_GRADUATION")
    if assessment["candidate_pool_mutation"].map(as_bool).any():
        failures.append("P3_1_PREMATURE_CANDIDATE_MUTATION")
    if any(str(x).strip() for x in assessment["alpha_score"]):
        failures.append("P3_1_ALPHA_SCORE_PRESENT")

    if failures:
        raise SystemExit("P3_2_UPSTREAM_FAILED:" + "|".join(sorted(set(failures))))
    return assessment.sort_values("p2a_overall_rank").reset_index(drop=True), decision


def candidate_row(row: pd.Series, tier: str, as_of_date: str) -> dict[str, Any]:
    return {
        "p2a_overall_rank": int(row["p2a_overall_rank"]),
        "security_id": str(row["security_id"]),
        "stock_code_5d": str(row["stock_code_5d"]).zfill(5),
        "security_name": str(row["security_name"]),
        "candidate_tier": tier,
        "candidate_status": "ACTIVE",
        "as_of_date": as_of_date,
        "primary_sleeve": str(row["primary_sleeve"]),
        "valuation_support_state": str(row["valuation_support_state"]),
        "thesis_strength": str(row["thesis_strength"]),
        "investment_thesis": str(row["investment_thesis"]),
        "principal_falsifier": str(row["principal_falsifier"]),
        "monitor_triggers": str(row["monitor_triggers"]),
        "ah_pair_status": str(row["ah_pair_status"]),
        "ah_relative_value_direction": str(row["ah_relative_value_direction"]),
        "h_discount_to_a_pct": row["h_discount_to_a_pct"],
        "material_confidence_cap_count": int(row["material_confidence_cap_count"]),
        "bounded_confidence_cap_count": int(row["bounded_confidence_cap_count"]),
        "p3_1_proposal_state": str(row["proposal_state"]),
        "formal_candidate_graduation": True,
        "portfolio_allocation_authorized": False,
        "simulation_admission_authorized": False,
        "real_account_admission_authorized": False,
        "orders_created": 0,
        "trade_authority": TRADE_AUTHORITY,
    }


def monitor_row(row: pd.Series, monitor_state: str, as_of_date: str) -> dict[str, Any]:
    return {
        "p2a_overall_rank": int(row["p2a_overall_rank"]),
        "security_id": str(row["security_id"]),
        "stock_code_5d": str(row["stock_code_5d"]).zfill(5),
        "security_name": str(row["security_name"]),
        "monitor_state": monitor_state,
        "candidate_member": False,
        "as_of_date": as_of_date,
        "p3_1_proposal_state": str(row["proposal_state"]),
        "proposal_reason": str(row["proposal_reason"]),
        "valuation_support_state": str(row["valuation_support_state"]),
        "investment_thesis": str(row["investment_thesis"]),
        "principal_falsifier": str(row["principal_falsifier"]),
        "monitor_triggers": str(row["monitor_triggers"]),
        "formal_candidate_graduation": False,
        "portfolio_allocation_authorized": False,
        "simulation_admission_authorized": False,
        "real_account_admission_authorized": False,
        "orders_created": 0,
        "trade_authority": TRADE_AUTHORITY,
    }


def ledger_row(row: pd.Series, mapping: dict[str, Any], as_of_date: str) -> dict[str, Any]:
    member = bool(mapping["candidate_member"])
    tier = str(mapping["candidate_tier"])
    return {
        "p2a_overall_rank": int(row["p2a_overall_rank"]),
        "security_id": str(row["security_id"]),
        "stock_code_5d": str(row["stock_code_5d"]).zfill(5),
        "security_name": str(row["security_name"]),
        "transition_as_of_date": as_of_date,
        "from_state": "NOT_HK_CANDIDATE",
        "p3_1_proposal_state": str(row["proposal_state"]),
        "to_state": f"HK_CANDIDATE_{tier}" if member else tier,
        "transition_action": str(mapping["transition_action"]),
        "formal_candidate_member": member,
        "formal_candidate_graduation": member,
        "transition_reason": str(row["proposal_reason"]),
        "a_share_candidate_mutation": False,
        "simulation_mutation": False,
        "real_account_mutation": False,
        "orders_created": 0,
        "trade_authority": TRADE_AUTHORITY,
    }


def build(root: Path, out: Path, p3_1_input: Path | None = None) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    contract_path = root / "config/hkcu_p3_2_candidate_pool_promotion_contract.json"
    contract = read_json(contract_path)
    failures: list[str] = []

    p3_1_dir = p3_1_input.resolve() if p3_1_input else rebuild_p3_1(root, out / "_p3_1_rebuild", contract)
    assessment, _ = verify_accepted_p3_1(p3_1_dir, contract)
    mapping = contract["promotion_mapping"]
    expected_states = set(mapping)
    observed_states = set(assessment["proposal_state"].astype(str))
    if observed_states != expected_states:
        failures.append("P3_1_PROPOSAL_STATE_VOCABULARY")

    candidates: list[dict[str, Any]] = []
    monitors: list[dict[str, Any]] = []
    ledger: list[dict[str, Any]] = []
    as_of_date = contract["as_of_date"]

    for _, row in assessment.iterrows():
        state = str(row["proposal_state"])
        if state not in mapping:
            failures.append(f"UNMAPPED_PROPOSAL_STATE:{state}")
            continue
        m = mapping[state]
        if bool(m["candidate_member"]):
            candidates.append(candidate_row(row, str(m["candidate_tier"]), as_of_date))
        else:
            monitors.append(monitor_row(row, str(m["candidate_tier"]), as_of_date))
        ledger.append(ledger_row(row, m, as_of_date))

    candidate_df = pd.DataFrame(candidates).sort_values("p2a_overall_rank").reset_index(drop=True)
    monitor_df = pd.DataFrame(monitors).sort_values("p2a_overall_rank").reset_index(drop=True)
    ledger_df = pd.DataFrame(ledger).sort_values("p2a_overall_rank").reset_index(drop=True)

    acc = contract["acceptance"]
    if len(candidate_df) != int(acc["formal_candidate_count"]): failures.append(f"FORMAL_CANDIDATE_COUNT:{len(candidate_df)}")
    if int(candidate_df["candidate_tier"].eq("CORE").sum()) != int(acc["core_candidate_count"]): failures.append("CORE_COUNT")
    if int(candidate_df["candidate_tier"].eq("WATCH").sum()) != int(acc["watch_candidate_count"]): failures.append("WATCH_COUNT")
    if int(monitor_df["monitor_state"].eq("RESEARCH_MONITOR").sum()) != int(acc["research_monitor_count"]): failures.append("RESEARCH_MONITOR_COUNT")
    if int(monitor_df["monitor_state"].eq("BLOCKER_MONITOR").sum()) != int(acc["blocker_monitor_count"]): failures.append("BLOCKER_MONITOR_COUNT")
    if len(ledger_df) != int(acc["promotion_ledger_count"]): failures.append("LEDGER_COUNT")
    if candidate_df["security_id"].duplicated().any() or monitor_df["security_id"].duplicated().any(): failures.append("DUPLICATE_SECURITY")
    if set(candidate_df["security_id"]) & set(monitor_df["security_id"]): failures.append("CANDIDATE_MONITOR_OVERLAP")
    if set(candidate_df["security_id"]) | set(monitor_df["security_id"]) != set(assessment["security_id"]): failures.append("ENTRY_COVERAGE")
    if not candidate_df["formal_candidate_graduation"].map(as_bool).all(): failures.append("FORMAL_GRADUATION_FLAG")
    if monitor_df["formal_candidate_graduation"].map(as_bool).any(): failures.append("MONITOR_FORMAL_GRADUATION")
    if not candidate_df["trade_authority"].eq(TRADE_AUTHORITY).all(): failures.append("CANDIDATE_TRADE_AUTHORITY")
    if not monitor_df["trade_authority"].eq(TRADE_AUTHORITY).all(): failures.append("MONITOR_TRADE_AUTHORITY")
    if not ledger_df["trade_authority"].eq(TRADE_AUTHORITY).all(): failures.append("LEDGER_TRADE_AUTHORITY")
    if candidate_df[["portfolio_allocation_authorized", "simulation_admission_authorized", "real_account_admission_authorized"]].map(as_bool).any().any(): failures.append("DOWNSTREAM_AUTHORITY_LEAK")
    if candidate_df["orders_created"].astype(int).ne(0).any() or monitor_df["orders_created"].astype(int).ne(0).any(): failures.append("ORDERS_CREATED")

    current_cfg = contract["current_publication"]
    candidate_path = out / current_cfg["candidate_current"]
    monitor_path = out / current_cfg["nonmember_monitors"]
    ledger_path = out / current_cfg["promotion_ledger"]
    candidate_df.to_csv(candidate_path, index=False)
    monitor_df.to_csv(monitor_path, index=False)
    ledger_df.to_csv(ledger_path, index=False)

    tier_counts = candidate_df["candidate_tier"].value_counts().astype(int).to_dict()
    monitor_counts = monitor_df["monitor_state"].value_counts().astype(int).to_dict()
    core_names = candidate_df.loc[candidate_df["candidate_tier"].eq("CORE"), ["security_id", "stock_code_5d", "security_name"]].to_dict("records")
    decision = {
        "program_id": PROGRAM_ID,
        "phase": contract["phase"],
        "status": acc["pass_status"] if not failures else "BLOCKED_P3_2_CANDIDATE_POOL_PROMOTION",
        "as_of_date": as_of_date,
        "entry_security_count": int(len(assessment)),
        "formal_candidate_count": int(len(candidate_df)),
        "candidate_tier_counts": tier_counts,
        "nonmember_monitor_count": int(len(monitor_df)),
        "nonmember_monitor_counts": monitor_counts,
        "core_candidates": core_names,
        "formal_candidate_graduations": int(len(candidate_df)),
        "hk_candidate_pool_admissions": int(len(candidate_df)),
        "a_share_candidate_mutations": 0,
        "simulation_mutations": 0,
        "real_account_mutations": 0,
        "portfolio_allocations": 0,
        "orders_created": 0,
        "next_gate": acc["next_gate"] if not failures else None,
        "trade_authority": TRADE_AUTHORITY,
    }
    quality = {
        "program_id": PROGRAM_ID,
        "status": "PASS" if not failures else "FAIL",
        "hard_failures": sorted(set(failures)),
        "accepted_p3_1_head_sha": contract["authoritative_inputs"]["accepted_p3_1_head_sha"],
        "accepted_p3_1_merge_sha": contract["authoritative_inputs"]["accepted_p3_1_merge_sha"],
        "accepted_p3_1_artifact_digest": contract["authoritative_inputs"]["accepted_p3_1_artifact_digest"],
        "accepted_p3_1_hashes_reproduced": True,
        "deterministic_mapping_only": True,
        "core_watch_relabelled": False,
        "defer_or_blocker_promoted": False,
        "all_77_entries_accounted_for": len(ledger_df) == 77,
        "formal_candidate_count": int(len(candidate_df)),
        "nonmember_monitor_count": int(len(monitor_df)),
        "a_share_candidate_mutations": 0,
        "simulation_mutations": 0,
        "real_account_mutations": 0,
        "portfolio_allocations": 0,
        "orders_created": 0,
        "trade_authority": TRADE_AUTHORITY,
    }
    decision_path = out / current_cfg["decision"]
    quality_path = out / current_cfg["quality"]
    write_json(decision_path, decision)
    write_json(quality_path, quality)

    manifest = {
        "program_id": PROGRAM_ID,
        "as_of_date": as_of_date,
        "contract_sha256": sha256_file(contract_path),
        "accepted_p3_1_artifact_digest": contract["authoritative_inputs"]["accepted_p3_1_artifact_digest"],
        "accepted_p3_1_security_assessment_sha256": contract["authoritative_inputs"]["accepted_p3_1_security_assessment_sha256"],
        "files": {},
        "trade_authority": TRADE_AUTHORITY,
    }
    for p in (candidate_path, monitor_path, ledger_path, decision_path, quality_path):
        manifest["files"][p.name] = {"sha256": sha256_file(p), "bytes": p.stat().st_size}
    manifest_path = out / current_cfg["manifest"]
    write_json(manifest_path, manifest)

    if failures:
        raise SystemExit("P3_2_BUILD_FAILED:" + "|".join(sorted(set(failures))))
    print(json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True))
    return decision


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--repo-root", default=".")
    p.add_argument("--output", required=True)
    p.add_argument("--p3-1-input", default=None)
    args = p.parse_args()
    build(
        Path(args.repo_root).resolve(),
        Path(args.output).resolve(),
        Path(args.p3_1_input).resolve() if args.p3_1_input else None,
    )


if __name__ == "__main__":
    main()
