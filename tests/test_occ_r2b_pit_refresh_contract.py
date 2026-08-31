from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_full_universe_matrix_pr_does_not_run_live_shards() -> None:
    text = (ROOT / ".github/workflows/fmdl-3b2-full-universe-matrix.yml").read_text(encoding="utf-8")
    assert "shards:" in text
    assert "if: github.event_name != 'pull_request'" in text
    assert "if: always() && github.event_name != 'pull_request'" in text


def test_r2b_pit_cutoff_is_optional_and_not_global_default() -> None:
    shard = (ROOT / "scripts/run_fmdl3b2_shard.py").read_text(encoding="utf-8")
    canary = (ROOT / "scripts/run_fmdl3b2_canary.py").read_text(encoding="utf-8")
    config = (ROOT / "config/fmdl3b2_matrix.json").read_text(encoding="utf-8")
    assert 'cfg.get("data_scope", {}).get("pit_cutoff_as_of_date")' in shard
    assert "as_of_cutoff: str | None = None" in canary
    assert '"pit_cutoff_as_of_date"' not in config


def test_financial_canary_pr_is_deterministic_only() -> None:
    text = (ROOT / ".github/workflows/fmdl-3b2-full-build-canary.yml").read_text(encoding="utf-8")
    assert "Run real build canary" in text
    assert text.count("if: github.event_name != 'pull_request'") >= 3
    assert "github.event_name != 'pull_request' && always()" in text
