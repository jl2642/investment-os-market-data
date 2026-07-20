#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import requests

ASSETS = {
    "sse_southbound_js": "https://www.sse.com.cn/xhtml/home/2021public/querySearch/search_southboundStock_2021.js",
    "sse_page": "https://www.sse.com.cn/services/hkexsc/disclo/eligible/",
    "szse_page": "https://www.szse.cn/szhk/hkbussiness/underlylist/",
    "szse_page_www": "https://www.szse.cn/www/szhk/hkbussiness/underlylist/",
    "szse_report_new_js": "https://www.szse.cn/modules/report/js/report_new.js",
    "szse_detail_report_js": "https://www.szse.cn/modules/report/js/detail_report.js",
    "szse_common_report_js": "https://www.szse.cn/modules/report/js/common_report.js",
    "szse_report_new_static_js": "https://res.static.szse.cn/www/modules/report/js/report_new.js",
    "szse_detail_report_static_js": "https://res.static.szse.cn/www/modules/report/js/detail_report.js",
    "szse_common_report_static_js": "https://res.static.szse.cn/www/modules/report/js/common_report.js",
    "szse_path_js": "https://www.szse.cn/szsePath.js",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0 InvestmentOS-FMDL5A/1.0", "Referer": "https://www.szse.cn/"})
    result = {}
    for name, url in ASSETS.items():
        try:
            r = s.get(url, timeout=60)
            result[name] = {"url": url, "status": r.status_code, "ok": r.ok, "content_type": r.headers.get("content-type"), "length": len(r.content)}
            suffix = ".js" if "javascript" in (r.headers.get("content-type") or "") or name.endswith("_js") else ".html"
            (out / f"{name}{suffix}").write_bytes(r.content)
        except Exception as exc:
            result[name] = {"url": url, "ok": False, "error": f"{type(exc).__name__}: {exc}"}
    (out / "FMDL5A_SOURCE_ASSETS.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
