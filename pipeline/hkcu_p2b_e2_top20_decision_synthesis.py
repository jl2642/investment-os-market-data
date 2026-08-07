#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

PROGRAM_ID = "HKCU-P2B-E2-S1"
TRADE_AUTHORITY = "NONE"
DIMS = {"GOVERNANCE_VALUE_TRAP", "EARNINGS_EXPECTATION_REVISION", "CATALYST"}


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


def bool_value(v) -> bool:
    return str(v).lower() in {"true", "1"}


def rebuild_d4(root: Path, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        sys.executable,
        str(root / "pipeline/hkcu_p2b_e2_deepen_top20_remaining_blockers.py"),
        "--repo-root", str(root),
        "--output", str(out),
    ], check=True)
    subprocess.run([
        sys.executable,
        str(root / "scripts/validate_hkcu_p2b_e2_deepening_d4.py"),
        "--output", str(out),
    ], check=True)


def explicit_complete_direction(title: str, summary: str) -> str:
    text = f"{title} {summary}".lower()
    negative = (
        "profit warning", "negative profit", "decrease by", "decline by", "decline of",
        "expected loss", "expects a loss", "loss attributable", "profit to fall", "profit fall",
        "profit decrease", "deterioration"
    )
    positive = (
        "positive profit", "profit increase", "increase by", "increase of", "profit to rise",
        "record profit", "profit growth"
    )
    if any(t in text for t in negative):
        return "NEGATIVE"
    if any(t in text for t in positive):
        return "POSITIVE"
    return "NEUTRAL_OR_UNKNOWN"


def build(root: Path, out: Path) -> None:
    contract = read_json(root / "config/hkcu_p2b_e2_top20_decision_synthesis_s1_contract.json")
    out.mkdir(parents=True, exist_ok=True)
    d4 = out / "_d4_rebuild"
    rebuild_d4(root, d4)

    d4_decision = read_json(d4 / "HKCU_P2B_E2_D4_DECISION.json")
    if d4_decision.get("status") != "PASS_P2B_E2_D4_REMAINING_BLOCKER_DEEPENING":
        raise SystemExit("UPSTREAM_D4_NOT_PASS")

    d3 = d4 / "_d3_rebuild"
    d2 = d3 / "_d2_rebuild"
    d1 = d2 / "_d1_rebuild"
    ledger = pd.read_csv(
        d1 / "HKCU_P2B_E2_D1_CURRENT_EVIDENCE_LEDGER.csv",
        dtype={"stock_code_5d": str}, keep_default_na=False,
    )
    d2_syn = pd.read_csv(
        d2 / "HKCU_P2B_E2_D2_TOP20_PARTIAL_SYNTHESIS.csv",
        dtype={"stock_code_5d": str}, keep_default_na=False,
    )
    d3_res = pd.read_csv(
        d3 / "HKCU_P2B_E2_D3_HIGH_BLOCKER_RESOLUTION.csv",
        dtype={"stock_code_5d": str}, keep_default_na=False,
    )
    d4_res = pd.read_csv(
        d4 / "HKCU_P2B_E2_D4_REMAINING_BLOCKER_RESOLUTION.csv",
        dtype={"stock_code_5d": str}, keep_default_na=False,
    )

    sel = contract["selection_policy"]
    top = ledger[
        pd.to_numeric(ledger["p2a_overall_rank"], errors="coerce").between(
            int(sel["rank_start"]), int(sel["rank_end"]), inclusive="both"
        ) & ledger["research_dimension"].isin(DIMS)
    ].copy().sort_values(["p2a_overall_rank", "research_dimension", "security_id"]).reset_index(drop=True)
    top["stock_code_5d"] = top["stock_code_5d"].astype(str).str.zfill(5)

    failures: list[str] = []
    if len(top) != int(sel["expected_dimension_rows"]): failures.append(f"DIMENSION_ROWS:{len(top)}")
    if top["security_id"].nunique() != int(sel["expected_security_count"]): failures.append(f"SECURITY_COUNT:{top['security_id'].nunique()}")
    if top.duplicated(["security_id", "research_dimension"]).any(): failures.append("DUPLICATE_SECURITY_DIMENSION")
    if set(top["research_dimension"]) != DIMS: failures.append("DIMENSION_VOCABULARY")
    if int((top["evidence_status"] == "EVIDENCE_PARTIAL").sum()) != int(sel["expected_partial_rows"]): failures.append("PARTIAL_ROW_COUNT")
    if int((top["evidence_status"] != "EVIDENCE_PARTIAL").sum()) != int(sel["expected_non_partial_rows"]): failures.append("NON_PARTIAL_ROW_COUNT")
    if int((top["evidence_status"] == "RESEARCH_REQUIRED").sum()) != int(sel["expected_research_required_rows"]): failures.append("RESEARCH_REQUIRED_REMAINS")

    d2_map = {(r.security_id, r.research_dimension): r for r in d2_syn.itertuples(index=False)}
    d3_map = {(r.security_id, r.research_dimension): r for r in d3_res.itertuples(index=False)}
    d4_map = {(r.security_id, r.research_dimension): r for r in d4_res.itertuples(index=False)}

    rows = []
    for r in top.itertuples(index=False):
        key = (r.security_id, r.research_dimension)
        state = "EVIDENCE_COMPLETE"
        direction = explicit_complete_direction(r.evidence_title, r.evidence_summary)
        materiality = "UNASSESSED_COMPLETE_EVIDENCE"
        blocker = direction == "NEGATIVE"
        finding = "PRIMARY_EVIDENCE_COMPLETE"
        next_evidence = "Continue routine issuer monitoring."
        monitor_trigger = "New issuer disclosure or material company-specific event."
        lineage = "D1_COMPLETE"

        if r.evidence_status == "EVIDENCE_PARTIAL":
            if key not in d2_map:
                failures.append(f"PARTIAL_WITHOUT_D2:{r.security_id}:{r.research_dimension}")
            else:
                s = d2_map[key]
                state = str(s.evidence_sufficiency)
                direction = str(s.finding_direction)
                materiality = str(s.materiality)
                blocker = bool_value(s.graduation_blocker)
                finding = str(s.finding)
                next_evidence = str(s.counterevidence_needed)
                monitor_trigger = str(s.monitor_trigger)
                lineage = "D2_PARTIAL_SYNTHESIS"

        if key in d3_map:
            x = d3_map[key]
            post = bool_value(x.post_blocker)
            status = str(x.resolution_status)
            blocker = post
            direction = str(x.resolution_direction)
            finding = str(x.evidence_title)
            next_evidence = str(x.remaining_question)
            monitor_trigger = str(x.monitor_trigger)
            materiality = str(x.prior_materiality) if hasattr(x, "prior_materiality") else materiality
            if post:
                state = "TARGETED_DEEPENING_REQUIRED"
            elif "MONITOR" in status:
                state = "MONITOR_ONLY"
            else:
                state = "CONFIDENCE_CAP_MONITOR"
            lineage = "D3_HIGH_BLOCKER_RESOLUTION"

        if key in d4_map:
            x = d4_map[key]
            post = bool_value(x.post_blocker)
            status = str(x.resolution_status)
            blocker = post
            direction = str(x.resolution_direction)
            finding = str(x.evidence_title)
            next_evidence = str(x.remaining_question)
            monitor_trigger = str(x.monitor_trigger)
            if post:
                state = "RETAINED_INVESTMENT_BLOCKER"
            elif "CONFIDENCE_CAP" in status:
                state = "CONFIDENCE_CAP_MONITOR"
            else:
                state = "MONITOR_ONLY"
            lineage = "D4_REMAINING_BLOCKER_RESOLUTION"

        if r.evidence_status != "EVIDENCE_PARTIAL" and explicit_complete_direction(r.evidence_title, r.evidence_summary) == "NEGATIVE":
            blocker = True
            state = "RETAINED_DIRECT_NEGATIVE_SIGNAL"
            direction = "NEGATIVE"
            finding = "DIRECT_NEGATIVE_SIGNAL_IN_COMPLETE_EVIDENCE"
            next_evidence = "Reconcile the direct negative issuer signal before any Candidate graduation."
            lineage = "S1_DIRECT_NEGATIVE_GUARD"

        rows.append({
            "p2a_overall_rank": int(r.p2a_overall_rank),
            "security_id": r.security_id,
            "stock_code_5d": str(r.stock_code_5d).zfill(5),
            "security_name": r.security_name,
            "research_dimension": r.research_dimension,
            "upstream_evidence_status": r.evidence_status,
            "source_url": r.source_url,
            "evidence_date": r.evidence_date,
            "evidence_title": r.evidence_title,
            "final_dimension_state": state,
            "final_direction": direction,
            "final_materiality": materiality,
            "final_blocker": bool(blocker),
            "final_finding": finding,
            "next_required_evidence": next_evidence,
            "monitor_trigger": monitor_trigger,
            "decision_lineage": lineage,
            "alpha_score": pd.NA,
            "trade_authority": TRADE_AUTHORITY,
        })

    dim = pd.DataFrame(rows).sort_values(["p2a_overall_rank", "research_dimension", "security_id"]).reset_index(drop=True)
    dim.insert(0, "decision_dimension_row_id", range(1, len(dim) + 1))

    allowed_states = set(contract["synthesis_policy"]["dimension_states"])
    if not set(dim["final_dimension_state"]).issubset(allowed_states): failures.append("DIMENSION_STATE_VOCABULARY")
    if dim["alpha_score"].notna().any(): failures.append("ALPHA_SCORE_PRESENT")
    if (dim["trade_authority"] != TRADE_AUTHORITY).any(): failures.append("TRADE_AUTHORITY_NOT_NONE")

    security_rows = []
    for security_id, grp in dim.groupby("security_id", sort=False):
        rank = int(grp["p2a_overall_rank"].iloc[0])
        blockers = grp[grp["final_blocker"].astype(bool)]
        cap_count = int(grp["final_dimension_state"].isin(["CONFIDENCE_CAP_MONITOR", "LIMITED_CONFIDENCE", "TARGETED_DEEPENING_REQUIRED"]).sum())
        monitor_count = int(grp["final_dimension_state"].isin(["MONITOR_ONLY", "CONFIDENCE_CAP_MONITOR"]).sum())
        negative_count = int((grp["final_direction"] == "NEGATIVE").sum())
        positive_count = int((grp["final_direction"] == "POSITIVE").sum())
        if len(blockers):
            decision_state = "HOLD_RETAINED_INVESTMENT_BLOCKER"
            confidence_cap = "BLOCKED_UNTIL_TRIGGER"
        else:
            decision_state = "ADVANCE_TO_P2B_CROSS_SECTIONAL_SYNTHESIS_WITH_CONFIDENCE_CAP"
            confidence_cap = "MEDIUM"
        required = [x for x in grp.loc[grp["final_dimension_state"].isin(["CONFIDENCE_CAP_MONITOR", "LIMITED_CONFIDENCE", "TARGETED_DEEPENING_REQUIRED", "RETAINED_INVESTMENT_BLOCKER", "RETAINED_DIRECT_NEGATIVE_SIGNAL"]), "next_required_evidence"].astype(str).tolist() if x]
        triggers = [x for x in grp["monitor_trigger"].astype(str).tolist() if x]
        blocker_findings = [x for x in blockers["final_finding"].astype(str).tolist() if x]
        security_rows.append({
            "p2a_overall_rank": rank,
            "security_id": security_id,
            "stock_code_5d": str(grp["stock_code_5d"].iloc[0]).zfill(5),
            "security_name": grp["security_name"].iloc[0],
            "complete_dimension_count": int((grp["upstream_evidence_status"] == "EVIDENCE_COMPLETE").sum()),
            "partial_dimension_count": int((grp["upstream_evidence_status"] == "EVIDENCE_PARTIAL").sum()),
            "confidence_cap_dimension_count": cap_count,
            "monitor_dimension_count": monitor_count,
            "retained_blocker_count": int(len(blockers)),
            "positive_signal_count": positive_count,
            "negative_signal_count": negative_count,
            "decision_state": decision_state,
            "confidence_cap": confidence_cap,
            "retained_blocker_summary": " | ".join(dict.fromkeys(blocker_findings)),
            "next_required_evidence": " | ".join(dict.fromkeys(required)),
            "monitor_triggers": " | ".join(dict.fromkeys(triggers)),
            "p2a_rank_preserved": True,
            "formal_candidate_graduation_allowed": False,
            "alpha_score": pd.NA,
            "trade_authority": TRADE_AUTHORITY,
        })

    sec = pd.DataFrame(security_rows).sort_values("p2a_overall_rank").reset_index(drop=True)
    allowed_decisions = set(contract["synthesis_policy"]["decision_states"])
    if len(sec) != int(sel["expected_security_count"]): failures.append("SECURITY_SYNTHESIS_COUNT")
    if not set(sec["decision_state"]).issubset(allowed_decisions): failures.append("DECISION_STATE_VOCABULARY")
    if sec["alpha_score"].notna().any(): failures.append("SECURITY_ALPHA_SCORE_PRESENT")
    if not sec["p2a_rank_preserved"].astype(bool).all(): failures.append("P2A_RANK_NOT_PRESERVED")

    blocked = sec[sec["decision_state"] == "HOLD_RETAINED_INVESTMENT_BLOCKER"].copy()
    advance = sec[sec["decision_state"] != "HOLD_RETAINED_INVESTMENT_BLOCKER"].copy()
    exp = contract["expected_result"]
    if len(advance) != int(exp["advance_security_count"]): failures.append(f"ADVANCE_SECURITY_COUNT:{len(advance)}")
    if len(blocked) != int(exp["blocked_security_count"]): failures.append(f"BLOCKED_SECURITY_COUNT:{len(blocked)}")
    if set(blocked["security_id"]) != set(exp["retained_blocker_security_ids"]): failures.append("RETAINED_BLOCKER_SECURITY_SET")

    dim_path = out / "HKCU_P2B_E2_S1_TOP20_DIMENSION_DECISION_SURFACE.csv"
    sec_path = out / "HKCU_P2B_E2_S1_TOP20_SECURITY_DECISION_SYNTHESIS.csv"
    blocker_path = out / "HKCU_P2B_E2_S1_RETAINED_INVESTMENT_BLOCKERS.csv"
    dim.to_csv(dim_path, index=False)
    sec.to_csv(sec_path, index=False)
    blocked.to_csv(blocker_path, index=False)

    decision = {
        "program_id": PROGRAM_ID,
        "phase": contract["phase"],
        "status": "PASS_P2B_E2_TOP20_DECISION_SYNTHESIS" if not failures else "BLOCKED_P2B_E2_TOP20_DECISION_SYNTHESIS",
        "security_count": int(len(sec)),
        "dimension_rows": int(len(dim)),
        "advance_security_count": int(len(advance)),
        "blocked_security_count": int(len(blocked)),
        "blocked_security_ids": blocked["security_id"].tolist(),
        "score_non_null_count": 0,
        "formal_candidate_graduation_allowed": False,
        "candidate_pool_mutations": 0,
        "simulation_mutations": 0,
        "real_account_mutations": 0,
        "orders_created": 0,
        "next_gate": contract["next_gate"],
        "trade_authority": TRADE_AUTHORITY,
    }
    quality = {
        "program_id": PROGRAM_ID,
        "status": "PASS" if not failures else "FAIL",
        "hard_failures": sorted(set(failures)),
        "p2a_rank_preserved_not_rescored": True,
        "missing_consensus_is_not_bearish": True,
        "direct_negative_complete_signal_guard": True,
        "formal_candidate_graduation_allowed": False,
        "trade_authority": TRADE_AUTHORITY,
    }
    decision_path = out / "HKCU_P2B_E2_S1_DECISION.json"
    quality_path = out / "HKCU_P2B_E2_S1_QUALITY_REPORT.json"
    write_json(decision_path, decision)
    write_json(quality_path, quality)

    report_lines = [
        "# HKCU P2B-E2 Top20 Decision Synthesis",
        "",
        f"Status: **{decision['status']}**",
        "",
        f"- Top20 securities: {len(sec)}",
        f"- Advance with confidence cap: {len(advance)}",
        f"- Retained investment blockers: {len(blocked)}",
        "- Alpha scores: 0",
        "- Formal Candidate graduation: not allowed",
        "",
        "## Security decision surface",
        "",
        "| Rank | Code | Security | Decision state | Blockers | Confidence cap |",
        "|---:|---|---|---|---:|---|",
    ]
    for r in sec.itertuples(index=False):
        report_lines.append(f"| {r.p2a_overall_rank} | {r.stock_code_5d} | {r.security_name} | {r.decision_state} | {r.retained_blocker_count} | {r.confidence_cap} |")
    report_lines += ["", "## Boundary", "", "This synthesis is research-readiness output only. It does not create an alpha score, formal HK Candidate graduation, portfolio mutation or order.", ""]
    report_path = out / "HKCU_P2B_E2_S1_TOP20_DECISION_SYNTHESIS.md"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")

    manifest = {"program_id": PROGRAM_ID, "as_of_date": sel["as_of_date"], "files": {}, "trade_authority": TRADE_AUTHORITY}
    for p in [dim_path, sec_path, blocker_path, decision_path, quality_path, report_path]:
        manifest["files"][p.name] = {"sha256": sha256_file(p), "bytes": p.stat().st_size}
    write_json(out / "HKCU_P2B_E2_S1_MANIFEST.json", manifest)

    if failures:
        raise SystemExit("P2B_E2_S1_BUILD_FAILED:" + "|".join(sorted(set(failures))))
    print(json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--repo-root", default=".")
    p.add_argument("--output", required=True)
    args = p.parse_args()
    build(Path(args.repo_root).resolve(), Path(args.output).resolve())


if __name__ == "__main__":
    main()
