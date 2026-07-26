#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

CN = ZoneInfo("Asia/Shanghai")
UT = "bd1d9ddb04089700cf9c27f6f7426281"
BOARD_ENDPOINTS = [
    "https://17.push2.eastmoney.com/api/qt/clist/get",
    "https://push2.eastmoney.com/api/qt/clist/get",
]
CONSTITUENT_ENDPOINTS = [
    "https://29.push2.eastmoney.com/api/qt/clist/get",
    "https://push2.eastmoney.com/api/qt/clist/get",
]


def request_json(
    endpoints: list[str],
    params: dict[str, Any],
    *,
    retries: int = 3,
) -> dict[str, Any]:
    query = urllib.parse.urlencode(params)
    errors: list[str] = []
    for endpoint in endpoints:
        for attempt in range(1, retries + 1):
            try:
                request = urllib.request.Request(
                    f"{endpoint}?{query}",
                    headers={
                        "User-Agent": "Mozilla/5.0 InvestmentOS-WP3R/1.0",
                        "Referer": "https://quote.eastmoney.com/center/boardlist.html#industry_board",
                    },
                )
                with urllib.request.urlopen(request, timeout=30) as response:
                    payload = json.loads(response.read().decode("utf-8", errors="replace"))
                if payload.get("data") is None:
                    raise ValueError("PROVIDER_DATA_IS_NULL")
                return payload
            except Exception as exc:
                errors.append(f"{endpoint}:attempt={attempt}:{type(exc).__name__}:{exc}")
                if attempt < retries:
                    time.sleep(attempt * 2)
    raise RuntimeError("|".join(errors))


def paginated_rows(
    endpoints: list[str],
    base_params: dict[str, Any],
    *,
    page_size: int,
    max_pages: int = 100,
) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    total = 0
    for page in range(1, max_pages + 1):
        params = dict(base_params)
        params.update({"pn": page, "pz": page_size})
        payload = request_json(endpoints, params)
        data = payload.get("data") or {}
        diff = data.get("diff") or []
        if isinstance(diff, dict):
            diff = list(diff.values())
        total = int(data.get("total") or total or 0)
        if not diff:
            break
        rows.extend(row for row in diff if isinstance(row, dict))
        if len(diff) < page_size or (total and len(rows) >= total):
            break
        time.sleep(0.05)
    else:
        raise RuntimeError("PAGINATION_SAFETY_LIMIT_REACHED")
    return rows, total


def exchange_suffix(code: str, market_id: Any) -> str:
    if code.startswith(("4", "8", "92")):
        return "BJ"
    if str(market_id) == "1" or code.startswith(("5", "6")):
        return "SH"
    return "SZ"


def normalize_security_id(code: Any, market_id: Any = None) -> str:
    digits = str(code or "").strip().split(".")[0].zfill(6)
    return f"{digits}.{exchange_suffix(digits, market_id)}"


def read_market_ids(path: Path) -> set[str]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if "security_code" not in (reader.fieldnames or []):
            raise ValueError("A_SHARE_CURRENT_SECURITY_CODE_COLUMN_MISSING")
        return {
            normalize_security_id(row["security_code"])
            for row in reader
            if str(row.get("security_code") or "").strip()
        }


def fetch_industry_boards(page_size: int) -> list[dict[str, str]]:
    rows, provider_total = paginated_rows(
        BOARD_ENDPOINTS,
        {
            "po": 1,
            "np": 1,
            "ut": UT,
            "fltt": 2,
            "invt": 2,
            "fid": "f3",
            "fs": "m:90 t:2 f:!50",
            "fields": "f12,f14",
        },
        page_size=page_size,
        max_pages=10,
    )
    boards = sorted(
        {
            str(row.get("f12") or "").strip(): str(row.get("f14") or "").strip()
            for row in rows
            if str(row.get("f12") or "").strip() and str(row.get("f14") or "").strip()
        }.items()
    )
    if len(boards) < 50 or (provider_total and len(boards) < min(provider_total, 50)):
        raise RuntimeError(
            f"INDUSTRY_BOARD_LIST_INCOMPLETE:boards={len(boards)}:provider_total={provider_total}"
        )
    return [{"industry_code": code, "industry_name": name} for code, name in boards]


def fetch_board_constituents(board_code: str, page_size: int) -> list[dict[str, Any]]:
    rows, _ = paginated_rows(
        CONSTITUENT_ENDPOINTS,
        {
            "po": 1,
            "np": 1,
            "ut": UT,
            "fltt": 2,
            "invt": 2,
            "fid": "f3",
            "fs": f"b:{board_code} f:!50",
            "fields": "f12,f13,f14",
        },
        page_size=page_size,
        max_pages=20,
    )
    return rows


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
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--board-page-size", type=int, default=100)
    parser.add_argument("--constituent-page-size", type=int, default=100)
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    now = datetime.now(CN)
    market_path = root / "investment_os_runtime/40_EVIDENCE_AND_LINEAGE/WP3_2A/CURRENT/A_SHARE_FULL_UNIVERSE.csv"
    market_ids = read_market_ids(market_path)
    boards = fetch_industry_boards(args.board_page_size)

    assignments: dict[str, dict[str, Any]] = {}
    duplicate_assignments: dict[str, list[dict[str, str]]] = {}
    provider_constituent_rows = 0
    board_failures: list[dict[str, str]] = []

    for index, board in enumerate(boards, start=1):
        try:
            constituents = fetch_board_constituents(
                board["industry_code"],
                args.constituent_page_size,
            )
        except Exception as exc:
            board_failures.append(
                {
                    "industry_code": board["industry_code"],
                    "industry_name": board["industry_name"],
                    "error": f"{type(exc).__name__}:{exc}",
                }
            )
            continue
        provider_constituent_rows += len(constituents)
        for item in constituents:
            code = str(item.get("f12") or "").strip().zfill(6)
            name = str(item.get("f14") or "").strip()
            if not code or not name:
                continue
            sid = normalize_security_id(code, item.get("f13"))
            if sid not in market_ids:
                continue
            candidate = {
                "security_id": sid,
                "security_code": code,
                "security_name": name,
                "industry_code": board["industry_code"],
                "industry_name": board["industry_name"],
                "classification_source": "EASTMONEY_INDUSTRY_BOARD_CONSTITUENCY",
                "effective_date": now.date().isoformat(),
                "source_timestamp": now.isoformat(),
                "authority": "DATA_AND_RESEARCH_EVIDENCE_ONLY",
                "trade_authority": "NONE",
            }
            prior = assignments.get(sid)
            if prior is None:
                assignments[sid] = candidate
            elif prior["industry_code"] != candidate["industry_code"]:
                duplicate_assignments.setdefault(sid, [
                    {
                        "industry_code": prior["industry_code"],
                        "industry_name": prior["industry_name"],
                    }
                ]).append(
                    {
                        "industry_code": candidate["industry_code"],
                        "industry_name": candidate["industry_name"],
                    }
                )
        if index % 10 == 0:
            time.sleep(0.2)
        else:
            time.sleep(0.05)

    final_rows = sorted(assignments.values(), key=lambda row: row["security_id"])
    covered_ids = set(assignments)
    missing_ids = sorted(market_ids - covered_ids)
    coverage = len(covered_ids) / len(market_ids) if market_ids else 0.0
    duplicate_conflict_count = len(duplicate_assignments)

    current_dir = root / "investment_os_runtime/40_EVIDENCE_AND_LINEAGE/WP3_R/INDUSTRY_MASTER"
    csv_path = current_dir / "SECURITY_INDUSTRY_MASTER_CURRENT.csv"
    manifest_path = current_dir / "SECURITY_INDUSTRY_MASTER_CURRENT.json"
    write_csv(csv_path, final_rows)

    passed = coverage >= 0.99 and not board_failures and duplicate_conflict_count == 0
    manifest = {
        "state_id": "WP3R_SECURITY_INDUSTRY_MASTER_CURRENT",
        "generated_at": now.isoformat(),
        "provider": "EASTMONEY_INDUSTRY_BOARD_CONSTITUENCY",
        "market_security_count": len(market_ids),
        "industry_board_count": len(boards),
        "provider_constituent_row_count": provider_constituent_rows,
        "row_count": len(final_rows),
        "industry_count": len({row["industry_code"] for row in final_rows}),
        "resolved_count": len(final_rows),
        "missing_count": len(missing_ids),
        "missing_security_ids": missing_ids,
        "coverage": round(coverage, 8),
        "duplicate_industry_assignment_count": duplicate_conflict_count,
        "duplicate_industry_assignments": duplicate_assignments,
        "board_failure_count": len(board_failures),
        "board_failures": board_failures,
        "status": (
            "PASS_CANONICAL_INDUSTRY_MASTER_CURRENT"
            if passed
            else "BLOCKED_INDUSTRY_MASTER_COVERAGE_OR_CONFLICT"
        ),
        "csv_path": str(csv_path.relative_to(root)),
        "classification_semantics": "Eastmoney primary industry-board constituency; one current industry per security required",
        "automatic_candidate_mutations": 0,
        "orders": 0,
        "trade_authority": "NONE",
    }
    write_json(manifest_path, manifest)
    print(json.dumps(manifest, ensure_ascii=False, sort_keys=True))
    if not passed:
        raise SystemExit(
            "INDUSTRY_MASTER_FAIL_CLOSED:"
            f"coverage={coverage:.8f}:missing={len(missing_ids)}:"
            f"duplicates={duplicate_conflict_count}:board_failures={len(board_failures)}"
        )


if __name__ == "__main__":
    main()
