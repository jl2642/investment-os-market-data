from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_a_share_recovery_and_daily_share_one_concurrency_surface() -> None:
    daily = _text(".github/workflows/fmdl-daily-production.yml")
    rebase = _text(".github/workflows/fmdl-2b4-full-rebase.yml")
    group = "group: fmdl-a-share-history-production-${{ github.ref }}"
    assert group in daily
    assert group in rebase
    assert "materialize_fmdl_history_dependencies.py" in daily
    assert "--verify" in daily


def test_d2_is_triggered_by_portfolio_marks_with_schedule_backstop() -> None:
    text = _text(".github/workflows/research-queue-d2-auto-consumer.yml")
    assert 'workflows: ["R2 WP2-R Market Marks Refresh"]' in text
    assert 'cron: "30 15 * * 1-5"' in text
    assert "github.event.workflow_run.conclusion == 'success'" in text


def test_p4_chain_is_success_driven_with_cron_backstops() -> None:
    expected = {
        ".github/workflows/p4-2-continuous-opportunity-funnel.yml": (
            'workflows: ["FMDL Daily A-share Governed Production", "Research Queue D2 Auto Consumer"]',
            'cron: "30 16 * * 1-5"',
        ),
        ".github/workflows/p4-3-unified-recommendation.yml": (
            'workflows: ["P4-2 Continuous Opportunity Funnel"]',
            'cron: "15 17 * * 1-5"',
        ),
        ".github/workflows/p4-4-trigger-shadow.yml": (
            'workflows: ["P4-3 Unified Decision Recommendation"]',
            'cron: "0 18 * * 1-5"',
        ),
        ".github/workflows/p4-5-forward-validation.yml": (
            'workflows: ["P4-4 Trigger Monitor and Autonomous Shadow Book"]',
            'cron: "45 18 * * 1-5"',
        ),
    }
    for path, (upstream, fallback) in expected.items():
        text = _text(path)
        assert upstream in text
        assert fallback in text
        assert "github.event.workflow_run.conclusion == 'success'" in text
        assert "github.event.workflow_run.head_branch == 'main'" in text
