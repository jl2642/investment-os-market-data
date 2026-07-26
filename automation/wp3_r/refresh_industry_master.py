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
from typing import Any
from zoneinfo import ZoneInfo

CN = ZoneInfo("Asia/Shanghai")
ENDPOINTS = [
    "https://82.push2.eastmoney.com/api/qt/clist/get",
    "https://7.push2.eastmoney.com/api/qt/clist/get",
    "https://push2.eastmoney.com/api/qt/clist/get",
]
MARKET_FILTER = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048"
FIELDS = "f12,f13,f14,f100"


def request_json(params: dict[str, Any], retries: int = 3) -> tuple[dict[str, Any], str]:
    query = urllib.parse.urlencode(params)
    errors: list[str] = []
    for endpoint in ENDPOINTS:
        for attempt in range(1, retries + 1):
            try:
                request = urllib.request.Request(
                    f"{endpoint}?{query}",
                    headers={
                        "User-Agent": "Mozilla/5.0 InvestmentOS-WP3R-IndustryMaster/2.0",
                        "Referer": "https://quote.eastmoney.com/center/gridlist.html",
                    },
                )
                with urllib.request.urlopen(request, timeout=30) as response:
                    payload = json.loads(response.read().decode("utf-8", errors="replace"))
                if payload.get("data") is None:
                    raise ValueError("PROVIDER_DATA_IS_NULL")
                return payload, endpoint
            except Exception as exc:
                errors.append(f"{endpoint}:attempt={attempt}:{type(exc).__name__}:{exc}")
                if attempt < retries:
                    time.sleep(attempt * 2)
    raise RuntimeError("|".join(errors))


def paginated_market_rows(page_size: int, max_pages: int = 100) -> tuple[list[dict[str, Any]], int, list[str]]:
    rows: list[dict[str, Any]] = []
    total = 0
    selected_endpoints: list[str] = []
    seen_codes: set[str] = set()
    for page in range(1, max_pages + 1):
        payload, endpoint = request_json(
            {
                "pn": page,
                "pz": page_size,
                "po": 1,
                "np": 1,
                "fltt": 2,
                "invt": 2,
                "fid": "f3",
                "fs": MARKET_FILTER,
                "fields": FIELDS,
            }
        )
        selected_endpoints.append(endpoint)
        data = payload.get("data") or {}
        diff = data.get("diff") or []
        if isinstance(diff, dict):
            diff = list(diff.values())
        total = int(data.get("total") or total or 0)
        if not diff:
            break
        new_rows = 0
        for row in diff:
            if not isinstance(row, dict):
                continue
            code = str(row.get("f12") or "").strip().zfill(6)
            if not code or code in seen_codes:
                continue
            seen_codes.add(code)
            rows.append(row)
            new_rows += 1
        if total and len(rows) >= total:
            break
        if new_rows == 0:
            break
        time.sleep(0.08)
    else:
        raise RuntimeError(f"PAGINATION_SAFETY_LIMIT_REACHED:rows={len(rows)}:provider_total={total}")
    return rows, total, sorted(set(selected_endpoints))


def exchange_suffix(code: str, market_id: Any) -> str:
    if code.startswith(("4", "8", "92")):
        return "BJ"
    if str(market_id) == "1" or code.startswith(("5", "6")):
        return "SH"
    return "SZ"


def normalize_security_id(code: Any, market_id: Any = None) -> str:
    digits = str(code or "").strip().split(".")[0].zfill(6)
    return f"{digits}.{exchange_suffix(digits, market_id)}"


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
    parser.add_argument("--page-size", type=int, default=200)
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    now = datetime.now(CN)
    market_path = root / "investment_os_runtime/40_EVIDENCE_AND_LINEAGE/WP3_2A/CURRENT/A_SHARE_FULL_UNIVERSE.csv"
    market = read_market_universe(market_path)
    provider_rows, provider_total, selected_endpoints = paginated_market_rows(args.page_size)

    assignments: dict[str, dict[str, Any]] = {}
    duplicate_assignments: dict[str, list[str]] = {}
    for item in provider_rows:
        code = str(item.get("f12") or "").strip().zfill(6)
        sid = normalize_security_id(code, item.get("f13"))
        if sid not in market:
            continue
        name = str(item.get("f14") or market[sid] or "").strip()
        industry_name = str(item.get("f100") or "").strip() or "UNRESOLVED"
        candidate = {
            "security_id": sid,
            "security_code": code,
            "security_name": name,
            "industry_code": industry_code(industry_name),
            "industry_name": industry_name,
            "classification_source": "EASTMONEY_F100_PRIMARY_INDUSTRY" if industry_name != "UNRESOLVED" else "WP3R_EXPLICIT_UNRESOLVED",
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

    for sid, security_name in market.items():
        if sid in assignments:
            continue
        assignments[sid] = {
            "security_id": sid,
            "security_code": sid.split(".")[0],
            "security_name": security_name,
            "industry_code": "UNRESOLVED",
            "industry_name": "UNRESOLVED",
            "classification_source": "WP3R_EXPLICIT_UNRESOLVED",
            "effective_date": now.date().isoformat(),
            "source_timestamp": now.isoformat(),
            "authority": "DATA_AND_RESEARCH_EVIDENCE_ONLY",
            "trade_authority": "NONE",
        }

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
        "provider": "EASTMONEY_F100_PRIMARY_INDUSTRY",
        "provider_endpoints_used": selected_endpoints,
        "market_filter": MARKET_FILTER,
        "requested_fields": FIELDS.split(","),
        "provider_total": provider_total,
        "provider_row_count": len(provider_rows),
        "market_security_count": len(market),
        "industry_board_count": len(industry_names),
        "provider_constituent_row_count": len(provider_rows),
        "row_count": len(final_rows),
        "industry_count": len(industry_names),
        "resolved_count": resolved_count,
        "missing_count": len(unresolved_ids),
        "missing_security_ids": unresolved_ids,
        "coverage": round(coverage, 8),
        "duplicate_industry_assignment_count": duplicate_conflict_count,
        "duplicate_industry_assignments": duplicate_assignments,
        "board_failure_count": 0,
        "board_failures": [],
        "status": "PASS_CANONICAL_INDUSTRY_MASTER_CURRENT" if passed else "BLOCKED_INDUSTRY_MASTER_COVERAGE_OR_CONFLICT",
        "csv_path": str(csv_path.relative_to(root)),
        "classification_semantics": "Eastmoney f100 primary industry name captured directly per security; deterministic internal industry code derived from the provider name",
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
