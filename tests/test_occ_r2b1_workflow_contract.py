from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_occ_r2b1_is_one_shot_governed_full_financial_rebuild() -> None:
    text = (ROOT / ".github/workflows/occ-r2b1-financial-baseline-rebuild.yml").read_text(encoding="utf-8")
    assert 'matrix:' in text
    assert '"31"' in text
    assert "run_fmdl3b2_shard_v2" in text
    assert "aggregate_fmdl3b2_matrix_v2" in text
    assert "run_fmdl3b3_comparability" in text
    assert "run_fmdl3b4_statement_current" in text
    assert "run_fmdl3cb_factor_engine" in text
    assert "run_fmdl3cc_hardening" in text
    assert "run_fmdl3cd_financial_score" in text
    assert "--domain FINANCIAL_STATEMENT_CONTEXT" in text
    assert "PENDING_OCC_R2B2" in text
    assert "git push origin HEAD:main" not in text
    assert "TRADE_AUTHORITY: NONE" in text


def test_occ_r2b1_injects_latest_accepted_a_share_current() -> None:
    text = (ROOT / ".github/workflows/occ-r2b1-financial-baseline-rebuild.yml").read_text(encoding="utf-8")
    assert "operating_current/domains/A_SHARE_FULL_MARKET.json" in text
    assert "SOURCE_COMMIT" in text
    assert "DAILY_MARKET_SNAPSHOT.csv" in text
    assert "INVESTMENT_OS_MARKET_DATA_INTERFACE.json" in text


def test_operating_current_registers_financial_statement_context() -> None:
    text = (ROOT / "automation/operating_current/publish_operating_current.py").read_text(encoding="utf-8")
    assert '"FINANCIAL_STATEMENT_CONTEXT": 120' in text


def test_occ_r2b1_injects_source_watermark_as_pit_cutoff() -> None:
    text = (ROOT / ".github/workflows/occ-r2b1-financial-baseline-rebuild.yml").read_text(encoding="utf-8")
    assert "pit_cutoff_as_of_date" in text
    assert "SOURCE_WATERMARK" in text
    assert "--config /tmp/occ-r2b1-fmdl3b2-matrix.json" in text
