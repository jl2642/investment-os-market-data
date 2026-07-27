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

    report = report_path.read_text(encoding="utf-8")
    portfolio = json.loads(portfolio_path.read_text(encoding="utf-8"))

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
    report = re.sub(r"¥-([0-9][0-9,]*\.[0-9]{2})", r"-¥\1", report)

    negative_section = report.split("### 真实账户主要负贡献", 1)[1].split("## 四、袖套层归因", 1)[0]
    assert "110017.OF" not in negative_section
    assert "217003.OF" not in negative_section
    assert "159612.SZ" not in negative_section
    assert "510500.SH" in negative_section
    assert "159352.SZ" in negative_section
    assert negative_section.count("\n- `") == 2

    report_path.write_text(report.rstrip() + "\n", encoding="utf-8")
    print({"real_negative_contributors": 2, "currency_sign_normalized": True})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
