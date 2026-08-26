"""Phase 3A point-in-time evidence ledger; shadow/research-only."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import re

SHA40 = re.compile(r"^[0-9a-f]{40}$")
ALLOWED_AUTHORITY_DOMAINS = {"CANONICAL_MAIN", "GOVERNED_NON_CANONICAL"}
ALLOWED_AVAILABILITY_BASES = {
    "CANONICAL_MAIN_COMMIT",
    "CANONICAL_MERGE_REACHABILITY",
    "VERIFIED_CONSERVATIVE_TIME",
    "GOVERNED_NON_CANONICAL_COMMIT",
}
FALSE_CONTROLS = {
    "hindsight_allowed": False,
    "retrospective_probability_backfill_allowed": False,
    "retrospective_scenario_backfill_allowed": False,
    "candidate_mutation_allowed": False,
    "real_position_mutation_allowed": False,
    "simulation_position_mutation_allowed": False,
    "target_portfolio_writeback_allowed": False,
    "user_decision_generation_allowed": False,
    "investment_recommendation_generation_allowed": False,
    "order_authorized": False,
    "orders": 0,
    "trade_authority": "NONE",
}


def _parse_timestamp(value: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError("TIMESTAMP_REQUIRED")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("INVALID_TIMESTAMP") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("OFFSET_AWARE_TIMESTAMP_REQUIRED")
    return parsed.astimezone(timezone.utc)


def _validate_source(source: dict, authority_domain: str) -> None:
    if not isinstance(source, dict):
        raise ValueError("SOURCE_REQUIRED")
    for key in ("repository", "path", "commit_sha", "provenance_status"):
        if not source.get(key):
            raise ValueError("SOURCE_FIELD_REQUIRED_" + key)
    if not SHA40.fullmatch(source["commit_sha"]):
        raise ValueError("INVALID_SOURCE_COMMIT_SHA")
    if authority_domain == "CANONICAL_MAIN":
        if source["provenance_status"] != "CANONICAL_MAIN":
            raise ValueError("CANONICAL_SOURCE_STATUS_REQUIRED")
    reachability_sha = source.get("canonical_reachability_sha")
    if reachability_sha is not None and not SHA40.fullmatch(reachability_sha):
        raise ValueError("INVALID_CANONICAL_REACHABILITY_SHA")


def validate_evidence_record(record: dict) -> None:
    for key in (
        "evidence_id",
        "evidence_key",
        "evidence_class",
        "security_ids",
        "evidence_as_of",
        "available_at",
        "availability_basis",
        "authority_domain",
        "source",
    ):
        if key not in record:
            raise ValueError("EVIDENCE_FIELD_REQUIRED_" + key)
    if not record["evidence_id"] or not record["evidence_key"] or not record["evidence_class"]:
        raise ValueError("EVIDENCE_IDENTITY_REQUIRED")
    if not isinstance(record["security_ids"], list):
        raise ValueError("SECURITY_IDS_MUST_BE_LIST")
    if len(record["security_ids"]) != len(set(record["security_ids"])):
        raise ValueError("DUPLICATE_SECURITY_ID")
    _parse_timestamp(record["available_at"])
    if record["availability_basis"] not in ALLOWED_AVAILABILITY_BASES:
        raise ValueError("INVALID_AVAILABILITY_BASIS")
    if record["authority_domain"] not in ALLOWED_AUTHORITY_DOMAINS:
        raise ValueError("INVALID_AUTHORITY_DOMAIN")
    _validate_source(record["source"], record["authority_domain"])


def validate_decision_point(point: dict) -> None:
    for key in (
        "decision_point_id",
        "at",
        "opportunity_security_ids",
        "required_evidence_keys",
    ):
        if key not in point:
            raise ValueError("DECISION_POINT_FIELD_REQUIRED_" + key)
    if not point["decision_point_id"]:
        raise ValueError("DECISION_POINT_ID_REQUIRED")
    _parse_timestamp(point["at"])
    if not isinstance(point["opportunity_security_ids"], list):
        raise ValueError("OPPORTUNITY_SECURITY_IDS_MUST_BE_LIST")
    if not isinstance(point["required_evidence_keys"], list):
        raise ValueError("REQUIRED_EVIDENCE_KEYS_MUST_BE_LIST")
    if len(point["required_evidence_keys"]) != len(set(point["required_evidence_keys"])):
        raise ValueError("DUPLICATE_REQUIRED_EVIDENCE_KEY")


def _scope_matches(record: dict, opportunity_security_ids: set[str]) -> bool:
    record_scope = set(record["security_ids"])
    return not record_scope or bool(record_scope & opportunity_security_ids)


def build_point_in_time_ledger(
    evidence_records,
    decision_points,
    *,
    allowed_authority_domains=("CANONICAL_MAIN",),
):
    """Build deterministic snapshots using only evidence available by each timestamp.

    The latest available version of each evidence_key is selected. Later versions
    are reported as future evidence but never leak into the selected snapshot.
    """
    records = [deepcopy(dict(x)) for x in evidence_records]
    points = [deepcopy(dict(x)) for x in decision_points]
    allowed_domains = tuple(allowed_authority_domains)

    if not allowed_domains or not set(allowed_domains) <= ALLOWED_AUTHORITY_DOMAINS:
        raise ValueError("INVALID_ALLOWED_AUTHORITY_DOMAINS")

    record_ids = set()
    for record in records:
        validate_evidence_record(record)
        if record["evidence_id"] in record_ids:
            raise ValueError("DUPLICATE_EVIDENCE_ID")
        record_ids.add(record["evidence_id"])

    point_ids = set()
    for point in points:
        validate_decision_point(point)
        if point["decision_point_id"] in point_ids:
            raise ValueError("DUPLICATE_DECISION_POINT_ID")
        point_ids.add(point["decision_point_id"])

    snapshots = []
    for point in sorted(points, key=lambda x: (_parse_timestamp(x["at"]), x["decision_point_id"])):
        point_time = _parse_timestamp(point["at"])
        opportunity_scope = set(point["opportunity_security_ids"])
        scoped = [
            r
            for r in records
            if r["authority_domain"] in allowed_domains
            and _scope_matches(r, opportunity_scope)
        ]

        eligible = [r for r in scoped if _parse_timestamp(r["available_at"]) <= point_time]
        future = [r for r in scoped if _parse_timestamp(r["available_at"]) > point_time]

        latest_by_key = {}
        superseded_ids = []
        for record in sorted(
            eligible,
            key=lambda r: (_parse_timestamp(r["available_at"]), r["evidence_id"]),
        ):
            prior = latest_by_key.get(record["evidence_key"])
            if prior is not None:
                superseded_ids.append(prior["evidence_id"])
            latest_by_key[record["evidence_key"]] = record

        selected = sorted(latest_by_key.values(), key=lambda r: (r["evidence_key"], r["evidence_id"]))
        selected_keys = {r["evidence_key"] for r in selected}
        missing = sorted(set(point["required_evidence_keys"]) - selected_keys)

        snapshot = {
            "decision_point_id": point["decision_point_id"],
            "at": point["at"],
            "checkpoint_type": point.get("checkpoint_type", "HISTORICAL_REPLAY_CHECKPOINT"),
            "opportunity_security_ids": sorted(opportunity_scope),
            "allowed_authority_domains": list(allowed_domains),
            "selected_evidence_ids": [r["evidence_id"] for r in selected],
            "selected_evidence": selected,
            "superseded_evidence_ids": sorted(set(superseded_ids)),
            "future_evidence_ids": sorted(r["evidence_id"] for r in future),
            "required_evidence_keys": sorted(point["required_evidence_keys"]),
            "unavailable_required_evidence_keys": missing,
            "snapshot_complete_for_declared_requirements": not missing,
        }
        for record in selected:
            if _parse_timestamp(record["available_at"]) > point_time:
                raise AssertionError("HINDSIGHT_CONTAMINATION")
        snapshots.append(snapshot)

    return {
        "schema_version": "1.0.0",
        "phase": "3A",
        "mode": "POINT_IN_TIME_EVIDENCE_LEDGER",
        "authority_domains_included": list(allowed_domains),
        "selection_rule": "LATEST_AVAILABLE_VERSION_PER_EVIDENCE_KEY_AT_OR_BEFORE_CHECKPOINT",
        "missing_data_policy": "EXPLICIT_UNAVAILABLE_NO_BACKFILL",
        "evidence_record_count": len(records),
        "decision_point_count": len(points),
        "snapshots": snapshots,
        "model_output_generated": False,
        "investment_recommendation_generated": False,
        "user_decision_generated": False,
        "controls": deepcopy(FALSE_CONTROLS),
    }
