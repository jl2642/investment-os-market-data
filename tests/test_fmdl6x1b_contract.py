import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("validator", ROOT / "scripts" / "validate_fmdl6x1b_contract.py")
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


class TestFMDL6X1B(unittest.TestCase):
    def setUp(self):
        self.data = validator.load()

    def test_canonical_contract_passes(self):
        self.assertEqual(validator.validate(self.data), [])

    def test_broker_or_portfolio_authority_fails(self):
        candidate = copy.deepcopy(self.data)
        candidate["scope"]["real_account_integration_authorized"] = True
        self.assertIn("scope_authority", validator.validate(candidate))

    def test_market_cap_filter_in_master_fails(self):
        candidate = copy.deepcopy(self.data)
        candidate["universe_layers"]["security_master_universe"]["price_market_cap_liquidity_or_profitability_filters_forbidden"] = False
        self.assertIn("master_filters", validator.validate(candidate))

    def test_unknown_default_include_fails(self):
        candidate = copy.deepcopy(self.data)
        candidate["instrument_classification"]["unknown_instrument_policy"] = "DEFAULT_INCLUDE"
        self.assertIn("unknown_policy", validator.validate(candidate))

    def test_special_profile_standard_ranking_fails(self):
        candidate = copy.deepcopy(self.data)
        candidate["instrument_classification"]["special_profile_research_eligible"][0]["standard_industrial_factor_ranking_allowed"] = True
        self.assertIn("special_profile_standard_ranking", validator.validate(candidate))

    def test_research_channel_conflation_fails(self):
        candidate = copy.deepcopy(self.data)
        candidate["orthogonal_status_dimensions"]["research_and_channel_status_must_not_be_conflated"] = False
        self.assertIn("orthogonal_status", validator.validate(candidate))

    def test_live_row_creation_fails(self):
        candidate = copy.deepcopy(self.data)
        candidate["zero_mutation_proof"]["live_security_rows_created"] = 1
        self.assertIn("zero_mutation", validator.validate(candidate))


if __name__ == "__main__":
    unittest.main()
