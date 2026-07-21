#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

URL = "https://di.hkex.com.hk/di/NSSrchCorp.aspx?g_lang=en&lang=EN&src=MAIN&"
SAMPLE_CODES = ["00019", "00087", "00388", "00700", "09988"]


def new_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (compatible; InvestmentOS/5B2; +https://github.com/jl2642/investment-os-market-data)",
            "Accept-Language": "en-US,en;q=0.9",
        }
    )
    return s


def hidden_fields(soup: BeautifulSoup) -> dict[str, str]:
    out: dict[str, str] = {}
    for node in soup.select('input[type="hidden"]'):
        name = node.get("name")
        if name:
            out[str(name)] = str(node.get("value") or "")
    return out


def summarize(url: str, html: str) -> dict[str, object]:
    soup = BeautifulSoup(html, "html.parser")
    options = [
        {"value": str(o.get("value") or ""), "label": o.get_text(" ", strip=True)}
        for o in soup.find_all("option")
        if str(o.get("value") or "").strip() or o.get_text(" ", strip=True)
    ]
    links = [
        {"href": urljoin(url, str(a.get("href") or "")), "label": a.get_text(" ", strip=True)}
        for a in soup.find_all("a")
        if a.get("href")
    ]
    selected = [x for x in options if x["value"] and x["value"] not in {f"{i:02d}" for i in range(1, 32)} and x["value"] not in {f"{i:02d}" for i in range(1, 13)} and not x["value"].startswith("20")]
    return {
        "title": soup.title.get_text(" ", strip=True) if soup.title else "",
        "options": options[:5000],
        "candidate_options": selected[:500],
        "links": links[:500],
        "text_excerpt": soup.get_text(" ", strip=True)[:10000],
    }


def post_code(code: str) -> dict[str, object]:
    s = new_session()
    r = s.get(URL, timeout=(15, 90))
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    payload = hidden_fields(soup)
    payload.update(
        {
            "txtStockCode": code,
            "txtCorpName": "",
            "ddlStartDateDD": "01",
            "ddlStartDateMM": "01",
            "ddlStartDateYYYY": "2026",
            "ddlEndDateDD": "21",
            "ddlEndDateMM": "07",
            "ddlEndDateYYYY": "2026",
            "cmdSearch": "Search",
        }
    )
    p = s.post(URL, data=payload, timeout=(15, 90), allow_redirects=True)
    p.raise_for_status()
    return {
        "stock_code": code,
        "final_url": p.url,
        "status_code": p.status_code,
        "history": [{"status": x.status_code, "url": x.url, "location": x.headers.get("location", "")} for x in p.history],
        "summary": summarize(p.url, p.text),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    result: dict[str, object] = {"samples": [], "errors": []}
    for code in SAMPLE_CODES:
        try:
            result["samples"].append(post_code(code))
        except Exception as exc:  # noqa: BLE001
            result["errors"].append({"stock_code": code, "error": f"{type(exc).__name__}: {exc}"})
        time.sleep(1)
    (out / "FMDL5B2_DI_MAPPING_PROBE.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
