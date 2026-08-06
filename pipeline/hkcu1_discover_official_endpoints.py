#!/usr/bin/env python3
"""Discover SSE/SZSE official Stock Connect machine endpoints with Playwright.

This script does not guess endpoint identifiers and does not publish eligibility data.
It opens the official pages, records network responses, classifies candidate data
responses, and emits an auditable candidate manifest for independent review.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from playwright.async_api import Response, async_playwright

OFFICIAL_PAGES = {
    "SH": "https://www.sse.com.cn/services/hkexsc/disclo/eligible/",
    "SZ": "https://www.szse.cn/szhk/hkbussiness/underlylist/",
}
OFFICIAL_HOST_SUFFIXES = {
    "SH": ("sse.com.cn", "sseinfo.com"),
    "SZ": ("szse.cn",),
}
CODE_RE = re.compile(r"(?<!\d)(\d{5})(?!\d)")
KEY_HINTS = {
    "code", "stockcode", "securitycode", "zqdm", "证券代码", "代碼",
    "name", "stockname", "securityname", "zqjc", "证券简称", "簡稱",
}


@dataclass
class Candidate:
    channel: str
    page_url: str
    request_url: str
    host: str
    status: int
    content_type: str
    resource_type: str
    body_sha256: str
    body_bytes: int
    detected_codes: int
    json_key_hints: list[str]
    score: int
    qualification: str
    rejection_reasons: list[str]


def official_host(channel: str, host: str) -> bool:
    host = host.lower().split(":", 1)[0]
    return any(host == suffix or host.endswith("." + suffix) for suffix in OFFICIAL_HOST_SUFFIXES[channel])


def inspect_json(value: Any) -> tuple[int, list[str]]:
    codes: set[str] = set()
    keys: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, child in node.items():
                norm = str(key).strip().lower()
                if norm in KEY_HINTS:
                    keys.add(str(key))
                if isinstance(child, (str, int)):
                    for match in CODE_RE.findall(str(child)):
                        codes.add(match)
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)
        elif isinstance(node, (str, int)):
            for match in CODE_RE.findall(str(node)):
                codes.add(match)

    walk(value)
    return len(codes), sorted(keys)


def classify(channel: str, response: Response, body: bytes) -> Candidate:
    url = response.url
    host = urlparse(url).hostname or ""
    ctype = (response.headers.get("content-type") or "").lower()
    resource_type = response.request.resource_type
    reasons: list[str] = []
    score = 0
    code_count = 0
    key_hints: list[str] = []

    if official_host(channel, host):
        score += 40
    else:
        reasons.append("NON_OFFICIAL_HOST")

    if response.status == 200:
        score += 10
    else:
        reasons.append(f"HTTP_{response.status}")

    is_json = "json" in ctype or body.lstrip().startswith((b"{", b"["))
    is_table_file = any(x in ctype for x in ("csv", "excel", "spreadsheet")) or url.lower().endswith((".csv", ".xls", ".xlsx"))
    if is_json:
        try:
            parsed = json.loads(body.decode("utf-8-sig", errors="strict"))
            code_count, key_hints = inspect_json(parsed)
            score += 20
        except Exception:
            reasons.append("JSON_PARSE_FAILED")
    elif is_table_file:
        text = body.decode("utf-8-sig", errors="ignore")
        code_count = len(set(CODE_RE.findall(text)))
        score += 20
    else:
        text = body.decode("utf-8", errors="ignore")
        code_count = len(set(CODE_RE.findall(text)))
        if "text/html" in ctype:
            reasons.append("HTML_RESPONSE")

    if code_count >= 100:
        score += 30
    elif code_count >= 10:
        score += 10
    else:
        reasons.append("INSUFFICIENT_DISTINCT_5D_CODES")

    if key_hints:
        score += 10

    qualification = "QUALIFIED_CANDIDATE" if score >= 90 and not any(r in reasons for r in ("NON_OFFICIAL_HOST", "HTML_RESPONSE", "JSON_PARSE_FAILED")) else "REVIEW_REQUIRED"
    return Candidate(
        channel=channel,
        page_url=OFFICIAL_PAGES[channel],
        request_url=url,
        host=host,
        status=response.status,
        content_type=ctype,
        resource_type=resource_type,
        body_sha256=hashlib.sha256(body).hexdigest(),
        body_bytes=len(body),
        detected_codes=code_count,
        json_key_hints=key_hints,
        score=score,
        qualification=qualification,
        rejection_reasons=sorted(set(reasons)),
    )


async def discover_channel(channel: str, timeout_ms: int) -> dict[str, Any]:
    candidates: list[Candidate] = []
    seen: set[str] = set()
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            locale="zh-CN",
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131 Safari/537.36",
            extra_http_headers={"Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7"},
        )
        page = await context.new_page()

        async def handle_response(response: Response) -> None:
            if response.url in seen:
                return
            seen.add(response.url)
            host = urlparse(response.url).hostname or ""
            if not official_host(channel, host):
                return
            if response.request.resource_type not in {"xhr", "fetch", "document", "other"}:
                return
            try:
                body = await response.body()
            except Exception:
                return
            if not body or len(body) > 50_000_000:
                return
            candidate = classify(channel, response, body)
            if candidate.detected_codes >= 10 or candidate.resource_type in {"xhr", "fetch"}:
                candidates.append(candidate)

        page.on("response", handle_response)
        navigation_error = None
        try:
            await page.goto(OFFICIAL_PAGES[channel], wait_until="networkidle", timeout=timeout_ms)
            await page.wait_for_timeout(5000)
            # Exercise common UI controls so lazy-loaded table requests are emitted.
            for selector in ["button:has-text('查询')", "button:has-text('搜尋')", "button:has-text('Search')", "input[type=submit]"]:
                try:
                    locator = page.locator(selector).first
                    if await locator.count():
                        await locator.click(timeout=1500)
                        await page.wait_for_timeout(2500)
                except Exception:
                    pass
        except Exception as exc:
            navigation_error = f"{type(exc).__name__}: {exc}"
        await page.wait_for_timeout(1000)
        await browser.close()

    ordered = sorted(candidates, key=lambda c: (-c.score, -c.detected_codes, c.request_url))
    qualified = [c for c in ordered if c.qualification == "QUALIFIED_CANDIDATE"]
    return {
        "channel": channel,
        "official_page": OFFICIAL_PAGES[channel],
        "navigation_error": navigation_error,
        "candidate_count": len(ordered),
        "qualified_candidate_count": len(qualified),
        "status": "PASS" if len(qualified) == 1 else "BLOCKED",
        "blocking_reason": None if len(qualified) == 1 else ("NO_QUALIFIED_ENDPOINT" if not qualified else "MULTIPLE_QUALIFIED_ENDPOINTS_REQUIRE_REVIEW"),
        "candidates": [asdict(c) for c in ordered],
    }


async def main_async(args: argparse.Namespace) -> int:
    results = [await discover_channel(channel, args.timeout_ms) for channel in ("SH", "SZ")]
    payload = {
        "program_id": "HKCU-1-R2B",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": "PLAYWRIGHT_NETWORK_CAPTURE_NO_ENDPOINT_GUESSING",
        "promotion_rule": "EXACTLY_ONE_QUALIFIED_OFFICIAL_ENDPOINT_PER_CHANNEL",
        "overall_status": "PASS" if all(item["status"] == "PASS" for item in results) else "BLOCKED",
        "channels": results,
        "trade_authority": "NONE",
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["overall_status"] == "PASS" else 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="outputs/hkcu1/discovery/HKCU1_OFFICIAL_ENDPOINT_DISCOVERY.json")
    parser.add_argument("--timeout-ms", type=int, default=60000)
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main_async(parse_args())))
