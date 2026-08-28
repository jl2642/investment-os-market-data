import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

from automation.operating_current.publish_operating_current import (
    build_index,
    can_advance,
    pointer_payload,
    receipt_payload,
)


class OperatingCurrentTests(unittest.TestCase):
    def make_receipt(self, status="PASS", key="2026-08-28", advance=True):
        args=Namespace(
            domain="A_SHARE_FULL_MARKET",status=status,
            source_workflow="wf",source_run_id="1",source_run_attempt=1,
            source_branch="automation/result",source_commit="a"*40,
            watermark=key,watermark_sort_key=key,qc_status="PASS",
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
            row=index["domains"][0]
            self.assertEqual(row["current"]["data_watermark"],"2026-08-28")
            self.assertEqual(row["latest_attempt"]["status"],"FAIL")
            self.assertEqual(row["health"],"LATEST_ATTEMPT_FAILED_CURRENT_PRESERVED")


if __name__=="__main__":
    unittest.main()
