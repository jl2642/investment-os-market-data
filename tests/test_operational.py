import json
from pathlib import Path

import pandas as pd

from pipeline.common import file_sha256
from pipeline.event_flags import build_market_event_flags
from pipeline.publish import publish_candidate, validate_control_payload


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _candidate(root: Path, *, hard_failures: list[str] | None = None) -> None:
    candidate = root / "outputs/candidate"
    candidate.mkdir(parents=True, exist_ok=True)
    universe = pd.DataFrame([
        {"as_of_date": "2026-07-16", "symbol": "600000.SH", "name": "浦发银行"}
    ])
    snapshot = pd.DataFrame([
        {
            "as_of_date": "2026-07-16",
            "symbol": "600000.SH",
            "close": 10.0,
            "prev_close": 9.0,
            "pct_change": 11.111,
            "turnover_cny": 1000.0,
            "data_status": "TRADED",
        },
        {
            "as_of_date": "2026-07-16",
            "symbol": "002677.SZ",
            "close": None,
            "prev_close": None,
            "pct_change": None,
            "turnover_cny": 0.0,
            "data_status": "SUSPENDED",
        },
    ])
    universe.to_csv(candidate / "A_SHARE_UNIVERSE.csv", index=False)
    snapshot.to_csv(candidate / "DAILY_MARKET_SNAPSHOT.csv", index=False)
    failures = hard_failures or []
    report = {
        "run_id": "TEST_RUN",
        "as_of_date": "2026-07-16",
        "market_wide_provider": "sina_public",
        "market_wide_source_function": "stock_zh_a_spot",
        "universe": {"hard_failures": failures, "soft_warnings": ["industry_fill_ratio"]},
        "snapshot": {"hard_failures": [], "soft_warnings": []},
    }
    _write_json(candidate / "FMDL_1BC_RUN_REPORT.json", report)
    (candidate / "FMDL_1BC_RUN_REPORT.md").write_text("# Test\n", encoding="utf-8")
    for dataset_id, csv_name, manifest_name in [
        ("a_share_universe", "A_SHARE_UNIVERSE.csv", "A_SHARE_UNIVERSE_MANIFEST.json"),
        ("daily_market_snapshot", "DAILY_MARKET_SNAPSHOT.csv", "DAILY_MARKET_SNAPSHOT_MANIFEST.json"),
    ]:
        csv_path = candidate / csv_name
        _write_json(
            candidate / manifest_name,
            {
                "dataset_id": dataset_id,
                "dataset_version": f"{dataset_id}-TEST_RUN",
                "run_id": "TEST_RUN",
                "as_of_date": "2026-07-16",
                "publication_status": "DEGRADED",
                "file": {
                    "sha256": file_sha256(csv_path),
                    "path": str(csv_path),
                    "size_bytes": csv_path.stat().st_size,
                },
                "row_count": len(pd.read_csv(csv_path)),
                "quality": {"gate_results_path": "candidate"},
                "lineage": {"parent_dataset_version": None, "last_known_good_dataset_version": None},
            },
        )
    _write_json(candidate / "A_SHARE_UNIVERSE_QUALITY.json", {"hard_failures": failures})
    _write_json(candidate / "DAILY_MARKET_SNAPSHOT_QUALITY.json", {"hard_failures": []})


def test_event_flags_are_reviewable_and_non_destructive() -> None:
    snapshot = pd.DataFrame([
        {"as_of_date": "2026-07-16", "symbol": "A", "data_status": "TRADED", "pct_change": 40.0, "turnover_cny": 1.0},
        {"as_of_date": "2026-07-16", "symbol": "B", "data_status": "SUSPENDED", "pct_change": None, "turnover_cny": 0.0},
        {"as_of_date": "2026-07-16", "symbol": "C", "data_status": "TRADED", "pct_change": 1.0, "turnover_cny": 0.0},
    ])
    flags = build_market_event_flags(snapshot)
    assert set(flags["event_type"]) == {
        "EXTREME_RETURN_REVIEW",
        "SUSPENDED_SECURITY",
        "ZERO_TURNOVER_REVIEW",
    }
    assert len(snapshot) == 3


def test_publish_promotes_current_and_writes_lkg(tmp_path: Path) -> None:
    _candidate(tmp_path)
    result = publish_candidate(root=tmp_path, generated_at="2026-07-16T17:30:00+08:00")
    assert result.action == "PROMOTED_CURRENT"
    release = json.loads((tmp_path / "outputs/current/CURRENT_RELEASE.json").read_text(encoding="utf-8"))
    validate_control_payload(release, "current_release.schema.json")
    assert release["run_id"] == "TEST_RUN"
    assert release["status"] == "PUBLISHED_WITH_WARNINGS"
    status = json.loads((tmp_path / "outputs/status/LAST_SUCCESS.json").read_text(encoding="utf-8"))
    validate_control_payload(status, "operating_status.schema.json")
    flags = pd.read_csv(tmp_path / "outputs/current/MARKET_EVENT_FLAGS.csv")
    assert "SUSPENDED_SECURITY" in set(flags["event_type"])


def test_hard_failure_quarantines_and_preserves_current(tmp_path: Path) -> None:
    current = tmp_path / "outputs/current"
    current.mkdir(parents=True)
    marker = current / "KEEP.txt"
    marker.write_text("last-known-good", encoding="utf-8")
    _candidate(tmp_path, hard_failures=["minimum_row_count"])
    result = publish_candidate(root=tmp_path, generated_at="2026-07-16T17:30:00+08:00")
    assert result.action == "QUARANTINED"
    assert marker.read_text(encoding="utf-8") == "last-known-good"
    assert (tmp_path / "outputs/quarantine/TEST_RUN/FAILURE_REPORT.json").exists()
    status = json.loads((tmp_path / "outputs/status/LAST_RUN.json").read_text(encoding="utf-8"))
    validate_control_payload(status, "operating_status.schema.json")
    assert status["status"] == "QUARANTINED"
    assert status["current_preserved"] is True
