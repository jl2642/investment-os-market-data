#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

SSE_URL = "https://query.sse.com.cn/commonQuery.do"
SZSE_URL = "https://www.szse.cn/api/report/ShowReport/data"
SSE_REFERER = "https://www.sse.com.cn/services/hkexsc/disclo/eligible/"
SZSE_REFERER = "https://www.szse.cn/szhk/hkbussiness/underlylist/"


def canonical_json(payload: Any) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json(payload))


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0 InvestmentOS-FMDL5A/1.0", "Accept": "application/json,text/javascript,*/*;q=0.1"})
    return s


def fetch_sse(s: requests.Session) -> tuple[list[dict[str, str]], dict[str, Any], bytes]:
    params = {
        "sqlId": "COMMON_SSE_JYFW_HGT_XXPL_BDZQQD_L",
        "pageHelp.pageSize": "1000",
        "pageHelp.pageNo": "1",
        "pageHelp.beginPage": "1",
        "pageHelp.cacheSize": "1",
        "pageHelp.endPage": "1",
        "keyword": "",
        "_": str(int(time.time() * 1000)),
    }
    r = s.get(SSE_URL, params=params, headers={"Referer": SSE_REFERER}, timeout=60)
    r.raise_for_status()
    raw = r.content
    payload = r.json()
    rows = payload.get("result") or []
    if len(rows) < 100 or not all(str(x.get("SECURITY_CODE", "")).isdigit() for x in rows):
        raise ValueError("SSE_SOURCE_SHAPE_OR_COUNT")
    update_dates = sorted({str(x.get("UPDATE_DATE", "")) for x in rows})
    if len(update_dates) != 1:
        raise ValueError("SSE_UPDATE_DATE_NOT_UNIQUE")
    normalized = [{
        "stock_code": str(x["SECURITY_CODE"]).zfill(5),
        "name_cn": str(x.get("ABBR_CN", "")).strip(),
        "name_en": str(x.get("ABBR_EN", "")).strip(),
        "security_type": str(x.get("SECURITY_TYPE", "")).strip(),
        "trade_flag": str(x.get("TRADE_FLAG", "")),
    } for x in rows]
    meta = {"source": "SSE", "url": r.url, "update_date": update_dates[0], "record_count": len(normalized), "raw_sha256": sha256_bytes(raw)}
    return normalized, meta, raw


def fetch_szse(s: requests.Session) -> tuple[list[dict[str, str]], dict[str, Any], bytes]:
    all_rows: list[dict[str, str]] = []
    raw_pages: list[bytes] = []
    first_meta: dict[str, Any] | None = None
    page = 1
    while True:
        params = {"SHOWTYPE": "JSON", "CATALOGID": "SGT_GGTBDQD", "TABKEY": "tab1", "PAGENO": str(page), "random": str(time.time())}
        r = s.get(SZSE_URL, params=params, headers={"Referer": SZSE_REFERER}, timeout=60)
        r.raise_for_status()
        raw_pages.append(r.content)
        payload = r.json()
        if not isinstance(payload, list) or not payload:
            raise ValueError("SZSE_SOURCE_SHAPE")
        block = payload[0]
        metadata = block.get("metadata") or {}
        data = block.get("data") or []
        if first_meta is None:
            first_meta = metadata
        all_rows.extend({
            "stock_code": str(x.get("zqdm", "")).zfill(5),
            "name_cn": str(x.get("zqjc", "")).strip(),
            "name_en": str(x.get("zqywjc", "")).strip(),
            "security_type": "",
            "trade_flag": "1",
        } for x in data)
        page_count = int(metadata.get("pagecount") or 0)
        if page >= page_count:
            break
        page += 1
        if page > 200:
            raise ValueError("SZSE_PAGE_GUARD")
    if first_meta is None or len(all_rows) < 100:
        raise ValueError("SZSE_SOURCE_EMPTY")
    expected = int(first_meta.get("recordcount") or 0)
    if expected != len(all_rows):
        raise ValueError(f"SZSE_RECORD_COUNT:{len(all_rows)}!={expected}")
    if not all(x["stock_code"].isdigit() and len(x["stock_code"]) == 5 for x in all_rows):
        raise ValueError("SZSE_CODE_SHAPE")
    combined_raw = b"\n".join(raw_pages)
    meta = {
        "source": "SZSE", "url": SZSE_URL, "update_date": str(first_meta.get("subname") or ""),
        "record_count": len(all_rows), "page_count": int(first_meta.get("pagecount") or 0),
        "raw_sha256": sha256_bytes(combined_raw),
    }
    return all_rows, meta, combined_raw


def build(output: Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    s = session()
    sse, sse_meta, sse_raw = fetch_sse(s)
    szse, szse_meta, szse_raw = fetch_szse(s)
    (output / "raw").mkdir(exist_ok=True)
    (output / "raw/SSE_SOUTHBOUND.json").write_bytes(sse_raw)
    (output / "raw/SZSE_SOUTHBOUND_PAGES.jsonl").write_bytes(szse_raw)

    by_code: dict[str, dict[str, Any]] = {}
    for route, rows in (("SHANGHAI_CONNECT", sse), ("SHENZHEN_CONNECT", szse)):
        for row in rows:
            code = row["stock_code"]
            item = by_code.setdefault(code, {
                "canonical_security_id": f"HKEX:{code}", "stock_code": code,
                "name_cn": row["name_cn"], "name_en": row["name_en"],
                "shanghai_connect": False, "shenzhen_connect": False,
                "eligibility_status": "BUY_AND_SELL_ELIGIBLE",
            })
            item["shanghai_connect" if route == "SHANGHAI_CONNECT" else "shenzhen_connect"] = True
            if not item["name_cn"] and row["name_cn"]: item["name_cn"] = row["name_cn"]
            if not item["name_en"] and row["name_en"]: item["name_en"] = row["name_en"]
    rows = [by_code[x] for x in sorted(by_code)]
    update_dates = sorted({sse_meta["update_date"], szse_meta["update_date"]})
    if len(update_dates) != 1:
        raise ValueError(f"ROUTE_UPDATE_DATE_MISMATCH:{update_dates}")
    effective_date = update_dates[0]
    fields = ["canonical_security_id","stock_code","name_cn","name_en","shanghai_connect","shenzhen_connect","eligibility_status"]
    with (output / "FMDL5A_CANONICAL_UNIVERSE.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)
    sh = {x["stock_code"] for x in sse}; sz = {x["stock_code"] for x in szse}
    diff = {"shanghai_only": sorted(sh-sz), "shenzhen_only": sorted(sz-sh), "both": len(sh&sz)}
    source_registry = {
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_update_date": effective_date,
        "effective_southbound_trading_date": effective_date,
        "effective_date_resolution": "SOURCE_UPDATE_DATE_CURRENT_LIST",
        "sources": [sse_meta, szse_meta],
    }
    write_json(output / "FMDL5A_SOURCE_REGISTRY.json", source_registry)
    write_json(output / "FMDL5A_ROUTE_DIFF.json", diff)
    universe_sha = sha256_bytes((output / "FMDL5A_CANONICAL_UNIVERSE.csv").read_bytes())
    release_seed = canonical_json({"universe_sha256": universe_sha, "source_update_date": effective_date, "source_hashes": [sse_meta["raw_sha256"], szse_meta["raw_sha256"]]})
    release_id = f"FMDL5A_{effective_date.replace('-','')}_{sha256_bytes(release_seed)[:12]}"
    decision = {
        "program_id": "FMDL-5A", "release_id": release_id,
        "status": "FMDL5A_MARKET_CONTRACT_AND_UNIVERSE_BOUNDARY_ACCEPTED",
        "hard_failures": [], "source_update_date": effective_date,
        "effective_southbound_trading_date": effective_date,
        "metrics": {"canonical_count": len(rows), "sse_count": len(sse), "szse_count": len(szse), "both_route_count": len(sh&sz), "shanghai_only_count": len(sh-sz), "shenzhen_only_count": len(sz-sh)},
        "universe_sha256": universe_sha,
        "candidate_pool_mutation_count": 0, "simulation_mutation_count": 0,
        "real_account_mutation_count": 0, "order_generation_count": 0,
        "trade_authority": "NONE", "next_gate": "FMDL-5B_HK_SECURITY_MASTER_AND_MARKET_SEMANTICS",
    }
    write_json(output / "FMDL5A_DECISION.json", decision)
    release = {**decision, "release_sequence": 10, "authority": "HK_STOCK_CONNECT_MARKET_CONTRACT_AND_UNIVERSE_ONLY", "source_registry": source_registry}
    write_json(output / "FMDL5A_RELEASE.json", release)
    manifest = {p.relative_to(output).as_posix(): sha256_bytes(p.read_bytes()) for p in sorted(output.rglob("*")) if p.is_file()}
    write_json(output / "FMDL5A_MANIFEST.json", manifest)
    return release


def main() -> int:
    p = argparse.ArgumentParser(); p.add_argument("--output", required=True); args=p.parse_args()
    release=build(Path(args.output)); print(json.dumps(release, ensure_ascii=False, indent=2)); return 0

if __name__ == "__main__": raise SystemExit(main())
