#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import requests

SSE_URL = "https://query.sse.com.cn/commonQuery.do"
SZSE_URL = "https://www.szse.cn/api/report/ShowReport/data"


def request_json(session: requests.Session, name: str, url: str, params: dict, output: Path, referer: str) -> dict:
    try:
        response = session.get(url, params=params, headers={"Referer": referer}, timeout=60)
        (output / f"{name}.txt").write_bytes(response.content)
        parsed = None
        error = None
        try:
            parsed = response.json()
            (output / f"{name}.json").write_text(json.dumps(parsed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        return {
            "name": name,
            "request_url": response.url,
            "status": response.status_code,
            "ok": response.ok,
            "content_type": response.headers.get("content-type", ""),
            "length": len(response.content),
            "json_parsed": parsed is not None,
            "top_type": type(parsed).__name__ if parsed is not None else None,
            "top_keys": sorted(parsed.keys()) if isinstance(parsed, dict) else None,
            "list_length": len(parsed) if isinstance(parsed, list) else None,
            "parse_error": error,
        }
    except Exception as exc:
        return {"name": name, "url": url, "ok": False, "error": f"{type(exc).__name__}: {exc}"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 InvestmentOS-FMDL5A/1.0", "Accept": "application/json,text/javascript,*/*;q=0.1"})
    probes = []
    sse_params = {
        "sqlId": "COMMON_SSE_JYFW_HGT_XXPL_BDZQQD_L",
        "pageHelp.pageSize": "1000",
        "pageHelp.pageNo": "1",
        "pageHelp.beginPage": "1",
        "pageHelp.cacheSize": "1",
        "pageHelp.endPage": "1",
        "keyword": "",
        "_": str(int(time.time() * 1000)),
    }
    probes.append(request_json(session, "sse_json", SSE_URL, sse_params, output, "https://www.sse.com.cn/services/hkexsc/disclo/eligible/"))
    for tab in ["tab1", "tab2", "", "1"]:
        params = {"SHOWTYPE": "JSON", "CATALOGID": "SGT_GGTBDQD", "PAGENO": "1", "PAGESIZE": "1000", "random": str(time.time())}
        if tab:
            params["TABKEY"] = tab
            params[f"{tab}PAGESIZE"] = "1000"
        name = "szse_" + (tab or "no_tab")
        probes.append(request_json(session, name, SZSE_URL, params, output, "https://www.szse.cn/szhk/hkbussiness/underlylist/"))
    (output / "FMDL5A_API_PROBE.json").write_text(json.dumps(probes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(probes, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
