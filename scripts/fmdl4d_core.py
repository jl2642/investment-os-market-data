from __future__ import annotations

import hashlib
import json
import math
import zipfile
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

VOLATILE_FIELDS = {"generated_at", "published_at", "created_at", "elapsed_seconds"}


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
    path.write_text(
        json.dumps(canonical(payload), ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, records: list[dict[str, Any]], *, sort_key: str = "symbol") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in sorted(records, key=lambda item: (str(item.get(sort_key, "")), str(item.get("thesis_record_id", "")))):
            handle.write(json.dumps(canonical(record), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    return records


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


def semantic_frame_hash(frame: pd.DataFrame, *, sort_by: Iterable[str] = ("symbol",)) -> str:
    clean_frame = frame.copy()
    clean_frame = clean_frame.drop(columns=[column for column in VOLATILE_FIELDS if column in clean_frame.columns], errors="ignore")
    available = [column for column in sort_by if column in clean_frame.columns]
    if available:
        clean_frame = clean_frame.sort_values(available, kind="stable")
    return stable_hash(clean_frame.to_dict(orient="records"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def deterministic_zip(source_root: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(item for item in source_root.rglob("*") if item.is_file()):
            relative = path.relative_to(source_root).as_posix()
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def feedback_ids_for_symbol(symbol: str, cfg: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for proposal in cfg["feedback_proposals"]:
        scope = proposal["scope_symbols"]
        if "ALL" in scope or symbol in scope:
            ids.append(proposal["proposal_id"])
    return sorted(ids)


def classify_catalyst(text: str) -> str:
    lowered = text.lower()
    if any(token in lowered for token in ["dividend", "distribution", "capital return", "payout", "asset monetization"]):
        return "CAPITAL_RETURN"
    if any(token in lowered for token in ["margin", "operating leverage", "profit", "cash"]):
        return "EARNINGS_AND_CASH"
    if any(token in lowered for token in ["ai", "hyperscaler", "datacenter", "data-center", "network"]):
        return "INDUSTRY_AND_PRODUCT_DEMAND"
    if any(token in lowered for token in ["throughput", "generation", "water", "orders", "shipments", "growth", "share gains"]):
        return "OPERATING_KPI"
    return "COMPANY_EVENT"


def threshold_condition(metric: str) -> tuple[str, str, str]:
    lowered = metric.lower()
    if any(token in lowered for token in ["cash flow", "free cash flow", "cash conversion"]):
        return (
            "Recurring cash generation reconciles to reported earnings and covers the relevant dividend, capex or working-capital burden.",
            "Recurring cash conversion remains weak or cannot be reconciled to reported earnings in consecutive official observations.",
            "CASH_QUALITY",
        )
    if any(token in lowered for token in ["margin", "yield"]):
        return (
            "The reported margin or yield is stable or improving and the change is explained by product mix, pricing or operating efficiency.",
            "The reported margin or yield deteriorates without a temporary, evidence-backed explanation.",
            "MARGIN_OR_YIELD",
        )
    if any(token in lowered for token in ["valuation", "price"]):
        return (
            "A timestamped current price clears an explicit base/bear/bull scenario with acceptable downside under the approved hurdle.",
            "The normalized bear case or expectations embedded in price fails the approved downside hurdle.",
            "VALUATION_AND_EXPECTATIONS",
        )
    if any(token in lowered for token in ["customer concentration", "top-customer"]):
        return (
            "Demand is supported by multiple customers or programs and concentration risk is stable or falling.",
            "Dependence on a single customer or program rises while order visibility, margin or cash conversion weakens.",
            "CUSTOMER_CONCENTRATION",
        )
    if any(token in lowered for token in ["investment-income", "investment income", "non-recurring", "recurring earnings", "operating profit"]):
        return (
            "Core recurring operating earnings explain the majority of reported profit and reconcile to cash generation.",
            "Headline profit depends materially on investment income, non-recurring items or minority-interest economics that are not reconciled.",
            "QUALITY_OF_EARNINGS",
        )
    if any(token in lowered for token in ["minority interest"]):
        return (
            "The economics attributable to listed-company shareholders are explicitly reconciled after minority interests.",
            "Growth is concentrated in subsidiaries while listed-company attributable economics remain unclear or deteriorate.",
            "MINORITY_INTEREST_ECONOMICS",
        )
    return (
        "The metric follows the expected path in the next official filing or operating disclosure and is supported by source-backed reconciliation.",
        "The metric moves materially opposite the thesis in consecutive official observations or the evidence cannot be reconciled.",
        "OPERATING_OR_THESIS_KPI",
    )


def build_catalyst_rows(
    queue_row: dict[str, Any],
    research: dict[str, Any],
    cfg: dict[str, Any],
) -> list[dict[str, Any]]:
    catalysts = parse_json_list(research.get("catalysts_json"))
    symbol = str(queue_row["symbol"])
    rows: list[dict[str, Any]] = []
    for index, catalyst in enumerate(catalysts, start=1):
        payload = {
            "symbol": symbol,
            "name": str(queue_row["name"]),
            "thesis_version": cfg["tracking"]["thesis_version"],
            "catalyst": str(catalyst),
            "category": classify_catalyst(str(catalyst)),
            "expected_window": "NEXT_REPORTED_PERIOD_OR_MATERIAL_EVENT",
            "source_status": "INHERITED_FROM_FMDL4B_SOURCE_BACKED_RESEARCH",
            "latest_status": "UNTESTED_BASELINE",
            "impact": "PROVE_OR_DISCONFIRM_THESIS",
            "next_evidence_source": "NEXT_OFFICIAL_FILING_OR_OPERATIONAL_DISCLOSURE",
            "update_sla_business_days": cfg["tracking"]["post_catalyst_update_sla_business_days"],
            "owner_role": "PUBLIC_EQUITY_RESEARCH_OWNER",
            "automatic_state_mutation": False,
            "authority": cfg["authority"],
            "trade_authority": "NONE",
        }
        semantic = stable_hash(payload)
        payload["catalyst_id"] = f"FMDL4D-CAT-{symbol}-{index:02d}-{semantic[:12]}"
        payload["semantic_hash"] = semantic
        rows.append(payload)
    return rows


def build_prove_kill_rows(
    queue_row: dict[str, Any],
    research: dict[str, Any],
    cfg: dict[str, Any],
) -> list[dict[str, Any]]:
    checks = parse_json_list(research.get("prove_kill_checks_json"))
    symbol = str(queue_row["symbol"])
    rows: list[dict[str, Any]] = []
    for index, metric in enumerate(checks, start=1):
        prove_condition, kill_condition, category = threshold_condition(str(metric))
        payload = {
            "symbol": symbol,
            "name": str(queue_row["name"]),
            "thesis_version": cfg["tracking"]["thesis_version"],
            "metric": str(metric),
            "category": category,
            "prove_condition": prove_condition,
            "kill_condition": kill_condition,
            "threshold_origin": cfg["tracking"]["threshold_origin"],
            "threshold_approval_status": cfg["tracking"]["threshold_approval_status"],
            "latest_status": "PENDING_BASELINE_OBSERVATION",
            "latest_evidence_id": None,
            "action_if_proved": "ADVANCE_REENTRY_REVIEW_ONLY",
            "action_if_warning": "CONTINUE_WATCH_AND_REQUEST_EVIDENCE",
            "action_if_killed": "RE_UNDERWRITE_OR_RETIRE_THESIS",
            "automatic_state_mutation": False,
            "owner_role": "PUBLIC_EQUITY_RESEARCH_OWNER",
            "authority": cfg["authority"],
            "trade_authority": "NONE",
        }
        semantic = stable_hash(payload)
        payload["prove_kill_id"] = f"FMDL4D-PK-{symbol}-{index:02d}-{semantic[:12]}"
        payload["semantic_hash"] = semantic
        rows.append(payload)
    return rows


def build_attribution_row(queue_row: dict[str, Any], research: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    source_as_of = str(research["as_of"])
    return {
        "symbol": str(queue_row["symbol"]),
        "name": str(queue_row["name"]),
        "thesis_version": cfg["tracking"]["thesis_version"],
        "exposure_status": cfg["tracking"]["exposure_status"],
        "observation_start": source_as_of,
        "observation_end": None,
        "current_price_available": False,
        "approved_entry_price_available": False,
        "benchmark": None,
        "gross_return": None,
        "benchmark_return": None,
        "active_return": None,
        "selection_attribution": None,
        "position_attribution": None,
        "timing_attribution": None,
        "fees_tax_attribution": None,
        "thesis_attribution_status": cfg["tracking"]["attribution_status"],
        "decision_attribution_status": "PROCESS_ONLY_BASELINE_NO_OUTCOME",
        "failure_classification": "NO_OBSERVATION",
        "confidence": "NOT_APPLICABLE",
        "reason": "NO_SIMULATION_OR_REAL_ACCOUNT_ADMISSION_AND_NO_APPROVED_ENTRY_PRICE",
        "next_observation_trigger": "FIRST_ACCEPTED_EXPOSURE_OR_FORMAL_THESIS_RETIREMENT",
        "candidate_pool_mutation_count": 0,
        "simulation_mutation_count": 0,
        "real_account_mutation_count": 0,
        "order_generation_count": 0,
        "authority": cfg["authority"],
        "trade_authority": "NONE",
    }


def build_thesis_record(
    queue_row: dict[str, Any],
    research: dict[str, Any],
    catalyst_rows: list[dict[str, Any]],
    prove_kill_rows: list[dict[str, Any]],
    cfg: dict[str, Any],
) -> dict[str, Any]:
    symbol = str(queue_row["symbol"])
    source_as_of = date.fromisoformat(str(research["as_of"]))
    max_review_date = source_as_of + timedelta(days=int(cfg["tracking"]["maximum_review_days_from_source_as_of"]))
    return_attribution = {
        "status": cfg["tracking"]["attribution_status"],
        "gross_return": None,
        "benchmark_return": None,
        "active_return": None,
        "selection_effect": None,
        "position_effect": None,
        "timing_effect": None,
        "reason": "NO_ACCEPTED_SIMULATION_OR_REAL_ACCOUNT_EXPOSURE",
    }
    decision_attribution = {
        "status": "PROCESS_ONLY_BASELINE_NO_OUTCOME",
        "selection_decision": "REENTRY_REVIEW_QUEUE_ONLY",
        "position_decision": "NO_POSITION",
        "timing_decision": "NO_APPROVED_ENTRY",
        "failure_classification": "NO_OBSERVATION",
    }
    payload = {
        "symbol": symbol,
        "name": str(queue_row["name"]),
        "thesis_version": cfg["tracking"]["thesis_version"],
        "source_as_of": str(research["as_of"]),
        "company_thesis_status": cfg["tracking"]["company_thesis_status_by_queue"][str(queue_row["queue_state"])],
        "security_thesis_readiness": cfg["tracking"]["security_thesis_readiness"],
        "position_action": cfg["tracking"]["position_action"],
        "portfolio_role": cfg["tracking"]["portfolio_role"],
        "thesis_summary": str(research["business_model"]) + " " + str(research["competitive_position"]),
        "variant_perception": str(research["variant_perception"]),
        "earnings_drivers": parse_json_list(research.get("earnings_drivers_json")),
        "risks": parse_json_list(research.get("risks_json")),
        "open_gates": parse_json_list(queue_row.get("open_gates_json")),
        "catalyst_ids": [row["catalyst_id"] for row in catalyst_rows],
        "prove_kill_ids": [row["prove_kill_id"] for row in prove_kill_rows],
        "evidence_ids": parse_json_list(queue_row.get("evidence_ids_json")),
        "research_id": str(queue_row["research_id"]),
        "transition_id": str(queue_row["transition_id"]),
        "return_attribution": return_attribution,
        "decision_attribution": decision_attribution,
        "lessons": [
            "NO_OUTCOME_YET_DO_NOT_INFER_ALPHA_FROM_RESEARCH_GRADUATION",
            "COMPANY_THESIS_SECURITY_READINESS_AND_POSITION_ACTION_REMAIN_SEPARATE",
        ],
        "feedback_proposal_ids": feedback_ids_for_symbol(symbol, cfg),
        "next_review_gate": {
            "event_trigger": "NEXT_OFFICIAL_FILING_OR_MATERIAL_DISCLOSURE",
            "maximum_review_date": max_review_date.isoformat(),
            "post_catalyst_update_sla_business_days": cfg["tracking"]["post_catalyst_update_sla_business_days"],
            "required_follow_on": str(queue_row["required_follow_on"]),
        },
        "authority": cfg["authority"],
        "trade_authority": "NONE",
    }
    semantic = stable_hash(payload)
    payload["thesis_record_id"] = f"FMDL4D-TH-{symbol}-{semantic[:16]}"
    payload["semantic_hash"] = semantic
    return payload


def validate_thesis_record(record: dict[str, Any], cfg: dict[str, Any]) -> list[str]:
    required = {
        "thesis_record_id", "symbol", "name", "thesis_version", "source_as_of",
        "company_thesis_status", "security_thesis_readiness", "position_action",
        "portfolio_role", "thesis_summary", "variant_perception", "earnings_drivers",
        "risks", "open_gates", "catalyst_ids", "prove_kill_ids", "evidence_ids",
        "research_id", "transition_id", "return_attribution", "decision_attribution",
        "lessons", "feedback_proposal_ids", "next_review_gate", "semantic_hash",
        "authority", "trade_authority",
    }
    errors: list[str] = []
    missing = sorted(required - set(record))
    if missing:
        errors.append("MISSING_FIELDS:" + ",".join(missing))
    if record.get("security_thesis_readiness") != cfg["tracking"]["security_thesis_readiness"]:
        errors.append("SECURITY_READINESS")
    if record.get("position_action") != "WAIT_FOR_PROOF":
        errors.append("POSITION_ACTION")
    if record.get("portfolio_role") != "UNASSIGNED_NO_EXPOSURE":
        errors.append("PORTFOLIO_ROLE")
    if len(record.get("catalyst_ids", [])) < 3:
        errors.append("CATALYST_IDS")
    if len(record.get("prove_kill_ids", [])) != 5:
        errors.append("PROVE_KILL_IDS")
    if record.get("return_attribution", {}).get("status") != "NOT_YET_OBSERVABLE_NO_POSITION":
        errors.append("RETURN_ATTRIBUTION_STATUS")
    if record.get("trade_authority") != "NONE":
        errors.append("TRADE_AUTHORITY")
    semantic_payload = {key: value for key, value in record.items() if key not in {"thesis_record_id", "semantic_hash"}}
    semantic = stable_hash(semantic_payload)
    if semantic != record.get("semantic_hash"):
        errors.append("SEMANTIC_HASH")
    expected = f"FMDL4D-TH-{record.get('symbol')}-{semantic[:16]}"
    if record.get("thesis_record_id") != expected:
        errors.append("THESIS_RECORD_ID")
    return errors
