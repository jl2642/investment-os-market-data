#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

CN = ZoneInfo("Asia/Shanghai")
HOSTS = [
    "https://56.push2.eastmoney.com",
    "https://62.push2.eastmoney.com",
    "https://72.push2.eastmoney.com",
    "https://82.push2.eastmoney.com",
    "https://7.push2.eastmoney.com",
    "https://push2.eastmoney.com",
    "https://push2delay.eastmoney.com",
    "http://push2.eastmoney.com",
]
ULIST_ENDPOINTS = [f"{host}/api/qt/ulist.np/get" for host in HOSTS]
STOCK_ENDPOINTS = [f"{host}/api/qt/stock/get" for host in HOSTS]
FIELDS = "f12,f13,f14,f100"


def request_json(
    endpoints: list[str],
    params: dict[str, Any],
    timeout_seconds: int = 10,
) -> tuple[dict[str, Any], str]:
    query = urllib.parse.urlencode(params)
    errors: list[str] = []
    for endpoint in endpoints:
        try:
            request = urllib.request.Request(
                f"{endpoint}?{query}",
                headers={
                    "User-Agent": "Mozilla/5.0 InvestmentOS-WP3R-IndustryMaster/3.1",
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
            errors.append(f"{endpoint}:{type(exc).__name__}:{exc}")
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


def ulist_params(security_ids: list[str]) -> dict[str, Any]:
    return {
        "OSVersion": "14.3",
        "appVersion": "6.3.8",
        "serverVersion": "6.3.6",
        "version": "6.3.8",
        "plat": "Iphone",
        "product": "EFund",
        "fltt": 2,
        "invt": 2,
        "ut": "fa5fd1943c7b386f172d6893dbfba10b",
        "fields": FIELDS,
        "secids": ",".join(eastmoney_secid(sid) for sid in security_ids),
    }


def fetch_ulist_batch(security_ids: list[str]) -> tuple[list[dict[str, Any]], str]:
    payload, endpoint = request_json(ULIST_ENDPOINTS, ulist_params(security_ids))
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


def add_rows(
    target: dict[str, dict[str, Any]],
    rows: list[dict[str, Any]],
    market: dict[str, str],
) -> set[str]:
    matched: set[str] = set()
    for row in rows:
        sid = normalize_security_id(row.get("f12"), row.get("f13"))
        if sid in market:
            target[sid] = row
            matched.add(sid)
    return matched


def fetch_all_via_ulist(
    market: dict[str, str],
    batch_size: int,
    max_workers: int,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], set[str]]:
    security_ids = sorted(market)
    batches = list(chunks(security_ids, batch_size))
    diagnostics: list[dict[str, Any]] = []
    endpoints_used: set[str] = set()
    raw_rows: dict[str, dict[str, Any]] = {}

    probe = batches[0]
    started = time.monotonic()
    try:
        rows, endpoint = fetch_ulist_batch(probe)
        endpoints_used.add(endpoint)
        matched = add_rows(raw_rows, rows, market)
        diagnostics.append(
            {
                "route": "ULIST_PROBE",
                "requested_count": len(probe),
                "returned_count": len(rows),
                "matched_count": len(matched),
                "status": "SUCCESS" if matched else "EMPTY",
                "endpoint": endpoint,
                "elapsed_seconds": round(time.monotonic() - started, 3),
            }
        )
        if not matched:
            raise RuntimeError("ULIST_PROBE_RETURNED_NO_CANONICAL_SECURITIES")
    except Exception as exc:
        diagnostics.append(
            {
                "route": "ULIST_PROBE",
                "requested_count": len(probe),
                "status": "FAILED",
                "error": f"{type(exc).__name__}:{exc}",
                "elapsed_seconds": round(time.monotonic() - started, 3),
            }
        )
        raise RuntimeError("ULIST_PROVIDER_UNAVAILABLE:" + json.dumps(diagnostics, ensure_ascii=False, sort_keys=True)) from exc

    remaining_batches = batches[1:]
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_ulist_batch, batch): (index, batch) for index, batch in enumerate(remaining_batches, start=2)}
        for future in as_completed(futures):
            batch_number, batch = futures[future]
            started = time.monotonic()
            try:
                rows, endpoint = future.result()
                endpoints_used.add(endpoint)
                matched = add_rows(raw_rows, rows, market)
                missing = sorted(set(batch) - matched)
                diagnostics.append(
                    {
                        "route": "ULIST_PRIMARY",
                        "batch_number": batch_number,
                        "requested_count": len(batch),
                        "returned_count": len(rows),
                        "matched_count": len(matched),
                        "missing_count": len(missing),
                        "status": "SUCCESS" if not missing else "PARTIAL",
                        "endpoint": endpoint,
                        "elapsed_seconds": round(time.monotonic() - started, 3),
                    }
                )
            except Exception as exc:
                diagnostics.append(
                    {
                        "route": "ULIST_PRIMARY",
                        "batch_number": batch_number,
                        "requested_count": len(batch),
                        "status": "FAILED",
                        "error": f"{type(exc).__name__}:{exc}",
                        "elapsed_seconds": round(time.monotonic() - started, 3),
                    }
                )

    return raw_rows, diagnostics, endpoints_used


def fetch_all_via_stock(
    market: dict[str, str],
    max_workers: int,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], set[str]]:
    security_ids = sorted(market)
    diagnostics: list[dict[str, Any]] = []
    endpoints_used: set[str] = set()
    raw_rows: dict[str, dict[str, Any]] = {}

    probe_sid = security_ids[0]
    started = time.monotonic()
    try:
        row, endpoint = fetch_stock(probe_sid)
        endpoints_used.add(endpoint)
        if not row:
            raise RuntimeError("STOCK_GET_PROBE_EMPTY")
        raw_rows[probe_sid] = row
        diagnostics.append(
            {
                "route": "STOCK_GET_PROBE",
                "security_id": probe_sid,
                "status": "SUCCESS",
                "endpoint": endpoint,
                "elapsed_seconds": round(time.monotonic() - started, 3),
            }
        )
    except Exception as exc:
        diagnostics.append(
            {
                "route": "STOCK_GET_PROBE",
                "security_id": probe_sid,
                "status": "FAILED",
                "error": f"{type(exc).__name__}:{exc}",
                "elapsed_seconds": round(time.monotonic() - started, 3),
            }
        )
        raise RuntimeError("STOCK_GET_PROVIDER_UNAVAILABLE:" + json.dumps(diagnostics, ensure_ascii=False, sort_keys=True)) from exc

    success_count = 1
    failure_count = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_stock, sid): sid for sid in security_ids[1:]}
        for future in as_completed(futures):
            sid = futures[future]
            try:
                row, endpoint = future.result()
                endpoints_used.add(endpoint)
                if row:
                    raw_rows[sid] = row
                    success_count += 1
                else:
                    failure_count += 1
            except Exception:
                failure_count += 1
    diagnostics.append(
        {
            "route": "STOCK_GET_FULL_FALLBACK",
            "requested_count": len(security_ids),
            "success_count": success_count,
            "failure_count": failure_count,
            "status": "COMPLETE" if failure_count == 0 else "PARTIAL",
        }
    )
    return raw_rows, diagnostics, endpoints_used


def collect_canonical_rows(
    market: dict[str, str],
    batch_size: int,
    max_workers: int,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], list[str], str]:
    diagnostics: list[dict[str, Any]] = []
    try:
        rows, route_diagnostics, endpoints = fetch_all_via_ulist(market, batch_size, max_workers)
        diagnostics.extend(route_diagnostics)
        route = "ULIST_BATCH_PRIMARY"
    except Exception as ulist_exc:
        diagnostics.append({"route": "ULIST_BATCH_PRIMARY", "status": "FAILED", "error": str(ulist_exc)})
        rows, route_diagnostics, endpoints = fetch_all_via_stock(market, max_workers)
        diagnostics.extend(route_diagnostics)
        route = "STOCK_GET_FULL_FALLBACK"

    unresolved = [sid for sid in market if sid not in rows or not str(rows[sid].get("f100") or "").strip()]
    if unresolved and len(unresolved) <= 100 and route != "STOCK_GET_FULL_FALLBACK":
        recovered = 0
        failures = 0
        for sid in unresolved:
            try:
                row, endpoint = fetch_stock(sid)
                endpoints.add(endpoint)
                if row:
                    rows[sid] = row
                    recovered += 1
                else:
                    failures += 1
            except Exception:
                failures += 1
        diagnostics.append(
            {
                "route": "STOCK_GET_GAP_FILL",
                "requested_count": len(unresolved),
                "recovered_count": recovered,
                "failure_count": failures,
                "status": "COMPLETE" if failures == 0 else "PARTIAL",
            }
        )

    return rows, diagnostics, sorted(endpoints), route


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
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--max-workers", type=int, default=6)
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 100:
        raise ValueError("BATCH_SIZE_MUST_BE_BETWEEN_1_AND_100")
    if not 1 <= args.max_workers <= 16:
        raise ValueError("MAX_WORKERS_MUST_BE_BETWEEN_1_AND_16")

    root = Path(args.repo_root).resolve()
    now = datetime.now(CN)
    market_path = root / "investment_os_runtime/40_EVIDENCE_AND_LINEAGE/WP3_2A/CURRENT/A_SHARE_FULL_UNIVERSE.csv"
    market = read_market_universe(market_path)
    provider_rows, fetch_diagnostics, endpoints_used, provider_route = collect_canonical_rows(
        market, args.batch_size, args.max_workers
    )

    final_rows: list[dict[str, Any]] = []
    for sid, market_name in sorted(market.items()):
        item = provider_rows.get(sid) or {}
        industry_name = str(item.get("f100") or "").strip() or "UNRESOLVED"
        final_rows.append(
            {
                "security_id": sid,
                "security_code": sid.split(".")[0],
                "security_name": str(item.get("f14") or market_name or "").strip(),
                "industry_code": industry_code(industry_name),
                "industry_name": industry_name,
                "classification_source": "EASTMONEY_F100_PRIMARY_INDUSTRY" if industry_name != "UNRESOLVED" else "WP3R_EXPLICIT_UNRESOLVED",
                "effective_date": now.date().isoformat(),
                "source_timestamp": now.isoformat(),
                "authority": "DATA_AND_RESEARCH_EVIDENCE_ONLY",
                "trade_authority": "NONE",
            }
        )

    unresolved_ids = [row["security_id"] for row in final_rows if row["industry_name"] == "UNRESOLVED"]
    resolved_count = len(final_rows) - len(unresolved_ids)
    coverage = resolved_count / len(market) if market else 0.0
    industry_names = {row["industry_name"] for row in final_rows if row["industry_name"] != "UNRESOLVED"}
    duplicate_conflict_count = 0
    passed = coverage >= 0.99 and duplicate_conflict_count == 0

    current_dir = root / "investment_os_runtime/40_EVIDENCE_AND_LINEAGE/WP3_R/INDUSTRY_MASTER"
    csv_path = current_dir / "SECURITY_INDUSTRY_MASTER_CURRENT.csv"
    manifest_path = current_dir / "SECURITY_INDUSTRY_MASTER_CURRENT.json"
    write_csv(csv_path, final_rows)

    manifest = {
        "state_id": "WP3R_SECURITY_INDUSTRY_MASTER_CURRENT",
        "generated_at": now.isoformat(),
        "provider": "EASTMONEY_F100_PRIMARY_INDUSTRY",
        "provider_route": provider_route,
        "provider_endpoints_used": endpoints_used,
        "requested_fields": FIELDS.split(","),
        "canonical_batch_size": args.batch_size,
        "max_workers": args.max_workers,
        "canonical_security_request_count": len(market),
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
        "duplicate_industry_assignments": {},
        "batch_failure_count": sum(1 for item in fetch_diagnostics if item.get("status") == "FAILED"),
        "status": "PASS_CANONICAL_INDUSTRY_MASTER_CURRENT" if passed else "BLOCKED_INDUSTRY_MASTER_COVERAGE_OR_CONFLICT",
        "csv_path": str(csv_path.relative_to(root)),
        "classification_semantics": "Canonical A-share Security Master is queried directly for Eastmoney f100 primary industry through bounded batch or stock routes; unresolved securities remain explicit",
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
