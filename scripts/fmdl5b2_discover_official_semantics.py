#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

SOURCES = {
    "hkex_full_list_of_securities": "https://www.hkex.com.hk/eng/services/trading/securities/securitieslists/ListOfSecurities.xlsx",
    "hkex_dual_counter_list": "https://www.hkex.com.hk/-/media/HKEX-Market/Services/Trading/Securities/Securities-Lists/Dual_Counter_Security_List.xlsx",
    "hkex_isin_assigned": "https://www.hkex.com.hk/-/media/HKEX-Market/Services/Trading/Securities/Securities-Lists/ISINs-assigned-by-HKEX/isinsehk.xls",
    "hkex_isin_external": "https://www.hkex.com.hk/-/media/HKEX-Market/Services/Trading/Securities/Securities-Lists/ISINs-assigned-by-Other-Numbering-Agencies/isino.xls",
    "hkex_equities_page": "https://www.hkex.com.hk/Products/Securities/Equities?sc_lang=en",
    "hkex_market_equities": "https://www.hkex.com.hk/Market-Data/Securities-Prices/Equities?sc_lang=en",
    "hkex_market_etp": "https://www.hkex.com.hk/Market-Data/Securities-Prices/Exchange-Traded-Products?sc_lang=en",
    "hkex_market_reit": "https://www.hkex.com.hk/Market-Data/Securities-Prices/Real-Estate-Investment-Trusts?sc_lang=en",
    "hkex_di_corporation_selector": "https://di.hkex.com.hk/di/NSSelectCorp.aspx?src=MAIN",
    "hkex_di_corporation_search": "https://di.hkex.com.hk/di/NSSrchCorp.aspx?g_lang=en&lang=EN&src=MAIN",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (compatible; InvestmentOS/5B2; +https://github.com/jl2642/investment-os-market-data)",
            "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
            "Referer": "https://www.hkex.com.hk/Products/Securities/Equities?sc_lang=en",
        }
    )
    adapter = requests.adapters.HTTPAdapter(max_retries=3)
    s.mount("https://", adapter)
    return s


def fetch(s: requests.Session, url: str) -> requests.Response:
    last: Exception | None = None
    for attempt in range(4):
        try:
            r = s.get(url, timeout=(15, 90), allow_redirects=True)
            r.raise_for_status()
            return r
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(2**attempt)
    assert last is not None
    raise last


def preview_excel(path: Path) -> dict[str, object]:
    result: dict[str, object] = {"sheets": []}
    try:
        book = pd.ExcelFile(path)
        for sheet in book.sheet_names:
            frame = pd.read_excel(path, sheet_name=sheet, header=None, nrows=25)
            result["sheets"].append(
                {
                    "name": str(sheet),
                    "preview_rows": frame.fillna("").astype(str).values.tolist(),
                    "preview_shape": [int(frame.shape[0]), int(frame.shape[1])],
                }
            )
    except Exception as exc:  # noqa: BLE001
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def discover_html(url: str, data: bytes) -> dict[str, object]:
    text = data.decode("utf-8", errors="replace")
    soup = BeautifulSoup(text, "html.parser")
    links: list[str] = []
    scripts: list[str] = []
    options: list[dict[str, str]] = []
    for node in soup.find_all(["a", "link"]):
        href = node.get("href")
        if href:
            links.append(urljoin(url, href))
    for node in soup.find_all("script"):
        src = node.get("src")
        if src:
            scripts.append(urljoin(url, src))
    for node in soup.find_all("option"):
        value = str(node.get("value") or "").strip()
        label = node.get_text(" ", strip=True)
        if value or label:
            options.append({"value": value, "label": label})
    patterns = sorted(
        set(
            re.findall(
                r"https?://[^\"'<>\s]+|/[A-Za-z0-9_?&=./%+-]*(?:api|Api|API|GetData|list|List|security|Security|corp|Corp)[A-Za-z0-9_?&=./%+-]*",
                text,
            )
        )
    )
    return {
        "title": soup.title.get_text(" ", strip=True) if soup.title else "",
        "links": sorted(set(links)),
        "scripts": sorted(set(scripts)),
        "options": options[:10000],
        "endpoint_candidates": patterns[:1000],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    out = Path(args.output)
    raw = out / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    s = session()
    registry: dict[str, object] = {"sources": {}, "hard_failures": []}

    for key, url in SOURCES.items():
        try:
            r = fetch(s, url)
            suffix = Path(urlparse(r.url).path).suffix or ".html"
            target = raw / f"{key}{suffix}"
            target.write_bytes(r.content)
            record: dict[str, object] = {
                "requested_url": url,
                "final_url": r.url,
                "status_code": r.status_code,
                "content_type": r.headers.get("content-type", ""),
                "size_bytes": len(r.content),
                "sha256": sha256(r.content),
                "file": str(target.relative_to(out)),
            }
            if suffix.lower() in {".xlsx", ".xls"}:
                record["workbook"] = preview_excel(target)
            else:
                record["html"] = discover_html(r.url, r.content)
            registry["sources"][key] = record
        except Exception as exc:  # noqa: BLE001
            registry["sources"][key] = {
                "requested_url": url,
                "error": f"{type(exc).__name__}: {exc}",
            }
            registry["hard_failures"].append(key)

    (out / "FMDL5B2_SOURCE_DISCOVERY.json").write_text(
        json.dumps(registry, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(registry, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
