from __future__ import annotations

import csv
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


PROGRAM_ID = "FMDL-5G"
RELEASE_SEQUENCE = 17


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def sha256_object(value: Any) -> str:
    return sha256_bytes(stable_json(value).encode("utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        for row in rows:
            handle.write(stable_json(row) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def parse_case_types(raw: str) -> list[str]:
    return sorted({token.strip() for token in (raw or "").split("|") if token.strip()})


def transition_payload(row: dict[str, str], target_route: str) -> dict[str, Any]:
    decision = row["research_decision"]
    cases = parse_case_types(row.get("case_types", ""))
    code = row["stock_code_5d"]
    state_meaning = (
        "RESEARCH_CASE_READY_FOR_HK_CANDIDATE_REENTRY_REVIEW_ONLY_NOT_CANDIDATE_ADMISSION"
        if decision == "GRADUATED"
        else "HK_SHADOW_TRACK_MONITORING_ONLY_NOT_CANDIDATE_ADMISSION"
    )
    payload: dict[str, Any] = {
        "transition_id": f"FMDL5G-{code}-{sha256_object([row['research_id'], target_route])[:12]}",
        "security_id": row["security_id"],
        "stock_code_5d": code,
        "official_security_name_en": row["official_security_name_en"],
        "research_id": row["research_id"],
        "research_object_sha256": row["object_sha256"],
        "source_research_decision": decision,
        "target_route": target_route,
        "case_types": cases,
        "cross_market_duplication_review_required": "A_H" in cases,
        "state_meaning": state_meaning,
        "candidate_pool_mutation_authorized": False,
        "simulation_mutation_authorized": False,
        "real_account_mutation_authorized": False,
        "order_generation_authorized": False,
        "trade_authority": "NONE",
    }
    payload["transition_sha256"] = sha256_object(payload)
    return payload


def validate_entry(repo_root: Path, contract: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    entry = contract["entry_gate"]
    pointer = load_json(repo_root / entry["pointer_path"])
    decision = load_json(repo_root / entry["decision_path"])
    base = load_json(repo_root / contract["canonical_base"]["publication_path"])

    errors: list[str] = []
    if pointer.get("status") != entry["required_status"]:
        errors.append("FMDL5F_LAST_SUCCESS_STATUS_MISMATCH")
    if pointer.get("next_gate") != entry["required_next_gate"]:
        errors.append("FMDL5F_NEXT_GATE_MISMATCH")
    if decision.get("status") != entry["required_status"]:
        errors.append("FMDL5F_DECISION_STATUS_MISMATCH")
    base_contract = contract["canonical_base"]
    if base.get("release_id") != base_contract["required_release_id"]:
        errors.append("CANONICAL_BASE_RELEASE_ID_MISMATCH")
    if int(base.get("release_sequence", -1)) != int(base_contract["required_release_sequence"]):
        errors.append("CANONICAL_BASE_SEQUENCE_MISMATCH")
    if base.get("status") != base_contract["required_status"]:
        errors.append("CANONICAL_BASE_STATUS_MISMATCH")
    if base.get("trade_authority") != "NONE" or pointer.get("trade_authority") != "NONE":
        errors.append("ENTRY_TRADE_AUTHORITY_ERROR")
    if errors:
        raise ValueError(";".join(errors))
    return pointer, decision, base


def build_candidate(repo_root: Path, output_dir: Path) -> dict[str, Any]:
    contract = load_json(repo_root / "config/fmdl5g_investment_os_integration.json")
    pointer, source_decision, base = validate_entry(repo_root, contract)
    inputs = contract["inputs"]

    graduation = read_csv(repo_root / inputs["graduation_registry"])
    objects = load_jsonl(repo_root / inputs["research_objects"])
    object_by_id = {str(row["research_id"]): row for row in objects}

    eligible_decisions = set(contract["transition_policy"]["eligible_research_decisions"])
    eligible_rows = [row for row in graduation if row.get("research_decision") in eligible_decisions]
    eligible_rows.sort(key=lambda row: (row["research_decision"], row["stock_code_5d"]))

    route_map = contract["transition_policy"]["decision_to_route"]
    transitions = [transition_payload(row, route_map[row["research_decision"]]) for row in eligible_rows]

    missing_bindings = [t["research_id"] for t in transitions if t["research_id"] not in object_by_id]
    object_hash_mismatches = [
        t["research_id"]
        for t in transitions
        if t["research_id"] in object_by_id
        and object_by_id[t["research_id"]].get("object_sha256") != t["research_object_sha256"]
    ]

    reentry = [t for t in transitions if t["target_route"] == "HK_CANDIDATE_REENTRY_REVIEW"]
    shadow = [t for t in transitions if t["target_route"] == "HK_SHADOW_TRACK_REVIEW"]
    duplicate_review = [t for t in transitions if t["cross_market_duplication_review_required"]]

    output_dir = output_dir.resolve()
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    transition_path = output_dir / "FMDL5G_STATE_TRANSITIONS.jsonl"
    write_jsonl(transition_path, transitions)

    queue_fields = [
        "transition_id", "security_id", "stock_code_5d", "official_security_name_en",
        "research_id", "source_research_decision", "target_route", "case_types",
        "cross_market_duplication_review_required", "state_meaning", "trade_authority"
    ]
    def queue_rows(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [{**item, "case_types": "|".join(item["case_types"])} for item in items]

    write_csv(output_dir / "FMDL5G_HK_CANDIDATE_REENTRY_REVIEW_QUEUE.csv", queue_rows(reentry), queue_fields)
    write_csv(output_dir / "FMDL5G_HK_SHADOW_TRACK_QUEUE.csv", queue_rows(shadow), queue_fields)

    duplication_rows = [
        {
            "transition_id": item["transition_id"],
            "security_id": item["security_id"],
            "stock_code_5d": item["stock_code_5d"],
            "official_security_name_en": item["official_security_name_en"],
            "research_id": item["research_id"],
            "case_type": "A_H",
            "review_state": "CROSS_MARKET_DUPLICATION_REVIEW_REQUIRED",
            "admission_state": "NO_AUTOMATIC_MARKET_SELECTION_OR_DUPLICATE_EXPOSURE",
            "trade_authority": "NONE",
        }
        for item in duplicate_review
    ]
    write_csv(
        output_dir / "FMDL5G_CROSS_MARKET_DUPLICATION_REVIEW.csv",
        duplication_rows,
        ["transition_id", "security_id", "stock_code_5d", "official_security_name_en", "research_id", "case_type", "review_state", "admission_state", "trade_authority"],
    )

    state_router_rows = [
        {
            "transition_id": item["transition_id"],
            "security_id": item["security_id"],
            "research_id": item["research_id"],
            "target_route": item["target_route"],
            "overlay_state": "ADDED_TO_READ_ONLY_FMDL5G_OVERLAY",
            "existing_candidate_pool_mutation": 0,
            "simulation_mutation": 0,
            "real_account_mutation": 0,
            "order_generation": 0,
            "trade_authority": "NONE",
        }
        for item in transitions
    ]
    router_fields = ["transition_id", "security_id", "research_id", "target_route", "overlay_state", "existing_candidate_pool_mutation", "simulation_mutation", "real_account_mutation", "order_generation", "trade_authority"]
    write_csv(output_dir / "FMDL5G_STATE_ROUTER.csv", state_router_rows, router_fields)

    downstream_fields = ["transition_id", "security_id", "research_id", "source_route", "router_decision", "reason_code", "mutation_count", "trade_authority"]
    simulation_rows = [
        {
            "transition_id": item["transition_id"], "security_id": item["security_id"], "research_id": item["research_id"],
            "source_route": item["target_route"], "router_decision": "NOT_ADMITTED",
            "reason_code": "SEPARATE_SIMULATION_GATE_REQUIRED", "mutation_count": 0, "trade_authority": "NONE"
        }
        for item in transitions
    ]
    real_rows = [
        {
            "transition_id": item["transition_id"], "security_id": item["security_id"], "research_id": item["research_id"],
            "source_route": item["target_route"], "router_decision": "NOT_ADMITTED",
            "reason_code": "USER_CONFIRMED_REAL_ACCOUNT_GATE_REQUIRED", "mutation_count": 0, "trade_authority": "NONE"
        }
        for item in transitions
    ]
    write_csv(output_dir / "FMDL5G_SIMULATION_ROUTER.csv", simulation_rows, downstream_fields)
    write_csv(output_dir / "FMDL5G_REAL_ACCOUNT_ROUTER.csv", real_rows, downstream_fields)

    state_diff = {
        "program_id": PROGRAM_ID,
        "canonical_base_release_id": base["release_id"],
        "canonical_base_package_sha256": base["package_sha256"],
        "integration_mode": contract["canonical_base"]["integration_mode"],
        "overlay_additions": {
            "state_transition_count": len(transitions),
            "candidate_reentry_review_count": len(reentry),
            "shadow_track_review_count": len(shadow),
            "cross_market_duplication_review_count": len(duplicate_review),
        },
        "canonical_base_repack_count": 0,
        "existing_candidate_pool_mutation_count": 0,
        "simulation_mutation_count": 0,
        "real_account_mutation_count": 0,
        "order_generation_count": 0,
        "trade_authority": "NONE",
    }
    write_json(output_dir / "FMDL5G_STATE_DIFF.json", state_diff)

    rollback = {
        "program_id": PROGRAM_ID,
        "base_release_id_before": base["release_id"],
        "base_release_id_after_candidate": base["release_id"],
        "base_package_sha256_before": base["package_sha256"],
        "base_package_sha256_after_candidate": base["package_sha256"],
        "failed_candidate_can_replace_current": False,
        "overlay_can_mutate_release8": False,
        "rollback_target": "PRESERVE_INVESTMENT_OS_RELEASE8_AND_PRIOR_FMDL5G_LAST_KNOWN_GOOD",
        "proof_state": "PASS",
        "trade_authority": "NONE",
    }
    write_json(output_dir / "FMDL5G_ROLLBACK_PROOF.json", rollback)

    duplicate_security_count = len(transitions) - len({item["security_id"] for item in transitions})
    metrics = {
        "source_registry_count": len(graduation),
        "source_formal_research_object_count": len(objects),
        "state_transition_count": len(transitions),
        "candidate_reentry_review_count": len(reentry),
        "shadow_track_review_count": len(shadow),
        "cross_market_duplication_review_count": len(duplicate_review),
        "duplicate_transition_security_count": duplicate_security_count,
        "missing_research_binding_count": len(missing_bindings),
        "research_object_hash_mismatch_count": len(object_hash_mismatches),
        "existing_candidate_pool_mutation_count": 0,
        "simulation_mutation_count": 0,
        "real_account_mutation_count": 0,
        "order_generation_count": 0,
        "trade_authority_error_count": 0,
    }

    policy = contract["transition_policy"]
    acceptance = contract["acceptance"]
    hard_failures: list[str] = []
    exact_checks = {
        "STATE_TRANSITION_COUNT": (metrics["state_transition_count"], policy["required_transition_count"]),
        "REENTRY_REVIEW_COUNT": (metrics["candidate_reentry_review_count"], policy["required_reentry_review_count"]),
        "SHADOW_TRACK_COUNT": (metrics["shadow_track_review_count"], policy["required_shadow_track_count"]),
    }
    for name, (actual, expected) in exact_checks.items():
        if actual != expected:
            hard_failures.append(f"{name}_EXPECTED_{expected}_ACTUAL_{actual}")
    if metrics["cross_market_duplication_review_count"] < acceptance["minimum_cross_market_duplication_review_count"]:
        hard_failures.append("INSUFFICIENT_CROSS_MARKET_DUPLICATION_REVIEWS")
    for metric in [
        "duplicate_transition_security_count", "missing_research_binding_count", "research_object_hash_mismatch_count",
        "existing_candidate_pool_mutation_count", "simulation_mutation_count", "real_account_mutation_count",
        "order_generation_count", "trade_authority_error_count"
    ]:
        if metrics[metric] != 0:
            hard_failures.append(metric.upper())

    stable_files = [
        "FMDL5G_STATE_TRANSITIONS.jsonl",
        "FMDL5G_HK_CANDIDATE_REENTRY_REVIEW_QUEUE.csv",
        "FMDL5G_HK_SHADOW_TRACK_QUEUE.csv",
        "FMDL5G_CROSS_MARKET_DUPLICATION_REVIEW.csv",
        "FMDL5G_STATE_ROUTER.csv",
        "FMDL5G_SIMULATION_ROUTER.csv",
        "FMDL5G_REAL_ACCOUNT_ROUTER.csv",
        "FMDL5G_STATE_DIFF.json",
        "FMDL5G_ROLLBACK_PROOF.json",
    ]
    stable_file_hashes = {name: sha256_file(output_dir / name) for name in stable_files}
    canonical_sha = sha256_object({
        "program_id": PROGRAM_ID,
        "source_release_id": pointer["release_id"],
        "canonical_base_release_id": base["release_id"],
        "files": stable_file_hashes,
    })
    release_id = f"FMDL5G_{pointer['as_of_date'].replace('-', '')}_{canonical_sha[:12]}"
    generated_at = datetime.now(timezone.utc).isoformat()
    status = contract["exit_status"] if not hard_failures else "FMDL5G_CANDIDATE_REJECTED"

    quality = {
        "program_id": PROGRAM_ID,
        "release_id": release_id,
        "generated_at_utc": generated_at,
        "metrics": metrics,
        "hard_failures": hard_failures,
        "controlled_warnings": [],
        "validation_state": "PASS" if not hard_failures else "FAIL",
        "trade_authority": "NONE",
    }
    write_json(output_dir / "FMDL5G_QUALITY_REPORT.json", quality)

    decision = {
        "program_id": PROGRAM_ID,
        "release_id": release_id,
        "release_sequence": RELEASE_SEQUENCE,
        "status": status,
        "as_of_date": pointer["as_of_date"],
        "generated_at_utc": generated_at,
        "authority": contract["authority"],
        "source_release_ids": {
            "fmdl5f": pointer["release_id"],
            "canonical_base": base["release_id"],
        },
        "metrics": metrics,
        "canonical_sha256": canonical_sha,
        "next_gate": contract["next_gate"],
        "hard_failures": hard_failures,
        "candidate_pool_mutation_count": 0,
        "simulation_mutation_count": 0,
        "real_account_mutation_count": 0,
        "order_generation_count": 0,
        "trade_authority": "NONE",
    }
    write_json(output_dir / "FMDL5G_DECISION.json", decision)

    manifest_files: dict[str, Any] = {}
    for path in sorted(output_dir.iterdir()):
        if path.name == "FMDL5G_MANIFEST.json" or not path.is_file():
            continue
        manifest_files[path.name] = {"sha256": sha256_file(path), "size_bytes": path.stat().st_size}
    manifest = {
        "program_id": PROGRAM_ID,
        "release_id": release_id,
        "release_sequence": RELEASE_SEQUENCE,
        "as_of_date": pointer["as_of_date"],
        "canonical_sha256": canonical_sha,
        "source_release_ids": decision["source_release_ids"],
        "files": manifest_files,
    }
    write_json(output_dir / "FMDL5G_MANIFEST.json", manifest)

    if hard_failures:
        raise RuntimeError("FMDL-5G candidate failed: " + ";".join(hard_failures))
    return decision
