#!/usr/bin/env python3
"""Fetch and preserve official Stock Connect southbound eligibility evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import pandas as pd
import requests

OFFICIAL_HOSTS = {"SSE": ("sse.com.cn", "sseinfo.com"), "SZSE": ("szse.cn",), "HKEX": ("hkex.com.hk",)}
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131 Safari/537.36 Investment-OS-HKCU1"
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
    declared_record_count: int | None = None
    page_count: int | None = None
    acquisition_mode: str = "DIRECT_OFFICIAL_FETCH"


def _official(url: str, authority: str) -> bool:
    host = urlparse(url).hostname or ""
    return any(host == d or host.endswith("." + d) for d in OFFICIAL_HOSTS[authority])


def _get(session: requests.Session, url: str, referer: str, timeout: int = 45) -> requests.Response:
    response = session.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT, "Referer": referer, "Accept": "*/*"})
    response.raise_for_status()
    return response


def _normalise_code(value: object) -> str | None:
    match = CODE_RE.search(str(value).replace(",", ""))
    return match.group(1).zfill(5) if match else None


def _find_code_column(df: pd.DataFrame) -> str:
    priorities = ("证券代码", "股份代号", "股票代码", "stock code", "code", "代码", "zqdm")
    for column in df.columns:
        label = str(column).strip().lower()
        if any(key.lower() == label or key.lower() in label for key in priorities):
            return column
    scores = {column: df[column].astype(str).map(lambda value: _normalise_code(value) is not None).mean() for column in df.columns}
    best = max(scores, key=scores.get)
    if scores[best] < 0.5:
        raise ValueError("no credible security-code column")
    return best


def _standardise(df: pd.DataFrame, expected_min_rows: int) -> pd.DataFrame:
    if df.empty:
        raise ValueError("official list is empty")
    code_column = _find_code_column(df)
    output = df.copy()
    output["security_code"] = output[code_column].map(_normalise_code)
    output = output[output.security_code.notna()].drop_duplicates("security_code")
    if len(output) < expected_min_rows:
        raise ValueError(f"implausibly small official list: {len(output)} rows")
    return output


def parse_sse_excel(content: bytes, expected_min_rows: int) -> pd.DataFrame:
    if content[:4] not in (b"PK\x03\x04", b"\xd0\xcf\x11\xe0"):
        raise ValueError("SSE payload is not a valid XLS/XLSX signature")
    frames = pd.read_excel(BytesIO(content), sheet_name=None, dtype=str)
    return _standardise(max(frames.values(), key=len), expected_min_rows)


def _set_query(url: str, **updates: object) -> str:
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.update({key: str(value) for key, value in updates.items()})
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, urlencode(query), parsed.fragment))


def fetch_szse_paginated(session: requests.Session, spec: dict) -> tuple[pd.DataFrame, bytes, int, int, str]:
    first = _get(session, _set_query(spec["payload_url"], PAGENO=1), spec["referer"])
    payload = first.json()
    if not isinstance(payload, list) or len(payload) != 1:
        raise ValueError("unexpected SZSE top-level payload")
    section = payload[0]
    metadata = section.get("metadata") or {}
    if metadata.get("catalogid") != spec.get("catalog_id"):
        raise ValueError("SZSE catalog identity mismatch")
    if metadata.get("name") != spec.get("expected_metadata_name"):
        raise ValueError("SZSE report name mismatch")
    page_count = int(metadata["pagecount"])
    record_count = int(metadata["recordcount"])
    list_date = str(metadata.get("subname") or spec.get("as_of_date") or "")
    rows: list[dict] = []
    raw_pages: list[bytes] = []
    for page_no in range(1, page_count + 1):
        response = first if page_no == 1 else _get(session, _set_query(spec["payload_url"], PAGENO=page_no), spec["referer"])
        raw_pages.append(response.content)
        data = response.json()[0]
        page_metadata = data.get("metadata") or {}
        if int(page_metadata.get("pageno", page_no)) != page_no or int(page_metadata.get("recordcount", record_count)) != record_count:
            raise ValueError(f"SZSE pagination metadata mismatch at page {page_no}")
        rows.extend(data.get("data") or [])
    frame = _standardise(pd.DataFrame(rows), int(spec.get("expected_min_rows", 100)))
    if len(frame) != record_count:
        raise ValueError(f"SZSE count mismatch: deduplicated={len(frame)} declared={record_count}")
    return frame, b"\n".join(raw_pages), record_count, page_count, list_date


def fetch_one(
    session: requests.Session,
    spec: dict,
    raw_dir: Path,
    sse_raw_file: Path | None = None,
) -> tuple[pd.DataFrame | None, SourceEvidence]:
    authority = spec["authority"]
    url = spec["payload_url"]
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    if not _official(url, authority):
        raise ValueError(f"non-official host for {authority}: {url}")
    acquisition_mode = "DIRECT_OFFICIAL_FETCH"
    try:
        parser = spec["parser"]
        if parser == "SSE_EXCEL":
            if sse_raw_file is not None:
                raw = sse_raw_file.read_bytes()
                status = 200
                content_type = "application/vnd.ms-excel"
                acquisition_mode = "BROWSER_SESSION_OFFICIAL_FETCH"
            else:
                response = _get(session, url, spec["referer"])
                raw = response.content
                status = response.status_code
                content_type = response.headers.get("content-type", "")
            frame = parse_sse_excel(raw, int(spec.get("expected_min_rows", 100)))
            declared, pages, list_date = len(frame), 1, spec.get("as_of_date")
        elif parser == "SZSE_PAGINATED_JSON":
            frame, raw, declared, pages, list_date = fetch_szse_paginated(session, spec)
            status, content_type = 200, "application/json"
        else:
            raise ValueError(f"unsupported parser: {parser}")
        digest = hashlib.sha256(raw).hexdigest()
        raw_dir.mkdir(parents=True, exist_ok=True)
        (raw_dir / f"{spec['source_id']}_{digest[:12]}.bin").write_bytes(raw)
        evidence = SourceEvidence(
            spec["source_id"], authority, spec["channel"], spec["eligibility_side"],
            spec["landing_url"], url, now, status, content_type, digest, len(raw),
            len(frame), list_date, parser, "PASS", None, declared, pages, acquisition_mode,
        )
        return frame, evidence
    except Exception as exc:
        evidence = SourceEvidence(
            spec["source_id"], authority, spec["channel"], spec["eligibility_side"],
            spec["landing_url"], url, now, 0, "", "", 0, 0,
            spec.get("as_of_date"), spec.get("parser", "UNKNOWN"), "BLOCKED",
            f"{type(exc).__name__}: {exc}", None, None, acquisition_mode,
        )
        return None, evidence


def run(registry: Path, output_dir: Path, allow_partial: bool = False, sse_raw_file: Path | None = None) -> int:
    config = json.loads(registry.read_text(encoding="utf-8"))
    specs = config.get("machine_readable_sources", [])
    if not specs:
        raise ValueError("registry has no machine_readable_sources")
    session = requests.Session()
    evidence: list[SourceEvidence] = []
    frames: list[pd.DataFrame] = []
    for spec in specs:
        override = sse_raw_file if spec.get("authority") == "SSE" else None
        frame, source_evidence = fetch_one(session, spec, output_dir / "raw", override)
        evidence.append(source_evidence)
        if frame is not None:
            output = frame.copy()
            output["authority"] = source_evidence.authority
            output["channel"] = source_evidence.channel
            output["eligibility_side"] = source_evidence.eligibility_side
            output["source_id"] = source_evidence.source_id
            output["source_sha256"] = source_evidence.sha256
            output["source_as_of_date"] = source_evidence.as_of_date
            output["acquisition_mode"] = source_evidence.acquisition_mode
            frames.append(output)
    output_dir.mkdir(parents=True, exist_ok=True)
    ledger = pd.DataFrame([asdict(item) for item in evidence])
    ledger.to_csv(output_dir / "HKCU1_SOURCE_LEDGER.csv", index=False)
    (output_dir / "HKCU1_SOURCE_LEDGER.json").write_text(
        json.dumps([asdict(item) for item in evidence], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    blocked = [item for item in evidence if item.status != "PASS"]
    decision = {
        "status": "PASS" if not blocked else "BLOCKED",
        "blocked_sources": [item.source_id for item in blocked],
        "source_rows": {item.source_id: item.row_count for item in evidence},
        "acquisition_modes": {item.source_id: item.acquisition_mode for item in evidence},
        "trade_authority": "NONE",
    }
    (output_dir / "HKCU1_FETCH_DECISION.json").write_text(
        json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if frames:
        pd.concat(frames, ignore_index=True).to_csv(output_dir / "HKCU1_OFFICIAL_LIST_ROWS.csv", index=False)
    return 0 if not blocked or allow_partial else 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--allow-partial", action="store_true")
    parser.add_argument("--sse-raw-file", type=Path)
    args = parser.parse_args()
    return run(args.registry, args.output_dir, args.allow_partial, args.sse_raw_file)


if __name__ == "__main__":
    raise SystemExit(main())
