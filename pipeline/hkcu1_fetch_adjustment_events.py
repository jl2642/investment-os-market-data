#!/usr/bin/env python3
"""Fetch official SSE/SZSE Stock Connect adjustment notices and normalize events.

R2C operating model:
- official SSE/SZSE domains only;
- current official notice indices are the forward-discovery authority;
- bootstrap URLs are audit/replay seeds only, never a substitute for live discovery;
- raw notice HTML is preserved with SHA-256;
- 调入 -> IN; 调出 -> OUT (later reconstructed as SELL_ONLY);
- effective dates are resolved from the versioned official Stock Connect calendar;
- the visible official notice-index window must reach back to the prior scan cursor,
  otherwise forward completeness fails closed;
- a successful run emits the next cursor but does not silently persist/promote it.
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

try:
    from pipeline.hkcu1_resolve_effective_dates import resolve_events
except ModuleNotFoundError:
    from hkcu1_resolve_effective_dates import resolve_events

OFFICIAL_HOSTS = {"SSE": ("sse.com.cn", "sseinfo.com"), "SZSE": ("szse.cn",)}
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
    discovery_origin: str
    retrieved_at_utc: str
    http_status: int
    sha256: str
    bytes: int
    announcement_date: str | None
    event_rows: int
    status: str
    failure_class: str
    raw_file: str | None = None
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
    if any(token in text for token in ("timeout", "connection", "502", "503", "504")):
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


def _table_events(soup: BeautifulSoup) -> list[tuple[str, str, str]]:
    output: list[tuple[str, str, str]] = []
    for table in soup.find_all("table"):
        rows = [[cell.get_text(" ", strip=True) for cell in tr.find_all(["th", "td"])] for tr in table.find_all("tr")]
        rows = [row for row in rows if row]
        if not rows:
            continue
        header_idx = code_idx = direction_idx = None
        name_indices: list[int] = []
        for idx, cells in enumerate(rows):
            ci = next((i for i, value in enumerate(cells) if "代码" in value), None)
            di = next((i for i, value in enumerate(cells) if "调整方向" in value or value.strip() == "方向"), None)
            if ci is not None and di is not None:
                header_idx, code_idx, direction_idx = idx, ci, di
                name_indices = [i for i, value in enumerate(cells) if "简称" in value]
                break
        if header_idx is None or code_idx is None or direction_idx is None:
            continue
        for cells in rows[header_idx + 1:]:
            if max(code_idx, direction_idx) >= len(cells):
                continue
            code = _code(cells[code_idx])
            direction = _normalise_direction(cells[direction_idx])
            if not code or not direction:
                continue
            name = ""
            for i in reversed(name_indices):
                if i < len(cells) and cells[i].strip() not in {"", "-"}:
                    name = cells[i].strip()
                    break
            output.append((code, name, direction))
    return output


def parse_notice_html(content: bytes, source_url: str, authority: str, channel: str, retrieved_at: str) -> tuple[list[dict], str | None]:
    text = content.decode("utf-8", errors="ignore")
    if len(text.strip()) < 100:
        text = content.decode("gb18030", errors="ignore")
    soup = BeautifulSoup(text, "html.parser")
    plain = soup.get_text(" ", strip=True)
    announcement_date = _find_announcement_date(plain)
    effective_from, effective_rule = _effective_date_and_rule(plain, announcement_date)
    digest = hashlib.sha256(content).hexdigest()
    events = []
    for code, name, direction in _table_events(soup):
        events.append({
            "security_code": code, "channel": channel, "direction": direction, "security_name": name,
            "announcement_date": announcement_date, "effective_from": effective_from,
            "effective_rule": effective_rule, "source_authority": authority,
            "source_document_type": "ADJUSTMENT_NOTICE", "source_url": source_url,
            "source_id": f"{authority}_ADJUSTMENT_NOTICE", "source_sha256": digest,
            "retrieved_at_utc": retrieved_at,
        })
    unique: dict[tuple[str, str, str], dict] = {}
    for row in events:
        unique[(row["security_code"], row["channel"], row["direction"])] = row
    return list(unique.values()), announcement_date


def discover_notice_urls(session: requests.Session, spec: dict) -> tuple[list[str], set[str], dict]:
    authority = spec["authority"]
    index_url = spec["index_url"]
    if not _official(index_url, authority):
        raise ValueError(f"non-official index URL: {index_url}")
    response = _get(session, index_url, index_url)
    soup = BeautifulSoup(response.text, "html.parser")
    title_needles = tuple(spec.get("title_contains", []))
    index_urls: list[str] = []
    for a in soup.find_all("a", href=True):
        title = a.get_text(" ", strip=True)
        if title_needles and not any(needle in title for needle in title_needles):
            continue
        url = urljoin(index_url, a["href"])
        if _official(url, authority):
            index_urls.append(url)
    index_urls = list(dict.fromkeys(index_urls))
    bootstrap_urls = [u for u in spec.get("bootstrap_notice_urls", []) if _official(u, authority)]
    all_urls = list(dict.fromkeys(index_urls + bootstrap_urls))
    return all_urls, set(index_urls), {
        "authority": authority, "channel": spec["channel"], "index_url": index_url,
        "status": "PASS", "failure_class": "NONE", "http_status": response.status_code,
        "index_discovered_urls": len(index_urls), "bootstrap_urls": len(bootstrap_urls),
        "total_fetch_urls": len(all_urls),
    }


def _load_bootstrap(config: dict, registry: Path) -> dict:
    ref = config.get("r2c_bootstrap_contract")
    if not ref:
        raise ValueError("registry missing r2c_bootstrap_contract")
    repo_root = registry.parent.parent
    path = repo_root / ref if not Path(ref).is_absolute() else Path(ref)
    return json.loads(path.read_text(encoding="utf-8"))


def run(registry: Path, output_dir: Path, as_of_date: str | None = None) -> int:
    config = json.loads(registry.read_text(encoding="utf-8"))
    bootstrap = _load_bootstrap(config, registry)
    specs = config.get("adjustment_notice_sources", [])
    if not specs:
        raise ValueError("registry has no adjustment_notice_sources")
    as_of_date = as_of_date or datetime.now(timezone.utc).date().isoformat()
    cursors = bootstrap.get("initial_scan_cursor", {})

    session = requests.Session()
    evidence: list[NoticeEvidence] = []
    index_ledger: list[dict] = []
    index_sets: dict[str, set[str]] = {}
    events: list[dict] = []
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    raw_dir = output_dir / "raw_notices"
    raw_dir.mkdir(parents=True, exist_ok=True)

    for spec in specs:
        authority, channel = spec["authority"], spec["channel"]
        try:
            urls, index_urls, index_row = discover_notice_urls(session, spec)
            index_sets[channel] = index_urls
            index_ledger.append(index_row)
        except Exception as exc:
            index_sets[channel] = set()
            urls = [u for u in spec.get("bootstrap_notice_urls", []) if _official(u, authority)]
            index_ledger.append({
                "authority": authority, "channel": channel, "index_url": spec["index_url"],
                "status": "BLOCKED", "failure_class": _failure_class(exc),
                "error": f"{type(exc).__name__}: {exc}", "index_discovered_urls": 0,
                "bootstrap_urls": len(urls), "total_fetch_urls": len(urls),
            })

        for url in urls:
            origin = "LIVE_INDEX" if url in index_sets[channel] else "BOOTSTRAP_SEED"
            try:
                response = _get(session, url, spec["index_url"])
                digest = hashlib.sha256(response.content).hexdigest()
                raw_name = f"{authority}_{channel}_{digest[:16]}.html"
                (raw_dir / raw_name).write_bytes(response.content)
                rows, announcement_date = parse_notice_html(response.content, url, authority, channel, now)
                if announcement_date and announcement_date > as_of_date:
                    rows = []
                evidence.append(NoticeEvidence(authority, channel, url, origin, now, response.status_code, digest,
                                               len(response.content), announcement_date, len(rows), "PASS", "NONE", raw_name))
                events.extend(rows)
            except Exception as exc:
                evidence.append(NoticeEvidence(authority, channel, url, origin, now, 0, "", 0, None, 0,
                                               "BLOCKED", _failure_class(exc), None, f"{type(exc).__name__}: {exc}"))

    if events:
        frame = pd.DataFrame(events).sort_values(
            ["announcement_date", "channel", "security_code", "direction", "source_url"], na_position="last"
        ).drop_duplicates(["security_code", "channel", "direction", "announcement_date", "source_url"])
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
        year = int(as_of_date[:4])
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

    unresolved = int(resolved["effective_from"].fillna("").astype(str).str.strip().eq("").sum()) if not resolved.empty else 0
    future = int(resolved["future_event"].sum()) if not resolved.empty and "future_event" in resolved.columns else 0
    zero_event_notices = sum(1 for ev in evidence if ev.status == "PASS" and ev.event_rows == 0)
    parsed_event_notices = sum(1 for ev in evidence if ev.status == "PASS" and ev.event_rows > 0)

    coverage: dict[str, dict] = {}
    for channel in ("SH", "SZ"):
        cursor = str(cursors.get(channel) or bootstrap["bootstrap_date"])
        live = [ev for ev in evidence if ev.channel == channel and ev.discovery_origin == "LIVE_INDEX" and ev.status == "PASS" and ev.announcement_date]
        dates = sorted({str(ev.announcement_date) for ev in live})
        index_row = next((row for row in index_ledger if row["channel"] == channel), {})
        reaches_cursor = bool(dates and min(dates) <= cursor)
        coverage[channel] = {
            "cursor_date": cursor,
            "live_index_notice_count": len(live),
            "oldest_live_notice_date": min(dates) if dates else None,
            "newest_live_notice_date": max(dates) if dates else None,
            "index_discovered_urls": int(index_row.get("index_discovered_urls", 0)),
            "index_window_reaches_cursor": reaches_cursor,
            "status": "PASS" if index_row.get("status") == "PASS" and reaches_cursor else "BLOCKED_COVERAGE_GAP",
        }

    blocked_channels = sorted(ch for ch, row in coverage.items() if row["status"] != "PASS")
    forward_complete = not blocked_channels and calendar_error is None and unresolved == 0 and parsed_event_notices > 0
    next_cursor = {"SH": as_of_date, "SZ": as_of_date} if forward_complete else dict(cursors)
    next_cursor_payload = {
        "bootstrap_date": bootstrap["bootstrap_date"], "scan_completed_through": next_cursor,
        "may_persist_only_after_release_gate": True, "trade_authority": "NONE"
    }
    (output_dir / "HKCU1_NEXT_EVENT_CURSOR.json").write_text(
        json.dumps(next_cursor_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output_dir / "HKCU1_ADJUSTMENT_INDEX_LEDGER.json").write_text(
        json.dumps(index_ledger, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    decision = {
        "status": "PASS_FORWARD_COMPLETE" if forward_complete else "DEGRADED",
        "event_rows": int(len(resolved)), "parsed_event_notices": parsed_event_notices,
        "zero_event_notices": zero_event_notices, "unresolved_effective_date_rows": unresolved,
        "future_effective_event_rows": future, "blocked_channels": blocked_channels,
        "calendar_id": calendar_id, "calendar_error": calendar_error,
        "sell_only_semantics": "OUT_TO_SELL_ONLY",
        "bootstrap_date": bootstrap["bootstrap_date"],
        "legacy_sell_only_history_complete": False,
        "pre_bootstrap_unknown_policy": "UNKNOWN_BLOCKED_NOT_BUYABLE",
        "forward_complete_from_bootstrap": forward_complete,
        "coverage_by_channel": coverage,
        "r2c_layer_usable": forward_complete,
        "publication_allowed": forward_complete,
        "next_cursor": next_cursor,
        "trade_authority": "NONE",
    }
    (output_dir / "HKCU1_R2C_EVENT_DECISION.json").write_text(
        json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8"
    )
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
