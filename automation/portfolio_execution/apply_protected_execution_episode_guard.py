from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

TRADE_AUTHORITY = "NONE"
EPISODIC_ACTION_TO_TRANSACTION = {"ADD": "BUY", "TRIM": "SELL"}
MATERIALIZED_TREATMENT = "SOURCE_BASELINE_ALREADY_CONTAINS_DELTA"
CONFIRMED_EVIDENCE = {"USER_CONFIRMED", "USER_SCREENSHOT_CONFIRMED"}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def parse_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    try:
        if len(text) == 10:
            return datetime.fromisoformat(text).replace(tzinfo=timezone.utc)
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def parse_date(value: Any) -> date | None:
    parsed = parse_datetime(value)
    return parsed.date() if parsed else None


def recommendation_episode_key(rec: dict[str, Any]) -> str:
    """Stable across ordinary mark rebases; changes when underwriting/action changes."""
    payload = {
        "security_id": rec.get("security_id"),
        "action": rec.get("action"),
        "underwriting_price": rec.get("underwriting_price"),
        "underwriting_price_as_of": rec.get("underwriting_price_as_of"),
        "entry_price": rec.get("entry_price"),
        "base_value": rec.get("base_value"),
        "probability_weighted_value": rec.get("probability_weighted_value"),
        "confidence": rec.get("confidence"),
        "top_reasons": rec.get("top_reasons"),
    }
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:20]


def transaction_datetime(entry: dict[str, Any]) -> datetime | None:
    for key in ("execution_time", "confirmed_at", "trade_date"):
        parsed = parse_datetime(entry.get(key))
        if parsed is not None:
            return parsed
    return None


def is_materialized_user_trade(entry: dict[str, Any]) -> bool:
    if entry.get("confirmation_authority") != "USER":
        return False
    if entry.get("evidence_status") not in CONFIRMED_EVIDENCE:
        return False
    if entry.get("position_engine_treatment") != MATERIALIZED_TREATMENT:
        return False
    event_type = str(entry.get("event_type") or "")
    return "TRADE" in event_type and float(entry.get("quantity") or 0.0) > 0


def trade_satisfies_current_episode(
    *,
    entry: dict[str, Any],
    account: str,
    rec: dict[str, Any],
    recommendation_generated_at: datetime | None,
) -> bool:
    action = str(rec.get("action") or "")
    required_tx_action = EPISODIC_ACTION_TO_TRANSACTION.get(action)
    if required_tx_action is None:
        return False
    if entry.get("account") != account:
        return False
    if entry.get("security_id") != rec.get("security_id"):
        return False
    if entry.get("action") != required_tx_action:
        return False
    if not is_materialized_user_trade(entry):
        return False

    tx_dt = transaction_datetime(entry)
    if tx_dt is None:
        return False

    underwriting_date = parse_date(rec.get("underwriting_price_as_of"))
    if underwriting_date is not None:
        if tx_dt.date() > underwriting_date:
            return True
        if tx_dt.date() < underwriting_date:
            return False
        # Same-day fresh underwriting after an earlier trade must reopen the episode.
        if recommendation_generated_at is not None and recommendation_generated_at.date() == underwriting_date:
            return tx_dt >= recommendation_generated_at
        return True

    # Suppress only when the transaction can be proven to follow the recommendation.
    if recommendation_generated_at is None:
        return False
    return tx_dt >= recommendation_generated_at


def matching_user_execution(
    *,
    account: str,
    rec: dict[str, Any],
    recommendation: dict[str, Any],
    ledger: dict[str, Any],
) -> dict[str, Any] | None:
    generated_at = parse_datetime(recommendation.get("generated_at_utc"))
    matches = [
        entry
        for entry in ledger.get("entries", [])
        if trade_satisfies_current_episode(
            entry=entry,
            account=account,
            rec=rec,
            recommendation_generated_at=generated_at,
        )
    ]
    if not matches:
        return None
    return max(matches, key=lambda entry: transaction_datetime(entry) or datetime.min.replace(tzinfo=timezone.utc))


def recompute_execution_cash(execution: dict[str, Any]) -> None:
    cash = float(execution.get("starting_cash") or 0.0)
    for row in execution.get("rows", []):
        if row.get("status") not in {"READY_FOR_USER_OR_VIRTUAL_EXECUTION", "PARTIAL_CASH_CONSTRAINED"}:
            continue
        notional = float(row.get("estimated_notional") or 0.0)
        if row.get("side") == "SELL":
            cash += notional
        elif row.get("side") == "BUY":
            cash -= notional
    execution["ending_cash_if_all_validated_actions_executed"] = cash


def apply_protected_execution_episode_guard(
    phase3: dict[str, Any],
    recommendation: dict[str, Any],
    ledger: dict[str, Any],
) -> dict[str, Any]:
    recs = {
        str(row.get("security_id")): row
        for row in recommendation.get("records", [])
        if row.get("security_id")
    }
    diagnostics: list[dict[str, Any]] = []

    for account_name, account_key in (("REAL", "real_account"), ("SIMULATION", "simulation_account")):
        account = phase3.get(account_key) or {}
        target_plan = account.get("target_plan") or {}
        execution = account.get("execution_validation") or {}
        target_rows = {
            str(row.get("security_id")): row
            for row in target_plan.get("rows", [])
            if row.get("security_id")
        }

        for execution_row in execution.get("rows", []):
            sid = str(execution_row.get("security_id") or "")
            rec = recs.get(sid)
            if rec is None or str(rec.get("action") or "") not in EPISODIC_ACTION_TO_TRANSACTION:
                continue
            matched = matching_user_execution(
                account=account_name,
                rec=rec,
                recommendation=recommendation,
                ledger=ledger,
            )
            if matched is None:
                continue

            target_row = target_rows.get(sid)
            episode_key = recommendation_episode_key(rec)
            if target_row is not None:
                target_row["target_weight"] = target_row.get("current_weight", target_row.get("target_weight"))
                reasons = target_row.setdefault("target_weight_reasons", [])
                if "CURRENT_RECOMMENDATION_EPISODE_ALREADY_EXECUTED_USER_CONFIRMED" not in reasons:
                    reasons.append("CURRENT_RECOMMENDATION_EPISODE_ALREADY_EXECUTED_USER_CONFIRMED")
                target_row["execution_episode_key"] = episode_key
                target_row["matched_user_delta_id"] = matched.get("delta_id")

            execution_row["target_weight"] = execution_row.get("current_weight", execution_row.get("target_weight"))
            execution_row["target_quantity"] = execution_row.get("current_quantity")
            execution_row["status"] = "NO_ACTION_ALREADY_EXECUTED_RECOMMENDATION_EPISODE"
            execution_row["side"] = "HOLD"
            execution_row["validated_quantity"] = 0
            execution_row["reason"] = "USER_CONFIRMED_EXECUTION_ALREADY_SATISFIES_CURRENT_RECOMMENDATION_EPISODE"
            execution_row["execution_episode_key"] = episode_key
            execution_row["matched_user_delta_id"] = matched.get("delta_id")
            execution_row.pop("estimated_notional", None)

            diagnostics.append({
                "account": account_name,
                "security_id": sid,
                "action": rec.get("action"),
                "episode_key": episode_key,
                "matched_user_delta_id": matched.get("delta_id"),
                "guard_result": "SUPPRESS_REPEAT_ADD_TRIM",
            })

        if target_plan.get("rows"):
            target_plan["target_cash_weight"] = max(
                0.0,
                1.0 - sum(float(row.get("target_weight") or 0.0) for row in target_plan["rows"]),
            )
        recompute_execution_cash(execution)

    base_phase3_id = str(phase3.get("phase3_id") or "")
    if diagnostics and base_phase3_id:
        identity_payload = {
            "base_phase3_id": base_phase3_id,
            "protected_execution_episode_guard": diagnostics,
        }
        identity_body = json.dumps(
            identity_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        phase3["phase3_id_before_execution_episode_guard"] = base_phase3_id
        phase3["phase3_id"] = (
            "PORTFOLIO_EXECUTION_CURRENT_"
            + hashlib.sha256(identity_body.encode("utf-8")).hexdigest()[:16]
        )

    controls = phase3.setdefault("controls", {})
    controls["protected_execution_episode_guard"] = True
    controls["protected_repeat_add_trim_after_user_execution"] = False
    phase3["protected_execution_episode_guard"] = {
        "status": "PASS",
        "suppressed_repeat_action_count": len(diagnostics),
        "diagnostics": diagnostics,
        "scope": "REAL_AND_LEGACY_SIMULATION_ONLY",
        "ai_autonomous_1m_affected": False,
        "orders": 0,
        "trade_authority": TRADE_AUTHORITY,
    }
    return phase3


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase3-json", required=True)
    parser.add_argument("--recommendation", required=True)
    parser.add_argument("--user-transaction-ledger", required=True)
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args()

    phase3 = load_json(Path(args.phase3_json))
    recommendation = load_json(Path(args.recommendation))
    ledger = load_json(Path(args.user_transaction_ledger))
    guarded = apply_protected_execution_episode_guard(phase3, recommendation, ledger)
    write_json(Path(args.output_json), guarded)


if __name__ == "__main__":
    main()
