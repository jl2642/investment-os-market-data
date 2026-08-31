from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_round3_production_restores_exact_operating_current_state():
    text=(ROOT/".github/workflows/round3-cross-market-limited-production.yml").read_text(encoding="utf-8")
    assert "Restore accepted Cross-Market state from Operating Current" in text
    assert "operating_current/domains/CROSS_MARKET_LIMITED.json" in text
    assert "source_branch" in text
    assert "source_commit_sha" in text
    assert "CROSS_MARKET_LIMITED_LEDGER_CURRENT.json" in text
    assert "CROSS_MARKET_LIMITED_RUN_CURRENT.json" in text
    assert "CROSS_MARKET_RESEARCH_PROPOSAL_CURRENT.json" in text
    assert "OCC_R4_CROSS_MARKET_STATE_MISSING" in text
    assert "git push origin HEAD:main" not in text
