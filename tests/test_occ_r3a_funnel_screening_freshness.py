from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class OccR3AFunnelScreeningFreshnessTests(unittest.TestCase):
    def test_occ_r3a_funnel_restores_exact_accepted_screening_current(self):
        text = (
            ROOT / ".github/workflows/p4-2-continuous-opportunity-funnel.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("operating_current/domains/A_SHARE_FULL_MARKET.json", text)
        self.assertIn("SCREENING_DOMAIN_RUNTIME", text)
        self.assertIn("source_branch", text)
        self.assertIn("source_commit_sha", text)
        self.assertIn("data_watermark", text)
        self.assertIn("refs/remotes/origin/p4-2-screening", text)
        self.assertIn("outputs/screens/current/SCREENING_MANIFEST.json", text)
        self.assertIn("outputs/screens/current/FMDL2C_RUN_REPORT.json", text)
        self.assertIn("outputs/screens/current/SCREENING_LONGLIST.csv", text)
        self.assertIn('domain.get("qc_status")=="PASS_CHAIN_COHERENT"', text)
        self.assertIn(
            'manifest.get("as_of_date")==domain.get("data_watermark")',
            text,
        )

    def test_occ_r3a_preserves_funnel_scope_and_zero_mutation(self):
        text = (
            ROOT / ".github/workflows/p4-2-continuous-opportunity-funnel.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("automation/opportunity_funnel/build_funnel.py", text)
        self.assertIn("candidate_membership_mutations", text)
        self.assertIn("trade_authority", text)
        self.assertIn("P42_PROTECTED_STATE_MUTATION", text)
        self.assertNotIn("git push origin HEAD:main", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
