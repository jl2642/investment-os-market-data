#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import pandas as pd


def _read_json(path: Path | None) -> dict:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _codes(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    result = []
    for value in values:
        digits = "".join(ch for ch in str(value) if ch.isdigit())
        if digits:
            result.append(digits[-5:].zfill(5))
    return sorted(set(result))


def _fresh_snapshot(rows_path: Path, as_of_date: str) -> pd.DataFrame:
    if not rows_path.exists():
        return pd.DataFrame()
    df = pd.read_csv(rows_path, dtype=str)
    required = {"security_code", "channel", "eligibility_side", "source_id", "source_sha256"}
    if not required.issubset(df.columns):
        return pd.DataFrame()
    out = df[list(required)].copy()
    out["security_code"] = out["security_code"].astype(str).str.zfill(5)
    out = out[out["channel"].isin(["SH", "SZ"])]
    out = out.drop_duplicates(["security_code", "channel"])
    channels = set(out["channel"])
    if channels != {"SH", "SZ"}:
        return pd.DataFrame()
    if out.groupby("channel")["security_code"].nunique().min() <= 0:
        return pd.DataFrame()
    out["effective_from"] = as_of_date
    out["bootstrap_provenance"] = "CURRENT_RUN_PRIMARY_OFFICIAL"
    return out.sort_values(["security_code", "channel"])


def _lkg_snapshot(lkg: dict, as_of_date: str, max_age_days: int) -> pd.DataFrame:
    validation_date = str(lkg.get("validation_date") or "")
    try:
        age = (date.fromisoformat(as_of_date) - date.fromisoformat(validation_date)).days
    except Exception:
        return pd.DataFrame()
    if age < 0 or age > max_age_days:
        return pd.DataFrame()
    sh, sz = _codes(lkg.get("sh_codes")), _codes(lkg.get("sz_codes"))
    if not sh or not sz:
        return pd.DataFrame()
    counts = lkg.get("counts") or {}
    if int(counts.get("SH", -1)) != len(sh) or int(counts.get("SZ", -1)) != len(sz):
        return pd.DataFrame()
    source_sha = lkg.get("source_sha256") or {}
    rows = []
    for channel, codes in (("SH", sh), ("SZ", sz)):
        for code in codes:
            rows.append({
                "security_code": code,
                "channel": channel,
                "eligibility_side": "BUY_SELL",
                "source_id": f"HKCU1_LKG_{channel}_SOUTHBOUND_BUY_LIST",
                "source_sha256": source_sha.get(channel, ""),
                "effective_from": validation_date,
                "bootstrap_provenance": "LAST_KNOWN_GOOD_CONTINUITY_ONLY",
            })
    return pd.DataFrame(rows).sort_values(["security_code", "channel"])


def prepare(
    fresh_rows_path: Path,
    fresh_decision_path: Path,
    lkg_path: Path,
    as_of_date: str,
    max_lkg_age_days: int,
) -> tuple[pd.DataFrame, dict]:
    fresh_decision = _read_json(fresh_decision_path)
    fresh = pd.DataFrame()
    if fresh_decision.get("status") == "PASS":
        fresh = _fresh_snapshot(fresh_rows_path, as_of_date)
    if not fresh.empty:
        decision = {
            "status": "PASS_FRESH_OFFICIAL",
            "eligibility_source_status": "FRESH_OFFICIAL",
            "fresh_official_available": True,
            "publication_source_gate": True,
            "bootstrap_rows": int(len(fresh)),
            "sh_rows": int((fresh["channel"] == "SH").sum()),
            "sz_rows": int((fresh["channel"] == "SZ").sum()),
            "bootstrap_effective_from": as_of_date,
            "canonical_action": "CONTINUE_TO_R2E_FRESHNESS_GATE",
            "trade_authority": "NONE",
        }
        return fresh, decision

    lkg = _read_json(lkg_path)
    continuity = _lkg_snapshot(lkg, as_of_date, max_lkg_age_days)
    if not continuity.empty:
        decision = {
            "status": "DEGRADED_CONTINUITY",
            "eligibility_source_status": "LKG_CONTINUITY",
            "fresh_official_available": False,
            "publication_source_gate": False,
            "bootstrap_rows": int(len(continuity)),
            "sh_rows": int((continuity["channel"] == "SH").sum()),
            "sz_rows": int((continuity["channel"] == "SZ").sum()),
            "lkg_snapshot_id": lkg.get("snapshot_id"),
            "lkg_validation_date": lkg.get("validation_date"),
            "lkg_source_as_of_dates": lkg.get("source_as_of_dates"),
            "canonical_action": "KEEP_PREVIOUS_CANONICAL_UNCHANGED",
            "trade_authority": "NONE",
        }
        return continuity, decision

    decision = {
        "status": "BLOCKED_NO_USABLE_ELIGIBILITY_EVIDENCE",
        "eligibility_source_status": "NONE",
        "fresh_official_available": False,
        "publication_source_gate": False,
        "bootstrap_rows": 0,
        "canonical_action": "KEEP_PREVIOUS_CANONICAL_UNCHANGED",
        "trade_authority": "NONE",
    }
    return pd.DataFrame(), decision


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--fresh-rows", type=Path, required=True)
    p.add_argument("--fresh-decision", type=Path, required=True)
    p.add_argument("--lkg", type=Path, required=True)
    p.add_argument("--as-of-date", required=True)
    p.add_argument("--max-lkg-age-days", type=int, default=14)
    p.add_argument("--output-snapshot", type=Path, required=True)
    p.add_argument("--output-decision", type=Path, required=True)
    a = p.parse_args()
    snapshot, decision = prepare(a.fresh_rows, a.fresh_decision, a.lkg, a.as_of_date, a.max_lkg_age_days)
    a.output_snapshot.parent.mkdir(parents=True, exist_ok=True)
    if not snapshot.empty:
        snapshot.to_csv(a.output_snapshot, index=False)
    a.output_decision.write_text(json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0 if decision["status"] in {"PASS_FRESH_OFFICIAL", "DEGRADED_CONTINUITY"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
