from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("Asia/Shanghai")
OUT = ROOT / "outputs/occ_r2/financial/current"

STATEMENT_RELEASE = ROOT / "outputs/financials/statements/current/FMDL3B4_RELEASE.json"
STATEMENT_CATALOG = ROOT / "outputs/financials/statements/current/FMDL3B4_STATEMENT_CATALOG.csv"
FACTOR_RELEASE = ROOT / "outputs/financial_factors/engine/current/FMDL3CB_RELEASE.json"
HARDENING_RELEASE = ROOT / "outputs/financial_factors/hardening/current/FMDL3CC_RELEASE.json"
SCORE_RELEASE = ROOT / "outputs/financial_factors/score/current/FMDL3CD_RELEASE.json"
SCORE_DECISION = ROOT / "outputs/financial_factors/score/current/FMDL3CD_DECISION.json"
MARKET_RELEASE = ROOT / "outputs/current/CURRENT_RELEASE.json"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_normalized_facts() -> pd.DataFrame:
    catalog = pd.read_csv(STATEMENT_CATALOG, encoding="utf-8-sig")
    paths = [
        ROOT / path
        for path in catalog.loc[
            catalog["dataset_role"].eq("statement_normalized"), "path"
        ].astype(str)
    ]
    if len(paths) != 32:
        raise SystemExit(f"EXPECTED_32_STATEMENT_SHARDS_GOT_{len(paths)}")
    parts = []
    for path in paths:
        frame = pd.read_parquet(path)
        if len(frame):
            parts.append(frame)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def main() -> int:
    statement = read_json(STATEMENT_RELEASE)
    factor = read_json(FACTOR_RELEASE)
    hardening = read_json(HARDENING_RELEASE)
    score = read_json(SCORE_RELEASE)
    score_decision = read_json(SCORE_DECISION)
    market = read_json(MARKET_RELEASE)
    facts = load_normalized_facts()

    market_date = str(market.get("as_of_date") or "")
    cutoff = pd.Timestamp(f"{market_date} 15:00:00", tz="Asia/Shanghai").tz_convert("UTC")
    if len(facts):
        available = pd.to_datetime(facts.get("available_from"), errors="coerce", utc=True)
        periods = pd.to_datetime(facts.get("period_end"), errors="coerce")
        eligible = available.le(cutoff)
        decision_grade = facts.get("decision_grade_eligible")
        if decision_grade is not None:
            eligible = eligible & decision_grade.fillna(False).astype(bool)
        period_watermark = (
            periods[eligible].max().date().isoformat()
            if bool(eligible.any()) and pd.notna(periods[eligible].max())
            else None
        )
        symbol_count = int(facts.loc[eligible, "symbol"].astype(str).nunique())
        eligible_fact_count = int(eligible.sum())
    else:
        period_watermark = None
        symbol_count = 0
        eligible_fact_count = 0

    releases = {
        "statement_release_id": statement.get("release_id"),
        "financial_factor_release_id": factor.get("release_id"),
        "financial_hardening_release_id": hardening.get("release_id"),
        "financial_score_release_id": score.get("release_id"),
    }
    required_statuses = {
        "statement": "FMDL3B4_POINT_IN_TIME_STATEMENT_STORE_ACCEPTED",
        "factor": "FMDL3CB_FINANCIAL_FACTOR_ENGINE_MVP_ACCEPTED",
        "hardening": "FMDL3CC_FINANCIAL_FACTOR_VALIDATION_AND_HARDENING_ACCEPTED",
        "score": "FMDL3CD_FINANCIAL_SCORE_AND_INVESTMENT_OS_INTERFACE_ACCEPTED",
    }
    observed_statuses = {
        "statement": statement.get("status"),
        "factor": factor.get("status"),
        "hardening": hardening.get("status"),
        "score": score.get("status"),
    }
    checks = {
        "MARKET_CURRENT_ACCEPTED": market.get("status") in {"PUBLISHED", "PUBLISHED_WITH_WARNINGS"},
        "STATEMENT_CURRENT_ACCEPTED": observed_statuses["statement"] == required_statuses["statement"],
        "FACTOR_CURRENT_ACCEPTED": observed_statuses["factor"] == required_statuses["factor"],
        "HARDENING_CURRENT_ACCEPTED": observed_statuses["hardening"] == required_statuses["hardening"],
        "SCORE_CURRENT_ACCEPTED": observed_statuses["score"] == required_statuses["score"],
        "REPORT_PERIOD_WATERMARK_PRESENT": period_watermark is not None,
        "DECISION_GRADE_FACTS_PRESENT": eligible_fact_count > 0,
        "DECISION_GRADE_SYMBOLS_PRESENT": symbol_count > 0,
        "ZERO_TRADE_AUTHORITY": all(
            str(payload.get("trade_authority") or "NONE") == "NONE"
            for payload in (statement, factor, hardening, score, score_decision)
        ),
    }
    failures = [name for name, passed in checks.items() if not passed]
    payload = {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "status": "PASS" if not failures else "FAIL",
        "qc_status": "PASS_FINANCIAL_BASELINE_REBUILT" if not failures else "FAIL",
        "market_as_of_date": market_date,
        "financial_report_period_watermark": period_watermark,
        "decision_grade_fact_count": eligible_fact_count,
        "decision_grade_symbol_count": symbol_count,
        "releases": releases,
        "score_metrics": score_decision.get("metrics", {}),
        "checks": checks,
        "hard_failures": failures,
        "controlled_limitations": [
            "R2B1_REFRESHES_STATEMENT_FACTS_FACTORS_HARDENING_AND_SCORE_ONLY",
            "CAPITALIZATION_AND_EXACT_VALUATION_REBUILD_REMAIN_OCC_R2B2",
            "NO_CANDIDATE_PORTFOLIO_OR_ORDER_MUTATION",
        ],
        "authority": "DATA_AND_RESEARCH_EVIDENCE_ONLY",
        "trade_authority": "NONE",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "FINANCIAL_CONTEXT_RELEASE.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
