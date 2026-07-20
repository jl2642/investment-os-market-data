from __future__ import annotations

import hashlib
import json
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

CORRECTION_TOKENS = ("更正", "修订", "补充")
RESTATEMENT_TOKENS = ("重述", "追溯调整", "会计差错")
REPORT_TOKENS = ("年度报告", "半年度报告", "季度报告", "一季报", "三季报", "财务报告", "年报", "半年报")
VOLATILE_SEMANTIC_COLUMNS = {"detected_at", "generated_at", "published_at", "retrieved_at", "source_retrieved_at"}


def stable_hash(payload: Any) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def symbol_from_code(code: object) -> str | None:
    value = re.sub(r"\D", "", str(code or ""))
    if len(value) != 6:
        return None
    if value.startswith(("4", "8", "92")):
        exchange = "BJ"
    elif value.startswith(("5", "6", "9")):
        exchange = "SH"
    else:
        exchange = "SZ"
    return f"{value}.{exchange}"


def classify_financial_title(title: object) -> str:
    text = str(title or "")
    if any(token in text for token in RESTATEMENT_TOKENS):
        return "FINANCIAL_RESTATEMENT"
    if any(token in text for token in CORRECTION_TOKENS):
        return "FINANCIAL_DISCLOSURE_CORRECTION"
    return "FINANCIAL_DISCLOSURE_NEW"


def is_financial_report_title(title: object) -> bool:
    text = str(title or "")
    has_report_context = any(token in text for token in REPORT_TOKENS) or bool(re.search(r"20\d{2}\s*年", text))
    has_revision_context = any(token in text for token in CORRECTION_TOKENS + RESTATEMENT_TOKENS)
    return has_report_context and (any(token in text for token in REPORT_TOKENS) or has_revision_context)


def period_end_from_title(title: object) -> str | None:
    text = str(title or "")
    year_match = re.search(r"(20\d{2})\s*年", text)
    if not year_match:
        return None
    year = int(year_match.group(1))
    if any(token in text for token in ("第一季度", "一季度", "一季报")):
        return f"{year:04d}-03-31"
    if any(token in text for token in ("半年度", "中期", "半年报")):
        return f"{year:04d}-06-30"
    if any(token in text for token in ("第三季度", "三季度", "三季报")):
        return f"{year:04d}-09-30"
    if any(token in text for token in ("年度", "年报")):
        return f"{year:04d}-12-31"
    return None


def daterange(start: date, end: date) -> Iterable[date]:
    cursor = start
    while cursor <= end:
        yield cursor
        cursor += timedelta(days=1)


def semantic_frame_hash(frame: pd.DataFrame, columns: list[str] | None = None) -> str:
    if frame.empty:
        return stable_hash([])
    work = frame.copy()
    if columns:
        work = work[[column for column in columns if column in work.columns]]
    else:
        work = work[[column for column in work.columns if column not in VOLATILE_SEMANTIC_COLUMNS]]
    work = work.reindex(sorted(work.columns), axis=1)
    sort_columns = [column for column in ("event_id", "symbol", "period_end", "line_item_id", "as_of_date") if column in work.columns]
    if sort_columns:
        work = work.sort_values(sort_columns, kind="mergesort")
    work = work.reset_index(drop=True)
    records = json.loads(work.to_json(orient="records", date_format="iso", double_precision=12))
    return stable_hash(records)


def inventory(root: Path, paths: Iterable[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for value in paths:
        path = root / str(value)
        rows.append({
            "path": str(value),
            "exists": path.exists(),
            "bytes": int(path.stat().st_size) if path.exists() else 0,
            "sha256": sha256_file(path) if path.exists() and path.is_file() else None,
        })
    return rows


def manifest_for_directory(root: Path, release_id: str) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "FMDL3EBC_MANIFEST.json":
            files.append({
                "path": str(path.relative_to(root)),
                "sha256": sha256_file(path),
                "bytes": int(path.stat().st_size),
            })
    return {
        "manifest_version": "1.0.0",
        "release_id": release_id,
        "files": files,
        "authority": "DATA_AND_RESEARCH_EVIDENCE_ONLY",
        "trade_authority": "NONE",
    }


def catalog_paths(catalog: pd.DataFrame, role_contains: str) -> list[str]:
    mask = catalog["dataset_role"].astype(str).str.contains(role_contains, case=False, regex=False)
    return catalog.loc[mask & catalog["exists"].astype(str).str.lower().eq("true"), "path"].astype(str).tolist()


def load_parquet_paths(root: Path, paths: Iterable[str], symbols: set[str] | None = None) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for value in paths:
        path = root / value
        if not path.exists():
            continue
        frame = pd.read_parquet(path)
        if symbols is not None and "symbol" in frame.columns:
            frame = frame[frame["symbol"].astype(str).isin(symbols)]
        if len(frame):
            frames.append(frame)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def first_existing(columns: Iterable[str], candidates: Iterable[str]) -> str | None:
    available = set(columns)
    return next((candidate for candidate in candidates if candidate in available), None)


def normalize_revision_columns(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    work = frame.copy()
    mapping = {
        "title": first_existing(work.columns, ["filing_title", "announcement_title", "title", "公告标题"]),
        "period_end": first_existing(work.columns, ["report_period_end", "period_end"]),
        "available_from": first_existing(work.columns, ["available_from", "effective_from"]),
        "announcement_date": first_existing(work.columns, ["announcement_date", "公告时间"]),
        "revision_sequence": first_existing(work.columns, ["revision_sequence", "sequence"]),
        "revision_id": first_existing(work.columns, ["revision_id"]),
        "filing_link": first_existing(work.columns, ["filing_link", "announcement_link", "公告链接"]),
    }
    for canonical, source in mapping.items():
        if source and source != canonical:
            work[canonical] = work[source]
        elif not source:
            work[canonical] = None
    work["symbol"] = work["symbol"].astype(str)
    work["revision_sequence"] = pd.to_numeric(work["revision_sequence"], errors="coerce").fillna(1).astype(int)
    work["event_type"] = work["title"].map(classify_financial_title)
    return work


def pick_historical_replay_cases(revisions: pd.DataFrame) -> list[dict[str, Any]]:
    work = normalize_revision_columns(revisions)
    if work.empty:
        return []
    work = work[work["period_end"].notna() & work["available_from"].notna()].copy()
    if work.empty:
        return []
    cases: list[dict[str, Any]] = []
    first = work.sort_values(["available_from", "symbol", "period_end", "revision_sequence"]).iloc[0]
    cases.append({
        "symbol": first["symbol"],
        "period_end": str(first["period_end"]),
        "event_type": "FINANCIAL_DISCLOSURE_NEW",
        "title": str(first.get("title") or ""),
        "effective_at": str(first["available_from"]),
        "source_reference": str(first.get("filing_link") or "FMDL3B4_REVISION_LEDGER"),
        "live_detected": False,
        "replay_kind": "REAL_HISTORICAL_FIRST_DISCLOSURE",
    })
    candidates: list[pd.DataFrame] = []
    for _, group in work.groupby(["symbol", "period_end"], dropna=False):
        if int(group["revision_sequence"].max()) >= 2:
            candidates.append(group.sort_values("revision_sequence"))
    if candidates:
        preferred = [g for g in candidates if g["title"].astype(str).map(classify_financial_title).isin(["FINANCIAL_DISCLOSURE_CORRECTION", "FINANCIAL_RESTATEMENT"]).any()]
        group = (preferred or candidates)[0]
        latest = group.iloc[-1]
        event_type = classify_financial_title(latest.get("title"))
        if event_type == "FINANCIAL_DISCLOSURE_NEW":
            event_type = "FINANCIAL_DISCLOSURE_CORRECTION"
        cases.append({
            "symbol": latest["symbol"],
            "period_end": str(latest["period_end"]),
            "event_type": event_type,
            "title": str(latest.get("title") or ""),
            "effective_at": str(latest["available_from"]),
            "source_reference": str(latest.get("filing_link") or "FMDL3B4_REVISION_LEDGER"),
            "live_detected": False,
            "replay_kind": "REAL_HISTORICAL_REVISION_CHAIN",
        })
    return cases
