#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

TRADE_AUTHORITY = "NONE"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def as_bool(value: Any) -> bool:
    return value is True or str(value).strip().lower() in {"1", "true", "yes", "y"}


def validate(root: Path, output: Path, committed_current: Path | None) -> None:
    contract = read_json(root / "config/hkcu_p3_2_candidate_pool_promotion_contract.json")
    cfg = contract["current_publication"]
    acc = contract["acceptance"]
    mapping = contract["promotion_mapping"]
    failures: list[str] = []

    candidate_path = output / cfg["candidate_current"]
    monitor_path = output / cfg["nonmember_monitors"]
    ledger_path = output / cfg["promotion_ledger"]
    decision_path = output / cfg["decision"]
    quality_path = output / cfg["quality"]
    manifest_path = output / cfg["manifest"]
    required = [candidate_path, monitor_path, ledger_path, decision_path, quality_path, manifest_path]
    for p in required:
        if not p.exists(): failures.append(f"MISSING_OUTPUT:{p.name}")
    if failures:
        raise SystemExit("P3_2_VALIDATION_FAILED:" + "|".join(failures))

    candidate = pd.read_csv(candidate_path, dtype={"stock_code_5d": str}, keep_default_na=False)
    monitor = pd.read_csv(monitor_path, dtype={"stock_code_5d": str}, keep_default_na=False)
    ledger = pd.read_csv(ledger_path, dtype={"stock_code_5d": str}, keep_default_na=False)
    decision = read_json(decision_path)
    quality = read_json(quality_path)
    manifest = read_json(manifest_path)

    if len(candidate) != int(acc["formal_candidate_count"]): failures.append(f"CANDIDATE_COUNT:{len(candidate)}")
    if candidate["security_id"].duplicated().any(): failures.append("DUPLICATE_CANDIDATE")
    if int(candidate["candidate_tier"].eq("CORE").sum()) != int(acc["core_candidate_count"]): failures.append("CORE_COUNT")
    if int(candidate["candidate_tier"].eq("WATCH").sum()) != int(acc["watch_candidate_count"]): failures.append("WATCH_COUNT")
    if set(candidate["candidate_tier"]) - {"CORE", "WATCH"}: failures.append("CANDIDATE_TIER_VOCABULARY")
    if not candidate["candidate_status"].eq("ACTIVE").all(): failures.append("CANDIDATE_STATUS")
    if not candidate["formal_candidate_graduation"].map(as_bool).all(): failures.append("CANDIDATE_GRADUATION_FLAG")
    if not candidate["trade_authority"].eq(TRADE_AUTHORITY).all(): failures.append("CANDIDATE_TRADE_AUTHORITY")
    if candidate[["portfolio_allocation_authorized", "simulation_admission_authorized", "real_account_admission_authorized"]].map(as_bool).any().any(): failures.append("DOWNSTREAM_AUTHORITY_LEAK")
    if candidate["orders_created"].astype(int).ne(0).any(): failures.append("CANDIDATE_ORDERS")

    if len(monitor) != int(acc["research_monitor_count"]) + int(acc["blocker_monitor_count"]): failures.append("MONITOR_COUNT")
    if int(monitor["monitor_state"].eq("RESEARCH_MONITOR").sum()) != int(acc["research_monitor_count"]): failures.append("RESEARCH_MONITOR_COUNT")
    if int(monitor["monitor_state"].eq("BLOCKER_MONITOR").sum()) != int(acc["blocker_monitor_count"]): failures.append("BLOCKER_MONITOR_COUNT")
    if monitor["candidate_member"].map(as_bool).any(): failures.append("MONITOR_CANDIDATE_MEMBER")
    if monitor["formal_candidate_graduation"].map(as_bool).any(): failures.append("MONITOR_GRADUATION")
    if set(candidate["security_id"]) & set(monitor["security_id"]): failures.append("MEMBERSHIP_OVERLAP")

    if len(ledger) != int(acc["promotion_ledger_count"]): failures.append("LEDGER_COUNT")
    if ledger["security_id"].duplicated().any(): failures.append("LEDGER_DUPLICATE")
    if not ledger["from_state"].eq("NOT_HK_CANDIDATE").all(): failures.append("LEDGER_FROM_STATE")
    if ledger["a_share_candidate_mutation"].map(as_bool).any(): failures.append("A_SHARE_CANDIDATE_MUTATION")
    if ledger["simulation_mutation"].map(as_bool).any(): failures.append("SIMULATION_MUTATION")
    if ledger["real_account_mutation"].map(as_bool).any(): failures.append("REAL_ACCOUNT_MUTATION")
    if ledger["orders_created"].astype(int).ne(0).any(): failures.append("LEDGER_ORDERS")
    if not ledger["trade_authority"].eq(TRADE_AUTHORITY).all(): failures.append("LEDGER_TRADE_AUTHORITY")

    candidate_ids = set(candidate["security_id"])
    monitor_ids = set(monitor["security_id"])
    if candidate_ids | monitor_ids != set(ledger["security_id"]): failures.append("LEDGER_COVERAGE")
    for _, row in ledger.iterrows():
        proposal = str(row["p3_1_proposal_state"])
        if proposal not in mapping:
            failures.append(f"UNMAPPED_LEDGER_STATE:{proposal}")
            continue
        expected = mapping[proposal]
        expected_member = bool(expected["candidate_member"])
        if as_bool(row["formal_candidate_member"]) != expected_member:
            failures.append(f"LEDGER_MEMBER_ROUTING:{row['security_id']}")
        if str(row["transition_action"]) != str(expected["transition_action"]):
            failures.append(f"LEDGER_ACTION_ROUTING:{row['security_id']}")
        if expected_member:
            expected_to = f"HK_CANDIDATE_{expected['candidate_tier']}"
        else:
            expected_to = str(expected["candidate_tier"])
        if str(row["to_state"]) != expected_to:
            failures.append(f"LEDGER_TO_STATE:{row['security_id']}")

    core = candidate[candidate["candidate_tier"].eq("CORE")]
    core_ids = set(core["security_id"])
    expected_core_ids = set(
        ledger.loc[ledger["p3_1_proposal_state"].eq("PROPOSE_CORE_CANDIDATE"), "security_id"]
    )
    if core_ids != expected_core_ids: failures.append("CORE_ID_ROUTING")
    expected_watch_ids = set(
        ledger.loc[ledger["p3_1_proposal_state"].eq("PROPOSE_WATCH_CANDIDATE"), "security_id"]
    )
    watch_ids = set(candidate.loc[candidate["candidate_tier"].eq("WATCH"), "security_id"])
    if watch_ids != expected_watch_ids: failures.append("WATCH_ID_ROUTING")

    if decision.get("program_id") != contract["program_id"]: failures.append("DECISION_PROGRAM_ID")
    if decision.get("status") != acc["pass_status"]: failures.append("DECISION_STATUS")
    if int(decision.get("formal_candidate_count", -1)) != len(candidate): failures.append("DECISION_CANDIDATE_COUNT")
    if decision.get("candidate_tier_counts") != candidate["candidate_tier"].value_counts().astype(int).to_dict(): failures.append("DECISION_TIER_TIEOUT")
    if int(decision.get("nonmember_monitor_count", -1)) != len(monitor): failures.append("DECISION_MONITOR_COUNT")
    if decision.get("nonmember_monitor_counts") != monitor["monitor_state"].value_counts().astype(int).to_dict(): failures.append("DECISION_MONITOR_TIEOUT")
    if int(decision.get("a_share_candidate_mutations", -1)) != 0: failures.append("DECISION_A_SHARE_MUTATION")
    if int(decision.get("simulation_mutations", -1)) != 0 or int(decision.get("real_account_mutations", -1)) != 0: failures.append("DECISION_PORTFOLIO_MUTATION")
    if int(decision.get("portfolio_allocations", -1)) != 0 or int(decision.get("orders_created", -1)) != 0: failures.append("DECISION_DOWNSTREAM_ACTION")
    if decision.get("next_gate") != acc["next_gate"]: failures.append("NEXT_GATE")
    if decision.get("trade_authority") != TRADE_AUTHORITY: failures.append("DECISION_TRADE_AUTHORITY")

    if quality.get("status") != "PASS" or quality.get("hard_failures"):
        failures.append("QUALITY_NOT_PASS")
    if quality.get("accepted_p3_1_hashes_reproduced") is not True: failures.append("P3_1_HASH_PROOF")
    if quality.get("deterministic_mapping_only") is not True: failures.append("DETERMINISTIC_MAPPING_PROOF")
    if quality.get("core_watch_relabelled") is not False: failures.append("CORE_WATCH_RELABEL")
    if quality.get("defer_or_blocker_promoted") is not False: failures.append("DEFER_BLOCKER_PROMOTED")

    if manifest.get("program_id") != contract["program_id"]: failures.append("MANIFEST_PROGRAM_ID")
    if manifest.get("trade_authority") != TRADE_AUTHORITY: failures.append("MANIFEST_TRADE_AUTHORITY")
    expected_files = {p.name for p in (candidate_path, monitor_path, ledger_path, decision_path, quality_path)}
    if set(manifest.get("files", {})) != expected_files: failures.append("MANIFEST_FILE_SET")
    for p in (candidate_path, monitor_path, ledger_path, decision_path, quality_path):
        item = manifest.get("files", {}).get(p.name, {})
        if item.get("sha256") != sha256_file(p): failures.append(f"MANIFEST_HASH:{p.name}")
        if int(item.get("bytes", -1)) != p.stat().st_size: failures.append(f"MANIFEST_BYTES:{p.name}")

    upstream_dir = output / "_p3_1_rebuild"
    if upstream_dir.exists():
        upstream = contract["authoritative_inputs"]
        checks = {
            "HKCU_P3_1_SECURITY_ASSESSMENT.csv": upstream["accepted_p3_1_security_assessment_sha256"],
            "HKCU_P3_1_RULE_ASSESSMENT.csv": upstream["accepted_p3_1_rule_assessment_sha256"],
            "HKCU_P3_1_DECISION.json": upstream["accepted_p3_1_decision_sha256"],
        }
        for name, expected in checks.items():
            p = upstream_dir / name
            if not p.exists() or sha256_file(p) != expected:
                failures.append(f"UPSTREAM_ACCEPTED_HASH:{name}")

    if committed_current is not None:
        for generated in (candidate_path, monitor_path, ledger_path, decision_path, quality_path, manifest_path):
            committed = committed_current / generated.name
            if not committed.exists():
                failures.append(f"COMMITTED_CURRENT_MISSING:{generated.name}")
            elif generated.read_bytes() != committed.read_bytes():
                failures.append(f"COMMITTED_CURRENT_MISMATCH:{generated.name}")

    if failures:
        raise SystemExit("P3_2_VALIDATION_FAILED:" + "|".join(sorted(set(failures))))
    print("PASS_P3_2_CANDIDATE_POOL_PROMOTION_VALIDATION")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--repo-root", default=".")
    p.add_argument("--output", required=True)
    p.add_argument("--committed-current", default=None)
    args = p.parse_args()
    validate(
        Path(args.repo_root).resolve(),
        Path(args.output).resolve(),
        Path(args.committed_current).resolve() if args.committed_current else None,
    )


if __name__ == "__main__":
    main()
