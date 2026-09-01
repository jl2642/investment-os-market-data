from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class S2OpportunityScreeningFreshnessTests(unittest.TestCase):
    def test_s2_resolves_latest_exact_coherent_screening_source(self):
        text = (
            ROOT / ".github/workflows/s2-investment-pipeline.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("operating_current/runs/A_SHARE_FULL_MARKET/", text)
        self.assertIn('row.get("qc_status")=="PASS_CHAIN_COHERENT"', text)
        self.assertIn('row.get("source_branch")', text)
        self.assertIn('row.get("source_commit_sha")', text)
        self.assertIn("SCREEN_BRANCH", text)
        self.assertIn("SCREEN_COMMIT", text)
        self.assertIn("refs/remotes/origin/s2-screening", text)
        self.assertIn(
            "outputs/screens/current/SCREENING_LONGLIST.csv",
            text,
        )
        self.assertIn(
            'test "$(git rev-parse refs/remotes/origin/s2-screening)" = "$SCREEN_COMMIT"',
            text,
        )

    def test_s2_replaces_candidate_gated_funnel_with_zero_mutation_pipeline(self):
        workflow = (
            ROOT / ".github/workflows/s2-investment-pipeline.yml"
        ).read_text(encoding="utf-8")
        engine = (
            ROOT / "automation/investment_pipeline/build_pipeline.py"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "automation/investment_pipeline/build_pipeline.py",
            workflow,
        )
        self.assertIn("candidate_membership_required", engine)
        self.assertIn(
            '"candidate_membership_mutations": 0',
            engine,
        )
        self.assertIn('"orders": 0', engine)
        self.assertIn("TRADE_AUTHORITY: NONE", workflow)
        self.assertNotIn("git push origin HEAD:main", workflow)


if __name__ == "__main__":
    unittest.main(verbosity=2)
