from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any


def run(*args: str, check: bool=True) -> subprocess.CompletedProcess[str]:
    cp=subprocess.run(args,text=True,capture_output=True,check=False)
    if check and cp.returncode!=0:
        raise RuntimeError(f"DOMAIN_HYDRATE_GIT_FAILED:{' '.join(args)}:{cp.stderr.strip()}")
    return cp


def load_domain_row(domain: str) -> dict[str,Any]:
    run(
        "git","fetch","origin",
        "refs/heads/operating-current:refs/remotes/origin/operating-current",
        "--force","--no-tags",
    )
    raw=run("git","show","refs/remotes/origin/operating-current:operating_current/OPERATING_CURRENT_INDEX.json")
    index=json.loads(raw.stdout)
    row=next((x for x in index.get("domains",[]) if x.get("domain_id")==domain),None)
    if row is None:
        raise RuntimeError(f"DOMAIN_NOT_IN_OPERATING_INDEX:{domain}")
    return row


def source_for(row: dict[str,Any], allow_latest_attempt: bool) -> tuple[dict[str,Any],bool]:
    current=row.get("current")
    latest=row.get("latest_attempt")
    if allow_latest_attempt and latest:
        if current is None or str(latest.get("published_at_utc") or "") > str(current.get("published_at_utc") or ""):
            return latest,True
    if current:
        return current,False
    if allow_latest_attempt and latest:
        return latest,True
    raise RuntimeError(f"NO_HYDRATABLE_DOMAIN_SOURCE:{row.get('domain_id')}")


def hydrate(domain: str, paths: list[str], allow_latest_attempt: bool=False) -> dict[str,Any]:
    row=load_domain_row(domain)
    source,used_latest_attempt=source_for(row,allow_latest_attempt)
    branch=str(source.get("source_branch") or "")
    commit=str(source.get("source_commit_sha") or "")
    if not branch or not commit:
        raise RuntimeError("DOMAIN_SOURCE_IDENTITY_INCOMPLETE")
    safe=domain.lower().replace("_","-")
    remote=f"refs/remotes/origin/hydrate-{safe}"
    run("git","fetch","origin",f"refs/heads/{branch}:{remote}","--force","--no-tags")
    remote_head=run("git","rev-parse",remote).stdout.strip()
    if run("git","merge-base","--is-ancestor",commit,remote_head,check=False).returncode!=0:
        raise RuntimeError(f"DOMAIN_SOURCE_COMMIT_NOT_ON_REMOTE:{domain}:{commit}")
    restored=[]
    for raw_path in paths:
        path=str(Path(raw_path))
        if path.startswith("../") or path.startswith("/"):
            raise RuntimeError(f"DOMAIN_HYDRATE_UNSAFE_PATH:{path}")
        if run("git","cat-file","-e",f"{commit}:{path}",check=False).returncode!=0:
            raise RuntimeError(f"DOMAIN_HYDRATE_PATH_MISSING:{domain}:{path}")
        run("git","checkout",commit,"--",path)
        restored.append(path)
    result={
        "status":"HYDRATED",
        "domain":domain,
        "source_status":source.get("status"),
        "source_branch":branch,
        "source_commit":commit,
        "source_watermark":source.get("data_watermark"),
        "used_latest_attempt":used_latest_attempt,
        "restored_paths":restored,
        "protected_state_mutations":0,
        "orders":0,
        "trade_authority":"NONE",
    }
    print(json.dumps(result,ensure_ascii=False,sort_keys=True))
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--domain",required=True)
    p.add_argument("--path",action="append",dest="paths",required=True)
    p.add_argument("--allow-latest-attempt",action="store_true")
    args=p.parse_args()
    hydrate(args.domain,args.paths,args.allow_latest_attempt)


if __name__=="__main__":
    main()
