from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

TRADE_AUTHORITY = "NONE"
AUTHORIZED_POSITION_ACTIONS = {"TRIM", "EXIT", "ADD"}
DEPLOYMENT_GATES = (10, 20, 30, 40)


def load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def dump(path: str, payload: dict) -> None:
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def trading_day_age(ai: dict, as_of_date: str) -> int:
    # NAV history is the authoritative AI-book observation clock. Same-date reruns do not age the experiment.
    dates = sorted({str(x.get("as_of_date")) for x in ai.get("nav_history", []) if x.get("as_of_date")})
    if as_of_date not in dates:
        dates.append(as_of_date)
        dates.sort()
    return max(1, len(dates))


def repair_account(account: dict) -> list[dict]:
    plan_rows = {str(x.get("security_id")): x for x in account.get("target_plan", {}).get("rows", [])}
    repairs = []
    for row in account.get("execution_validation", {}).get("rows", []):
        sid = str(row.get("security_id") or "")
        plan = plan_rows.get(sid, {})
        action = str(plan.get("action") or "")
        side = str(row.get("side") or "")
        # A risk cap may diagnose a weight gap, but cannot manufacture a protected-account trade.
        if side in {"BUY", "SELL"} and action not in AUTHORIZED_POSITION_ACTIONS:
            current_weight = float(row.get("current_weight") or plan.get("current_weight") or 0.0)
            current_qty = float(row.get("current_quantity") or plan.get("current_quantity") or 0.0)
            plan["target_weight"] = current_weight
            reasons = list(plan.get("target_weight_reasons") or [])
            reasons = [r for r in reasons if not str(r).startswith(("SINGLE_NAME_CAP_", "RISK_GROUP_CAP_", "TOTAL_WEIGHT_"))]
            reasons.append("RISK_REVIEW_DIAGNOSTIC_ONLY_NO_POSITION_ACTION_AUTHORITY")
            plan["target_weight_reasons"] = list(dict.fromkeys(reasons))
            row.update({
                "target_weight": current_weight,
                "target_quantity": current_qty,
                "validated_quantity": 0,
                "estimated_notional": 0.0,
                "side": "HOLD",
                "status": "NO_ACTION_REVIEW_ONLY",
                "reason": "CURRENT_RECOMMENDATION_DOES_NOT_AUTHORIZE_POSITION_CHANGE",
                "orders": 0,
                "trade_authority": TRADE_AUTHORITY,
            })
            repairs.append({"security_id": sid, "action": action, "repair": "SUPPRESS_UNAUTHORIZED_POSITION_CHANGE"})
    return repairs


def deployment_discipline(ai: dict, phase3_ai: dict, as_of_date: str) -> dict:
    age = trading_day_age(ai, as_of_date)
    nav = float(ai.get("current_nav") or ai.get("initial_capital") or 1_000_000.0)
    cash = float(ai.get("cash") or 0.0)
    cash_weight = cash / nav if nav > 0 else 1.0
    positions = len(ai.get("positions", []))
    next_gate = next((g for g in DEPLOYMENT_GATES if age < g), None)
    triggered = []
    status = "NORMAL_ACCUMULATION"
    if age >= 40 and cash_weight > 0.50:
        triggered.append("EXPERIMENT_INSUFFICIENT_DEPLOYMENT")
        status = "POLICY_PROPOSAL_REVIEW_REQUIRED"
    elif age >= 30 and cash_weight > 0.70:
        triggered.append("OPPORTUNITY_STARVATION_REVIEW_REQUIRED")
        status = "OPPORTUNITY_RESEARCH_REVIEW_REQUIRED"
    elif age >= 20 and cash_weight > 0.50:
        triggered.append("DAY20_DEPLOYMENT_REVIEW")
        status = "DECISION_GRADE_D2_AND_ELIGIBLE_BUY_REVIEW"
    elif age >= 10 and cash_weight > 0.80:
        triggered.append("AI_BOOK_DEPLOYMENT_REVIEW")
        status = "THROUGHPUT_AND_GATE_REVIEW"
    reason = "DECISION_GRADE_BUY_NOT_CURRENTLY_AVAILABLE" if positions == 0 and cash_weight > 0.99 else "PORTFOLIO_CONSTRAINTS_AND_CURRENT_RECOMMENDATIONS"
    discipline = {
        "experiment_trading_day": age,
        "cash_weight": cash_weight,
        "position_count": positions,
        "deployment_status": status,
        "triggered_gates": triggered,
        "next_gate_trading_day": next_gate,
        "trading_days_to_next_gate": None if next_gate is None else max(0, next_gate - age),
        "high_cash_reason": reason if cash_weight > 0.70 else None,
        "rules": {
            "day10_cash_gt_80pct": "AI_BOOK_DEPLOYMENT_REVIEW",
            "day20": "AT_LEAST_5_DECISION_GRADE_D2_TARGET_AND_30_TO_50PCT_DEPLOYMENT_IF_ELIGIBLE_BUYS_EXIST",
            "day30_cash_gt_70pct": "OPPORTUNITY_STARVATION_REVIEW_REQUIRED",
            "day40_cash_gt_50pct": "EXPERIMENT_INSUFFICIENT_DEPLOYMENT_POLICY_PROPOSAL_ONLY",
            "forced_buying": False,
            "policy_auto_effective": False,
        },
        "orders": 0,
        "trade_authority": TRADE_AUTHORITY,
    }
    ai["deployment_discipline"] = discipline
    phase3_ai["deployment_discipline"] = discipline
    return discipline


def render_brief(phase3: dict, original: str) -> str:
    ai = phase3["ai_autonomous"]
    d = ai.get("deployment_discipline", {})
    ready = [x for x in phase3["real_account"]["execution_validation"]["rows"] if x.get("status") not in {"NO_ACTION", "NO_ACTION_REVIEW_ONLY", "MANUAL_FUND_EXECUTION_REVIEW"}]
    lines = [
        "# 股票投资助手｜Portfolio + Execution + AI Autonomous CURRENT",
        "",
        f"- 数据水位：{phase3['as_of_date']}",
        "- Target Weight Engine：true（风险目标与动作授权已分离）",
        "- Execution Validator：true",
        f"- AI_AUTONOMOUS_1M NAV：{ai['current_nav']:.2f}",
        f"- AI现金：{ai['cash']:.2f}（{ai['cash_weight']:.1%}）",
        f"- AI持仓数：{ai['position_count']}",
        f"- AI累计收益：{ai['performance']['cumulative_return']:.2%}",
        f"- AI部署阶段：第 {d.get('experiment_trading_day')} 个完整观察交易日 / {d.get('deployment_status')}",
        f"- 距下一 deployment gate：{d.get('trading_days_to_next_gate')} 个交易日" if d.get("trading_days_to_next_gate") is not None else "- 已进入最终 deployment gate 区间",
        f"- 高现金原因：{d.get('high_cash_reason') or 'N/A'}",
        "- Real / legacy Simulation 自动改仓：false",
        "- Orders：0；trade_authority：NONE",
        "",
        "## Real 当前需要关注的执行建议",
        "",
    ]
    if ready:
        for row in ready:
            lines.append(f"- {row['security_name']} ({row['security_id']}) {row['side']} {row.get('validated_quantity', 0):g}，状态 {row['status']}。")
    else:
        lines.append("- 当前没有获得正式动作授权的上市证券调仓。")
    lines += [
        "",
        "## 动作授权边界",
        "",
        "- HOLD + concentration/drawdown/valuation/risk review 只形成复核，不得由机械风险上限转换成 BUY/SELL。",
        "- 只有当前正式 ADD/TRIM/EXIT Recommendation 才可进入 protected-account execution validation；仍需用户决策且不下单。",
        "",
        "## AI_AUTONOMOUS_1M",
        "",
        "- 独立于真实账户和原有受保护模拟盘；只有 AI virtual ledger 可按正式规则自行变更。",
        "- 10/20/30/40交易日 deployment discipline 只触发诊断/研究/Policy Proposal，不以仓位率强迫买入。",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--phase3", required=True)
    p.add_argument("--ai", required=True)
    p.add_argument("--brief", required=True)
    p.add_argument("--as-of-date", required=True)
    args = p.parse_args()
    phase3 = load(args.phase3)
    ai = load(args.ai)
    repairs = repair_account(phase3["real_account"]) + repair_account(phase3["simulation_account"])
    phase3["authorization_boundary_repairs"] = repairs
    discipline = deployment_discipline(ai, phase3["ai_autonomous"], args.as_of_date)
    phase3["controls"]["risk_target_is_trade_authority"] = False
    phase3["controls"]["hold_review_can_generate_trade"] = False
    phase3["orders"] = 0
    phase3["trade_authority"] = TRADE_AUTHORITY
    dump(args.phase3, phase3)
    dump(args.ai, ai)
    Path(args.brief).write_text(render_brief(phase3, Path(args.brief).read_text(encoding="utf-8")), encoding="utf-8")
    print(json.dumps({"repairs": repairs, "deployment_discipline": discipline, "orders": 0, "trade_authority": TRADE_AUTHORITY}, ensure_ascii=False))


if __name__ == "__main__":
    main()
