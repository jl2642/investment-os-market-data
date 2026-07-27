from __future__ import annotations

import json
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    state = root / "investment_os_runtime/30_STATE_CURRENT"
    samples = root / "investment_os_runtime/50_OPERATING_PRODUCTS/DEVELOPMENT_SAMPLES"
    simulation = json.loads((state / "20_SIMULATION/SIMULATION_POSITIONS_CURRENT.json").read_text(encoding="utf-8"))
    summary = simulation["summary"]
    cash = round(float(summary["execution_cash_balance"]), 2)
    unrealized = round(float(summary["open_unrealized_pnl"]), 2)

    unified_path = samples / "R4_UNIFIED_OPERATING_STATUS_SAMPLE.json"
    unified = json.loads(unified_path.read_text(encoding="utf-8"))
    unified["simulation"]["cash_rmb"] = cash
    unified["simulation"]["unrealized_pnl_rmb"] = unrealized
    unified["simulation"]["cash_source_field"] = "summary.execution_cash_balance"
    unified["simulation"]["unrealized_pnl_source_field"] = "summary.open_unrealized_pnl"
    unified_path.write_text(json.dumps(unified, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")

    daily_path = samples / "R4_DAILY_OPERATING_BRIEF_SAMPLE.md"
    daily = daily_path.read_text(encoding="utf-8")
    marker = "- 模拟盘：`16`个持仓，总资产约¥1,007,938.48，研究现金约"
    lines = []
    for line in daily.splitlines():
        if line.startswith(marker):
            line = f"- 模拟盘：`16`个持仓，总资产约¥1,007,938.48，研究现金约¥{cash:,.2f}。"
        lines.append(line)
    daily_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    monthly_path = samples / "R4_MONTHLY_INVESTMENT_REVIEW_SAMPLE.md"
    monthly = monthly_path.read_text(encoding="utf-8")
    marker = "- 模拟盘总资产约¥1,007,938.48；当前未实现盈亏字段约"
    lines = []
    for line in monthly.splitlines():
        if line.startswith(marker):
            line = f"- 模拟盘总资产约¥1,007,938.48；当前未实现盈亏约¥{unrealized:,.2f}，但本数值不是月度收益。"
        lines.append(line)
    monthly_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    print({"simulation_cash_rmb": cash, "simulation_open_unrealized_pnl_rmb": unrealized})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
