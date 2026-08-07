#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
import pandas as pd

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",required=True)
    args=p.parse_args()
    out=Path(args.output)
    decision=json.loads((out/"HKCU_P2B_E1_DECISION.json").read_text())
    quality=json.loads((out/"HKCU_P2B_E1_QUALITY_REPORT.json").read_text())
    dim=pd.read_csv(out/"HKCU_P2B_E1_DIMENSION_MATRIX.csv")
    ah=pd.read_csv(out/"HKCU_P2B_E1_AH_PAIR_REGISTRY.csv",dtype={"a_code":str,"h_code":str})
    rem=pd.read_csv(out/"HKCU_P2B_E1_REMAINING_RESEARCH_QUEUE.csv")
    errors=[]
    if decision.get("status")!="PASS_P2B_E1_COMMON_AH_EVIDENCE": errors.append("DECISION")
    if quality.get("status")!="PASS": errors.append("QUALITY")
    if decision.get("transaction_tax_tasks_completed")!=77: errors.append("TX_COUNT")
    if decision.get("ah_leads_resolved")!=15: errors.append("AH_COUNT")
    if decision.get("true_ah_pairs")!=13: errors.append("AH_TRUE")
    if decision.get("not_applicable_ah_leads")!=2: errors.append("AH_NA")
    if len(rem)!=231: errors.append("REMAINING")
    if set(rem["research_dimension"])!={"GOVERNANCE_VALUE_TRAP","EARNINGS_EXPECTATION_REVISION","CATALYST"}: errors.append("REMAINING_DIMS")
    if not (dim.loc[dim["research_dimension"].eq("TRANSACTION_COST_TAX"),"evidence_status"]=="EVIDENCE_COMPLETE").all(): errors.append("TX_NOT_COMPLETE")
    ahdim=dim[dim["research_dimension"].eq("A_H_RELATIVE_VALUATION")]
    if int((ahdim["evidence_status"]=="EVIDENCE_COMPLETE").sum())!=15: errors.append("AH_COMPLETE")
    if ah["security_id"].duplicated().any(): errors.append("AH_DUP")
    for col in ["candidate_pool_mutations","simulation_mutations","real_account_mutations","orders_created"]:
        if decision.get(col)!=0: errors.append(col)
    if decision.get("trade_authority")!="NONE": errors.append("AUTHORITY")
    if errors: raise SystemExit("P2B_E1_VALIDATION_FAILED:"+",".join(errors))
    print("PASS_P2B_E1_VALIDATION")

if __name__=="__main__":
    main()
