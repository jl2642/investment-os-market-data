"""First-batch P5 adapter. RAW daily quotes only; never publishes or appends raw to qfq.
Use explicit completed-session calendar, trusted dated security metadata, and a same-date
legacy fallback. No credentials in code, logs or files. Callers own authorization."""
from __future__ import annotations
import datetime as dt
import math, re, time, urllib.request, urllib.error, urllib.parse, json, hashlib
from collections import Counter
from zoneinfo import ZoneInfo
from pathlib import Path

FIELDS={"open":"open_price","high":"high_price","low":"low_price","close":"close_price","volume_shares":"volume","turnover_cny":"turnover"}
ZONE=ZoneInfo("Asia/Shanghai")
class SourceUnavailable(Exception):pass
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args):return None

def read_incremental_dump(key:str, path:Path, *, sleep=time.sleep, opener=None, download=None):
    """Two attempts max; request a bounded 10-day export; return digest, no raw logging.
    Injectable transports allow deterministic fault tests. Caller cleans temp directory."""
    if not key:raise SourceUnavailable("SECRET_MISSING")
    path=Path(path);opener=opener or urllib.request.build_opener(NoRedirect()).open
    download=download or urllib.request.urlopen
    for attempt in range(2):
        try:
            req=urllib.request.Request("https://fuyao.aicubes.cn/api/dump/market-dumps/daily-k-10d/download-url",headers={"X-api-key":key,"User-Agent":"InvestmentOS-P5-shadow/1.0"})
            with opener(req,timeout=20) as r:j=json.loads(r.read(65536))
            if j.get("code")!=0:
                if j.get("code") in (4001,):raise SourceUnavailable("RETRYABLE")
                raise SourceUnavailable("AUTH_OR_PROVIDER_DENIED")
            url=j.get("data",{}).get("presigned_url","")
            if urllib.parse.urlsplit(url).scheme!="https":raise SourceUnavailable("BAD_TICKET")
            h=hashlib.sha256();n=0
            # Object-storage request has no API key.
            with download(urllib.request.Request(url,headers={"User-Agent":"InvestmentOS-P5-shadow/1.0"}),timeout=30) as r,path.open("wb") as f:
                while True:
                    b=r.read(1048576)
                    if not b:break
                    n+=len(b)
                    if n>16*1024*1024:raise SourceUnavailable("BYTE_CAP")
                    h.update(b);f.write(b)
            with path.open("rb") as f:
                if f.read(4)!=b"PAR1":raise SourceUnavailable("BAD_PARQUET")
                f.seek(-4,2)
                if f.read(4)!=b"PAR1":raise SourceUnavailable("BAD_PARQUET")
            return {"sha256":h.hexdigest(),"bytes":n,"attempts":attempt+1}
        except Exception as exc:
            path.unlink(missing_ok=True)
            transient=(isinstance(exc,(TimeoutError,urllib.error.URLError)) and not isinstance(exc,urllib.error.HTTPError)) or (isinstance(exc,urllib.error.HTTPError) and exc.code in (429,500,502,503,504)) or (isinstance(exc,SourceUnavailable) and str(exc)=="RETRYABLE")
            if not transient or attempt:raise SourceUnavailable("BOUNDED_SOURCE_UNAVAILABLE") from None
            sleep(1)
    raise SourceUnavailable("BOUNDED_SOURCE_UNAVAILABLE")

def session_date(ms):
    return dt.datetime.fromtimestamp(int(ms)/1000,ZONE).date().isoformat()

def number(x):
    try:
        v=float(x)
        return v if math.isfinite(v) else None
    except (ValueError,TypeError,OverflowError):return None

def valid_quote(q):
    a=[number(q.get(k)) for k in FIELDS]
    if any(v is None for v in a):return False
    o,h,l,c,v,t=a
    return 0<l<=min(o,c)<=max(o,c)<=h and v>0 and t>0

def normalize_rows(rows, sessions, universe):
    """Map unadjusted CNY bars into canonical raw quote keys, quarantine duplicate keys.
    Unknown dates and out-of-universe securities cannot create history or membership."""
    sessions=set(sessions);universe=set(universe);out={};bad=set();counts=Counter()
    for r in rows:
        try:s=str(r["thscode"]);d=session_date(r["date_ms"])
        except (KeyError,ValueError,TypeError,OverflowError,OSError):counts["invalid_identity"]+=1;continue
        if s not in universe or not re.fullmatch(r"\d{6}\.(SH|SZ|BJ)",s):counts["outside_universe"]+=1;continue
        if d not in sessions:counts["outside_session"]+=1;continue
        k=(s,d)
        if k in out or k in bad:
            out.pop(k,None);bad.add(k);counts["duplicate_key"]+=1;continue
        q={dest:number(r.get(src)) for dest,src in FIELDS.items()}
        if r.get("adjusted")!="none" or r.get("currency")!="CNY" or r.get("interval")!="1d" or not valid_quote(q):
            bad.add(k);counts["invalid_bar"]+=1;continue
        out[k]={"symbol":s,"as_of_date":d,**q}
    return out,dict(counts)

def resolve_day(quotes, target, metadata, fallback, confirmed_suspended=frozenset()):
    """Same-date quote resolution. Metadata must independently supply exchange status,
    previous-close/return (ex-rights aware). Do not infer suspension from absent bars.
    Existing full-row fallback is invoked once for unresolved symbols; stale fallback rejected.
    Source provenance is returned separately; no output is published."""
    out={};why=Counter();unresolved=[]
    for s,m in metadata.items():
        if m.get("as_of_date")!=target:raise ValueError("METADATA_DATE")
        q=quotes.get((s,target))
        if s in confirmed_suspended:
            if q is not None:unresolved.append(s);why["status_conflict"]+=1;continue
            why["confirmed_suspension"]+=1
            # independently confirmed status; no artificial close or volume
            out[s]={**m,"data_status":"SUSPENDED","record_quality":"PARTIAL","source_primary":"exchange_status_confirmed",**{k:None for k in FIELDS},"pct_change":None,"amplitude_pct":None,"turnover_rate_pct":None,"market_cap_cny":None,"float_market_cap_cny":None,"pe_ttm":None,"pb":None}
            continue
        prev=number(m.get("prev_close"));pct=number(m.get("pct_change"))
        if q is None or m.get("data_status")!="TRADED" or prev is None or prev<=0 or pct is None or abs((q["close"]/prev-1)*100-pct)>0.05:
            unresolved.append(s);why["needs_legacy"]+=1;continue
        # All other fields remain tied to same-session legacy metadata; recompute amplitude only if already present.
        row={**m,**q,"source_primary":"hithink.raw_daily+legacy_session_metadata"}
        if row.get("amplitude_pct") is not None:row["amplitude_pct"]=(q["high"]-q["low"])/prev*100
        out[s]=row;why["primary"]+=1
    f=fallback(tuple(unresolved)) if unresolved else {}
    for s in unresolved:
        r=f.get(s)
        if r is None or r.get("as_of_date")!=target or r.get("symbol")!=s:
            why["unresolved"]+=1;continue
        if r.get("data_status")=="TRADED" and not valid_quote(r):
            why["unresolved"]+=1;continue
        if s in confirmed_suspended and r.get("data_status")!="SUSPENDED":
            why["unresolved"]+=1;continue
        out[s]=dict(r);why["legacy"]+=1
    return out,dict(why)

def raw_gap_plan(quotes, sessions, symbols, confirmed_suspensions=frozenset()):
    """Explicit date-key raw gap inventory. Not a qfq append authorization.
    Never produce zero-filled/synthetic bars or overwrite accepted adjusted history."""
    keys={(s,d) for s in symbols for d in sessions}
    suspended=keys&set(confirmed_suspensions)
    observed=keys&set(quotes)
    conflicts=suspended&observed
    usable=observed-suspended
    return {"raw_ready":len(usable),"confirmed_no_trade":len(suspended-conflicts),"status_conflict":len(conflicts),"missing":len(keys-observed-suspended),"history_append_authorized":False,"adjustment_mode":"none"}
