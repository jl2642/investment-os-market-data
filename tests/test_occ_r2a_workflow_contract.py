from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_occ_r2a_workflow_is_event_driven_and_governed() -> None:
    text = (ROOT / ".github/workflows/occ-r2a-financial-valuation-live.yml").read_text(encoding="utf-8")
    assert 'workflows: ["FMDL Daily A-share Governed Production"]' in text
    assert "--domain FINANCIAL_VALUATION_CONTEXT" in text
    assert "PENDING_OCC_R2B" in text
    assert "RESULT_BRANCH: automation/occ-r2a-valuation-" in text
    assert "git push origin HEAD:main" not in text
    assert "TRADE_AUTHORITY: NONE" in text


def test_operating_current_registers_valuation_context_staleness() -> None:
    text = (ROOT / "automation/operating_current/publish_operating_current.py").read_text(encoding="utf-8")
    assert '"FINANCIAL_VALUATION_CONTEXT": 7' in text
