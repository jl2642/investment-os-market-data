#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

CN = ZoneInfo("Asia/Shanghai")
ULIST_ENDPOINTS = [
    "https://push2.eastmoney.com/api/qt/ulist.np/get",
    "https://82.push2.eastmoney.com/api/qt/ulist.np/get",
    "https://7.push2.eastmoney.com/api/qt/ulist.np/get",
]
STOCK_ENDPOINTS = [
    "https://push2.eastmoney.com/api/qt/stock/get",
    "https://82.push2.eastmoney.com/api/qt/stock/get",
    "https://7.push2.eastmoney.com/api/qt/stock/get",
]
FIELDS = "f12,f13,f14,f100"


def request_json(
    endpoints: list[str],
    params: dict[str, Any],
    retries: int = 2,
    timeout_seconds: int = 15,
) -> tuple[dict[str, Any], str]:
    query = urllib.parse.urlencode(params)
    errors: list[str] = []
    for endpoint in endpoints:
        for attempt in range(1, retries + 1):
            try:
                request = urllib.request.Request(
                    f"{endpoint}?{query}",
                    headers={
                        "User-Agent": "Mozilla/5.0 InvestmentOS-WP3R-IndustryMaster/3.0",
                        "Referer": "https://quote.eastmoney.com/center/gridlist.html",
                        "Accept": "application/json,text/plain,*/*",
                    },
                )
                with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                    payload = json.loads(response.read().decode("utf-8", errors="replace"))
                if payload.get("data") is None:
                    raise ValueError("PROVIDER_DATA_IS_NULL")
                return payload, endpoint
            except Exception as exc:
                errors.append(f"{endpoint}:attempt={attempt}:{type(exc).__name__}:{exc}")
                if attempt < retries:
                    time.sleep(attempt)
    raise RuntimeError("|".join(errors))


def exchange_suffix(code: str, market_id: Any = None) -> str:
    if code.startswith(("4", "8", "92")):
        return "BJ"
    if str(market_id) == "1" or code.startswith(("5", "6")):
        return "SH"
    return "SZ"


def normalize_security_id(code: Any, market_id: Any = None) -> str:
    digits = str(code or "").strip().split(".")[0].zfill(6)
    return f"{digits}.{exchange_suffix(digits, market_id)}"


def eastmoney_secid(security_id: str) -> str:
    code, suffix = security_id.split(".", 1)
    return f"{'1' if suffix == 'SH' else '0'}.{code}"


def read_market_universe(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = {str(field).strip().lstrip("\ufeff"): field for field in (reader.fieldnames or []) if field is not None}
        code_field = fields.get("security_code")
        name_field = fields.get("security_name")
        if code_field is None:
            raise ValueError("A_SHARE_CURRENT_SECURITY_CODE_COLUMN_MISSING:" + ",".join(map(str, reader.fieldnames or [])))
        result: dict[str, str] = {}
        for row in reader:
            raw = str(row.get(code_field) or "").strip()
            if not raw:
                continue
            sid = normalize_security_id(raw)
            result[sid] = str(row.get(name_field) or "").strip() if name_field else ""
    if len(result) < 5000:
        raise ValueError(f"A_SHARE_CURRENT_SECURITY_ID_COUNT_TOO_LOW:{len(result)}")
    return result


def chunks(values: list[str], size: int) -> Iterable[list[str]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


def parse_diff(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data") or {}
    diff = data.get("diff") or []
    if isinstance(diff, dict):
        diff = list(diff.values())
    return [row for row in diff if isinstance(row, dict)]


def fetch_ulist_batch(security_ids: list[str]) -> tuple[list[dict[str, Any]], str]:
    payload, endpoint = request_json(
        ULIST_ENDPOINTS,
        {
            "fltt": 2,
            "invt": 2,
            "ut": "fa5fd1943c7b386f172d6893dbfba10b",
            "fields": FIELDS,
            "secids": ",".join(eastmoney_secid(sid) for sid in security_ids),
        },
    )
    return parse_diff(payload), endpoint


def fetch_stock(security_id: str) -> tuple[dict[str, Any] | None, str]:
    payload, endpoint = request_json(
        STOCK_ENDPOINTS,
        {
            "fltt": 2,
            "invt": 2,
            "ut": "fa5fd1943c7b386f172d6893dbfba10b",
            "fields": FIELDS,
            "secid": eastmoney_secid(security_id),
        },
    )
    data = payload.get("data")
    return (data if isinstance(data, dict) else None), endpoint


def collect_canonical_industry_rows(
    market: dict[str, str],
    batch_size: int,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], list[str], int]:
    security_ids = sorted(market)
    raw_rows: dict[str, dict[str, Any]] = {}
    diagnostics: list[dict[str, Any]] = []
    endpoints_used: set[str] = set()
    returned_rows = 0

    failed_ids: list[str] = []
    for batch_number, batch in enumerate(chunks(security_ids, batch_size), start=1):
        started = time.monotonic()
        try:
            rows, endpoint = fetch_ulist_batch(batch)
            endpoints_used.add(endpoint)
            returned_rows += len(rows)
            matched: set[str] = set()
            for row in rows:
                sid = normalize_security_id(row.get("f12"), row.get("f13"))
                if sid in market:
                    raw_rows[sid] = row
                    matched.add(sid)
            missing = sorted(set(batch) - matched)
            failed_ids.extend(missing)
            diagnostics.append(
                {
                    "route": "ULIST_PRIMARY",
                    "batch_number": batch_number,
                    "requested_count": len(batch),
                    "returned_count": len(rows),
                    "matched_count": len(matched),
                    "missing_count": len(missing),
                    "status": "SUCCESS" if not missing else "PARTIAL",
                    "elapsed_seconds": round(time.monotonic() - started, 3),
                }
            )
        except Exception as exc:
            failed_ids.extend(batch)
            diagnostics.append(
                {
                    "route": "ULIST_PRIMARY",
                    "batch_number": batch_number,
                    "requested_count": len(batch),
                    "returned_count": 0,
                    "matched_count": 0,
                    "missing_count": len(batch),
                    "status": "FAILED",
                    "error": f"{type(exc).__name__}:{exc}",
                    "elapsed_seconds": round(time.monotonic() - started, 3),
                }
            )
        time.sleep(0.05)

    retry_ids = sorted(set(failed_ids))
    if retry_ids:
        for batch_number, batch in enumerate(chunks(retry_ids, 20), start=1):
            started = time.monotonic()
            try:
                rows, endpoint = fetch_ulist_batch(batch)
                endpoints_used.add(endpoint)
                returned_rows += len(rows)
                matched: set[str] = set()
                for row in rows:
                    sid = normalize_security_id(row.get("f12"), row.get("f13"))
                    if sid in market:
                        raw_rows[sid] = row
                        matched.add(sid)
                diagnostics.append(
                    {
                        "route": "ULIST_SMALL_BATCH_RETRY",
                        "batch_number": batch_number,
                        "requested_count": len(batch),
                        "returned_count": len(rows),
                        "matched_count": len(matched),
                        "missing_count": len(set(batch) - matched),
                        "status": "SUCCESS" if set(batch) <= matched else "PARTIAL",
                        "elapsed_seconds": round(time.monotonic() - started, 3),
                    }
                )
            except Exception as exc:
                diagnostics.append(
                    {
                        "route": "ULIST_SMALL_BATCH_RETRY",
                        "batch_number": batch_number,
                        "requested_count": len(batch),
                        "returned_count": 0,
                        "matched_count": 0,
                        "missing_count": len(batch),
                        "status": "FAILED",
                        "error": f"{type(exc).__name__}:{exc}",
                        "elapsed_seconds": round(time.monotonic() - started, 3),
                    }
                )
            time.sleep(0.05)

    unresolved_or_blank = [
        sid
        for sid in security_ids
        if sid not in raw_rows or not str(raw_rows[sid].get("f100") or "").strip()
    ]
    if len(unresolved_or_blank) <= 100:
        for sid in unresolved_or_blank:
            started = time.monotonic()
            try:
                row, endpoint = fetch_stock(sid)
                endpoints_used.add(endpoint)
                if row:
                    raw_rows[sid] = row
                    returned_rows += 1
                diagnostics.append(
                    {
                        "route": "STOCK_GET_FINAL_FALLBACK",
                        "security_id": sid,
                        "status": "SUCCESS" if row else "EMPTY",
                        "elapsed_seconds": round(time.monotonic() - started, 3),
                    }
                )
            except Exception as exc:
                diagnostics.append(
                    {
                        "route": "STOCK_GET_FINAL_FALLBACK",
                        "security_id": sid,
                        "status": "FAILED",
                        "error": f"{type(exc).__name__}:{exc}",
                        "elapsed_seconds": round(time.monotonic() - started, 3),
                    }
                )
            time.sleep(0.02)
    elif unresolved_or_blank:
        diagnostics.append(
            {
                "route": "STOCK_GET_FINAL_FALLBACK",
                "status": "SKIPPED_TOO_MANY_UNRESOLVED",
                "unresolved_count": len(unresolved_or_blank),
                "maximum_individual_fallback": 100,
            }
        )

    return raw_rows, diagnostics, sorted(endpoints_used), returned_rows


def industry_code(industry_name: str) -> str:
    if industry_name == "UNRESOLVED":
        return "UNRESOLVED"
    return "EMF100_" + hashlib.sha256(industry_name.encode("utf-8")).hexdigest()[:12].upper()


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "security_id",
        "security_code",
        "security_name",
        "industry_code",
        "industry_name",
        "classification_source",
        "effective_date",
        "source_timestamp",
        "authority",
        "trade_authority",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--batch-size", type=int, default=80)
    args = parser.parse_args()
    if args.batch_size < 1 or args.batch_size > 100:
        raise ValueError("BATCH_SIZE_MUST_BE_BETWEEN_1_AND_100")

    root = Path(args.repo_root).resolve()
    now = datetime.now(CN)
    market_path = root / "investment_os_runtime/40_EVIDENCE_AND_LINEAGE/WP3_2A/CURRENT/A_SHARE_FULL_UNIVERSE.csv"
    market = read_market_universe(market_path)
    provider_rows, fetch_diagnostics, endpoints_used, provider_returned_rows = collect_canonical_industry_rows(
        market, args.batch_size
    )

    assignments: dict[str, dict[str, Any]] = {}
    duplicate_assignments: dict[str, list[str]] = {}
    for sid, market_name in market.items():
        item = provider_rows.get(sid) or {}
        code = sid.split(".")[0]
        name = str(item.get("f14") or market_name or "").strip()
        industry_name = str(item.get("f100") or "").strip() or "UNRESOLVED"
        candidate = {
            "security_id": sid,
            "security_code": code,
            "security_name": name,
            "industry_code": industry_code(industry_name),
            "industry_name": industry_name,
            "classification_source": "EASTMONEY_ULIST_F100_PRIMARY_INDUSTRY" if industry_name != "UNRESOLVED" else "WP3R_EXPLICIT_UNRESOLVED",
            "effective_date": now.date().isoformat(),
            "source_timestamp": now.isoformat(),
            "authority": "DATA_AND_RESEARCH_EVIDENCE_ONLY",
            "trade_authority": "NONE",
        }
        prior = assignments.get(sid)
        if prior and prior["industry_name"] != candidate["industry_name"]:
            duplicate_assignments.setdefault(sid, [prior["industry_name"]]).append(candidate["industry_name"])
            continue
        assignments[sid] = candidate

    final_rows = sorted(assignments.values(), key=lambda row: row["security_id"])
    unresolved_ids = sorted(row["security_id"] for row in final_rows if row["industry_name"] == "UNRESOLVED")
    resolved_count = len(final_rows) - len(unresolved_ids)
    coverage = resolved_count / len(market) if market else 0.0
    duplicate_conflict_count = len(duplicate_assignments)
    industry_names = {row["industry_name"] for row in final_rows if row["industry_name"] != "UNRESOLVED"}
    passed = coverage >= 0.99 and duplicate_conflict_count == 0

    current_dir = root / "investment_os_runtime/40_EVIDENCE_AND_LINEAGE/WP3_R/INDUSTRY_MASTER"
    csv_path = current_dir / "SECURITY_INDUSTRY_MASTER_CURRENT.csv"
    manifest_path = current_dir / "SECURITY_INDUSTRY_MASTER_CURRENT.json"
    write_csv(csv_path, final_rows)

    manifest = {
        "state_id": "WP3R_SECURITY_INDUSTRY_MASTER_CURRENT",
        "generated_at": now.isoformat(),
        "provider": "EASTMONEY_ULIST_F100_PRIMARY_INDUSTRY",
        "provider_endpoints_used": endpoints_used,
        "requested_fields": FIELDS.split(","),
        "canonical_batch_size": args.batch_size,
        "canonical_security_request_count": len(market),
        "provider_returned_row_count_including_retries": provider_returned_rows,
        "unique_provider_security_count": len(provider_rows),
        "fetch_diagnostics": fetch_diagnostics,
        "market_security_count": len(market),
        "industry_board_count": len(industry_names),
        "row_count": len(final_rows),
        "industry_count": len(industry_names),
        "resolved_count": resolved_count,
        "missing_count": len(unresolved_ids),
        "missing_security_ids": unresolved_ids,
        "coverage": round(coverage, 8),
        "duplicate_industry_assignment_count": duplicate_conflict_count,
        "duplicate_industry_assignments": duplicate_assignments,
        "batch_failure_count": sum(1 for item in fetch_diagnostics if item.get("status") == "FAILED"),
        "status": "PASS_CANONICAL_INDUSTRY_MASTER_CURRENT" if passed else "BLOCKED_INDUSTRY_MASTER_COVERAGE_OR_CONFLICT",
        "csv_path": str(csv_path.relative_to(root)),
        "classification_semantics": "Canonical A-share Security Master is queried directly in bounded Eastmoney ulist batches for f100 primary industry; unresolved securities are retained explicitly",
        "unresolved_policy": "EXPLICIT_ROW_RETAINED_AND_INDUSTRY_RELATIVE_RANKING_BLOCKED_FOR_UNRESOLVED_SECURITY",
        "automatic_candidate_mutations": 0,
        "orders": 0,
        "trade_authority": "NONE",
    }
    write_json(manifest_path, manifest)
    print(json.dumps(manifest, ensure_ascii=False, sort_keys=True))
    if not passed:
        raise SystemExit(
            "INDUSTRY_MASTER_FAIL_CLOSED:"
            f"coverage={coverage:.8f}:unresolved={len(unresolved_ids)}:duplicates={duplicate_conflict_count}"
        )


if __name__ == "__main__":
    main()
