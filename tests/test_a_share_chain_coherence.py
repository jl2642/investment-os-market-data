import json
from pathlib import Path

from pipeline.run_daily import _same_date_noop_eligibility
from scripts.a_share_chain_coherence import assess_chain_coherence


def _write(root: Path, path: str, payload: dict) -> None:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload), encoding="utf-8")


def _coherent_fixture(root: Path, date: str = "2026-08-28") -> None:
    _write(root, "outputs/current/CURRENT_RELEASE.json", {"as_of_date": date})
    _write(
        root,
        "outputs/history/current/HISTORY_CURRENT_RELEASE.json",
        {"as_of_date": date, "release_id": "H1"},
    )
    _write(
        root,
        "outputs/factors/current/FACTOR_CURRENT_RELEASE.json",
        {"as_of_date": date, "release_id": "F1", "history_release_id": "H1"},
    )
    _write(
        root,
        "outputs/screens/current/SCREENING_CURRENT_RELEASE.json",
        {"as_of_date": date, "release_id": "S1", "factor_release_id": "F1"},
    )


def test_chain_coherence_passes_only_when_dates_and_lineage_match(tmp_path: Path) -> None:
    _coherent_fixture(tmp_path)
    result = assess_chain_coherence(tmp_path, target_date="2026-08-28")
    assert result["status"] == "PASS_COHERENT"
    assert result["reasons"] == []
    assert result["screening_refresh_required"] is False


def test_stale_screening_forces_downstream_refresh(tmp_path: Path) -> None:
    _coherent_fixture(tmp_path)
    _write(
        tmp_path,
        "outputs/screens/current/SCREENING_CURRENT_RELEASE.json",
        {"as_of_date": "2026-08-07", "release_id": "S0", "factor_release_id": "F0"},
    )
    result = assess_chain_coherence(tmp_path, target_date="2026-08-28")
    assert result["status"] == "DEGRADED_CHAIN_MISMATCH"
    assert result["screening_refresh_required"] is True
    assert any(reason.startswith("SCREENING_AS_OF_MISMATCH") for reason in result["reasons"])
    assert any(reason.startswith("SCREENING_FACTOR_LINEAGE_MISMATCH") for reason in result["reasons"])


def test_factor_history_lineage_mismatch_blocks_coherent_noop(tmp_path: Path) -> None:
    _coherent_fixture(tmp_path)
    _write(
        tmp_path,
        "outputs/factors/current/FACTOR_CURRENT_RELEASE.json",
        {"as_of_date": "2026-08-28", "release_id": "F1", "history_release_id": "OLD_HISTORY"},
    )
    result = assess_chain_coherence(tmp_path, target_date="2026-08-28")
    assert result["status"] == "DEGRADED_CHAIN_MISMATCH"
    assert any(reason.startswith("FACTOR_HISTORY_LINEAGE_MISMATCH") for reason in result["reasons"])


def test_missing_screening_blocks_coherent_noop(tmp_path: Path) -> None:
    _coherent_fixture(tmp_path)
    (tmp_path / "outputs/screens/current/SCREENING_CURRENT_RELEASE.json").unlink()
    result = assess_chain_coherence(tmp_path, target_date="2026-08-28")
    assert result["status"] == "DEGRADED_CHAIN_MISMATCH"
    assert "SCREENING_CURRENT_MISSING" in result["reasons"]


def test_same_date_daily_noop_requires_coherent_downstream_chain(tmp_path: Path) -> None:
    _coherent_fixture(tmp_path)
    allowed, result = _same_date_noop_eligibility(tmp_path, "2026-08-28")
    assert allowed is True
    assert result["status"] == "PASS_COHERENT"

    _write(
        tmp_path,
        "outputs/screens/current/SCREENING_CURRENT_RELEASE.json",
        {"as_of_date": "2026-08-07", "release_id": "S0", "factor_release_id": "F0"},
    )
    allowed, result = _same_date_noop_eligibility(tmp_path, "2026-08-28")
    assert allowed is False
    assert result["status"] == "DEGRADED_CHAIN_MISMATCH"
    assert result["screening_refresh_required"] is True
