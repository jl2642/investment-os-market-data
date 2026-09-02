from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TRADE_AUTHORITY = "NONE"
IMMEDIATE_ACTIONS = {"BUY", "ADD", "TRIM", "EXIT"}
POSITION_ACTIONS = {"ADD", "HOLD", "TRIM", "EXIT"}


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


def num(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_market_snapshot(path: Path | None) -> tuple[dict[str, dict[str, Any]], str | None]:
    if path is None or not path.exists() or path.stat().st_size == 0:
        return {}, None
    rows: dict[str, dict[str, Any]] = {}
    latest_date: str | None = None
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            sid = str(row.get("symbol") or row.get("security_id") or "")
            if not sid:
                continue
            close = num(row.get("close") or row.get("last") or row.get("price"))
            as_of = str(row.get("as_of_date") or row.get("date") or "")
            if close is None:
                continue
            rows[sid] = {
                "price": close,
                "as_of_date": as_of or None,
                "record_quality": row.get("record_quality"),
                "data_status": row.get("data_status"),
            }
            if as_of and (latest_date is None or as_of > latest_date):
                latest_date = as_of
    return rows, latest_date


def monitoring_maps(surface: dict[str, Any]) -> tuple[dict[str, list[dict[str, Any]]], set[str]]:
    by_sid: dict[str, list[dict[str, Any]]] = {}
    held: set[str] = set()
    for row in (surface.get("portfolio_monitoring") or {}).get("rows", []):
        sid = str(row.get("security_id") or "")
        if not sid:
            continue
        held.add(sid)
        by_sid.setdefault(sid, []).append(row)
    return by_sid, held


def prior_trigger_keys(prior: dict[str, Any]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for row in prior.get("subjects", []) if isinstance(prior, dict) else []:
        sid = str(row.get("security_id") or "")
        if sid:
            out[sid] = {
                str(x)
                for x in row.get("mechanical_trigger_keys", [])
                if str(x)
            }
    return out


def choose_price(
    sid: str,
    recommendation: dict[str, Any],
    monitoring: dict[str, list[dict[str, Any]]],
    market: dict[str, dict[str, Any]],
    market_date: str | None,
) -> tuple[float | None, str, str | None]:
    if sid in market:
        return num(market[sid].get("price")), "A_SHARE_FULL_MARKET", market[sid].get("as_of_date") or market_date
    rows = monitoring.get(sid, [])
    prices = [num(row.get("current_price")) for row in rows]
    prices = [x for x in prices if x is not None]
    if prices:
        return prices[0], "S3_PORTFOLIO_MARK", None
    price = num(recommendation.get("current_price"))
    return price, "D2_UNDERWRITING_PRICE_ONLY", None


def priority_rank(value: str) -> int:
    return {
        "CRITICAL": 0,
        "HIGH": 1,
        "MEDIUM_HIGH": 2,
        "MEDIUM": 3,
        "LOW": 4,
    }.get(value, 9)


def build(
    *,
    recommendation: dict[str, Any],
    surface: dict[str, Any],
    market_rows: dict[str, dict[str, Any]] | None = None,
    market_date: str | None = None,
    prior: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    now = now or datetime.now(timezone.utc)
    generated_at = now.replace(microsecond=0).isoformat()
    market_rows = market_rows or {}
    prior = prior or {}
    monitoring, held_ids = monitoring_maps(surface)
    prior_keys = prior_trigger_keys(prior)
    baseline = not bool(prior.get("lifecycle_id"))

    subjects: list[dict[str, Any]] = []
    review_queue: list[dict[str, Any]] = []

    for rec in sorted(recommendation.get("records", []), key=lambda x: str(x.get("security_id") or "")):
        sid = str(rec.get("security_id") or "")
        if not sid:
            continue
        name = rec.get("security_name")
        action = str(rec.get("action") or "WATCH")
        held = sid in held_ids
        rows = monitoring.get(sid, [])
        flags = sorted({str(flag) for row in rows for flag in row.get("monitoring_flags", [])})
        accounts = sorted({str(row.get("account")) for row in rows if row.get("account")})
        latest_price, price_source, price_as_of = choose_price(
            sid, rec, monitoring, market_rows, market_date
        )
        entry_price = num(rec.get("entry_price"))
        trigger_keys: list[str] = []
        review_reasons: list[dict[str, Any]] = []

        if held and action in {"TRIM", "EXIT"}:
            key = f"POSITION_ACTION_{action}"
            trigger_keys.append(key)
            review_reasons.append({
                "type": "USER_ACTION_REVIEW",
                "key": key,
                "priority": "HIGH",
                "reason": f"Current decision-grade holding action is {action}.",
                "next_step": "PORTFOLIO_AND_EXECUTION_VALIDATION",
            })
        elif held and action == "ADD":
            key = "POSITION_ACTION_ADD"
            trigger_keys.append(key)
            review_reasons.append({
                "type": "USER_ACTION_REVIEW",
                "key": key,
                "priority": "MEDIUM_HIGH",
                "reason": "Current decision-grade holding action is ADD.",
                "next_step": "PORTFOLIO_AND_EXECUTION_VALIDATION",
            })
        elif not held and action == "BUY":
            key = "NEW_CAPITAL_ACTION_BUY"
            trigger_keys.append(key)
            review_reasons.append({
                "type": "USER_ACTION_REVIEW",
                "key": key,
                "priority": "HIGH",
                "reason": "Current decision-grade new-capital action is BUY.",
                "next_step": "PORTFOLIO_AND_EXECUTION_VALIDATION",
            })

        price_trigger = False
        if latest_price is not None and entry_price is not None:
            if action == "BUY_BELOW" and not held and latest_price <= entry_price:
                price_trigger = True
                key = "BUY_BELOW_PRICE_CONDITION_MET"
                trigger_keys.append(key)
                review_reasons.append({
                    "type": "REUNDERWRITE_REQUIRED",
                    "key": key,
                    "priority": "HIGH",
                    "reason": f"Latest price {latest_price:.4f} is at/below entry threshold {entry_price:.4f}.",
                    "next_step": "FRESH_D2_BEFORE_ANY_BUY",
                })
            elif held and action == "HOLD" and rec.get("top_blocker") == "PRICE_BLOCKED" and latest_price <= entry_price:
                price_trigger = True
                key = "HOLD_PRICE_REOPEN_CONDITION_MET"
                trigger_keys.append(key)
                review_reasons.append({
                    "type": "REUNDERWRITE_REQUIRED",
                    "key": key,
                    "priority": "MEDIUM_HIGH",
                    "reason": f"Holding price {latest_price:.4f} is at/below research entry threshold {entry_price:.4f}.",
                    "next_step": "FRESH_D2_AND_PORTFOLIO_FIT_BEFORE_ADD",
                })

        if "ACCOUNT_WEIGHT_GE_15PCT" in flags:
            key = "PORTFOLIO_CONCENTRATION_ACTIVE"
            trigger_keys.append(key)
            review_reasons.append({
                "type": "PORTFOLIO_REVIEW_REQUIRED",
                "key": key,
                "priority": "HIGH",
                "reason": "Current account weight is at/above the governed 15% concentration flag.",
                "next_step": "PHASE3_TARGET_WEIGHT_AND_SIZING_REVIEW",
            })

        if "DRAWDOWN_GE_15PCT" in flags:
            key = "DRAWDOWN_MONITOR_ACTIVE"
            trigger_keys.append(key)
            # Drawdown is already reflected in a current D2 thesis.  It remains
            # a lifecycle state but does not mechanically force repeated D2.
            review_reasons.append({
                "type": "RISK_MONITOR",
                "key": key,
                "priority": "MEDIUM",
                "reason": "Current unrealized drawdown is at/above 15%; loss alone is not an exit trigger.",
                "next_step": "REUNDERWRITE_ONLY_ON_NEW_EVIDENCE_OR_PRICE_REOPEN",
            })

        current_set = set(trigger_keys)
        prior_set = prior_keys.get(sid, set())
        new_keys = sorted(current_set - prior_set) if not baseline else []
        cleared_keys = sorted(prior_set - current_set) if not baseline else []

        for reason in review_reasons:
            include = reason["type"] in {"USER_ACTION_REVIEW", "REUNDERWRITE_REQUIRED", "PORTFOLIO_REVIEW_REQUIRED"}
            if include:
                review_queue.append({
                    "security_id": sid,
                    "security_name": name,
                    "accounts": accounts,
                    "current_action": action,
                    "review_type": reason["type"],
                    "trigger_key": reason["key"],
                    "priority": reason["priority"],
                    "reason": reason["reason"],
                    "next_step": reason["next_step"],
                    "latest_price": latest_price,
                    "entry_price": entry_price,
                    "price_source": price_source,
                    "price_as_of": price_as_of,
                    "transition": "BASELINE_ACTIVE" if baseline else ("NEW_TRIGGER" if reason["key"] in new_keys else "PERSISTING"),
                    "orders": 0,
                    "trade_authority": TRADE_AUTHORITY,
                })

        if held:
            if action in {"TRIM", "EXIT", "ADD"}:
                lifecycle_state = f"HELD_{action}_REVIEW"
            elif "PORTFOLIO_CONCENTRATION_ACTIVE" in current_set:
                lifecycle_state = "HELD_CONCENTRATION_REVIEW"
            elif price_trigger:
                lifecycle_state = "HELD_PRICE_REUNDERWRITE"
            elif "DRAWDOWN_MONITOR_ACTIVE" in current_set:
                lifecycle_state = "HELD_HOLD_DRAWDOWN_MONITOR"
            else:
                lifecycle_state = "HELD_HOLD"
        else:
            if action == "BUY":
                lifecycle_state = "FLAT_BUY_REVIEW"
            elif action == "BUY_BELOW":
                lifecycle_state = "FLAT_PRICE_REUNDERWRITE" if price_trigger else "FLAT_WAIT_BUY_BELOW"
            elif action == "AVOID":
                lifecycle_state = "FLAT_AVOID"
            else:
                lifecycle_state = f"FLAT_{action or 'WATCH'}"

        subjects.append({
            "security_id": sid,
            "security_name": name,
            "accounts": accounts,
            "position_state": "HELD" if held else "FLAT",
            "current_action": action,
            "lifecycle_state": lifecycle_state,
            "latest_price": latest_price,
            "price_source": price_source,
            "price_as_of": price_as_of,
            "entry_price": entry_price,
            "expected_return": num(rec.get("expected_return")),
            "top_blocker": rec.get("top_blocker"),
            "ready_for_user_decision": bool(rec.get("ready_for_user_decision")),
            "monitoring_flags": flags,
            "mechanical_trigger_keys": sorted(current_set),
            "new_trigger_keys": new_keys,
            "cleared_trigger_keys": cleared_keys,
            "semantic_watch": {
                "catalysts": rec.get("catalysts") or [],
                "kill_thesis": rec.get("kill_thesis") or [],
                "automatic_keyword_inference_authorized": False,
                "semantic_reunderwrite_required_before_state_change": True,
            },
            "orders": 0,
            "trade_authority": TRADE_AUTHORITY,
        })

    review_queue.sort(key=lambda x: (priority_rank(x["priority"]), x["security_id"], x["trigger_key"]))
    input_identity = {
        "recommendation_state_id": recommendation.get("state_id"),
        "recommendation_generated_at_utc": recommendation.get("generated_at_utc"),
        "surface_id": surface.get("surface_id"),
        "surface_as_of_date": surface.get("as_of_date"),
        "market_date": market_date,
    }
    lifecycle_id = "DECISION_LIFECYCLE_CURRENT_" + canonical_hash({
        "inputs": input_identity,
        "subjects": [
            {
                "security_id": row["security_id"],
                "action": row["current_action"],
                "state": row["lifecycle_state"],
                "price": row["latest_price"],
                "triggers": row["mechanical_trigger_keys"],
            }
            for row in subjects
        ],
    })[:16]

    payload = {
        "schema_version": "1.0.0",
        "lifecycle_id": lifecycle_id,
        "status": "PASS_DECISION_LIFECYCLE",
        "generated_at_utc": generated_at,
        "as_of_date": max(
            [x for x in [market_date, str(surface.get("as_of_date") or "")] if x],
            default=str(surface.get("as_of_date") or ""),
        ),
        "baseline_mode": baseline,
        "input_identity": input_identity,
        "summary": {
            "subject_count": len(subjects),
            "held_subject_count": sum(x["position_state"] == "HELD" for x in subjects),
            "flat_subject_count": sum(x["position_state"] == "FLAT" for x in subjects),
            "review_queue_count": len(review_queue),
            "reunderwrite_required_count": sum(x["review_type"] == "REUNDERWRITE_REQUIRED" for x in review_queue),
            "user_action_review_count": sum(x["review_type"] == "USER_ACTION_REVIEW" for x in review_queue),
            "portfolio_review_required_count": sum(x["review_type"] == "PORTFOLIO_REVIEW_REQUIRED" for x in review_queue),
            "semantic_watch_clause_count": sum(
                len(x["semantic_watch"]["catalysts"]) + len(x["semantic_watch"]["kill_thesis"])
                for x in subjects
            ),
            "automatic_semantic_trigger_count": 0,
        },
        "subjects": subjects,
        "controls": {
            "automatic_buy_sell": False,
            "automatic_position_mutation": False,
            "automatic_semantic_keyword_inference": False,
            "fresh_d2_required_after_price_trigger": True,
            "candidate_membership_mutations": 0,
            "real_account_mutations": 0,
            "simulation_mutations": 0,
            "orders": 0,
            "trade_authority": TRADE_AUTHORITY,
        },
        "orders": 0,
        "trade_authority": TRADE_AUTHORITY,
    }
    queue_payload = {
        "schema_version": "1.0.0",
        "queue_id": "TRIGGER_REVIEW_QUEUE_" + canonical_hash(review_queue)[:16],
        "source_lifecycle_id": lifecycle_id,
        "generated_at_utc": generated_at,
        "as_of_date": payload["as_of_date"],
        "review_count": len(review_queue),
        "records": review_queue,
        "orders": 0,
        "trade_authority": TRADE_AUTHORITY,
    }
    return payload, queue_payload


def render_markdown(lifecycle: dict[str, Any], queue: dict[str, Any]) -> str:
    s = lifecycle["summary"]
    lines = [
        "# 股票投资助手｜Decision Lifecycle Watch CURRENT",
        "",
        f"- 数据水位：`{lifecycle['as_of_date']}`",
        f"- Thesis subjects：`{s['subject_count']}`",
        f"- 持仓 / 非持仓：`{s['held_subject_count']} / {s['flat_subject_count']}`",
        f"- 当前复核队列：`{s['review_queue_count']}`",
        f"- 需要重新D2：`{s['reunderwrite_required_count']}`",
        f"- 需要用户动作复核：`{s['user_action_review_count']}`",
        f"- 组合风险复核：`{s['portfolio_review_required_count']}`",
        "- 自动交易：`false`；Orders：`0`；trade_authority：`NONE`",
        "",
        "## 当前复核队列",
        "",
    ]
    if not queue["records"]:
        lines.append("- 当前没有机械触发的复核事项。")
    else:
        for row in queue["records"]:
            lines.append(
                f"- **{row['security_name']} ({row['security_id']})** — "
                f"`{row['review_type']}` / `{row['priority']}`：{row['reason']} "
                f"下一步：`{row['next_step']}`。"
            )
    lines += [
        "",
        "## 语义触发边界",
        "",
        "- Catalyst / kill-thesis 只登记监控条款；GitHub 不做关键词推断。",
        "- 价格条件命中只会要求重新D2；不得直接转换成BUY/ADD。",
        "- 浮亏本身不是卖出条件；TRIM/EXIT 必须来自当前 decision-grade Recommendation。",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--recommendation", required=True)
    p.add_argument("--surface", required=True)
    p.add_argument("--market-snapshot")
    p.add_argument("--market-date")
    p.add_argument("--prior")
    p.add_argument("--output-json", required=True)
    p.add_argument("--output-queue", required=True)
    p.add_argument("--output-md", required=True)
    args = p.parse_args()

    recommendation = load_json(Path(args.recommendation))
    surface = load_json(Path(args.surface))
    market_rows, detected_date = load_market_snapshot(Path(args.market_snapshot) if args.market_snapshot else None)
    prior = load_json(Path(args.prior), {}) if args.prior else {}
    lifecycle, queue = build(
        recommendation=recommendation,
        surface=surface,
        market_rows=market_rows,
        market_date=args.market_date or detected_date,
        prior=prior,
    )
    write_json(Path(args.output_json), lifecycle)
    write_json(Path(args.output_queue), queue)
    Path(args.output_md).write_text(render_markdown(lifecycle, queue), encoding="utf-8")
    print(json.dumps({
        "lifecycle_id": lifecycle["lifecycle_id"],
        "as_of_date": lifecycle["as_of_date"],
        **lifecycle["summary"],
        "orders": 0,
        "trade_authority": TRADE_AUTHORITY,
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
