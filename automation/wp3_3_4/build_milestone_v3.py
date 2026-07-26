#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd


HERE = Path(__file__).resolve()
SPEC = importlib.util.spec_from_file_location("wp3_3_4_v2", HERE.with_name("build_milestone_v2.py"))
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load WP3-3/4 v2 engine")
v2 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = v2
SPEC.loader.exec_module(v2)
base = v2.base


def strategy_sleeve(row: pd.Series) -> str:
    profile = str(row.get("sector_profile") or "")
    industry = str(row.get("industry_name") or "")
    if profile in {"BANK", "INSURANCE", "SECURITIES", "DIVERSIFIED_FINANCIALS"}:
        return "FINANCIAL_SEPARATE_PROFILE"
    if industry.startswith("B ") or "采矿" in industry:
        return "RESOURCE_CYCLE"
    if industry.startswith("D ") or industry.startswith("G ") or "水电煤气" in industry or "运输仓储" in industry:
        return "DEFENSIVE_INFRA_YIELD"
    return "QUALITY_GROWTH"


def sleeve_gate(row: pd.Series, cfg: dict[str, Any]) -> tuple[bool, list[str]]:
    sleeve = str(row.get("strategy_sleeve") or "QUALITY_GROWTH")
    if sleeve == "FINANCIAL_SEPARATE_PROFILE":
        return False, ["SEPARATE_FINANCIAL_PROFILE_REQUIRED"]
    rule = cfg["strategy_sleeve_gates"][sleeve]
    reasons: list[str] = []
    score_state = str(row.get("score_state") or "")
    confidence = str(row.get("score_confidence") or "")
    values = {
        "financial_score": base.clean_scalar(row.get("financial_score")),
        "profitability": base.clean_scalar(row.get("profitability_returns_score")),
        "growth": base.clean_scalar(row.get("growth_momentum_score")),
        "cash_quality": base.clean_scalar(row.get("cash_earnings_quality_score")),
        "balance_sheet": base.clean_scalar(row.get("balance_sheet_efficiency_score")),
    }
    if not score_state.startswith("SCORE_ACCEPTED"):
        reasons.append("FINANCIAL_SCORE_NOT_ACCEPTED")
    if confidence not in set(rule["allowed_confidence"]):
        reasons.append("CONFIDENCE_NOT_ALLOWED")
    for key, minimum_key in [
        ("financial_score", "minimum_financial_score"),
        ("profitability", "minimum_profitability_score"),
        ("growth", "minimum_growth_score"),
        ("cash_quality", "minimum_cash_quality_score"),
        ("balance_sheet", "minimum_balance_sheet_score"),
    ]:
        value = values[key]
        minimum = float(rule[minimum_key])
        if value is None:
            reasons.append(f"{key.upper()}_MISSING")
        elif float(value) < minimum:
            reasons.append(f"{key.upper()}_BELOW_{sleeve}_GATE")
    if rule.get("require_positive_shareholder_or_dividend_yield"):
        shareholder = base.clean_scalar(row.get("current_shareholder_yield_ttm"))
        dividend = base.clean_scalar(row.get("dividend_yield_ttm"))
        if not ((shareholder is not None and float(shareholder) > 0) or (dividend is not None and float(dividend) > 0)):
            reasons.append("POSITIVE_SHAREHOLDER_OR_DIVIDEND_YIELD_NOT_PROVEN")
    return not reasons, reasons


def apply_strategy_sleeves(assessment: pd.DataFrame, cfg: dict[str, Any]) -> pd.DataFrame:
    frame = assessment.copy()
    frame["strategy_sleeve"] = frame.apply(strategy_sleeve, axis=1)
    gates = frame.apply(lambda row: sleeve_gate(row, cfg), axis=1)
    frame["financial_gate_pass"] = [item[0] for item in gates]
    frame["financial_gate_reasons"] = ["|".join(item[1]) for item in gates]

    dispositions: list[str] = []
    for row in frame.itertuples(index=False):
        sleeve = str(getattr(row, "strategy_sleeve", ""))
        gate_pass = bool(getattr(row, "financial_gate_pass", False))
        size_pass = bool(getattr(row, "institutional_size_gate", False))
        liquidity_pass = bool(getattr(row, "research_liquidity_gate", False))
        prior_rejected = str(getattr(row, "prior_graduation_decision", "")) == "REJECTED"
        if sleeve == "FINANCIAL_SEPARATE_PROFILE":
            disposition = "SEPARATE_PROFILE_REVIEW_REQUIRED"
        elif prior_rejected:
            disposition = "DEFER_PRIOR_REJECTION_REQUIRES_NEW_EVIDENCE"
        elif gate_pass and size_pass and liquidity_pass:
            disposition = "MULTIDIMENSIONAL_ELIGIBLE"
        elif gate_pass and liquidity_pass:
            disposition = "WATCH_SMALL_CAP_OR_CAPITALIZATION_REVIEW"
        elif str(getattr(row, "score_state", "")).startswith("SCORE_ACCEPTED"):
            disposition = "DEFER_BELOW_STRATEGY_SLEEVE_OR_INVESTABILITY_GATE"
        else:
            disposition = "DEFER_FINANCIAL_EVIDENCE_OR_PROFILE"
        dispositions.append(disposition)
    frame["multidimensional_disposition"] = dispositions
    return frame.sort_values(
        ["research_priority_score", "financial_score", "current_market_cap_cny", "security_code"],
        ascending=[False, False, False, True],
        na_position="last",
    ).reset_index(drop=True)


def executive_review(assessment: pd.DataFrame, longlist: pd.DataFrame, core: pd.DataFrame, comparison: pd.DataFrame, workplan: pd.DataFrame, cfg: dict[str, Any]) -> str:
    disposition = assessment["multidimensional_disposition"].value_counts().to_dict()
    sleeves = assessment["strategy_sleeve"].value_counts().to_dict()
    long_sleeves = longlist["strategy_sleeve"].value_counts().to_dict() if len(longlist) else {}
    core_disp = core["core20_review_disposition"].value_counts().to_dict()
    buckets = longlist["research_bucket"].value_counts().to_dict() if len(longlist) else {}
    overlap = int(comparison["overlap"].sum()) if len(comparison) else 0
    top = []
    for row in longlist.head(20).itertuples(index=False):
        top.append(
            f"| {int(row.research_longlist_rank)} | {row.security_code} | {row.security_name} | {row.strategy_sleeve} | "
            f"{row.industry_bucket} | {base.clean_scalar(row.current_market_cap_cny)} | {base.clean_scalar(row.financial_score)} | "
            f"{base.clean_scalar(row.research_priority_score)} | {row.valuation_context_state} |"
        )
    return f"""# WP3-3 + WP3-4｜多维筛选、行业Longlist与历史Core20重审

- 数据基准：{cfg['as_of_date']}已接受普通A股Current
- WP3-2B Eligible Universe：{len(assessment)}
- 多维研究Longlist：{len(longlist)}
- 统一研究工作计划：{len(workplan)}
- 历史Core20重审：{len(core)}
- 新Longlist与历史Core20重合：{overlap}
- 投资排名：否
- Candidate、Research Object、真实账户、模拟盘和订单变更：0
- trade_authority：NONE

## 1. 方法边界

本轮以研究优先级而非投资排名组织工作。估值仅依据FMDL-3E旧收盘价与2026-07-24 Current价格比例联动重估；底层财务期间并未被宣称更新。通用非金融评分不再机械套用于所有行业，而按`QUALITY_GROWTH`、`DEFENSIVE_INFRA_YIELD`、`RESOURCE_CYCLE`和`FINANCIAL_SEPARATE_PROFILE`分开设门禁。

## 2. 策略袖套覆盖

全市场：
```json
{json.dumps(sleeves, ensure_ascii=False, indent=2, sort_keys=True)}
```

Longlist：
```json
{json.dumps(long_sleeves, ensure_ascii=False, indent=2, sort_keys=True)}
```

金融公司保持独立Profile研究，不以零分填充。公用事业与基础设施允许较低成长和更高杠杆，但必须有盈利、现金及股东回报支持；资源周期要求更高盈利和现金质量，不能凭单纯价格动量入选。

## 3. 全市场分层

```json
{json.dumps(disposition, ensure_ascii=False, indent=2, sort_keys=True)}
```

此前正式研究拒绝的公司必须出现新证据，不得仅凭量化分数重新进入Longlist。

## 4. Longlist分桶

```json
{json.dumps(buckets, ensure_ascii=False, indent=2, sort_keys=True)}
```

A桶要求至少100亿元当前市值、研究流动性和风险控制；B桶保持至少50亿元市值；C桶用于小市值或证据补齐观察。行业和板块设置集中度上限。

## 5. 历史Core20重审

```json
{json.dumps(core_disp, ensure_ascii=False, indent=2, sort_keys=True)}
```

历史Core20不享受祖父条款。未进入新Longlist的Core20仍进入`CORE20_MANDATORY_REVIEW`，这是强制重审，不是自动留存。

## 6. A桶前20个研究任务

| Rank | Code | Name | Strategy sleeve | Industry | Current market cap CNY | Financial | Priority | Valuation |
|---:|---|---|---|---|---:|---:|---:|---|
{chr(10).join(top)}

## 7. 下一步门禁

WP3-5 + WP3-6基于统一研究工作计划完成Research Object、Entry Baseline和Candidate Core / Shadow / Ready-to-Buy建议。任何Candidate成员变更必须形成单独受治理Proposal并由用户批准。
"""


def write_outputs(root: Path, output_dir: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    data = base.load_data(root, cfg)
    assessment = base.build_assessment(data, cfg)
    assessment = v2.apply_current_price_and_investability(assessment, cfg)
    assessment = apply_strategy_sleeves(assessment, cfg)
    longlist = v2.select_tiered_longlist(assessment, cfg)
    core = base.core20_review(assessment, cfg)
    comparison = base.comparison_table(longlist, core)
    workplan = v2.build_unified_workplan(longlist, core)
    gaps = assessment[
        assessment["multidimensional_disposition"].isin(
            [
                "SEPARATE_PROFILE_REVIEW_REQUIRED",
                "DEFER_FINANCIAL_EVIDENCE_OR_PROFILE",
                "DEFER_PRIOR_REJECTION_REQUIRES_NEW_EVIDENCE",
                "WATCH_SMALL_CAP_OR_CAPITALIZATION_REVIEW",
            ]
        )
        | assessment["historical_core20"]
    ].copy()

    output_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "full_market_assessment": output_dir / "WP3_3_4_FULL_MARKET_ASSESSMENT.csv",
        "eligible_research_universe": output_dir / "WP3_3_4_ELIGIBLE_RESEARCH_UNIVERSE.csv",
        "industry_longlist": output_dir / "WP3_3_INDUSTRY_LONGLIST.csv",
        "historical_core20_review": output_dir / "WP3_4_HISTORICAL_CORE20_REVIEW.csv",
        "new_vs_old_comparison": output_dir / "WP3_4_NEW_VS_OLD_CANDIDATE_COMPARISON.csv",
        "unified_research_workplan": output_dir / "WP3_3_4_UNIFIED_RESEARCH_WORKPLAN.csv",
        "research_gap_queue": output_dir / "WP3_3_4_RESEARCH_GAP_QUEUE.csv",
        "executive_review": output_dir / "WP3_3_4_EXECUTIVE_REVIEW.md",
    }
    assessment.to_csv(files["full_market_assessment"], index=False, encoding="utf-8-sig")
    assessment[assessment["multidimensional_disposition"].eq("MULTIDIMENSIONAL_ELIGIBLE")].to_csv(files["eligible_research_universe"], index=False, encoding="utf-8-sig")
    longlist.to_csv(files["industry_longlist"], index=False, encoding="utf-8-sig")
    core.to_csv(files["historical_core20_review"], index=False, encoding="utf-8-sig")
    comparison.to_csv(files["new_vs_old_comparison"], index=False, encoding="utf-8-sig")
    workplan.to_csv(files["unified_research_workplan"], index=False, encoding="utf-8-sig")
    gaps.to_csv(files["research_gap_queue"], index=False, encoding="utf-8-sig")
    files["executive_review"].write_text(executive_review(assessment, longlist, core, comparison, workplan, cfg), encoding="utf-8")

    bucket_counts = longlist["research_bucket"].value_counts().to_dict() if len(longlist) else {}
    metrics = {
        "full_market_rows": int(len(assessment)),
        "multidimensional_eligible_rows": int(assessment["multidimensional_disposition"].eq("MULTIDIMENSIONAL_ELIGIBLE").sum()),
        "industry_longlist_rows": int(len(longlist)),
        "deep_dive_rows": int(bucket_counts.get("A_DEEP_DIVE", 0)),
        "structured_research_rows": int(bucket_counts.get("B_STRUCTURED_RESEARCH", 0)),
        "watch_rows": int(bucket_counts.get("C_WATCH_AND_EVIDENCE_FILL", 0)),
        "industry_bucket_count": int(longlist["industry_bucket"].nunique()) if len(longlist) else 0,
        "strategy_sleeve_count": int(longlist["strategy_sleeve"].nunique()) if len(longlist) else 0,
        "historical_core20_review_rows": int(len(core)),
        "core20_longlist_overlap": int(comparison["overlap"].sum()),
        "unified_research_workplan_rows": int(len(workplan)),
        "separate_profile_review_rows": int(assessment["multidimensional_disposition"].eq("SEPARATE_PROFILE_REVIEW_REQUIRED").sum()),
        "prior_rejection_deferred_rows": int(assessment["multidimensional_disposition"].eq("DEFER_PRIOR_REJECTION_REQUIRES_NEW_EVIDENCE").sum()),
        "candidate_membership_mutations": 0,
        "research_object_mutations": 0,
        "simulation_trade_mutations": 0,
        "real_account_mutations": 0,
        "orders": 0,
    }
    manifest = {
        "program_id": cfg["program_id"],
        "contract_version": "3.0.0",
        "status": "PROPOSAL_ONLY_PENDING_HUMAN_REVIEW",
        "as_of_date": cfg["as_of_date"],
        "method": "INDUSTRY_SLEEVE_TIERED_MULTIDIMENSIONAL_RESEARCH_PRIORITY_NOT_INVESTMENT_RANKING",
        "valuation_refresh": "PRICE_LINKED_REBASE_ONLY_UNDERLYING_FINANCIAL_PERIOD_UNCHANGED",
        "metrics": metrics,
        "authority": cfg["authority"],
        "files": {key: {"path": str(path.relative_to(root)), "sha256": base.sha256_file(path)} for key, path in files.items()},
        "next_gate": "WP3-5_WP3-6_RESEARCH_OBJECT_ENTRY_BASELINE_AND_CANDIDATE_REBUILD_PROPOSAL",
        "trade_authority": "NONE",
    }
    base.write_json(output_dir / "WP3_3_4_MANIFEST.json", manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--config", default="automation/wp3_3_4/config.json")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    cfg = base.read_json(root / args.config)
    print(json.dumps(write_outputs(root, root / args.output_dir, cfg), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
