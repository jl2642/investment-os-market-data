#!/usr/bin/env python3
"""Fetch the public SSE southbound eligibility workbook through Chromium's real page network stack.

R2B-R1-R2 hardening notes:
- Do not use Playwright ``context.request`` for the protected workbook. That API
  uses an APIRequestContext network stack and can receive HTTP 403 even after a
  browser page has visited the SSE landing page.
- Do not spoof a stale Chrome user-agent. Use Chromium's native UA so the TLS /
  browser / UA fingerprint is internally consistent.
- Trigger the official workbook through a real DOM anchor click in the visited
  SSE page and capture the browser download. This preserves the normal browser
  navigation/referrer/cookie path.
- Record diagnostic evidence without weakening the official-source boundary.
No third-party source or cached synthetic list is accepted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

SSE_LANDING = "https://www.sse.com.cn/services/hkexsc/disclo/eligible/"
SSE_PAYLOAD = "https://query.sse.com.cn/commonExcelDd.do?sqlId=COMMON_SSE_JYFW_HGT_XXPL_BDZQQD_L&keyword="
VALID_SIGNATURES = (b"PK\x03\x04", b"\xd0\xcf\x11\xe0")


def _official_sse(url: str) -> bool:
    host = urlparse(url).hostname or ""
    return (
        host == "sse.com.cn"
        or host.endswith(".sse.com.cn")
        or host == "sseinfo.com"
        or host.endswith(".sseinfo.com")
    )


def _header_subset(headers: dict[str, str]) -> dict[str, str]:
    keep = {
        "content-type",
        "content-disposition",
        "content-length",
        "referer",
        "user-agent",
        "accept",
        "sec-fetch-site",
        "sec-fetch-mode",
        "sec-fetch-dest",
    }
    return {str(k).lower(): str(v) for k, v in headers.items() if str(k).lower() in keep}


def _validate_workbook(raw: bytes) -> None:
    if len(raw) < 10_000:
        raise ValueError(f"SSE workbook implausibly small: {len(raw)} bytes")
    if raw[:4] not in VALID_SIGNATURES:
        raise ValueError(f"SSE payload is not XLS/XLSX; prefix={raw[:16].hex()}")


def run(output_file: Path, evidence_file: Path) -> int:
    if not _official_sse(SSE_LANDING) or not _official_sse(SSE_PAYLOAD):
        raise ValueError("non-official SSE URL")

    evidence: dict[str, object] = {
        "status": "BLOCKED",
        "authority": "SSE",
        "landing_url": SSE_LANDING,
        "payload_url": SSE_PAYLOAD,
        "retrieved_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "acquisition_mode": "BROWSER_NATIVE_DOWNLOAD",
        "landing_http_status": 0,
        "landing_final_url": "",
        "browser_user_agent": "",
        "browser_cookie_names": [],
        "payload_http_status": 0,
        "payload_response_headers": {},
        "payload_request_headers": {},
        "download_url": "",
        "suggested_filename": "",
        "bytes": 0,
        "sha256": "",
        "signature_hex": "",
        "console_errors": [],
        "page_errors": [],
        "network_events": [],
        "error": None,
        "trade_authority": "NONE",
    }

    console_errors: list[str] = []
    page_errors: list[str] = []
    network_events: list[dict[str, object]] = []
    payload_request_headers: dict[str, str] = {}
    payload_response_headers: dict[str, str] = {}
    payload_status = 0

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            # Use Chromium's native UA. A spoofed UA that disagrees with the actual
            # Chromium/TLS fingerprint can itself trigger SSE anti-bot controls.
            context = browser.new_context(locale="zh-CN", accept_downloads=True)
            page = context.new_page()

            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
            page.on("pageerror", lambda exc: page_errors.append(str(exc)))

            def on_request(req) -> None:
                nonlocal payload_request_headers
                if "commonExcelDd.do" in req.url and _official_sse(req.url):
                    payload_request_headers = _header_subset(req.headers)
                    network_events.append({
                        "kind": "request",
                        "url": req.url,
                        "method": req.method,
                        "headers": payload_request_headers,
                    })

            def on_response(resp) -> None:
                nonlocal payload_status, payload_response_headers
                if "commonExcelDd.do" in resp.url and _official_sse(resp.url):
                    payload_status = resp.status
                    payload_response_headers = _header_subset(resp.headers)
                    network_events.append({
                        "kind": "response",
                        "url": resp.url,
                        "status": resp.status,
                        "headers": payload_response_headers,
                    })

            page.on("request", on_request)
            page.on("response", on_response)

            landing_response = page.goto(SSE_LANDING, wait_until="domcontentloaded", timeout=90_000)
            evidence["landing_http_status"] = landing_response.status if landing_response else 0
            evidence["landing_final_url"] = page.url
            page.wait_for_timeout(2_000)
            evidence["browser_user_agent"] = page.evaluate("() => navigator.userAgent")
            evidence["browser_cookie_names"] = sorted({c["name"] for c in context.cookies()})

            # Real Chromium navigation/download path.  We intentionally create the
            # anchor inside the official landing page so the browser supplies the
            # normal page context and referrer instead of APIRequestContext headers.
            with page.expect_download(timeout=45_000) as download_info:
                page.evaluate(
                    """url => {
                        const a = document.createElement('a');
                        a.href = url;
                        a.style.display = 'none';
                        document.body.appendChild(a);
                        a.click();
                        setTimeout(() => a.remove(), 1000);
                    }""",
                    SSE_PAYLOAD,
                )
            download = download_info.value
            evidence["download_url"] = download.url
            evidence["suggested_filename"] = download.suggested_filename

            output_file.parent.mkdir(parents=True, exist_ok=True)
            download.save_as(str(output_file))
            raw = output_file.read_bytes()
            _validate_workbook(raw)

            evidence.update({
                "status": "PASS",
                "payload_http_status": payload_status,
                "payload_response_headers": payload_response_headers,
                "payload_request_headers": payload_request_headers,
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "signature_hex": raw[:16].hex(),
                "network_events": network_events[-20:],
            })
            browser.close()
    except PlaywrightTimeoutError as exc:
        evidence["error"] = f"PlaywrightTimeoutError: {exc}"
    except Exception as exc:
        evidence["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        evidence["payload_http_status"] = payload_status
        evidence["payload_response_headers"] = payload_response_headers
        evidence["payload_request_headers"] = payload_request_headers
        evidence["console_errors"] = console_errors[-20:]
        evidence["page_errors"] = page_errors[-20:]
        evidence["network_events"] = network_events[-20:]
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
