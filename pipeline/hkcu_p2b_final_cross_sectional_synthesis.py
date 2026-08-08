#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import akshare as ak
import pandas as pd

PROGRAM_ID = "HKCU-P2B-FINAL"
TRADE_AUTHORITY = "NONE"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def rebuild_upstream(root: Path, work: Path) -> dict[str, Path]:
    py = sys.executable
    dirs = {k: work / k for k in ["p2a", "e1", "s1", "s2", "s3", "s4"]}
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)

    run([py, str(root / "pipeline/hkcu_p2a_build_longlist.py"), "--repo-root", str(root), "--output", str(dirs["p2a"])])
    run([py, str(root / "scripts/validate_hkcu_p2a.py"), "--repo-root", str(root), "--output", str(dirs["p2a"])])

    run([py, str(root / "pipeline/hkcu_p2b_apply_e1_evidence.py"), "--repo-root", str(root), "--output", str(dirs["e1"])])
    run([py, str(root / "scripts/validate_hkcu_p2b_e1.py"), "--output", str(dirs["e1"])])

    run([py, str(root / "pipeline/hkcu_p2b_e2_top20_decision_synthesis.py"), "--repo-root", str(root), "--output", str(dirs["s1"])])
    run([py, str(root / "scripts/validate_hkcu_p2b_e2_top20_decision_synthesis.py"), "--output", str(dirs["s1"])])

    for stage, contract, validator in [
        ("s2", "config/hkcu_p2b_e2_ranks21_40_decision_synthesis_s2_contract.json", "scripts/validate_hkcu_p2b_e2_ranks21_40_decision_synthesis.py"),
        ("s3", "config/hkcu_p2b_e2_ranks41_60_decision_synthesis_s3_contract.json", "scripts/validate_hkcu_p2b_e2_ranks41_60_decision_synthesis.py"),
        ("s4", "config/hkcu_p2b_e2_ranks61_77_decision_synthesis_s4_contract.json", "scripts/validate_hkcu_p2b_e2_ranks61_77_decision_synthesis.py"),
    ]:
        run([py, str(root / "pipeline/hkcu_p2b_e2_window_decision_synthesis.py"), "--repo-root", str(root), "--contract", str(root / contract), "--output", str(dirs[stage])])
        run([py, str(root / validator), "--output", str(dirs[stage])])
    return dirs


def normalize_direction(v: Any) -> str:
    s = str(v).strip().upper()
    if "MIXED" in s:
        return "MIXED"
    if "NEGATIVE" in s:
        return "NEGATIVE"
    if "POSITIVE" in s:
        return "POSITIVE"
    if s in {"NEUTRAL", "UNKNOWN", "", "NAN", "NONE"}:
        return "NEUTRAL_OR_UNKNOWN"
    return "NEUTRAL_OR_UNKNOWN"


def as_bool(v: Any) -> bool:
    return str(v).strip().lower() == "true"


def retry(fn, attempts: int = 4, delay: float = 2.0):
    last = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as exc:  # network/API boundary
            last = exc
            if i + 1 < attempts:
                time.sleep(delay * (i + 1))
    raise RuntimeError(f"RETRY_EXHAUSTED:{last}")


def get_h_close(code: str, date_yyyymmdd: str) -> float:
    def fetch():
        return ak.stock_hk_hist(symbol=str(code).zfill(5), period="daily", start_date=date_yyyymmdd, end_date=date_yyyymmdd, adjust="")
    df = retry(fetch)
    if df is None or df.empty:
        raise RuntimeError(f"HK_PRICE_EMPTY:{code}:{date_yyyymmdd}")
    date_col = next((c for c in ["日期", "date", "Date"] if c in df.columns), None)
    close_col = next((c for c in ["收盘", "close", "Close"] if c in df.columns), None)
    if date_col is None or close_col is None:
        raise RuntimeError(f"HK_PRICE_SCHEMA:{code}:{list(df.columns)}")
    target = pd.Timestamp(date_yyyymmdd)
    dates = pd.to_datetime(df[date_col], errors="coerce")
    rows = df.loc[dates.eq(target)]
    if len(rows) != 1:
        raise RuntimeError(f"HK_PRICE_DATE_MISMATCH:{code}:{date_yyyymmdd}:{len(rows)}")
    value = pd.to_numeric(rows.iloc[0][close_col], errors="coerce")
    if pd.isna(value) or float(value) <= 0:
        raise RuntimeError(f"HK_PRICE_INVALID:{code}:{value}")
    return float(value)


def get_cny_per_hkd(date_iso: str) -> float:
    df = retry(ak.currency_boc_safe)
    if df is None or df.empty:
        raise RuntimeError("SAFE_FX_EMPTY")
    date_col = next((c for c in ["日期", "date", "Date"] if c in df.columns), None)
    hkd_col = next((c for c in df.columns if "港元" in str(c) or str(c).strip().upper() == "HKD"), None)
    if date_col is None or hkd_col is None:
        raise RuntimeError(f"SAFE_FX_SCHEMA:{list(df.columns)}")
    dates = pd.to_datetime(df[date_col], errors="coerce")
    rows = df.loc[dates.eq(pd.Timestamp(date_iso))]
    if len(rows) != 1:
        raise RuntimeError(f"SAFE_FX_DATE_MISMATCH:{date_iso}:{len(rows)}")
    raw = pd.to_numeric(rows.iloc[0][hkd_col], errors="coerce")
    if pd.isna(raw) or float(raw) <= 0:
        raise RuntimeError(f"SAFE_FX_INVALID:{raw}")
    # SAFE central parity is conventionally RMB per 100 HKD.
    return float(raw) / 100.0


def build_ah_relative_value(root: Path, contract: dict[str, Any], p2a: pd.DataFrame) -> pd.DataFrame:
    policy = contract["cross_section_policy"]
    date_iso = policy["ah_price_date"]
    date_compact = date_iso.replace("-", "")
    ah = pd.read_csv(root / contract["authoritative_inputs"]["ah_pair_registry"], dtype=str, keep_default_na=False)
    ah = ah[ah["pair_status"].eq("TRUE_AH_PAIR")].copy()
    if len(ah) != int(contract["expected_counts"]["true_ah_pair_count"]):
        raise RuntimeError(f"AH_TRUE_PAIR_COUNT:{len(ah)}")

    snap = pd.read_csv(root / contract["authoritative_inputs"]["a_share_snapshot"], dtype={"symbol": str}, keep_default_na=False)
    if "symbol" not in snap.columns or "close" not in snap.columns:
        raise RuntimeError("A_SNAPSHOT_SCHEMA")
    manifest = read_json(root / contract["authoritative_inputs"]["a_share_snapshot_manifest"])
    if str(manifest.get("as_of")) != date_iso:
        raise RuntimeError(f"A_SNAPSHOT_DATE:{manifest.get('as_of')}")
    a_close = pd.to_numeric(snap.set_index("symbol")["close"], errors="coerce")
    cny_per_hkd = get_cny_per_hkd(policy["ah_fx_date"])

    p2a_names = p2a.set_index("security_id")["security_name"].to_dict()
    rows = []
    for r in ah.itertuples(index=False):
        a_symbol = f"{r.a_code}.{r.a_exchange}"
        if a_symbol not in a_close.index:
            raise RuntimeError(f"A_PRICE_MISSING:{a_symbol}")
        ac = float(a_close.loc[a_symbol])
        if not pd.notna(ac) or ac <= 0:
            raise RuntimeError(f"A_PRICE_INVALID:{a_symbol}:{ac}")
        hc = get_h_close(r.h_code, date_compact)
        ratio = ac / (hc * cny_per_hkd)
        discount = ratio - 1.0
        direction = "H_DISCOUNT_TO_A" if discount > 1e-12 else ("H_PREMIUM_TO_A" if discount < -1e-12 else "PARITY")
        rows.append({
            "security_id": r.security_id,
            "stock_code_5d": str(r.h_code).zfill(5),
            "security_name": p2a_names.get(r.security_id, ""),
            "a_symbol": a_symbol,
            "a_close_cny": round(ac, 6),
            "a_price_date": date_iso,
            "h_close_hkd": round(hc, 6),
            "h_price_date": date_iso,
            "cny_per_hkd": round(cny_per_hkd, 8),
            "fx_quote_convention": "CNY_PER_HKD_FROM_SAFE_RMB_PER_100_HKD_DIVIDED_BY_100",
            "fx_date": policy["ah_fx_date"],
            "a_over_h_ratio": round(ratio, 8),
            "h_discount_to_a_pct": round(discount * 100.0, 4),
            "relative_value_direction": direction,
            "h_price_source": policy["ah_h_price_source"],
            "a_price_source": policy["ah_a_price_source"],
            "fx_source": policy["ah_fx_source"],
            "alpha_score": pd.NA,
            "formal_candidate_graduation_allowed": False,
            "trade_authority": TRADE_AUTHORITY,
        })
    return pd.DataFrame(rows).sort_values("security_id").reset_index(drop=True)


def build(root: Path, out: Path) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    contract_path = root / "config/hkcu_p2b_final_cross_sectional_synthesis_contract.json"
    contract = read_json(contract_path)
    failures: list[str] = []
    upstream = rebuild_upstream(root, out / "_upstream")

    p2a = pd.read_csv(upstream["p2a"] / "HKCU_P2A_RESEARCH_LONGLIST.csv", dtype={"stock_code_5d": str}, keep_default_na=False)
    p2a = p2a.rename(columns={"overall_rank": "p2a_overall_rank"})
    if "p2a_overall_rank" not in p2a.columns:
        raise RuntimeError("P2A_RANK_COLUMN_MISSING")
    p2a["p2a_overall_rank"] = pd.to_numeric(p2a["p2a_overall_rank"], errors="raise").astype(int)

    e1_dim = pd.read_csv(upstream["e1"] / "HKCU_P2B_E1_DIMENSION_MATRIX.csv", dtype={"stock_code_5d": str}, keep_default_na=False)
    e1_tx = e1_dim[e1_dim["research_dimension"].eq("TRANSACTION_COST_TAX")][["security_id", "evidence_status", "evidence_count"]].copy()
    e1_tx = e1_tx.rename(columns={"evidence_status": "transaction_tax_evidence_status", "evidence_count": "transaction_tax_evidence_count"})
    e1_ah = pd.read_csv(upstream["e1"] / "HKCU_P2B_E1_AH_PAIR_REGISTRY.csv", dtype=str, keep_default_na=False)
    ah_status = e1_ah[["security_id", "pair_status", "a_code", "a_exchange"]].rename(columns={"pair_status": "ah_pair_status"})

    specs = [
        ("s1", "HKCU_P2B_E2_S1_TOP20_DIMENSION_DECISION_SURFACE.csv", "HKCU_P2B_E2_S1_TOP20_SECURITY_DECISION_SYNTHESIS.csv"),
        ("s2", "HKCU_P2B_E2_S2_RANKS21_40_DIMENSION_DECISION_SURFACE.csv", "HKCU_P2B_E2_S2_RANKS21_40_SECURITY_DECISION_SYNTHESIS.csv"),
        ("s3", "HKCU_P2B_E2_S3_RANKS41_60_DIMENSION_DECISION_SURFACE.csv", "HKCU_P2B_E2_S3_RANKS41_60_SECURITY_DECISION_SYNTHESIS.csv"),
        ("s4", "HKCU_P2B_E2_S4_RANKS61_77_DIMENSION_DECISION_SURFACE.csv", "HKCU_P2B_E2_S4_RANKS61_77_SECURITY_DECISION_SYNTHESIS.csv"),
    ]
    dim_parts, sec_parts = [], []
    for stage, dname, sname in specs:
        d = pd.read_csv(upstream[stage] / dname, dtype={"stock_code_5d": str}, keep_default_na=False)
        s = pd.read_csv(upstream[stage] / sname, dtype={"stock_code_5d": str}, keep_default_na=False)
        d["decision_stage"] = stage.upper()
        s["decision_stage"] = stage.upper()
        dim_parts.append(d)
        sec_parts.append(s)
    dim = pd.concat(dim_parts, ignore_index=True, sort=False)
    upstream_sec = pd.concat(sec_parts, ignore_index=True, sort=False)

    exp = contract["expected_counts"]
    if len(p2a) != int(exp["security_count"]): failures.append(f"P2A_SECURITY_COUNT:{len(p2a)}")
    if len(dim) != int(exp["company_dimension_rows"]): failures.append(f"DIMENSION_ROWS:{len(dim)}")
    if dim.duplicated(["security_id", "research_dimension"]).any(): failures.append("DUPLICATE_DIMENSION")
    if len(upstream_sec) != int(exp["security_count"]) or upstream_sec["security_id"].duplicated().any(): failures.append("UPSTREAM_SECURITY_UNION")
    if set(p2a["security_id"]) != set(upstream_sec["security_id"]): failures.append("SECURITY_SET_MISMATCH")
    if sorted(p2a["p2a_overall_rank"].tolist()) != list(range(1, 78)): failures.append("P2A_RANK_SET")

    blocked_ids = set(exp["blocked_security_ids"])
    upstream_blocked = set(upstream_sec.loc[upstream_sec["decision_state"].eq("HOLD_RETAINED_INVESTMENT_BLOCKER"), "security_id"])
    if upstream_blocked != blocked_ids: failures.append("BLOCKER_SET_MISMATCH")

    if len(e1_tx) != int(exp["transaction_tax_complete_count"]) or not e1_tx["transaction_tax_evidence_status"].eq("EVIDENCE_COMPLETE").all():
        failures.append("TRANSACTION_TAX_NOT_COMPLETE")

    # Descriptive evidence balance only; never used for ranking or graduation.
    dim["direction_bucket"] = dim["final_direction"].map(normalize_direction)
    counts = dim.pivot_table(index="security_id", columns="direction_bucket", values="research_dimension", aggfunc="count", fill_value=0)
    for c in ["POSITIVE", "NEGATIVE", "MIXED", "NEUTRAL_OR_UNKNOWN"]:
        if c not in counts.columns: counts[c] = 0
    counts = counts[["POSITIVE", "NEGATIVE", "MIXED", "NEUTRAL_OR_UNKNOWN"]].reset_index()
    counts = counts.rename(columns={
        "POSITIVE": "positive_dimension_count", "NEGATIVE": "negative_dimension_count",
        "MIXED": "mixed_dimension_count", "NEUTRAL_OR_UNKNOWN": "neutral_unknown_dimension_count",
    })

    base_cols = [c for c in [
        "p2a_overall_rank", "security_id", "stock_code_5d", "security_name", "primary_sleeve", "sleeves", "sleeve_count",
        "aggregate_score", "source_model", "source_layer", "close", "price_date", "quote_currency",
        "return_20d", "return_60d", "return_120d", "volatility_60d", "max_drawdown_120d",
        "valuation_status", "fundamentals_status", "growth_status", "dividend_status"
    ] if c in p2a.columns]
    sec = p2a[base_cols].copy()
    sec = sec.merge(counts, on="security_id", how="left", validate="one_to_one")
    sec = sec.merge(e1_tx, on="security_id", how="left", validate="one_to_one")
    sec = sec.merge(ah_status, on="security_id", how="left", validate="one_to_one")
    sec["ah_pair_status"] = sec["ah_pair_status"].replace("", pd.NA).fillna("NOT_APPLICABLE_NO_CONFIRMED_PAIR")
    sec["final_p2b_state"] = sec["security_id"].map(lambda x: "HOLD_RETAINED_INVESTMENT_BLOCKER" if x in blocked_ids else "READY_FOR_P3_CONTRACT_EVALUATION_WITH_CONFIDENCE_CAP")
    sec["retained_blocker"] = sec["security_id"].isin(blocked_ids)
    sec["evidence_balance"] = sec.apply(
        lambda r: "MIXED" if r["mixed_dimension_count"] > 0 or (r["positive_dimension_count"] > 0 and r["negative_dimension_count"] > 0)
        else ("POSITIVE_SKEW" if r["positive_dimension_count"] > r["negative_dimension_count"]
              else ("NEGATIVE_SKEW" if r["negative_dimension_count"] > r["positive_dimension_count"] else "NEUTRAL_OR_UNRESOLVED")), axis=1)
    sec["p2a_rank_preserved_not_rescored"] = True
    sec["alpha_score"] = pd.NA
    sec["formal_candidate_graduation_allowed"] = False
    sec["trade_authority"] = TRADE_AUTHORITY
    sec = sec.sort_values("p2a_overall_rank").reset_index(drop=True)

    ah_rel = build_ah_relative_value(root, contract, p2a)
    if len(ah_rel) != int(exp["ah_numeric_completed_count"]): failures.append(f"AH_NUMERIC_COUNT:{len(ah_rel)}")
    if ah_rel[["a_close_cny", "h_close_hkd", "cny_per_hkd"]].isna().any().any(): failures.append("AH_NUMERIC_MISSING")
    ah_map = ah_rel.set_index("security_id")["h_discount_to_a_pct"].to_dict()
    sec["h_discount_to_a_pct"] = sec["security_id"].map(ah_map)
    dir_map = ah_rel.set_index("security_id")["relative_value_direction"].to_dict()
    sec["ah_relative_value_direction"] = sec["security_id"].map(dir_map).fillna("NOT_APPLICABLE")

    advance_count = int((~sec["retained_blocker"]).sum())
    blocked_count = int(sec["retained_blocker"].sum())
    if advance_count != int(exp["advance_security_count"]): failures.append(f"ADVANCE_COUNT:{advance_count}")
    if blocked_count != int(exp["blocked_security_count"]): failures.append(f"BLOCKED_COUNT:{blocked_count}")
    if sec["alpha_score"].notna().any(): failures.append("ALPHA_SCORE_PRESENT")

    blocker_surface = sec[sec["retained_blocker"]].copy()
    dim["alpha_score"] = pd.NA
    dim["formal_candidate_graduation_allowed"] = False
    dim["trade_authority"] = TRADE_AUTHORITY

    sec_path = out / "HKCU_P2B_FINAL_SECURITY_CROSS_SECTION.csv"
    dim_path = out / "HKCU_P2B_FINAL_COMPANY_DIMENSION_SURFACE.csv"
    blocker_path = out / "HKCU_P2B_FINAL_RETAINED_BLOCKERS.csv"
    ah_path = out / "HKCU_P2B_FINAL_AH_RELATIVE_VALUE.csv"
    sec.to_csv(sec_path, index=False)
    dim.to_csv(dim_path, index=False)
    blocker_surface.to_csv(blocker_path, index=False)
    ah_rel.to_csv(ah_path, index=False)

    decision = {
        "program_id": PROGRAM_ID,
        "phase": contract["phase"],
        "status": contract["pass_status"] if not failures else contract["blocked_status"],
        "security_count": int(len(sec)),
        "company_dimension_rows": int(len(dim)),
        "advance_security_count": advance_count,
        "blocked_security_count": blocked_count,
        "blocked_security_ids": sorted(blocker_surface["security_id"].tolist()),
        "transaction_tax_complete_count": int(sec["transaction_tax_evidence_status"].eq("EVIDENCE_COMPLETE").sum()),
        "true_ah_pair_count": int((sec["ah_pair_status"] == "TRUE_AH_PAIR").sum()),
        "ah_numeric_completed_count": int(len(ah_rel)),
        "alpha_score_non_null_count": 0,
        "formal_candidate_graduation_allowed": False,
        "candidate_pool_mutations": 0,
        "simulation_mutations": 0,
        "real_account_mutations": 0,
        "orders_created": 0,
        "next_gate": contract["next_gate"] if not failures else None,
        "trade_authority": TRADE_AUTHORITY,
    }
    quality = {
        "program_id": PROGRAM_ID,
        "status": "PASS" if not failures else "FAIL",
        "hard_failures": sorted(set(failures)),
        "all_77_security_decision_surfaces_present": len(sec) == 77,
        "all_231_company_dimensions_present": len(dim) == 231,
        "p2a_rank_preserved_not_rescored": True,
        "evidence_balance_descriptive_not_scored": True,
        "cross_dimension_event_deduplication_preserved": True,
        "missing_consensus_is_not_bearish": True,
        "transaction_tax_is_execution_context_not_alpha": True,
        "ah_relative_value_is_context_not_alpha": True,
        "ah_price_fx_synchronized_date": contract["cross_section_policy"]["ah_price_date"],
        "formal_candidate_graduation_allowed": False,
        "trade_authority": TRADE_AUTHORITY,
    }
    decision_path = out / "HKCU_P2B_FINAL_DECISION.json"
    quality_path = out / "HKCU_P2B_FINAL_QUALITY_REPORT.json"
    write_json(decision_path, decision)
    write_json(quality_path, quality)

    report = [
        "# HKCU P2B Final Cross-sectional Synthesis", "",
        f"Status: **{decision['status']}**", "",
        f"- Securities: {len(sec)}", f"- Company decision dimensions: {len(dim)}",
        f"- Ready for P3 contract evaluation with confidence cap: {advance_count}",
        f"- Retained investment blockers: {blocked_count}",
        f"- Synchronized A/H relative-value observations: {len(ah_rel)} / {int(exp['true_ah_pair_count'])}",
        "- New alpha score: 0", "- Formal HK Candidate graduation: not allowed", "",
        "## Boundary", "",
        "This gate is a cross-sectional research-readiness surface. It preserves P2A screening rank and evidence semantics, but does not promote any security to the formal HK Candidate Pool and does not modify portfolios or create orders.", ""
    ]
    report_path = out / "HKCU_P2B_FINAL_CROSS_SECTIONAL_SYNTHESIS.md"
    report_path.write_text("\n".join(report), encoding="utf-8")

    manifest = {
        "program_id": PROGRAM_ID,
        "as_of_date": contract["as_of_date"],
        "contract_sha256": sha256_file(contract_path),
        "files": {},
        "upstream_decision_sha256": {},
        "trade_authority": TRADE_AUTHORITY,
    }
    for stage, p in [
        ("P2A", upstream["p2a"] / "HKCU_P2A_DECISION.json"),
        ("E1", upstream["e1"] / "HKCU_P2B_E1_DECISION.json"),
        ("S1", upstream["s1"] / "HKCU_P2B_E2_S1_DECISION.json"),
        ("S2", upstream["s2"] / "HKCU_P2B_E2_S2_RANKS21_40_DECISION.json"),
        ("S3", upstream["s3"] / "HKCU_P2B_E2_S3_RANKS41_60_DECISION.json"),
        ("S4", upstream["s4"] / "HKCU_P2B_E2_S4_RANKS61_77_DECISION.json"),
    ]:
        manifest["upstream_decision_sha256"][stage] = sha256_file(p)
    for p in [sec_path, dim_path, blocker_path, ah_path, decision_path, quality_path, report_path]:
        manifest["files"][p.name] = {"sha256": sha256_file(p), "bytes": p.stat().st_size}
    write_json(out / "HKCU_P2B_FINAL_MANIFEST.json", manifest)

    if failures:
        raise SystemExit("P2B_FINAL_BUILD_FAILED:" + "|".join(sorted(set(failures))))
    print(json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True))
    return decision


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--repo-root", default=".")
    p.add_argument("--output", required=True)
    args = p.parse_args()
    build(Path(args.repo_root).resolve(), Path(args.output).resolve())


if __name__ == "__main__":
    main()
