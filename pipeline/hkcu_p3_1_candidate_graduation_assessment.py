#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any

import pandas as pd

PROGRAM_ID = "HKCU-P3-1"
TRADE_AUTHORITY = "NONE"
DIMS = ("GOVERNANCE_VALUE_TRAP", "EARNINGS_EXPECTATION_REVISION", "CATALYST")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def as_bool(value: Any) -> bool:
    return value is True or str(value).strip().lower() in {"1", "true", "yes", "y"}


def finite(value: Any) -> float | None:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def rebuild_p2b_final(root: Path, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            sys.executable,
            str(root / "pipeline/hkcu_p2b_final_cross_sectional_synthesis.py"),
            "--repo-root",
            str(root),
            "--output",
            str(out),
        ],
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            str(root / "scripts/validate_hkcu_p2b_final_cross_sectional_synthesis.py"),
            "--output",
            str(out),
        ],
        check=True,
    )


def valuation_support(row: pd.Series) -> tuple[str, bool, str]:
    ey = finite(row.get("earnings_yield"))
    pe = finite(row.get("pe_ratio"))
    dy = finite(row.get("dividend_yield_365d"))
    observed = [x for x in (ey, pe, dy) if x is not None]
    if not observed:
        return "MISSING", False, "No accepted earnings-yield, P/E or dividend-yield observation is available; valuation cannot be neutral-filled."
    if (ey is not None and ey > 0) or (dy is not None and dy > 0):
        note = f"Accepted valuation context: earnings_yield={ey}, pe_ratio={pe}, dividend_yield_365d={dy}."
        return "SUPPORTIVE", True, note
    if pe is not None and pe > 0:
        note = f"Accepted valuation context is limited rather than absent: earnings_yield={ey}, pe_ratio={pe}, dividend_yield_365d={dy}."
        return "LIMITED", True, note
    note = f"Accepted valuation fields are present but do not provide positive support: earnings_yield={ey}, pe_ratio={pe}, dividend_yield_365d={dy}."
    return "ADVERSE_OR_UNUSABLE", False, note


def choose_dimension(grp: pd.DataFrame, directions: set[str]) -> pd.Series | None:
    priority = {"EARNINGS_EXPECTATION_REVISION": 0, "CATALYST": 1, "GOVERNANCE_VALUE_TRAP": 2}
    x = grp[grp["final_direction"].astype(str).isin(directions)].copy()
    if x.empty:
        return None
    x["_priority"] = x["research_dimension"].map(priority).fillna(9)
    x = x.sort_values(["_priority", "research_dimension"])
    return x.iloc[0]


def thesis_package(grp: pd.DataFrame, sec_row: pd.Series) -> tuple[str, str, str, str]:
    positive = choose_dimension(grp, {"POSITIVE"})
    mixed = choose_dimension(grp, {"MIXED"})
    negative = choose_dimension(grp, {"NEGATIVE"})
    primary_sleeve = str(sec_row.get("primary_sleeve") or "UNSPECIFIED")
    if positive is not None:
        thesis = (
            f"P2A primary sleeve={primary_sleeve}; accepted {positive['research_dimension']} evidence is positive: "
            f"{positive['final_finding']}."
        )
        strength = "COMPANY_EVIDENCE_SUPPORTED"
    elif mixed is not None:
        thesis = (
            f"P2A primary sleeve={primary_sleeve}; accepted {mixed['research_dimension']} evidence is mixed and requires disciplined monitoring: "
            f"{mixed['final_finding']}."
        )
        strength = "MIXED_COMPANY_EVIDENCE"
    else:
        first = grp.sort_values("research_dimension").iloc[0]
        thesis = (
            f"P2A primary sleeve={primary_sleeve} remains the quantitative research rationale; company-specific evidence is not positive enough to strengthen it. "
            f"Current reference finding: {first['final_finding']}."
        )
        strength = "QUANTITATIVE_ONLY_WITH_COMPANY_MONITOR"

    if negative is not None:
        falsifier = f"Principal downside/falsifier: {negative['research_dimension']} negative finding — {negative['final_finding']}."
    else:
        cap = grp[grp["final_dimension_state"].astype(str).isin({"TARGETED_DEEPENING_REQUIRED", "LIMITED_CONFIDENCE", "CONFIDENCE_CAP_MONITOR"})]
        if not cap.empty:
            r = cap.iloc[0]
            needed = str(r.get("next_required_evidence") or "")
            falsifier = f"Principal downside/falsifier: unresolved {r['research_dimension']} uncertainty; required evidence: {needed}."
        else:
            r = grp.iloc[0]
            falsifier = f"Principal downside/falsifier: a new adverse issuer disclosure that invalidates the accepted {r['research_dimension']} finding."

    triggers = []
    for x in grp["monitor_trigger"].astype(str).tolist():
        x = x.strip()
        if x and x.lower() not in {"nan", "none"} and x not in triggers:
            triggers.append(x)
    monitor = " | ".join(triggers[:3])
    return thesis, falsifier, monitor, strength


def rule_row(
    security_id: str,
    stock_code_5d: str,
    security_name: str,
    rank: int,
    rule: dict[str, Any],
    state: str,
    rationale: str,
) -> dict[str, Any]:
    return {
        "p2a_overall_rank": rank,
        "security_id": security_id,
        "stock_code_5d": stock_code_5d,
        "security_name": security_name,
        "rule_id": rule["rule_id"],
        "rule_name": rule["name"],
        "rule_type": rule["type"],
        "applicability": rule["applicability"],
        "rule_state": state,
        "rationale": rationale,
        "alpha_score": pd.NA,
        "formal_candidate_graduation": False,
        "trade_authority": TRADE_AUTHORITY,
    }


def build(root: Path, out: Path) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    contract_path = root / "config/hkcu_p3_1_candidate_graduation_assessment_contract.json"
    contract = read_json(contract_path)
    p3_0 = read_json(root / contract["authoritative_inputs"]["p3_0_contract"])
    failures: list[str] = []

    entry = contract["entry_contract"]
    p3_accept = p3_0["acceptance"]
    if p3_0.get("program_id") != entry["required_p3_0_program_id"]:
        failures.append("P3_0_PROGRAM_ID")
    if p3_accept.get("pass_status") != entry["required_p3_0_pass_status"]:
        failures.append("P3_0_PASS_STATUS")
    if p3_accept.get("next_gate") != entry["required_p3_0_next_gate"]:
        failures.append("P3_0_NEXT_GATE")
    if len(p3_0.get("graduation_rules", [])) != int(entry["graduation_rule_count"]):
        failures.append("P3_0_RULE_COUNT")

    upstream = out / "_p2b_final_rebuild"
    rebuild_p2b_final(root, upstream)
    decision = read_json(upstream / "HKCU_P2B_FINAL_DECISION.json")
    if decision.get("status") != "PASS_P2B_FINAL_CROSS_SECTIONAL_SYNTHESIS":
        failures.append("P2B_FINAL_NOT_PASS")

    sec = pd.read_csv(
        upstream / "HKCU_P2B_FINAL_SECURITY_CROSS_SECTION.csv",
        dtype={"stock_code_5d": str},
        keep_default_na=False,
    )
    dim = pd.read_csv(
        upstream / "HKCU_P2B_FINAL_COMPANY_DIMENSION_SURFACE.csv",
        dtype={"stock_code_5d": str},
        keep_default_na=False,
    )
    hkcu = pd.read_csv(
        root / contract["authoritative_inputs"]["hkcu_current"],
        dtype={"stock_code_5d": str},
        keep_default_na=False,
        encoding="utf-8-sig",
    )
    sec["stock_code_5d"] = sec["stock_code_5d"].astype(str).str.zfill(5)
    dim["stock_code_5d"] = dim["stock_code_5d"].astype(str).str.zfill(5)

    if len(sec) != int(entry["entry_security_count"]):
        failures.append(f"SECURITY_COUNT:{len(sec)}")
    if sec["security_id"].duplicated().any():
        failures.append("DUPLICATE_SECURITY")
    if len(dim) != int(entry["entry_security_count"]) * len(DIMS):
        failures.append(f"DIMENSION_ROWS:{len(dim)}")
    if dim.duplicated(["security_id", "research_dimension"]).any():
        failures.append("DUPLICATE_DIMENSION")
    if set(dim["research_dimension"]) != set(DIMS):
        failures.append("DIMENSION_VOCABULARY")

    hkcu_map = hkcu.set_index("security_id", drop=False)
    missing_hkcu = sorted(set(sec["security_id"]) - set(hkcu_map.index))
    if missing_hkcu:
        failures.append("HKCU_MEMBERSHIP_MISSING:" + ",".join(missing_hkcu))

    blocked_ids = set(entry["retained_blocker_security_ids"])
    observed_blocked = set(sec.loc[sec["retained_blocker"].map(as_bool), "security_id"])
    if observed_blocked != blocked_ids:
        failures.append("BLOCKER_SET_MISMATCH")

    rules = {r["rule_id"]: r for r in p3_0["graduation_rules"]}
    if set(rules) != {f"P3R{i:02d}" for i in range(1, 13)}:
        failures.append("RULE_ID_SET")

    rule_rows: list[dict[str, Any]] = []
    security_rows: list[dict[str, Any]] = []
    material_states = set(contract["confidence_policy"]["material_cap_states"])
    bounded_states = set(contract["confidence_policy"]["bounded_cap_states"])
    neutral_unknown = set(contract["confidence_policy"]["neutral_unknown_directions"])

    for s in sec.sort_values("p2a_overall_rank").itertuples(index=False):
        sid = str(s.security_id)
        rank = int(s.p2a_overall_rank)
        code = str(s.stock_code_5d).zfill(5)
        name = str(s.security_name)
        g = dim[dim["security_id"].eq(sid)].copy()
        if len(g) != 3:
            failures.append(f"SECURITY_DIMENSION_COUNT:{sid}:{len(g)}")
            continue
        if sid not in hkcu_map.index:
            continue
        h = hkcu_map.loc[sid]
        h = h.iloc[0] if isinstance(h, pd.DataFrame) else h

        retained = as_bool(getattr(s, "retained_blocker"))
        publication = as_bool(h.get("publication_eligible"))
        buy_eligible = as_bool(h.get("buy_eligible"))
        sell_only = as_bool(h.get("sell_only"))
        investability = str(h.get("investability_status") or "")
        freshness = str(h.get("freshness_status") or "")
        elig_date = str(h.get("eligibility_as_of_date") or "")
        factor_date = str(h.get("fmdl5e_as_of_date") or "")
        txn_complete = str(getattr(s, "transaction_tax_evidence_status")) == "EVIDENCE_COMPLETE"
        all_dims_synth = (
            set(g["research_dimension"]) == set(DIMS)
            and not g["upstream_evidence_status"].astype(str).eq("RESEARCH_REQUIRED").any()
            and g["final_dimension_state"].astype(str).str.len().gt(0).all()
        )
        gov = g[g["research_dimension"].eq("GOVERNANCE_VALUE_TRAP")].iloc[0]
        earn = g[g["research_dimension"].eq("EARNINGS_EXPECTATION_REVISION")].iloc[0]
        gov_ok = not as_bool(gov["final_blocker"])
        earn_ok = not as_bool(earn["final_blocker"])
        investability_ok = investability in {"ELIGIBLE_CORE", "ELIGIBLE_WATCH"}
        fresh_ok = freshness == "CURRENT" and elig_date == contract["as_of_date"] and factor_date == contract["as_of_date"]
        liquidity_ok = investability_ok
        valuation_state, valuation_pass, valuation_note = valuation_support(pd.Series(s._asdict()))
        thesis, falsifier, monitor, thesis_strength = thesis_package(g, pd.Series(s._asdict()))
        thesis_pass = all(bool(str(x).strip()) for x in (thesis, falsifier, monitor))

        ah_pair = str(getattr(s, "ah_pair_status"))
        if ah_pair == "TRUE_AH_PAIR":
            ah_state = "PASS"
            rv_dir = str(getattr(s, "ah_relative_value_direction"))
            discount = finite(getattr(s, "h_discount_to_a_pct"))
            ah_review = (
                f"Confirmed same-issuer A/H pair reviewed. relative_value_direction={rv_dir}, "
                f"h_discount_to_a_pct={discount}. Spread is context only and not alpha."
            )
        else:
            ah_state = "NOT_APPLICABLE"
            ah_review = "No confirmed A/H pair is present in accepted P2B Final; no cross-listing exposure is invented."

        hard_eval = {
            "P3R01": (True, "Accepted P2B Final lineage is present and P2A rank is preserved without re-scoring."),
            "P3R02": (not retained, "No retained blocker." if not retained else "Exact P2B Final retained investment blocker remains."),
            "P3R03": (
                publication and buy_eligible and not sell_only and investability_ok,
                f"publication_eligible={publication}; buy_eligible={buy_eligible}; sell_only={sell_only}; investability_status={investability}.",
            ),
            "P3R04": (
                fresh_ok,
                f"freshness_status={freshness}; eligibility_as_of_date={elig_date}; fmdl5e_as_of_date={factor_date}; required={contract['as_of_date']}.",
            ),
            "P3R05": (txn_complete, f"transaction_tax_evidence_status={getattr(s, 'transaction_tax_evidence_status')}."),
            "P3R06": (all_dims_synth, "All three company dimensions have accepted synthesis and no RESEARCH_REQUIRED residue."),
            "P3R07": (gov_ok, f"governance final_blocker={as_bool(gov['final_blocker'])}; finding={gov['final_finding']}."),
            "P3R08": (earn_ok, f"earnings final_blocker={as_bool(earn['final_blocker'])}; finding={earn['final_finding']}."),
            "P3R09": (liquidity_ok, f"Accepted HKCU/P2A investability remains {investability}; no lower Phase-3 threshold is invented."),
        }
        decision_eval = {
            "P3R10": (valuation_pass, f"{valuation_state}: {valuation_note}"),
            "P3R11": (thesis_pass, f"thesis={thesis} | falsifier={falsifier} | monitor={monitor}"),
        }

        for rid in [f"P3R{i:02d}" for i in range(1, 10)]:
            passed, rationale = hard_eval[rid]
            rule_rows.append(rule_row(sid, code, name, rank, rules[rid], "PASS" if passed else "FAIL", rationale))
        for rid in ("P3R10", "P3R11"):
            passed, rationale = decision_eval[rid]
            rule_rows.append(rule_row(sid, code, name, rank, rules[rid], "PASS" if passed else "FAIL", rationale))
        rule_rows.append(rule_row(sid, code, name, rank, rules["P3R12"], ah_state, ah_review))

        hard_pass = all(x[0] for x in hard_eval.values())
        decision_pass = all(x[0] for x in decision_eval.values()) and ah_state in {"PASS", "NOT_APPLICABLE"}
        material_cap_count = int(g["final_dimension_state"].astype(str).isin(material_states).sum())
        bounded_cap_count = int(g["final_dimension_state"].astype(str).isin(bounded_states).sum())
        positive_count = int(g["final_direction"].astype(str).eq("POSITIVE").sum())
        negative_count = int(g["final_direction"].astype(str).eq("NEGATIVE").sum())
        mixed_count = int(g["final_direction"].astype(str).eq("MIXED").sum())
        neutral_unknown_count = int(g["final_direction"].astype(str).isin(neutral_unknown).sum())

        if retained:
            proposal = "HOLD_RETAINED_INVESTMENT_BLOCKER"
            proposal_reason = "P2B Final retained blocker is preserved; no Phase-3 rule can waive it."
        elif not hard_pass or not decision_pass or material_cap_count > 0:
            proposal = "DEFER_RESEARCH_MONITOR"
            reasons = []
            if not hard_pass:
                reasons.append("one_or_more_hard_rules_failed")
            if not decision_pass:
                reasons.append("one_or_more_decision_rules_failed")
            if material_cap_count:
                reasons.append(f"material_confidence_caps={material_cap_count}")
            proposal_reason = "; ".join(reasons)
        elif (
            valuation_state == "SUPPORTIVE"
            and bounded_cap_count == 0
            and negative_count == 0
            and positive_count >= 1
        ):
            proposal = "PROPOSE_CORE_CANDIDATE"
            proposal_reason = "All applicable rules pass with supportive valuation, positive company evidence and no retained/material/bounded confidence cap."
        else:
            proposal = "PROPOSE_WATCH_CANDIDATE"
            proposal_reason = (
                "All applicable rules pass, but bounded uncertainty, mixed/neutral evidence, event timing or limited valuation support warrants Watch rather than Core."
            )

        security_rows.append(
            {
                "p2a_overall_rank": rank,
                "security_id": sid,
                "stock_code_5d": code,
                "security_name": name,
                "primary_sleeve": str(getattr(s, "primary_sleeve", "")),
                "p2b_evidence_balance": str(getattr(s, "evidence_balance", "")),
                "valuation_support_state": valuation_state,
                "valuation_support_note": valuation_note,
                "thesis_strength": thesis_strength,
                "investment_thesis": thesis,
                "principal_falsifier": falsifier,
                "monitor_triggers": monitor,
                "ah_pair_status": ah_pair,
                "ah_relative_value_direction": str(getattr(s, "ah_relative_value_direction", "")),
                "h_discount_to_a_pct": getattr(s, "h_discount_to_a_pct", ""),
                "cross_listing_review": ah_review,
                "positive_dimension_count": positive_count,
                "negative_dimension_count": negative_count,
                "mixed_dimension_count": mixed_count,
                "neutral_unknown_dimension_count": neutral_unknown_count,
                "material_confidence_cap_count": material_cap_count,
                "bounded_confidence_cap_count": bounded_cap_count,
                "all_applicable_hard_rules_pass": hard_pass,
                "all_applicable_decision_rules_pass": decision_pass,
                "proposal_state": proposal,
                "proposal_reason": proposal_reason,
                "formal_candidate_graduation": False,
                "candidate_pool_mutation": False,
                "alpha_score": pd.NA,
                "trade_authority": TRADE_AUTHORITY,
            }
        )

    assessments = pd.DataFrame(security_rows).sort_values("p2a_overall_rank").reset_index(drop=True)
    rule_surface = pd.DataFrame(rule_rows).sort_values(["p2a_overall_rank", "rule_id"]).reset_index(drop=True)

    if len(assessments) != int(contract["acceptance"]["security_assessment_count"]):
        failures.append(f"ASSESSMENT_COUNT:{len(assessments)}")
    if len(rule_surface) != int(contract["acceptance"]["rule_assessment_row_count"]):
        failures.append(f"RULE_ASSESSMENT_COUNT:{len(rule_surface)}")
    if rule_surface.duplicated(["security_id", "rule_id"]).any():
        failures.append("DUPLICATE_RULE_ASSESSMENT")
    if not set(rule_surface["rule_state"]).issubset(set(contract["rule_states"])):
        failures.append("RULE_STATE_VOCABULARY")
    if not set(assessments["proposal_state"]).issubset(set(contract["proposal_states"])):
        failures.append("PROPOSAL_STATE_VOCABULARY")

    blocked = assessments[assessments["proposal_state"].eq("HOLD_RETAINED_INVESTMENT_BLOCKER")]
    if set(blocked["security_id"]) != blocked_ids:
        failures.append("P3_1_BLOCKER_SET")
    if len(blocked) != int(entry["retained_blocker_security_count"]):
        failures.append(f"P3_1_BLOCKER_COUNT:{len(blocked)}")
    if assessments["formal_candidate_graduation"].map(as_bool).any():
        failures.append("FORMAL_GRADUATION_OCCURRED")
    if assessments["candidate_pool_mutation"].map(as_bool).any():
        failures.append("CANDIDATE_MUTATION_OCCURRED")
    if assessments["alpha_score"].notna().any():
        failures.append("ALPHA_SCORE_PRESENT")
    if not assessments["trade_authority"].eq(TRADE_AUTHORITY).all():
        failures.append("TRADE_AUTHORITY_MUTATION")

    prefix = contract["output_prefix"]
    assessment_path = out / f"{prefix}_SECURITY_ASSESSMENT.csv"
    rule_path = out / f"{prefix}_RULE_ASSESSMENT.csv"
    blocker_path = out / f"{prefix}_RETAINED_BLOCKERS.csv"
    assessment_path.write_text(assessments.to_csv(index=False), encoding="utf-8")
    rule_path.write_text(rule_surface.to_csv(index=False), encoding="utf-8")
    blocker_path.write_text(blocked.to_csv(index=False), encoding="utf-8")

    counts = assessments["proposal_state"].value_counts().astype(int).to_dict()
    dec = {
        "program_id": PROGRAM_ID,
        "phase": contract["phase"],
        "status": contract["acceptance"]["pass_status"] if not failures else contract["acceptance"]["blocked_status"],
        "security_assessment_count": int(len(assessments)),
        "rule_assessment_row_count": int(len(rule_surface)),
        "proposal_state_counts": counts,
        "retained_blocker_security_count": int(len(blocked)),
        "retained_blocker_security_ids": sorted(blocked["security_id"].tolist()),
        "formal_candidate_graduation_count": 0,
        "candidate_pool_mutations": 0,
        "simulation_mutations": 0,
        "real_account_mutations": 0,
        "orders_created": 0,
        "alpha_score_non_null_count": 0,
        "next_gate": contract["acceptance"]["next_gate"] if not failures else None,
        "trade_authority": TRADE_AUTHORITY,
    }
    quality = {
        "program_id": PROGRAM_ID,
        "status": "PASS" if not failures else "FAIL",
        "hard_failures": sorted(set(failures)),
        "p3_0_contract_bound": True,
        "p2b_final_real_rebuild_and_independent_validation": True,
        "all_77_securities_assessed": len(assessments) == 77,
        "all_12_rules_materialized_per_security": len(rule_surface) == 77 * 12,
        "no_weighted_score": True,
        "no_neutral_fill": True,
        "no_automatic_waiver": True,
        "no_fixed_top_n": True,
        "missing_consensus_is_not_bearish": True,
        "ah_relative_value_is_context_not_alpha": True,
        "formal_candidate_graduation_count": 0,
        "candidate_pool_mutations": 0,
        "trade_authority": TRADE_AUTHORITY,
    }
    decision_path = out / f"{prefix}_DECISION.json"
    quality_path = out / f"{prefix}_QUALITY_REPORT.json"
    write_json(decision_path, dec)
    write_json(quality_path, quality)

    report_lines = [
        "# HKCU P3-1 Candidate Graduation Assessment",
        "",
        f"Status: **{dec['status']}**",
        "",
        f"- Security assessments: {len(assessments)}",
        f"- Rule assessments: {len(rule_surface)}",
        f"- Core proposals: {counts.get('PROPOSE_CORE_CANDIDATE', 0)}",
        f"- Watch proposals: {counts.get('PROPOSE_WATCH_CANDIDATE', 0)}",
        f"- Deferred research monitors: {counts.get('DEFER_RESEARCH_MONITOR', 0)}",
        f"- Retained blockers: {counts.get('HOLD_RETAINED_INVESTMENT_BLOCKER', 0)}",
        "- Formal Candidate promotions: 0",
        "- Candidate Pool mutations: 0",
        "",
        "| Rank | Code | Security | Proposal | Valuation | Material caps | Bounded caps |",
        "|---:|---|---|---|---|---:|---:|",
    ]
    for r in assessments.itertuples(index=False):
        report_lines.append(
            f"| {r.p2a_overall_rank} | {r.stock_code_5d} | {r.security_name} | {r.proposal_state} | "
            f"{r.valuation_support_state} | {r.material_confidence_cap_count} | {r.bounded_confidence_cap_count} |"
        )
    report_lines += [
        "",
        "## Boundary",
        "",
        "P3-1 is assessment-only. Proposal states are not formal Candidate Pool membership, portfolio allocation, simulation positions, real-account positions or trade authority.",
        "",
    ]
    report_path = out / f"{prefix}_ASSESSMENT.md"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")

    manifest = {
        "program_id": PROGRAM_ID,
        "as_of_date": contract["as_of_date"],
        "contract_sha256": sha256_file(contract_path),
        "p3_0_contract_sha256": sha256_file(root / contract["authoritative_inputs"]["p3_0_contract"]),
        "files": {},
        "upstream_p2b_final_decision_sha256": sha256_file(upstream / "HKCU_P2B_FINAL_DECISION.json"),
        "trade_authority": TRADE_AUTHORITY,
    }
    for p in [assessment_path, rule_path, blocker_path, decision_path, quality_path, report_path]:
        manifest["files"][p.name] = {"sha256": sha256_file(p), "bytes": p.stat().st_size}
    write_json(out / f"{prefix}_MANIFEST.json", manifest)

    if failures:
        raise SystemExit("P3_1_BUILD_FAILED:" + "|".join(sorted(set(failures))))
    print(json.dumps(dec, ensure_ascii=False, indent=2, sort_keys=True))
    return dec


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--repo-root", default=".")
    p.add_argument("--output", required=True)
    args = p.parse_args()
    build(Path(args.repo_root).resolve(), Path(args.output).resolve())


if __name__ == "__main__":
    main()
