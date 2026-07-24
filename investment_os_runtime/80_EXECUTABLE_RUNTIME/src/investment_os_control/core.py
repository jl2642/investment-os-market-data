from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any
import hashlib
import json

from jsonschema import Draft202012Validator


class ControlError(RuntimeError):
    pass


class AuthorityError(ControlError):
    pass


class FreshnessError(ControlError):
    pass


class PermissionError(ControlError):
    pass


class PromotionError(ControlError):
    pass


VOLATILE_KEYS = {
    "run_id", "generated_at", "published_at", "checked_at", "created_at",
    "updated_at", "workflow_run_id", "artifact_id"
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def canonicalize(value: Any, *, ignore_volatile: bool = False) -> Any:
    if isinstance(value, dict):
        return {
            key: canonicalize(item, ignore_volatile=ignore_volatile)
            for key, item in sorted(value.items())
            if not (ignore_volatile and key in VOLATILE_KEYS)
        }
    if isinstance(value, list):
        return [canonicalize(item, ignore_volatile=ignore_volatile) for item in value]
    return value


def canonical_hash(value: Any, *, ignore_volatile: bool = False) -> str:
    canonical = canonicalize(value, ignore_volatile=ignore_volatile)
    data = json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def parse_date(value: str) -> date:
    return date.fromisoformat(value[:10])


def assess_freshness(
    as_of_date: str,
    evaluation_date: str,
    maximum_age_calendar_days: int,
    stale_behavior: str,
) -> dict[str, Any]:
    age = (parse_date(evaluation_date) - parse_date(as_of_date)).days
    stale = age > maximum_age_calendar_days
    if not stale:
        outcome = "PASS"
    elif stale_behavior in {"BLOCK", "BLOCK_LIVE_ACTION"}:
        outcome = "BLOCK"
    elif stale_behavior in {"REVIEW_ONLY", "HUMAN_REENTRY_REVIEW", "REQUIRE_USER_CONFIRMATION"}:
        outcome = "REVIEW_REQUIRED"
    else:
        outcome = "RESTRICT"
    return {
        "as_of_date": as_of_date,
        "evaluation_date": evaluation_date,
        "age_calendar_days": age,
        "maximum_age_calendar_days": maximum_age_calendar_days,
        "stale": stale,
        "stale_behavior": stale_behavior,
        "outcome": outcome,
    }


def classify_semantic_change(old: Any, new: Any) -> dict[str, Any]:
    exact_old = canonical_hash(old)
    exact_new = canonical_hash(new)
    semantic_old = canonical_hash(old, ignore_volatile=True)
    semantic_new = canonical_hash(new, ignore_volatile=True)
    return {
        "exact_change": exact_old != exact_new,
        "semantic_change": semantic_old != semantic_new,
        "run_id_only_or_metadata_only": exact_old != exact_new and semantic_old == semantic_new,
        "old_semantic_hash": semantic_old,
        "new_semantic_hash": semantic_new,
    }


def enforce_market_permission(binding: dict[str, Any], requested_action: str) -> dict[str, Any]:
    if binding.get("trade_authority") != "NONE":
        raise AuthorityError("TRADE_AUTHORITY_ESCALATION")
    permissions = binding.get("permissions", {})
    key_map = {
        "RESEARCH": "research",
        "CANDIDATE_PROPOSAL": "candidate_proposal",
        "CANDIDATE_ADMISSION": "candidate_automatic_admission",
        "SIMULATION_PROPOSAL": "simulation_proposal",
        "SIMULATION_ADMISSION": "simulation_automatic_admission",
        "REAL_ACTION_PROPOSAL": "real_action_proposal",
        "REAL_ACCOUNT_ADMISSION": "real_automatic_admission",
        "ORDER_EXECUTION": "order_execution",
    }
    if requested_action not in key_map:
        raise PermissionError(f"UNKNOWN_ACTION:{requested_action}")
    allowed = bool(permissions.get(key_map[requested_action], False))
    return {
        "market": binding.get("market"),
        "requested_action": requested_action,
        "allowed": allowed,
        "outcome": "ALLOW" if allowed else "BLOCK",
        "trade_authority": "NONE",
    }


def route_event(event: dict[str, Any], taxonomy: dict[str, Any]) -> dict[str, Any]:
    level = event.get("level")
    if level not in taxonomy["levels"]:
        raise ControlError(f"UNKNOWN_EVENT_LEVEL:{level}")
    spec = taxonomy["levels"][level]
    return {
        "event_id": event.get("event_id"),
        "level": level,
        "meaning": spec["meaning"],
        "routes": list(spec["routes"]),
        "urgency": spec["urgency"],
        "automatic_trade": False,
        "state_change_mode": "PROPOSAL_ONLY",
        "trade_authority": "NONE",
    }


def gate_operating_product(product: dict[str, Any]) -> dict[str, Any]:
    status = product.get("status", "CANDIDATE")
    qc = product.get("qc_status")
    promotion = product.get("promotion_record")
    if status == "CURRENT" and not (qc == "PASS" and isinstance(promotion, dict)):
        raise PromotionError("CURRENT_WITHOUT_QC_AND_PROMOTION")
    if product.get("investment_state_mutations", 0) != 0:
        raise PromotionError("SCHEDULED_PRODUCT_UNAUTHORIZED_STATE_MUTATION")
    if product.get("orders", 0) != 0:
        raise PromotionError("ORDER_GENERATION_PROHIBITED")
    return {
        "product_id": product.get("product_id"),
        "status": status,
        "eligible_for_current": qc == "PASS" and isinstance(promotion, dict),
        "trade_authority": "NONE",
    }


def validate_schema(instance: Any, schema: dict[str, Any]) -> list[str]:
    validator = Draft202012Validator(schema)
    return [
        "/".join(map(str, error.absolute_path)) + ":" + error.message
        for error in sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))
    ]


def validate_runtime(root: Path, evaluation_date: str) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    control = read_json(root / "00_CONTROL" / "EXECUTION_REGISTER_CURRENT.json")
    if control.get("trade_authority") != "NONE":
        errors.append("CONTROL_TRADE_AUTHORITY")

    binding_root = root / "50_MARKET_CAPABILITY_BINDINGS"
    registry = read_json(binding_root / "BINDING_REGISTRY.json")
    if registry.get("binding_count") != 6:
        errors.append("BINDING_COUNT")
    if registry.get("trade_authority") != "NONE":
        errors.append("BINDING_TRADE_AUTHORITY")

    a_share = read_json(binding_root / "A_SHARE_CURRENT.json")
    daily = a_share["datasets"]["daily_market_snapshot"]
    freshness = assess_freshness(
        a_share["as_of_date"],
        evaluation_date,
        daily["maximum_age_calendar_days"],
        daily["stale_behavior"],
    )
    if freshness["stale"]:
        if freshness["outcome"] != "BLOCK":
            errors.append("A_SHARE_STALENESS_NOT_BLOCKED")
        else:
            warnings.append("A_SHARE_LIVE_ACTION_BLOCKED_BY_STALENESS")
    elif freshness["outcome"] != "PASS":
        errors.append("A_SHARE_FRESH_DATA_NOT_ACCEPTED")

    hk = read_json(binding_root / "HK_CONNECT_CURRENT.json")
    if enforce_market_permission(hk, "CANDIDATE_ADMISSION")["allowed"]:
        errors.append("HK_AUTOMATIC_CANDIDATE_ADMISSION")

    us = read_json(binding_root / "US_RESEARCH_ADAPTER_CURRENT.json")
    if not enforce_market_permission(us, "RESEARCH")["allowed"]:
        errors.append("US_RESEARCH_NOT_ALLOWED")
    for action in ("CANDIDATE_PROPOSAL", "SIMULATION_PROPOSAL", "REAL_ACTION_PROPOSAL", "ORDER_EXECUTION"):
        if enforce_market_permission(us, action)["allowed"]:
            errors.append(f"US_PERMISSION:{action}")

    fmdl7 = read_json(binding_root / "FMDL7_GOVERNANCE_BINDING.json")
    controls = fmdl7["controls"]
    forbidden = [
        "forced_common_factor_score", "global_cross_market_stock_rank",
        "ticker_only_identity_matching", "neutral_fill", "silent_source_substitution",
        "automatic_candidate_promotion", "automatic_simulation_admission",
        "automatic_real_account_admission", "automatic_rule_mutation",
    ]
    if any(controls.get(key) is not False for key in forbidden):
        errors.append("CROSS_MARKET_CONTROL")
    if controls.get("human_user_is_only_investment_authority") is not True:
        errors.append("HUMAN_AUTHORITY")
    if controls.get("trade_authority") != "NONE":
        errors.append("FMDL7_TRADE_AUTHORITY")

    cadence = read_json(root / "60_OPERATIONS_AND_EVENT" / "CADENCE_REGISTRY.json")
    if any(row["activation"] not in {"DISABLED_UNTIL_WP6", "INTERFACE_ACTIVE_PRODUCER_DISABLED"} for row in cadence["cadences"]):
        errors.append("AUTOMATION_PREMATURELY_ACTIVE")

    candidate_attribution = read_json(root / "70_ATTRIBUTION_AND_CALIBRATION" / "CANDIDATE_OUTCOME_CONTRACT.json")
    if candidate_attribution.get("alpha_claim_allowed") is not False:
        errors.append("CANDIDATE_ALPHA_OVERCLAIM")

    rule_calibration = read_json(root / "70_ATTRIBUTION_AND_CALIBRATION" / "RULE_CALIBRATION_CONTRACT.json")
    if rule_calibration.get("automatic_rule_change") is not False:
        errors.append("AUTOMATIC_RULE_CHANGE")

    zero = read_json(root / "00_CONTROL" / "ZERO_MUTATION_PROOF.json")
    for key in (
        "candidate_membership_mutations", "simulation_trade_mutations",
        "real_account_mutations", "rule_auto_mutations", "orders"
    ):
        if int(zero.get(key, 0)) != 0:
            errors.append(f"ZERO_MUTATION:{key}")

    return {
        "runtime_version": "1.0.1",
        "evaluation_date": evaluation_date,
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "warnings": warnings,
        "trade_authority": "NONE",
    }
