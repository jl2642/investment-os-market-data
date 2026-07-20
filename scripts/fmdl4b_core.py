from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable

import pandas as pd


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(canonical(payload), ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def semantic_frame_hash(frame: pd.DataFrame, *, sort_by: Iterable[str]) -> str:
    working = frame.copy()
    available = [column for column in sort_by if column in working.columns]
    if available:
        working = working.sort_values(available, kind="stable")
    return stable_hash(working.to_dict(orient="records"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    return records


def write_jsonl(path: Path, records: list[dict[str, Any]], *, sort_key: str = "symbol") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in sorted(records, key=lambda item: str(item.get(sort_key, ""))):
            handle.write(json.dumps(canonical(record), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")


def evidence_context(envelope: dict[str, Any]) -> dict[str, Any]:
    return {
        "evidence_id": envelope.get("evidence_id"),
        "quality_state": envelope.get("quality_state"),
        "financial_evidence": envelope.get("financial_evidence", {}),
        "valuation_evidence": envelope.get("valuation_evidence", {}),
        "market_evidence": envelope.get("market_evidence", {}),
        "shareholder_return_evidence": envelope.get("shareholder_return_evidence", {}),
        "screening_evidence": envelope.get("screening_evidence", {}),
        "controlled_limitations": envelope.get("controlled_limitations", []),
        "source_release_ids": envelope.get("source_release_ids", {}),
    }


def research_object(
    profile: dict[str, Any],
    registry_row: dict[str, Any],
    envelope: dict[str, Any],
    *,
    research_version: str,
    authority: str,
) -> dict[str, Any]:
    base = {
        "symbol": str(profile["symbol"]),
        "name": str(profile["name"]),
        "as_of": str(envelope.get("as_of") or registry_row.get("as_of_date") or ""),
        "research_version": research_version,
        "research_stage": profile["research_stage"],
        "graduation_decision": profile["decision"],
        "business_model": profile["business_model"],
        "competitive_position": profile["competitive_position"],
        "owner_quality": profile["owner_quality"],
        "earnings_drivers": profile["earnings_drivers"],
        "valuation_scenarios": {
            "status": "NOT_FULLY_UNDERWRITTEN_IN_FMDL4B",
            "trailing_context": envelope.get("valuation_evidence", {}),
            "graduation_condition": profile["graduation_condition"],
        },
        "catalysts": profile["catalysts"],
        "risks": profile["risks"],
        "variant_perception": profile["variant_perception"],
        "why_now": profile["why_now"],
        "first_rejection": profile["first_rejection"],
        "what_would_make_investable": profile["what_would_make_investable"],
        "prove_kill_checks": profile["prove_kill_checks"],
        "decision_reason_codes": profile["decision_reason_codes"],
        "graduation_condition": profile["graduation_condition"],
        "next_workflow": profile["next_workflow"],
        "evidence_ids": [envelope["evidence_id"]],
        "evidence_context": evidence_context(envelope),
        "public_sources": profile["public_sources"],
        "source_count": len(profile["public_sources"]),
        "screen_rank": int(registry_row["overall_rank"]),
        "screen_research_priority": str(registry_row["research_priority"]),
        "research_status": "SOURCE_BACKED_BASELINE_COMPLETE",
        "candidate_pool_mutation_authorized": False,
        "simulation_mutation_authorized": False,
        "real_account_mutation_authorized": False,
        "state_mutation_authorized": False,
        "authority": authority,
        "trade_authority": "NONE",
    }
    semantic = stable_hash(base)
    base["research_id"] = f"FMDL4B-RSCH-{base['symbol']}-{semantic[:16]}"
    base["semantic_hash"] = semantic
    return base


def validate_research_object(record: dict[str, Any], cfg: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = {
        "research_id", "symbol", "name", "as_of", "research_version", "research_stage",
        "graduation_decision", "business_model", "competitive_position", "owner_quality",
        "earnings_drivers", "valuation_scenarios", "catalysts", "risks", "variant_perception",
        "why_now", "first_rejection", "what_would_make_investable", "prove_kill_checks",
        "decision_reason_codes", "graduation_condition", "next_workflow", "evidence_ids",
        "evidence_context", "public_sources", "source_count", "research_status",
        "state_mutation_authorized", "authority", "trade_authority", "semantic_hash",
    }
    missing = sorted(required - set(record))
    if missing:
        errors.append("MISSING_FIELDS:" + ",".join(missing))
    if record.get("graduation_decision") not in cfg["graduation_policy"]["allowed_decisions"]:
        errors.append("DECISION")
    expected_stage = cfg["stage_model"]["decision_to_stage"].get(record.get("graduation_decision"))
    if record.get("graduation_decision") in {"GRADUATED", "REJECTED"} and record.get("research_stage") != expected_stage:
        errors.append("DECISION_STAGE")
    for field in cfg["graduation_policy"]["required_pm_fields"] + cfg["graduation_policy"]["required_research_fields"]:
        value = record.get(field)
        if value in (None, "", [], {}):
            errors.append(f"EMPTY:{field}")
    if len(record.get("public_sources", [])) < cfg["research_cohort"]["minimum_public_source_count"]:
        errors.append("SOURCE_COUNT")
    for source in record.get("public_sources", []):
        if not all(source.get(key) for key in ["source_id", "title", "source_date", "source_type", "url"]):
            errors.append("SOURCE_SHAPE")
        if not str(source.get("source_date", "")).startswith(str(cfg["research_cohort"]["required_current_source_year"])):
            errors.append("SOURCE_FRESHNESS")
    if record.get("state_mutation_authorized") is not False:
        errors.append("STATE_MUTATION")
    if record.get("trade_authority") != "NONE":
        errors.append("TRADE_AUTHORITY")
    semantic_payload = {key: value for key, value in record.items() if key not in {"research_id", "semantic_hash"}}
    semantic = stable_hash(semantic_payload)
    if semantic != record.get("semantic_hash"):
        errors.append("SEMANTIC_HASH")
    expected_id = f"FMDL4B-RSCH-{record.get('symbol')}-{semantic[:16]}"
    if expected_id != record.get("research_id"):
        errors.append("RESEARCH_ID")
    return sorted(set(errors))


def raw_score_only_decision(profile: dict[str, Any]) -> bool:
    narrative_fields = [
        "business_model", "competitive_position", "owner_quality", "variant_perception",
        "why_now", "first_rejection", "what_would_make_investable",
    ]
    if any(not str(profile.get(field, "")).strip() for field in narrative_fields):
        return True
    if not profile.get("prove_kill_checks") or not profile.get("public_sources"):
        return True
    return False
