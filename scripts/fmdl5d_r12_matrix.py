#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_month_matrix(start: date, end: date) -> list[dict[str, str]]:
    if start > end:
        raise ValueError("DISCLOSURE_MONTH_RANGE_INVALID")
    rows: list[dict[str, str]] = []
    cursor = date(start.year, start.month, 1)
    while cursor <= end:
        next_month = date(cursor.year + 1, 1, 1) if cursor.month == 12 else date(cursor.year, cursor.month + 1, 1)
        month_start = max(start, cursor)
        month_end = min(end, next_month - timedelta(days=1))
        rows.append(
            {
                "month_key": cursor.strftime("%Y-%m"),
                "start_date": month_start.isoformat(),
                "end_date": month_end.isoformat(),
            }
        )
        cursor = next_month
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", default="config/fmdl5d_hkex_disclosure_financial_contract.json")
    parser.add_argument("--start-date", default="")
    parser.add_argument("--end-date", default="")
    parser.add_argument("--output", required=True)
    parser.add_argument("--github-output", default="")
    args = parser.parse_args()

    contract = read_json(Path(args.contract))
    source_decision = read_json(Path(contract["source_release"]["decision_path"]))
    if source_decision.get("status") != contract["source_release"]["required_status"]:
        raise ValueError(f"SOURCE_RELEASE_NOT_ACCEPTED:{source_decision.get('status')}")

    start = date.fromisoformat(args.start_date or contract["period_policy"]["default_start_date"])
    source_metrics = source_decision.get("metrics", {})
    inferred_end = source_metrics.get("max_market_date") or source_metrics.get("market_max_date")
    if not inferred_end and not args.end_date:
        raise ValueError("SOURCE_RELEASE_MARKET_MAX_DATE_MISSING")
    end = date.fromisoformat(args.end_date or str(inferred_end))
    months = build_month_matrix(start, end)
    matrix = {"include": months}
    payload = {
        "program_id": "FMDL-5D-R1.2",
        "stage": "HKEX_DISCLOSURE_MONTH_MATRIX",
        "source_release_id": source_decision["release_id"],
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "expected_month_count": len(months),
        "months": months,
        "trade_authority": "NONE",
    }
    write_json(Path(args.output), payload)

    if args.github_output:
        github_output = Path(args.github_output)
        with github_output.open("a", encoding="utf-8") as handle:
            handle.write(f"matrix={json.dumps(matrix, separators=(',', ':'))}\n")
            handle.write(f"expected_month_count={len(months)}\n")
    else:
        print(json.dumps(matrix, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
