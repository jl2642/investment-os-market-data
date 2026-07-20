from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

VOLATILE_FIELDS = {"generated_at", "published_at", "elapsed_seconds"}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(canonical(payload), ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


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


def semantic_frame_hash(frame: pd.DataFrame, *, sort_by: Iterable[str] = ("symbol",)) -> str:
    clean_frame = frame.copy()
    clean_frame = clean_frame.drop(columns=[c for c in VOLATILE_FIELDS if c in clean_frame.columns], errors="ignore")
    available = [column for column in sort_by if column in clean_frame.columns]
    if available:
        clean_frame = clean_frame.sort_values(available, kind="stable")
    return stable_hash(clean_frame.to_dict(orient="records"))


def parse_json_object(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value:
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def route_for_priority(priority: Any, cfg: dict[str, Any]) -> list[str]:
    key = str(priority or "DEFAULT")
    routes = cfg["public_equity_routing"]["priority_routes"]
    return list(routes.get(key, routes["DEFAULT"]))


def quality_state(unified: dict[str, Any], financial: dict[str, Any]) -> tuple[str, list[str]]:
    limitations: list[str] = []
    financial_state = str(financial.get("score_state") or "")
    financial_confidence = str(financial.get("score_confidence") or "UNAVAILABLE")
    valuation_count = int(unified.get("valuation_valid_metric_count") or 0)
    shareholder_state = str(unified.get("shareholder_return_state") or "UNAVAILABLE")
    capitalization_state = str(unified.get("capitalization_state") or "")

    if not financial_state.startswith("SCORE_ACCEPTED"):
        limitations.append("FINANCIAL_SCORE_NOT_DECISION_GRADE")
    if financial_confidence in {"LOW", "UNAVAILABLE"}:
        limitations.append("FINANCIAL_CONFIDENCE_LIMITED")
    if valuation_count < 2:
        limitations.append("VALUATION_EVIDENCE_THIN")
    if shareholder_state != "COMPLETE":
        limitations.append("SHAREHOLDER_RETURN_EVIDENCE_INCOMPLETE")
    if capitalization_state not in {"COMPLETE", "VALID", "ACCEPTED"}:
        limitations.append("CAPITALIZATION_STATE_REQUIRES_REVIEW")

    if not limitations and financial_confidence == "HIGH" and valuation_count >= 3:
        return "DECISION_GRADE", limitations
    if unified.get("close") is not None and financial_state:
        return "RESEARCH_USABLE_WITH_LIMITATIONS", limitations
    return "REVIEW_ONLY", limitations


def envelope_record(
    unified: dict[str, Any],
    financial: dict[str, Any],
    screening: dict[str, Any] | None,
    *,
    release_ids: dict[str, str],
    cfg: dict[str, Any],
) -> dict[str, Any]:
    screening = screening or {}
    quality, limitations = quality_state(unified, financial)
    if not screening:
        limitations.append("NOT_IN_FMDL2_RESEARCH_LONGLIST")
    source_release_ids = dict(release_ids)
    market = {
        key: clean(unified.get(key))
        for key in [
            "exchange", "board", "sector_profile", "market_as_of_date", "close",
            "total_market_cap_cny", "float_market_cap_cny", "capitalization_state",
            "capitalization_lineage_id",
        ]
    }
    financial_evidence = {
        key: clean(financial.get(key))
        for key in [
            "financial_score", "score_band", "score_confidence", "score_confidence_numeric",
            "available_family_count", "available_family_weight", "global_factor_weight_coverage",
            "conditional_weight_share", "ranking_eligible", "score_state", "source_hardening_release_id",
        ]
    }
    valuation = {
        key: clean(unified.get(key))
        for key in [
            "pe_ttm", "pe_ttm_state", "earnings_yield_ttm", "earnings_yield_ttm_state",
            "pb", "pb_state", "ps_ttm", "ps_ttm_state", "fcf_yield_ttm", "fcf_yield_ttm_state",
            "ev_sales_ttm", "ev_sales_ttm_state", "ev_operating_income_ttm",
            "ev_operating_income_ttm_state", "valuation_valid_metric_count",
            "valuation_decision_grade_metric_count", "valuation_row_hash",
        ]
    }
    shareholder = {
        key: clean(unified.get(key))
        for key in [
            "implemented_cash_dividend_per_share_ttm", "implemented_cash_dividend_total_cny_ttm",
            "dividend_yield_ttm", "completed_buyback_yield_ttm",
            "completed_issuance_dilution_yield_ttm", "shareholder_yield_ttm",
            "shareholder_return_state", "complete_shareholder_yield", "shareholder_event_lineage_ids_json",
        ]
    }
    screening_evidence = {
        key: clean(screening.get(key))
        for key in [
            "overall_rank", "research_priority", "primary_sleeve", "sleeves", "aggregate_score",
            "investability_status", "factor_record_quality", "confidence_grade", "event_flag_count",
            "longlist_row_hash",
        ]
    }
    base = {
        "symbol": str(unified["symbol"]),
        "name": str(unified.get("name") or ""),
        "as_of": str(unified.get("market_as_of_date") or ""),
        "source_release_ids": source_release_ids,
        "market_evidence": market,
        "financial_evidence": financial_evidence,
        "valuation_evidence": valuation,
        "shareholder_return_evidence": shareholder,
        "screening_evidence": screening_evidence,
        "quality_state": quality,
        "controlled_limitations": sorted(set(limitations)),
        "authority": cfg["evidence_envelope"]["authority"],
        "trade_authority": "NONE",
    }
    semantic = stable_hash(base)
    base["evidence_id"] = f"FMDL4A-EV-{base['symbol']}-{semantic[:16]}"
    base["semantic_hash"] = semantic
    return base


def validate_envelope_shape(record: dict[str, Any]) -> list[str]:
    required = {
        "evidence_id", "symbol", "name", "as_of", "source_release_ids", "market_evidence",
        "financial_evidence", "valuation_evidence", "shareholder_return_evidence",
        "screening_evidence", "quality_state", "controlled_limitations", "semantic_hash",
        "authority", "trade_authority",
    }
    errors: list[str] = []
    missing = sorted(required - set(record))
    if missing:
        errors.append("MISSING_FIELDS:" + ",".join(missing))
    if record.get("trade_authority") != "NONE":
        errors.append("TRADE_AUTHORITY")
    if record.get("authority") != "DATA_AND_RESEARCH_EVIDENCE_ONLY":
        errors.append("AUTHORITY")
    if record.get("quality_state") not in {"DECISION_GRADE", "RESEARCH_USABLE_WITH_LIMITATIONS", "REVIEW_ONLY"}:
        errors.append("QUALITY_STATE")
    semantic_payload = {k: v for k, v in record.items() if k not in {"evidence_id", "semantic_hash"}}
    if stable_hash(semantic_payload) != record.get("semantic_hash"):
        errors.append("SEMANTIC_HASH")
    expected_id = f"FMDL4A-EV-{record.get('symbol')}-{str(record.get('semantic_hash'))[:16]}"
    if record.get("evidence_id") != expected_id:
        errors.append("EVIDENCE_ID")
    return errors


def json_dumps(value: Any) -> str:
    return json.dumps(canonical(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
