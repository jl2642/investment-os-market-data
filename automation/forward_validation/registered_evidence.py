from __future__ import annotations

import hashlib
import json
import subprocess
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

MAIN_FAMILIES={
    "CANDIDATE_STATE":{
        "path":"investment_os_runtime/30_STATE_CURRENT/40_CANDIDATE/CANDIDATE_CURRENT.json",
        "evidence_key":"CANDIDATE_STATE",
    },
    "REAL_ACCOUNT_STATE":{
        "path":"investment_os_runtime/30_STATE_CURRENT/10_REAL_ACCOUNT/REAL_ACCOUNT_POSITIONS_CURRENT.json",
        "evidence_key":"REAL_ACCOUNT_STATE",
    },
    "RESEARCH_CORE2":{
        "path":"investment_os_runtime/30_STATE_CURRENT/30_RESEARCH/WP4_CORE2_RESEARCH_CURRENT.json",
        "evidence_key":"RESEARCH_CORE2",
    },
    "RESEARCH_601138_P0":{
        "path":"investment_os_runtime/40_EVIDENCE_AND_LINEAGE/WP5/P0_REUNDERWRITE/601138.SH/WP5_P0_REUNDERWRITE_CURRENT.json",
        "evidence_key":"RESEARCH_601138_P0",
    },
    "DECISION_00669_BUY_REVIEW":{
        "path":"investment_os_runtime/30_STATE_CURRENT/60_DECISIONS/HKCU_TTI_00669_BUY_REVIEW_CURRENT.json",
        "evidence_key":"DECISION_00669_BUY_REVIEW",
    },
}
D2_STATE_PATH="investment_os_runtime/30_STATE_CURRENT/30_RESEARCH/RESEARCH_QUEUE_D2_CURRENT.json"
VOLATILE_D2_KEYS={"as_of","state_id","last_attempt_at","attempt_count","generated_at","generated_at_utc"}


def canonical(value: Any) -> str:
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str)


def sha256(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def parse_ts(value: str) -> datetime:
    dt=datetime.fromisoformat(value.replace("Z","+00:00"))
    if dt.tzinfo is None:
        dt=dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def git(repo_root: Path,*args: str,check: bool=True) -> subprocess.CompletedProcess[str]:
    cp=subprocess.run(["git",*args],cwd=repo_root,text=True,capture_output=True,check=False)
    if check and cp.returncode!=0:
        raise RuntimeError(f"P45_GIT_FAILED:{' '.join(args)}:{cp.stderr.strip()}")
    return cp


def blob_at(repo_root: Path,commit: str,path: str) -> str | None:
    cp=git(repo_root,"rev-parse",f"{commit}:{path}",check=False)
    return cp.stdout.strip() if cp.returncode==0 and cp.stdout.strip() else None


def show_json(repo_root: Path,commit: str,path: str) -> dict[str,Any]:
    cp=git(repo_root,"show",f"{commit}:{path}")
    return json.loads(cp.stdout)


def commit_time(repo_root: Path,commit: str) -> str:
    return git(repo_root,"show","-s","--format=%cI",commit).stdout.strip()


def is_ancestor(repo_root: Path,ancestor: str,descendant: str) -> bool:
    return git(repo_root,"merge-base","--is-ancestor",ancestor,descendant,check=False).returncode==0


def strip_volatile(value: Any) -> Any:
    if isinstance(value,Mapping):
        return {k:strip_volatile(v) for k,v in sorted(value.items()) if k not in VOLATILE_D2_KEYS}
    if isinstance(value,list):
        return [strip_volatile(x) for x in value]
    return value


def d2_artifacts(repo_root: Path,source_commit: str,d2: Mapping[str,Any]) -> list[dict[str,Any]]:
    rows=[]
    for q in sorted(d2.get("queue",[]),key=lambda x:str(x.get("security_id",""))):
        path=str(q.get("semantic_artifact") or "")
        if not path:
            raise RuntimeError(f"P45_D2_ARTIFACT_PATH_MISSING:{q.get('security_id')}")
        blob=blob_at(repo_root,source_commit,path)
        if not blob:
            raise RuntimeError(f"P45_D2_ARTIFACT_UNRESOLVED:{source_commit}:{path}")
        data=show_json(repo_root,source_commit,path)
        sid=str(q["security_id"])
        if str(data.get("security_id"))!=sid:
            raise RuntimeError(f"P45_D2_ARTIFACT_SECURITY_MISMATCH:{sid}")
        rows.append({"security_id":sid,"path":path,"blob_sha":blob})
    return rows


def d2_semantic_identity(repo_root: Path,source_commit: str) -> dict[str,Any]:
    d2=show_json(repo_root,source_commit,D2_STATE_PATH)
    state_blob=blob_at(repo_root,source_commit,D2_STATE_PATH)
    artifacts=d2_artifacts(repo_root,source_commit,d2)
    semantic=sha256({
        "state":strip_volatile(d2),
        "artifact_blobs":artifacts,
    })
    return {
        "family_id":"RESEARCH_D2",
        "authority":"GOVERNED_OPERATING_D2_SOURCE",
        "source_commit":source_commit,
        "path":D2_STATE_PATH,
        "blob_sha":state_blob,
        "semantic_identity":semantic,
        "d2_state":d2,
        "artifacts":artifacts,
    }


def main_family_baseline(repo_root: Path,main_commit: str) -> dict[str,Any]:
    out={}
    for family,cfg in MAIN_FAMILIES.items():
        blob=blob_at(repo_root,main_commit,cfg["path"])
        if not blob:
            raise RuntimeError(f"P45_REGISTERED_MAIN_FAMILY_MISSING:{family}:{cfg['path']}")
        out[family]={
            "family_id":family,
            "authority":"PROTECTED_MAIN",
            "source_commit":main_commit,
            "path":cfg["path"],
            "blob_sha":blob,
            "semantic_identity":blob,
        }
    return out


def main_family_events(
    repo_root: Path,
    *,
    baseline_commit: str,
    current_commit: str,
    cutoff_utc: str,
) -> list[dict[str,Any]]:
    if not is_ancestor(repo_root,baseline_commit,current_commit):
        raise RuntimeError("P45_MAIN_HISTORY_DISCONTINUITY")
    cutoff=parse_ts(cutoff_utc)
    events=[]
    for family,cfg in MAIN_FAMILIES.items():
        cp=git(
            repo_root,"log","--first-parent","--full-history","--reverse",
            "--format=%H%x09%cI",
            f"{baseline_commit}..{current_commit}","--",cfg["path"]
        )
        prior_blob=blob_at(repo_root,baseline_commit,cfg["path"])
        for line in cp.stdout.splitlines():
            if not line.strip(): continue
            commit,available_at=line.split("\t",1)
            blob=blob_at(repo_root,commit,cfg["path"])
            if not blob or blob==prior_blob:
                continue
            prior_blob=blob
            if parse_ts(available_at)<=cutoff:
                continue
            events.append({
                "family_id":family,
                "authority":"PROTECTED_MAIN",
                "source_commit":commit,
                "path":cfg["path"],
                "blob_sha":blob,
                "semantic_identity":blob,
                "available_at_utc":parse_ts(available_at).isoformat(),
                "evidence_key":cfg["evidence_key"],
            })
    return events


def d2_events_from_receipts(
    repo_root: Path,
    *,
    receipts_dir: Path,
    cutoff_utc: str,
    baseline_semantic_identity: str,
) -> list[dict[str,Any]]:
    cutoff=parse_ts(cutoff_utc)
    events=[]
    seen_semantics={baseline_semantic_identity}
    for path in sorted(receipts_dir.glob("*.json")) if receipts_dir.exists() else []:
        try:
            receipt=json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if receipt.get("domain_id")!="RESEARCH_D2" or receipt.get("status")!="PASS":
            continue
        available_at=str(receipt.get("published_at_utc") or "")
        if not available_at or parse_ts(available_at)<=cutoff:
            continue
        source_commit=str(receipt.get("source_commit_sha") or "")
        if not source_commit:
            continue
        identity=d2_semantic_identity(repo_root,source_commit)
        semantic=identity["semantic_identity"]
        if semantic in seen_semantics:
            continue
        seen_semantics.add(semantic)
        events.append({
            **{k:v for k,v in identity.items() if k not in {"d2_state","artifacts"}},
            "available_at_utc":parse_ts(available_at).isoformat(),
            "evidence_key":"RESEARCH_D2_DYNAMIC",
            "d2_state":identity["d2_state"],
            "artifacts":identity["artifacts"],
            "operating_receipt":receipt,
        })
    return events


def security_ids_for_family(family_id: str,data: Mapping[str,Any]) -> list[str]:
    ids=set()
    if family_id=="CANDIDATE_STATE":
        for row in data.get("candidate_core_members",[]):
            if row.get("security_id"): ids.add(str(row["security_id"]))
        for row in data.get("historical_core20_archive",[]):
            sid=row.get("security_id")
            if sid: ids.add(str(sid))
            else:
                code=str(row.get("stock_code") or row.get("code") or "").zfill(6)
                if code and code!="000000":
                    suffix=".SH" if code.startswith(("5","6")) else ".SZ"
                    ids.add(code+suffix)
    elif family_id=="REAL_ACCOUNT_STATE":
        for row in data.get("holdings",[]):
            sid=row.get("security_id")
            if sid: ids.add(str(sid))
    elif family_id=="RESEARCH_CORE2":
        for row in data.get("records",[]):
            if row.get("security_id"): ids.add(str(row["security_id"]))
    elif family_id=="RESEARCH_601138_P0":
        ids.update(str(x) for x in (data.get("research_objects") or {}).keys())
    elif family_id=="DECISION_00669_BUY_REVIEW":
        if data.get("security_id"): ids.add(str(data["security_id"]))
    return sorted(ids)


def evidence_records_for_version(repo_root: Path,version: Mapping[str,Any]) -> tuple[list[dict[str,Any]],dict[str,Any]]:
    family=str(version["family_id"])
    available=str(version["available_at_utc"])
    if family=="RESEARCH_D2":
        records=[]
        data_by_id={}
        d2=version.get("d2_state") or show_json(repo_root,str(version["source_commit"]),D2_STATE_PATH)
        artifacts=version.get("artifacts") or d2_artifacts(repo_root,str(version["source_commit"]),d2)
        for row in artifacts:
            eid="P45_"+sha256({
                "family":family,"commit":version["source_commit"],
                "path":row["path"],"blob":row["blob_sha"],
            })[:28]
            records.append({
                "evidence_id":eid,
                "evidence_key":"RESEARCH_D2_"+row["security_id"].replace(".","_"),
                "evidence_class":["RESEARCH_D2","PRIMARY_DISCLOSURE_SYNTHESIS"],
                "security_ids":[row["security_id"]],
                "available_at":available,
                "source":{
                    "commit_sha":version["source_commit"],"path":row["path"],
                    "blob_sha":row["blob_sha"],"provenance_status":"GOVERNED_D2_SOURCE",
                },
            })
            data_by_id[eid]=show_json(repo_root,str(version["source_commit"]),row["path"])
        return records,data_by_id

    data=show_json(repo_root,str(version["source_commit"]),str(version["path"]))
    ids=security_ids_for_family(family,data)
    eid="P45_"+sha256({
        "family":family,"commit":version["source_commit"],
        "path":version["path"],"blob":version["blob_sha"],
    })[:28]
    record={
        "evidence_id":eid,
        "evidence_key":MAIN_FAMILIES[family]["evidence_key"],
        "evidence_class":[family],
        "security_ids":ids,
        "available_at":available,
        "source":{
            "commit_sha":version["source_commit"],"path":version["path"],
            "blob_sha":version["blob_sha"],"provenance_status":"PROTECTED_MAIN",
        },
    }
    return [record],{eid:data}


def event_sort_key(event: Mapping[str,Any]) -> tuple[str,str,str]:
    return (
        str(event["available_at_utc"]),
        str(event["family_id"]),
        str(event["semantic_identity"]),
    )


def build_global_packet(
    repo_root: Path,
    *,
    event: Mapping[str,Any],
    active_versions: Mapping[str,Mapping[str,Any]],
) -> tuple[dict[str,Any],dict[str,Any]]:
    records=[]
    data_by_id={}
    opportunity_ids=set()
    for family in sorted(active_versions):
        version=active_versions[family]
        recs,data=evidence_records_for_version(repo_root,version)
        records.extend(recs)
        data_by_id.update(data)
        for rec in recs:
            opportunity_ids.update(str(x) for x in rec.get("security_ids",[]))
    records.sort(key=lambda x:x["evidence_id"])
    packet={
        "decision_point_id":"P45_"+sha256({
            "event_family":event["family_id"],
            "event_semantic_identity":event["semantic_identity"],
            "active_family_semantics":{
                k:active_versions[k]["semantic_identity"] for k in sorted(active_versions)
            },
        })[:24],
        "at":event["available_at_utc"],
        "opportunity_security_ids":sorted(opportunity_ids),
        "selected_evidence_ids":[x["evidence_id"] for x in records],
        "selected_evidence":records,
        "contributing_registered_family_ids":sorted(active_versions),
        "active_family_source_identities":{
            k:{
                "source_commit":active_versions[k]["source_commit"],
                "path":active_versions[k]["path"],
                "blob_sha":active_versions[k]["blob_sha"],
                "semantic_identity":active_versions[k]["semantic_identity"],
                "available_at_utc":active_versions[k]["available_at_utc"],
            }
            for k in sorted(active_versions)
        },
        "trigger_event":{
            "family_id":event["family_id"],
            "semantic_identity":event["semantic_identity"],
            "available_at_utc":event["available_at_utc"],
        },
    }
    packet["global_forward_evidence_state_fingerprint"]=sha256({
        "active_family_semantics":{
            k:active_versions[k]["semantic_identity"] for k in sorted(active_versions)
        }
    })
    packet["packet_sha256"]=sha256(packet)
    return packet,data_by_id
