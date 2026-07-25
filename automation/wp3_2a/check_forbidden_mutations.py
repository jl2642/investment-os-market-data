from __future__ import annotations
import argparse, json, subprocess
from pathlib import Path

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--repo-root",required=True); ap.add_argument("--base-ref",required=True); ap.add_argument("--config",required=True)
    a=ap.parse_args(); repo=Path(a.repo_root); config=json.loads(Path(a.config).read_text(encoding="utf-8"))
    run=subprocess.run(["git","diff","--name-only",f"{a.base_ref}...HEAD"],cwd=repo,text=True,capture_output=True)
    if run.returncode: raise SystemExit(run.stderr)
    files=[x.strip() for x in run.stdout.splitlines() if x.strip()]
    forbidden=[f for f in files if any(f.startswith(p) for p in config["forbidden_mutation_prefixes"])]
    result={"status":"PASS" if not forbidden else "FAIL","changed_files":files,"forbidden_files":forbidden,"orders":0,"trade_authority":"NONE"}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    raise SystemExit(0 if not forbidden else 2)
if __name__=="__main__": main()
