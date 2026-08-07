#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

PROGRAM_ID = "HKCU-P2B-E2-D3"
TRADE_AUTHORITY = "NONE"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def rebuild_d2(root: Path, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        sys.executable,
        str(root / "pipeline/hkcu_p2b_e2_synthesize_top20_partial.py"),
        "--repo-root", str(root),
        "--output", str(out),
    ], check=True)
    subprocess.run([
        sys.executable,
        str(root / "scripts/validate_hkcu_p2b_e2_deepening_d2.py"),
        "--output", str(out),
    ], check=True)


def bool_series(series: pd.Series) -> pd.Series:
    return series.astype(str).str.lower().isin(["true", "1"])


def build(root: Path, out: Path) -> None:
    contract_path = root / "config/hkcu_p2b_e2_deepening_d3_contract.json"
    contract = read_json(contract_path)
    out.mkdir(parents=True, exist_ok=True)

    d2_out = out / "_d2_rebuild"
    rebuild_d2(root, d2_out)

    d2_decision = read_json(d2_out / "HKCU_P2B_E2_D2_DECISION.json")
    if d2_decision.get("status") != "PASS_P2B_E2_D2_TOP20_SYNTHESIS":
        raise SystemExit("UPSTREAM_D2_NOT_PASS")

    blockers = pd.read_csv(
        d2_out / "HKCU_P2B_E2_D2_TOP20_BLOCKER_QUEUE.csv",
        dtype={"stock_code_5d": str},
        keep_default_na=False,
    )
    selection = contract["selection_policy"]
    high = blockers[
        (blockers["materiality"] == selection["required_materiality"])
        & bool_series(blockers["graduation_blocker"])
    ].copy().sort_values(["p2a_overall_rank", "research_dimension", "security_id"]).reset_index(drop=True)

    evidence_path = root / contract["authoritative_inputs"]["d3_evidence"]
    evidence = pd.read_csv(evidence_path, dtype={"stock_code_5d": str}, keep_default_na=False)
    evidence["stock_code_5d"] = evidence["stock_code_5d"].astype(str).str.zfill(5)
    evidence = evidence.sort_values(["p2a_overall_rank", "research_dimension", "security_id"]).reset_index(drop=True)

    failures: list[str] = []
    expected_rows = int(selection["expected_target_rows"])
    expected_securities = int(selection["expected_security_count"])
    if len(high) != expected_rows:
        failures.append(f"HIGH_BLOCKER_COUNT:{len(high)}")
    if high["security_id"].nunique() != expected_securities:
        failures.append(f"HIGH_BLOCKER_SECURITY_COUNT:{high['security_id'].nunique()}")
    if len(evidence) != expected_rows:
        failures.append(f"EVIDENCE_ROW_COUNT:{len(evidence)}")
    if evidence["security_id"].nunique() != expected_securities:
        failures.append(f"EVIDENCE_SECURITY_COUNT:{evidence['security_id'].nunique()}")
    if evidence.duplicated(["security_id", "research_dimension"]).any():
        failures.append("DUPLICATE_EVIDENCE_SECURITY_DIMENSION")

    high_keys = set(zip(high["security_id"], high["research_dimension"]))
    evidence_keys = set(zip(evidence["security_id"], evidence["research_dimension"]))
    missing = sorted(high_keys - evidence_keys)
    extra = sorted(evidence_keys - high_keys)
    if missing:
        failures.append("MISSING_HIGH_BLOCKER_EVIDENCE:" + ",".join(f"{a}:{b}" for a,b in missing))
    if extra:
        failures.append("EXTRA_NON_HIGH_BLOCKER_EVIDENCE:" + ",".join(f"{a}:{b}" for a,b in extra))

    allowed = set(contract["evidence_policy"]["allowed_resolution_statuses"])
    cleared = set(contract["evidence_policy"]["cleared_statuses"])
    retained = set(contract["evidence_policy"]["retained_statuses"])
    if not set(evidence["resolution_status"]).issubset(allowed):
        failures.append("INVALID_RESOLUTION_STATUS")
    post = bool_series(evidence["post_blocker"])
    inconsistent_clear = evidence[evidence["resolution_status"].isin(cleared) & post]
    inconsistent_retain = evidence[evidence["resolution_status"].isin(retained) & ~post]
    if not inconsistent_clear.empty:
        failures.append("CLEARED_STATUS_STILL_BLOCKER")
    if not inconsistent_retain.empty:
        failures.append("RETAINED_STATUS_NOT_BLOCKER")

    as_of = pd.Timestamp(selection["as_of_date"])
    dates = pd.to_datetime(evidence["evidence_date"], errors="coerce")
    if dates.isna().any():
        failures.append("INVALID_EVIDENCE_DATE")
    if (dates > as_of).any():
        failures.append("FUTURE_DATED_EVIDENCE")
    for col in ["source_url", "evidence_title", "evidence_summary", "resolution_rationale", "monitor_trigger", "remaining_question", "cross_dimension_signal"]:
        if evidence[col].astype(str).str.strip().eq("").any():
            failures.append("BLANK_REQUIRED_EVIDENCE_FIELD:" + col)
    urls = evidence["source_url"].astype(str)
    if not urls.str.startswith(("https://www1.hkexnews.hk/", "https://www.hkexnews.hk/")).all():
        failures.append("NON_PRIMARY_SOURCE_URL")
    secondary = evidence["secondary_source_url"].astype(str).str.strip()
    bad_secondary = secondary[(secondary != "") & ~secondary.str.startswith(("https://www1.hkexnews.hk/", "https://www.hkexnews.hk/"))]
    if len(bad_secondary):
        failures.append("NON_PRIMARY_SECONDARY_SOURCE_URL")

    prior_cols = [
        "p2a_overall_rank", "security_id", "stock_code_5d", "security_name", "research_dimension",
        "materiality", "finding", "counterevidence_needed", "monitor_trigger", "source_url", "evidence_date", "evidence_title"
    ]
    prior = high[prior_cols].rename(columns={
        "materiality": "prior_materiality",
        "finding": "prior_finding",
        "counterevidence_needed": "prior_counterevidence_needed",
        "monitor_trigger": "prior_monitor_trigger",
        "source_url": "prior_source_url",
        "evidence_date": "prior_evidence_date",
        "evidence_title": "prior_evidence_title",
    })
    resolution = evidence.merge(
        prior,
        on=["p2a_overall_rank", "security_id", "stock_code_5d", "security_name", "research_dimension"],
        how="left",
        validate="one_to_one",
    )
    if resolution["prior_finding"].eq("").any():
        failures.append("PRIOR_LINEAGE_JOIN_FAILED")
    resolution["alpha_score"] = pd.NA
    resolution["trade_authority"] = TRADE_AUTHORITY
    resolution = resolution.sort_values(["p2a_overall_rank", "research_dimension", "security_id"]).reset_index(drop=True)

    resolution_path = out / "HKCU_P2B_E2_D3_HIGH_BLOCKER_RESOLUTION.csv"
    resolution.to_csv(resolution_path, index=False)

    key_to_d3 = {
        (r.security_id, r.research_dimension): r
        for r in evidence.itertuples(index=False)
    }
    remaining_rows = []
    for row in blockers.itertuples(index=False):
        key = (row.security_id, row.research_dimension)
        if key in key_to_d3:
            d3 = key_to_d3[key]
            if str(d3.post_blocker).lower() not in ("true", "1"):
                continue
            current = row._asdict()
            current.update({
                "d3_resolution_status": d3.resolution_status,
                "d3_resolution_direction": d3.resolution_direction,
                "d3_resolution_rationale": d3.resolution_rationale,
                "d3_monitor_trigger": d3.monitor_trigger,
                "d3_remaining_question": d3.remaining_question,
                "cross_dimension_signal": d3.cross_dimension_signal,
                "current_blocker_reason": d3.remaining_question,
            })
            remaining_rows.append(current)
        else:
            current = row._asdict()
            current.update({
                "d3_resolution_status": "",
                "d3_resolution_direction": "",
                "d3_resolution_rationale": "",
                "d3_monitor_trigger": "",
                "d3_remaining_question": "",
                "cross_dimension_signal": "",
                "current_blocker_reason": row.counterevidence_needed,
            })
            remaining_rows.append(current)

    remaining = pd.DataFrame(remaining_rows)
    if not remaining.empty:
        remaining["_mat"] = remaining["materiality"].map({"HIGH": 0, "MEDIUM": 1, "LOW": 2}).fillna(9)
        remaining = remaining.sort_values(["_mat", "p2a_overall_rank", "research_dimension", "security_id"]).drop(columns=["_mat"]).reset_index(drop=True)
        remaining.insert(0, "remaining_priority_rank", range(1, len(remaining) + 1))
    remaining_path = out / "HKCU_P2B_E2_D3_REMAINING_BLOCKER_QUEUE.csv"
    remaining.to_csv(remaining_path, index=False)

    d2_sec = pd.read_csv(
        d2_out / "HKCU_P2B_E2_D2_TOP20_SECURITY_READINESS.csv",
        dtype={"stock_code_5d": str},
        keep_default_na=False,
    )
    rem_counts = remaining.groupby("security_id").size().to_dict() if not remaining.empty else {}
    high_counts = remaining[remaining["materiality"] == "HIGH"].groupby("security_id").size().to_dict() if not remaining.empty else {}
    sec_rows = []
    for row in d2_sec.itertuples(index=False):
        n = int(rem_counts.get(row.security_id, 0))
        nh = int(high_counts.get(row.security_id, 0))
        sec_rows.append({
            "p2a_overall_rank": int(row.p2a_overall_rank),
            "security_id": row.security_id,
            "stock_code_5d": str(row.stock_code_5d).zfill(5),
            "security_name": row.security_name,
            "remaining_blocker_rows": n,
            "remaining_high_blocker_rows": nh,
            "d3_readiness": "TARGETED_DEEPENING_REQUIRED" if n else "READY_WITH_CONFIDENCE_CAP",
            "formal_candidate_graduation_allowed": False,
            "alpha_score": pd.NA,
            "trade_authority": TRADE_AUTHORITY,
        })
    sec = pd.DataFrame(sec_rows).sort_values("p2a_overall_rank").reset_index(drop=True)
    sec_path = out / "HKCU_P2B_E2_D3_TOP20_SECURITY_READINESS.csv"
    sec.to_csv(sec_path, index=False)

    actual = {
        "target_rows": int(len(resolution)),
        "cleared_or_monitor_only_rows": int((~bool_series(resolution["post_blocker"])).sum()),
        "retained_targeted_rows": int(bool_series(resolution["post_blocker"]).sum()),
        "remaining_total_blocker_rows_after_d3": int(len(remaining)),
        "remaining_targeted_security_count": int((sec["d3_readiness"] == "TARGETED_DEEPENING_REQUIRED").sum()),
        "ready_with_confidence_cap_security_count": int((sec["d3_readiness"] == "READY_WITH_CONFIDENCE_CAP").sum()),
    }
    expected = {k: int(v) for k, v in contract["expected_d3_result"].items()}
    for k, v in expected.items():
        if actual.get(k) != v:
            failures.append(f"EXPECTED_RESULT_MISMATCH:{k}:{actual.get(k)}:{v}")

    if resolution["alpha_score"].notna().any() or sec["alpha_score"].notna().any():
        failures.append("ALPHA_SCORE_NON_NULL")

    quality = {
        "program_id": PROGRAM_ID,
        "status": "PASS" if not failures else "FAIL",
        "hard_failures": sorted(set(failures)),
        "target_rows": actual["target_rows"],
        "remaining_blockers": actual["remaining_total_blocker_rows_after_d3"],
        "primary_official_evidence_only": True,
        "formal_candidate_graduation_allowed": False,
        "trade_authority": TRADE_AUTHORITY,
    }
    quality_path = out / "HKCU_P2B_E2_D3_QUALITY_REPORT.json"
    write_json(quality_path, quality)

    decision = {
        "program_id": PROGRAM_ID,
        "status": "PASS_P2B_E2_D3_HIGH_BLOCKER_DEEPENING" if not failures else "BLOCKED_P2B_E2_D3_HIGH_BLOCKER_DEEPENING",
        **actual,
        "score_non_null_count": 0,
        "formal_candidate_graduation_allowed": False,
        "candidate_pool_mutations": 0,
        "simulation_mutations": 0,
        "real_account_mutations": 0,
        "orders_created": 0,
        "next_gate": contract["next_gate"],
        "trade_authority": TRADE_AUTHORITY,
    }
    decision_path = out / "HKCU_P2B_E2_D3_DECISION.json"
    write_json(decision_path, decision)

    manifest = {
        "program_id": PROGRAM_ID,
        "as_of_date": selection["as_of_date"],
        "upstream_d2_status": d2_decision.get("status"),
        "files": {},
        "trade_authority": TRADE_AUTHORITY,
    }
    for p in [resolution_path, remaining_path, sec_path, quality_path, decision_path]:
        manifest["files"][p.name] = {"sha256": sha256_file(p), "bytes": p.stat().st_size}
    write_json(out / "HKCU_P2B_E2_D3_MANIFEST.json", manifest)

    if failures:
        raise SystemExit("P2B_E2_D3_BUILD_FAILED:" + "|".join(sorted(set(failures))))
    print(json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--repo-root", default=".")
    p.add_argument("--output", required=True)
    args = p.parse_args()
    build(Path(args.repo_root).resolve(), Path(args.output).resolve())


if __name__ == "__main__":
    main()
