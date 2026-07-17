#!/usr/bin/env python3
"""Independently validate the FMDL-2D stability candidate."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "outputs/stability/candidate"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(root: Path = ROOT) -> dict[str, Any]:
    base = root / CANDIDATE.relative_to(ROOT)
    acceptance = read_json(base / "FMDL2D_ACCEPTANCE.json")
    manifest = read_json(base / "FMDL2D_MANIFEST.json")
    config = read_json(root / "config/fmdl2d_replay_stability.json")
    failures: list[str] = []
    if manifest.get("status") != "CANDIDATE_ACCEPTED":
        failures.append("MANIFEST_NOT_ACCEPTED")
    if acceptance.get("hard_failures"):
        failures.append("ACCEPTANCE_HAS_HARD_FAILURES")
    if acceptance.get("same_date_semantic_replay", {}).get("status") != "PASS":
        failures.append("SAME_DATE_REPLAY_NOT_PASS")
    if acceptance.get("trade_authority") != "NONE":
        failures.append("TRADE_AUTHORITY_NOT_NONE")
    if acceptance.get("authority") != "RESEARCH_PRIORITY_ONLY_NO_TRADE_AUTHORITY":
        failures.append("AUTHORITY_BOUNDARY_MISMATCH")
    artifact_map = {item["dataset_id"]: item for item in manifest.get("artifacts", [])}
    required = {
        "acceptance",
        "daily_replay_summary",
        "rank_transitions",
        "sleeve_transitions",
        "rank_migrations",
        "false_positive_risk_review",
        "replay_longlists",
    }
    if set(artifact_map) != required:
        failures.append("ARTIFACT_SET_MISMATCH")
    for dataset_id, item in artifact_map.items():
        path = root / item["path"]
        if not path.exists():
            failures.append(f"MISSING_{dataset_id}")
            continue
        if sha256_file(path) != item.get("sha256"):
            failures.append(f"HASH_MISMATCH_{dataset_id}")

    daily = pd.read_csv(base / "DAILY_REPLAY_SUMMARY.csv")
    transitions = pd.read_csv(base / "RANK_TRANSITIONS.csv")
    sleeve = pd.read_csv(base / "SLEEVE_TRANSITIONS.csv")
    fragility = pd.read_csv(base / "FALSE_POSITIVE_RISK_REVIEW.csv")
    replay = pd.read_csv(base / "REPLAY_LONGLISTS.csv", dtype={"symbol": str})
    expected_sessions = int(config["replay"]["sessions"])
    if len(daily) != expected_sessions:
        failures.append("REPLAY_SESSION_COUNT_MISMATCH")
    if daily["as_of_date"].astype(str).duplicated().any():
        failures.append("DUPLICATE_REPLAY_DATE")
    if len(transitions) != max(0, expected_sessions - 1):
        failures.append("TRANSITION_COUNT_MISMATCH")
    if replay.duplicated(["replay_date", "symbol"]).any():
        failures.append("DUPLICATE_REPLAY_DATE_SYMBOL")
    if int(daily["longlist_rows"].min()) < int(
        config["hard_gates"]["minimum_longlist_rows_per_session"]
    ):
        failures.append("REPLAY_LONGLIST_BELOW_HARD_FLOOR")
    expected_sleeve_rows = max(0, expected_sessions - 1) * 4
    if len(sleeve) != expected_sleeve_rows:
        failures.append("SLEEVE_TRANSITION_ROW_COUNT_MISMATCH")
    if fragility["symbol"].astype(str).duplicated().any():
        failures.append("DUPLICATE_CURRENT_FRAGILITY_SYMBOL")
    if set(replay["authority"].astype(str)) != {
        "RESEARCH_PRIORITY_ONLY_NO_TRADE_AUTHORITY"
    }:
        failures.append("REPLAY_AUTHORITY_MISMATCH")
    if replay["name"].isna().any() or replay["name"].astype(str).str.strip().eq("").any():
        failures.append("REPLAY_SECURITY_NAME_MISSING")

    payload = {
        "validation_version": "1.0.0",
        "status": "PASS" if not failures else "FAIL",
        "as_of_date": acceptance.get("as_of_date"),
        "hard_failures": failures,
        "metrics": {
            "replay_sessions": len(daily),
            "transition_rows": len(transitions),
            "sleeve_transition_rows": len(sleeve),
            "replay_longlist_rows": len(replay),
            "current_fragility_rows": len(fragility),
        },
        "authority": "RESEARCH_PRIORITY_ONLY_NO_TRADE_AUTHORITY",
        "trade_authority": "NONE",
    }
    (base / "FMDL2D_VALIDATION.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if failures:
        raise RuntimeError(";".join(failures))
    print(json.dumps(payload, ensure_ascii=False))
    return payload


if __name__ == "__main__":
    validate()
