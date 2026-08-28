from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = {
    "daily": ROOT / ".github/workflows/fmdl-daily-production.yml",
    "history_factor": ROOT / ".github/workflows/fmdl-2b4-incremental-refresh.yml",
    "screening": ROOT / ".github/workflows/fmdl-2c-screening-funnel.yml",
    "recovery": ROOT / ".github/workflows/fmdl-2b4-full-rebase.yml",
}


def _text(name: str) -> str:
    return WORKFLOWS[name].read_text(encoding="utf-8")


def test_round1_disables_direct_main_publication() -> None:
    for path in WORKFLOWS.values():
        text = path.read_text(encoding="utf-8")
        assert "git push origin HEAD:main" not in text
        assert 'git push origin "HEAD:main"' not in text
        assert "git pull --rebase origin main" not in text


def test_daily_transaction_orders_market_factor_and_screening() -> None:
    text = _text("daily")
    ordered_markers = [
        "python pipeline/run_daily.py",
        "python -m scripts.run_fmdl2b4_operating",
        "python -m scripts.run_screening_funnel_v2",
        "python -m scripts.publish_fmdl2c",
    ]
    positions = [text.index(marker) for marker in ordered_markers]
    assert positions == sorted(positions)
    assert "automation/fmdl-daily-${{ github.run_id }}-a${{ github.run_attempt }}" in text
    assert "direct_main_push: disabled" in text


def test_daily_publication_tolerates_absent_optional_paths() -> None:
    text = _text("daily")
    assert "publication_paths=(" in text
    assert 'if [[ -e "$path" ]]' in text
    assert 'git add -A -- "$path"' in text
    assert "outputs/quarantine" in text


def test_component_workflows_are_not_scheduled_publishers() -> None:
    for name in ("history_factor", "screening"):
        text = _text(name)
        assert "\n  schedule:" not in text
        assert "Scheduled production is owned by fmdl-daily-production.yml." in text
        assert "permissions:\n  contents: read" in text


def test_daily_and_recovery_inherit_operating_current_runtime() -> None:
    daily = _text("daily")
    recovery = _text("recovery")
    marker = "python -m scripts.hydrate_fmdl_runtime_from_operating_current"
    assert marker in daily
    assert marker in recovery
    assert daily.index(marker) < daily.index("python pipeline/run_daily.py")
    assert recovery.index(marker) < recovery.index("Assess multi-session recovery need")


def test_candidate_publishers_use_distinct_rolling_branches() -> None:
    weekly = (ROOT / ".github/workflows/wp3_r_weekly_screen.yml").read_text(encoding="utf-8")
    ledger = (ROOT / ".github/workflows/wp3_r_candidate_price_ledger.yml").read_text(encoding="utf-8")
    assert "automation/wp3-r-candidate-weekly-current" in weekly
    assert "automation/wp3-r-candidate-ledger-current" in ledger
    assert "WP3R_PUBLISH_BRANCH: automation/wp3-r-candidate-weekly-current" in weekly
    assert "WP3R_PUBLISH_BRANCH: automation/wp3-r-candidate-ledger-current" in ledger
