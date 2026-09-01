#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

TRADE_AUTHORITY = "NONE"
ACTION_ORDER = {
    "EXIT": 0,
    "TRIM": 1,
    "ADD": 2,
    "HOLD": 3,
    "BUY": 4,
    "BUY_BELOW": 5,
    "WATCH_FOR_EVIDENCE": 6,
    "WATCH": 7,
    "AVOID": 8,
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def walk_safety_values(
    value: Any, trade_authorities: list[Any], orders: list[Any]
) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "trade_authority":
                trade_authorities.append(item)
            if key == "orders":
                orders.append(item)
            walk_safety_values(item, trade_authorities, orders)
    elif isinstance(value, list):
        for item in value:
            walk_safety_values(item, trade_authorities, orders)


def assert_safe(label: str, payload: Any) -> None:
    authorities: list[Any] = []
    order_values: list[Any] = []
    walk_safety_values(payload, authorities, order_values)
    if authorities and set(authorities) != {TRADE_AUTHORITY}:
        raise ValueError(
            f"{label}_TRADE_AUTHORITY_VIOLATION:{authorities}"
        )
    if any(value not in {0, None} for value in order_values):
        raise ValueError(f"{label}_ORDER_AUTHORITY_VIOLATION:{order_values}")


def holding_map(payload: dict[str, Any], account: str) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for row in payload.get("holdings", []) or []:
        sid = str(row.get("security_id") or "").strip()
        if not sid:
            continue
        rows[sid] = {
            "security_id": sid,
            "security_name": row.get("security_name"),
            "account": account,
        }
    return rows


def mark_map(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("security_id")): row
        for row in payload.get("marks", []) or []
        if row.get("security_id")
    }


def _fmt_pct(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{value:.1%}"
    return "—"


def _fmt_price(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{value:.2f}"
    return "—"


def build_surface(
    *,
    marks_domain: dict[str, Any],
    investment_domain: dict[str, Any],
    marks: dict[str, Any],
    real_positions: dict[str, Any],
    simulation_positions: dict[str, Any],
    recommendation: dict[str, Any],
    d1: dict[str, Any],
) -> dict[str, Any]:
    for label, payload in {
        "marks_domain": marks_domain,
        "investment_domain": investment_domain,
        "marks": marks,
        "real_positions": real_positions,
        "simulation_positions": simulation_positions,
        "recommendation": recommendation,
        "d1": d1,
    }.items():
        assert_safe(label, payload)

    if marks_domain.get("status") != "PASS":
        raise ValueError("PORTFOLIO_MARKS_DOMAIN_NOT_PASS")
    if investment_domain.get("status") != "PASS":
        raise ValueError("S2_INVESTMENT_PIPELINE_DOMAIN_NOT_PASS")
    if recommendation.get("status") != "PASS_S2_RECOMMENDATION":
        raise ValueError("S2_RECOMMENDATION_NOT_CURRENT")
    if d1.get("status") != "D1_FAST_TRIAGE_COMPLETE":
        raise ValueError("S2_D1_NOT_CURRENT")

    mark_date = str((marks.get("data_watermark") or {}).get("latest_mark_date") or "")
    if not mark_date:
        mark_date = str(marks_domain.get("data_watermark") or "")
    if not mark_date:
        raise ValueError("PORTFOLIO_MARK_DATE_MISSING")

    real = holding_map(real_positions, "REAL")
    simulation = holding_map(simulation_positions, "SIMULATION")
    marks_by_id = mark_map(marks)
    portfolio_ids = set(real) | set(simulation)

    portfolio_rows: list[dict[str, Any]] = []
    opportunity_rows: list[dict[str, Any]] = []
    covered: set[str] = set()

    for rec in recommendation.get("records", []) or []:
        sid = str(rec.get("security_id") or "").strip()
        if not sid:
            continue
        accounts = [name for name, book in (("REAL", real), ("SIMULATION", simulation)) if sid in book]
        base = real.get(sid) or simulation.get(sid) or {}
        row = {
            "security_id": sid,
            "security_name": rec.get("security_name") or base.get("security_name"),
            "accounts": accounts,
            "action": rec.get("action"),
            "ready_for_user_decision": bool(rec.get("ready_for_user_decision")),
            "current_price": rec.get("current_price"),
            "entry_price": rec.get("entry_price"),
            "expected_return": rec.get("expected_return"),
            "bear_downside": rec.get("bear_downside"),
            "confidence": rec.get("confidence"),
            "top_blocker": rec.get("top_blocker"),
            "kill_thesis": rec.get("kill_thesis"),
            "catalysts": rec.get("catalysts") or [],
            "orders": 0,
            "trade_authority": TRADE_AUTHORITY,
        }
        if accounts:
            covered.add(sid)
            portfolio_rows.append(row)
        else:
            opportunity_rows.append(row)

    uncovered = []
    for sid in sorted(portfolio_ids - covered):
        mark = marks_by_id.get(sid, {})
        base = real.get(sid) or simulation.get(sid) or {}
        accounts = [name for name, book in (("REAL", real), ("SIMULATION", simulation)) if sid in book]
        uncovered.append(
            {
                "security_id": sid,
                "security_name": base.get("security_name"),
                "accounts": accounts,
                "action": "NO_CURRENT_S2_RECOMMENDATION",
                "current_price": mark.get("mark_price") or mark.get("price"),
                "ready_for_user_decision": False,
                "top_blocker": "NO_CURRENT_D2_UNDERWRITING_OR_RECOMMENDATION",
                "orders": 0,
                "trade_authority": TRADE_AUTHORITY,
            }
        )

    portfolio_rows.sort(key=lambda row: (ACTION_ORDER.get(str(row.get("action")), 99), str(row.get("security_id"))))
    opportunity_rows.sort(key=lambda row: (ACTION_ORDER.get(str(row.get("action")), 99), str(row.get("security_id"))))

    research_rows = []
    for row in d1.get("research_objects", []) or []:
        research_rows.append(
            {
                "security_id": row.get("security_id"),
                "security_name": row.get("security_name"),
                "d1_rank": row.get("d1_rank"),
                "d1_disposition": row.get("d1_disposition"),
                "research_priority": row.get("research_priority"),
                "d2_questions": row.get("d2_questions") or [],
            }
        )

    review_count = sum(bool(row.get("ready_for_user_decision")) for row in portfolio_rows + opportunity_rows)
    action_counts: dict[str, int] = {}
    for row in portfolio_rows + opportunity_rows:
        action = str(row.get("action") or "UNKNOWN")
        action_counts[action] = action_counts.get(action, 0) + 1

    identity_payload = {
        "mark_date": mark_date,
        "marks_source": marks_domain.get("source_commit_sha"),
        "investment_source": investment_domain.get("source_commit_sha"),
        "recommendation_state_id": recommendation.get("state_id"),
        "d1_state_id": d1.get("state_id"),
        "portfolio_ids": sorted(portfolio_ids),
    }
    digest = hashlib.sha256(
        json.dumps(identity_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    return {
        "schema_version": "1.0.0",
        "surface_id": f"S3_PORTFOLIO_PRODUCT_SURFACE_{digest[:16]}",
        "status": "PASS_S3_PORTFOLIO_PRODUCT_SURFACE",
        "as_of_date": mark_date,
        "source_bindings": {
            "portfolio_marks": {
                "domain": "PORTFOLIO_MARKS",
                "watermark": marks_domain.get("data_watermark"),
                "source_commit": marks_domain.get("source_commit_sha"),
            },
            "investment_pipeline": {
                "domain": "INVESTMENT_PIPELINE",
                "watermark": investment_domain.get("data_watermark"),
                "source_commit": investment_domain.get("source_commit_sha"),
                "recommendation_state_id": recommendation.get("state_id"),
                "d1_state_id": d1.get("state_id"),
            },
        },
        "executive": {
            "portfolio_holding_count": len(portfolio_ids),
            "portfolio_recommendation_coverage_count": len(covered),
            "portfolio_uncovered_count": len(uncovered),
            "new_opportunity_count": len(opportunity_rows),
            "decision_review_required_count": review_count,
            "action_counts": action_counts,
            "implementation_ready": False,
            "automatic_rebalance_allowed": False,
            "automatic_position_change_allowed": False,
        },
        "portfolio_decisions": portfolio_rows,
        "portfolio_uncovered": uncovered,
        "new_opportunities": opportunity_rows,
        "research_queue": {
            "batch_size": d1.get("batch_size", 0),
            "routing_summary": d1.get("routing_summary") or {},
            "rows": research_rows,
        },
        "product_surface": {
            "canonical_user_products": [
                "DAILY_INVESTMENT_BRIEF",
                "PORTFOLIO_DECISION_SURFACE",
            ],
            "legacy_r3_r4_wp5_products_are_current": False,
            "legacy_products_role": "HISTORICAL_DEVELOPMENT_EVIDENCE_ONLY",
            "next_human_step": (
                "REVIEW_DECISION_READY_ITEMS"
                if review_count
                else "NO_DECISION_READY_ITEM_CONTINUE_RESEARCH_AND_MONITORING"
            ),
        },
        "controls": {
            "candidate_membership_mutations": 0,
            "real_account_mutations": 0,
            "simulation_mutations": 0,
            "target_portfolio_writebacks": 0,
            "user_decisions_generated": 0,
            "orders": 0,
            "trade_authority": TRADE_AUTHORITY,
        },
        "orders": 0,
        "trade_authority": TRADE_AUTHORITY,
    }


def render_daily_brief(surface: dict[str, Any]) -> str:
    executive = surface["executive"]
    lines = [
        "# 股票投资助手｜Daily Investment Brief",
        "",
        f"- 数据日期：{surface['as_of_date']}",
        f"- 当前需人工复核的决策项：{executive['decision_review_required_count']}",
        f"- 当前持仓覆盖：{executive['portfolio_recommendation_coverage_count']} / {executive['portfolio_holding_count']}",
        f"- 新机会：{executive['new_opportunity_count']}",
        "- 自动交易：关闭；orders = 0；trade_authority = NONE",
        "",
        "## 1. 当前持仓决策面",
    ]
    if surface["portfolio_decisions"]:
        lines += ["", "| 标的 | 账户 | 动作 | 当前价 | 预期收益 | 关键阻断 |", "|---|---|---|---:|---:|---|"]
        for row in surface["portfolio_decisions"]:
            lines.append(
                f"| {row.get('security_id')} {row.get('security_name') or ''} | "
                f"{'/'.join(row.get('accounts') or [])} | {row.get('action')} | "
                f"{_fmt_price(row.get('current_price'))} | {_fmt_pct(row.get('expected_return'))} | "
                f"{row.get('top_blocker') or '—'} |"
            )
    else:
        lines.append("")
        lines.append("当前没有被 S2 Recommendation 覆盖的持仓决策项。")

    if surface["portfolio_uncovered"]:
        lines += ["", "### 未覆盖持仓", ""]
        for row in surface["portfolio_uncovered"]:
            lines.append(
                f"- {row['security_id']} {row.get('security_name') or ''}："
                "暂无当前 S2 underwriting / recommendation，不生成动作。"
            )

    lines += ["", "## 2. 新资本机会", ""]
    if surface["new_opportunities"]:
        for row in surface["new_opportunities"]:
            lines.append(
                f"- {row.get('action')}｜{row.get('security_id')} {row.get('security_name') or ''}"
                f"｜当前价 {_fmt_price(row.get('current_price'))}"
                f"｜预期收益 {_fmt_pct(row.get('expected_return'))}"
                f"｜阻断 {row.get('top_blocker') or '无'}"
            )
    else:
        lines.append("- 当前没有新的 S2 推荐机会。")

    rq = surface["research_queue"]
    lines += [
        "",
        "## 3. 研究队列",
        "",
        f"- D1 本轮：{rq.get('batch_size', 0)} 只；进入 D2：{(rq.get('routing_summary') or {}).get('advance_to_d2_count', 0)} 只。",
    ]
    for row in (rq.get("rows") or [])[:10]:
        lines.append(
            f"- {row.get('d1_rank')}. {row.get('security_id')} {row.get('security_name') or ''}｜{row.get('d1_disposition')}"
        )

    lines += [
        "",
        "## 4. 决策边界",
        "",
        "- 本简报只整合当前持仓身份、Portfolio Marks、S2 D1/D2/Recommendation。",
        "- 旧 R3/R4/WP5 决策包不再作为当前产品入口，只保留历史追溯价值。",
        "- ready_for_user_decision 只表示值得人工复核，不表示已授权执行。",
        "- 任何真实/模拟持仓变化仍需显式用户决策；系统不下单、不自动调仓。",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--marks-domain", required=True)
    parser.add_argument("--investment-domain", required=True)
    parser.add_argument("--marks", required=True)
    parser.add_argument("--real-positions", required=True)
    parser.add_argument("--simulation-positions", required=True)
    parser.add_argument("--recommendation", required=True)
    parser.add_argument("--d1", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()

    surface = build_surface(
        marks_domain=read_json(Path(args.marks_domain)),
        investment_domain=read_json(Path(args.investment_domain)),
        marks=read_json(Path(args.marks)),
        real_positions=read_json(Path(args.real_positions)),
        simulation_positions=read_json(Path(args.simulation_positions)),
        recommendation=read_json(Path(args.recommendation)),
        d1=read_json(Path(args.d1)),
    )
    write_json(Path(args.output_json), surface)
    out_md = Path(args.output_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render_daily_brief(surface), encoding="utf-8")
    print(json.dumps({
        "status": surface["status"],
        "as_of_date": surface["as_of_date"],
        "decision_review_required_count": surface["executive"]["decision_review_required_count"],
        "orders": 0,
        "trade_authority": TRADE_AUTHORITY,
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
