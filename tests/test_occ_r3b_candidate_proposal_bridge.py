from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_occ_r3b_dynamic_candidate_restores_exact_accepted_screening():
    text=(ROOT/".github/workflows/wp3_r_dynamic_candidate_loop.yml").read_text(encoding="utf-8")
    assert "operating_current/domains/A_SHARE_FULL_MARKET.json" in text
    assert "SCREENING_DOMAIN_RUNTIME" in text
    assert "source_branch" in text
    assert "source_commit_sha" in text
    assert "refs/remotes/origin/candidate-dynamic-screening" in text
    assert "outputs/screens/current/SCREENING_MANIFEST.json" in text
    assert "outputs/screens/current/SCREENING_LONGLIST.csv" in text
    assert 'domain.get("qc_status")=="PASS_CHAIN_COHERENT"' in text
    assert 'manifest.get("as_of_date")==domain.get("data_watermark")' in text


def test_occ_r3b_preserves_governed_proposal_only_boundary():
    text=(ROOT/".github/workflows/wp3_r_dynamic_candidate_loop.yml").read_text(encoding="utf-8")
    assert "canonical_authority" in text
    assert "MERGE_OF_GOVERNED_PR_ONLY" in text
    assert "proposal_branch_candidate_membership_mutations: 0" in text
    assert "Core / Shadow / Ready proposed mutations: 0 / 0 / 0" in text
    assert "direct_main_push: disabled" in text
    assert "trade_authority: NONE" in text
    assert 'git push origin "HEAD:$RESULT_BRANCH"' in text
    assert "git push origin HEAD:main" not in text
