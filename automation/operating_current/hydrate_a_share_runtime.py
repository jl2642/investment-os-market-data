from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

DOMAIN="A_SHARE_FULL_MARKET"
OPERATING_REF="refs/remotes/origin/operating-current"
LEGACY_PREFIX="automation/fmdl2b4-rebase-"
STATE_PATHS=(
    "outputs/history/current",
    "outputs/history/archive",
    "outputs/factors/current",
    "outputs/factors/archive",
    "datasets/history/incremental",
    "datasets/history/repair",
)


def run(*args: str, check: bool=True) -> subprocess.CompletedProcess[str]:
    cp=subprocess.run(args,text=True,capture_output=True,check=False)
    if check and cp.returncode!=0:
        raise RuntimeError(f"HYDRATE_GIT_FAILED:{' '.join(args)}:{cp.stderr.strip()}")
    return cp


def show_json(commit: str,path: str) -> dict[str,Any]:
    cp=run("git","show",f"{commit}:{path}")
    return json.loads(cp.stdout)


def fetch_named_branch(branch: str, remote_name: str) -> str:
    run("git","fetch","origin",f"refs/heads/{branch}:refs/remotes/origin/{remote_name}","--force","--no-tags")
    return run("git","rev-parse",f"refs/remotes/origin/{remote_name}").stdout.strip()


def validate_a_share_source(commit: str, label: str) -> dict[str,Any]:
    market=show_json(commit,"outputs/current/CURRENT_RELEASE.json")
    history=show_json(commit,"outputs/history/current/HISTORY_CURRENT_MANIFEST.json")
    factors=show_json(commit,"outputs/factors/current/FACTOR_CURRENT_RELEASE.json")
    dates={str(market.get("as_of_date")),str(history.get("as_of_date")),str(factors.get("as_of_date"))}
    if len(dates)!=1:
        raise RuntimeError(f"A_SHARE_RUNTIME_DATE_DIVERGENCE:{label}:{sorted(dates)}")
    date_value=next(iter(dates))
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}",date_value):
        raise RuntimeError(f"A_SHARE_RUNTIME_INVALID_DATE:{label}:{date_value}")
    if market.get("status") not in {"PUBLISHED","PUBLISHED_WITH_WARNINGS"}:
        raise RuntimeError(f"A_SHARE_RUNTIME_MARKET_NOT_PUBLISHED:{label}")
    if market.get("hard_failures"):
        raise RuntimeError(f"A_SHARE_RUNTIME_MARKET_HARD_FAILURE:{label}")
    if factors.get("status") not in {"PUBLISHED","PUBLISHED_WITH_WARNINGS"}:
        raise RuntimeError(f"A_SHARE_RUNTIME_FACTOR_NOT_PUBLISHED:{label}")
    return {"label":label,"commit":commit,"watermark":date_value}


def operating_candidate() -> dict[str,Any] | None:
    cp=run(
        "git","fetch","origin",
        "refs/heads/operating-current:refs/remotes/origin/operating-current",
        "--force","--no-tags",check=False,
    )
    if cp.returncode!=0:
        return None
    raw=run("git","show",f"{OPERATING_REF}:operating_current/domains/{DOMAIN}.json",check=False)
    if raw.returncode!=0:
        return None
    pointer=json.loads(raw.stdout)
    branch=str(pointer.get("source_branch") or "")
    commit=str(pointer.get("source_commit_sha") or "")
    if not branch or not commit:
        return None
    remote=fetch_named_branch(branch,"hydrate-a-share-current-source")
    if run("git","merge-base","--is-ancestor",commit,remote,check=False).returncode!=0:
        raise RuntimeError("A_SHARE_CURRENT_SOURCE_NOT_ON_REMOTE_BRANCH")
    candidate=validate_a_share_source(commit,"OPERATING_CURRENT")
    candidate["source_branch"]=branch
    return candidate


def legacy_candidates(limit: int=8) -> list[dict[str,Any]]:
    refs=run("git","ls-remote","--heads","origin",f"refs/heads/{LEGACY_PREFIX}*",check=False)
    rows=[]
    for line in refs.stdout.splitlines():
        parts=line.split()
        if len(parts)!=2:
            continue
        commit=parts[0]
        branch=parts[1].removeprefix("refs/heads/")
        match=re.search(r"rebase-(\d+)-a(\d+)$",branch)
        sort_key=(int(match.group(1)),int(match.group(2))) if match else (0,0)
        rows.append((sort_key,branch,commit))
    rows.sort(reverse=True)
    out=[]
    for idx,(_,branch,expected) in enumerate(rows[:limit]):
        remote=fetch_named_branch(branch,f"hydrate-a-share-legacy-{idx}")
        if remote!=expected:
            raise RuntimeError(f"A_SHARE_LEGACY_REMOTE_DRIFT:{branch}")
        try:
            candidate=validate_a_share_source(remote,f"LEGACY_RECOVERY:{branch}")
        except Exception:
            continue
        candidate["source_branch"]=branch
        out.append(candidate)
    return out


def choose_source(candidates: list[dict[str,Any]]) -> dict[str,Any]:
    if not candidates:
        raise RuntimeError("A_SHARE_NO_VALID_RUNTIME_SOURCE")
    # On equal watermarks prefer formal Operating Current over legacy recovery.
    return max(
        candidates,
        key=lambda row:(str(row["watermark"]),1 if row["label"]=="OPERATING_CURRENT" else 0),
    )


def hydrate() -> dict[str,Any]:
    candidates=[]
    current=operating_candidate()
    if current:
        candidates.append(current)
    candidates.extend(legacy_candidates())
    chosen=choose_source(candidates)
    for path in STATE_PATHS:
        exists=run("git","cat-file","-e",f"{chosen['commit']}:{path}",check=False)
        if exists.returncode!=0:
            raise RuntimeError(f"A_SHARE_RUNTIME_PATH_MISSING:{chosen['commit']}:{path}")
        run("git","checkout",chosen["commit"],"--",path)
    result={
        "status":"HYDRATED",
        "domain":DOMAIN,
        "source_label":chosen["label"],
        "source_branch":chosen["source_branch"],
        "source_commit":chosen["commit"],
        "watermark":chosen["watermark"],
        "restored_paths":list(STATE_PATHS),
        "protected_state_mutations":0,
        "orders":0,
        "trade_authority":"NONE",
    }
    print(json.dumps(result,ensure_ascii=False,sort_keys=True))
    return result


if __name__=="__main__":
    hydrate()
