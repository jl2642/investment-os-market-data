#!/usr/bin/env python3
"""Classify HKCU-1 source failures and decide whether a run may publish.

The key operating rule is deliberately conservative:
- fresh official evidence may advance a release candidate;
- a last-known-good (LKG) snapshot may preserve continuity and enable diffs;
- an LKG snapshot must never be silently relabelled as fresh/current;
- source/infrastructure failures must be distinguished from code/data-contract failures.
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

FAILURE_CLASSES = {
    "NONE",
    "TRANSIENT_INFRA",
    "SOURCE_BLOCKED",
    "DATA_CONTRACT_CHANGE",
    "CODE_DEFECT",
    "UNKNOWN",
}


def classify_sse_evidence(evidence: dict) -> str:
    if evidence.get("status") == "PASS":
        return "NONE"
    explicit = str(evidence.get("failure_class") or "").upper()
    if explicit in FAILURE_CLASSES - {"NONE"}:
        return explicit

    statuses = []
    for key in ("landing_http_status", "payload_http_status"):
        try:
            statuses.append(int(evidence.get(key) or 0))
        except (TypeError, ValueError):
            pass
    error = str(evidence.get("error") or "").lower()

    if 403 in statuses or 429 in statuses:
        return "SOURCE_BLOCKED"
    if any(status >= 500 for status in statuses) or "timeout" in error or "connection" in error:
        return "TRANSIENT_INFRA"
    if "xls" in error or "xlsx" in error or "signature" in error or "contract" in error:
        return "DATA_CONTRACT_CHANGE"
    return "UNKNOWN"


def lkg_age_days(lkg: dict, as_of_date: str) -> int:
    source_dates = [d for d in (lkg.get("source_as_of_dates") or {}).values() if d]
    if not source_dates:
        raise ValueError("LKG has no source_as_of_dates")
    latest = max(date.fromisoformat(str(d)) for d in source_dates)
    return (date.fromisoformat(as_of_date) - latest).days


def decide(sse_evidence: dict, lkg: dict | None, as_of_date: str, max_continuity_age_days: int = 14) -> dict:
    failure_class = classify_sse_evidence(sse_evidence)
    if sse_evidence.get("status") == "PASS":
        return {
            "status": "FRESH_PASS",
            "failure_class": "NONE",
            "fresh_official_available": True,
            "continuity_available": True,
            "publication_allowed": True,
            "canonical_action": "MAY_BUILD_NEW_RELEASE_CANDIDATE",
            "as_of_date": as_of_date,
            "lkg_age_days": 0,
            "trade_authority": "NONE",
        }

    age = None
    continuity = False
    if lkg:
        try:
            age = lkg_age_days(lkg, as_of_date)
            continuity = 0 <= age <= max_continuity_age_days
        except Exception:
            continuity = False

    return {
        "status": "DEGRADED_CONTINUITY" if continuity else "BLOCKED_NO_FRESH_SOURCE",
        "failure_class": failure_class,
        "fresh_official_available": False,
        "continuity_available": continuity,
        "publication_allowed": False,
        "canonical_action": "KEEP_PREVIOUS_CANONICAL_UNCHANGED",
        "as_of_date": as_of_date,
        "lkg_age_days": age,
        "max_continuity_age_days": max_continuity_age_days,
        "trade_authority": "NONE",
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--sse-evidence", type=Path, required=True)
    p.add_argument("--lkg", type=Path)
    p.add_argument("--as-of-date", required=True)
    p.add_argument("--max-continuity-age-days", type=int, default=14)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()

    evidence = json.loads(a.sse_evidence.read_text(encoding="utf-8"))
    lkg = json.loads(a.lkg.read_text(encoding="utf-8")) if a.lkg and a.lkg.exists() else None
    result = decide(evidence, lkg, a.as_of_date, a.max_continuity_age_days)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
