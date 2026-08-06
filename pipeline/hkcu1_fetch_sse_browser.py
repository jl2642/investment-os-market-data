#!/usr/bin/env python3
"""Fetch the public SSE southbound eligibility workbook through a real browser session.

The browser first visits the official landing page, then requests the official
query.sse.com.cn workbook in the same context. No third-party source is used.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

SSE_LANDING = "https://www.sse.com.cn/services/hkexsc/disclo/eligible/"
SSE_PAYLOAD = "https://query.sse.com.cn/commonExcelDd.do?sqlId=COMMON_SSE_JYFW_HGT_XXPL_BDZQQD_L&keyword="
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131 Safari/537.36 Investment-OS-HKCU1"


def _official_sse(url: str) -> bool:
    host = urlparse(url).hostname or ""
    return host == "sse.com.cn" or host.endswith(".sse.com.cn") or host == "sseinfo.com" or host.endswith(".sseinfo.com")


def run(output_file: Path, evidence_file: Path) -> int:
    if not _official_sse(SSE_LANDING) or not _official_sse(SSE_PAYLOAD):
        raise ValueError("non-official SSE URL")
    evidence = {
        "status": "BLOCKED",
        "authority": "SSE",
        "landing_url": SSE_LANDING,
        "payload_url": SSE_PAYLOAD,
        "retrieved_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "http_status": 0,
        "content_type": "",
        "bytes": 0,
        "sha256": "",
        "error": None,
        "trade_authority": "NONE",
    }
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent=USER_AGENT, locale="zh-CN")
            page = context.new_page()
            page.goto(SSE_LANDING, wait_until="domcontentloaded", timeout=90000)
            page.wait_for_timeout(1500)
            response = context.request.get(
                SSE_PAYLOAD,
                headers={
                    "Referer": SSE_LANDING,
                    "Accept": "application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*",
                    "User-Agent": USER_AGENT,
                },
                timeout=90000,
            )
            evidence["http_status"] = response.status
            evidence["content_type"] = response.headers.get("content-type", "")
            if not response.ok:
                raise RuntimeError(f"SSE browser-context request returned HTTP {response.status}")
            raw = response.body()
            if raw[:4] not in (b"PK\x03\x04", b"\xd0\xcf\x11\xe0"):
                raise ValueError("SSE browser payload is not XLS/XLSX")
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_bytes(raw)
            evidence.update({
                "status": "PASS",
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            })
            browser.close()
    except Exception as exc:
        evidence["error"] = f"{type(exc).__name__}: {exc}"
    evidence_file.parent.mkdir(parents=True, exist_ok=True)
    evidence_file.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if evidence["status"] == "PASS" else 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-file", type=Path, required=True)
    parser.add_argument("--evidence-file", type=Path, required=True)
    args = parser.parse_args()
    return run(args.output_file, args.evidence_file)


if __name__ == "__main__":
    raise SystemExit(main())
