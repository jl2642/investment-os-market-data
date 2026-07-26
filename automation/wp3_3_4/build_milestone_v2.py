#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


HERE = Path(__file__).resolve()
SPEC = importlib.util.spec_from_file_location("wp3_3_4_base", HERE.with_name("build_milestone.py"))
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load WP3-3/4 base engine")
base = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = base
SPEC.loader.exec_module(base)


def clean(value: Any) -> Any:
    return base.clean_scalar(value)


def current_valuation_context(row: pd.Series, cfg: dict[str, Any]) -> tuple[str, float | None, list[str]]:
    valid_count = clean(row.get("valuation_valid_metric_count"))
    pe = clean(row.get("current_pe_ttm"))
    fcf_yield = clean(row.get("current_fcf_yield_ttm"))
    shareholder_yield = clean(row.get("current_shareholder_yield_ttm"))
    minimum_count = int(cfg["valuation_context"]["minimum_valid_metric_count"])
    notes = ["PRICE_LINKED_REBASE_FROM_FMDL3E_TO_20260724_CURRENT"]
    if valid_count is None or int(valid_count) < minimum_count:
        return "VALUATION_EVIDENCE_INSUFFICIENT", None, notes + ["VALUATION_VALID_METRICS_BELOW_MINIMUM"]

    components: list[float] = []
    if pe is not None:
        pe_value = float(pe)
        if 0 < pe_value <= 35:
            components.append(85.0)
        elif pe_value <= float(cfg["valuation_context"]["moderate_pe_ttm_max"]):
            components.append(65.0)
        elif pe_value >= float(cfg["valuation_context"]["high_expectation_pe_ttm_min"]):
            components.append(25.0)
            notes.append("HIGH_EXPECTATION_PE")
        elif pe_value > 0:
            components.append(45.0)
        else:
            notes.append("NON_POSITIVE_OR_NOT_MEANINGFUL_PE")
    if fcf_yield is not None:
        components.append(75.0 if float(fcf_yield) > 0 else 30.0)
        if float(fcf_yield) <= 0:
            notes.append("NON_POSITIVE_FCF_YIELD")
    if shareholder_yield is not None:
        components.append(70.0 if float(shareholder_yield) > 0 else 45.0)
    if not components:
        return "VALUATION_EVIDENCE_INSUFFICIENT", None, notes + ["NO_USABLE_VALUATION_COMPONENT"]

    score = float(np.mean(components))
    if score >= 70:
        state = "VALUATION_SUPPORTIVE_FOR_RESEARCH"
    elif score >= 45:
        state = "VALUATION_NEUTRAL_OR_MIXED"
    else:
        state = "VALUATION_HIGH_EXPECTATION_OR_WEAK_CASH_SUPPORT"
    return state, score, notes


def apply_current_price_and_investability(assessment: pd.DataFrame, cfg: dict[str, Any]) -> pd.DataFrame:
    frame = assessment.copy()
    current_price = pd.to_numeric(frame["last_price"], errors="coerce")
    old_close = pd.to_numeric(frame["close"], errors="coerce")
    ratio = current_price / old_close
    ratio = ratio.where((current_price > 0) & (old_close > 0))
    frame["valuation_price_ratio"] = ratio
    frame["valuation_price_rebase_status"] = np.where(
        ratio.notna(),
        "PRICE_LINKED_REBASE_FROM_FMDL3E_TO_20260724_CURRENT",
        "PRICE_LINKED_REBASE_UNAVAILABLE",
    )
    frame["current_pe_ttm"] = pd.to_numeric(frame["pe_ttm"], errors="coerce") * ratio
    frame["current_fcf_yield_ttm"] = pd.to_numeric(frame["fcf_yield_ttm"], errors="coerce") / ratio
    frame["current_shareholder_yield_ttm"] = pd.to_numeric(frame["shareholder_yield_ttm"], errors="coerce") / ratio
    frame["current_market_cap_cny"] = pd.to_numeric(frame["total_market_cap"], errors="coerce") * 10000.0
    frame["current_turnover_cny"] = pd.to_numeric(frame["turnover_amount"], errors="coerce")

    valuation = frame.apply(lambda row: current_valuation_context(row, cfg), axis=1)
    frame["valuation_context_state"] = [item[0] for item in valuation]
    frame["valuation_context_score"] = [item[1] for item in valuation]
    frame["valuation_context_notes"] = ["|".join(item[2]) for item in valuation]

    frame["institutional_size_gate"] = frame["current_market_cap_cny"].ge(5_000_000_000.0)
    frame["deep_dive_size_gate"] = frame["current_market_cap_cny"].ge(10_000_000_000.0)
    avg_turnover = pd.to_numeric(frame.get("avg_turnover_cny_20d"), errors="coerce")
    frame["research_liquidity_gate"] = frame["current_turnover_cny"].ge(50_000_000.0) | avg_turnover.ge(50_000_000.0)
    frame["deep_dive_liquidity_gate"] = frame["current_turnover_cny"].ge(100_000_000.0) | avg_turnover.ge(100_000_000.0)

    penalty = pd.Series(0.0, index=frame.index)
    penalty += np.where(frame["current_market_cap_cny"].lt(10_000_000_000.0), 4.0, 0.0)
    penalty += np.where(frame["valuation_context_state"].eq("VALUATION_HIGH_EXPECTATION_OR_WEAK_CASH_SUPPORT"), 8.0, 0.0)
    penalty += np.where(frame["valuation_context_state"].eq("VALUATION_NEUTRAL_OR_MIXED"), 2.0, 0.0)
    penalty += np.where(pd.to_numeric(frame.get("volatility_60d"), errors="coerce").gt(0.80), 6.0, 0.0)
    penalty += np.where(pd.to_numeric(frame.get("max_drawdown_120d"), errors="coerce").lt(-0.40), 6.0, 0.0)
    penalty += np.where(frame["historical_factor_score"].isna(), 1.5, 0.0)
    frame["research_risk_penalty"] = penalty
    frame["research_priority_score_pre_penalty"] = frame["research_priority_score"]
    frame["research_priority_score"] = pd.to_numeric(frame["research_priority_score"], errors="coerce") - penalty

    dispositions = []
    for row in frame.itertuples(index=False):
        score_state = str(getattr(row, "score_state", ""))
        gate_pass = bool(getattr(row, "financial_gate_pass", False))
        size_pass = bool(getattr(row, "institutional_size_gate", False))
        liquidity_pass = bool(getattr(row, "research_liquidity_gate", False))
        prior_rejected = str(getattr(row, "prior_graduation_decision", "")) == "REJECTED"
        if score_state == "CONTROLLED_PROFILE_EXCLUSION":
            disposition = "SEPARATE_PROFILE_REVIEW_REQUIRED"
        elif prior_rejected:
            disposition = "DEFER_PRIOR_REJECTION_REQUIRES_NEW_EVIDENCE"
        elif gate_pass and size_pass and liquidity_pass:
            disposition = "MULTIDIMENSIONAL_ELIGIBLE"
        elif gate_pass and liquidity_pass:
            disposition = "WATCH_SMALL_CAP_OR_CAPITALIZATION_REVIEW"
        elif score_state.startswith("SCORE_ACCEPTED"):
            disposition = "DEFER_BELOW_STABLE_GROWTH_OR_INVESTABILITY_GATE"
        else:
            disposition = "DEFER_FINANCIAL_EVIDENCE_OR_PROFILE"
        dispositions.append(disposition)
    frame["multidimensional_disposition"] = dispositions
    return frame.sort_values(
        ["research_priority_score", "financial_score", "current_market_cap_cny", "security_code"],
        ascending=[False, False, False, True],
        na_position="last",
    ).reset_index(drop=True)


def select_with_caps(
    source: pd.DataFrame,
    target: int,
    selected_codes: set[str],
    industry_counts: dict[str, int],
    board_counts: dict[str, int],
    cfg: dict[str, Any],
) -> list[pd.Series]:
    rows: list[pd.Series] = []
    max_industry = int(cfg["longlist"]["maximum_per_industry"])
    max_board = int(cfg["longlist"]["maximum_per_board"])
    for _, row in source.iterrows():
        code = str(row["security_code"])
        if code in selected_codes:
            continue
        industry = str(row.get("industry_bucket") or "UNCLASSIFIED")
        board = str(row.get("board") or "UNKNOWN")
        if industry_counts.get(industry, 0) >= max_industry:
            continue
        if board_counts.get(board, 0) >= max_board:
            continue
        rows.append(row)
        selected_codes.add(code)
        industry_counts[industry] = industry_counts.get(industry, 0) + 1
        board_counts[board] = board_counts.get(board, 0) + 1
        if len(rows) >= target:
            break
    return rows


def select_tiered_longlist(assessment: pd.DataFrame, cfg: dict[str, Any]) -> pd.DataFrame:
    eligible = assessment[assessment["multidimensional_disposition"].eq("MULTIDIMENSIONAL_ELIGIBLE")].copy()
    eligible = eligible.sort_values(
        ["research_priority_score", "financial_score", "current_market_cap_cny", "security_code"],
        ascending=[False, False, False, True],
        na_position="last",
    )
    selected_codes: set[str] = set()
    industry_counts: dict[str, int] = {}
    board_counts: dict[str, int] = {}

    a_source = eligible[
        eligible["deep_dive_size_gate"]
        & eligible["deep_dive_liquidity_gate"]
        & eligible["valuation_context_state"].ne("VALUATION_HIGH_EXPECTATION_OR_WEAK_CASH_SUPPORT")
        & ~eligible["research_risk_flags"].str.contains("HIGH_60D_VOLATILITY|DEEP_120D_DRAWDOWN", na=False)
    ]
    a_rows = select_with_caps(a_source, 20, selected_codes, industry_counts, board_counts, cfg)

    b_source = eligible[eligible["institutional_size_gate"] & eligible["research_liquidity_gate"]]
    b_rows = select_with_caps(b_source, 20, selected_codes, industry_counts, board_counts, cfg)

    c_source = assessment[
        assessment["multidimensional_disposition"].isin(
            ["MULTIDIMENSIONAL_ELIGIBLE", "WATCH_SMALL_CAP_OR_CAPITALIZATION_REVIEW"]
        )
    ].sort_values(
        ["research_priority_score", "financial_score", "current_market_cap_cny", "security_code"],
        ascending=[False, False, False, True],
        na_position="last",
    )
    remaining = max(0, int(cfg["longlist"]["maximum_rows"]) - len(a_rows) - len(b_rows))
    c_rows = select_with_caps(c_source, remaining, selected_codes, industry_counts, board_counts, cfg)

    rows = []
    for lane, lane_rows in [("A_DEEP_DIVE", a_rows), ("B_STRUCTURED_RESEARCH", b_rows), ("C_WATCH_AND_EVIDENCE_FILL", c_rows)]:
        for row in lane_rows:
            record = row.copy()
            record["research_bucket"] = lane
            rows.append(record)
    longlist = pd.DataFrame(rows).reset_index(drop=True)
    if len(longlist):
        longlist.insert(0, "research_longlist_rank", range(1, len(longlist) + 1))
        longlist["proposed_next_step"] = longlist["research_bucket"].map(
            {
                "A_DEEP_DIVE": "FULL_RESEARCH_OBJECT_AND_VALUATION_SCENARIO",
                "B_STRUCTURED_RESEARCH": "COMPANY_TEARSHEET_AND_EARNINGS_QUALITY_REVIEW",
                "C_WATCH_AND_EVIDENCE_FILL": "EVIDENCE_FILL_AND_TRIGGER_MONITORING",
            }
        )
        longlist["candidate_membership_mutation"] = 0
        longlist["trade_authority"] = "NONE"
    return longlist


def build_unified_workplan(longlist: pd.DataFrame, core_review: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    long_codes = set(longlist["security_code"].astype(str)) if len(longlist) else set()
    for row in longlist.itertuples(index=False):
        rows.append(
            {
                "security_code": row.security_code,
                "security_name": row.security_name,
                "workplan_lane": row.research_bucket,
                "workplan_priority": int(row.research_longlist_rank),
                "historical_core20": bool(row.historical_core20),
                "source": "WP3_3_INDUSTRY_LONGLIST",
                "required_next_work": row.proposed_next_step,
                "candidate_membership_mutation": 0,
                "trade_authority": "NONE",
            }
        )
    priority = len(rows)
    for row in core_review.itertuples(index=False):
        if str(row.security_code) in long_codes:
            continue
        priority += 1
        rows.append(
            {
                "security_code": row.security_code,
                "security_name": row.security_name,
                "workplan_lane": "CORE20_MANDATORY_REVIEW",
                "workplan_priority": priority,
                "historical_core20": True,
                "source": "WP3_4_HISTORICAL_CORE20_REVIEW",
                "required_next_work": row.core20_review_disposition,
                "candidate_membership_mutation": 0,
                "trade_authority": "NONE",
            }
        )
    return pd.DataFrame(rows)


def executive_review(assessment: pd.DataFrame, longlist: pd.DataFrame, core: pd.DataFrame, comparison: pd.DataFrame, workplan: pd.DataFrame, cfg: dict[str, Any]) -> str:
    disp = assessment["multidimensional_disposition"].value_counts().to_dict()
    core_disp = core["core20_review_disposition"].value_counts().to_dict()
    bucket_counts = longlist["research_bucket"].value_counts().to_dict() if len(longlist) else {}
    overlap = int(comparison["overlap"].sum()) if len(comparison) else 0
    top = []
    for row in longlist.head(20).itertuples(index=False):
        top.append(
            f"| {int(row.research_longlist_rank)} | {row.security_code} | {row.security_name} | {row.research_bucket} | "
            f"{row.industry_bucket} | {clean(row.current_market_cap_cny)} | {clean(row.financial_score)} | "
            f"{clean(row.research_priority_score)} | {row.valuation_context_state} |"
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

本轮使用FMDL财务质量、盈利能力、成长、现金质量、资产负债表、估值语境、历史因子和当前流动性安排研究工作。估值通过FMDL-3E旧收盘价与2026-07-24 Current价格的比例进行价格联动重估；底层财务期不因此被宣称为更新。所有分数均为研究优先级，不构成投资吸引力排名、Candidate准入或交易建议。

## 2. 全市场分层

```json
{json.dumps(disp, ensure_ascii=False, indent=2, sort_keys=True)}
```

金融及通用非金融评分包不适用的公司进入独立Profile研究，不以零分替代。此前被正式研究拒绝的公司必须先出现新证据，不得凭量化分数重新进入Longlist。

## 3. Longlist分桶

```json
{json.dumps(bucket_counts, ensure_ascii=False, indent=2, sort_keys=True)}
```

A桶要求至少100亿元当前市值、研究流动性、稳健成长财务门禁和风险控制；B桶保持至少50亿元市值；C桶用于小市值或证据补齐观察。行业与板块设置集中度上限。

## 4. 历史Core20重审

```json
{json.dumps(core_disp, ensure_ascii=False, indent=2, sort_keys=True)}
```

历史Core20不享受祖父条款。未进入新Longlist的Core20仍进入`CORE20_MANDATORY_REVIEW`研究通道，这只是强制重审，不是自动留存。

## 5. A桶前20个研究任务

| Rank | Code | Name | Lane | Industry | Current market cap CNY | Financial | Priority | Valuation |
|---:|---|---|---|---|---:|---:|---:|---|
{chr(10).join(top)}

## 6. 下一步门禁

WP3-5 + WP3-6基于统一研究工作计划完成Research Object、Entry Baseline和Candidate Core / Shadow / Ready-to-Buy建议。任何Candidate成员变更必须形成单独受治理Proposal并由用户批准。
"""


def write_outputs(root: Path, output_dir: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    data = base.load_data(root, cfg)
    assessment = base.build_assessment(data, cfg)
    assessment = apply_current_price_and_investability(assessment, cfg)
    longlist = select_tiered_longlist(assessment, cfg)
    core = base.core20_review(assessment, cfg)
    comparison = base.comparison_table(longlist, core)
    workplan = build_unified_workplan(longlist, core)
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
    assessment[assessment["multidimensional_disposition"].eq("MULTIDIMENSIONAL_ELIGIBLE")].to_csv(
        files["eligible_research_universe"], index=False, encoding="utf-8-sig"
    )
    longlist.to_csv(files["industry_longlist"], index=False, encoding="utf-8-sig")
    core.to_csv(files["historical_core20_review"], index=False, encoding="utf-8-sig")
    comparison.to_csv(files["new_vs_old_comparison"], index=False, encoding="utf-8-sig")
    workplan.to_csv(files["unified_research_workplan"], index=False, encoding="utf-8-sig")
    gaps.to_csv(files["research_gap_queue"], index=False, encoding="utf-8-sig")
    files["executive_review"].write_text(
        executive_review(assessment, longlist, core, comparison, workplan, cfg), encoding="utf-8"
    )

    bucket_counts = longlist["research_bucket"].value_counts().to_dict() if len(longlist) else {}
    metrics = {
        "full_market_rows": int(len(assessment)),
        "multidimensional_eligible_rows": int(assessment["multidimensional_disposition"].eq("MULTIDIMENSIONAL_ELIGIBLE").sum()),
        "industry_longlist_rows": int(len(longlist)),
        "deep_dive_rows": int(bucket_counts.get("A_DEEP_DIVE", 0)),
        "structured_research_rows": int(bucket_counts.get("B_STRUCTURED_RESEARCH", 0)),
        "watch_rows": int(bucket_counts.get("C_WATCH_AND_EVIDENCE_FILL", 0)),
        "industry_bucket_count": int(longlist["industry_bucket"].nunique()) if len(longlist) else 0,
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
        "contract_version": "2.0.0",
        "status": "PROPOSAL_ONLY_PENDING_HUMAN_REVIEW",
        "as_of_date": cfg["as_of_date"],
        "method": "TIERED_MULTIDIMENSIONAL_RESEARCH_PRIORITY_NOT_INVESTMENT_RANKING",
        "valuation_refresh": "PRICE_LINKED_REBASE_ONLY_UNDERLYING_FINANCIAL_PERIOD_UNCHANGED",
        "metrics": metrics,
        "authority": cfg["authority"],
        "files": {
            key: {"path": str(path.relative_to(root)), "sha256": base.sha256_file(path)}
            for key, path in files.items()
        },
        "next_gate": "WP3-5_WP3-6_RESEARCH_OBJECT_ENTRY_BASELINE_AND_CANDIDATE_REBUILD_PROPOSAL",
        "trade_authority": "NONE",
    }
    manifest_path = output_dir / "WP3_3_4_MANIFEST.json"
    base.write_json(manifest_path, manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--config", default="automation/wp3_3_4/config.json")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    cfg = base.read_json(root / args.config)
    result = write_outputs(root, root / args.output_dir, cfg)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
