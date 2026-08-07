from __future__ import annotations

import json

import pandas as pd

from pipeline.hkcu1_r2e_prepare_bootstrap import prepare


def test_fresh_official_rows_take_precedence_over_lkg(tmp_path):
    rows = pd.DataFrame([
        {"security_code": "00005", "channel": "SH", "eligibility_side": "BUY_SELL", "source_id": "SSE", "source_sha256": "a"},
        {"security_code": "00005", "channel": "SZ", "eligibility_side": "BUY_SELL", "source_id": "SZSE", "source_sha256": "b"},
    ])
    rows_path = tmp_path / "rows.csv"
    rows.to_csv(rows_path, index=False)
    decision_path = tmp_path / "decision.json"
    decision_path.write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
    lkg_path = tmp_path / "lkg.json"
    lkg_path.write_text(json.dumps({
        "snapshot_id": "LKG", "validation_date": "2026-08-07",
        "counts": {"SH": 1, "SZ": 1}, "sh_codes": ["00004"], "sz_codes": ["00004"],
        "source_sha256": {"SH": "x", "SZ": "y"},
    }), encoding="utf-8")

    snapshot, decision = prepare(rows_path, decision_path, lkg_path, "2026-08-07", 14)
    assert decision["status"] == "PASS_FRESH_OFFICIAL"
    assert decision["eligibility_source_status"] == "FRESH_OFFICIAL"
    assert set(snapshot["security_code"]) == {"00005"}
    assert set(snapshot["bootstrap_provenance"]) == {"CURRENT_RUN_PRIMARY_OFFICIAL"}


def test_source_block_uses_valid_lkg_only_for_continuity(tmp_path):
    missing_rows = tmp_path / "missing.csv"
    blocked_decision = tmp_path / "decision.json"
    blocked_decision.write_text(json.dumps({"status": "BLOCKED"}), encoding="utf-8")
    lkg_path = tmp_path / "lkg.json"
    lkg_path.write_text(json.dumps({
        "snapshot_id": "LKG", "validation_date": "2026-08-07",
        "counts": {"SH": 2, "SZ": 2},
        "sh_codes": ["00004", "00005"], "sz_codes": ["00004", "00005"],
        "source_sha256": {"SH": "x", "SZ": "y"},
    }), encoding="utf-8")

    snapshot, decision = prepare(missing_rows, blocked_decision, lkg_path, "2026-08-07", 14)
    assert decision["status"] == "DEGRADED_CONTINUITY"
    assert decision["eligibility_source_status"] == "LKG_CONTINUITY"
    assert decision["publication_source_gate"] is False
    assert len(snapshot) == 4
    assert set(snapshot["bootstrap_provenance"]) == {"LAST_KNOWN_GOOD_CONTINUITY_ONLY"}


def test_expired_lkg_fails_closed(tmp_path):
    decision_path = tmp_path / "decision.json"
    decision_path.write_text(json.dumps({"status": "BLOCKED"}), encoding="utf-8")
    lkg_path = tmp_path / "lkg.json"
    lkg_path.write_text(json.dumps({
        "snapshot_id": "OLD", "validation_date": "2026-07-01",
        "counts": {"SH": 1, "SZ": 1}, "sh_codes": ["00005"], "sz_codes": ["00005"],
        "source_sha256": {"SH": "x", "SZ": "y"},
    }), encoding="utf-8")

    snapshot, decision = prepare(tmp_path / "missing.csv", decision_path, lkg_path, "2026-08-07", 14)
    assert snapshot.empty
    assert decision["status"] == "BLOCKED_NO_USABLE_ELIGIBILITY_EVIDENCE"
