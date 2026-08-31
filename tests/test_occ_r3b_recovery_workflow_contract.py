from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class OccR3BRecoveryWorkflowContractTests(unittest.TestCase):
    def test_one_shot_uses_exact_accepted_screening_and_retained_engine(self):
        text = (
            ROOT / ".github/workflows/occ-r3b-candidate-proposal-recovery.yml"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "operating_current/domains/A_SHARE_FULL_MARKET.json",
            text,
        )
        self.assertIn("PASS_CHAIN_COHERENT", text)
        self.assertIn("SCREENING_COMMIT", text)
        self.assertIn("SCREENING_WATERMARK", text)
        self.assertIn("2026-08-28", text)
        self.assertIn("build_candidate_dynamic_loop.py --force-weekly", text)
        self.assertIn("ROUND2_CANDIDATE_DELTA_20260828", text)
        self.assertIn("validate_candidate_dynamic_pr.py", text)

    def test_one_shot_is_proposal_only_and_fail_closed(self):
        text = (
            ROOT / ".github/workflows/occ-r3b-candidate-proposal-recovery.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("cp /tmp/CANDIDATE_BASE.json", text)
        self.assertIn("canonical_candidate_mutations", text)
        self.assertIn("core_shadow_ready_automatic_mutations", text)
        self.assertIn("OCC_R3B_RECOVERY_RECEIPT.json", text)
        self.assertIn("automation/occ-r3b-candidate-proposal-", text)
        self.assertNotIn("git push origin HEAD:main", text)
        self.assertIn("trade_authority':'NONE'", text)
        self.assertIn('trade_authority: NONE', text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
