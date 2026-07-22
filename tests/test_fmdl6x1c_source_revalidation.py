from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, "scripts")
from fmdl6x1c_benchmark import capability_decisions, parse_payload, validate_contract  # noqa: E402


class Fmdl6x1cTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Path(__file__).resolve().parents[1]
        self.contract = json.loads((self.repo / "config/fmdl6x1c_source_cost_execution_route_contract.json").read_text(encoding="utf-8"))

    def test_contract_passes(self) -> None:
        checks, errors = validate_contract(self.repo)
        self.assertGreater(len(checks), 10)
        self.assertEqual(errors, [])

    def test_pipe_parser(self) -> None:
        parsed = parse_payload("PIPE_TEXT", b"Symbol|Name\nAAPL|Apple\nFile Creation Time: 1\n")
        self.assertEqual(parsed["parse_status"], "PASS")
        self.assertEqual(parsed["row_count"], 1)

    def test_zip_parser(self) -> None:
        import io
        import zipfile
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr("nasdaqlisted.txt", "x")
            archive.writestr("otherlisted.txt", "y")
        parsed = parse_payload("ZIP_DIRECTORY", stream.getvalue())
        self.assertEqual(parsed["member_count"], 2)

    def test_capabilities_pass_with_expected_routes(self) -> None:
        observations = []
        for group in self.contract["route_groups"]:
            for route in group["routes"]:
                observations.append({"route_id": route["route_id"], "success": True, "failure_class": None})
        decisions = capability_decisions(self.contract, {"observations": observations})
        self.assertTrue(all(item["status"] == "PASS" for item in decisions))

    def test_market_capability_fails_without_event_route(self) -> None:
        observations = []
        for group in self.contract["route_groups"]:
            for route in group["routes"]:
                success = route["route_id"] != "YAHOO_QUERY1_AAPL_EVENTS" and route["route_id"] != "YAHOO_QUERY2_AAPL_EVENTS"
                observations.append({"route_id": route["route_id"], "success": success, "failure_class": None if success else "HTTP_4XX_AUTH_OR_BLOCK"})
        decisions = {item["capability_id"]: item for item in capability_decisions(self.contract, {"observations": observations})}
        self.assertEqual(decisions["MARKET_HISTORY_AND_CORPORATE_ACTIONS"]["status"], "FAIL")

    def test_sec_controlled_block_is_explicitly_accepted(self) -> None:
        observations = []
        sec_ids = {"SEC_COMPANY_TICKERS_EXCHANGE", "SEC_SUBMISSIONS_AAPL", "SEC_COMPANYFACTS_AAPL"}
        for group in self.contract["route_groups"]:
            for route in group["routes"]:
                blocked = route["route_id"] in sec_ids
                observations.append({"route_id": route["route_id"], "success": not blocked, "failure_class": "HTTP_4XX_AUTH_OR_BLOCK" if blocked else None})
        decisions = {item["capability_id"]: item for item in capability_decisions(self.contract, {"observations": observations})}
        self.assertEqual(decisions["SEC_IDENTITY_SUBMISSIONS_AND_FINANCIAL_FACTS"]["status"], "PASS")
        self.assertEqual(set(decisions["SEC_IDENTITY_SUBMISSIONS_AND_FINANCIAL_FACTS"]["controlled_blocked_routes"]), sec_ids)

    def test_paid_budget_remains_zero(self) -> None:
        self.assertEqual(self.contract["cost_policy"]["current_stage_paid_subscription_budget"], 0)
        self.assertTrue(self.contract["cost_policy"]["paid_route_activation_requires_user_approval"])


if __name__ == "__main__":
    unittest.main()
