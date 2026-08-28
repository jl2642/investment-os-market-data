from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

CN=ZoneInfo("Asia/Shanghai")
PROVIDER="EASTMONEY_PUBLIC_DAILY_KLINE"
CLOSE_AVAILABLE_TIME="15:05:00"
BASE_URL="https://push2his.eastmoney.com/api/qt/stock/kline/get"


def canonical_hash(payload: Any) -> str:
    body=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(",",":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z","+00:00"))


def secid(security_id: str) -> str:
    sid=security_id.upper()
    code=sid.split(".",1)[0].zfill(6)
    if sid.endswith(".SH"):
        return f"1.{code}"
    if sid.endswith((".SZ",".BJ")):
        return f"0.{code}"
    raise ValueError(f"UNSUPPORTED_A_SHARE_ID:{security_id}")


def request_json(url: str, retries: int=3) -> dict[str,Any]:
    errors=[]
    for attempt in range(1,retries+1):
        try:
            req=urllib.request.Request(url,headers={
                "User-Agent":"Mozilla/5.0 InvestmentOS-P4-4/1.0",
                "Referer":"https://quote.eastmoney.com/",
            })
            with urllib.request.urlopen(req,timeout=20) as resp:
                return json.loads(resp.read().decode("utf-8",errors="replace"))
        except Exception as exc:
            errors.append(f"attempt={attempt}:{type(exc).__name__}:{exc}")
            if attempt<retries:
                time.sleep(attempt)
    raise RuntimeError("|".join(errors))


def first_eligible_mark(request: dict[str,Any], now: datetime) -> dict[str,Any] | None:
    signal=parse_ts(request["signal_available_at"]).astimezone(CN)
    today=now.astimezone(CN)
    begin=signal.date().strftime("%Y%m%d")
    end=today.date().strftime("%Y%m%d")
    query=urllib.parse.urlencode({
        "secid":secid(request["security_id"]),
        "klt":"101",
        "fqt":"0",
        "beg":begin,
        "end":end,
        "fields1":"f1,f2,f3,f4,f5,f6",
        "fields2":"f51,f52,f53,f54,f55,f56",
    })
    payload=request_json(f"{BASE_URL}?{query}")
    klines=((payload.get("data") or {}).get("klines") or [])
    candidates=[]
    for raw in klines:
        parts=str(raw).split(",")
        if len(parts)<3:
            continue
        session=parts[0]
        close=float(parts[2])
        if close<=0:
            continue
        availability=datetime.fromisoformat(f"{session}T{CLOSE_AVAILABLE_TIME}").replace(tzinfo=CN)
        if session==today.date().isoformat() and today.time()<datetime.fromisoformat(CLOSE_AVAILABLE_TIME).time():
            continue
        if availability<=signal:
            continue
        candidates.append((availability,session,close))
    if not candidates:
        return None
    availability,session,close=min(candidates,key=lambda x:x[0])
    identity=canonical_hash({
        "security_id":request["security_id"],
        "market_session":session,
        "mark":close,
        "provider":PROVIDER,
    })
    return {
        "action_id":request["action_id"],
        "security_id":request["security_id"],
        "market":"A_SHARE",
        "market_session":session,
        "mark":close,
        "mark_type":"FIRST_ELIGIBLE_COMPLETED_CLOSE_AFTER_SIGNAL",
        "provider":PROVIDER,
        "completed_session":True,
        "available_at_utc":availability.astimezone(ZoneInfo("UTC")).isoformat(),
        "mark_identity":identity,
    }


def acquire(request_path: Path, now: datetime | None=None) -> dict[str,Any]:
    now=now or datetime.now(tz=ZoneInfo("UTC"))
    req=json.loads(request_path.read_text(encoding="utf-8"))
    requests=req.get("requests",[])
    if not requests:
        return {
            "schema_version":"1.0.0",
            "packet_id":"EMPTY_NO_PENDING_ACTION",
            "status":"EMPTY_NO_PENDING_ACTION",
            "generated_at_utc":now.isoformat(),
            "request_count":0,
            "mark_count":0,
            "marks":[],
            "errors":[],
            "orders":0,
            "trade_authority":"NONE",
        }
    marks=[]
    errors=[]
    for row in requests:
        if row.get("market")!="A_SHARE":
            errors.append({
                "action_id":row.get("action_id"),
                "security_id":row.get("security_id"),
                "code":"UNSUPPORTED_MARKET_ADAPTER_FAIL_CLOSED",
            })
            continue
        try:
            mark=first_eligible_mark(row,now)
            if mark is None:
                errors.append({
                    "action_id":row.get("action_id"),
                    "security_id":row.get("security_id"),
                    "code":"NO_ELIGIBLE_COMPLETED_SESSION_AFTER_SIGNAL_YET",
                })
            else:
                marks.append(mark)
        except Exception as exc:
            errors.append({
                "action_id":row.get("action_id"),
                "security_id":row.get("security_id"),
                "code":"MARK_FETCH_FAILED",
                "detail":f"{type(exc).__name__}:{exc}",
            })
    semantic={"requests":[
        {
            "action_id":x.get("action_id"),
            "security_id":x.get("security_id"),
            "signal_available_at":x.get("signal_available_at"),
        } for x in requests
    ],"marks":marks,"errors":[
        {
            "action_id":x.get("action_id"),
            "security_id":x.get("security_id"),
            "code":x.get("code"),
        } for x in errors
    ]}
    packet_id=canonical_hash(semantic)
    status=(
        "PASS_COMPLETE" if len(marks)==len(requests)
        else "PENDING_OR_BLOCKED_FAIL_CLOSED"
    )
    return {
        "schema_version":"1.0.0",
        "packet_id":packet_id,
        "status":status,
        "generated_at_utc":now.isoformat(),
        "request_count":len(requests),
        "mark_count":len(marks),
        "marks":marks,
        "errors":errors,
        "orders":0,
        "trade_authority":"NONE",
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--mark-request",required=True)
    p.add_argument("--output",required=True)
    p.add_argument("--now")
    args=p.parse_args()
    now=datetime.fromisoformat(args.now.replace("Z","+00:00")) if args.now else None
    payload=acquire(Path(args.mark_request),now)
    Path(args.output).parent.mkdir(parents=True,exist_ok=True)
    Path(args.output).write_text(
        json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+"\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status":payload["status"],
        "requests":payload["request_count"],
        "marks":payload["mark_count"],
        "errors":len(payload["errors"]),
        "orders":0,
        "trade_authority":"NONE",
    },ensure_ascii=False))


if __name__=="__main__":
    main()
