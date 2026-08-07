#!/usr/bin/env python3
"""Fetch official SSE/SZSE Stock Connect adjustment notices and normalize events.

R2C design:
- authority comes only from official SSE/SZSE domains;
- notice-index discovery is incremental and may be supplemented by official bootstrap URLs;
- 调入 -> IN; 调出 -> OUT (reconstructed as SELL_ONLY, not terminal deletion);
- explicit effective dates are preserved;
- SSE's "next Stock Connect trading day" rule is resolved against the versioned
  official Stock Connect calendar for the requested as-of year;
- future-effective events are retained as evidence but are not applied early;
- partial historical coverage is never promoted as production-complete.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

from pipeline.hkcu1_resolve_effective_dates import resolve_events

OFFICIAL_HOSTS = {
    "SSE": ("sse.com.cn", "sseinfo.com"),
    "SZSE": ("szse.cn",),
}
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131 Safari/537.36 Investment-OS-HKCU1"
CODE_RE = re.compile(r"(?<!\d)(\d{1,5})(?!\d)")
DATE_CN_RE = re.compile(r"(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日")
DATE_ISO_RE = re.compile(r"(20\d{2})[-/]([01]?\d)[-/]([0-3]?\d)")
EXPLICIT_EFFECTIVE_RE = re.compile(r"自\s*(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日\s*起生效")


@dataclass(frozen=True)
class NoticeEvidence:
    authority: str
    channel: str
    source_url: str
    retrieved_at_utc: str
    http_status: int
    sha256: str
    bytes: int
    announcement_date: str | None
    event_rows: int
    status: str
    failure_class: str
    error: str | None = None


def _official(url: str, authority: str) -> bool:
    host = urlparse(url).hostname or ""
    return any(host == d or host.endswith("." + d) for d in OFFICIAL_HOSTS[authority])


def _get(session: requests.Session, url: str, referer: str, attempts: int = 3) -> requests.Response:
    last: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            r = session.get(url, timeout=20, headers={"User-Agent": USER_AGENT, "Referer": referer, "Accept": "text/html,*/*"})
            if r.status_code in {403, 429} or r.status_code >= 500:
                r.raise_for_status()
            r.raise_for_status()
            return r
        except Exception as exc:
            last = exc
            if attempt < attempts:
                time.sleep(min(attempt * 3, 6))
    assert last is not None
    raise last


def _failure_class(exc: Exception) -> str:
    text = str(exc).lower()
    if "403" in text or "429" in text:
        return "SOURCE_BLOCKED"
    if "timeout" in text or "connection" in text or "502" in text or "503" in text or "504" in text:
        return "TRANSIENT_INFRA"
    return "UNKNOWN"


def _date_iso(parts: tuple[str, str, str]) -> str:
    y, m, d = (int(x) for x in parts)
    return f"{y:04d}-{m:02d}-{d:02d}"


def _find_announcement_date(text: str) -> str | None:
    match = DATE_CN_RE.search(text) or DATE_ISO_RE.search(text)
    return _date_iso(match.groups()) if match else None


def _effective_date_and_rule(text: str, announcement_date: str | None) -> tuple[str | None, str]:
    match = EXPLICIT_EFFECTIVE_RE.search(text)
    if match:
        return _date_iso(match.groups()), "EXPLICIT_IN_NOTICE"
    if "自下一港股通交易日起生效" in text or "下一港股通交易日起生效" in text:
        return None, "NEXT_STOCK_CONNECT_TRADING_DAY"
    if "自今日起生效" in text and announcement_date:
        return announcement_date, "SAME_DAY_IN_NOTICE"
    return None, "UNRESOLVED_EFFECTIVE_DATE"


def _code(value: object) -> str | None:
    m = CODE_RE.search(str(value).replace(",", ""))
    return m.group(1).zfill(5) if m else None


def _normalise_direction(value: object) -> str | None:
    text = str(value).strip()
    if "调入" in text:
        return "IN"
    if "调出" in text:
        return "OUT"
    return None


def parse_notice_html(content: bytes, source_url: str, authority: str, channel: str, retrieved_at: str) -> tuple[list[dict], str | None]:
    text = content.decode("utf-8", errors="ignore")
    if len(text.strip()) < 100:
        text = content.decode("gb18030", errors="ignore")
    soup = BeautifulSoup(text, "html.parser")
    plain = soup.get_text(" ", strip=True)
    announcement_date = _find_announcement_date(plain)
    effective_from, effective_rule = _effective_date_and_rule(plain, announcement_date)
    digest = hashlib.sha256(content).hexdigest()

    events: list[dict] = []
    try:
        tables = pd.read_html(text)
    except ValueError:
        tables = []
    for table in tables:
        if table.empty:
            continue
        code_col = next((c for c in table.columns if "代码" in str(c)), None)
        direction_col = next((c for c in table.columns if "调整方向" in str(c) or "方向" == str(c).strip()), None)
        if code_col is None or direction_col is None:
            continue
        name_cols = [c for c in table.columns if "简称" in str(c)]
        for _, row in table.iterrows():
            code = _code(row.get(code_col))
            direction = _normalise_direction(row.get(direction_col))
            if not code or not direction:
                continue
            name = ""
            for c in name_cols:
                candidate = str(row.get(c) or "").strip()
                if candidate and candidate.lower() != "nan":
                    name = candidate
                    break
            events.append({
                "security_code": code,
                "channel": channel,
                "direction": direction,
                "security_name": name,
                "announcement_date": announcement_date,
                "effective_from": effective_from,
                "effective_rule": effective_rule,
                "source_authority": authority,
                "source_document_type": "ADJUSTMENT_NOTICE",
                "source_url": source_url,
                "source_id": f"{authority}_ADJUSTMENT_NOTICE",
                "source_sha256": digest,
                "retrieved_at_utc": retrieved_at,
            })
    unique: dict[tuple[str, str, str], dict] = {}
    for row in events:
        unique[(row["security_code"], row["channel"], row["direction"])] = row
    return list(unique.values()), announcement_date


def discover_notice_urls(session: requests.Session, spec: dict) -> tuple[list[str], dict]:
    authority = spec["authority"]
    index_url = spec["index_url"]
    if not _official(index_url, authority):
        raise ValueError(f"non-official index URL: {index_url}")
    response = _get(session, index_url, index_url)
    soup = BeautifulSoup(response.text, "html.parser")
    title_needles = tuple(spec.get("title_contains", []))
    urls: list[str] = []
    for a in soup.find_all("a", href=True):
        title = a.get_text(" ", strip=True)
        if title_needles and not any(needle in title for needle in title_needles):
            continue
        url = urljoin(index_url, a["href"])
        if _official(url, authority):
            urls.append(url)
    urls.extend(spec.get("bootstrap_notice_urls", []))
    deduped = list(dict.fromkeys(urls))
    return deduped, {
        "authority": authority,
        "channel": spec["channel"],
        "index_url": index_url,
        "status": "PASS",
        "failure_class": "NONE",
        "http_status": response.status_code,
        "discovered_urls": len(deduped),
    }


def _coverage_complete(specs: list[dict]) -> bool:
    return all(str(spec.get("bootstrap_coverage", "")).upper() == "COMPLETE_HISTORY" for spec in specs)


def run(registry: Path, output_dir: Path, as_of_date: str | None = None) -> int:
    config = json.loads(registry.read_text(encoding="utf-8"))
    specs = config.get("adjustment_notice_sources", [])
    if not specs:
        raise ValueError("registry has no adjustment_notice_sources")
    session = requests.Session()
    evidence: list[NoticeEvidence] = []
    index_ledger: list[dict] = []
    events: list[dict] = []
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    for spec in specs:
        authority, channel = spec["authority"], spec["channel"]
        try:
            urls, index_row = discover_notice_urls(session, spec)
            index_ledger.append(index_row)
        except Exception as exc:
            urls = list(spec.get("bootstrap_notice_urls", []))
            index_ledger.append({
                "authority": authority, "channel": channel, "index_url": spec["index_url"],
                "status": "BLOCKED", "failure_class": _failure_class(exc), "error": f"{type(exc).__name__}: {exc}",
                "discovered_urls": len(urls),
            })

        for url in urls:
            if not _official(url, authority):
                continue
            try:
                response = _get(session, url, spec["index_url"])
                rows, announcement_date = parse_notice_html(response.content, url, authority, channel, now)
                if as_of_date and announcement_date and announcement_date > as_of_date:
                    rows = []
                digest = hashlib.sha256(response.content).hexdigest()
                evidence.append(NoticeEvidence(authority, channel, url, now, response.status_code, digest,
                                               len(response.content), announcement_date, len(rows), "PASS", "NONE"))
                events.extend(rows)
            except Exception as exc:
                evidence.append(NoticeEvidence(authority, channel, url, now, 0, "", 0, None, 0,
                                               "BLOCKED", _failure_class(exc), f"{type(exc).__name__}: {exc}"))

    if events:
        frame = pd.DataFrame(events)
        frame = frame.sort_values(["announcement_date", "channel", "security_code", "direction", "source_url"], na_position="last")
        frame = frame.drop_duplicates(["security_code", "channel", "direction", "announcement_date", "source_url"])
    else:
        frame = pd.DataFrame(columns=[
            "security_code", "channel", "direction", "security_name", "announcement_date", "effective_from",
            "effective_rule", "source_authority", "source_document_type", "source_url", "source_id",
            "source_sha256", "retrieved_at_utc",
        ])

    output_dir.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output_dir / "HKCU1_ADJUSTMENT_EVENTS.csv", index=False)

    resolved = frame.copy()
    calendar_id = None
    calendar_error = None
    if not frame.empty:
        year = int((as_of_date or now[:10])[:4])
        calendar_path = registry.parent / f"hkcu1_stock_connect_calendar_{year}.json"
        try:
            calendar = json.loads(calendar_path.read_text(encoding="utf-8"))
            calendar_id = calendar.get("calendar_id")
            resolved = resolve_events(frame, calendar, as_of_date)
        except Exception as exc:
            calendar_error = f"{type(exc).__name__}: {exc}"
    resolved.to_csv(output_dir / "HKCU1_ADJUSTMENT_EVENTS_RESOLVED.csv", index=False)

    (output_dir / "HKCU1_ADJUSTMENT_NOTICE_LEDGER.json").write_text(
        json.dumps([asdict(x) for x in evidence], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output_dir / "HKCU1_ADJUSTMENT_INDEX_LEDGER.json").write_text(
        json.dumps(index_ledger, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    unresolved = 0
    future = 0
    if not resolved.empty:
        unresolved = int(resolved["effective_from"].fillna("").astype(str).str.strip().eq("").sum())
        if "future_event" in resolved.columns:
            future = int(resolved["future_event"].sum())
    blocked_channels = sorted({row["channel"] for row in index_ledger if row["status"] != "PASS" and not any(
        ev.authority == row["authority"] and ev.status == "PASS" for ev in evidence
    )})
    historical_complete = _coverage_complete(specs)
    source_ok = not blocked_channels and calendar_error is None and unresolved == 0
    decision = {
        "status": "PASS" if source_ok else "DEGRADED",
        "event_rows": int(len(resolved)),
        "unresolved_effective_date_rows": unresolved,
        "future_effective_event_rows": future,
        "blocked_channels": blocked_channels,
        "calendar_id": calendar_id,
        "calendar_error": calendar_error,
        "sell_only_semantics": "OUT_TO_SELL_ONLY",
        "historical_coverage_complete": historical_complete,
        "coverage_gate": "PASS" if historical_complete else "BLOCKED_PARTIAL_HISTORY",
        "publication_allowed": source_ok and historical_complete,
        "trade_authority": "NONE",
    }
    (output_dir / "HKCU1_R2C_EVENT_DECISION.json").write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--registry", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--as-of-date")
    a = p.parse_args()
    return run(a.registry, a.output_dir, a.as_of_date)


if __name__ == "__main__":
    raise SystemExit(main())
