from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_occ_r5_nightly_schedule_precedes_0800_controller() -> None:
    expected = {
        ".github/workflows/fmdl-daily-production.yml": 'cron: "30 9 * * 1-5"',       # 17:30 CN
        ".github/workflows/wp2_r_market_marks_refresh.yml": 'cron: "45 14 * * 1-5"', # 22:45 CN
        ".github/workflows/s2-investment-pipeline.yml": 'cron: "30 10 * * 1-5"',   # 18:30 CN backstop after Daily
        ".github/workflows/research-queue-d2-auto-consumer.yml": 'cron: "30 15 * * 1-5"', # 23:30 CN recovery cadence
        ".github/workflows/round3-cross-market-limited-production.yml": 'cron: "30 21 * * 1-5"', # 05:30
    }
    for path, marker in expected.items():
        assert marker in text(path), (path, marker)


def test_cross_market_uses_previous_shanghai_date_before_controller() -> None:
    workflow = text(".github/workflows/round3-cross-market-limited-production.yml")
    assert "TZ=Asia/Shanghai date -d 'yesterday' +%F" in workflow
    assert "defaults to previous Asia/Shanghai date" in workflow
    assert "Restore accepted Cross-Market state from Operating Current" in workflow


def test_s2_decision_callback_uses_d2_success_without_rotating_d1() -> None:
    workflow = text(".github/workflows/s2-investment-pipeline.yml")
    assert '"Research Queue D2 Auto Consumer"' in workflow
    assert "workflow_dispatch:" in workflow
    assert "d2_callback" in workflow
    assert "Bind current S2 D1 transaction" in workflow
    assert "source_d1_state_id" in workflow
    assert "Trigger S3 product surface after coherent decision publication" in workflow


def test_legacy_wp3_2a_provider_retry_schedule_is_retired() -> None:
    workflow = text(".github/workflows/wp3_2a_universe_refresh.yml")
    on_block = workflow.split("permissions:", 1)[0]
    assert "workflow_dispatch:" in on_block
    assert "schedule:" not in on_block


def test_r5_preserves_zero_trade_authority() -> None:
    paths = [
        ".github/workflows/s2-investment-pipeline.yml",
        ".github/workflows/research-queue-d2-auto-consumer.yml",
        ".github/workflows/p4-2-continuous-opportunity-funnel.yml",
        ".github/workflows/p4-3-unified-recommendation.yml",
        ".github/workflows/p4-4-trigger-shadow.yml",
        ".github/workflows/p4-5-forward-validation.yml",
        ".github/workflows/round3-cross-market-limited-production.yml",
        ".github/workflows/occ-r4-portfolio-decision-freshness.yml",
    ]
    for path in paths:
        workflow = text(path)
        assert "TRADE_AUTHORITY: NONE" in workflow
        assert "git push origin HEAD:main" not in workflow


def test_obsolete_p4_4_p4_5_schedules_are_retired() -> None:
    for path in (
        ".github/workflows/p4-4-trigger-shadow.yml",
        ".github/workflows/p4-5-forward-validation.yml",
    ):
        workflow = text(path)
        on_block = workflow.split("permissions:", 1)[0]
        assert "workflow_dispatch:" in on_block
        assert "schedule:" not in on_block
        assert "push:" not in on_block
        assert "workflow_run:" not in on_block


def test_d2_automatic_runtime_has_no_redundant_main_push_trigger() -> None:
    workflow = text(".github/workflows/research-queue-d2-auto-consumer.yml")
    on_block = workflow.split("permissions:", 1)[0]
    assert "workflow_dispatch:" in on_block
    assert "schedule:" in on_block
    assert "push:" not in on_block
