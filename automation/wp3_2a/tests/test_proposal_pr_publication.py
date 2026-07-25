from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "automation/wp3_2a/create_or_update_pr.sh"


def test_proposal_pr_publication_is_unique_and_observable():
    text = SCRIPT.read_text(encoding="utf-8")

    assert 'RUN_KEY="${GITHUB_RUN_ID:-manual}-${GITHUB_RUN_ATTEMPT:-1}"' in text
    assert 'BRANCH="${BRANCH_BASE}-${RUN_KEY}"' in text
    assert "git push --set-upstream origin" in text
    assert "--force" not in text
    assert "CREATE_OR_UPDATE_PR.log" in text
    assert "CREATE_OR_UPDATE_PR_EXIT_CODE.txt" in text
    assert "PROPOSAL_PR_RECEIPT.json" in text
    assert "gh pr create" in text
    assert "trade_authority=NONE" in text


def test_publication_stages_only_wp3_2a_governed_area():
    text = SCRIPT.read_text(encoding="utf-8")

    assert (
        "git add investment_os_runtime/40_EVIDENCE_AND_LINEAGE/WP3_2A"
        in text
    )
    assert "git add .github automation docs investment_os_runtime" not in text
