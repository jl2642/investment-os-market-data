from __future__ import annotations

import json
import re
from pathlib import Path


def money(value: float) -> str:
    amount = float(value)
    if amount < 0:
        return f"-¥{abs(amount):,.2f}"
    return f"¥{amount:,.2f}"


def replace_section(text: str, heading: str, next_heading: str, body: str) -> str:
    pattern = re.compile(
        rf"(?ms)^{re.escape(heading)}\n.*?(?=^{re.escape(next_heading)}\n)"
    )
    replacement = heading + "\n\n" + body.rstrip() + "\n\n"
    if not pattern.search(text):
        raise ValueError(f"section not found: {heading}")
    return pattern.sub(replacement, text, count=1)


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    report_path = root / "investment_os_runtime/70_ATTRIBUTION_AND_CALIBRATION/R5_ATTRIBUTION_AND_CALIBRATION_REPORT_CURRENT.md"
    portfolio_path = root / "investment_os_runtime/70_ATTRIBUTION_AND_CALIBRATION/R5_PORTFOLIO_ATTRIBUTION_CURRENT.json"
    calibration_path = root / "investment_os_runtime/70_ATTRIBUTION_AND_CALIBRATION/R5_RULE_CALIBRATION_PROPOSALS_CURRENT.json"

    report = report_path.read_text(encoding="utf-8")
    portfolio = json.loads(portfolio_path.read_text(encoding="utf-8"))
    calibration = json.loads(calibration_path.read_text(encoding="utf-8"))

    real_negative = sorted(
        (
            row
            for row in portfolio["real_account"]["security_contribution"]
            if float(row["unrealized_pnl_rmb"]) < 0
        ),
        key=lambda row: float(row["unrealized_pnl_rmb"]),
    )
    if not real_negative:
        real_body = "- 当前没有负贡献持仓。"
    else:
        real_body = "\n".join(
            f"- `{row['security_id']}` {row['security_name']}：{money(row['unrealized_pnl_rmb'])}，"
            f"当前权重{float(row['weight_of_total_assets']) * 100:.2f}%。"
            for row in real_negative
        )

    report = replace_section(
        report,
        "### 真实账户主要负贡献",
        "## 四、袖套层归因",
        real_body,
    )

    chinese_proposals = {
        "R5-CAL-001": ("Current与完整收盘门禁", "任何真实动作或期间归因前，必须取得最新完整收盘行情，并由用户确认零Delta或提供全部交易Delta。"),
        "R5-CAL-002": ("模拟盘P&L桥接为强制项", "每次复盘必须将当前持仓未实现P&L，通过已实现盈亏、费用及其他Ledger项目桥接到账户总P&L，不得强行令两者相等。"),
        "R5-CAL-003": ("快照贡献不等于期间收益", "当前持仓相对记录成本的贡献必须单独标识；在期初、期末和资金流Ledger完成前，月度或年度收益结论保持阻断。"),
        "R5-CAL-004": ("先诊断袖套内部，再考虑组合重构", "当袖套仍处于参考区间时，优先审查其内部选股、估值和进入质量，不因局部亏损推倒重建整个组合。"),
        "R5-CAL-005": ("No-add与Hard-review门禁继续有效", "持仓跌破成本不能自动触发补仓；新增资金必须重新通过投资逻辑、现金流、估值及组合适配门禁。"),
        "R5-CAL-006": ("Candidate Alpha必须等待成熟窗口", "在20/60/120个交易日窗口成熟并完成Benchmark对账前，继续禁止Alpha声明，不因短期价格表现自动改变Candidate成员。"),
        "R5-CAL-007": ("真实账户现金仍是执行余额", "外部流动性不纳入证券账户战略配置，不为真实账户设定固定战略现金目标。"),
        "R5-CAL-008": ("单一快照不得修改策略规则", "规则变更必须具备多期独立样本、失败类型归类、回归测试及用户明确批准；当前只形成Proposal。"),
    }
    proposal_lines = []
    for index, proposal in enumerate(calibration["proposals"], start=1):
        title, text = chinese_proposals[proposal["proposal_id"]]
        proposal_lines.append(
            f"{index}. **{title}**：{text} 状态：`{proposal['status']}`。"
        )
    report = replace_section(
        report,
        "## 七、策略校准提案",
        "## 八、R6输入要求",
        "\n".join(proposal_lines),
    )

    report = re.sub(r"¥-([0-9][0-9,]*\.[0-9]{2})", r"-¥\1", report)
    report = report.replace(" + -¥", " − ¥")

    negative_section = report.split("### 真实账户主要负贡献", 1)[1].split("## 四、袖套层归因", 1)[0]
    assert "110017.OF" not in negative_section
    assert "217003.OF" not in negative_section
    assert "159612.SZ" not in negative_section
    assert "510500.SH" in negative_section
    assert "159352.SZ" in negative_section
    assert negative_section.count("\n- `") == 2
    assert "Current-state and completed-close gate" not in report
    assert "Current与完整收盘门禁" in report
    assert report.count("PROPOSED_NOT_APPLIED") >= 8

    report_path.write_text(report.rstrip() + "\n", encoding="utf-8")
    print({"real_negative_contributors": 2, "currency_sign_normalized": True, "calibration_language": "zh-CN"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
