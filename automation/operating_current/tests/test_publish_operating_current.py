import json
import subprocess
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from automation.operating_current.publish_operating_current import (
    build_index,
    can_advance,
    checkout_operating_branch,
    pointer_payload,
    receipt_payload,
)


class OperatingCurrentTests(unittest.TestCase):
    def make_receipt(self, status="PASS", key="2026-08-28", advance=True, qc_status="PASS"):
        args=Namespace(
            domain="A_SHARE_FULL_MARKET",status=status,
            source_workflow="wf",source_run_id="1",source_run_attempt=1,
            source_branch="automation/result",source_commit="a"*40,
            watermark=key,watermark_sort_key=key,qc_status=qc_status,
            advance_current=advance,real_account_mutations=0,
            simulation_mutations=0,candidate_membership_mutations=0,
            orders=0,trade_authority="NONE",note=""
        )
        return receipt_payload(args,"2026-08-28T00:00:00Z")

    def test_fail_never_advances(self):
        current=pointer_payload(self.make_receipt())
        ok,reason=can_advance(current,self.make_receipt(status="FAIL",key="2026-08-29",advance=False))
        self.assertFalse(ok)
        self.assertEqual(reason,"NON_PASS_DOES_NOT_ADVANCE")

    def test_watermark_regression_rejected(self):
        current=pointer_payload(self.make_receipt(key="2026-08-28"))
        ok,reason=can_advance(current,self.make_receipt(key="2026-08-27"))
        self.assertFalse(ok)
        self.assertEqual(reason,"WATERMARK_REGRESSION")

    def test_equal_watermark_refresh_allowed(self):
        current=pointer_payload(self.make_receipt(key="2026-08-28"))
        ok,reason=can_advance(current,self.make_receipt(key="2026-08-28"))
        self.assertTrue(ok)
        self.assertEqual(reason,"PASS_NONREGRESSING")

    def test_equal_watermark_qc_regression_rejected(self):
        current=pointer_payload(self.make_receipt(
            key="2026-08-28", qc_status="PASS_CHAIN_COHERENT"
        ))
        ok,reason=can_advance(current,self.make_receipt(
            key="2026-08-28", qc_status="PASS_HISTORY_FACTOR_SCREENING_REFRESH_REQUIRED"
        ))
        self.assertFalse(ok)
        self.assertEqual(reason,"SAME_WATERMARK_QC_REGRESSION")

    def test_equal_watermark_qc_upgrade_allowed(self):
        current=pointer_payload(self.make_receipt(
            key="2026-08-28", qc_status="PASS_HISTORY_FACTOR_SCREENING_REFRESH_REQUIRED"
        ))
        ok,reason=can_advance(current,self.make_receipt(
            key="2026-08-28", qc_status="PASS_CHAIN_COHERENT"
        ))
        self.assertTrue(ok)
        self.assertEqual(reason,"PASS_NONREGRESSING")

    def test_operating_branch_sync_is_append_only_merge_not_rebase(self):
        calls=[]

        def fake_run(*args, check=True):
            calls.append((args, check))
            stdout="local-head\n" if args[:3] == ("git","rev-parse","HEAD") else ""
            return subprocess.CompletedProcess(args, 0, stdout=stdout, stderr="")

        with patch(
            "automation.operating_current.publish_operating_current.remote_branch_sha",
            return_value="a"*40,
        ), patch(
            "automation.operating_current.publish_operating_current.run",
            side_effect=fake_run,
        ):
            remote, head=checkout_operating_branch()

        self.assertEqual(remote, "a"*40)
        self.assertEqual(head, "local-head")
        argv=[entry[0] for entry in calls]
        self.assertIn(("git","merge","--no-edit","origin/main"), argv)
        self.assertFalse(any(call_args[:2] == ("git","rebase") for call_args in argv))
        self.assertTrue(any(
            call_args[:3] == ("git","fetch","origin")
            and "--force" in call_args
            and "operating-current:refs/remotes/origin/operating-current" in call_args
            for call_args in argv
        ))

    def test_operating_branch_merge_conflict_fails_closed(self):
        calls=[]

        def fake_run(*args, check=True):
            calls.append((args, check))
            if args[:3] == ("git","merge","--no-edit"):
                return subprocess.CompletedProcess(args, 1, stdout="", stderr="conflict")
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

        with patch(
            "automation.operating_current.publish_operating_current.remote_branch_sha",
            return_value="b"*40,
        ), patch(
            "automation.operating_current.publish_operating_current.run",
            side_effect=fake_run,
        ):
            with self.assertRaisesRegex(RuntimeError, "OPERATING_CURRENT_MAIN_MERGE_FAILED"):
                checkout_operating_branch()

        argv=[entry[0] for entry in calls]
        self.assertIn(("git","merge","--abort"), argv)
    def test_index_preserves_current_and_exposes_latest_failure(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/"domains").mkdir()
            (root/"runs"/"A_SHARE_FULL_MARKET").mkdir(parents=True)
            current=pointer_payload(self.make_receipt(key="2026-08-28"))
            (root/"domains"/"A_SHARE_FULL_MARKET.json").write_text(json.dumps(current),encoding="utf-8")
            failed=self.make_receipt(status="FAIL",key="2026-08-29",advance=False)
            failed["published_at_utc"]="2026-08-29T00:00:00Z"
            (root/"runs"/"A_SHARE_FULL_MARKET"/"2-a1-fail.json").write_text(json.dumps(failed),encoding="utf-8")
            index=build_index(root)
            rows={x["domain_id"]:x for x in index["domains"]}
            row=rows["A_SHARE_FULL_MARKET"]
            self.assertEqual(row["current"]["data_watermark"],"2026-08-28")
            self.assertEqual(row["latest_attempt"]["status"],"FAIL")
            self.assertEqual(row["health"],"LATEST_ATTEMPT_FAILED_CURRENT_PRESERVED")
            self.assertTrue({
                "A_SHARE_FULL_MARKET",
                "PORTFOLIO_MARKS",
                "CANDIDATE_WEEKLY_OBSERVATION",
                "RESEARCH_D2",
                "CROSS_MARKET_LIMITED",
                "FINANCIAL_VALUATION_CONTEXT",
            }.issubset(rows))
            missing=[x for x in index["domains"] if x["domain_id"]!="A_SHARE_FULL_MARKET"]
            self.assertTrue(all(x["health"]=="MISSING_CURRENT" for x in missing))


if __name__=="__main__":
    unittest.main()
