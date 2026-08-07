#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

PROGRAM_ID = "HKCU-P2B-E2-D4"
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


def bool_series(series: pd.Series) -> pd.Series:
    return series.astype(str).str.lower().isin(["true", "1"])


def rebuild_d3(root: Path, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        sys.executable,
        str(root / "pipeline/hkcu_p2b_e2_deepen_top20_high_blockers.py"),
        "--repo-root", str(root),
        "--output", str(out),
    ], check=True)
    subprocess.run([
        sys.executable,
        str(root / "scripts/validate_hkcu_p2b_e2_deepening_d3.py"),
        "--output", str(out),
    ], check=True)


def build(root: Path, out: Path) -> None:
    contract_path = root / "config/hkcu_p2b_e2_deepening_d4_contract.json"
    contract = read_json(contract_path)
    out.mkdir(parents=True, exist_ok=True)

    d3_out = out / "_d3_rebuild"
    rebuild_d3(root, d3_out)

    d3_decision = read_json(d3_out / "HKCU_P2B_E2_D3_DECISION.json")
    if d3_decision.get("status") != "PASS_P2B_E2_D3_HIGH_BLOCKER_DEEPENING":
        raise SystemExit("UPSTREAM_D3_NOT_PASS")

    prior = pd.read_csv(
        d3_out / "HKCU_P2B_E2_D3_REMAINING_BLOCKER_QUEUE.csv",
        dtype={"stock_code_5d": str},
        keep_default_na=False,
    ).sort_values(["remaining_priority_rank", "p2a_overall_rank", "research_dimension", "security_id"]).reset_index(drop=True)

    selection = contract["selection_policy"]
    evidence = pd.read_csv(
        root / contract["authoritative_inputs"]["d4_evidence"],
        dtype={"stock_code_5d": str},
        keep_default_na=False,
    ).sort_values(["remaining_priority_rank", "p2a_overall_rank", "research_dimension", "security_id"]).reset_index(drop=True)
    evidence["stock_code_5d"] = evidence["stock_code_5d"].astype(str).str.zfill(5)

    failures: list[str] = []
    expected_rows = int(selection["expected_target_rows"])
    expected_securities = int(selection["expected_security_count"])

    if len(prior) != expected_rows:
        failures.append(f"PRIOR_BLOCKER_COUNT:{len(prior)}")
    if prior["security_id"].nunique() != expected_securities:
        failures.append(f"PRIOR_SECURITY_COUNT:{prior['security_id'].nunique()}")
    if len(evidence) != expected_rows:
        failures.append(f"EVIDENCE_ROW_COUNT:{len(evidence)}")
    if evidence["security_id"].nunique() != expected_securities:
        failures.append(f"EVIDENCE_SECURITY_COUNT:{evidence['security_id'].nunique()}")
    if evidence.duplicated(["security_id", "research_dimension"]).any():
        failures.append("DUPLICATE_EVIDENCE_SECURITY_DIMENSION")

    prior_keys = set(zip(prior["security_id"], prior["research_dimension"]))
    evidence_keys = set(zip(evidence["security_id"], evidence["research_dimension"]))
    missing = sorted(prior_keys - evidence_keys)
    extra = sorted(evidence_keys - prior_keys)
    if missing:
        failures.append("MISSING_D3_BLOCKER_EVIDENCE:" + ",".join(f"{a}:{b}" for a, b in missing))
    if extra:
        failures.append("EXTRA_NON_D3_BLOCKER_EVIDENCE:" + ",".join(f"{a}:{b}" for a, b in extra))

    policy = contract["evidence_policy"]
    allowed = set(policy["allowed_resolution_statuses"])
    blockers = set(policy["blocker_statuses"])
    if not set(evidence["resolution_status"]).issubset(allowed):
        failures.append("INVALID_RESOLUTION_STATUS")
    post = bool_series(evidence["post_blocker"])
    if not evidence.loc[post, "resolution_status"].isin(blockers).all():
        failures.append("POST_BLOCKER_STATUS_INCONSISTENT")
    if evidence.loc[~post, "resolution_status"].isin(blockers).any():
        failures.append("NON_BLOCKER_HAS_BLOCKER_STATUS")
    if not evidence.loc[post, "decision_effect"].eq("RETAIN_BLOCKER").all():
        failures.append("POST_BLOCKER_DECISION_EFFECT")
    if evidence.loc[~post, "decision_effect"].eq("RETAIN_BLOCKER").any():
        failures.append("CLEARED_ROW_RETAIN_EFFECT")

    as_of = pd.Timestamp(selection["as_of_date"])
    dates = pd.to_datetime(evidence["evidence_date"], errors="coerce")
    if dates.isna().any():
        failures.append("INVALID_EVIDENCE_DATE")
    if (dates > as_of).any():
        failures.append("FUTURE_DATED_EVIDENCE")
    for col in [
        "source_url", "evidence_title", "evidence_summary", "resolution_status",
        "resolution_direction", "decision_effect", "post_materiality", "post_finding",
        "resolution_rationale", "monitor_trigger", "remaining_question", "cross_dimension_signal",
    ]:
        if evidence[col].astype(str).str.strip().eq("").any():
            failures.append("BLANK_REQUIRED_EVIDENCE_FIELD:" + col)

    primary_prefixes = ("https://www1.hkexnews.hk/", "https://www.hkexnews.hk/")
    if not evidence["source_url"].astype(str).str.startswith(primary_prefixes).all():
        failures.append("NON_PRIMARY_SOURCE_URL")
    secondary = evidence["secondary_source_url"].astype(str).str.strip()
    bad_secondary = secondary[(secondary != "") & ~secondary.str.startswith(primary_prefixes)]
    if len(bad_secondary):
        failures.append("NON_PRIMARY_SECONDARY_SOURCE_URL")

    expected_blocker_keys = set(contract["expected_retained_blocker_keys"])
    actual_blocker_keys = set(
        evidence.loc[post, "security_id"].astype(str) + "|" + evidence.loc[post, "research_dimension"].astype(str)
    )
    if actual_blocker_keys != expected_blocker_keys:
        failures.append("RETAINED_BLOCKER_KEY_SET:" + ",".join(sorted(actual_blocker_keys)))

    # Decision-semantic guards: stale/missing data cannot silently become bearish; fresh
    # negative issuer signals must be carried even if they emerged in a different dimension.
    yue = evidence[(evidence["security_id"] == "HKEX:00551") & (evidence["research_dimension"] == "GOVERNANCE_VALUE_TRAP")]
    brilliance_earn = evidence[(evidence["security_id"] == "HKEX:01114") & (evidence["research_dimension"] == "CATALYST")]
    brilliance_gov = evidence[(evidence["security_id"] == "HKEX:01114") & (evidence["research_dimension"] == "GOVERNANCE_VALUE_TRAP")]
    if len(yue) != 1 or not bool_series(yue["post_blocker"]).all() or not yue["post_finding"].str.contains("NEGATIVE_EARNINGS", case=False).all():
        failures.append("YUE_YUEN_FRESH_EARNINGS_GUARD")
    if len(brilliance_earn) != 1 or not bool_series(brilliance_earn["post_blocker"]).all() or not brilliance_earn["post_finding"].str.contains("NEGATIVE_EARNINGS", case=False).all():
        failures.append("BRILLIANCE_EARNINGS_GUARD")
    if len(brilliance_gov) != 1 or bool_series(brilliance_gov["post_blocker"]).any():
        failures.append("BRILLIANCE_GOVERNANCE_DUPLICATE_BLOCKER")

    pending_optional = evidence[evidence["security_id"].isin(["HKEX:00300", "HKEX:01530"]) & (evidence["research_dimension"] == "CATALYST")]
    if len(pending_optional) != 2 or bool_series(pending_optional["post_blocker"]).any():
        failures.append("PENDING_OPTIONALITY_BLOCKER_GUARD")
    missing_current = evidence[
        (evidence["research_dimension"] == "EARNINGS_EXPECTATION_REVISION")
        & evidence["resolution_direction"].eq("UNKNOWN")
    ]
    if bool_series(missing_current["post_blocker"]).any():
        failures.append("MISSING_DATA_BEARISH_GUARD")

    prior_cols = [
        "remaining_priority_rank", "p2a_overall_rank", "security_id", "stock_code_5d",
        "security_name", "research_dimension", "materiality", "finding",
        "current_blocker_reason", "counterevidence_needed", "monitor_trigger",
        "source_url", "evidence_date", "evidence_title",
    ]
    prior_small = prior[prior_cols].rename(columns={
        "materiality": "prior_materiality",
        "finding": "prior_finding",
        "current_blocker_reason": "prior_blocker_reason",
        "counterevidence_needed": "prior_counterevidence_needed",
        "monitor_trigger": "prior_monitor_trigger",
        "source_url": "prior_source_url",
        "evidence_date": "prior_evidence_date",
        "evidence_title": "prior_evidence_title",
    })
    resolution = evidence.merge(
        prior_small,
        on=["remaining_priority_rank", "p2a_overall_rank", "security_id", "stock_code_5d", "security_name", "research_dimension"],
        how="left",
        validate="one_to_one",
    )
    if resolution["prior_finding"].astype(str).str.strip().eq("").any():
        failures.append("PRIOR_LINEAGE_JOIN_FAILED")
    resolution["alpha_score"] = pd.NA
    resolution["trade_authority"] = TRADE_AUTHORITY
    resolution = resolution.sort_values(["remaining_priority_rank", "p2a_overall_rank", "research_dimension", "security_id"]).reset_index(drop=True)

    resolution_path = out / "HKCU_P2B_E2_D4_REMAINING_BLOCKER_RESOLUTION.csv"
    resolution.to_csv(resolution_path, index=False)

    retained = resolution[bool_series(resolution["post_blocker"])].copy().reset_index(drop=True)
    if not retained.empty:
        retained.insert(0, "retained_priority_rank", range(1, len(retained) + 1))
    retained_path = out / "HKCU_P2B_E2_D4_RETAINED_INVESTMENT_BLOCKERS.csv"
    retained.to_csv(retained_path, index=False)

    d3_sec = pd.read_csv(
        d3_out / "HKCU_P2B_E2_D3_TOP20_SECURITY_READINESS.csv",
        dtype={"stock_code_5d": str},
        keep_default_na=False,
    )
    retained_counts = retained.groupby("security_id").size().to_dict() if not retained.empty else {}
    sec_rows = []
    for row in d3_sec.itertuples(index=False):
        n = int(retained_counts.get(row.security_id, 0))
        sec_rows.append({
            "p2a_overall_rank": int(row.p2a_overall_rank),
            "security_id": row.security_id,
            "stock_code_5d": str(row.stock_code_5d).zfill(5),
            "security_name": row.security_name,
            "retained_investment_blocker_rows": n,
            "d4_readiness": "RETAINED_INVESTMENT_BLOCKER" if n else "READY_WITH_CONFIDENCE_CAP",
            "formal_candidate_graduation_allowed": False,
            "alpha_score": pd.NA,
            "trade_authority": TRADE_AUTHORITY,
        })
    sec = pd.DataFrame(sec_rows).sort_values("p2a_overall_rank").reset_index(drop=True)
    sec_path = out / "HKCU_P2B_E2_D4_TOP20_SECURITY_READINESS.csv"
    sec.to_csv(sec_path, index=False)

    actual = {
        "target_rows": int(len(resolution)),
        "target_security_count": int(resolution["security_id"].nunique()),
        "cleared_or_confidence_cap_rows": int((~bool_series(resolution["post_blocker"])).sum()),
        "retained_investment_blocker_rows": int(bool_series(resolution["post_blocker"]).sum()),
        "remaining_blocker_rows": int(len(retained)),
        "remaining_blocker_security_count": int(retained["security_id"].nunique()),
        "ready_with_confidence_cap_security_count": int((sec["d4_readiness"] == "READY_WITH_CONFIDENCE_CAP").sum()),
    }
    expected = {k: int(v) for k, v in contract["expected_d4_result"].items()}
    for key, expected_value in expected.items():
        if actual.get(key) != expected_value:
            failures.append(f"EXPECTED_RESULT_MISMATCH:{key}:{actual.get(key)}:{expected_value}")

    if resolution["alpha_score"].notna().any() or sec["alpha_score"].notna().any():
        failures.append("ALPHA_SCORE_NON_NULL")

    quality = {
        "program_id": PROGRAM_ID,
        "status": "PASS" if not failures else "FAIL",
        "hard_failures": sorted(set(failures)),
        "target_rows": actual["target_rows"],
        "retained_investment_blockers": actual["retained_investment_blocker_rows"],
        "primary_official_evidence_only": True,
        "missing_consensus_is_not_bearish": True,
        "formal_candidate_graduation_allowed": False,
        "trade_authority": TRADE_AUTHORITY,
    }
    quality_path = out / "HKCU_P2B_E2_D4_QUALITY_REPORT.json"
    write_json(quality_path, quality)

    decision = {
        "program_id": PROGRAM_ID,
        "status": "PASS_P2B_E2_D4_REMAINING_BLOCKER_DEEPENING" if not failures else "BLOCKED_P2B_E2_D4_REMAINING_BLOCKER_DEEPENING",
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
    decision_path = out / "HKCU_P2B_E2_D4_DECISION.json"
    write_json(decision_path, decision)

    manifest = {
        "program_id": PROGRAM_ID,
        "as_of_date": selection["as_of_date"],
        "upstream_d3_status": d3_decision.get("status"),
        "files": {},
        "trade_authority": TRADE_AUTHORITY,
    }
    for path in [resolution_path, retained_path, sec_path, quality_path, decision_path]:
        manifest["files"][path.name] = {"sha256": sha256_file(path), "bytes": path.stat().st_size}
    write_json(out / "HKCU_P2B_E2_D4_MANIFEST.json", manifest)

    if failures:
        raise SystemExit("P2B_E2_D4_BUILD_FAILED:" + "|".join(sorted(set(failures))))
    print(json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--repo-root", default=".")
    p.add_argument("--output", required=True)
    args = p.parse_args()
    build(Path(args.repo_root).resolve(), Path(args.output).resolve())


if __name__ == "__main__":
    main()
