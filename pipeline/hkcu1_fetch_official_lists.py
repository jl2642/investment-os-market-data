#!/usr/bin/env python3
"""Fetch and preserve official Stock Connect southbound eligibility evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from io import BytesIO, StringIO
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import pandas as pd
import requests

OFFICIAL_HOSTS = {"SSE": ("sse.com.cn", "sseinfo.com"), "SZSE": ("szse.cn",), "HKEX": ("hkex.com.hk",)}
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131 Safari/537.36 Investment-OS-HKCU1"
CODE_RE = re.compile(r"(?<!\d)(\d{1,5})(?!\d)")

@dataclass(frozen=True)
class SourceEvidence:
    source_id: str; authority: str; channel: str; eligibility_side: str
    landing_url: str; payload_url: str; retrieved_at_utc: str; http_status: int
    content_type: str; sha256: str; bytes: int; row_count: int
    as_of_date: str | None; parser: str; status: str; error: str | None = None
    declared_record_count: int | None = None; page_count: int | None = None


def _official(url: str, authority: str) -> bool:
    host = urlparse(url).hostname or ""
    return any(host == d or host.endswith("." + d) for d in OFFICIAL_HOSTS[authority])


def _get(session: requests.Session, url: str, referer: str, timeout: int = 45) -> requests.Response:
    r = session.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT, "Referer": referer, "Accept": "*/*"})
    r.raise_for_status(); return r


def _normalise_code(value: object) -> str | None:
    m = CODE_RE.search(str(value).replace(",", "")); return m.group(1).zfill(5) if m else None


def _find_code_column(df: pd.DataFrame) -> str:
    priorities = ("证券代码", "股份代号", "股票代码", "stock code", "code", "代码", "zqdm")
    for c in df.columns:
        lc = str(c).strip().lower()
        if any(k.lower() == lc or k.lower() in lc for k in priorities): return c
    scores = {c: df[c].astype(str).map(lambda x: _normalise_code(x) is not None).mean() for c in df.columns}
    best = max(scores, key=scores.get)
    if scores[best] < 0.5: raise ValueError("no credible security-code column")
    return best


def _standardise(df: pd.DataFrame, expected_min_rows: int) -> pd.DataFrame:
    if df.empty: raise ValueError("official list is empty")
    code_col = _find_code_column(df)
    out = df.copy(); out["security_code"] = out[code_col].map(_normalise_code)
    out = out[out.security_code.notna()].drop_duplicates("security_code")
    if len(out) < expected_min_rows: raise ValueError(f"implausibly small official list: {len(out)} rows")
    return out


def parse_sse_excel(content: bytes, expected_min_rows: int) -> pd.DataFrame:
    if content[:4] not in (b"PK\x03\x04", b"\xd0\xcf\x11\xe0"):
        raise ValueError("SSE payload is not a valid XLS/XLSX signature")
    frames = pd.read_excel(BytesIO(content), sheet_name=None, dtype=str)
    return _standardise(max(frames.values(), key=len), expected_min_rows)


def _set_query(url: str, **updates: object) -> str:
    p = urlparse(url); q = dict(parse_qsl(p.query, keep_blank_values=True)); q.update({k: str(v) for k, v in updates.items()})
    return urlunparse((p.scheme, p.netloc, p.path, p.params, urlencode(q), p.fragment))


def fetch_szse_paginated(session: requests.Session, spec: dict) -> tuple[pd.DataFrame, bytes, int, int, str]:
    first = _get(session, _set_query(spec["payload_url"], PAGENO=1), spec["referer"])
    payload = first.json()
    if not isinstance(payload, list) or len(payload) != 1: raise ValueError("unexpected SZSE top-level payload")
    section = payload[0]; metadata = section.get("metadata") or {}
    if metadata.get("catalogid") != spec.get("catalog_id"): raise ValueError("SZSE catalog identity mismatch")
    if metadata.get("name") != spec.get("expected_metadata_name"): raise ValueError("SZSE report name mismatch")
    page_count = int(metadata["pagecount"]); record_count = int(metadata["recordcount"])
    list_date = str(metadata.get("subname") or spec.get("as_of_date") or "")
    rows: list[dict] = []
    raw_pages: list[bytes] = []
    for page_no in range(1, page_count + 1):
        r = first if page_no == 1 else _get(session, _set_query(spec["payload_url"], PAGENO=page_no), spec["referer"])
        raw_pages.append(r.content); data = r.json()[0]
        md = data.get("metadata") or {}
        if int(md.get("pageno", page_no)) != page_no or int(md.get("recordcount", record_count)) != record_count:
            raise ValueError(f"SZSE pagination metadata mismatch at page {page_no}")
        rows.extend(data.get("data") or [])
    df = _standardise(pd.DataFrame(rows), int(spec.get("expected_min_rows", 100)))
    if len(df) != record_count: raise ValueError(f"SZSE count mismatch: deduplicated={len(df)} declared={record_count}")
    canonical_raw = b"\n".join(raw_pages)
    return df, canonical_raw, record_count, page_count, list_date


def fetch_one(session: requests.Session, spec: dict, raw_dir: Path) -> tuple[pd.DataFrame | None, SourceEvidence]:
    authority, url = spec["authority"], spec["payload_url"]
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    if not _official(url, authority): raise ValueError(f"non-official host for {authority}: {url}")
    try:
        parser = spec["parser"]
        if parser == "SSE_EXCEL":
            r = _get(session, url, spec["referer"]); raw = r.content
            df = parse_sse_excel(raw, int(spec.get("expected_min_rows", 100)))
            status, ctype, declared, pages, list_date = r.status_code, r.headers.get("content-type", ""), len(df), 1, spec.get("as_of_date")
        elif parser == "SZSE_PAGINATED_JSON":
            df, raw, declared, pages, list_date = fetch_szse_paginated(session, spec)
            status, ctype = 200, "application/json"
        else: raise ValueError(f"unsupported parser: {parser}")
        digest = hashlib.sha256(raw).hexdigest(); raw_dir.mkdir(parents=True, exist_ok=True)
        (raw_dir / f"{spec['source_id']}_{digest[:12]}.bin").write_bytes(raw)
        ev = SourceEvidence(spec["source_id"], authority, spec["channel"], spec["eligibility_side"], spec["landing_url"], url, now, status, ctype, digest, len(raw), len(df), list_date, parser, "PASS", None, declared, pages)
        return df, ev
    except Exception as exc:
        ev = SourceEvidence(spec["source_id"], authority, spec["channel"], spec["eligibility_side"], spec["landing_url"], url, now, 0, "", "", 0, 0, spec.get("as_of_date"), spec.get("parser", "UNKNOWN"), "BLOCKED", f"{type(exc).__name__}: {exc}")
        return None, ev


def run(registry: Path, output_dir: Path, allow_partial: bool = False) -> int:
    config = json.loads(registry.read_text(encoding="utf-8")); specs = config.get("machine_readable_sources", [])
    if not specs: raise ValueError("registry has no machine_readable_sources")
    session = requests.Session(); evidence=[]; frames=[]
    for spec in specs:
        df, ev = fetch_one(session, spec, output_dir / "raw"); evidence.append(ev)
        if df is not None:
            x=df.copy(); x["authority"]=ev.authority; x["channel"]=ev.channel; x["eligibility_side"]=ev.eligibility_side
            x["source_id"]=ev.source_id; x["source_sha256"]=ev.sha256; x["source_as_of_date"]=ev.as_of_date; frames.append(x)
    output_dir.mkdir(parents=True, exist_ok=True)
    ledger=pd.DataFrame([asdict(x) for x in evidence]); ledger.to_csv(output_dir/"HKCU1_SOURCE_LEDGER.csv",index=False)
    (output_dir/"HKCU1_SOURCE_LEDGER.json").write_text(json.dumps([asdict(x) for x in evidence],ensure_ascii=False,indent=2),encoding="utf-8")
    blocked=[x for x in evidence if x.status!="PASS"]
    decision={"status":"PASS" if not blocked else "BLOCKED","blocked_sources":[x.source_id for x in blocked],"source_rows":{x.source_id:x.row_count for x in evidence},"trade_authority":"NONE"}
    (output_dir/"HKCU1_FETCH_DECISION.json").write_text(json.dumps(decision,ensure_ascii=False,indent=2),encoding="utf-8")
    if frames: pd.concat(frames,ignore_index=True).to_csv(output_dir/"HKCU1_OFFICIAL_LIST_ROWS.csv",index=False)
    return 0 if not blocked or allow_partial else 2


def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument("--registry",type=Path,required=True); p.add_argument("--output-dir",type=Path,required=True); p.add_argument("--allow-partial",action="store_true")
    a=p.parse_args(); return run(a.registry,a.output_dir,a.allow_partial)

if __name__=="__main__": raise SystemExit(main())
