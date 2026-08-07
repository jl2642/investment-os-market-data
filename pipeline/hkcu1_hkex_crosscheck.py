#!/usr/bin/env python3
"""R2D HKEX official structural/linkage cross-check.

HKEX is not treated as a third independent row-level Southbound list. The HKEX
Eligible Securities page is used to prove that HKEX publishes both Southbound
references and that those references point to the configured SSE/SZSE primary
authorities. Any structural/linkage conflict fails closed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import time
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131 Safari/537.36 Investment-OS-HKCU1"
UPDATE_RE = re.compile(r"Updated\s+(\d{1,2})\s+([A-Za-z]{3})\s+(20\d{2})", re.I)
MONTHS = {m: i for i, m in enumerate(("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), 1)}


def _host_allowed(url: str, domains: list[str]) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in domains)


def _get(session: requests.Session, url: str, attempts: int = 3) -> requests.Response:
    last: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = session.get(
                url,
                timeout=25,
                headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*"},
            )
            response.raise_for_status()
            return response
        except Exception as exc:
            last = exc
            if attempt < attempts:
                time.sleep(min(2 * attempt, 5))
    assert last is not None
    raise last


def _chrome_render(url: str) -> tuple[str, dict]:
    chrome = next(
        (
            shutil.which(name)
            for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser")
            if shutil.which(name)
        ),
        None,
    )
    if not chrome:
        return "", {"browser_available": False, "browser_error": "No Chrome/Chromium executable on runner"}
    try:
        proc = subprocess.run(
            [
                chrome,
                "--headless=new",
                "--no-sandbox",
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--virtual-time-budget=5000",
                "--dump-dom",
                url,
            ],
            capture_output=True,
            text=True,
            timeout=40,
            check=False,
        )
        html = proc.stdout or ""
        return html, {
            "browser_available": True,
            "browser_executable": chrome,
            "browser_exit_code": proc.returncode,
            "browser_dom_bytes": len(html.encode("utf-8", errors="ignore")),
            "browser_stderr_tail": (proc.stderr or "")[-1000:],
        }
    except Exception as exc:
        return "", {"browser_available": True, "browser_error": f"{type(exc).__name__}: {exc}"}


def parse_update_date(text: str) -> str | None:
    match = UPDATE_RE.search(text)
    if not match:
        return None
    day, month, year = match.groups()
    month_num = MONTHS.get(month.title())
    if month_num is None:
        return None
    return f"{int(year):04d}-{month_num:02d}-{int(day):02d}"


def parse_hkex_page(html: str, base_url: str, contract: dict) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    plain = soup.get_text(" ", strip=True)
    heading = contract["hkex_page"]["required_heading"]
    heading_present = heading.lower() in plain.lower()
    links: dict[str, dict] = {}
    for channel, spec in contract["required_links"].items():
        needle = spec["label_contains"].lower()
        matches = []
        for anchor in soup.find_all("a", href=True):
            label = anchor.get_text(" ", strip=True)
            if needle in label.lower():
                matches.append(
                    {
                        "label": label,
                        "url": urljoin(base_url, anchor["href"]),
                    }
                )
        links[channel] = {"matches": matches}
    return {
        "heading_present": heading_present,
        "page_update_date": parse_update_date(plain),
        "links": links,
    }


def validate(parsed: dict, contract: dict, validation_date: str) -> dict:
    errors: list[str] = []
    if not parsed["heading_present"]:
        errors.append("MISSING_ALL_ELIGIBLE_SECURITIES_HEADING")

    link_results: dict[str, dict] = {}
    for channel, spec in contract["required_links"].items():
        matches = parsed["links"].get(channel, {}).get("matches", [])
        if not matches:
            errors.append(f"MISSING_{channel}_SOUTHBOUND_LINK")
            link_results[channel] = {"status": "BLOCKED", "reason": "MISSING_LINK", "matches": []}
            continue
        valid = []
        invalid = []
        for match in matches:
            if _host_allowed(match["url"], spec["expected_domains"]):
                valid.append(match)
            else:
                invalid.append(match)
        if not valid:
            errors.append(f"{channel}_LINK_NOT_ON_PRIMARY_OFFICIAL_DOMAIN")
            link_results[channel] = {"status": "BLOCKED", "reason": "NON_OFFICIAL_TARGET", "matches": matches}
            continue
        expected_url = spec["expected_landing_url"].rstrip("/")
        exact_or_equivalent = any(m["url"].rstrip("/") == expected_url for m in valid)
        link_results[channel] = {
            "status": "PASS" if exact_or_equivalent else "PASS_EQUIVALENT_OFFICIAL_DOMAIN",
            "expected_authority": spec["expected_authority"],
            "expected_landing_url": spec["expected_landing_url"],
            "valid_matches": valid,
            "invalid_matches": invalid,
            "exact_expected_url_present": exact_or_equivalent,
        }

    update_date = parsed["page_update_date"]
    lag_days = None
    if not update_date:
        errors.append("UNPARSEABLE_HKEX_PAGE_UPDATE_DATE")
    else:
        try:
            validation = date.fromisoformat(validation_date)
            updated = date.fromisoformat(update_date)
            lag_days = (validation - updated).days
            max_lag = int(contract["hkex_page"].get("max_page_update_lag_days", 3))
            if lag_days < 0:
                errors.append("HKEX_PAGE_UPDATE_DATE_IN_FUTURE")
            elif lag_days > max_lag:
                errors.append("HKEX_PAGE_TOO_STALE")
        except Exception:
            errors.append("INVALID_DATE_ARITHMETIC")

    return {
        "status": "PASS_REFERENCE_CONSISTENT" if not errors else "BLOCKED_CROSSCHECK",
        "validation_date": validation_date,
        "hkex_page_update_date": update_date,
        "hkex_page_update_lag_days": lag_days,
        "heading_present": parsed["heading_present"],
        "link_results": link_results,
        "errors": errors,
        "security_level_independent_row_list_expected": False,
        "cross_check_role": "SECONDARY_OFFICIAL_STRUCTURAL_AND_LINKAGE_CROSS_CHECK",
        "primary_authority_unchanged": True,
        "publication_allowed": not errors,
        "candidate_pool_mutations": 0,
        "simulation_mutations": 0,
        "real_account_mutations": 0,
        "orders_created": 0,
        "trade_authority": "NONE",
    }


def run(contract_path: Path, output_dir: Path, validation_date: str) -> int:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    page = contract["hkex_page"]
    url = page["url"]
    if not _host_allowed(url, page["official_domains"]):
        raise ValueError("HKEX cross-check URL is not on configured official domain")

    session = requests.Session()
    retrieved_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    mode = "STATIC_HTTP_DOM"
    browser_diag: dict = {}
    http_status = 0
    error = None
    html = ""
    try:
        response = _get(session, url)
        http_status = response.status_code
        html = response.text
        parsed = parse_hkex_page(html, url, contract)
        if not parsed["heading_present"] or any(not parsed["links"][c]["matches"] for c in contract["required_links"]):
            rendered, browser_diag = _chrome_render(url)
            if rendered:
                html = rendered
                parsed = parse_hkex_page(html, url, contract)
                mode = "CHROME_RENDERED_DOM"
            else:
                mode = "STATIC_AND_BROWSER_INCOMPLETE"
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        rendered, browser_diag = _chrome_render(url)
        if rendered:
            html = rendered
            parsed = parse_hkex_page(html, url, contract)
            mode = "CHROME_RENDERED_DOM_AFTER_HTTP_FAILURE"
        else:
            parsed = {"heading_present": False, "page_update_date": None, "links": {c: {"matches": []} for c in contract["required_links"]}}
            mode = "BLOCKED_SOURCE"

    result = validate(parsed, contract, validation_date)
    if error:
        result["source_http_error"] = error
    result.update(
        {
            "source_id": page["source_id"],
            "source_url": url,
            "retrieved_at_utc": retrieved_at,
            "http_status": http_status,
            "acquisition_mode": mode,
            "raw_sha256": hashlib.sha256(html.encode("utf-8", errors="ignore")).hexdigest() if html else None,
            **browser_diag,
        }
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    if html:
        raw_dir = output_dir / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        (raw_dir / "HKEX_ELIGIBLE_SECURITIES_PAGE.html").write_text(html, encoding="utf-8")
    (output_dir / "HKCU1_R2D_HKEX_CROSSCHECK_DECISION.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["publication_allowed"] else 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--validation-date", required=True)
    args = parser.parse_args()
    return run(args.contract, args.output_dir, args.validation_date)


if __name__ == "__main__":
    raise SystemExit(main())
