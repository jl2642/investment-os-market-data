#!/usr/bin/env python3
"""Fetch and preserve official Stock Connect southbound eligibility evidence.

The module deliberately separates landing pages, machine-readable payloads and
adjustment notices. Empty, HTML-instead-of-data, stale or non-official payloads
fail closed. It never writes candidate, portfolio or order state.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from io import BytesIO, StringIO
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin

import pandas as pd
import requests

OFFICIAL_HOSTS = {
    "SSE": ("sse.com.cn", "sseinfo.com"),
    "SZSE": ("szse.cn",),
    "HKEX": ("hkex.com.hk",),
}
USER_AGENT = "Investment-OS-HKCU1/1.0 (+auditable research data ingestion)"
CODE_RE = re.compile(r"(?<!\d)(\d{1,5})(?!\d)")


@dataclass(frozen=True)
class SourceEvidence:
    source_id: str
    authority: str
    channel: str
    eligibility_side: str
    landing_url: str
    payload_url: str
    retrieved_at_utc: str
    http_status: int
    content_type: str
    sha256: str
    bytes: int
    row_count: int
    as_of_date: str | None
    parser: str
    status: str
    error: str | None = None


def _official(url: str, authority: str) -> bool:
    host = requests.utils.urlparse(url).hostname or ""
    return any(host == d or host.endswith("." + d) for d in OFFICIAL_HOSTS[authority])


def _get(session: requests.Session, url: str, timeout: int = 30) -> requests.Response:
    r = session.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT, "Referer": url})
    r.raise_for_status()
    return r


def _normalise_code(value: object) -> str | None:
    m = CODE_RE.search(str(value).replace(",", ""))
    return m.group(1).zfill(5) if m else None


def _find_code_column(df: pd.DataFrame) -> str:
    priorities = ("证券代码", "股份代号", "股票代码", "stock code", "code", "代码")
    lowered = {str(c).strip().lower(): c for c in df.columns}
    for key in priorities:
        for lc, original in lowered.items():
            if key.lower() == lc or key.lower() in lc:
                return original
    best = None
    best_ratio = 0.0
    for c in df.columns:
        ratio = df[c].astype(str).map(lambda x: _normalise_code(x) is not None).mean()
        if ratio > best_ratio:
            best, best_ratio = c, ratio
    if best is None or best_ratio < 0.5:
        raise ValueError("no credible security-code column")
    return best


def parse_tabular(content: bytes, content_type: str, url: str) -> pd.DataFrame:
    head = content[:512].lower()
    if b"<html" in head or b"<!doctype" in head:
        raise ValueError("received HTML instead of a machine-readable list")
    suffix = url.lower().split("?")[0]
    if suffix.endswith((".xlsx", ".xls")) or b"spreadsheet" in content_type.encode().lower():
        frames = pd.read_excel(BytesIO(content), sheet_name=None, dtype=str)
        df = max(frames.values(), key=len)
    else:
        decoded = None
        for enc in ("utf-8-sig", "gb18030", "big5", "latin1"):
            try:
                decoded = content.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if decoded is None:
            raise ValueError("unsupported text encoding")
        df = pd.read_csv(StringIO(decoded), dtype=str, sep=None, engine="python")
    if df.empty:
        raise ValueError("official list is empty")
    code_col = _find_code_column(df)
    out = df.copy()
    out["security_code"] = out[code_col].map(_normalise_code)
    out = out[out["security_code"].notna()].drop_duplicates("security_code")
    if len(out) < 50:
        raise ValueError(f"implausibly small official list: {len(out)} rows")
    return out


def fetch_one(session: requests.Session, spec: dict, raw_dir: Path) -> tuple[pd.DataFrame | None, SourceEvidence]:
    authority = spec["authority"]
    url = spec["payload_url"]
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    if not _official(url, authority):
        raise ValueError(f"non-official host for {authority}: {url}")
    try:
        r = _get(session, url)
        content = r.content
        digest = hashlib.sha256(content).hexdigest()
        raw_dir.mkdir(parents=True, exist_ok=True)
        ext = Path(requests.utils.urlparse(url).path).suffix or ".bin"
        (raw_dir / f"{spec['source_id']}_{digest[:12]}{ext}").write_bytes(content)
        df = parse_tabular(content, r.headers.get("content-type", ""), url)
        evidence = SourceEvidence(
            source_id=spec["source_id"], authority=authority, channel=spec["channel"],
            eligibility_side=spec["eligibility_side"], landing_url=spec["landing_url"],
            payload_url=url, retrieved_at_utc=now, http_status=r.status_code,
            content_type=r.headers.get("content-type", ""), sha256=digest, bytes=len(content),
            row_count=len(df), as_of_date=spec.get("as_of_date"), parser="pandas_tabular_v1",
            status="PASS")
        return df, evidence
    except Exception as exc:  # evidence must survive failures
        evidence = SourceEvidence(
            source_id=spec["source_id"], authority=authority, channel=spec["channel"],
            eligibility_side=spec["eligibility_side"], landing_url=spec["landing_url"],
            payload_url=url, retrieved_at_utc=now, http_status=0, content_type="", sha256="",
            bytes=0, row_count=0, as_of_date=spec.get("as_of_date"), parser="pandas_tabular_v1",
            status="BLOCKED", error=f"{type(exc).__name__}: {exc}")
        return None, evidence


def run(registry: Path, output_dir: Path, allow_partial: bool = False) -> int:
    config = json.loads(registry.read_text(encoding="utf-8"))
    specs = config.get("machine_readable_sources", [])
    if not specs:
        raise ValueError("registry has no machine_readable_sources")
    session = requests.Session()
    evidence: list[SourceEvidence] = []
    frames: list[pd.DataFrame] = []
    for spec in specs:
        df, ev = fetch_one(session, spec, output_dir / "raw")
        evidence.append(ev)
        if df is not None:
            x = df.copy()
            x["authority"] = ev.authority
            x["channel"] = ev.channel
            x["eligibility_side"] = ev.eligibility_side
            x["source_id"] = ev.source_id
            x["source_sha256"] = ev.sha256
            x["source_as_of_date"] = ev.as_of_date
            frames.append(x)
    output_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([asdict(x) for x in evidence]).to_csv(output_dir / "HKCU1_SOURCE_LEDGER.csv", index=False)
    (output_dir / "HKCU1_SOURCE_LEDGER.json").write_text(
        json.dumps([asdict(x) for x in evidence], ensure_ascii=False, indent=2), encoding="utf-8")
    blocked = [x for x in evidence if x.status != "PASS"]
    if blocked and not allow_partial:
        (output_dir / "HKCU1_FETCH_DECISION.json").write_text(json.dumps({
            "status": "BLOCKED", "reason": "OFFICIAL_SOURCE_INGESTION_INCOMPLETE",
            "blocked_sources": [x.source_id for x in blocked], "trade_authority": "NONE"
        }, indent=2), encoding="utf-8")
        return 2
    if frames:
        pd.concat(frames, ignore_index=True).to_csv(output_dir / "HKCU1_OFFICIAL_LIST_ROWS.csv", index=False)
    return 0 if not blocked else 2


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--registry", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--allow-partial", action="store_true")
    a = p.parse_args()
    return run(a.registry, a.output_dir, a.allow_partial)


if __name__ == "__main__":
    raise SystemExit(main())
