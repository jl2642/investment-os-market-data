from __future__ import annotations

import unittest
from pathlib import Path

from fmdl6x3a_research_universe_readiness import (
    deterministic_zip,
    profile_for,
    readiness_tier,
    research_scope,
    validate_contract,
)


class Fmdl6x3aTests(unittest.TestCase):
    def test_common_equity_profile(self):
        self.assertEqual(profile_for("COMMON_EQUITY"), "STANDARD_OPERATING_COMPANY")

    def test_unknown_instrument_requires_review(self):
        self.assertEqual(profile_for("WARRANT"), "NON_STANDARD_REVIEW")

    def test_excluded_status_has_precedence(self):
        self.assertEqual(research_scope("STANDARD_OPERATING_COMPANY", "EXCLUDED"), "EXCLUDED")

    def test_reference_profile_is_reference_only(self):
        self.assertEqual(research_scope("ETF_ETP_REFERENCE", "REFERENCE_ONLY"), "REFERENCE_ONLY")

    def test_standard_profile_remains_in_scope_with_pending_identity(self):
        self.assertEqual(
            research_scope("STANDARD_OPERATING_COMPANY", "RESEARCH_REVIEW_REQUIRED"),
            "STANDARD_RESEARCH_PROFILE",
        )

    def test_full_readiness_tier(self):
        self.assertEqual(
            readiness_tier("STANDARD_RESEARCH_PROFILE", True, True, True),
            "READY_FOR_6X3B_FINANCIAL_NORMALIZATION_AND_MARKET_SANDBOX",
        )

    def test_market_only_does_not_open_financial_normalization(self):
        self.assertEqual(
            readiness_tier("STANDARD_RESEARCH_PROFILE", True, False, False),
            "MARKET_SANDBOX_ONLY_SEC_BACKFILL_PENDING",
        )

    def test_deterministic_zip(self):
        entries = {"b.jsonl": b"2\n", "a.jsonl": b"1\n"}
        self.assertEqual(deterministic_zip(entries), deterministic_zip(entries))

    def test_frozen_repository_contract(self):
        validate_contract(Path("."))


if __name__ == "__main__":
    unittest.main()
