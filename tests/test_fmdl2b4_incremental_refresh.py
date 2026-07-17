import json
from pathlib import Path

import pandas as pd
import pytest

from scripts.fmdl2b4_history import canonical_hash, load_composite_shard, sha256_file
from scripts.finalize_b4_history_candidate import rehash_frame
from scripts.publish_fmdl2b4 import publish
from scripts.run_b4_factor_refresh import _normalize_composite_lineage
from scripts.run_incremental_history_refresh import canonical_incremental_row, continuity_passes


def engine_config() -> dict:
    return {
        "daily_fast_path": {
            "continuity_relative_tolerance": 0.003,
            "continuity_absolute_cny_tolerance": 0.02,
            "snapshot_adjustment_mode": "qfq_current_session_equivalent",
            "snapshot_record_quality": "VALIDATED_INCREMENTAL",
        }
    }


def history_row(symbol: str, trade_date: str, close: float, provider: str = "sina_daily", adjustment: str = "qfq") -> dict:
    row = {
        "trade_date": trade_date,
        "symbol": symbol,
        "open": close,
        "high": close,
        "low": close,
        "close": close,
        "volume_shares": 100.0,
        "turnover_cny": 1000.0,
        "provider_id": provider,
        "source_function": "test",
        "adjustment_mode": adjustment,
        "retrieved_at": "2026-07-17T18:00:00+08:00",
        "record_quality": "VALID",
    }
    row["row_hash"] = canonical_hash(row)
    return row


def test_continuity_accepts_normal_session_and_rejects_corporate_action_break() -> None:
    config = engine_config()
    normal = pd.Series({"close": 10.10, "pct_change": 1.0, "prev_close": 10.0})
    passed, expected, difference = continuity_passes(normal, 10.0, config)
    assert passed is True
    assert expected == pytest.approx(10.0)
    assert difference == pytest.approx(0.0)

    break_row = pd.Series({"close": 8.08, "pct_change": 1.0, "prev_close": 10.0})
    passed, expected, difference = continuity_passes(break_row, 10.0, config)
    assert passed is False
    assert expected == pytest.approx(8.0)
    assert difference == pytest.approx(2.0)


def test_incremental_row_has_explicit_qfq_equivalent_lineage_and_reproducible_hash() -> None:
    snapshot = pd.Series({
        "as_of_date": "2026-07-17",
        "symbol": "600000.SH",
        "open": 10.0,
        "high": 10.2,
        "low": 9.9,
        "close": 10.1,
        "volume_shares": 1000.0,
        "turnover_cny": 10100.0,
    })
    row = canonical_incremental_row(snapshot, "2026-07-17T18:00:00+08:00", engine_config())
    assert row["provider_id"] == "sina_public_snapshot"
    assert row["adjustment_mode"] == "qfq_current_session_equivalent"
    assert row["record_quality"] == "VALIDATED_INCREMENTAL"
    payload = {key: value for key, value in row.items() if key != "row_hash"}
    assert row["row_hash"] == canonical_hash(payload)


def test_composite_precedence_is_repair_then_delta_then_base(tmp_path: Path) -> None:
    base = pd.DataFrame([
        history_row("600000.SH", "2026-07-15", 10.0),
        history_row("600000.SH", "2026-07-16", 10.1),
    ])
    delta = pd.DataFrame([
        history_row("600000.SH", "2026-07-17", 10.2, "sina_public_snapshot", "qfq_current_session_equivalent")
    ])
    repair = pd.DataFrame([
        history_row("600000.SH", "2026-07-15", 9.0),
        history_row("600000.SH", "2026-07-16", 9.1),
        history_row("600000.SH", "2026-07-17", 9.2),
    ])
    base_path = tmp_path / "base.parquet"
    delta_path = tmp_path / "delta.parquet"
    repair_path = tmp_path / "repair.parquet"
    base.to_parquet(base_path, index=False)
    delta.to_parquet(delta_path, index=False)
    repair.to_parquet(repair_path, index=False)
    base_manifest_path = tmp_path / "base_manifest.json"
    base_manifest = {
        "release_id": "BASE",
        "shard_count": 1,
        "shards": [{"shard_id": 0, "path": str(base_path), "sha256": sha256_file(base_path), "rows": len(base)}],
    }
    base_manifest_path.write_text(json.dumps(base_manifest), encoding="utf-8")
    manifest = {
        "release_id": "CURRENT",
        "as_of_date": "2026-07-17",
        "base_release_id": "BASE",
        "base_manifest_path": str(base_manifest_path),
        "base_manifest_sha256": sha256_file(base_manifest_path),
        "logical_shards": 1,
        "delta_files": [{"path": str(delta_path), "sha256": sha256_file(delta_path)}],
        "repair_files": [{"path": str(repair_path), "sha256": sha256_file(repair_path)}],
    }
    composite = load_composite_shard(manifest, 0, root=tmp_path)
    assert len(composite) == 3
    assert composite["close"].tolist() == [9.0, 9.1, 9.2]
    assert composite.duplicated(["symbol", "trade_date"]).sum() == 0


def test_rehash_frame_reconciles_modified_repair_lineage() -> None:
    frame = pd.DataFrame([history_row("600000.SH", "2026-07-17", 10.0)])
    frame.loc[0, "record_quality"] = "FULL_REPAIR_VALID"
    assert frame.loc[0, "row_hash"] != canonical_hash(frame.loc[0].drop(labels=["row_hash"]).to_dict())
    repaired = rehash_frame(frame)
    assert repaired.loc[0, "row_hash"] == canonical_hash(repaired.loc[0].drop(labels=["row_hash"]).to_dict())


def test_validated_snapshot_delta_is_explicit_composite_not_silent_mix() -> None:
    frame = pd.DataFrame([
        history_row("600000.SH", "2026-07-16", 10.0),
        {
            **history_row("600000.SH", "2026-07-17", 10.1, "sina_public_snapshot", "qfq_current_session_equivalent"),
            "record_quality": "VALIDATED_INCREMENTAL",
        },
    ])
    normalized, state = _normalize_composite_lineage(frame)
    assert state == "COMPOSITE_VALIDATED"
    assert set(normalized["provider_id"]) == {"COMPOSITE_VALIDATED"}
    assert set(normalized["adjustment_mode"]) == {"qfq"}


def test_failed_candidate_validation_preserves_existing_lkg(tmp_path: Path) -> None:
    paths = [
        tmp_path / "outputs/history/refresh_candidate",
        tmp_path / "outputs/factors/refresh_candidate",
        tmp_path / "outputs/history/current",
        tmp_path / "outputs/factors/current",
        tmp_path / "diagnostics",
    ]
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "outputs/history/current/marker.txt").write_text("history-lkg", encoding="utf-8")
    (tmp_path / "outputs/factors/current/marker.txt").write_text("factor-lkg", encoding="utf-8")
    (tmp_path / "outputs/history/refresh_candidate/HISTORY_REFRESH_QUALITY.json").write_text(
        json.dumps({"hard_failures": ["SYNTHETIC_FAILURE"]}), encoding="utf-8"
    )
    (tmp_path / "outputs/factors/refresh_candidate/BASIC_FACTOR_QUALITY.json").write_text(
        json.dumps({"hard_failures": []}), encoding="utf-8"
    )
    (tmp_path / "outputs/history/refresh_candidate/HISTORY_CURRENT_MANIFEST.json").write_text(
        json.dumps({"status": "CANDIDATE_FAIL", "as_of_date": "2026-07-17"}), encoding="utf-8"
    )
    (tmp_path / "outputs/factors/refresh_candidate/BASIC_FACTOR_MANIFEST.json").write_text(
        json.dumps({"status": "CANDIDATE_GENERATED", "as_of_date": "2026-07-17"}), encoding="utf-8"
    )
    (tmp_path / "diagnostics/FMDL2B4_CANDIDATE_VALIDATION.json").write_text(
        json.dumps({"status": "FAIL"}), encoding="utf-8"
    )
    with pytest.raises(RuntimeError):
        publish(tmp_path)
    assert (tmp_path / "outputs/history/current/marker.txt").read_text(encoding="utf-8") == "history-lkg"
    assert (tmp_path / "outputs/factors/current/marker.txt").read_text(encoding="utf-8") == "factor-lkg"
