from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TRADE_AUTHORITY = "NONE"
AI_BOOK_ID = "AI_AUTONOMOUS_1M"
AI_INITIAL_CAPITAL = 1_000_000.0
LISTED_LOT = 100
DEFAULT_SINGLE_NAME_CAP = 0.10
DEFAULT_GROUP_CAP = 0.30
AI_CASH_FLOOR = 0.20
MAX_AI_POSITIONS = 10
PROTECTED_POSITION_ACTIONS = {"ADD", "TRIM", "EXIT"}
DEPLOYMENT_GATES = (10, 20, 30, 40)
DAY20_MIN_DECISION_GRADE_D2 = 5

CONFIDENCE_MULTIPLIER = {
    "HIGH": 1.00,
    "HIGH_MEDIUM": 0.95,
    "MEDIUM_HIGH": 0.90,
    "MEDIUM": 0.80,
    "LOW": 0.60,
}


def load_json(path: Path | None, default: Any = None) -> Any:
    if path is None or not path.exists():
        return {} if default is None else default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def canonical_hash(payload: Any) -> str:
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def num(value: Any, default: float | None = None) -> float | None:
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def confidence_multiplier(value: Any) -> float:
    return CONFIDENCE_MULTIPLIER.get(str(value or "").upper(), 0.75)


def research_score(rec: dict[str, Any]) -> float:
    expected = max(0.0, num(rec.get("expected_return"), 0.0) or 0.0)
    bear = num(rec.get("bear_downside"), -0.35)
    bear = -0.35 if bear is None else bear
    downside_penalty = min(1.0, max(0.35, 1.0 + bear))
    return expected * confidence_multiplier(rec.get("confidence")) * downside_penalty


def risk_group(holding: dict[str, Any] | None, rec: dict[str, Any]) -> str:
    holding = holding or {}
    name = str(rec.get("security_name") or holding.get("security_name") or "")
    asset_class = str(holding.get("asset_class") or "")
    bucket = str(holding.get("portfolio_bucket") or "")
    if "标普500" in name:
        return "US_SP500"
    if asset_class == "BOND_FUND":
        return "FIXED_INCOME"
    if "A500" in name:
        return "A_SHARE_A500"
    if "中证500" in name:
        return "A_SHARE_CSI500"
    if bucket:
        return bucket.split("/")[0].upper()
    if asset_class:
        return asset_class
    sid = str(rec.get("security_id") or "")
    return "A_SHARE_STOCK" if sid.endswith((".SH", ".SZ", ".BJ")) else "OTHER"


def recommendation_map(recommendation: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("security_id")): row
        for row in recommendation.get("records", [])
        if row.get("security_id")
    }


def lifecycle_map(lifecycle: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("security_id")): row
        for row in lifecycle.get("subjects", [])
        if row.get("security_id")
    }


def account_snapshot(account: dict[str, Any]) -> dict[str, Any]:
    summary = account.get("summary") or {}
    total_assets = float(summary.get("account_total_assets") or 0.0)
    cash = float(summary.get("execution_cash_balance") or 0.0)
    holdings = list(account.get("holdings", []))
    rows = []
    for holding in holdings:
        market_value = float(holding.get("market_value") or 0.0)
        rows.append({
            **holding,
            "current_weight": market_value / total_assets if total_assets > 0 else 0.0,
        })
    return {
        "account": account.get("account"),
        "total_assets": total_assets,
        "cash": cash,
        "cash_weight": cash / total_assets if total_assets > 0 else 0.0,
        "holdings": rows,
    }


def provisional_target_weight(
    *,
    current_weight: float,
    rec: dict[str, Any],
    lifecycle: dict[str, Any] | None,
    single_name_cap: float = DEFAULT_SINGLE_NAME_CAP,
) -> tuple[float, list[str]]:
    action = str(rec.get("action") or "WATCH")
    lifecycle_state = str((lifecycle or {}).get("lifecycle_state") or "")
    reasons: list[str] = []
    target = current_weight

    if action == "EXIT":
        target = 0.0
        reasons.append("CURRENT_DECISION_EXIT")
    elif action == "TRIM":
        target = current_weight * 0.50
        reasons.append("CURRENT_DECISION_TRIM_HALF_STEP")
    elif action == "ADD":
        score = research_score(rec)
        if current_weight >= single_name_cap:
            target = current_weight
            reasons.append("CURRENT_DECISION_ADD_BLOCKED_BY_EXISTING_SINGLE_NAME_CAP")
        else:
            target = min(
                single_name_cap,
                current_weight + min(0.025, score * 0.10),
            )
            reasons.append("CURRENT_DECISION_ADD_SCORE_SIZED")
    elif action == "HOLD":
        target = current_weight
        reasons.append("CURRENT_DECISION_HOLD_PRESERVE")
    else:
        reasons.append("NO_HELD_ACTION_CHANGE")

    # Risk limits are diagnostics unless the current formal Recommendation
    # already authorizes a position change.  They must never manufacture a
    # protected-account BUY/SELL from HOLD alone.
    if action in PROTECTED_POSITION_ACTIONS and target > single_name_cap:
        target = single_name_cap if action != "EXIT" else 0.0
        reasons.append("SINGLE_NAME_CAP_10PCT_ACTION_SIZING")
    elif current_weight > single_name_cap:
        reasons.append("SINGLE_NAME_CAP_10PCT_RISK_REVIEW_ONLY")

    if "CONCENTRATION_REVIEW" in lifecycle_state:
        reasons.append("CONCENTRATION_REVIEW_DIAGNOSTIC_ONLY")

    return max(0.0, target), reasons

def enforce_group_caps(rows: list[dict[str, Any]], group_cap: float = DEFAULT_GROUP_CAP) -> None:
    """Limit only incremental ADD risk; never shrink HOLD/TRIM/EXIT rows mechanically."""
    by_group: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_group.setdefault(row["risk_group"], []).append(row)

    for group, members in by_group.items():
        current_total = sum(float(x.get("current_weight") or 0.0) for x in members)
        add_members = [x for x in members if str(x.get("action") or "") == "ADD"]
        if not add_members:
            if current_total > group_cap:
                for member in members:
                    member["target_weight_reasons"].append(
                        f"RISK_GROUP_CAP_{group}_30PCT_REVIEW_ONLY"
                    )
            continue

        allowed_increase = max(0.0, group_cap - current_total)
        desired_increase = sum(
            max(0.0, float(x["target_weight"]) - float(x.get("current_weight") or 0.0))
            for x in add_members
        )
        if desired_increase <= allowed_increase + 1e-12:
            continue
        scale = allowed_increase / desired_increase if desired_increase > 0 else 0.0
        for member in add_members:
            current = float(member.get("current_weight") or 0.0)
            desired = max(0.0, float(member["target_weight"]) - current)
            member["target_weight"] = current + desired * scale
            member["target_weight_reasons"].append(
                f"RISK_GROUP_CAP_{group}_30PCT_LIMITS_ADD_ONLY"
            )

def build_account_target_plan(
    account: dict[str, Any],
    recommendation: dict[str, Any],
    lifecycle: dict[str, Any],
) -> dict[str, Any]:
    snap = account_snapshot(account)
    recs = recommendation_map(recommendation)
    life = lifecycle_map(lifecycle)
    rows: list[dict[str, Any]] = []
    for holding in snap["holdings"]:
        sid = str(holding.get("security_id"))
        rec = recs.get(sid)
        if rec is None:
            rows.append({
                "security_id": sid,
                "security_name": holding.get("security_name"),
                "asset_class": holding.get("asset_class"),
                "current_weight": holding["current_weight"],
                "target_weight": holding["current_weight"],
                "research_score": 0.0,
                "risk_group": risk_group(holding, {}),
                "target_weight_reasons": ["NO_CURRENT_RECOMMENDATION_FAIL_CLOSED"],
                "action": "HOLD_NO_CURRENT_RECOMMENDATION",
                "current_quantity": num(holding.get("quantity"), 0.0),
                "available_quantity": num(holding.get("available_quantity"), 0.0),
                "current_price": num(holding.get("mark"), 0.0),
            })
            continue
        target, reasons = provisional_target_weight(
            current_weight=holding["current_weight"],
            rec=rec,
            lifecycle=life.get(sid),
        )
        rows.append({
            "security_id": sid,
            "security_name": holding.get("security_name"),
            "asset_class": holding.get("asset_class"),
            "current_weight": holding["current_weight"],
            "target_weight": target,
            "research_score": research_score(rec),
            "risk_group": risk_group(holding, rec),
            "target_weight_reasons": reasons,
            "action": rec.get("action"),
            "current_quantity": num(holding.get("quantity"), 0.0),
            "available_quantity": num(holding.get("available_quantity"), 0.0),
            "current_price": num(holding.get("mark"), num(rec.get("current_price"), 0.0)),
            "expected_return": num(rec.get("expected_return"), 0.0),
            "bear_downside": num(rec.get("bear_downside"), None),
            "confidence": rec.get("confidence"),
        })

    enforce_group_caps(rows)

    # If proposed ADDs exceed available portfolio headroom, scale only the
    # incremental ADD amounts.  Existing HOLD/TRIM/EXIT targets are preserved.
    base_total = sum(
        float(x.get("current_weight") or 0.0)
        if str(x.get("action") or "") == "ADD"
        else float(x["target_weight"])
        for x in rows
    )
    add_rows = [x for x in rows if str(x.get("action") or "") == "ADD"]
    desired_add = sum(
        max(0.0, float(x["target_weight"]) - float(x.get("current_weight") or 0.0))
        for x in add_rows
    )
    add_headroom = max(0.0, 1.0 - base_total)
    if desired_add > add_headroom + 1e-12:
        scale = add_headroom / desired_add if desired_add > 0 else 0.0
        for row in add_rows:
            current = float(row.get("current_weight") or 0.0)
            increment = max(0.0, float(row["target_weight"]) - current)
            row["target_weight"] = current + increment * scale
            row["target_weight_reasons"].append("TOTAL_WEIGHT_HEADROOM_LIMITS_ADD_ONLY")
    target_total = sum(float(x["target_weight"]) for x in rows)

    return {
        "account": snap["account"],
        "total_assets": snap["total_assets"],
        "current_cash": snap["cash"],
        "current_cash_weight": snap["cash_weight"],
        "target_cash_weight": max(0.0, 1.0 - target_total),
        "rows": sorted(rows, key=lambda x: x["security_id"]),
    }


def is_listed_security(security_id: str, asset_class: str | None) -> bool:
    return security_id.endswith((".SH", ".SZ", ".BJ")) and asset_class != "BOND_FUND"


def rounded_target_quantity(
    *,
    target_weight: float,
    total_assets: float,
    price: float,
    security_id: str,
    asset_class: str | None,
) -> float | None:
    if price <= 0:
        return None
    if not is_listed_security(security_id, asset_class):
        return None
    raw = max(0.0, target_weight * total_assets / price)
    return float(math.floor(raw / LISTED_LOT) * LISTED_LOT)


def build_execution_plan(account_plan: dict[str, Any]) -> dict[str, Any]:
    total_assets = float(account_plan["total_assets"])
    available_cash = float(account_plan["current_cash"])
    rows: list[dict[str, Any]] = []
    enriched = []
    for row in account_plan["rows"]:
        target_qty = rounded_target_quantity(
            target_weight=float(row["target_weight"]),
            total_assets=total_assets,
            price=float(row.get("current_price") or 0.0),
            security_id=row["security_id"],
            asset_class=row.get("asset_class"),
        )
        enriched.append((row, target_qty))
    enriched.sort(
        key=lambda pair: (
            0 if pair[1] is not None and pair[1] < float(pair[0].get("current_quantity") or 0.0) else 1,
            -float(pair[0].get("research_score") or 0.0),
            pair[0]["security_id"],
        )
    )

    for row, target_qty in enriched:
        sid = row["security_id"]
        current_qty = float(row.get("current_quantity") or 0.0)
        price = float(row.get("current_price") or 0.0)
        asset_class = row.get("asset_class")
        action = str(row.get("action") or "")
        base = {
            "security_id": sid,
            "security_name": row.get("security_name"),
            "asset_class": asset_class,
            "action": action,
            "current_weight": row["current_weight"],
            "target_weight": row["target_weight"],
            "current_quantity": current_qty,
            "price": price,
            "orders": 0,
            "trade_authority": TRADE_AUTHORITY,
        }
        if not is_listed_security(sid, asset_class):
            rows.append({
                **base,
                "status": "MANUAL_FUND_EXECUTION_REVIEW",
                "side": "REVIEW",
                "validated_quantity": None,
                "reason": "NON_LISTED_FUND_SUBSCRIPTION_REDEMPTION_RULES_NOT_MODELED",
            })
            continue
        if action not in PROTECTED_POSITION_ACTIONS:
            rows.append({
                **base,
                "status": "NO_ACTION_REVIEW_ONLY",
                "side": "HOLD",
                "validated_quantity": 0,
                "target_quantity": current_qty,
                "reason": "CURRENT_RECOMMENDATION_DOES_NOT_AUTHORIZE_POSITION_CHANGE",
            })
            continue
        if target_qty is None or price <= 0:
            rows.append({
                **base,
                "status": "BLOCK_INVALID_PRICE",
                "side": "BLOCK",
                "validated_quantity": 0,
                "reason": "VALID_PRICE_REQUIRED",
            })
            continue

        delta = target_qty - current_qty
        if abs(delta) < 1e-9:
            rows.append({
                **base,
                "status": "NO_ACTION",
                "side": "HOLD",
                "validated_quantity": 0,
                "target_quantity": target_qty,
                "reason": "CURRENT_QUANTITY_ALREADY_MATCHES_ROUNDED_TARGET",
            })
            continue

        if action == "ADD" and delta < 0:
            rows.append({
                **base,
                "status": "NO_ACTION_DIRECTION_BLOCKED",
                "side": "HOLD",
                "validated_quantity": 0,
                "target_quantity": current_qty,
                "reason": "ADD_CANNOT_AUTHORIZE_SELL",
            })
            continue
        if action in {"TRIM", "EXIT"} and delta > 0:
            rows.append({
                **base,
                "status": "NO_ACTION_DIRECTION_BLOCKED",
                "side": "HOLD",
                "validated_quantity": 0,
                "target_quantity": current_qty,
                "reason": "TRIM_OR_EXIT_CANNOT_AUTHORIZE_BUY",
            })
            continue

        if delta < 0:
            qty = abs(delta)
            if target_qty == 0:
                qty = current_qty
            else:
                qty = math.floor(qty / LISTED_LOT) * LISTED_LOT
            qty = min(qty, float(row.get("available_quantity") or current_qty))
            if qty <= 0:
                rows.append({
                    **base,
                    "status": "BLOCK_NO_AVAILABLE_QUANTITY",
                    "side": "SELL",
                    "validated_quantity": 0,
                    "target_quantity": target_qty,
                    "reason": "AVAILABLE_QUANTITY_ZERO",
                })
                continue
            proceeds = qty * price
            available_cash += proceeds
            rows.append({
                **base,
                "status": "READY_FOR_USER_OR_VIRTUAL_EXECUTION",
                "side": "SELL",
                "validated_quantity": qty,
                "target_quantity": target_qty,
                "estimated_notional": proceeds,
                "reason": "SELL_QUANTITY_VALIDATED",
            })
            continue

        desired_buy = math.floor(delta / LISTED_LOT) * LISTED_LOT
        if desired_buy <= 0:
            rows.append({
                **base,
                "status": "BLOCK_LOT_SIZE",
                "side": "BUY",
                "validated_quantity": 0,
                "target_quantity": target_qty,
                "reason": "INCREMENT_BELOW_100_SHARE_LOT",
            })
            continue
        affordable = math.floor(available_cash / price / LISTED_LOT) * LISTED_LOT
        qty = min(desired_buy, affordable)
        if qty <= 0:
            rows.append({
                **base,
                "status": "BLOCK_CASH",
                "side": "BUY",
                "validated_quantity": 0,
                "target_quantity": target_qty,
                "reason": "INSUFFICIENT_EXECUTION_CASH_FOR_ONE_LOT",
            })
            continue
        status = "READY_FOR_USER_OR_VIRTUAL_EXECUTION"
        reason = "BUY_QUANTITY_VALIDATED"
        if qty < desired_buy:
            status = "PARTIAL_CASH_CONSTRAINED"
            reason = "BUY_REDUCED_TO_AVAILABLE_CASH"
        notional = qty * price
        available_cash -= notional
        rows.append({
            **base,
            "status": status,
            "side": "BUY",
            "validated_quantity": qty,
            "target_quantity": target_qty,
            "estimated_notional": notional,
            "reason": reason,
        })

    return {
        "account": account_plan["account"],
        "starting_cash": account_plan["current_cash"],
        "ending_cash_if_all_validated_actions_executed": available_cash,
        "rows": sorted(rows, key=lambda x: x["security_id"]),
        "controls": {
            "a_share_buy_lot": LISTED_LOT,
            "single_name_cap": DEFAULT_SINGLE_NAME_CAP,
            "group_cap": DEFAULT_GROUP_CAP,
            "real_or_legacy_simulation_mutation_authorized": False,
            "orders": 0,
            "trade_authority": TRADE_AUTHORITY,
        },
    }


def initial_ai_state(as_of_date: str) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "book_id": AI_BOOK_ID,
        "initial_capital": AI_INITIAL_CAPITAL,
        "cash": AI_INITIAL_CAPITAL,
        "positions": [],
        "transactions": [],
        "realized_pnl": 0.0,
        "nav_history": [{
            "as_of_date": as_of_date,
            "nav": AI_INITIAL_CAPITAL,
            "cash": AI_INITIAL_CAPITAL,
            "position_market_value": 0.0,
        }],
        "peak_nav": AI_INITIAL_CAPITAL,
        "current_nav": AI_INITIAL_CAPITAL,
        "cumulative_return": 0.0,
        "max_drawdown": 0.0,
        "turnover_since_inception": 0.0,
        "orders": 0,
        "trade_authority": TRADE_AUTHORITY,
    }


def ai_position_map(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("security_id")): dict(row)
        for row in state.get("positions", [])
        if row.get("security_id")
    }


def ai_target_weights(
    recommendation: dict[str, Any],
    lifecycle: dict[str, Any],
    state: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    recs = recommendation_map(recommendation)
    positions = ai_position_map(state)
    candidates: list[dict[str, Any]] = []

    for sid, rec in recs.items():
        action = str(rec.get("action") or "WATCH")
        held = sid in positions
        if action in {"AVOID", "EXIT"}:
            if held:
                candidates.append({
                    "security_id": sid,
                    "rec": rec,
                    "score": 0.0,
                    "forced_target": 0.0,
                    "risk_group": risk_group(None, rec),
                })
            continue
        if held and action == "TRIM":
            current_value = float(positions[sid].get("market_value") or 0.0)
            current_weight = current_value / max(float(state.get("current_nav") or AI_INITIAL_CAPITAL), 1.0)
            candidates.append({
                "security_id": sid,
                "rec": rec,
                "score": research_score(rec),
                "forced_target": min(DEFAULT_SINGLE_NAME_CAP, current_weight * 0.5),
                "risk_group": risk_group(None, rec),
            })
            continue
        if held and action in {"HOLD", "ADD", "BUY"}:
            candidates.append({
                "security_id": sid,
                "rec": rec,
                "score": research_score(rec),
                "forced_target": None,
                "risk_group": risk_group(None, rec),
            })
            continue
        if not held and action == "BUY":
            candidates.append({
                "security_id": sid,
                "rec": rec,
                "score": research_score(rec),
                "forced_target": None,
                "risk_group": risk_group(None, rec),
            })
            continue
        if not held and action == "BUY_BELOW":
            continue

    ranked = sorted(
        [x for x in candidates if x["forced_target"] is None],
        key=lambda x: (-x["score"], x["security_id"]),
    )
    allowed = ranked[:MAX_AI_POSITIONS]
    allowed_ids = {x["security_id"] for x in allowed}
    total_score = sum(max(x["score"], 1e-9) for x in allowed) or 1.0
    investable = 1.0 - AI_CASH_FLOOR

    out: dict[str, dict[str, Any]] = {}
    group_used: dict[str, float] = {}
    for item in candidates:
        sid = item["security_id"]
        if item["forced_target"] is not None:
            weight = float(item["forced_target"])
        elif sid not in allowed_ids:
            weight = 0.0
        else:
            raw = investable * max(item["score"], 1e-9) / total_score
            weight = min(DEFAULT_SINGLE_NAME_CAP, raw)
        group = item["risk_group"]
        remaining_group = max(0.0, DEFAULT_GROUP_CAP - group_used.get(group, 0.0))
        weight = min(weight, remaining_group)
        group_used[group] = group_used.get(group, 0.0) + weight
        out[sid] = {
            "target_weight": max(0.0, weight),
            "score": item["score"],
            "risk_group": group,
            "action": item["rec"].get("action"),
            "security_name": item["rec"].get("security_name"),
        }
    for sid, pos in positions.items():
        if sid not in out:
            out[sid] = {
                "target_weight": 0.0,
                "score": 0.0,
                "risk_group": str(pos.get("risk_group") or "UNKNOWN"),
                "action": "NO_CURRENT_ELIGIBLE_THESIS",
                "security_name": pos.get("security_name"),
            }
    return out


def lifecycle_prices(lifecycle: dict[str, Any]) -> dict[str, float]:
    out = {}
    for row in lifecycle.get("subjects", []):
        sid = str(row.get("security_id") or "")
        price = num(row.get("latest_price"))
        if sid and price is not None and price > 0:
            out[sid] = price
    return out


def current_decision_grade_ai_d2_ids(recommendation: dict[str, Any]) -> set[str]:
    """Count formal new-capital D2 outcomes usable by the AI-book experiment."""
    required = (
        "current_price",
        "entry_price",
        "base_value",
        "probability_weighted_value",
        "expected_return",
        "confidence",
        "bear_downside",
    )
    valid_actions = {"BUY", "BUY_BELOW", "WATCH_FOR_EVIDENCE", "WATCH", "AVOID"}
    out: set[str] = set()
    for rec in recommendation.get("records", []):
        sid = str(rec.get("security_id") or "")
        if not sid.endswith((".SH", ".SZ", ".BJ")):
            continue
        if rec.get("portfolio_implication") != "NEW_CAPITAL_CANDIDATE":
            continue
        if str(rec.get("action") or "") not in valid_actions:
            continue
        if all(rec.get(key) is not None for key in required):
            out.add(sid)
    return out


def update_ai_deployment_discipline(
    *,
    state: dict[str, Any],
    recommendation: dict[str, Any],
    as_of_date: str,
) -> dict[str, Any]:
    dates = sorted({
        str(row.get("as_of_date"))
        for row in state.get("nav_history", [])
        if row.get("as_of_date")
    })
    if as_of_date not in dates:
        dates.append(as_of_date)
        dates.sort()
    trading_day = max(1, len(dates))

    current_d2 = current_decision_grade_ai_d2_ids(recommendation)
    prior_seen = set(state.get("decision_grade_d2_seen", []))
    seen = sorted(prior_seen | current_d2)
    state["decision_grade_d2_seen"] = seen

    nav = float(state.get("current_nav") or AI_INITIAL_CAPITAL)
    cash = float(state.get("cash") or 0.0)
    cash_weight = cash / nav if nav > 0 else 1.0
    deployed_weight = max(0.0, 1.0 - cash_weight)
    recs = recommendation_map(recommendation)
    eligible_buy_ids = sorted(
        sid for sid, rec in recs.items()
        if rec.get("portfolio_implication") == "NEW_CAPITAL_CANDIDATE"
        and rec.get("action") == "BUY"
    )
    buy_below_ids = sorted(
        sid for sid, rec in recs.items()
        if rec.get("portfolio_implication") == "NEW_CAPITAL_CANDIDATE"
        and rec.get("action") == "BUY_BELOW"
    )

    triggered: list[str] = []
    if trading_day >= 10 and cash_weight > 0.80:
        triggered.append("AI_BOOK_DEPLOYMENT_REVIEW")
    if trading_day >= 20:
        if len(seen) < DAY20_MIN_DECISION_GRADE_D2:
            triggered.append("D2_THROUGHPUT_SHORTFALL")
        if cash_weight > 0.50:
            triggered.append("DAY20_DEPLOYMENT_REVIEW")
        if eligible_buy_ids and deployed_weight < 0.30:
            triggered.append("DEPLOYMENT_BELOW_30PCT_WITH_ELIGIBLE_BUY")
    if trading_day >= 30 and cash_weight > 0.70:
        triggered.append("OPPORTUNITY_STARVATION_REVIEW_REQUIRED")
    if trading_day >= 40 and cash_weight > 0.50:
        triggered.append("EXPERIMENT_INSUFFICIENT_DEPLOYMENT")

    if "EXPERIMENT_INSUFFICIENT_DEPLOYMENT" in triggered:
        status = "POLICY_PROPOSAL_REVIEW_REQUIRED"
    elif "OPPORTUNITY_STARVATION_REVIEW_REQUIRED" in triggered:
        status = "OPPORTUNITY_RESEARCH_REVIEW_REQUIRED"
    elif "D2_THROUGHPUT_SHORTFALL" in triggered:
        status = "D2_THROUGHPUT_REVIEW_REQUIRED"
    elif "DAY20_DEPLOYMENT_REVIEW" in triggered:
        status = "DECISION_GRADE_D2_AND_ELIGIBLE_BUY_REVIEW"
    elif "AI_BOOK_DEPLOYMENT_REVIEW" in triggered:
        status = "THROUGHPUT_AND_GATE_REVIEW"
    else:
        status = "NORMAL_ACCUMULATION"

    if cash_weight <= 0.70:
        high_cash_reason = None
    elif len(seen) < DAY20_MIN_DECISION_GRADE_D2:
        high_cash_reason = "INSUFFICIENT_CUMULATIVE_DECISION_GRADE_D2"
    elif not eligible_buy_ids and buy_below_ids:
        high_cash_reason = "BUY_BELOW_REQUIRES_FRESH_D2_TO_BECOME_BUY"
    elif not eligible_buy_ids:
        high_cash_reason = "NO_CURRENT_DECISION_GRADE_BUY"
    else:
        high_cash_reason = "PORTFOLIO_CONSTRAINTS_CASH_FLOOR_OR_LOT_SIZE"

    next_gate = next((gate for gate in DEPLOYMENT_GATES if gate > trading_day), None)
    discipline = {
        "experiment_trading_day": trading_day,
        "cash_weight": cash_weight,
        "deployed_weight": deployed_weight,
        "position_count": len(state.get("positions", [])),
        "deployment_status": status,
        "triggered_gates": triggered,
        "next_gate_trading_day": next_gate,
        "trading_days_to_next_gate": None if next_gate is None else next_gate - trading_day,
        "cumulative_decision_grade_d2_count": len(seen),
        "cumulative_decision_grade_d2_ids": seen,
        "current_decision_grade_d2_ids": sorted(current_d2),
        "current_eligible_buy_ids": eligible_buy_ids,
        "current_buy_below_ids": buy_below_ids,
        "high_cash_reason": high_cash_reason,
        "rules": {
            "day10_cash_gt_80pct": "AI_BOOK_DEPLOYMENT_REVIEW",
            "day20_min_cumulative_decision_grade_d2": DAY20_MIN_DECISION_GRADE_D2,
            "day20_deployment_target_if_eligible_buys_exist": [0.30, 0.50],
            "day30_cash_gt_70pct": "OPPORTUNITY_STARVATION_REVIEW_REQUIRED",
            "day40_cash_gt_50pct": "EXPERIMENT_INSUFFICIENT_DEPLOYMENT_POLICY_PROPOSAL_ONLY",
            "buy_below_direct_buy_authorized": False,
            "forced_buying": False,
            "policy_auto_effective": False,
        },
        "orders": 0,
        "trade_authority": TRADE_AUTHORITY,
    }
    state["deployment_discipline"] = discipline
    return discipline


def apply_ai_virtual_rebalance(
    *,
    recommendation: dict[str, Any],
    lifecycle: dict[str, Any],
    prior_state: dict[str, Any] | None,
    as_of_date: str,
    slippage_bps: float = 10.0,
) -> tuple[dict[str, Any], dict[str, Any]]:
    state = json.loads(json.dumps(prior_state)) if prior_state else initial_ai_state(as_of_date)
    if not state:
        state = initial_ai_state(as_of_date)
    if state.get("book_id") != AI_BOOK_ID:
        raise ValueError("AI_BOOK_ID_MISMATCH")
    prices = lifecycle_prices(lifecycle)
    positions = ai_position_map(state)

    prior_nav = float(state.get("cash") or 0.0)
    for sid, pos in positions.items():
        price = prices.get(sid, num(pos.get("last_price"), 0.0) or 0.0)
        pos["last_price"] = price
        pos["market_value"] = float(pos.get("quantity") or 0.0) * price
        prior_nav += pos["market_value"]
    state["current_nav"] = prior_nav

    targets = ai_target_weights(recommendation, lifecycle, state)
    sells: list[tuple[str, float]] = []
    buys: list[tuple[str, float]] = []
    diagnostics: list[dict[str, Any]] = []
    for sid, target in targets.items():
        price = prices.get(sid)
        current_qty = float(positions.get(sid, {}).get("quantity") or 0.0)
        if price is None or price <= 0:
            diagnostics.append({"security_id": sid, "status": "BLOCK_NO_PRICE"})
            continue
        target_qty = float(math.floor((target["target_weight"] * prior_nav / price) / LISTED_LOT) * LISTED_LOT)
        delta = target_qty - current_qty
        if delta < 0:
            sells.append((sid, abs(delta)))
        elif delta > 0:
            buys.append((sid, delta))

    traded_notional = 0.0
    new_transactions: list[dict[str, Any]] = []

    for sid, desired_qty in sorted(sells):
        pos = positions.get(sid)
        if not pos:
            continue
        qty = min(float(pos.get("quantity") or 0.0), desired_qty)
        if qty <= 0:
            continue
        price = prices[sid] * (1.0 - slippage_bps / 10_000.0)
        proceeds = qty * price
        avg_cost = float(pos.get("average_cost") or 0.0)
        realized = qty * (price - avg_cost)
        state["cash"] = float(state.get("cash") or 0.0) + proceeds
        state["realized_pnl"] = float(state.get("realized_pnl") or 0.0) + realized
        pos["quantity"] = float(pos.get("quantity") or 0.0) - qty
        traded_notional += proceeds
        new_transactions.append({
            "as_of_date": as_of_date,
            "security_id": sid,
            "security_name": pos.get("security_name"),
            "side": "SELL",
            "quantity": qty,
            "execution_price": price,
            "notional": proceeds,
            "realized_pnl": realized,
            "reason": "AI_TARGET_WEIGHT_REBALANCE",
        })
        if pos["quantity"] <= 1e-9:
            positions.pop(sid, None)

    recs = recommendation_map(recommendation)
    buys.sort(key=lambda x: (-targets[x[0]]["score"], x[0]))
    slippage_rate = slippage_bps / 10_000.0

    def raw_position_value(security_id: str) -> float:
        pos = positions.get(security_id)
        if not pos:
            return 0.0
        raw_price = prices.get(
            security_id,
            float(pos.get("last_price") or 0.0),
        )
        return float(pos.get("quantity") or 0.0) * raw_price

    def current_raw_nav() -> float:
        return float(state.get("cash") or 0.0) + sum(
            raw_position_value(existing_sid) for existing_sid in positions
        )

    def group_raw_value(group: str) -> float:
        total = 0.0
        for existing_sid, pos in positions.items():
            existing_group = str(
                targets.get(existing_sid, {}).get("risk_group")
                or pos.get("risk_group")
                or "UNKNOWN"
            )
            if existing_group == group:
                total += raw_position_value(existing_sid)
        return total

    for sid, desired_qty in buys:
        price_raw = prices[sid]
        price = price_raw * (1.0 + slippage_rate)
        desired_qty = math.floor(desired_qty / LISTED_LOT) * LISTED_LOT

        # Enforce portfolio limits on post-execution marked weights, not only
        # on pre-trade target weights.  Buy slippage lowers ending NAV, so a
        # nominal 10% / 30% target can otherwise finish slightly above cap.
        nav_before_buy = current_raw_nav()
        current_single_value = raw_position_value(sid)
        group = str(targets[sid]["risk_group"])
        current_group_value = group_raw_value(group)

        max_single_raw_add = max(
            0.0,
            (DEFAULT_SINGLE_NAME_CAP * nav_before_buy - current_single_value)
            / (1.0 + DEFAULT_SINGLE_NAME_CAP * slippage_rate),
        )
        max_group_raw_add = max(
            0.0,
            (DEFAULT_GROUP_CAP * nav_before_buy - current_group_value)
            / (1.0 + DEFAULT_GROUP_CAP * slippage_rate),
        )
        cap_qty = math.floor(
            min(max_single_raw_add, max_group_raw_add)
            / price_raw
            / LISTED_LOT
        ) * LISTED_LOT
        desired_after_caps = min(desired_qty, cap_qty)

        affordable_qty = math.floor(
            float(state.get("cash") or 0.0) / price / LISTED_LOT
        ) * LISTED_LOT
        qty = min(desired_after_caps, affordable_qty)
        if qty <= 0:
            reason = "BLOCK_POST_EXECUTION_CAP_OR_CASH_OR_LOT"
            diagnostics.append({
                "security_id": sid,
                "status": reason,
                "desired_quantity": desired_qty,
                "cap_quantity": cap_qty,
                "affordable_quantity": affordable_qty,
            })
            continue
        if qty < desired_qty:
            diagnostics.append({
                "security_id": sid,
                "status": "BUY_REDUCED_BY_POST_EXECUTION_CAP_OR_CASH",
                "desired_quantity": desired_qty,
                "validated_quantity": qty,
                "cap_quantity": cap_qty,
                "affordable_quantity": affordable_qty,
            })
        notional = qty * price
        state["cash"] = float(state.get("cash") or 0.0) - notional
        old = positions.get(sid)
        old_qty = float(old.get("quantity") or 0.0) if old else 0.0
        old_cost = float(old.get("average_cost") or 0.0) if old else 0.0
        new_qty = old_qty + qty
        new_cost = ((old_qty * old_cost) + notional) / new_qty
        rec = recs.get(sid, {})
        positions[sid] = {
            "security_id": sid,
            "security_name": rec.get("security_name") or (old or {}).get("security_name"),
            "quantity": new_qty,
            "average_cost": new_cost,
            "last_price": price_raw,
            "market_value": new_qty * price_raw,
            "risk_group": targets[sid]["risk_group"],
            "source_action": rec.get("action"),
        }
        traded_notional += notional
        new_transactions.append({
            "as_of_date": as_of_date,
            "security_id": sid,
            "security_name": positions[sid].get("security_name"),
            "side": "BUY",
            "quantity": qty,
            "execution_price": price,
            "notional": notional,
            "realized_pnl": 0.0,
            "reason": "AI_TARGET_WEIGHT_REBALANCE",
        })

    ending_nav = float(state.get("cash") or 0.0)
    for sid, pos in positions.items():
        price = prices.get(sid, float(pos.get("last_price") or 0.0))
        pos["last_price"] = price
        pos["market_value"] = float(pos.get("quantity") or 0.0) * price
        ending_nav += pos["market_value"]

    # Attribution weights must use the fully computed ending NAV.  Computing
    # them inside the NAV accumulation loop gives early positions a partial
    # denominator and can make reported group weights exceed 100% of actual
    # invested exposure even when the portfolio itself is within limits.
    attribution = []
    for sid, pos in positions.items():
        price = float(pos.get("last_price") or 0.0)
        attribution.append({
            "security_id": sid,
            "security_name": pos.get("security_name"),
            "market_value": pos["market_value"],
            "unrealized_pnl": float(pos.get("quantity") or 0.0) * (
                price - float(pos.get("average_cost") or 0.0)
            ),
            "weight": pos["market_value"] / ending_nav if ending_nav > 0 else 0.0,
            "risk_group": pos.get("risk_group"),
        })

    state["positions"] = sorted(positions.values(), key=lambda x: x["security_id"])
    state["transactions"] = list(state.get("transactions", [])) + new_transactions
    state["current_nav"] = ending_nav
    state["peak_nav"] = max(float(state.get("peak_nav") or AI_INITIAL_CAPITAL), ending_nav)
    current_drawdown = ending_nav / state["peak_nav"] - 1.0 if state["peak_nav"] > 0 else 0.0
    state["max_drawdown"] = min(float(state.get("max_drawdown") or 0.0), current_drawdown)
    state["cumulative_return"] = ending_nav / AI_INITIAL_CAPITAL - 1.0
    state["turnover_since_inception"] = float(state.get("turnover_since_inception") or 0.0) + (
        traded_notional / prior_nav if prior_nav > 0 else 0.0
    )
    history = list(state.get("nav_history", []))
    history.append({
        "as_of_date": as_of_date,
        "nav": ending_nav,
        "cash": state["cash"],
        "position_market_value": ending_nav - state["cash"],
    })
    by_date = {row["as_of_date"]: row for row in history}
    state["nav_history"] = [by_date[k] for k in sorted(by_date)]
    state["orders"] = 0
    state["trade_authority"] = TRADE_AUTHORITY

    discipline = update_ai_deployment_discipline(
        state=state,
        recommendation=recommendation,
        as_of_date=as_of_date,
    )

    report = {
        "book_id": AI_BOOK_ID,
        "as_of_date": as_of_date,
        "prior_nav": prior_nav,
        "current_nav": ending_nav,
        "cash": state["cash"],
        "cash_weight": state["cash"] / ending_nav if ending_nav > 0 else 0.0,
        "position_count": len(state["positions"]),
        "new_transaction_count": len(new_transactions),
        "new_transactions": new_transactions,
        "diagnostics": diagnostics,
        "deployment_discipline": discipline,
        "target_weights": targets,
        "attribution": sorted(attribution, key=lambda x: x["security_id"]),
        "performance": {
            "cumulative_return": state["cumulative_return"],
            "max_drawdown": state["max_drawdown"],
            "realized_pnl": state["realized_pnl"],
            "turnover_since_inception": state["turnover_since_inception"],
        },
        "controls": {
            "initial_capital": AI_INITIAL_CAPITAL,
            "max_positions": MAX_AI_POSITIONS,
            "single_name_cap": DEFAULT_SINGLE_NAME_CAP,
            "risk_group_cap": DEFAULT_GROUP_CAP,
            "cash_floor": AI_CASH_FLOOR,
            "buy_lot": LISTED_LOT,
            "slippage_bps": slippage_bps,
            "real_account_mutations": 0,
            "legacy_simulation_mutations": 0,
            "orders": 0,
            "trade_authority": TRADE_AUTHORITY,
        },
    }
    return state, report


def build_phase3(
    *,
    recommendation: dict[str, Any],
    lifecycle: dict[str, Any],
    real: dict[str, Any],
    simulation: dict[str, Any],
    prior_ai: dict[str, Any] | None,
    as_of_date: str,
) -> dict[str, Any]:
    real_plan = build_account_target_plan(real, recommendation, lifecycle)
    sim_plan = build_account_target_plan(simulation, recommendation, lifecycle)
    real_execution = build_execution_plan(real_plan)
    sim_execution = build_execution_plan(sim_plan)
    ai_state, ai_report = apply_ai_virtual_rebalance(
        recommendation=recommendation,
        lifecycle=lifecycle,
        prior_state=prior_ai,
        as_of_date=as_of_date,
    )
    payload = {
        "schema_version": "1.0.0",
        "phase3_id": "PORTFOLIO_EXECUTION_CURRENT_" + canonical_hash({
            "recommendation": recommendation.get("state_id"),
            "lifecycle": lifecycle.get("lifecycle_id"),
            "real_plan": real_plan,
            "simulation_plan": sim_plan,
            "ai_nav": ai_state.get("current_nav"),
            "ai_txn_count": len(ai_state.get("transactions", [])),
            "ai_deployment_discipline": ai_report.get("deployment_discipline"),
        })[:16],
        "status": "PASS_PORTFOLIO_EXECUTION_AND_AI_SIMULATION",
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "as_of_date": as_of_date,
        "real_account": {
            "target_plan": real_plan,
            "execution_validation": real_execution,
            "automatic_mutation_authorized": False,
        },
        "simulation_account": {
            "target_plan": sim_plan,
            "execution_validation": sim_execution,
            "automatic_mutation_authorized": False,
        },
        "ai_autonomous": ai_report,
        "controls": {
            "target_weight_engine": True,
            "execution_validator": True,
            "ai_autonomous_virtual_ledger": True,
            "real_account_mutations": 0,
            "legacy_simulation_mutations": 0,
            "candidate_mutations": 0,
            "risk_target_is_trade_authority": False,
            "hold_review_can_generate_trade": False,
            "orders": 0,
            "trade_authority": TRADE_AUTHORITY,
        },
        "orders": 0,
        "trade_authority": TRADE_AUTHORITY,
    }
    return {"phase3": payload, "ai_state": ai_state}


def render_markdown(phase3: dict[str, Any]) -> str:
    ai = phase3["ai_autonomous"]
    discipline = ai.get("deployment_discipline", {})
    lines = [
        "# 股票投资助手｜Portfolio + Execution + AI Autonomous CURRENT",
        "",
        f"- 数据水位：{phase3['as_of_date']}",
        "- Target Weight Engine：true",
        "- Execution Validator：true",
        f"- AI_AUTONOMOUS_1M NAV：{ai['current_nav']:.2f}",
        f"- AI现金：{ai['cash']:.2f}（{ai['cash_weight']:.1%}）",
        f"- AI持仓数：{ai['position_count']}",
        f"- AI累计收益：{ai['performance']['cumulative_return']:.2%}",
        f"- AI最大回撤：{ai['performance']['max_drawdown']:.2%}",
        f"- AI部署阶段：第 {discipline.get('experiment_trading_day', 1)} 个完整观察交易日 / {discipline.get('deployment_status', 'NORMAL_ACCUMULATION')}",
        f"- AI累计 decision-grade D2：{discipline.get('cumulative_decision_grade_d2_count', 0)}",
        (
            f"- 距下一 deployment gate：{discipline['trading_days_to_next_gate']} 个交易日"
            if discipline.get("trading_days_to_next_gate") is not None
            else "- 已进入最终 deployment gate 区间"
        ),
        f"- 高现金原因：{discipline.get('high_cash_reason') or 'N/A'}",
        "- Real / legacy Simulation 自动改仓：false",
        "- Orders：0；trade_authority：NONE",
        "",
        "## Real 当前需要关注的执行建议",
        "",
    ]
    ready = [
        x for x in phase3["real_account"]["execution_validation"]["rows"]
        if x["status"] not in {
            "NO_ACTION",
            "NO_ACTION_REVIEW_ONLY",
            "NO_ACTION_DIRECTION_BLOCKED",
            "MANUAL_FUND_EXECUTION_REVIEW",
        }
    ]
    if not ready:
        lines.append("- 当前没有需要执行验证的上市证券调仓。")
    else:
        for row in ready:
            lines.append(
                f"- {row['security_name']} ({row['security_id']}) "
                f"{row['side']} {row.get('validated_quantity', 0):g}，"
                f"状态 {row['status']}。"
            )
    lines += [
        "",
        "## AI_AUTONOMOUS_1M",
        "",
        "- 独立于真实账户和原有受保护模拟盘。",
        "- 只有该虚拟账本允许按正式 Recommendation 自主变更。",
        "- BUY_BELOW 达价不直接买入，仍需 fresh D2 后成为正式 BUY。",
        "- 10/20/30/40交易日 deployment discipline 只触发诊断/研究/Policy Proposal，不强迫买入。",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--recommendation", required=True)
    p.add_argument("--lifecycle", required=True)
    p.add_argument("--real", required=True)
    p.add_argument("--simulation", required=True)
    p.add_argument("--prior-ai")
    p.add_argument("--as-of-date", required=True)
    p.add_argument("--output-json", required=True)
    p.add_argument("--output-ai", required=True)
    p.add_argument("--output-md", required=True)
    args = p.parse_args()
    result = build_phase3(
        recommendation=load_json(Path(args.recommendation)),
        lifecycle=load_json(Path(args.lifecycle)),
        real=load_json(Path(args.real)),
        simulation=load_json(Path(args.simulation)),
        prior_ai=load_json(Path(args.prior_ai), {}) if args.prior_ai else None,
        as_of_date=args.as_of_date,
    )
    write_json(Path(args.output_json), result["phase3"])
    write_json(Path(args.output_ai), result["ai_state"])
    Path(args.output_md).write_text(render_markdown(result["phase3"]), encoding="utf-8")
    print(json.dumps({
        "phase3_id": result["phase3"]["phase3_id"],
        "as_of_date": result["phase3"]["as_of_date"],
        "ai_nav": result["ai_state"]["current_nav"],
        "ai_position_count": len(result["ai_state"]["positions"]),
        "ai_cash": result["ai_state"]["cash"],
        "orders": 0,
        "trade_authority": TRADE_AUTHORITY,
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
