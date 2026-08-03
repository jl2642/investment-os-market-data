import json, subprocess, sys, tempfile, unittest
from pathlib import Path
SCRIPT=Path(__file__).resolve().parents[1]/"p0_operational.py"
class P0Tests(unittest.TestCase):
    def run_cli(self,*args,cwd=None): return subprocess.run([sys.executable,str(SCRIPT),*map(str,args)],cwd=cwd,text=True,capture_output=True)
    def make_repo(self,root:Path,authority="NONE"):
        c=root/"investment_os_runtime/00_CONTROL"; s=root/"investment_os_runtime/20_SCHEMAS_AND_INTERFACES"; p=root/"investment_os_runtime/80_PRODUCTION_ACCEPTANCE"; st=root/"investment_os_runtime/30_STATE_CURRENT"
        c.mkdir(parents=True); s.mkdir(parents=True); p.mkdir(parents=True); (st/"10_REAL_ACCOUNT").mkdir(parents=True); (st/"20_SIMULATION").mkdir(); (st/"40_CANDIDATE").mkdir()
        src=Path(__file__).resolve().parents[3]
        for name in ["CORE_STATIC_CONSTITUTION_CURRENT.md","CORE_RULE_CATALOG_CURRENT.json","CANONICAL_IO_CONTRACT_CURRENT.json","MARKET_DATA_EOD_CONTRACT_CURRENT.json","PORTFOLIO_SNAPSHOT_CONTRACT_CURRENT.json","PERFORMANCE_ATTRIBUTION_CONTRACT_CURRENT.json","REPORTING_MANIFEST_CONTRACT_CURRENT.json","RESEARCH_FUNNEL_CONTRACT_CURRENT.json","OBSERVABILITY_CONTRACT_CURRENT.json","P0_ACCEPTANCE_REGISTER_CURRENT.json","R6_P0_ACCEPTANCE_CHECKLIST_CURRENT.md"]: (c/name).write_bytes((src/"investment_os_runtime/00_CONTROL"/name).read_bytes())
        for name in ["canonical_run_manifest.schema.json","report_manifest.schema.json","p0_acceptance_register.schema.json"]: (s/name).write_bytes((src/"investment_os_runtime/20_SCHEMAS_AND_INTERFACES"/name).read_bytes())
        def dump(path,obj): path.write_text(json.dumps(obj),encoding="utf-8")
        dump(c/"EXECUTION_REGISTER_CURRENT.json",{"trade_authority":authority})
        dump(c/"R4_OPERATING_PRODUCT_CONTRACT_CURRENT.json",{"development_mode":True,"trade_authority":"NONE"})
        dump(c/"R5_ATTRIBUTION_CONTRACT_CURRENT.json",{"layers":[{"status":"BLOCKED"}],"trade_authority":"NONE"})
        dump(c/"R6_PRODUCTION_ACCEPTANCE_CONTRACT_CURRENT.json",{"production_completion_definition":{"full_month_complete":False},"trade_authority":"NONE"})
        dump(p/"R6_OBSERVATION_LEDGER_CURRENT.json",{"checkpoint_passed":1,"checkpoint_total":10,"trade_authority":"NONE"})
        dump(st/"10_REAL_ACCOUNT/REAL_ACCOUNT_POSITIONS_CURRENT.json",{"holdings":[{}]*7,"trade_authority":"NONE"})
        dump(st/"20_SIMULATION/SIMULATION_POSITIONS_CURRENT.json",{"holdings":[{}]*16,"trade_authority":"NONE"})
        dump(st/"40_CANDIDATE/CANDIDATE_CURRENT.json",{"counts":{"candidate_core":2,"research_queue":33,"shadow_track":38,"ready_for_user_decision":0},"trade_authority":"NONE"})
    def test_validate_pass_with_blockers(self):
        with tempfile.TemporaryDirectory() as td:
            self.make_repo(Path(td)); p=self.run_cli("validate","--repo-root",td); self.assertEqual(p.returncode,0,p.stdout+p.stderr); self.assertEqual(json.loads(p.stdout)["status"],"PASS_WITH_BLOCKERS")
    def test_authority_violation_fails(self):
        with tempfile.TemporaryDirectory() as td:
            self.make_repo(Path(td),"FULL"); p=self.run_cli("validate","--repo-root",td); self.assertNotEqual(p.returncode,0); self.assertIn("TRADE_AUTHORITY",p.stdout)
    def test_run_manifest_is_deterministic(self):
        args=["build-run-manifest","--workflow-name","x","--trigger-type","manual","--started-at","2026-08-03T00:00:00Z","--completed-at","2026-08-03T00:01:00Z","--commit-before","abcdef0","--commit-after","abcdef0","--idempotency-key","k","--status","NO_OP"]
        a=self.run_cli(*args); b=self.run_cli(*args); self.assertEqual(json.loads(a.stdout)["run_id"],json.loads(b.stdout)["run_id"])
    def test_report_manifest_blocks_low_completeness(self):
        p=self.run_cli("build-report-manifest","--report-type","MONTHLY","--period-start","2026-07-01","--period-end","2026-07-31","--commit","abcdef0","--completeness","0.4"); self.assertEqual(json.loads(p.stdout)["publication_status"],"BLOCKED")
if __name__=="__main__": unittest.main()
