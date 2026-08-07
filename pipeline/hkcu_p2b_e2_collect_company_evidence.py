#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

import akshare as ak
import pandas as pd

PROGRAM_ID = "HKCU-P2B-E2"
TRADE_AUTHORITY = "NONE"
AS_OF_DATE = date(2026, 8, 7)

PROFILE_SOURCE_URL = "https://emweb.securities.eastmoney.com/PC_HKF10/pages/home/index.html?code={code}&type=web&color=w#/CompanyProfile"
CORE_SOURCE_URL = "https://emweb.securities.eastmoney.com/PC_HKF10/pages/home/index.html?code={code}&type=web&color=w#/CoreReading"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def safe_text(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and math.isnan(v):
        return ""
    return str(v).strip()


def finite(v: Any) -> float | None:
    if v is None:
        return None
    try:
        x = float(str(v).replace(",", "").replace("%", "").strip())
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def parse_date(v: Any) -> date | None:
    s = safe_text(v)
    if not s:
        return None
    s = s.split()[0].replace("/", "-")
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def retry_call(fn, symbol: str, attempts: int, backoff_seconds: float):
    last_error = ""
    for attempt in range(1, attempts + 1):
        try:
            df = fn(symbol=symbol)
            if df is None:
                return pd.DataFrame(), ""
            return df, ""
        except Exception as exc:
            last_error = f"{type(exc).__name__}:{exc}"
            if attempt < attempts:
                time.sleep(backoff_seconds * attempt)
    return pd.DataFrame(), last_error


def first_record(df: pd.DataFrame) -> dict[str, Any]:
    if df is None or df.empty:
        return {}
    return {str(k): v for k, v in df.iloc[0].to_dict().items()}


def normalize_profile(rec: dict[str, Any]) -> dict[str, Any]:
    return {
        "company_name": safe_text(rec.get("公司名称")),
        "english_name": safe_text(rec.get("英文名称")),
        "registered_place": safe_text(rec.get("注册地")),
        "incorporation_date": safe_text(rec.get("公司成立日期")),
        "industry": safe_text(rec.get("所属行业")),
        "chairman": safe_text(rec.get("董事长")),
        "company_secretary": safe_text(rec.get("公司秘书")),
        "employees": safe_text(rec.get("员工人数")),
        "office_address": safe_text(rec.get("办公地址")),
        "company_website": safe_text(rec.get("公司网址")),
        "email": safe_text(rec.get("E-MAIL")),
        "fiscal_year_end": safe_text(rec.get("年结日")),
        "auditor": safe_text(rec.get("核数师")),
        "company_introduction": safe_text(rec.get("公司介绍")),
    }


def normalize_financial(rec: dict[str, Any]) -> dict[str, Any]:
    mapping = {
        "eps": "基本每股收益(元)",
        "book_value_per_share": "每股净资产(元)",
        "dividend_per_share_ttm_hkd": "每股股息TTM(港元)",
        "payout_ratio_pct": "派息比率(%)",
        "operating_cash_flow_per_share": "每股经营现金流(元)",
        "dividend_yield_ttm_pct": "股息率TTM(%)",
        "total_market_cap_hkd": "总市值(港元)",
        "hk_market_cap_hkd": "港股市值(港元)",
        "revenue": "营业总收入",
        "revenue_rolling_qoq_growth_pct": "营业总收入滚动环比增长(%)",
        "net_margin_pct": "销售净利率(%)",
        "net_profit": "净利润",
        "net_profit_rolling_qoq_growth_pct": "净利润滚动环比增长(%)",
        "roe_pct": "股东权益回报率(%)",
        "pe": "市盈率",
        "pb": "市净率",
        "roa_pct": "总资产回报率(%)",
    }
    return {out: finite(rec.get(src)) for out, src in mapping.items()}


def normalize_dividend(df: pd.DataFrame) -> dict[str, Any]:
    if df is None or df.empty:
        return {
            "latest_dividend_announcement_date": "",
            "latest_dividend_fiscal_year": "",
            "latest_dividend_scheme": "",
            "latest_dividend_type": "",
            "latest_ex_date": "",
            "latest_payment_date": "",
        }
    x = df.copy()
    if "最新公告日期" in x.columns:
        x["_parsed"] = x["最新公告日期"].map(parse_date)
        x = x.sort_values("_parsed", ascending=False, na_position="last")
    rec = x.iloc[0].to_dict()
    return {
        "latest_dividend_announcement_date": safe_text(rec.get("最新公告日期")),
        "latest_dividend_fiscal_year": safe_text(rec.get("财政年度")),
        "latest_dividend_scheme": safe_text(rec.get("分红方案")),
        "latest_dividend_type": safe_text(rec.get("分配类型")),
        "latest_ex_date": safe_text(rec.get("除净日")),
        "latest_payment_date": safe_text(rec.get("发放日")),
    }


def governance_flags(profile: dict[str, Any], fin: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    if not profile.get("auditor"):
        flags.append("AUDITOR_NOT_AVAILABLE_IN_SECONDARY_PROFILE")
    if not profile.get("chairman"):
        flags.append("CHAIRMAN_NOT_AVAILABLE_IN_SECONDARY_PROFILE")
    roe = fin.get("roe_pct")
    ocfps = fin.get("operating_cash_flow_per_share")
    profit_growth = fin.get("net_profit_rolling_qoq_growth_pct")
    payout = fin.get("payout_ratio_pct")
    pe = fin.get("pe")
    if roe is not None and roe < 0:
        flags.append("NEGATIVE_ROE")
    elif roe is not None and roe < 5:
        flags.append("LOW_ROE_LT_5PCT")
    if ocfps is not None and ocfps < 0:
        flags.append("NEGATIVE_OPERATING_CASH_FLOW_PER_SHARE")
    if profit_growth is not None and profit_growth < -30:
        flags.append("NET_PROFIT_ROLLING_DECLINE_GT_30PCT")
    if payout is not None and (payout < 0 or payout > 120):
        flags.append("PAYOUT_RATIO_OUTLIER")
    if pe is not None and pe < 0:
        flags.append("NEGATIVE_EARNINGS_PE")
    return flags


def catalyst_context(dividend: dict[str, Any]) -> tuple[str, str, int]:
    ann = parse_date(dividend.get("latest_dividend_announcement_date"))
    exd = parse_date(dividend.get("latest_ex_date"))
    pay = parse_date(dividend.get("latest_payment_date"))
    if not ann:
        return "RESEARCH_REQUIRED", "NO_DATED_DIVIDEND_EVENT_IN_SECONDARY_SOURCE", 0
    days = (AS_OF_DATE - ann).days
    future_event = (exd is not None and exd >= AS_OF_DATE) or (pay is not None and pay >= AS_OF_DATE)
    if 0 <= days <= 180 and future_event:
        return "EVIDENCE_PARTIAL", "DATED_DIVIDEND_EVENT_PRESENT_PRIMARY_VERIFICATION_REQUIRED", 1
    if 0 <= days <= 365:
        return "EVIDENCE_PARTIAL", "RECENT_DIVIDEND_EVENT_CONTEXT_PRIMARY_CATALYST_REVIEW_REQUIRED", 1
    return "RESEARCH_REQUIRED", "NO_RECENT_DATED_CATALYST_FROM_DIVIDEND_FEED", 0


def run_e1(repo_root: Path, work: Path) -> Path:
    e1_dir = work / "_e1"
    e1_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            sys.executable,
            str(repo_root / "pipeline/hkcu_p2b_apply_e1_evidence.py"),
            "--repo-root", str(repo_root),
            "--output", str(e1_dir),
        ],
        check=True,
    )
    return e1_dir


def run_baseline(repo_root: Path, work: Path) -> Path:
    base_dir = work / "_baseline"
    base_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            sys.executable,
            str(repo_root / "pipeline/hkcu_p2b_build_research_baseline.py"),
            "--repo-root", str(repo_root),
            "--output", str(base_dir),
        ],
        check=True,
    )
    return base_dir


def build(repo_root: Path, output: Path) -> None:
    contract = read_json(repo_root / "config/hkcu_p2b_e2_company_evidence_contract.json")
    output.mkdir(parents=True, exist_ok=True)
    baseline_dir = run_baseline(repo_root, output)
    e1_dir = run_e1(repo_root, output)

    sec = pd.read_csv(
        baseline_dir / "HKCU_P2B_SECURITY_TYPE_MATRIX.csv",
        dtype={"stock_code_5d": str},
    )
    e1_dim = pd.read_csv(
        e1_dir / "HKCU_P2B_E1_DIMENSION_MATRIX.csv",
        dtype={"stock_code_5d": str},
    )
    remaining = pd.read_csv(
        e1_dir / "HKCU_P2B_E1_REMAINING_RESEARCH_QUEUE.csv",
        dtype={"stock_code_5d": str},
    )
    expected = contract["expected_counts"]
    failures: list[str] = []
    if len(sec) != int(expected["security_count"]):
        failures.append(f"SECURITY_COUNT:{len(sec)}")
    if len(remaining) != int(expected["e1_remaining_company_specific_tasks"]):
        failures.append(f"E1_REMAINING_COUNT:{len(remaining)}")

    attempts = int(contract["network_policy"]["attempts"])
    backoff = float(contract["network_policy"]["backoff_seconds"])
    sleep_between = float(contract["network_policy"]["sleep_between_securities_seconds"])

    evidence_rows: list[dict[str, Any]] = []
    dimension_rows: list[dict[str, Any]] = []
    fetch_errors: list[dict[str, str]] = []

    for _, s in sec.sort_values("p2a_overall_rank").iterrows():
        code = str(s["stock_code_5d"]).zfill(5)
        profile_df, profile_error = retry_call(ak.stock_hk_company_profile_em, code, attempts, backoff)
        fin_df, fin_error = retry_call(ak.stock_hk_financial_indicator_em, code, attempts, backoff)
        div_df, div_error = retry_call(ak.stock_hk_dividend_payout_em, code, attempts, backoff)

        if profile_error:
            fetch_errors.append({"security_id": s["security_id"], "feed": "company_profile", "error": profile_error})
        if fin_error:
            fetch_errors.append({"security_id": s["security_id"], "feed": "financial_indicator", "error": fin_error})
        if div_error:
            fetch_errors.append({"security_id": s["security_id"], "feed": "dividend", "error": div_error})

        profile = normalize_profile(first_record(profile_df))
        fin = normalize_financial(first_record(fin_df))
        dividend = normalize_dividend(div_df)
        flags = governance_flags(profile, fin)
        catalyst_status, catalyst_reason, catalyst_count = catalyst_context(dividend)

        profile_ok = any(bool(v) for v in profile.values())
        fin_ok = any(v is not None for v in fin.values())
        div_ok = bool(dividend.get("latest_dividend_announcement_date"))
        company_url = profile.get("company_website", "")

        evidence_rows.append({
            "p2a_overall_rank": int(s["p2a_overall_rank"]),
            "security_id": s["security_id"],
            "stock_code_5d": code,
            "official_security_name_en": s["official_security_name_en"],
            "official_issuer_name_en": s["official_issuer_name_en"],
            "p2b_security_type": s["p2b_security_type"],
            "profile_fetch_status": "SUCCESS" if profile_ok else "UNAVAILABLE",
            "financial_indicator_fetch_status": "SUCCESS" if fin_ok else "UNAVAILABLE",
            "dividend_fetch_status": "SUCCESS" if div_ok else "UNAVAILABLE",
            "profile_source_url": PROFILE_SOURCE_URL.format(code=code),
            "core_reading_source_url": CORE_SOURCE_URL.format(code=code),
            "primary_source_lead_url": company_url,
            **profile,
            **fin,
            **dividend,
            "governance_value_trap_flags": "|".join(flags),
            "governance_flag_count": len(flags),
            "source_authority": "SECONDARY_STRUCTURED_PUBLIC_DATA",
            "primary_verification_required": True,
            "score_contribution": 0,
            "trade_authority": TRADE_AUTHORITY,
        })

        gov_status = "EVIDENCE_PARTIAL" if (profile_ok and fin_ok) else "RESEARCH_REQUIRED"
        gov_reason = (
            "SECONDARY_PROFILE_AND_FINANCIAL_CONTEXT_COLLECTED_PRIMARY_GOVERNANCE_VERIFICATION_REQUIRED"
            if gov_status == "EVIDENCE_PARTIAL"
            else "SECONDARY_COMPANY_CONTEXT_INCOMPLETE"
        )
        dimension_rows.append({
            "p2a_overall_rank": int(s["p2a_overall_rank"]),
            "security_id": s["security_id"],
            "stock_code_5d": code,
            "official_security_name_en": s["official_security_name_en"],
            "research_dimension": "GOVERNANCE_VALUE_TRAP",
            "evidence_status": gov_status,
            "evidence_count": int(profile_ok) + int(fin_ok),
            "evidence_reason": gov_reason,
            "evidence_summary": "|".join(flags) if flags else "NO_AUTOMATED_VALUE_TRAP_FLAG_FROM_SECONDARY_CONTEXT",
            "primary_source_lead_url": company_url,
            "score": pd.NA,
            "score_status": "NO_SCORE_SECONDARY_CONTEXT_ONLY",
            "next_action": "PRIMARY_GOVERNANCE_AND_ACCOUNTING_REVIEW",
            "trade_authority": TRADE_AUTHORITY,
        })
        dimension_rows.append({
            "p2a_overall_rank": int(s["p2a_overall_rank"]),
            "security_id": s["security_id"],
            "stock_code_5d": code,
            "official_security_name_en": s["official_security_name_en"],
            "research_dimension": "EARNINGS_EXPECTATION_REVISION",
            "evidence_status": "DATA_UNAVAILABLE",
            "evidence_count": int(fin_ok),
            "evidence_reason": "NO_RELIABLE_CONSENSUS_REVISION_FEED_IN_CURRENT_AUTOMATED_SOURCE",
            "evidence_summary": (
                f"TRAILING_CONTEXT_ONLY:revenue_rolling_growth={fin.get('revenue_rolling_qoq_growth_pct')};"
                f"net_profit_rolling_growth={fin.get('net_profit_rolling_qoq_growth_pct')}"
            ),
            "primary_source_lead_url": company_url,
            "score": pd.NA,
            "score_status": "NO_SCORE_TRAILING_GROWTH_NOT_REVISION",
            "next_action": "COLLECT_DATED_GUIDANCE_RESULTS_AND_RELIABLE_CONSENSUS_IF_AVAILABLE",
            "trade_authority": TRADE_AUTHORITY,
        })
        dimension_rows.append({
            "p2a_overall_rank": int(s["p2a_overall_rank"]),
            "security_id": s["security_id"],
            "stock_code_5d": code,
            "official_security_name_en": s["official_security_name_en"],
            "research_dimension": "CATALYST",
            "evidence_status": catalyst_status,
            "evidence_count": catalyst_count,
            "evidence_reason": catalyst_reason,
            "evidence_summary": (
                f"DIVIDEND_ANNOUNCEMENT={dividend.get('latest_dividend_announcement_date','')};"
                f"EX_DATE={dividend.get('latest_ex_date','')};PAYMENT_DATE={dividend.get('latest_payment_date','')}"
            ),
            "primary_source_lead_url": company_url,
            "score": pd.NA,
            "score_status": "NO_SCORE_PRIMARY_CATALYST_CONFIRMATION_REQUIRED",
            "next_action": "PRIMARY_ANNOUNCEMENT_CATALYST_REVIEW",
            "trade_authority": TRADE_AUTHORITY,
        })
        if sleep_between > 0:
            time.sleep(sleep_between)

    evidence = pd.DataFrame(evidence_rows).sort_values(["p2a_overall_rank", "security_id"]).reset_index(drop=True)
    dimensions = pd.DataFrame(dimension_rows).sort_values(
        ["p2a_overall_rank", "research_dimension", "security_id"]
    ).reset_index(drop=True)
    error_df = pd.DataFrame(fetch_errors, columns=["security_id", "feed", "error"])

    profile_success = int((evidence["profile_fetch_status"] == "SUCCESS").sum())
    fin_success = int((evidence["financial_indicator_fetch_status"] == "SUCCESS").sum())
    div_success = int((evidence["dividend_fetch_status"] == "SUCCESS").sum())
    min_profile = int(contract["acceptance"]["minimum_profile_success_count"])
    min_fin = int(contract["acceptance"]["minimum_financial_success_count"])
    if profile_success < min_profile:
        failures.append(f"PROFILE_SUCCESS_BELOW_GATE:{profile_success}:{min_profile}")
    if fin_success < min_fin:
        failures.append(f"FINANCIAL_SUCCESS_BELOW_GATE:{fin_success}:{min_fin}")
    if len(evidence) != int(expected["security_count"]):
        failures.append("COMPANY_EVIDENCE_ROW_COUNT")
    if len(dimensions) != int(expected["company_dimension_rows"]):
        failures.append("COMPANY_DIMENSION_ROW_COUNT")
    if evidence["security_id"].duplicated().any():
        failures.append("DUPLICATE_COMPANY_EVIDENCE_SECURITY")
    if dimensions["score"].notna().any():
        failures.append("E2_UNSUPPORTED_SCORE_PRESENT")
    if (evidence["trade_authority"] != TRADE_AUTHORITY).any() or (dimensions["trade_authority"] != TRADE_AUTHORITY).any():
        failures.append("TRADE_AUTHORITY_NOT_NONE")

    primary_queue = dimensions[
        dimensions["research_dimension"].isin(
            ["GOVERNANCE_VALUE_TRAP", "EARNINGS_EXPECTATION_REVISION", "CATALYST"]
        )
    ].copy()
    primary_queue["priority_bucket"] = pd.cut(
        pd.to_numeric(primary_queue["p2a_overall_rank"], errors="coerce"),
        bins=[0, 20, 40, 77],
        labels=["P1_TOP20", "P2_RANK21_40", "P3_RANK41_77"],
        include_lowest=True,
    ).astype(str)
    primary_queue["queue_rank"] = range(1, len(primary_queue) + 1)
    primary_queue = primary_queue[
        [
            "queue_rank", "priority_bucket", "p2a_overall_rank", "security_id", "stock_code_5d",
            "official_security_name_en", "research_dimension", "evidence_status",
            "evidence_reason", "evidence_summary", "primary_source_lead_url",
            "next_action", "trade_authority"
        ]
    ]

    evidence_path = output / "HKCU_P2B_E2_COMPANY_EVIDENCE_INTAKE.csv"
    dimension_path = output / "HKCU_P2B_E2_DIMENSION_EVIDENCE.csv"
    queue_path = output / "HKCU_P2B_E2_PRIMARY_RESEARCH_QUEUE.csv"
    error_path = output / "HKCU_P2B_E2_FETCH_ERRORS.csv"
    evidence.to_csv(evidence_path, index=False, encoding="utf-8-sig")
    dimensions.to_csv(dimension_path, index=False, encoding="utf-8-sig")
    primary_queue.to_csv(queue_path, index=False, encoding="utf-8-sig")
    error_df.to_csv(error_path, index=False, encoding="utf-8-sig")

    status_counts = {
        str(k): int(v) for k, v in dimensions["evidence_status"].value_counts(dropna=False).items()
    }
    dimension_status = {
        dim: {
            str(k): int(v)
            for k, v in dimensions.loc[dimensions["research_dimension"] == dim, "evidence_status"]
            .value_counts(dropna=False).items()
        }
        for dim in ["GOVERNANCE_VALUE_TRAP", "EARNINGS_EXPECTATION_REVISION", "CATALYST"]
    }
    decision = {
        "program_id": PROGRAM_ID,
        "phase": "P2B_E2_COMPANY_SPECIFIC_EVIDENCE",
        "status": "PASS_P2B_E2_SECONDARY_INTAKE_PRIMARY_REVIEW_REQUIRED" if not failures else "FAIL_P2B_E2_INTAKE",
        "security_count": int(len(evidence)),
        "profile_success_count": profile_success,
        "financial_indicator_success_count": fin_success,
        "dividend_event_available_count": div_success,
        "company_dimension_rows": int(len(dimensions)),
        "dimension_status_counts": dimension_status,
        "primary_research_queue_count": int(len(primary_queue)),
        "primary_research_priority_top20_task_count": int((primary_queue["priority_bucket"] == "P1_TOP20").sum()),
        "hard_failures": failures,
        "formal_candidate_graduation_allowed": False,
        "next_gate": "P2B_E2_PRIMARY_COMPANY_EVIDENCE_TOP20" if not failures else "BLOCKED_REPAIR",
        "candidate_pool_mutations": 0,
        "simulation_mutations": 0,
        "real_account_mutations": 0,
        "orders_created": 0,
        "trade_authority": TRADE_AUTHORITY,
    }
    quality = {
        "program_id": PROGRAM_ID,
        "status": "PASS" if not failures else "FAIL",
        "source_authority": "SECONDARY_STRUCTURED_PUBLIC_DATA",
        "source_interfaces": contract["source_interfaces"],
        "security_count": int(len(evidence)),
        "profile_success_count": profile_success,
        "financial_indicator_success_count": fin_success,
        "dividend_event_available_count": div_success,
        "fetch_error_count": int(len(error_df)),
        "evidence_status_counts": status_counts,
        "dimension_status_counts": dimension_status,
        "hard_failures": failures,
        "warnings": [
            "Secondary structured data is research context only and does not close primary governance review.",
            "Trailing revenue/profit growth is not earnings-expectation revision and is never scored as such.",
            "Dividend events are catalyst leads only until verified against primary issuer/HKEX disclosures."
        ],
        "candidate_pool_mutations": 0,
        "simulation_mutations": 0,
        "real_account_mutations": 0,
        "orders_created": 0,
        "trade_authority": TRADE_AUTHORITY,
    }
    decision_path = output / "HKCU_P2B_E2_DECISION.json"
    quality_path = output / "HKCU_P2B_E2_QUALITY_REPORT.json"
    write_json(decision_path, decision)
    write_json(quality_path, quality)

    outputs = [evidence_path, dimension_path, queue_path, error_path, decision_path, quality_path]
    manifest = {
        "program_id": PROGRAM_ID,
        "phase": "P2B_E2_COMPANY_SPECIFIC_EVIDENCE",
        "inputs": {
            "config/hkcu_p2b_e2_company_evidence_contract.json": sha256_file(
                repo_root / "config/hkcu_p2b_e2_company_evidence_contract.json"
            ),
            "upstream_e1_decision_sha256": sha256_file(e1_dir / "HKCU_P2B_E1_DECISION.json"),
        },
        "outputs": {p.name: sha256_file(p) for p in outputs},
        "trade_authority": TRADE_AUTHORITY,
    }
    write_json(output / "HKCU_P2B_E2_MANIFEST.json", manifest)

    if failures:
        raise SystemExit("P2B_E2_INTAKE_FAILED:" + ",".join(failures))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--repo-root", default=".")
    p.add_argument("--output", required=True)
    args = p.parse_args()
    build(Path(args.repo_root).resolve(), Path(args.output).resolve())


if __name__ == "__main__":
    main()
