#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import pandas as pd
import requests

from fmdl5d_core import is_financial_filing
from run_fmdl5d_disclosure_financial_store import (
    HKEX_API_ENDPOINT,
    HKEX_SEARCH_PAGE,
    _extract_view_state_and_action,
    _parse_hkex_record,
    now_utc,
)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def split_windows(start: date, end: date, window_days: int = 7) -> list[tuple[date, date]]:
    if window_days <= 0:
        raise ValueError("DISCLOSURE_WINDOW_DAYS_MUST_BE_POSITIVE")
    if start > end:
        raise ValueError("DISCLOSURE_WINDOW_RANGE_INVALID")
    windows: list[tuple[date, date]] = []
    cursor = start
    while cursor <= end:
        window_end = min(end, cursor + timedelta(days=window_days - 1))
        windows.append((cursor, window_end))
        cursor = window_end + timedelta(days=1)
    return windows


def remaining_timeout(deadline_monotonic: float, configured_seconds: float) -> float:
    remaining = deadline_monotonic - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("HKEX_REQUEST_HARD_DEADLINE_EXCEEDED")
    return max(1.0, min(configured_seconds, remaining))


def fetch_hkex_window_bounded(
    session: requests.Session,
    start: date,
    end: date,
    retrieved_at: str,
    *,
    deadline_monotonic: float,
    request_timeout_seconds: float,
    api_timeout_seconds: float,
    page_size: int,
    max_pages: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if page_size <= 0 or max_pages <= 0:
        raise ValueError("HKEX_PAGINATION_POLICY_INVALID")
    from_text = start.strftime("%Y%m%d")
    to_text = end.strftime("%Y%m%d")

    page = session.get(
        HKEX_SEARCH_PAGE,
        params={
            "sortDir": "0",
            "sortByRecordDate": "on",
            "searchType": "0",
            "category": "0",
            "t1code": "-2",
            "t2Gcode": "-2",
            "t2code": "-2",
            "documentType": "-1",
            "rowRange": "0",
            "lang": "EN",
        },
        timeout=remaining_timeout(deadline_monotonic, request_timeout_seconds),
    )
    page.raise_for_status()
    view_state, form_action = _extract_view_state_and_action(page.text)
    if view_state:
        submit_url = urljoin(HKEX_SEARCH_PAGE, form_action or HKEX_SEARCH_PAGE)
        post = session.post(
            submit_url,
            data={
                "j_idt10": "j_idt10",
                "j_idt10:loadMoreRange": "100",
                "javax.faces.ViewState": view_state,
                "from": from_text,
                "to": to_text,
            },
            timeout=remaining_timeout(deadline_monotonic, request_timeout_seconds),
        )
        post.raise_for_status()

    all_records: list[dict[str, Any]] = []
    fetched = 0
    total: int | None = None
    page_count = 0
    while True:
        if page_count >= max_pages:
            raise RuntimeError(f"HKEX_PAGINATION_PAGE_CAP_EXCEEDED:{max_pages}:{fetched}:{total}")
        row_range = fetched + page_size
        response = session.get(
            HKEX_API_ENDPOINT,
            params={
                "sortDir": "0",
                "sortByOptions": "DateTime",
                "category": "0",
                "market": "SEHK",
                "stockId": "-1",
                "documentType": "-1",
                "fromDate": from_text,
                "toDate": to_text,
                "title": "",
                "searchType": "0",
                "t1code": "-2",
                "t2Gcode": "-2",
                "t2code": "-2",
                "rowRange": str(row_range),
                "lang": "E",
            },
            headers={
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Referer": HKEX_SEARCH_PAGE,
                "X-Requested-With": "XMLHttpRequest",
            },
            timeout=remaining_timeout(deadline_monotonic, api_timeout_seconds),
        )
        response.raise_for_status()
        page_count += 1
        data = response.json()
        raw_result = data.get("result")
        if not raw_result or raw_result == "null":
            break
        records = json.loads(raw_result) if isinstance(raw_result, str) else raw_result
        if not records:
            break
        if total is None:
            total = int(records[0].get("TOTAL_COUNT", len(records)))
        previous_fetched = fetched
        new_records = records[fetched:]
        for raw in new_records:
            parsed = _parse_hkex_record(raw, retrieved_at)
            if parsed:
                all_records.append(parsed)
        fetched = len(records)
        has_next = bool(data.get("hasNextRow")) and not (total is not None and fetched >= total)
        if has_next and fetched <= previous_fetched:
            raise RuntimeError(f"HKEX_PAGINATION_NO_PROGRESS:{fetched}:{total}")
        if not has_next:
            break

    diagnostics = {
        "page_count": page_count,
        "reported_total_count": total,
        "fetched_raw_record_count": fetched,
        "parsed_record_count": len(all_records),
    }
    return all_records, diagnostics


def dedupe_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in records:
        key = (str(row.get("stock_code_5d", "")), str(row.get("news_id", "")), str(row.get("filing_url", "")))
        deduped[key] = row
    return sorted(deduped.values(), key=lambda row: row.get("release_timestamp", ""))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--month-key", required=True)
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--contract", default="config/fmdl5d_hkex_disclosure_financial_contract.json")
    parser.add_argument("--window-days", type=int, default=7)
    parser.add_argument("--max-attempts", type=int, default=2)
    parser.add_argument("--attempt-deadline-seconds", type=int, default=150)
    parser.add_argument("--request-timeout-seconds", type=int, default=20)
    parser.add_argument("--api-timeout-seconds", type=int, default=35)
    parser.add_argument("--page-size", type=int, default=2500)
    parser.add_argument("--max-pages", type=int, default=8)
    args = parser.parse_args()

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    contract = json.loads(Path(args.contract).read_text(encoding="utf-8"))
    source_decision = json.loads(Path(contract["source_release"]["decision_path"]).read_text(encoding="utf-8"))
    if source_decision.get("status") != contract["source_release"]["required_status"]:
        raise ValueError(f"SOURCE_RELEASE_NOT_ACCEPTED:{source_decision.get('status')}")

    start = date.fromisoformat(args.start_date)
    end = date.fromisoformat(args.end_date)
    if args.month_key != start.strftime("%Y-%m") or args.month_key != end.strftime("%Y-%m"):
        raise ValueError(f"DISCLOSURE_MONTH_KEY_RANGE_MISMATCH:{args.month_key}:{start}:{end}")

    overlay = pd.read_csv(contract["source_release"]["semantic_overlay_path"], dtype={"stock_code_5d": str})
    overlay["stock_code_5d"] = overlay["stock_code_5d"].astype(str).str.zfill(5)
    universe_codes = set(overlay["stock_code_5d"])
    windows = split_windows(start, end, args.window_days)
    retrieved_at = now_utc()
    safe_month = args.month_key.replace("-", "_")
    prefix = f"FMDL5D_R12_DISCLOSURE_MONTH_{safe_month}"
    status_path = output / f"{prefix}_STATUS.json"
    records_path = output / f"{prefix}_RECORDS.json"

    accepted_records: list[dict[str, Any]] = []
    completed_windows: list[dict[str, Any]] = []
    failed_windows: list[dict[str, Any]] = []
    warnings: list[str] = []

    def persist(state: str) -> None:
        combined = dedupe_records(accepted_records)
        write_json(records_path, combined)
        status = {
            "program_id": "FMDL-5D-R1.2",
            "stage": "HKEX_DISCLOSURE_MONTH",
            "state": state,
            "generated_at_utc": now_utc(),
            "source_release_id": source_decision["release_id"],
            "month_key": args.month_key,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "expected_window_count": len(windows),
            "completed_window_count": len(completed_windows),
            "failed_window_count": len(failed_windows),
            "completed_windows": completed_windows,
            "failed_windows": failed_windows,
            "warning_count": len(warnings),
            "warnings": warnings,
            "accepted_financial_record_count": len(combined),
            "covered_security_count": len({row.get("stock_code_5d") for row in combined}),
            "request_policy": {
                "window_days": args.window_days,
                "max_attempts": args.max_attempts,
                "attempt_deadline_seconds": args.attempt_deadline_seconds,
                "request_timeout_seconds": args.request_timeout_seconds,
                "api_timeout_seconds": args.api_timeout_seconds,
                "page_size": args.page_size,
                "max_pages": args.max_pages,
            },
            "trade_authority": "NONE",
        }
        write_json(status_path, status)

    persist("RUNNING")
    for window_index, (window_start, window_end) in enumerate(windows):
        last_error = ""
        result_records: list[dict[str, Any]] = []
        diagnostics: dict[str, Any] = {}
        successful_attempt = 0
        for attempt in range(1, args.max_attempts + 1):
            session = requests.Session()
            session.headers.update(
                {
                    "User-Agent": "Mozilla/5.0 (compatible; InvestmentOS-FMDL5D-R1.2/1.0; research-data-pipeline)",
                    "Accept-Language": "en-US,en;q=0.9",
                }
            )
            try:
                deadline = time.monotonic() + args.attempt_deadline_seconds
                raw_records, diagnostics = fetch_hkex_window_bounded(
                    session,
                    window_start,
                    window_end,
                    retrieved_at,
                    deadline_monotonic=deadline,
                    request_timeout_seconds=args.request_timeout_seconds,
                    api_timeout_seconds=args.api_timeout_seconds,
                    page_size=args.page_size,
                    max_pages=args.max_pages,
                )
                result_records = [
                    row
                    for row in raw_records
                    if row.get("stock_code_5d") in universe_codes and is_financial_filing(str(row.get("title", "")), str(row.get("category", "")))
                ]
                successful_attempt = attempt
                last_error = ""
                break
            except Exception as exc:  # noqa: BLE001
                last_error = f"{type(exc).__name__}:{exc}"
                if attempt < args.max_attempts:
                    time.sleep(attempt * 2)
            finally:
                session.close()

        window_key = f"{window_start.isoformat()}_{window_end.isoformat()}"
        if last_error:
            warning = f"HKEX_WINDOW_FAILED:{window_key}:{last_error}"
            warnings.append(warning)
            failed_windows.append(
                {
                    "window_index": window_index,
                    "start_date": window_start.isoformat(),
                    "end_date": window_end.isoformat(),
                    "error": last_error,
                }
            )
            persist("FAILED")
            break

        accepted_records.extend(result_records)
        window_payload = {
            "window_index": window_index,
            "start_date": window_start.isoformat(),
            "end_date": window_end.isoformat(),
            "successful_attempt": successful_attempt,
            "accepted_financial_record_count": len(result_records),
            **diagnostics,
        }
        completed_windows.append(window_payload)
        write_json(output / f"{prefix}_WINDOW_{window_index:02d}_RECORDS.json", dedupe_records(result_records))
        persist("RUNNING")

    success = not failed_windows and len(completed_windows) == len(windows)
    persist("SUCCESS" if success else "FAILED")
    return 0 if success else 2


if __name__ == "__main__":
    raise SystemExit(main())
