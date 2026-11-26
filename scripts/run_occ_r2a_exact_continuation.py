"""Reuse accepted PIT share/factor assets for a full-universe exact-formula candidate.

No provider requests, no authoritative promotion. Until financial AND share event
catch-up is proven, fresh prices do not imply fresh denominators. Keep every
current market security, including unpriced or new symbols, explicitly quarantined.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
from pathlib import Path

import pandas as pd

from scripts import fmdl3db_core as cap
from scripts import fmdl3dc_core as val

ROOT = Path(__file__).resolve().parents[1]


def read_blob(ref, path, expected=None):
    payload = subprocess.check_output(["git", "show", f"{ref}:{path}"], cwd=ROOT)
    if expected is not None and hashlib.sha256(payload).hexdigest() != expected:
        raise ValueError("INPUT_HASH_MISMATCH:" + path)
    return payload


def read_json(ref, path):
    return json.loads(read_blob(ref, path))


def manifest_map(ref, path, expected_release):
    data = read_json(ref, path)
    if data["release_id"] != expected_release or data["trade_authority"] != "NONE":
        raise ValueError("MANIFEST_RELEASE_MISMATCH:" + path)
    return {row["path"]: row["sha256"] for row in data["files"]}


def parquet(ref, path, expected):
    return pd.read_parquet(io.BytesIO(read_blob(ref, path, expected)))


def csv(ref, path, expected):
    return pd.read_csv(io.BytesIO(read_blob(ref, path, expected)), dtype={"symbol": str}, encoding="utf-8-sig")


def build_capitalization(universe, snapshot, ledger, release, cfg):
    date = release["as_of_date"]
    for frame in (universe, snapshot):
        if frame["symbol"].duplicated().any() or set(frame["as_of_date"].astype(str)) != {date}:
            raise ValueError("MARKET_MEMBERSHIP_OR_DATE_MISMATCH")
    if set(universe.symbol) != set(snapshot.symbol):
        raise ValueError("UNIVERSE_SNAPSHOT_MISMATCH")
    if ledger.duplicated(["symbol", "source_effective_date", "source_row_hash"]).any():
        raise ValueError("DUPLICATE_LEDGER_KEY")
    if set(ledger.trade_authority) != {"NONE"}:
        raise ValueError("LEDGER_AUTHORITY_INVALID")
    prior = ledger.loc[ledger.source_effective_date.astype(str).le(date)].copy()
    prior = prior.sort_values(["symbol", "source_effective_date", "source_row_hash"]).drop_duplicates("symbol", keep="last").set_index("symbol")
    indexed = snapshot.set_index("symbol")
    rows = []
    for security in universe.to_dict("records"):
        symbol = security["symbol"]
        quote = indexed.loc[symbol]
        close = pd.to_numeric(pd.Series([quote["close"]]), errors="coerce").iloc[0]
        # Unresolved quote must not become a confirmed suspension.
        price_ok = (pd.notna(close) and close > 0 and quote["record_quality"] in {"VALID","PARTIAL"}
                    and quote["data_status"] == "TRADED" and pd.notna(quote["row_hash"]))
        share = prior.loc[symbol] if symbol in prior.index else None
        share_ok = (share is not None and pd.notna(share["total_shares"]) and pd.notna(share["float_a_shares"])
                    and 0 < share["float_a_shares"] <= share["total_shares"])
        state = "VALID" if price_ok and share_ok else ("PRICE_UNAVAILABLE" if not price_ok else "NO_EFFECTIVE_SHARE_ROW")
        row = {
            "symbol": symbol, "name": security["name"], "exchange": security["exchange"], "board": security["board"],
            "price_as_of_date": date, "price_source_timestamp": quote.get("source_timestamp"),
            "close": float(close) if price_ok else None,
            "price_row_hash": quote["row_hash"] if price_ok else None,
            "price_record_quality": quote["record_quality"], "price_data_status": quote["data_status"],
            "share_effective_date": share["source_effective_date"] if share_ok else None,
            "total_shares": float(share["total_shares"]) if share_ok else None,
            "float_a_shares": float(share["float_a_shares"]) if share_ok else None,
            "share_source_row_hash": share["source_row_hash"] if share_ok else None,
            "share_source_id": share["source_id"] if share_ok else None,
            "capitalization_state": state,
            "state_reason": "PIT_ACCEPTED_LEDGER_ONLY" if state == "VALID" else
                ("NON_POSITIVE_OR_MISSING_CLOSE" if not price_ok else "NO_PIT_EFFECTIVE_SHARE_ROW"),
            "total_market_cap_cny": float(close * share["total_shares"]) if state == "VALID" else None,
            "float_market_cap_cny": float(close * share["float_a_shares"]) if state == "VALID" else None,
            "source_release_id": release["run_id"],
            "source_universe_version": release["dataset_versions"]["a_share_universe"],
            "source_snapshot_version": release["dataset_versions"]["daily_market_snapshot"],
            "universe_row_hash": security.get("row_hash"),
            "authority": cap.AUTHORITY, "trade_authority": "NONE",
        }
        row["lineage_id"] = cap.stable_hash({k: row[k] for k in ("symbol","price_as_of_date","price_row_hash","share_effective_date","share_source_row_hash")}|{"contract_version":cfg["contract_version"]})
        rows.append(row)
    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--market-commit", required=True)
    parser.add_argument("--financial-commit", required=True)
    parser.add_argument("--exact-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    M,F,V = args.market_commit,args.financial_commit,args.exact_commit
    mr = read_json(M,"outputs/current/CURRENT_RELEASE.json")
    fctx = read_json(F,"outputs/occ_r2/financial/current/FINANCIAL_CONTEXT_RELEASE.json")
    vctx = read_json(V,"outputs/occ_r2/valuation/current/FINANCIAL_VALUATION_CONTEXT_RELEASE.json")
    croot = "outputs/capitalization/current/"
    froot = "outputs/financial_factors/engine/current/"
    cr = read_json(V,croot+"FMDL3DB_RELEASE.json")
    fr = read_json(F,froot+"FMDL3CB_RELEASE.json")
    if not (fctx["status"]==vctx["status"]=="PASS"
        and vctx["qc_status"]=="PASS_EXACT_VALUATION_REBUILT"
        and vctx["source_lineage"]["financial_source_commit"]==F
        and fctx["releases"]["financial_factor_release_id"]==fr["release_id"]==vctx["releases"]["financial_factor_release_id"]
        and vctx["releases"]["capitalization_release_id"]==cr["release_id"]
        and mr["status"] in {"PUBLISHED","PUBLISHED_WITH_WARNINGS"} and mr["hard_failures"]==[]
        and fctx["market_as_of_date"]<=vctx["market_as_of_date"]<=mr["as_of_date"]):
        raise ValueError("ACCEPTED_SOURCE_LINEAGE_OR_PIT_MISMATCH")
    cm = manifest_map(V,croot+"FMDL3DB_MANIFEST.json",cr["release_id"])
    fm = manifest_map(F,froot+"FMDL3CB_MANIFEST.json",fr["release_id"])
    ledger = parquet(V,cr["effective_share_ledger_path"],cm["FMDL3DB_EFFECTIVE_SHARE_LEDGER.parquet"])
    if len(ledger)!=cr["metrics"]["effective_share_ledger_row_count"]:
        raise ValueError("LEDGER_COUNT_MISMATCH")
    profiles = csv(F,fr["sector_profile_path"],fm[Path(fr["sector_profile_path"]).name])
    derived = pd.concat([parquet(F,p,fm["derived_inputs/"+Path(p).name]) for p in fr["derived_input_shards"]],ignore_index=True)
    if profiles.symbol.duplicated().any():
        raise ValueError("DUPLICATE_PROFILE")
    u,s = [csv(M,mr["current_files"][key]["path"],mr["current_files"][key]["sha256"]) for key in ("a_share_universe","daily_market_snapshot")]
    cconfig = json.loads((ROOT/"config/fmdl3db_engine.json").read_text())
    vconfig = json.loads((ROOT/"config/fmdl3dc_engine.json").read_text())
    reg = pd.read_csv(ROOT/"config/fmdl3da_valuation_metric_registry.csv",encoding="utf-8-sig")
    current = build_capitalization(u,s,ledger,mr,cconfig)
    scope = cap.capitalization_coverage_population(u,s,current)
    eligible = current.loc[scope["eligible_mask"]]
    valid = eligible.capitalization_state.isin(cap.VALID_CAP_STATES)
    price_coverage = float(eligible.close.notna().mean())
    cap_coverage = float(valid.mean())
    detail,calc = val.build_outputs(current,profiles,derived,reg,vconfig)
    date = mr["as_of_date"]
    cutoff = pd.Timestamp(date+" 15:00:00",tz="Asia/Shanghai").tz_convert("UTC")
    available = pd.to_datetime(detail.denominator_available_from,utc=True,errors="coerce")
    share_future = current.share_effective_date.dropna().astype(str).gt(date)
    assert not share_future.any() and not (available>cutoff).any()
    assert not calc.symbol.duplicated().any() and not detail.duplicated(["symbol","metric_id"]).any()
    assert set(calc.symbol)==set(u.symbol)
    assert set(calc.market_as_of_date)=={date}
    assert len(detail)==len(u)*len(vconfig["engine"]["expected_valuation_metric_ids"])
    assert set(calc.trade_authority)==set(detail.trade_authority)=={"NONE"}
    # Engine values are exactly calculated on accepted inputs, but evidence for
    # intervening share/financial revisions is not yet complete. No production
    # decision-grade claims or Current advancement from this candidate.
    numeric_valid = {str(k):int(v) for k,v in detail.loc[detail.decision_grade].groupby("metric_id").size().items()}
    detail["decision_grade"] = False
    calc["decision_grade_metric_count"] = 0
    detail["denominator_freshness"] = "LKG_EVENT_CLOSURE_UNPROVEN"
    calc["denominator_freshness"] = "LKG_EVENT_CLOSURE_UNPROVEN"
    # Hash the final rows after downgrade; retain underlying engine lineage separately.
    calc["row_hash"] = calc.apply(lambda r:val.stable_hash({k:v for k,v in r.items() if k!="row_hash"}),axis=1)
    decision = {
        "status":"BLOCKED_EVENT_CLOSURE", "production_ready":False, "production_write":False,
        "market_as_of_date":date,"financial_baseline_as_of_date":fctx["market_as_of_date"],
        "share_baseline_as_of_date":vctx["market_as_of_date"],
        "source_commits":{"market":M,"financial":F,"exact":V},
        "universe_rows":len(u),"valuation_rows":len(calc),"metric_rows":len(detail),
        "price_coverage":price_coverage,"capitalization_coverage":cap_coverage,
        "capitalization_99pct_gate":cap_coverage>=vconfig["engine"]["minimum_capitalization_coverage"],
        "price_98pct_gate":price_coverage>=cconfig["acceptance"]["minimum_accepted_price_coverage"],
        "scope_checks":scope["checks"],"formula_valid_metric_counts":numeric_valid,
        "financial_event_completeness":"UNPROVEN","share_event_completeness":"UNPROVEN",
        "decision_grade_count":0,"future_selected_count":0,"orders":0,"trade_authority":"NONE",
    }
    args.output.mkdir(parents=True,exist_ok=True)
    current.to_parquet(args.output/"CAPITALIZATION_CANDIDATE.parquet",index=False)
    detail.to_parquet(args.output/"VALUATION_METRIC_DETAIL_CANDIDATE.parquet",index=False)
    calc.to_parquet(args.output/"VALUATION_CONTEXT_CANDIDATE.parquet",index=False)
    (args.output/"EXACT_CONTINUATION_DECISION.json").write_text(json.dumps(decision,ensure_ascii=False,indent=2)+"\n")
    print("EXACT_CONTINUATION",json.dumps(decision,ensure_ascii=False,sort_keys=True),flush=True)


if __name__=="__main__":
    main()
