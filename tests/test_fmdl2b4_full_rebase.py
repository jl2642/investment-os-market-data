import json
from pathlib import Path

import pandas as pd
import pytest

import scripts.build_fmdl2b4_full_rebase_candidate as recovery
import scripts.run_incremental_history_refresh as incremental
from scripts.build_fmdl2b4_full_rebase_candidate import validate_recovery_gap


def test_full_rebase_rejects_same_day_and_single_session() -> None:
    with pytest.raises(RuntimeError, match="FULL_REBASE_TARGET_NOT_AFTER_CURRENT"):
        validate_recovery_gap("2026-08-06", "2026-08-06", [])
    with pytest.raises(RuntimeError, match="FULL_REBASE_NOT_REQUIRED_GAP_1"):
        validate_recovery_gap("2026-08-05", "2026-08-06", ["2026-08-06"])


def test_full_rebase_accepts_multi_session_gap() -> None:
    sessions = [
        "2026-07-20", "2026-07-21", "2026-07-22", "2026-07-23", "2026-07-24",
        "2026-07-27", "2026-07-28", "2026-07-29", "2026-07-30", "2026-07-31",
        "2026-08-03", "2026-08-04", "2026-08-05", "2026-08-06",
    ]
    validate_recovery_gap("2026-07-17", "2026-08-06", sessions)


def test_full_rebase_rejects_calendar_not_ending_at_target() -> None:
    with pytest.raises(RuntimeError, match="FULL_REBASE_SESSION_CALENDAR_NOT_AT_TARGET"):
        validate_recovery_gap("2026-07-17", "2026-08-06", ["2026-07-20", "2026-08-05"])


def test_weekend_and_holiday_do_not_create_false_multi_session_gap(monkeypatch: pytest.MonkeyPatch) -> None:
    calendar = pd.DataFrame({
        "trade_date": pd.to_datetime([
            "2026-08-07",  # Friday
            "2026-08-10",  # Monday
            "2026-08-12",  # Wednesday; Tuesday intentionally treated as holiday
        ])
    })
    monkeypatch.setattr(incremental.ak, "tool_trade_date_hist_sina", lambda: calendar)

    weekend_sessions = incremental.completed_sessions_between("2026-08-07", "2026-08-10")
    assert weekend_sessions == ["2026-08-10"]
    with pytest.raises(RuntimeError, match="FULL_REBASE_NOT_REQUIRED_GAP_1"):
        validate_recovery_gap("2026-08-07", "2026-08-10", weekend_sessions)

    holiday_sessions = incremental.completed_sessions_between("2026-08-10", "2026-08-12")
    assert holiday_sessions == ["2026-08-12"]
    with pytest.raises(RuntimeError, match="FULL_REBASE_NOT_REQUIRED_GAP_1"):
        validate_recovery_gap("2026-08-10", "2026-08-12", holiday_sessions)


def _write_minimal_inputs(root: Path, *, logical_shards: int = 2) -> tuple[bytes, bytes]:
    (root / "config").mkdir(parents=True, exist_ok=True)
    (root / "outputs/current").mkdir(parents=True, exist_ok=True)
    (root / "outputs/history/current").mkdir(parents=True, exist_ok=True)
    (root / "outputs/factors/current").mkdir(parents=True, exist_ok=True)

    (root / "config/fmdl2_incremental_refresh.json").write_text(
        json.dumps({
            "composite_store": {"repair_path": "datasets/history/repair"},
            "daily_fast_path": {"minimum_market_append_ratio": 0.97},
        }),
        encoding="utf-8",
    )
    (root / "config/fmdl2_full_backfill_plan.json").write_text(
        json.dumps({
            "sharding": {"logical_shards": logical_shards},
            "quality_gates": {"minimum_board_usable_ratio": 0.90},
        }),
        encoding="utf-8",
    )
    pd.DataFrame([{
        "symbol": "600000.SH",
        "board": "SH_MAIN",
        "list_date": "1999-11-10",
        "is_st": False,
        "is_suspended": False,
    }]).to_csv(root / "outputs/current/A_SHARE_UNIVERSE.csv", index=False)
    pd.DataFrame([{
        "symbol": "600000.SH",
        "as_of_date": "2026-08-06",
        "data_status": "TRADED",
    }]).to_csv(root / "outputs/current/DAILY_MARKET_SNAPSHOT.csv", index=False)
    pd.DataFrame([{"symbol": "600000.SH"}]).to_csv(
        root / "outputs/history/current/HISTORY_CURRENT_STATUS.csv", index=False
    )

    history_marker = b"history-last-known-good\n"
    factor_marker = b"factor-last-known-good\n"
    (root / "outputs/history/current/LKG_MARKER.bin").write_bytes(history_marker)
    (root / "outputs/factors/current/LKG_MARKER.bin").write_bytes(factor_marker)
    return history_marker, factor_marker


def _patch_recovery_context(monkeypatch: pytest.MonkeyPatch, *, logical_shards: int) -> None:
    prior = {
        "release_id": "LKG_HISTORY",
        "as_of_date": "2026-07-17",
        "logical_shards": logical_shards,
    }
    current = {"as_of_date": "2026-08-06", "hard_failures": []}
    sessions = [
        "2026-07-20", "2026-07-21", "2026-07-22", "2026-07-23", "2026-07-24",
        "2026-07-27", "2026-07-28", "2026-07-29", "2026-07-30", "2026-07-31",
        "2026-08-03", "2026-08-04", "2026-08-05", "2026-08-06",
    ]
    monkeypatch.setattr(
        recovery,
        "recovery_context",
        lambda root=recovery.ROOT: (current, prior, "2026-08-06", "2026-07-17", sessions),
    )


def _assert_lkg_unchanged(root: Path, history_marker: bytes, factor_marker: bytes) -> None:
    assert (root / "outputs/history/current/LKG_MARKER.bin").read_bytes() == history_marker
    assert (root / "outputs/factors/current/LKG_MARKER.bin").read_bytes() == factor_marker


def test_missing_recovery_shards_fail_before_current_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    history_marker, factor_marker = _write_minimal_inputs(tmp_path, logical_shards=2)
    _patch_recovery_context(monkeypatch, logical_shards=2)
    incoming = tmp_path / "incoming"
    incoming.mkdir()

    with pytest.raises(RuntimeError, match="RECOVERY_SHARD_MANIFEST_COUNT_0_EXPECTED_2"):
        recovery.build_candidate(incoming, "R2_MISSING_SHARDS", root=tmp_path)

    _assert_lkg_unchanged(tmp_path, history_marker, factor_marker)
    assert not (tmp_path / "outputs/history/refresh_candidate").exists()


def test_corrupted_recovery_shard_hash_fails_before_current_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    history_marker, factor_marker = _write_minimal_inputs(tmp_path, logical_shards=1)
    _patch_recovery_context(monkeypatch, logical_shards=1)
    incoming = tmp_path / "incoming/shard_00"
    incoming.mkdir(parents=True)

    history_path = incoming / "shard_00.parquet"
    history_path.write_bytes(b"intentionally-not-a-valid-parquet")
    status_path = incoming / "shard_00_status.csv"
    pd.DataFrame([{
        "symbol": "600000.SH",
        "board": "SH_MAIN",
        "state": "READY",
        "latest_valid_date": "2026-08-06",
    }]).to_csv(status_path, index=False)
    manifest = {
        "release_id": "R2_BAD_HASH",
        "shard_id": 0,
        "total_shards": 1,
        "as_of_date": "2026-08-06",
        "history_file": history_path.name,
        "history_sha256": "0" * 64,
        "status_file": status_path.name,
        "status_sha256": recovery.sha256_file(status_path),
    }
    (incoming / "shard_00_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )

    with pytest.raises(RuntimeError, match="RECOVERY_HISTORY_HASH_MISMATCH_0"):
        recovery.build_candidate(tmp_path / "incoming", "R2_BAD_HASH", root=tmp_path)

    _assert_lkg_unchanged(tmp_path, history_marker, factor_marker)
    assert not (tmp_path / "outputs/history/refresh_candidate").exists()


def test_recovery_workflow_is_manual_only_governed_and_never_direct_pushes_main() -> None:
    workflow = Path(".github/workflows/fmdl-2b4-full-rebase.yml").read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "schedule:" not in workflow
    assert workflow.count("if: github.event_name == 'workflow_dispatch'") >= 3
    assert "TRADE_AUTHORITY: NONE" in workflow
    assert "automation/fmdl2b4-rebase-" in workflow
    assert "git push origin main" not in workflow
    assert 'git push origin "HEAD:$RESULT_BRANCH"' in workflow
    assert "Protected main is never pushed directly." in workflow
    assert "Candidate, simulation, real holdings and orders are outside this workflow." in workflow
