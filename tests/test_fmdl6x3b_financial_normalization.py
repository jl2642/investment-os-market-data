from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts/fmdl6x3b_financial_normalization.py"
SPEC = importlib.util.spec_from_file_location("fmdl6x3b", MODULE_PATH)
m = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(m)


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def zip_rows(path: Path, entries: dict[str, list[dict]]) -> None:
    payload = {name: m.jsonl_bytes(rows) for name, rows in entries.items()}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(m.deterministic_zip(payload))


class FMDL6X3BTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = Path(tempfile.mkdtemp())
        contract_source = Path(__file__).resolve().parents[1] / m.CONTRACT_PATH
        contract_target = self.temp / m.CONTRACT_PATH
        contract_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(contract_source, contract_target)
        contract = m.read_json(contract_target)
        entry = {
            "phase_id": contract["entry_gate"]["required_phase_id"],
            "release_id": contract["entry_gate"]["required_release_id"],
            "release_sequence": contract["entry_gate"]["required_release_sequence"],
            "status": contract["entry_gate"]["required_status"],
            "next_gate": contract["entry_gate"]["required_next_gate"],
            "trade_authority": "NONE",
        }
        write_json(self.temp / contract["entry_gate"]["pointer_path"], entry)
        readiness_root = self.temp / contract["input_contract"]["readiness_root"]
        sec_root = self.temp / contract["input_contract"]["sec_root"]
        write_json(readiness_root / "FMDL6X3A_MANIFEST.json", {"release_id": entry["release_id"]})
        write_json(sec_root / "FMDL6X2E_MANIFEST.json", {"release_id": "SEC-TEST"})
        self.ready = [
            self.ready_row("SEC-AAPL", "ISS-AAPL", "AAPL", "LIST-AAPL"),
            self.ready_row("SEC-MSFT", "ISS-MSFT", "MSFT", "LIST-MSFT"),
            self.ready_row("SEC-NVDA", "ISS-NVDA", "NVDA", "LIST-NVDA"),
        ]
        zip_rows(readiness_root / "FMDL6X3A_READINESS_SHARDS.zip", {"SECURITY_READINESS/00.jsonl": self.ready, "ISSUER_READINESS/00.jsonl": []})
        facts = []
        facts += self.fact_set("AAPL", "SEC-AAPL", "ISS-AAPL", "0000320193-26-000013", "2025-12-28", "2026-03-28", 2026, "Q2", {
            "RevenueFromContractWithCustomerExcludingAssessedTax": (111184000000, "USD"),
            "CostOfGoodsAndServicesSold": (56403000000, "USD"),
            "GrossProfit": (54781000000, "USD"),
            "ResearchAndDevelopmentExpense": (11419000000, "USD"),
            "SellingGeneralAndAdministrativeExpense": (7477000000, "USD"),
            "OperatingIncomeLoss": (35885000000, "USD"),
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest": (35833000000, "USD"),
            "IncomeTaxExpenseBenefit": (6255000000, "USD"),
            "NetIncomeLoss": (29578000000, "USD"),
            "EarningsPerShareBasic": (2.02, "USD/shares"),
            "EarningsPerShareDiluted": (2.01, "USD/shares"),
        })
        facts += self.fact_set("MSFT", "SEC-MSFT", "ISS-MSFT", "0001193125-26-191507", "2026-01-01", "2026-03-31", 2026, "Q3", {
            "RevenueFromContractWithCustomerExcludingAssessedTax": (82886000000, "USD"),
            "CostOfGoodsAndServicesSold": (26828000000, "USD"),
            "GrossProfit": (56058000000, "USD"),
            "ResearchAndDevelopmentExpense": (8915000000, "USD"),
            "SellingAndMarketingExpense": (6814000000, "USD"),
            "GeneralAndAdministrativeExpense": (1931000000, "USD"),
            "OperatingIncomeLoss": (38398000000, "USD"),
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest": (39340000000, "USD"),
            "IncomeTaxExpenseBenefit": (7562000000, "USD"),
            "NetIncomeLoss": (31778000000, "USD"),
            "EarningsPerShareDiluted": (4.27, "USD/shares"),
        })
        facts += self.fact_set("NVDA", "SEC-NVDA", "ISS-NVDA", "0001045810-26-000052", "2026-01-26", "2026-04-26", 2026, "Q1", {
            "RevenueFromContractWithCustomerExcludingAssessedTax": (81615000000, "USD"),
            "CostOfRevenue": (20458000000, "USD"),
            "GrossProfit": (61157000000, "USD"),
            "ResearchAndDevelopmentExpense": (6321000000, "USD"),
            "SellingGeneralAndAdministrativeExpense": (1300000000, "USD"),
            "OperatingExpenses": (7621000000, "USD"),
            "OperatingIncomeLoss": (53536000000, "USD"),
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest": (69903000000, "USD"),
            "IncomeTaxExpenseBenefit": (11582000000, "USD"),
            "NetIncomeLoss": (58321000000, "USD"),
            "EarningsPerShareDiluted": (2.39, "USD/shares"),
        })
        self.assertEqual(len(facts), 33)
        zip_rows(sec_root / "FMDL6X2E_FACTS_SHARDS.zip", {"FACTS/2026/00.jsonl": facts})
        filings = []
        for row in self.ready:
            symbol = row["symbol"]
            accession = {"AAPL": "0000320193-26-000013", "MSFT": "0001193125-26-191507", "NVDA": "0001045810-26-000052"}[symbol]
            filings.append({"filing_id": "FIL-" + symbol, "canonical_issuer_id": row["canonical_issuer_id"], "canonical_security_id": row["canonical_security_id"], "symbol": symbol, "cik10": "0000000000", "accession_number": accession, "form": "10-Q", "filing_date": "2026-04-30", "accepted_at": "2026-04-30T00:00:00Z", "report_period": "2026-03-31", "source_authority": "SEC_OFFICIAL", "data_grade": "DECISION_GRADE_OFFICIAL_SEC"})
        zip_rows(sec_root / "FMDL6X2E_FILINGS_SHARDS.zip", {"FILINGS/2026/00.jsonl": filings})

    def tearDown(self) -> None:
        shutil.rmtree(self.temp)

    @staticmethod
    def ready_row(sid, iid, symbol, lid):
        return {"canonical_security_id": sid, "canonical_issuer_id": iid, "canonical_listing_id": lid, "symbol": symbol, "research_profile": "STANDARD_OPERATING_COMPANY", "ready_for_fmdl6x3b": True}

    @staticmethod
    def fact_set(symbol, sid, iid, accession, start, end, fy, fp, values):
        out = []
        for tag, (value, unit) in values.items():
            out.append({"fact_id": "FACT-" + symbol + "-" + tag, "canonical_issuer_id": iid, "canonical_security_id": sid, "symbol": symbol, "cik10": "0000000000", "accession_number": accession, "form": "10-Q", "filing_date": "2026-04-30", "accepted_at": "2026-04-30T00:00:00Z", "report_period": end, "taxonomy": "us-gaap", "tag": tag, "label": tag, "value": value, "unit": unit, "start_date": start, "end_date": end, "period_type": "duration", "fiscal_year": fy, "fiscal_period": fp, "source_url": "https://www.sec.gov/Archives/edgar/test", "source_authority": "SEC_OFFICIAL", "data_grade": "DECISION_GRADE_OFFICIAL_SEC"})
        return out

    def build_candidate(self):
        candidate = self.temp / "candidate"
        return candidate, m.build(self.temp, candidate, "2026-07-22T16:00:00Z", "abc123")

    def test_contract_validation(self):
        self.assertEqual(m.validate_contract(self.temp)["phase_id"], "FMDL-6X3-B")

    def test_source_fact_mapping_and_lineage(self):
        candidate, result = self.build_candidate()
        self.assertEqual(result["quality"]["normalized_source_fact_count"], 33)
        self.assertEqual(result["quality"]["unmapped_source_tag_count"], 0)
        with zipfile.ZipFile(candidate / "FMDL6X3B_FINANCIAL_SHARDS.zip") as archive:
            rows = []
            for name in archive.namelist():
                if name.startswith("NORMALIZED_SOURCE_FACT/"):
                    rows += [json.loads(line) for line in archive.read(name).decode().splitlines() if line]
        self.assertEqual(len(rows), 33)
        self.assertTrue(all(row["source_id"] and row["source_url"].startswith("https://www.sec.gov/") for row in rows))

    def test_derived_sga_and_opex(self):
        candidate, result = self.build_candidate()
        self.assertEqual(result["coverage"]["canonical_statement_row_count"], 36)
        with zipfile.ZipFile(candidate / "FMDL6X3B_FINANCIAL_SHARDS.zip") as archive:
            rows = []
            for name in archive.namelist():
                if name.startswith("CANONICAL_STATEMENT/"):
                    rows += [json.loads(line) for line in archive.read(name).decode().splitlines() if line]
        msft = {row["canonical_metric"]: row for row in rows if row["symbol"] == "MSFT"}
        self.assertEqual(msft["SELLING_GENERAL_AND_ADMINISTRATIVE"]["value"], 8745000000)
        self.assertEqual(msft["OPERATING_EXPENSES"]["value"], 17660000000)

    def test_derived_ratios(self):
        _, result = self.build_candidate()
        self.assertEqual(result["coverage"]["derived_metric_row_count"], 27)

    def test_validation_equations(self):
        candidate, result = self.build_candidate()
        self.assertEqual(result["quality"]["validation_check_count"], 12)
        self.assertEqual(result["quality"]["validation_failure_count"], 0)
        self.assertTrue(all(row["status"] == "PASS" for row in m.read_json(candidate / "FMDL6X3B_VALIDATION_CHECKS.json")))

    def test_ttm_and_annual_are_blocked_not_inferred(self):
        candidate, result = self.build_candidate()
        self.assertEqual(result["coverage"]["ttm_ready_security_count"], 0)
        self.assertEqual(result["coverage"]["annual_ready_security_count"], 0)
        readiness = m.read_json(candidate / "FMDL6X3B_PERIOD_READINESS.json")
        self.assertTrue(all(row["ttm_status"].startswith("BLOCKED") for row in readiness))
        self.assertTrue(all(row["annual_status"].startswith("BLOCKED") for row in readiness))

    def test_shards_and_quality(self):
        _, result = self.build_candidate()
        self.assertEqual(result["quality"]["manifested_shard_count"], 256)
        self.assertEqual(result["quality"]["quality_status"], "PASS")

    def test_same_input_byte_replay(self):
        candidate, _ = self.build_candidate()
        result = m.validate_candidate(self.temp, candidate, "2026-07-22T16:00:00Z", "abc123", self.temp / "acceptance.json")
        self.assertTrue(result["same_input_byte_replay"])

    def test_publish_and_immutable_collision(self):
        candidate, _ = self.build_candidate()
        pointer = m.publish(self.temp, candidate, "2026-07-22T16:00:00Z", "abc123")
        self.assertEqual(pointer["release_sequence"], 37)
        current = self.temp / "outputs/fmdl6x3/current/financial_normalization"
        release = self.temp / pointer["release_path"]
        self.assertEqual((current / "FMDL6X3B_DECISION.json").read_bytes(), (release / "FMDL6X3B_DECISION.json").read_bytes())
        m.publish(self.temp, candidate, "2026-07-22T16:00:00Z", "abc123")


if __name__ == "__main__":
    unittest.main()
