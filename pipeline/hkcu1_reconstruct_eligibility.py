#!/usr/bin/env python3
"""Reconstruct channel-specific point-in-time Stock Connect eligibility."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

VALID_DIRECTIONS = {"IN", "OUT", "SELL_ONLY", "BUY_SELL", "NOT_ELIGIBLE"}


def _code(v: object) -> str:
    digits = "".join(ch for ch in str(v) if ch.isdigit())
    if not digits:
        raise ValueError(f"invalid security code: {v!r}")
    return digits[-5:].zfill(5)


def canonical_csv_hash(df: pd.DataFrame) -> str:
    data = df.sort_values(list(df.columns)).to_csv(index=False, lineterminator="\n").encode()
    return hashlib.sha256(data).hexdigest()


def reconstruct(snapshot_rows: pd.DataFrame, events: pd.DataFrame, as_of_date: str) -> pd.DataFrame:
    cutoff = pd.Timestamp(as_of_date)
    required_snapshot = {"security_code", "channel", "eligibility_side", "effective_from"}
    required_events = {"security_code", "channel", "direction", "effective_from"}
    if not required_snapshot.issubset(snapshot_rows.columns):
        raise ValueError(f"snapshot missing {sorted(required_snapshot - set(snapshot_rows.columns))}")
    if not events.empty and not required_events.issubset(events.columns):
        raise ValueError(f"events missing {sorted(required_events - set(events.columns))}")

    snap = snapshot_rows.copy()
    snap["security_code"] = snap["security_code"].map(_code)
    snap["effective_from"] = pd.to_datetime(snap["effective_from"], errors="raise")
    snap = snap[snap["effective_from"] <= cutoff]
    if snap.empty:
        raise ValueError("no official snapshot effective on or before as_of_date")

    state: dict[tuple[str, str], dict] = {}
    for _, r in snap.sort_values("effective_from").iterrows():
        key = (r["security_code"], str(r["channel"]).upper())
        side = str(r["eligibility_side"]).upper()
        status = "BUY_ELIGIBLE" if side in {"BUY_SELL", "BUY_ELIGIBLE"} else "SELL_ONLY"
        state[key] = {
            "security_code": key[0], "channel": key[1], "channel_status": status,
            "effective_from": r["effective_from"].date().isoformat(),
            "source_id": r.get("source_id", ""), "source_sha256": r.get("source_sha256", "")
        }

    if not events.empty:
        ev = events.copy()
        ev["security_code"] = ev["security_code"].map(_code)
        ev["effective_from"] = pd.to_datetime(ev["effective_from"], errors="raise")
        ev = ev[ev["effective_from"] <= cutoff].sort_values(["effective_from", "security_code"])
        bad = set(ev["direction"].astype(str).str.upper()) - VALID_DIRECTIONS
        if bad:
            raise ValueError(f"invalid directions: {sorted(bad)}")
        for _, r in ev.iterrows():
            key = (r["security_code"], str(r["channel"]).upper())
            direction = str(r["direction"]).upper()
            if direction in {"IN", "BUY_SELL"}:
                status = "BUY_ELIGIBLE"
            elif direction in {"OUT", "SELL_ONLY"}:
                # Official removal from the buy-eligible Southbound list does not
                # erase the ability of an existing holder to dispose of an SEHK-
                # listed security through Stock Connect. Preserve that state as
                # SELL_ONLY. A terminal NOT_ELIGIBLE event is reserved for cases
                # where official evidence says the security is no longer sellable
                # through the relevant channel (for example, no longer SEHK-listed).
                status = "SELL_ONLY"
            else:
                status = "NOT_ELIGIBLE"
            state[key] = {
                "security_code": key[0], "channel": key[1], "channel_status": status,
                "effective_from": r["effective_from"].date().isoformat(),
                "source_id": r.get("source_id", ""), "source_sha256": r.get("source_sha256", "")
            }

    long = pd.DataFrame(state.values())
    codes = sorted(long["security_code"].unique())
    records = []
    for code in codes:
        sub = long[long.security_code == code].set_index("channel")
        sh = sub.loc["SH", "channel_status"] if "SH" in sub.index else "UNKNOWN_BLOCKED"
        sz = sub.loc["SZ", "channel_status"] if "SZ" in sub.index else "UNKNOWN_BLOCKED"
        buy = sh == "BUY_ELIGIBLE" or sz == "BUY_ELIGIBLE"
        sell_only = not buy and (sh == "SELL_ONLY" or sz == "SELL_ONLY")
        combined = "BUY_ELIGIBLE_BOTH" if sh == sz == "BUY_ELIGIBLE" else (
            "BUY_ELIGIBLE_SH_ONLY" if sh == "BUY_ELIGIBLE" else (
            "BUY_ELIGIBLE_SZ_ONLY" if sz == "BUY_ELIGIBLE" else (
            "SELL_ONLY" if sell_only else (
            "NOT_ELIGIBLE" if sh == sz == "NOT_ELIGIBLE" else "UNKNOWN_BLOCKED"))))
        records.append({"security_code": code, "sh_status": sh, "sz_status": sz,
                        "combined_status": combined, "buy_eligible": buy,
                        "sell_only": sell_only,
                        "as_of_date": cutoff.date().isoformat()})
    return pd.DataFrame(records)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--snapshot", type=Path, required=True)
    p.add_argument("--events", type=Path, required=True)
    p.add_argument("--as-of-date", required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    a = p.parse_args()
    snapshot = pd.read_csv(a.snapshot, dtype=str)
    events = pd.read_csv(a.events, dtype=str) if a.events.exists() else pd.DataFrame()
    result = reconstruct(snapshot, events, a.as_of_date)
    a.output_dir.mkdir(parents=True, exist_ok=True)
    result.to_csv(a.output_dir / "HKCU1_POINT_IN_TIME_ELIGIBILITY.csv", index=False)
    (a.output_dir / "HKCU1_ELIGIBILITY_HASH.json").write_text(json.dumps({
        "as_of_date": a.as_of_date, "rows": len(result),
        "canonical_sha256": canonical_csv_hash(result), "trade_authority": "NONE"
    }, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
