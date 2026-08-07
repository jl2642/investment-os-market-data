#!/usr/bin/env python3
"""Discover current SSE/SZSE Stock Connect adjustment notices in rendered official DOM.

Official notice landing pages are JavaScript-rendered on some hosted-runner paths,
so requests may return HTTP 200 with zero usable links. This adapter uses a real
Chromium page context, preserves diagnostics, and emits only official-domain URLs.
It does not fetch or parse the notices themselves.
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

OFFICIAL_HOSTS = {"SSE": ("sse.com.cn", "sseinfo.com"), "SZSE": ("szse.cn",)}


def _official(url: str, authority: str) -> bool:
    host = urlparse(url).hostname or ""
    return any(host == d or host.endswith("." + d) for d in OFFICIAL_HOSTS[authority])


def _discover_one(browser, spec: dict, max_attempts: int = 3) -> dict:
    authority = spec["authority"]
    channel = spec["channel"]
    index_url = spec["index_url"]
    needles = tuple(spec.get("title_contains", []))
    attempts = []
    final_urls: list[str] = []
    for attempt_no in range(1, max_attempts + 1):
        context = browser.new_context(locale="zh-CN")
        page = context.new_page()
        console_errors: list[str] = []
        page_errors: list[str] = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda exc: page_errors.append(str(exc)))
        row = {
            "attempt_no": attempt_no, "http_status": 0, "final_url": "", "anchor_count": 0,
            "matched_urls": [], "console_errors": console_errors, "page_errors": page_errors, "error": None,
        }
        try:
            response = page.goto(index_url, wait_until="domcontentloaded", timeout=45_000)
            row["http_status"] = response.status if response else 0
            row["final_url"] = page.url
            page.wait_for_timeout(3_000)
            anchors = page.locator("a[href]")
            row["anchor_count"] = anchors.count()
            matched = []
            for idx in range(anchors.count()):
                a = anchors.nth(idx)
                try:
                    text = a.inner_text(timeout=1_000).strip()
                    href = a.get_attribute("href") or ""
                except Exception:
                    continue
                if needles and not any(needle in text for needle in needles):
                    continue
                url = urljoin(page.url, href)
                if _official(url, authority):
                    matched.append(url)
            final_urls = list(dict.fromkeys(matched))
            row["matched_urls"] = final_urls
            attempts.append(row)
            context.close()
            if final_urls:
                break
        except PlaywrightTimeoutError as exc:
            row["error"] = f"PlaywrightTimeoutError: {exc}"
            attempts.append(row)
            context.close()
        except Exception as exc:
            row["error"] = f"{type(exc).__name__}: {exc}"
            attempts.append(row)
            context.close()
        if attempt_no < max_attempts:
            time.sleep(min(attempt_no * 3, 6))

    statuses = [int(a.get("http_status") or 0) for a in attempts]
    if final_urls:
        status = "PASS"
        failure_class = "NONE"
    elif 403 in statuses or 429 in statuses:
        status = "BLOCKED"
        failure_class = "SOURCE_BLOCKED"
    elif any(s >= 500 for s in statuses) or any("timeout" in str(a.get("error") or "").lower() for a in attempts):
        status = "BLOCKED"
        failure_class = "TRANSIENT_INFRA"
    else:
        status = "BLOCKED"
        failure_class = "DYNAMIC_INDEX_NO_MATCH"
    return {
        "authority": authority,
        "channel": channel,
        "index_url": index_url,
        "status": status,
        "failure_class": failure_class,
        "discovered_urls": final_urls,
        "discovered_url_count": len(final_urls),
        "attempts": attempts,
    }


def run(registry: Path, output: Path, max_attempts: int = 3) -> int:
    config = json.loads(registry.read_text(encoding="utf-8"))
    specs = config.get("adjustment_notice_sources", [])
    if not specs:
        raise ValueError("registry has no adjustment_notice_sources")
    for spec in specs:
        if not _official(spec["index_url"], spec["authority"]):
            raise ValueError(f"non-official notice index: {spec['index_url']}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        channels = [_discover_one(browser, spec, max_attempts) for spec in specs]
        browser.close()

    result = {
        "retrieved_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "status": "PASS" if all(row["status"] == "PASS" for row in channels) else "DEGRADED",
        "channels": channels,
        "trade_authority": "NONE",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--registry", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--max-attempts", type=int, default=3)
    a = p.parse_args()
    return run(a.registry, a.output, a.max_attempts)


if __name__ == "__main__":
    raise SystemExit(main())
