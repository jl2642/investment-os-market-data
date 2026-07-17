import json

import pandas as pd

from scripts import aggregate_full_backfill_v2 as policy


def test_quarantined_impossible_ohlc_is_warning_not_promoted_hard_failure(tmp_path, monkeypatch) -> None:
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    monkeypatch.setattr(policy, "CANDIDATE", candidate)

    quality = {
        "hard_failures": ["IMPOSSIBLE_OHLC"],
        "controlled_warnings": ["QUARANTINED_SYMBOLS_PRESENT"],
        "metrics": {"impossible_ohlc_rows": 3},
    }
    release = {"status": "CANDIDATE_REJECTED", "hard_failures": ["IMPOSSIBLE_OHLC"]}
    report = {
        "release_id": "TEST",
        "as_of_date": "2026-07-16",
        "status": "CANDIDATE_REJECTED",
        "hard_failures": ["IMPOSSIBLE_OHLC"],
        "metrics": {
            "attempted_symbols": 2,
            "usable_symbols": 1,
            "usable_ratio": 0.5,
            "quarantined_symbols": 1,
            "history_rows": 251,
            "base_store_size_mib": 0.1,
            "impossible_ohlc_rows": 3,
            "board_results": {"STAR": {"attempted": 2, "usable": 1, "usable_ratio": 0.5}},
        },
    }
    status = pd.DataFrame([
        {"symbol": "688001.SH", "state": "READY", "impossible_ohlc_rows": 0},
        {"symbol": "688002.SH", "state": "QUARANTINED", "impossible_ohlc_rows": 3},
    ])

    (candidate / "HISTORICAL_STORE_QUALITY.json").write_text(json.dumps(quality), encoding="utf-8")
    (candidate / "HISTORICAL_STORE_RELEASE.json").write_text(json.dumps(release), encoding="utf-8")
    (candidate / "FMDL2B2_RUN_REPORT.json").write_text(json.dumps(report), encoding="utf-8")
    status.to_csv(candidate / "HISTORICAL_SYMBOL_STATUS.csv", index=False)

    assert policy.apply_quarantine_aware_policy()
    revised = json.loads((candidate / "HISTORICAL_STORE_QUALITY.json").read_text(encoding="utf-8"))
    assert revised["hard_failures"] == []
    assert revised["metrics"]["impossible_ohlc_rows"] == 0
    assert revised["metrics"]["quarantined_impossible_ohlc_rows"] == 3


def test_promoted_impossible_ohlc_remains_fatal(tmp_path, monkeypatch) -> None:
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    monkeypatch.setattr(policy, "CANDIDATE", candidate)
    (candidate / "HISTORICAL_STORE_QUALITY.json").write_text(json.dumps({"hard_failures": ["IMPOSSIBLE_OHLC"]}), encoding="utf-8")
    (candidate / "HISTORICAL_STORE_RELEASE.json").write_text(json.dumps({}), encoding="utf-8")
    (candidate / "FMDL2B2_RUN_REPORT.json").write_text(json.dumps({}), encoding="utf-8")
    pd.DataFrame([{"symbol": "688001.SH", "state": "READY", "impossible_ohlc_rows": 1}]).to_csv(
        candidate / "HISTORICAL_SYMBOL_STATUS.csv", index=False
    )
    assert not policy.apply_quarantine_aware_policy()
