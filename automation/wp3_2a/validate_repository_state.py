from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

def sha(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""): h.update(c)
    return h.hexdigest()

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--repo-root",required=True); a=ap.parse_args(); repo=Path(a.repo_root)
    errors=[]; proposals=[]
    root=repo/"investment_os_runtime/40_EVIDENCE_AND_LINEAGE/WP3_2A/PROPOSALS"
    if root.exists():
        for p in sorted(x for x in root.iterdir() if x.is_dir()):
            required=["A_SHARE_FULL_UNIVERSE.csv","ACQUISITION_MANIFEST.json","LINEAGE_ACCEPTANCE.json","PROPOSAL_MANIFEST.json","ZERO_INVESTMENT_MUTATION_PROOF.json"]
            missing=[x for x in required if not (p/x).exists()]
            if missing: errors.append(f"{p.name}: missing {missing}"); continue
            m=json.loads((p/"PROPOSAL_MANIFEST.json").read_text(encoding="utf-8")); l=json.loads((p/"LINEAGE_ACCEPTANCE.json").read_text(encoding="utf-8"))
            if l.get("status")!="PASS": errors.append(f"{p.name}: lineage not PASS")
            if sha(p/"A_SHARE_FULL_UNIVERSE.csv")!=m.get("data_sha256"): errors.append(f"{p.name}: data hash mismatch")
            if m.get("trade_authority")!="NONE" or m.get("orders")!=0: errors.append(f"{p.name}: authority violation")
            proposals.append(p.name)
    current=repo/"investment_os_runtime/40_EVIDENCE_AND_LINEAGE/WP3_2A/CURRENT"
    if current.exists():
        for name in ["A_SHARE_FULL_UNIVERSE.csv","LINEAGE_ACCEPTANCE.json","PROPOSAL_MANIFEST.json"]:
            if not (current/name).exists(): errors.append(f"CURRENT missing {name}")
    result={"status":"PASS" if not errors else "FAIL","proposal_count":len(proposals),"proposals":proposals,"current_present":current.exists(),"errors":errors,"orders":0,"trade_authority":"NONE"}
    print(json.dumps(result,ensure_ascii=False,indent=2)); raise SystemExit(0 if not errors else 2)
if __name__=="__main__":main()
