from __future__ import annotations

import argparse, bisect, hashlib, json, re, shutil, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import akshare as ak
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "config/fmdl3a_benchmark.json"
TZ = ZoneInfo("Asia/Shanghai")
STATEMENTS = {
    "BALANCE_SHEET": ("stock_balance_sheet_by_report_em", "资产负债表"),
    "INCOME_STATEMENT": ("stock_profit_sheet_by_report_em", "利润表"),
    "CASH_FLOW_STATEMENT": ("stock_cash_flow_sheet_by_report_em", "现金流量表"),
}
META = {
    "CNINFO_OFFICIAL_DISCLOSURE": ("DISCLOSURE_METADATA", "REGULATORY_OR_EXCHANGE_STRUCTURED_DISCLOSURE"),
    "EASTMONEY_NOTICE_FALLBACK": ("DISCLOSURE_METADATA", "AUDITABLE_STANDARDIZED_PUBLIC_PROVIDER"),
    "EASTMONEY_STATEMENTS": ("FINANCIAL_STATEMENTS", "AUDITABLE_STANDARDIZED_PUBLIC_PROVIDER"),
    "SINA_STATEMENTS": ("FINANCIAL_STATEMENTS", "AUDITABLE_STANDARDIZED_PUBLIC_PROVIDER"),
    "EASTMONEY_FINANCIAL_INDICATORS": ("FINANCIAL_INDICATORS", "AUDITABLE_STANDARDIZED_PUBLIC_PROVIDER"),
    "EASTMONEY_CURRENT_VALUATION": ("VALUATION_AND_CAPITALIZATION", "MARKET_DATA_PROVIDER_FOR_MARKET_NUMERATORS"),
    "EASTMONEY_HISTORICAL_VALUATION": ("VALUATION_AND_CAPITALIZATION", "MARKET_DATA_PROVIDER_FOR_MARKET_NUMERATORS"),
    "EASTMONEY_SHARE_CAPITAL": ("SHARE_CAPITAL", "AUDITABLE_STANDARDIZED_PUBLIC_PROVIDER"),
    "EASTMONEY_DIVIDENDS": ("SHAREHOLDER_RETURN", "AUDITABLE_STANDARDIZED_PUBLIC_PROVIDER"),
    "EASTMONEY_BUYBACKS": ("SHAREHOLDER_RETURN", "AUDITABLE_STANDARDIZED_PUBLIC_PROVIDER"),
    "SINA_TRADING_CALENDAR": ("MARKET_CALENDAR", "AUDITABLE_STANDARDIZED_PUBLIC_PROVIDER"),
}

def now() -> datetime: return datetime.now(TZ)
def code(s: str) -> str: return s.split(".")[0]
def em_symbol(s: str) -> str:
    c, x = s.split("."); return f"{x}{c}"
def sina_symbol(s: str) -> str: return em_symbol(s).lower()
def suffix(s: str) -> str: return s
def dump(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
def sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()
def col(df: pd.DataFrame, names: list[str]) -> str | None:
    upper = {str(c).upper(): str(c) for c in df.columns}
    for n in names:
        if n.upper() in upper: return upper[n.upper()]
    return None
def run(fn, kwargs=None, tries=2):
    started=time.monotonic(); err=None
    for i in range(tries):
        try:
            df=fn(**(kwargs or {}))
            if not isinstance(df,pd.DataFrame): df=pd.DataFrame(df)
            return ("SUCCESS" if not df.empty else "EMPTY",df,i+1,round(time.monotonic()-started,4),None,None)
        except Exception as e:
            err=e
            if i+1<tries: time.sleep(0.8*(i+1))
    return ("ERROR",pd.DataFrame(),tries,round(time.monotonic()-started,4),type(err).__name__,str(err)[:800])
def row(run_id,sample,source,component,adapter,result):
    status,df,attempts,elapsed,etype,emsg=result; fam,rank=META[source]
    return {"run_id":run_id,"symbol":sample["symbol"] if sample else "*","name":sample["name"] if sample else "FULL_MARKET",
      "profile":sample["profile"] if sample else "FULL_MARKET","board":sample["board"] if sample else "FULL_MARKET",
      "source_id":source,"source_family":fam,"source_rank":rank,"adapter":adapter,"component":component,
      "status":status,"attempts":attempts,"row_count":len(df),"column_count":len(df.columns),"elapsed_seconds":elapsed,
      "has_report_date":False,"has_announcement_date":False,"has_revision_signal":False,
      "latest_report_period":None,"earliest_report_period":None,"temporal_fields_present":"",
      "required_field_hits":0,"required_field_total":0,"sample_value_coverage_ratio":None,
      "error_type":etype,"error_message":emsg,"record_quality":"VALID" if status=="SUCCESS" else ("PARTIAL" if status=="EMPTY" else "INVALID"),
      "source_retrieved_at":now().isoformat(timespec="seconds")}
def periods(df: pd.DataFrame, names=("REPORT_DATE","报告日")) -> set[str]:
    c=col(df,list(names))
    if not c:return set()
    return {x.date().isoformat() for x in pd.to_datetime(df[c],errors="coerce").dropna()}
def add_temporal(r,df,report_names,announce_names):
    rc=col(df,report_names); ac=[col(df,[x]) for x in announce_names]; ac=[x for x in ac if x]
    r["has_report_date"]=bool(rc); r["has_announcement_date"]=bool(ac)
    r["temporal_fields_present"]="|".join(([rc] if rc else [])+ac)
    if rc:
        p=pd.to_datetime(df[rc],errors="coerce").dropna()
        if len(p): r["earliest_report_period"]=p.min().date().isoformat(); r["latest_report_period"]=p.max().date().isoformat()
def parse_period(title: str) -> str | None:
    t=str(title).replace(" ","")
    if "摘要" in t or "英文版" in t:return None
    m=re.search(r"(20\d{2})年?",t)
    if not m:return None
    y=int(m.group(1))
    if re.search(r"第一季度报告|一季度报告|第一季报|一季报",t):return f"{y}-03-31"
    if re.search(r"半年度报告|半年报|中期报告",t):return f"{y}-06-30"
    if re.search(r"第三季度报告|三季度报告|第三季报|三季报",t):return f"{y}-09-30"
    if re.search(r"年度报告|年度财务报告|年报",t):return f"{y}-12-31"
    return None
def classify(df,source,sample,title_names,date_names,link_names):
    tc,dc,lc=col(df,title_names),col(df,date_names),col(df,link_names)
    if not tc or not dc:return []
    out=[]
    for _,x in df.iterrows():
        t=str(x.get(tc,"")); p=parse_period(t); d=pd.to_datetime(x.get(dc),errors="coerce")
        if not p or pd.isna(d):continue
        out.append({"symbol":sample["symbol"],"name":sample["name"],"profile":sample["profile"],"board":sample["board"],
          "source_id":source,"report_period_end":p,"announcement_timestamp_raw":d.isoformat(),"announcement_date":d.date().isoformat(),
          "filing_title":t,"filing_link":str(x.get(lc,"")) if lc else None,"is_revision":bool(re.search(r"更正|修订|更新后|补充",t))})
    out.sort(key=lambda z:(z["report_period_end"],z["announcement_timestamp_raw"],z["filing_title"]))
    counts={}
    for x in out: counts[x["report_period_end"]]=counts.get(x["report_period_end"],0)+1; x["revision_sequence"]=counts[x["report_period_end"]]
    return out

def bench_disclosure(sample,cfg,run_id):
    rows=[]; filings=[]; start=cfg["benchmark_window"]["announcement_start_date"]; end=now().strftime("%Y%m%d")
    a=run(ak.stock_zh_a_disclosure_report_cninfo,{"symbol":code(sample["symbol"]),"market":"沪深京","keyword":"报告","category":"","start_date":start,"end_date":end},3)
    r=row(run_id,sample,"CNINFO_OFFICIAL_DISCLOSURE","PERIODIC_AND_REVISION_FILINGS","akshare.stock_zh_a_disclosure_report_cninfo",a)
    if len(a[1]):
        f=classify(a[1],"CNINFO_OFFICIAL_DISCLOSURE",sample,["公告标题"],["公告时间"],["公告链接"]); filings+=f
        r["has_announcement_date"]=bool(col(a[1],["公告时间"])); r["has_revision_signal"]=any(x["is_revision"] for x in f)
        r["required_field_hits"]=sum(bool(col(a[1],[x])) for x in ["代码","公告标题","公告时间","公告链接"]); r["required_field_total"]=4
        r["sample_value_coverage_ratio"]=r["required_field_hits"]/4
    rows.append(r)
    b=run(ak.stock_individual_notice_report,{"security":code(sample["symbol"]),"symbol":"财务报告","begin_date":start,"end_date":end})
    r=row(run_id,sample,"EASTMONEY_NOTICE_FALLBACK","FINANCIAL_REPORT_NOTICES","akshare.stock_individual_notice_report",b)
    if len(b[1]):
        f=classify(b[1],"EASTMONEY_NOTICE_FALLBACK",sample,["公告标题"],["公告日期"],["网址"]); filings+=f
        r["has_announcement_date"]=bool(col(b[1],["公告日期"])); r["has_revision_signal"]=any(x["is_revision"] for x in f)
        r["required_field_hits"]=sum(bool(col(b[1],[x])) for x in ["代码","公告标题","公告日期","网址"]); r["required_field_total"]=4
        r["sample_value_coverage_ratio"]=r["required_field_hits"]/4
    rows.append(r); return rows,filings

def bench_statements(sample,run_id,source):
    rows=[]; sets=[]; ok=0; elapsed=0
    for component,(em_fn,sina_name) in STATEMENTS.items():
        if source=="EASTMONEY_STATEMENTS": fn=getattr(ak,em_fn); kwargs={"symbol":em_symbol(sample["symbol"])}; adapter=f"akshare.{em_fn}"
        else: fn=ak.stock_financial_report_sina; kwargs={"stock":sina_symbol(sample["symbol"]),"symbol":sina_name}; adapter="akshare.stock_financial_report_sina"
        z=run(fn,kwargs); r=row(run_id,sample,source,component,adapter,z)
        if len(z[1]):
            add_temporal(r,z[1],["REPORT_DATE","报告日"],["NOTICE_DATE","UPDATE_DATE","更新日期"])
            sets.append(periods(z[1])); ok+=1
        else: sets.append(set())
        elapsed+=z[3]; rows.append(r)
    common=set.intersection(*sets) if all(sets) else set()
    status="SUCCESS" if ok==3 else ("PARTIAL" if ok else "ERROR")
    z=(status,pd.DataFrame({"report_period_end":sorted(common)}),1,round(elapsed,4),None,None)
    r=row(run_id,sample,source,"THREE_STATEMENT_BUNDLE","bundle",z); r["row_count"]=len(common); r["has_report_date"]=bool(common)
    r["latest_report_period"]=max(common) if common else None; r["earliest_report_period"]=min(common) if common else None
    r["required_field_hits"]=ok; r["required_field_total"]=3; r["sample_value_coverage_ratio"]=ok/3
    r["record_quality"]="VALID" if ok==3 else ("PARTIAL" if ok else "INVALID"); rows.append(r)
    return rows,common

def bench_extended(sample,run_id):
    if not sample.get("extended"):return []
    specs=[
      ("EASTMONEY_FINANCIAL_INDICATORS","REPORT_PERIOD_INDICATORS",ak.stock_financial_analysis_indicator_em,{"symbol":suffix(sample["symbol"]),"indicator":"按报告期"},["REPORT_DATE"],["NOTICE_DATE","UPDATE_DATE"],["REPORT_DATE","EPSJB","PARENTNETPROFIT","ROEJQ","ZCFZL"]),
      ("EASTMONEY_HISTORICAL_VALUATION","HISTORICAL_VALUATION",ak.stock_value_em,{"symbol":code(sample["symbol"])},["数据日期"],[],["数据日期","总市值","流通市值","总股本","PE(TTM)","市净率","市销率"]),
      ("EASTMONEY_DIVIDENDS","DIVIDEND_HISTORY",ak.stock_fhps_detail_em,{"symbol":code(sample["symbol"])},["报告期"],["业绩披露日期","预案公告日","最新公告日期"],["报告期","现金分红-现金分红比例","预案公告日","股权登记日","除权除息日","方案进度"]),
      ("EASTMONEY_SHARE_CAPITAL","SHARE_CAPITAL_HISTORY",ak.stock_zh_a_gbjg_em,{"symbol":suffix(sample["symbol"])},["变更日期"],[],["变更日期","总股本","已流通股份","已上市流通A股","变动原因"])]
    out=[]
    for src,comp,fn,kwargs,rnames,anames,expected in specs:
        z=run(fn,kwargs); r=row(run_id,sample,src,comp,f"akshare.{fn.__name__}",z)
        if len(z[1]):
            add_temporal(r,z[1],rnames,anames); r["required_field_hits"]=sum(bool(col(z[1],[x])) for x in expected)
            r["required_field_total"]=len(expected); r["sample_value_coverage_ratio"]=r["required_field_hits"]/len(expected)
        out.append(r)
    return out

def bench_symbol(sample,cfg,run_id):
    rows,filings=bench_disclosure(sample,cfg,run_id)
    a,ep=bench_statements(sample,run_id,"EASTMONEY_STATEMENTS"); b,sp=bench_statements(sample,run_id,"SINA_STATEMENTS")
    return rows+a+b+bench_extended(sample,run_id),filings,ep,sp

def global_sources(samples,run_id):
    out=[]
    z=run(ak.stock_zh_a_spot_em,tries=3); r=row(run_id,None,"EASTMONEY_CURRENT_VALUATION","FULL_MARKET_CURRENT_VALUATION","akshare.stock_zh_a_spot_em",z)
    if len(z[1]):
        cc=col(z[1],["代码"]); have=set(z[1][cc].astype(str).str.zfill(6)) if cc else set(); want={code(x["symbol"]) for x in samples}
        expected=["代码","最新价","市盈率-动态","市净率","总市值","流通市值"]; r["required_field_hits"]=sum(bool(col(z[1],[x])) for x in expected)
        r["required_field_total"]=len(expected); r["sample_value_coverage_ratio"]=len(want&have)/len(want)
    out.append(r)
    z=run(ak.stock_repurchase_em,tries=3); r=row(run_id,None,"EASTMONEY_BUYBACKS","FULL_MARKET_BUYBACK_EVENTS","akshare.stock_repurchase_em",z)
    if len(z[1]):
        expected=["股票代码","计划回购金额区间-下限","已回购股份数量","已回购金额","最新公告日期"]
        r["required_field_hits"]=sum(bool(col(z[1],[x])) for x in expected); r["required_field_total"]=len(expected)
        r["sample_value_coverage_ratio"]=r["required_field_hits"]/len(expected); r["has_announcement_date"]=bool(col(z[1],["最新公告日期"]))
    out.append(r); return out

def calendar(run_id):
    z=run(ak.tool_trade_date_hist_sina,tries=3); r=row(run_id,None,"SINA_TRADING_CALENDAR","TRADING_CALENDAR","akshare.tool_trade_date_hist_sina",z); dates=[]
    if len(z[1]):
        c=col(z[1],["trade_date","日期"])
        if c: dates=sorted({x.date() for x in pd.to_datetime(z[1][c],errors="coerce").dropna()}); r["has_report_date"]=bool(dates)
    if not dates:r["record_quality"]="INVALID"
    return dates,r
def next_open(d,dates,open_time):
    i=bisect.bisect_right(dates,d); return None if i>=len(dates) else f"{dates[i].isoformat()}T{open_time}+08:00"

def pit_table(samples,filings,period_map,dates,cfg,run_id):
    out=[]; minp=cfg["benchmark_window"]["minimum_report_period_end"]; om=cfg["availability_policy"]["market_open_time"]; sm={x["symbol"]:x for x in samples}
    official=[x for x in filings if x["source_id"]=="CNINFO_OFFICIAL_DISCLOSURE"]; fallback=[x for x in filings if x["source_id"]=="EASTMONEY_NOTICE_FALLBACK"]
    for sym,ps in period_map.items():
        for p in sorted(x for x in ps if x>=minp):
            a=[x for x in official if x["symbol"]==sym and x["report_period_end"]==p]; b=[x for x in fallback if x["symbol"]==sym and x["report_period_end"]==p]; chosen=a or b
            if not chosen:
                s=sm[sym]; out.append({"run_id":run_id,"symbol":sym,"name":s["name"],"profile":s["profile"],"board":s["board"],"report_period_end":p,
                 "filing_source_id":None,"filing_title":None,"filing_link":None,"announcement_date":None,"announcement_timestamp_raw":None,
                 "availability_rule":"NEXT_TRADING_SESSION_OPEN","available_from":None,"revision_sequence":None,"match_status":"UNMATCHED",
                 "point_in_time_grade":"BLOCKED","future_information_flag":False}); continue
            for x in chosen:
                av=next_open(date.fromisoformat(x["announcement_date"]),dates,om); future=False
                if av:
                    at=pd.Timestamp(x["announcement_timestamp_raw"]); at=at.tz_localize("Asia/Shanghai") if at.tzinfo is None else at
                    future=pd.Timestamp(av)<=at
                out.append({"run_id":run_id,"symbol":sym,"name":x["name"],"profile":x["profile"],"board":x["board"],"report_period_end":p,
                 "filing_source_id":x["source_id"],"filing_title":x["filing_title"],"filing_link":x["filing_link"],"announcement_date":x["announcement_date"],
                 "announcement_timestamp_raw":x["announcement_timestamp_raw"],"availability_rule":"NEXT_TRADING_SESSION_OPEN","available_from":av,
                 "revision_sequence":x["revision_sequence"],"match_status":"OFFICIAL_MATCHED" if a else "FALLBACK_MATCHED",
                 "point_in_time_grade":"DECISION_GRADE_DAILY" if a and av else ("DEGRADED_FALLBACK" if av else "BLOCKED"),"future_information_flag":future})
    return pd.DataFrame(out)

def summary(rows):
    out=[]
    for src,g in rows.groupby("source_id"):
        c=g[g["component"]!="THREE_STATEMENT_BUNDLE"]; ok=c["status"].eq("SUCCESS"); elapsed=pd.to_numeric(c["elapsed_seconds"],errors="coerce")
        out.append({"source_id":src,"source_family":g["source_family"].iloc[0],"source_rank":g["source_rank"].iloc[0],"call_count":len(c),
         "success_calls":int(ok.sum()),"empty_calls":int(c["status"].eq("EMPTY").sum()),"error_calls":int(c["status"].eq("ERROR").sum()),
         "success_ratio":round(float(ok.mean()) if len(c) else 0,6),"symbols_attempted":int(c.loc[c["symbol"]!="*","symbol"].nunique()),
         "symbols_successful":int(c.loc[(c["symbol"]!="*")&ok,"symbol"].nunique()),"profiles_successful":"|".join(sorted(c.loc[ok,"profile"].astype(str).unique())),
         "boards_successful":"|".join(sorted(c.loc[ok,"board"].astype(str).unique())),"median_elapsed_seconds":round(float(elapsed.median()),4) if len(elapsed) else None,
         "p95_elapsed_seconds":round(float(elapsed.quantile(.95)),4) if len(elapsed) else None})
    return pd.DataFrame(out).sort_values("source_id")
def coverage(rows):
    out=[]; s=rows[rows["symbol"]!="*"]
    for src,sg in s.groupby("source_id"):
        for dim in ["profile","board"]:
            for val,g in sg.groupby(dim):
                if src in {"EASTMONEY_STATEMENTS","SINA_STATEMENTS"}:g=g[g["component"]=="THREE_STATEMENT_BUNDLE"]
                ok=g["status"].eq("SUCCESS"); out.append({"source_id":src,"dimension_type":dim.upper(),"dimension_value":val,"attempted":len(g),
                 "successful":int(ok.sum()),"success_ratio":round(float(ok.mean()) if len(g) else 0,6),"rows_returned":int(g["row_count"].sum())})
    return pd.DataFrame(out).sort_values(["source_id","dimension_type","dimension_value"])
def source_ratio(s,src):
    x=s[s["source_id"]==src]; return 0 if x.empty else float(x["success_ratio"].iloc[0])
def bundle_ratio(rows,src):
    x=rows[(rows["source_id"]==src)&(rows["component"]=="THREE_STATEMENT_BUNDLE")]; return float(x["status"].eq("SUCCESS").mean()) if len(x) else 0
def decide(cfg,rows,summ,pit,dates,run_id):
    p=cfg["acceptance_policy"]; off=source_ratio(summ,"CNINFO_OFFICIAL_DISCLOSURE"); notice=source_ratio(summ,"EASTMONEY_NOTICE_FALLBACK")
    em=bundle_ratio(rows,"EASTMONEY_STATEMENTS"); si=bundle_ratio(rows,"SINA_STATEMENTS")
    pp=pit["match_status"].eq("OFFICIAL_MATCHED").mean() if len(pit) else 0; future=int(pit["future_information_flag"].fillna(False).sum()) if len(pit) else 0
    vr=rows[rows["source_id"]=="EASTMONEY_CURRENT_VALUATION"]; vc=float(vr["sample_value_coverage_ratio"].iloc[0]) if len(vr) and pd.notna(vr["sample_value_coverage_ratio"].iloc[0]) else 0
    profiles={k:round(float(g["status"].eq("SUCCESS").mean()),6) for k,g in rows[(rows["source_id"]=="EASTMONEY_STATEMENTS")&(rows["component"]=="THREE_STATEMENT_BUNDLE")].groupby("profile")}
    ext={x:source_ratio(summ,x) for x in ["EASTMONEY_FINANCIAL_INDICATORS","EASTMONEY_HISTORICAL_VALUATION","EASTMONEY_SHARE_CAPITAL","EASTMONEY_DIVIDENDS"]}
    bb=source_ratio(summ,"EASTMONEY_BUYBACKS"); hard=[]
    if not dates:hard.append("TRADING_CALENDAR_UNAVAILABLE")
    if off<p["minimum_official_disclosure_call_success_ratio"]:hard.append("OFFICIAL_DISCLOSURE_ROUTE_BELOW_THRESHOLD")
    if em<p["minimum_statement_bundle_success_ratio"]:hard.append("PRIMARY_STATEMENT_BUNDLE_BELOW_THRESHOLD")
    if si<p["minimum_statement_fallback_bundle_success_ratio"]:hard.append("STATEMENT_FALLBACK_BUNDLE_BELOW_THRESHOLD")
    if pp<p["minimum_point_in_time_match_ratio"]:hard.append("POINT_IN_TIME_OFFICIAL_MATCH_BELOW_THRESHOLD")
    if vc<p["minimum_current_valuation_sample_coverage"]:hard.append("CURRENT_VALUATION_SAMPLE_COVERAGE_BELOW_THRESHOLD")
    missing=[x for x in cfg["sample_design"]["minimum_profiles"] if profiles.get(x,0)<=0]
    if missing:hard.append("PRIMARY_STATEMENT_PROFILE_GAP:"+",".join(missing))
    if future:hard.append(f"POINT_IN_TIME_FUTURE_INFORMATION:{future}")
    decisions=[
      {"source_id":"CNINFO_OFFICIAL_DISCLOSURE","decision":"PRIMARY_ANNOUNCEMENT_AND_REVISION_METADATA" if off>=p["minimum_official_disclosure_call_success_ratio"] and pp>=p["minimum_point_in_time_match_ratio"] else "REMEDIATION_REQUIRED","success_ratio":round(off,6),"point_in_time_match_ratio":round(float(pp),6)},
      {"source_id":"EASTMONEY_NOTICE_FALLBACK","decision":"DEGRADED_METADATA_FALLBACK_ONLY" if notice>=p["minimum_official_disclosure_call_success_ratio"] else "NOT_RELIABLE_AS_FALLBACK","success_ratio":round(notice,6)},
      {"source_id":"EASTMONEY_STATEMENTS","decision":"PRIMARY_STRUCTURED_THREE_STATEMENT_SOURCE" if em>=p["minimum_statement_bundle_success_ratio"] else "REMEDIATION_REQUIRED","bundle_success_ratio":round(em,6),"profile_coverage":profiles},
      {"source_id":"SINA_STATEMENTS","decision":"FALLBACK_STRUCTURED_THREE_STATEMENT_SOURCE" if si>=p["minimum_statement_fallback_bundle_success_ratio"] else "NOT_RELIABLE_AS_FALLBACK","bundle_success_ratio":round(si,6)},
      {"source_id":"EASTMONEY_CURRENT_VALUATION","decision":"PRIMARY_CURRENT_MARKET_CAP_PE_PB_SOURCE" if vc>=p["minimum_current_valuation_sample_coverage"] else "REMEDIATION_REQUIRED","sample_coverage_ratio":round(vc,6),"denominator_policy":"RAW_ONLY; FMDL3D_RECOMPUTES_VALIDITY"}]
    for src,label in [("EASTMONEY_FINANCIAL_INDICATORS","CROSS_CHECK_AND_FACTOR_SUPPORT_ONLY"),("EASTMONEY_HISTORICAL_VALUATION","CONDITIONAL_HISTORICAL_VALUATION_SOURCE"),("EASTMONEY_SHARE_CAPITAL","PRIMARY_HISTORICAL_SHARE_CAPITAL_SOURCE"),("EASTMONEY_DIVIDENDS","PRIMARY_DIVIDEND_EVENT_SOURCE")]:
        decisions.append({"source_id":src,"decision":label if ext[src]>=p["minimum_extended_source_success_ratio"] else "SUPPORT_ONLY_OR_REMEDIATION_REQUIRED","success_ratio":round(ext[src],6)})
    decisions.append({"source_id":"EASTMONEY_BUYBACKS","decision":"PRIMARY_BUYBACK_EVENT_SOURCE" if bb>=1 else "DEGRADED_OR_REMEDIATION_REQUIRED","success_ratio":round(bb,6)})
    return {"decision_version":"1.0.0","run_id":run_id,"generated_at":now().isoformat(timespec="seconds"),"program_id":"FMDL-3A",
      "status":"FMDL3A_ACCEPTED_SOURCE_ROUTE_AND_COVERAGE_GATES_FROZEN" if not hard else "FMDL3A_REMEDIATION_REQUIRED",
      "exit_gate":"SOURCE_ROUTE_AND_NUMERIC_COVERAGE_GATES_FROZEN" if not hard else "NOT_MET",
      "measured_metrics":{"sample_symbol_count":len(cfg["sample_design"]["symbols"]),"official_disclosure_call_success_ratio":round(off,6),
       "fallback_notice_call_success_ratio":round(notice,6),"primary_statement_bundle_success_ratio":round(em,6),"fallback_statement_bundle_success_ratio":round(si,6),
       "official_point_in_time_match_ratio":round(float(pp),6),"current_valuation_sample_coverage_ratio":round(vc,6),"future_information_count":future,
       "primary_statement_profile_coverage":profiles,"extended_source_success_ratios":ext,"buyback_source_success_ratio":round(bb,6)},
      "frozen_point_in_time_contract":{"resolution":"DAILY","report_period_end_is_not_availability":True,"primary_availability_source":"CNINFO_OFFICIAL_DISCLOSURE",
       "date_only_rule":"NEXT_TRADING_SESSION_OPEN","timestamp_rule":"NEXT_TRADING_SESSION_OPEN","market_open_time":cfg["availability_policy"]["market_open_time"],
       "calendar_source":cfg["availability_policy"]["calendar_source"],"restatement_rule":"NEW_REVISION_SEQUENCE; ZERO_SILENT_OVERWRITE","fallback_notice_grade":"DEGRADED_METADATA_ONLY"},
      "source_decisions":decisions,"hard_failures":hard,"controlled_limitations":[f"{k}_BELOW_THRESHOLD:{v:.4f}" for k,v in ext.items() if v<p["minimum_extended_source_success_ratio"]],
      "authority":cfg["authority"],"trade_authority":cfg["trade_authority"],"next_phase":"FMDL-3B" if not hard else "FMDL-3A-R"}

def write_outputs(cfg,run_id,rows,summ,cov,pit,decision):
    root=ROOT/cfg["publication"]["candidate_root"]; shutil.rmtree(root,ignore_errors=True); root.mkdir(parents=True)
    files={"FMDL3A_BENCHMARK_ROWS.csv":rows,"FMDL3A_SOURCE_SUMMARY.csv":summ,"FMDL3A_COVERAGE_MAP.csv":cov,"FMDL3A_POINT_IN_TIME_EVIDENCE.csv":pit,
      "FMDL3_SOURCE_INDEX.csv":pd.DataFrame(decision["source_decisions"])}
    for n,df in files.items(): df.assign(run_id=run_id,authority=decision["authority"],trade_authority=decision["trade_authority"]).to_csv(root/n,index=False)
    dump(root/"FMDL3A_SOURCE_DECISION.json",decision)
    manifest={"manifest_version":"1.0.0","run_id":run_id,"generated_at":now().isoformat(timespec="seconds"),"program_id":"FMDL-3A","status":"CANDIDATE",
      "decision_status":decision["status"],"files":{},"authority":decision["authority"],"trade_authority":decision["trade_authority"]}
    for p in root.iterdir(): manifest["files"][p.name]={"path":str(p.relative_to(ROOT)),"size_bytes":p.stat().st_size,"sha256":sha(p)}
    dump(root/"FMDL3A_MANIFEST.json",manifest)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--config",type=Path,default=CFG); ap.add_argument("--workers",type=int,default=3); a=ap.parse_args()
    cfg=json.loads(a.config.read_text(encoding="utf-8")); run_id=f"FMDL3A_{now().strftime('%Y%m%dT%H%M%S%z')}"; samples=cfg["sample_design"]["symbols"]
    dates,cr=calendar(run_id); allrows=[cr]+global_sources(samples,run_id); filings=[]; ep={}
    with ThreadPoolExecutor(max_workers=max(1,a.workers)) as ex:
        fut={ex.submit(bench_symbol,s,cfg,run_id):s for s in samples}
        for f in as_completed(fut):
            s=fut[f]
            try:r,ff,e,_=f.result(); allrows+=r; filings+=ff; ep[s["symbol"]]=e
            except Exception as exc:
                z=("ERROR",pd.DataFrame(),1,0,type(exc).__name__,str(exc)); allrows.append(row(run_id,s,"EASTMONEY_STATEMENTS","SYMBOL_BENCHMARK_UNHANDLED_FAILURE","bench_symbol",z)); ep[s["symbol"]]=set()
    rows=pd.DataFrame(allrows).sort_values(["source_id","symbol","component"]); summ=summary(rows); cov=coverage(rows); pit=pit_table(samples,filings,ep,dates,cfg,run_id)
    decision=decide(cfg,rows,summ,pit,dates,run_id); write_outputs(cfg,run_id,rows,summ,cov,pit,decision); print(json.dumps(decision,ensure_ascii=False,indent=2))
    return 0 if not decision["hard_failures"] else 2
if __name__=="__main__": raise SystemExit(main())
