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
    "https://push2.eastmoney.com/api/qt/clist/get",
]
FIELDS = "f12,f13,f14,f100"
FS = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048"


def request_json(params: dict[str, Any], retries: int = 3) -> dict[str, Any]:
    errors = []
    query = urllib.parse.urlencode(params)
    for endpoint in ENDPOINTS:
        for attempt in range(1, retries + 1):
            try:
                request = urllib.request.Request(
                    f"{endpoint}?{query}",
                    headers={
                        "User-Agent": "Mozilla/5.0 InvestmentOS-WP3R/1.0",
                        "Referer": "https://quote.eastmoney.com/center/gridlist.html",
                    },
                )
                with urllib.request.urlopen(request, timeout=30) as response:
                    return json.loads(response.read().decode("utf-8", errors="replace"))
            except Exception as exc:
                errors.append(f"{endpoint}:attempt={attempt}:{type(exc).__name__}:{exc}")
                if attempt < retries:
                    time.sleep(attempt * 2)
    raise RuntimeError("|".join(errors))


def exchange_suffix(code: str, market_id: Any) -> str:
    if code.startswith(("4", "8", "92")):
        return "BJ"
    if str(market_id) == "1" or code.startswith(("5", "6")):
        return "SH"
    return "SZ"


def industry_code(name: str) -> str:
    return "EMI-" + hashlib.sha1(name.encode("utf-8")).hexdigest()[:10].upper()


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
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--page-size", type=int, default=500)
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    now = datetime.now(CN)
    rows: dict[str, dict[str, Any]] = {}
    page = 1
    total_expected = None
    while True:
        payload = request_json(
            {
                "pn": page,
                "pz": args.page_size,
                "po": 1,
                "np": 1,
                "fltt": 2,
                "invt": 2,
                "fid": "f3",
                "fs": FS,
                "fields": FIELDS,
            }
        )
        data = payload.get("data") or {}
        diff = data.get("diff") or []
        total_expected = int(data.get("total") or total_expected or 0)
        if isinstance(diff, dict):
            diff = list(diff.values())
        if not diff:
            break
        for item in diff:
            code = str(item.get("f12") or "").zfill(6)
            name = str(item.get("f14") or "").strip()
            industry = str(item.get("f100") or "").strip()
            if not code or not name:
                continue
            sid = f"{code}.{exchange_suffix(code, item.get('f13'))}"
            rows[sid] = {
                "security_id": sid,
                "security_code": code,
                "security_name": name,
                "industry_code": industry_code(industry) if industry else "UNRESOLVED",
                "industry_name": industry or "UNRESOLVED",
                "classification_source": "EASTMONEY_F100_INDUSTRY",
                "effective_date": now.date().isoformat(),
                "source_timestamp": now.isoformat(),
                "authority": "DATA_AND_RESEARCH_EVIDENCE_ONLY",
                "trade_authority": "NONE",
            }
        if len(diff) < args.page_size or len(rows) >= total_expected:
            break
        page += 1
        if page > 30:
            raise RuntimeError("INDUSTRY_MASTER_PAGINATION_SAFETY_LIMIT")

    final_rows = sorted(rows.values(), key=lambda row: row["security_id"])
    unresolved = [row for row in final_rows if row["industry_name"] == "UNRESOLVED"]
    coverage = (len(final_rows) - len(unresolved)) / len(final_rows) if final_rows else 0.0
    if len(final_rows) < 5000 or coverage < 0.99:
        raise SystemExit(f"INDUSTRY_MASTER_FAIL_CLOSED:rows={len(final_rows)}:coverage={coverage:.6f}")

    current_dir = root / "investment_os_runtime/40_EVIDENCE_AND_LINEAGE/WP3_R/INDUSTRY_MASTER"
    csv_path = current_dir / "SECURITY_INDUSTRY_MASTER_CURRENT.csv"
    manifest_path = current_dir / "SECURITY_INDUSTRY_MASTER_CURRENT.json"
    write_csv(csv_path, final_rows)
    manifest = {
        "state_id": "WP3R_SECURITY_INDUSTRY_MASTER_CURRENT",
        "generated_at": now.isoformat(),
        "provider": "EASTMONEY_F100_INDUSTRY",
        "row_count": len(final_rows),
        "provider_total_expected": total_expected,
        "industry_count": len({row["industry_code"] for row in final_rows if row["industry_code"] != "UNRESOLVED"}),
        "resolved_count": len(final_rows) - len(unresolved),
        "unresolved_count": len(unresolved),
        "coverage": round(coverage, 8),
        "status": "PASS_CANONICAL_INDUSTRY_MASTER_CURRENT",
        "csv_path": str(csv_path.relative_to(root)),
        "classification_semantics": "provider industry label with stable system-local derived code",
        "automatic_candidate_mutations": 0,
        "orders": 0,
        "trade_authority": "NONE",
    }
    write_json(manifest_path, manifest)
    print(json.dumps(manifest, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
