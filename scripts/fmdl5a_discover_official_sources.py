#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

SOURCES = {
    "hkex": "https://www.hkex.com.hk/Mutual-Market/Stock-Connect/Eligible-Stocks/View-All-Eligible-Securities?sc_lang=en",
    "sse": "https://www.sse.com.cn/services/hkexsc/disclo/eligible/",
    "szse": "https://www.szse.cn/szhk/hkbussiness/underlylist/",
}

KEYWORDS = ("eligible", "underly", "hkexsc", "hkbussiness", "stockconnect", "southbound", "query", "api", "json")


def fetch(session: requests.Session, name: str, url: str, output: Path) -> dict:
    response = session.get(url, timeout=40)
    response.raise_for_status()
    text = response.text
    (output / f"{name}.html").write_text(text, encoding="utf-8")
    soup = BeautifulSoup(text, "html.parser")
    scripts = [urljoin(url, x.get("src")) for x in soup.find_all("script") if x.get("src")]
    links = [urljoin(url, x.get("href")) for x in soup.find_all("a") if x.get("href")]
    literal_urls = re.findall(r"https?://[^\"'<>\\s]+", text)
    relative_candidates = re.findall(r"[\"']([^\"']*(?:api|query|eligible|underly|hkexsc|hkbussiness)[^\"']*)[\"']", text, re.I)
    candidates = sorted({u for u in scripts + links + literal_urls + [urljoin(url, x) for x in relative_candidates] if any(k in u.lower() for k in KEYWORDS)})
    return {
        "name": name,
        "url": url,
        "status": response.status_code,
        "content_type": response.headers.get("content-type"),
        "content_length": len(response.content),
        "scripts": scripts,
        "candidate_urls": candidates,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({"User-Agent": "InvestmentOS-FMDL5A/1.0 contact=repository-owner"})
    result = {name: fetch(session, name, url, output) for name, url in SOURCES.items()}
    (output / "FMDL5A_SOURCE_DISCOVERY.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: {"status": v["status"], "candidates": len(v["candidate_urls"])} for k, v in result.items()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
