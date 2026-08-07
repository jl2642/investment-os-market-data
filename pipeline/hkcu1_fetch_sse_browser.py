#!/usr/bin/env python3
"""Fetch the public SSE southbound eligibility workbook through Chromium.

Production hardening:
- official SSE/SSEInfo domains only;
- real Chromium page/download network path, never APIRequestContext;
- bounded retries with fresh browser contexts;
- alternate official landing pages may bootstrap the same protected payload;
- classify SOURCE_BLOCKED vs TRANSIENT_INFRA vs DATA_CONTRACT_CHANGE;
- always persist detailed evidence; never substitute third-party data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

SSE_PAYLOAD = "https://query.sse.com.cn/commonExcelDd.do?sqlId=COMMON_SSE_JYFW_HGT_XXPL_BDZQQD_L&keyword="
SSE_LANDINGS = (
    "https://www.sse.com.cn/services/hkexsc/disclo/eligible/",
    "https://www.sse.com.cn/services/hkexsc/home/",
    "https://star.sse.com.cn/services/hkexsc/home/",
)
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
        "content-type", "content-disposition", "content-length", "referer",
        "user-agent", "accept", "sec-fetch-site", "sec-fetch-mode", "sec-fetch-dest",
    }
    return {str(k).lower(): str(v) for k, v in headers.items() if str(k).lower() in keep}


def _validate_workbook(raw: bytes) -> None:
    if len(raw) < 10_000:
        raise ValueError(f"SSE workbook implausibly small: {len(raw)} bytes")
    if raw[:4] not in VALID_SIGNATURES:
        raise ValueError(f"SSE payload is not XLS/XLSX; prefix={raw[:16].hex()}")


def _classify(attempt: dict) -> str:
    statuses = []
    for key in ("landing_http_status", "payload_http_status"):
        try:
            statuses.append(int(attempt.get(key) or 0))
        except (TypeError, ValueError):
            pass
    error = str(attempt.get("error") or "").lower()
    if 403 in statuses or 429 in statuses:
        return "SOURCE_BLOCKED"
    if any(s >= 500 for s in statuses) or "timeout" in error or "connection" in error:
        return "TRANSIENT_INFRA"
    if "xls" in error or "xlsx" in error or "signature" in error or "implausibly small" in error:
        return "DATA_CONTRACT_CHANGE"
    return "UNKNOWN"


def _attempt(output_file: Path, attempt_no: int) -> dict:
    evidence: dict[str, object] = {
        "attempt_no": attempt_no,
        "status": "BLOCKED",
        "failure_class": "UNKNOWN",
        "retrieved_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "acquisition_mode": "BROWSER_NATIVE_DOWNLOAD",
        "landing_candidates": list(SSE_LANDINGS),
        "landing_attempts": [],
        "landing_url": "",
        "landing_http_status": 0,
        "landing_final_url": "",
        "browser_user_agent": "",
        "browser_cookie_names": [],
        "payload_url": SSE_PAYLOAD,
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
            context = browser.new_context(locale="zh-CN", accept_downloads=True)
            page = context.new_page()
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
            page.on("pageerror", lambda exc: page_errors.append(str(exc)))

            def on_request(req) -> None:
                nonlocal payload_request_headers
                if "commonExcelDd.do" in req.url and _official_sse(req.url):
                    payload_request_headers = _header_subset(req.headers)
                    network_events.append({"kind": "request", "url": req.url, "method": req.method,
                                           "headers": payload_request_headers})

            def on_response(resp) -> None:
                nonlocal payload_status, payload_response_headers
                if "commonExcelDd.do" in resp.url and _official_sse(resp.url):
                    payload_status = resp.status
                    payload_response_headers = _header_subset(resp.headers)
                    network_events.append({"kind": "response", "url": resp.url, "status": resp.status,
                                           "headers": payload_response_headers})

            page.on("request", on_request)
            page.on("response", on_response)

            selected_landing = None
            for landing in SSE_LANDINGS:
                if not _official_sse(landing):
                    continue
                try:
                    response = page.goto(landing, wait_until="domcontentloaded", timeout=45_000)
                    status = response.status if response else 0
                    evidence["landing_attempts"].append({"url": landing, "status": status, "final_url": page.url})
                    if 0 < status < 400:
                        selected_landing = landing
                        evidence["landing_url"] = landing
                        evidence["landing_http_status"] = status
                        evidence["landing_final_url"] = page.url
                        break
                except PlaywrightTimeoutError as exc:
                    evidence["landing_attempts"].append({"url": landing, "status": 0, "error": f"timeout: {exc}"})

            if not selected_landing:
                statuses = [int(x.get("status") or 0) for x in evidence["landing_attempts"]]
                evidence["landing_http_status"] = statuses[-1] if statuses else 0
                raise RuntimeError(f"no usable official SSE landing page; statuses={statuses}")

            page.wait_for_timeout(1_500)
            evidence["browser_user_agent"] = page.evaluate("() => navigator.userAgent")
            evidence["browser_cookie_names"] = sorted({c["name"] for c in context.cookies()})

            # Trigger through a DOM anchor in the official page context. If SSE blocks
            # the payload, the response listener captures 403/429 and the timeout is
            # later classified as SOURCE_BLOCKED rather than CODE_DEFECT.
            with page.expect_download(timeout=25_000) as download_info:
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
                "failure_class": "NONE",
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
        if evidence["status"] != "PASS":
            evidence["failure_class"] = _classify(evidence)
    return evidence


def run(output_file: Path, evidence_file: Path, max_attempts: int = 3) -> int:
    if not _official_sse(SSE_PAYLOAD) or any(not _official_sse(u) for u in SSE_LANDINGS):
        raise ValueError("non-official SSE URL configured")
    if max_attempts < 1 or max_attempts > 6:
        raise ValueError("max_attempts must be between 1 and 6")

    attempts: list[dict] = []
    final: dict | None = None
    for attempt_no in range(1, max_attempts + 1):
        if output_file.exists():
            output_file.unlink()
        result = _attempt(output_file, attempt_no)
        attempts.append(result)
        final = result
        if result.get("status") == "PASS":
            break
        if attempt_no < max_attempts:
            time.sleep(min(5 * attempt_no, 15))

    assert final is not None
    summary = dict(final)
    summary.update({
        "authority": "SSE",
        "status": "PASS" if any(a.get("status") == "PASS" for a in attempts) else "BLOCKED",
        "attempt_count": len(attempts),
        "max_attempts": max_attempts,
        "attempts": attempts,
        "failure_class": "NONE" if any(a.get("status") == "PASS" for a in attempts) else final.get("failure_class", "UNKNOWN"),
        "trade_authority": "NONE",
    })
    evidence_file.parent.mkdir(parents=True, exist_ok=True)
    evidence_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if summary["status"] == "PASS" else 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-file", type=Path, required=True)
    parser.add_argument("--evidence-file", type=Path, required=True)
    parser.add_argument("--max-attempts", type=int, default=3)
    args = parser.parse_args()
    return run(args.output_file, args.evidence_file, args.max_attempts)


if __name__ == "__main__":
    raise SystemExit(main())
