from __future__ import annotations

import hashlib
import json
import math
import zipfile
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

VOLATILE_FIELDS = {"generated_at", "published_at", "elapsed_seconds"}


def clean(value: Any) -> Any:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            value = value.item()
        except (AttributeError, ValueError):
            pass
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return round(value, 12)
    return value


def canonical(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): canonical(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [canonical(item) for item in value]
    if isinstance(value, set):
        return sorted(canonical(item) for item in value)
    return clean(value)


def stable_hash(payload: Any) -> str:
    text = json.dumps(canonical(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(canonical(payload), ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    return records


def write_jsonl(path: Path, records: list[dict[str, Any]], *, sort_key: str = "symbol") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in sorted(records, key=lambda row: (str(row.get(sort_key, "")), str(row.get("lineage_id", "")))):
            handle.write(json.dumps(canonical(record), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")


def parse_json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    if isinstance(value, str) and value:
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []
    return []


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def semantic_frame_hash(frame: pd.DataFrame, *, sort_by: Iterable[str] = ("symbol",)) -> str:
    working = frame.copy()
    working = working.drop(columns=[column for column in VOLATILE_FIELDS if column in working.columns], errors="ignore")
    available = [column for column in sort_by if column in working.columns]
    if available:
        working = working.sort_values(available, kind="stable")
    return stable_hash(working.to_dict(orient="records"))


def deterministic_zip(source_root: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(item for item in source_root.rglob("*") if item.is_file()):
            relative = path.relative_to(source_root).as_posix()
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def snapshot_hashes(root: Path, paths: Iterable[str]) -> dict[str, str | None]:
    snapshot: dict[str, str | None] = {}
    for relative in paths:
        path = root / relative
        snapshot[relative] = sha256_file(path) if path.exists() and path.is_file() else None
    return snapshot


def build_lineage_records(
    graduated: pd.DataFrame,
    evidence_records: list[dict[str, Any]],
    research_objects: pd.DataFrame,
    transitions: list[dict[str, Any]],
    thesis_records: list[dict[str, Any]],
    queue: pd.DataFrame,
) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    evidence_by_symbol = {str(row["symbol"]): row for row in evidence_records}
    research_by_symbol = {str(row["symbol"]): row for row in research_objects.to_dict(orient="records")}
    transition_by_symbol = {str(row["symbol"]): row for row in transitions}
    thesis_by_symbol = {str(row["symbol"]): row for row in thesis_records}
    queue_by_symbol = {str(row["symbol"]): row for row in queue.to_dict(orient="records")}
    records: list[dict[str, Any]] = []

    for decision in graduated.sort_values(["overall_rank", "symbol"], kind="stable").to_dict(orient="records"):
        symbol = str(decision["symbol"])
        evidence = evidence_by_symbol.get(symbol)
        research = research_by_symbol.get(symbol)
        transition = transition_by_symbol.get(symbol)
        thesis = thesis_by_symbol.get(symbol)
        queue_row = queue_by_symbol.get(symbol)
        if not all([evidence, research, transition, thesis, queue_row]):
            errors.append(f"MISSING_LINEAGE_OBJECT:{symbol}")
            continue

        decision_evidence = str(decision.get("evidence_id") or "")
        research_evidence = parse_json_list(research.get("evidence_ids_json"))
        transition_evidence = list(transition.get("evidence_ids", []))
        thesis_evidence = list(thesis.get("evidence_ids", []))
        evidence_id = str(evidence.get("evidence_id") or "")
        research_id = str(research.get("research_id") or "")
        transition_id = str(transition.get("transition_id") or "")
        thesis_id = str(thesis.get("thesis_record_id") or "")

        row_errors: list[str] = []
        if decision_evidence != evidence_id or research_evidence != [evidence_id] or transition_evidence != [evidence_id] or thesis_evidence != [evidence_id]:
            row_errors.append("EVIDENCE_IDENTITY")
        if str(decision.get("research_id") or "") != research_id or transition.get("research_id") != research_id or thesis.get("research_id") != research_id:
            row_errors.append("RESEARCH_IDENTITY")
        if thesis.get("transition_id") != transition_id or queue_row.get("transition_id") != transition_id:
            row_errors.append("TRANSITION_IDENTITY")
        if str(decision.get("graduation_decision")) != "GRADUATED":
            row_errors.append("NOT_GRADUATED")
        if transition.get("trade_authority") != "NONE" or thesis.get("trade_authority") != "NONE":
            row_errors.append("TRADE_AUTHORITY")
        if row_errors:
            errors.extend(f"{symbol}:{item}" for item in row_errors)

        base = {
            "symbol": symbol,
            "name": str(decision.get("name") or evidence.get("name") or ""),
            "evidence_id": evidence_id,
            "evidence_as_of": str(evidence.get("as_of") or ""),
            "evidence_quality_state": str(evidence.get("quality_state") or ""),
            "research_id": research_id,
            "research_stage": str(research.get("research_stage") or ""),
            "graduation_decision": str(decision.get("graduation_decision") or ""),
            "transition_id": transition_id,
            "state_domain": str(transition.get("state_domain") or ""),
            "queue_state": str(queue_row.get("queue_state") or ""),
            "thesis_record_id": thesis_id,
            "thesis_version": str(thesis.get("thesis_version") or ""),
            "company_thesis_status": str(thesis.get("company_thesis_status") or ""),
            "security_thesis_readiness": str(thesis.get("security_thesis_readiness") or ""),
            "position_action": str(thesis.get("position_action") or ""),
            "return_attribution_status": str(thesis.get("return_attribution", {}).get("status") or ""),
            "candidate_pool_mutation_count": 0,
            "simulation_mutation_count": 0,
            "real_account_mutation_count": 0,
            "order_generation_count": 0,
            "trade_authority": "NONE",
        }
        semantic = stable_hash(base)
        base["lineage_id"] = f"FMDL4FINAL-LIN-{symbol}-{semantic[:16]}"
        base["semantic_hash"] = semantic
        records.append(base)
    return records, errors


def validate_operational_record(record: dict[str, Any], expected_as_of: str) -> list[str]:
    errors: list[str] = []
    if record.get("evidence_as_of") != expected_as_of:
        errors.append("STALE_OR_UNBOUND_EVIDENCE")
    if not str(record.get("research_id") or ""):
        errors.append("MISSING_RESEARCH_LINEAGE")
    if record.get("state_domain") != "FMDL4C_REENTRY_REVIEW_QUEUE":
        errors.append("STATE_DOMAIN_CROSSOVER")
    for key in ["candidate_pool_mutation_count", "simulation_mutation_count", "real_account_mutation_count"]:
        if int(record.get(key, 0)) != 0:
            errors.append("UNAUTHORIZED_INVESTMENT_STATE_MUTATION")
            break
    if int(record.get("order_generation_count", 0)) != 0:
        errors.append("UNAUTHORIZED_ORDER_GENERATION")
    if record.get("trade_authority") != "NONE":
        errors.append("UNAUTHORIZED_TRADE_AUTHORITY")
    return sorted(set(errors))


def run_failure_injections(base_record: dict[str, Any], expected_as_of: str) -> list[dict[str, Any]]:
    fixtures: list[tuple[str, dict[str, Any], set[str]]] = []

    stale = dict(base_record)
    stale["evidence_as_of"] = "2020-01-01"
    fixtures.append(("STALE_EVIDENCE_AS_CURRENT", stale, {"STALE_OR_UNBOUND_EVIDENCE"}))

    missing = dict(base_record)
    missing["research_id"] = ""
    fixtures.append(("MISSING_RESEARCH_LINEAGE", missing, {"MISSING_RESEARCH_LINEAGE"}))

    crossover = dict(base_record)
    crossover["state_domain"] = "REAL_ACCOUNT"
    crossover["candidate_pool_mutation_count"] = 1
    fixtures.append(("CROSS_DOMAIN_STATE_MUTATION", crossover, {"STATE_DOMAIN_CROSSOVER", "UNAUTHORIZED_INVESTMENT_STATE_MUTATION"}))

    unauthorized = dict(base_record)
    unauthorized["real_account_mutation_count"] = 1
    unauthorized["order_generation_count"] = 1
    unauthorized["trade_authority"] = "EXECUTE"
    fixtures.append(("UNAUTHORIZED_REAL_ACCOUNT_OR_ORDER_ACTION", unauthorized, {"UNAUTHORIZED_INVESTMENT_STATE_MUTATION", "UNAUTHORIZED_ORDER_GENERATION", "UNAUTHORIZED_TRADE_AUTHORITY"}))

    results: list[dict[str, Any]] = []
    for fixture_id, fixture, expected_errors in fixtures:
        observed = set(validate_operational_record(fixture, expected_as_of))
        results.append({
            "fixture_id": fixture_id,
            "status": "REJECTED_AS_REQUIRED" if expected_errors.issubset(observed) else "FAILURE_INJECTION_NOT_CAUGHT",
            "expected_error_codes": sorted(expected_errors),
            "observed_error_codes": sorted(observed),
            "current_replacement_authorized": False,
            "last_known_good_replacement_authorized": False,
            "trade_authority": "NONE",
        })
    return results


def capability_matrix(cfg: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"capability": row[0], "status": row[1], "evidence_or_boundary": row[2]}
        for row in cfg["capability_matrix"]
    ]


def file_library_maintenance_plan(cfg: dict[str, Any]) -> dict[str, Any]:
    audit = cfg["file_library_audit"]
    return {
        "plan_version": "1.0.0",
        "audit_date": audit["audit_date"],
        "verification_posture": audit["verification_posture"],
        "current_canonical_release_sequence": audit["canonical_release_sequence"],
        "observed_pointer_release_sequences": audit["observed_pointer_release_sequences"],
        "retain_now": [
            "股票投资助手_CURRENT.zip_RELEASE4_UNTIL_REPLACEMENT_ACCEPTED",
            "股票投资助手_CURRENT_POINTER.md_RELEASE4_UNTIL_REPLACEMENT_ACCEPTED",
            "GITHUB_FMDL4A_TO_FMDL4FINAL_IMMUTABLE_RELEASES"
        ],
        "delete_only_after_release8_single_package_acceptance": [
            "RELEASE2_POINTER_DUPLICATE",
            "RELEASE3_POINTER_DUPLICATE",
            "OBSOLETE_CONTINUE_OR_FRAGMENT_FILES",
            "SUPERSEDED_INTERMEDIATE_FILE_LIBRARY_PACKAGES"
        ],
        "new_canonical_targets": [
            "股票投资助手_CURRENT.zip_RELEASE8_SINGLE_PACKAGE",
            "股票投资助手_CURRENT_POINTER.md_RELEASE8"
        ],
        "project_sources_required": False,
        "automatic_deletion_performed": False,
        "safety_rule": audit["cleanup_rule"],
        "authority": "FILE_LIBRARY_MAINTENANCE_PLAN_ONLY",
        "trade_authority": "NONE"
    }
