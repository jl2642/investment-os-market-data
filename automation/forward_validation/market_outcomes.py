from __future__ import annotations

import hashlib
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, time
from typing import Any
from zoneinfo import ZoneInfo

CN=ZoneInfo("Asia/Shanghai")
UTC=ZoneInfo("UTC")
SETTLED_CUTOFF="15:30:00"
PROVIDER="EASTMONEY_PUBLIC_DAILY_KLINE"
BASE_URL="https://push2his.eastmoney.com/api/qt/stock/kline/get"


def canonical(value: Any) -> str:
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str)


def sha256(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def secid(security_id: str) -> str:
    sid=security_id.upper()
    code=sid.split(".",1)[0].zfill(6)
    if sid.endswith(".SH"):
        return f"1.{code}"
    if sid.endswith((".SZ",".BJ")):
        return f"0.{code}"
    raise ValueError(f"P45_UNSUPPORTED_MARKET:{security_id}")


def request_json(url: str,retries: int=3) -> dict[str,Any]:
    errors=[]
    for attempt in range(1,retries+1):
        try:
            req=urllib.request.Request(url,headers={
                "User-Agent":"Mozilla/5.0 InvestmentOS-P4-5/1.0",
                "Referer":"https://quote.eastmoney.com/",
            })
            with urllib.request.urlopen(req,timeout=20) as resp:
                return json.loads(resp.read().decode("utf-8",errors="replace"))
        except Exception as exc:
            errors.append(f"attempt={attempt}:{type(exc).__name__}:{exc}")
            if attempt<retries:
                time.sleep(attempt)
    raise RuntimeError("|".join(errors))


def fetch_daily(security_id: str,begin: str,end: str,fqt: int) -> dict[str,float]:
    query=urllib.parse.urlencode({
        "secid":secid(security_id),
        "klt":"101","fqt":str(fqt),
        "beg":begin.replace("-",""),"end":end.replace("-",""),
        "fields1":"f1,f2,f3,f4,f5,f6",
        "fields2":"f51,f52,f53,f54,f55,f56",
    })
    payload=request_json(f"{BASE_URL}?{query}")
    rows=((payload.get("data") or {}).get("klines") or [])
    out={}
    for raw in rows:
        parts=str(raw).split(",")
        if len(parts)>=3:
            try:
                close=float(parts[2])
            except ValueError:
                continue
            if close>0:
                out[parts[0]]=close
    return out


def fetch_calendar(begin: str,end: str) -> list[str]:
    query=urllib.parse.urlencode({
        "secid":"1.000001","klt":"101","fqt":"0",
        "beg":begin.replace("-",""),"end":end.replace("-",""),
        "fields1":"f1,f2,f3,f4,f5,f6",
        "fields2":"f51,f52,f53,f54,f55,f56",
    })
    payload=request_json(f"{BASE_URL}?{query}")
    rows=((payload.get("data") or {}).get("klines") or [])
    return sorted({
        str(row).split(",",1)[0]
        for row in rows
        if len(str(row).split(",",1)[0])==10
    })


def entry_date_for_checkpoint(checkpoint_at_utc: str,calendar: list[str]) -> str:
    checkpoint=datetime.fromisoformat(checkpoint_at_utc.replace("Z","+00:00")).astimezone(CN)
    local_date=checkpoint.date().isoformat()
    cutoff=time.fromisoformat(SETTLED_CUTOFF)
    if checkpoint.time()>=cutoff and local_date in calendar:
        eligible=[d for d in calendar if d<=local_date]
    else:
        eligible=[d for d in calendar if d<local_date]
    if not eligible:
        raise RuntimeError("P45_NO_SETTLED_ENTRY_SESSION")
    return eligible[-1]


def completed_horizon_dates(checkpoint_at_utc: str,calendar: list[str]) -> dict[str,str]:
    checkpoint=datetime.fromisoformat(checkpoint_at_utc.replace("Z","+00:00")).astimezone(CN)
    local_date=checkpoint.date().isoformat()
    future=[d for d in calendar if d>local_date]
    out={}
    if len(future)>=1: out["H1"]=future[0]
    if len(future)>=3: out["H3"]=future[2]
    if len(future)>=5: out["H5"]=future[4]
    return out


def factor_status(raw: dict[str,float],qfq: dict[str,float],dates: list[str]) -> dict[str,Any]:
    factors=[]
    for d in dates:
        r=raw.get(d); q=qfq.get(d)
        if r is None or q is None or r<=0 or q<=0:
            return {"status":"CORPORATE_ACTION_STATUS_UNRESOLVED","factor_relative_range":None}
        factors.append(q/r)
    rel=0.0 if not factors else max(factors)/min(factors)-1.0
    return {
        "status":"NO_ADJUSTMENT_FACTOR_CHANGE_OBSERVED" if rel<=1e-8 else "ADJUSTMENT_FACTOR_CHANGE_OBSERVED",
        "factor_relative_range":rel,
    }


def update_checkpoint(
    checkpoint: dict[str,Any],
    *,
    now: datetime,
    allow_outcome_reads: bool,
) -> tuple[dict[str,Any],int]:
    cp=json.loads(json.dumps(checkpoint))
    at=str(cp["checkpoint_available_at_utc"])
    local_checkpoint=datetime.fromisoformat(at.replace("Z","+00:00")).astimezone(CN)
    begin=(local_checkpoint.date()-timedelta(days=45)).isoformat()
    end=now.astimezone(CN).date().isoformat()
    calendar=fetch_calendar(begin,end)
    entry_date=entry_date_for_checkpoint(at,calendar)
    horizons=completed_horizon_dates(at,calendar)

    outcome_reads=0
    securities=cp["shared_packet"]["opportunity_security_ids"]
    endpoints=cp.setdefault("outcomes",{}).setdefault("endpoints",{})
    for sid in securities:
        if not sid.upper().endswith((".SH",".SZ",".BJ")):
            endpoints.setdefault(sid,{
                "security_id":sid,
                "status":"OUTCOME_PROVIDER_PENDING_UNSUPPORTED_MARKET",
                "entry_date":None,
                "entry_close":None,
                "entry_provider":None,
                "entry_bound_for_checkpoint_at":at,
                "horizons":{},
            })
            continue
        raw=fetch_daily(sid,begin,end,0)
        qfq=fetch_daily(sid,begin,end,1)
        if entry_date not in raw:
            endpoints.setdefault(sid,{
                "security_id":sid,
                "status":"ENTRY_CLOSE_UNRESOLVED",
                "entry_date":entry_date,
                "entry_close":None,
                "entry_provider":PROVIDER,
                "entry_bound_for_checkpoint_at":at,
                "horizons":{},
            })
            continue
        row=endpoints.setdefault(sid,{
            "security_id":sid,
            "status":"ENTRY_BOUND",
            "entry_date":entry_date,
            "entry_close":raw[entry_date],
            "entry_provider":PROVIDER,
            "entry_bound_for_checkpoint_at":at,
            "horizons":{},
        })
        if row.get("entry_date")!=entry_date or float(row.get("entry_close"))!=float(raw[entry_date]):
            raise RuntimeError(f"P45_ENTRY_ANCHOR_DRIFT:{sid}")
        if not allow_outcome_reads:
            continue
        for horizon,date in horizons.items():
            if horizon in row["horizons"]:
                continue
            if date not in raw:
                continue
            window=[d for d in calendar if entry_date<=d<=date]
            ca=factor_status(raw,qfq,window)
            if ca["status"]=="CORPORATE_ACTION_STATUS_UNRESOLVED":
                continue
            ret=raw[date]/raw[entry_date]-1.0
            row["horizons"][horizon]={
                "date":date,
                "close":raw[date],
                "provider":PROVIDER,
                "corporate_action_status":ca,
                "local_currency_price_return":ret,
            }
            outcome_reads+=1

    edges=cp["parallel_outputs"]["r2"].get("dominance_edges",[])
    edge_results=cp["outcomes"].setdefault("edge_results",{})
    if allow_outcome_reads:
        for edge in edges:
            eid=edge["edge_id"]
            erow=edge_results.setdefault(eid,{
                "edge_id":eid,
                "comparison_signature_sha256":edge["comparison_signature_sha256"],
                "dominator_security_id":edge["dominator_security_id"],
                "dominated_security_id":edge["dominated_security_id"],
                "horizons":{},
            })
            dom=endpoints.get(edge["dominator_security_id"],{})
            sub=endpoints.get(edge["dominated_security_id"],{})
            for horizon in ("H1","H3","H5"):
                if horizon in erow["horizons"]:
                    continue
                d=(dom.get("horizons") or {}).get(horizon)
                s=(sub.get("horizons") or {}).get(horizon)
                if d is None or s is None:
                    continue
                spread=float(d["local_currency_price_return"])-float(s["local_currency_price_return"])
                erow["horizons"][horizon]={
                    "edge_return_spread":spread,
                    "concordant":spread>=0,
                    "dominator_return":d["local_currency_price_return"],
                    "dominated_return":s["local_currency_price_return"],
                }

    h5_all=bool(securities) and all("H5" in endpoints.get(sid,{}).get("horizons",{}) for sid in securities)
    cp["outcome_schedule_status"]="H5_MATURE_ALL_ENDPOINTS" if h5_all else "PARTIALLY_MATURE_OR_WAITING"
    cp["economically_mature"]=h5_all
    cp["entry_binding_complete"]=all(
        endpoints.get(sid,{}).get("entry_close") is not None for sid in securities
    )
    cp["outcome_provider_pending_security_ids"]=sorted(
        sid for sid in securities
        if endpoints.get(sid,{}).get("status")=="OUTCOME_PROVIDER_PENDING_UNSUPPORTED_MARKET"
    )
    cp["last_outcome_refresh_at_utc"]=now.astimezone(UTC).replace(microsecond=0).isoformat()
    cp["outcome_read_count"]=sum(
        len(row.get("horizons",{})) for row in endpoints.values()
    )
    return cp,outcome_reads
