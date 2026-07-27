#!/usr/bin/env python3
from __future__ import annotations

import argparse
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


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def fetch(endpoint: str, params: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    url = endpoint + "?" + urllib.parse.urlencode(params)
    try:
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 InvestmentOS-WP3R-Diagnostic/1.0",
                "Referer": "https://quote.eastmoney.com/center/gridlist.html",
            },
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
        return json.loads(raw.decode("utf-8", errors="replace")), None
    except Exception as exc:
        return None, f"{type(exc).__name__}:{exc}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--page-size", type=int, default=20)
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    now = datetime.now(CN)
    params = {
        "pn": 1,
        "pz": args.page_size,
        "po": 1,
        "np": 1,
        "fltt": 2,
        "invt": 2,
        "fid": "f3",
        "fs": FS,
        "fields": FIELDS,
    }
    attempts = []
    selected = None
    for endpoint in ENDPOINTS:
        payload, error = fetch(endpoint, params)
        attempt = {"endpoint": endpoint, "error": error, "response_received": payload is not None}
        if payload is not None:
            data = payload.get("data") or {}
            diff = data.get("diff") or []
            if isinstance(diff, dict):
                diff = list(diff.values())
            keys = sorted({key for row in diff if isinstance(row, dict) for key in row})
            f100_nonempty = sum(1 for row in diff if str(row.get("f100") or "").strip())
            attempt.update(
                {
                    "data_keys": sorted(data.keys()),
                    "provider_total": data.get("total"),
                    "sample_row_count": len(diff),
                    "sample_row_keys": keys,
                    "f100_nonempty_count": f100_nonempty,
                    "f100_coverage": round(f100_nonempty / len(diff), 8) if diff else 0.0,
                    "sample_rows": diff[:5],
                }
            )
            selected = attempt
            attempts.append(attempt)
            break
        attempts.append(attempt)
        time.sleep(1)
    status = "PASS_F100_PRESENT" if selected and selected.get("f100_nonempty_count", 0) else "BLOCKED_F100_ABSENT_OR_PROVIDER_UNAVAILABLE"
    diagnostic = {
        "diagnostic_id": "WP3R_INDUSTRY_PROVIDER_DIAGNOSTIC_CURRENT",
        "generated_at": now.isoformat(),
        "status": status,
        "requested_fields": FIELDS.split(","),
        "market_filter": FS,
        "attempts": attempts,
        "selected_endpoint": selected.get("endpoint") if selected else None,
        "automatic_candidate_mutations": 0,
        "orders": 0,
        "trade_authority": "NONE",
    }
    output = root / "investment_os_runtime/40_EVIDENCE_AND_LINEAGE/WP3_R/INDUSTRY_MASTER/INDUSTRY_PROVIDER_DIAGNOSTIC_CURRENT.json"
    write_json(output, diagnostic)
    print(json.dumps(diagnostic, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
