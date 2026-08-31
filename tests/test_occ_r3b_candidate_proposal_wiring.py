from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_occ_r3b_candidate_loop_binds_exact_accepted_screening_current():
    text = (
        ROOT / ".github/workflows/wp3_r_dynamic_candidate_loop.yml"
    ).read_text(encoding="utf-8")

    assert "operating_current/domains/A_SHARE_FULL_MARKET.json" in text
    assert "refs/remotes/origin/wp3r-screening" in text
    assert "source_branch" in text
    assert "source_commit_sha" in text
    assert "outputs/screens/current/SCREENING_MANIFEST.json" in text
    assert "outputs/screens/current/SCREENING_LONGLIST.csv" in text
    assert "PASS_CHAIN_COHERENT" in text
    assert "data_watermark" in text


def test_occ_r3b_remains_proposal_only_for_canonical_candidate():
    text = (
        ROOT / ".github/workflows/wp3_r_dynamic_candidate_loop.yml"
    ).read_text(encoding="utf-8")

    assert "cp /tmp/CANDIDATE_BASE.json" in text
    assert "proposal_then_application_pr_required" in text
    assert "MERGE_OF_GOVERNED_PR_ONLY" in text
    assert "proposal_branch_candidate_membership_mutations: 0" in text
    assert "direct_main_push: disabled" in text
    assert "trade_authority: NONE" in text
