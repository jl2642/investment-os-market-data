from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("Asia/Shanghai")
AUTHORITY = "DATA_AND_RESEARCH_EVIDENCE_ONLY"
TRADE_AUTHORITY = "NONE"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


def build_summary(
    *,
    market_context: dict,
    financial_context: dict,
    capitalization_release: dict,
    capitalization_decision: dict,
    valuation_release: dict,
    valuation_decision: dict,
    market_source_branch: str,
    market_source_commit: str,
    financial_source_branch: str,
    financial_source_commit: str,
) -> dict:
    market_watermark = str(market_context["data_watermark"])
    financial_market_watermark = str(financial_context["data_watermark"])
    report_watermark = str(financial_context["financial_report_period_watermark"])
    cap_market_date = str(capitalization_release["source_release"]["as_of_date"])
    metrics = dict(valuation_decision.get("metrics") or {})
    metric_valid_counts = dict(metrics.get("metric_valid_counts") or {})

    checks = {
        "MARKET_CURRENT_ACCEPTED": market_context.get("status") == "PASS",
        "FINANCIAL_CURRENT_ACCEPTED": financial_context.get("status") == "PASS",
        "MARKET_FINANCIAL_WATERMARK_MATCH": market_watermark == financial_market_watermark,
        "CAPITALIZATION_ACCEPTED": capitalization_decision.get("status")
        == "FMDL3DB_EFFECTIVE_SHARE_COUNT_AND_CAPITALIZATION_ENGINE_ACCEPTED",
        "CAPITALIZATION_MARKET_WATERMARK_MATCH": cap_market_date == market_watermark,
        "VALUATION_ACCEPTED": valuation_decision.get("status")
        == "FMDL3DC_VALUATION_ENGINE_CURRENT_ACCEPTED",
        "VALUATION_MARKET_WATERMARK_MATCH": str(metrics.get("market_as_of_date"))
        == market_watermark,
        "VALUATION_USES_REFRESHED_FINANCIAL_FACTOR_RELEASE": str(
            metrics.get("factor_engine_release_id")
        )
        == str(financial_context["releases"]["financial_factor_release_id"]),
        "ZERO_FUTURE_SELECTED_DENOMINATOR": int(
            metrics.get("future_selected_denominator_count", -1)
        )
        == 0,
        "EV_SALES_RESTORED": int(metric_valid_counts.get("VAL_EV_SALES_TTM", 0)) > 0,
        "EV_OPERATING_INCOME_RESTORED": int(
            metric_valid_counts.get("VAL_EV_OPERATING_INCOME_TTM", 0)
        )
        > 0,
        "ZERO_TRADE_AUTHORITY": market_context.get("trade_authority") == "NONE"
        and financial_context.get("trade_authority") == "NONE"
        and capitalization_decision.get("trade_authority") == "NONE"
        and valuation_decision.get("trade_authority") == "NONE",
    }
    failures = [name for name, passed in checks.items() if not bool(passed)]
    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "status": "PASS" if not failures else "FAIL",
        "qc_status": "PASS_EXACT_VALUATION_REBUILT" if not failures else "FAIL_EXACT_VALUATION_REBUILD",
        "market_as_of_date": market_watermark,
        "financial_report_period_watermark": report_watermark,
        "financial_event_propagation": "COMPLETE" if not failures else "INCOMPLETE",
        "source_lineage": {
            "market_source_branch": market_source_branch,
            "market_source_commit": market_source_commit,
            "financial_source_branch": financial_source_branch,
            "financial_source_commit": financial_source_commit,
        },
        "releases": {
            "capitalization_release_id": capitalization_release.get("release_id"),
            "valuation_release_id": valuation_release.get("release_id"),
            "financial_factor_release_id": metrics.get("factor_engine_release_id"),
        },
        "valuation_metrics": metrics,
        "checks": checks,
        "hard_failures": failures,
        "controlled_limitations": [
            "R2B2_REBUILDS_CAPITALIZATION_AND_EXACT_VALUATION_ONLY",
            "FINANCIAL_FACTOR_AND_SCORE_METHODOLOGY_REMAINS_FROZEN",
            "NO_CANDIDATE_PORTFOLIO_OR_ORDER_MUTATION",
        ],
        "authority": AUTHORITY,
        "trade_authority": TRADE_AUTHORITY,
    }


def main() -> int:
    market_context = load_json(Path(os.environ["MARKET_CONTEXT_PATH"]))
    financial_context = load_json(Path(os.environ["FINANCIAL_CONTEXT_PATH"]))
    capitalization_release = load_json(
        ROOT / "outputs/capitalization/current/FMDL3DB_RELEASE.json"
    )
    capitalization_decision = load_json(
        ROOT / "outputs/capitalization/current/FMDL3DB_DECISION.json"
    )
    valuation_release = load_json(ROOT / "outputs/valuation/engine/current/FMDL3DC_RELEASE.json")
    valuation_decision = load_json(
        ROOT / "outputs/valuation/engine/current/FMDL3DC_DECISION.json"
    )

    summary = build_summary(
        market_context=market_context,
        financial_context=financial_context,
        capitalization_release=capitalization_release,
        capitalization_decision=capitalization_decision,
        valuation_release=valuation_release,
        valuation_decision=valuation_decision,
        market_source_branch=os.environ["MARKET_SOURCE_BRANCH"],
        market_source_commit=os.environ["MARKET_SOURCE_COMMIT"],
        financial_source_branch=os.environ["FINANCIAL_SOURCE_BRANCH"],
        financial_source_commit=os.environ["FINANCIAL_SOURCE_COMMIT"],
    )
    output = ROOT / "outputs/occ_r2/valuation/current/FINANCIAL_VALUATION_CONTEXT_RELEASE.json"
    write_json(output, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
