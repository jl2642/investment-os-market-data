from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_occ_r3a_funnel_restores_exact_accepted_screening_current():
    text = (
        ROOT / ".github/workflows/p4-2-continuous-opportunity-funnel.yml"
    ).read_text(encoding="utf-8")

    assert "operating_current/domains/A_SHARE_FULL_MARKET.json" in text
    assert "SCREENING_DOMAIN_RUNTIME" in text
    assert "source_branch" in text
    assert "source_commit_sha" in text
    assert "data_watermark" in text
    assert "refs/remotes/origin/p4-2-screening" in text
    assert "outputs/screens/current/SCREENING_MANIFEST.json" in text
    assert "outputs/screens/current/FMDL2C_RUN_REPORT.json" in text
    assert "outputs/screens/current/SCREENING_LONGLIST.csv" in text
    assert 'domain.get("qc_status")=="PASS_CHAIN_COHERENT"' in text
    assert 'manifest.get("as_of_date")==domain.get("data_watermark")' in text


def test_occ_r3a_preserves_funnel_scope_and_zero_mutation():
    text = (
        ROOT / ".github/workflows/p4-2-continuous-opportunity-funnel.yml"
    ).read_text(encoding="utf-8")

    assert "automation/opportunity_funnel/build_funnel.py" in text
    assert "candidate_membership_mutations" in text
    assert "trade_authority" in text
    assert "P42_PROTECTED_STATE_MUTATION" in text
    assert "git push origin HEAD:main" not in text
