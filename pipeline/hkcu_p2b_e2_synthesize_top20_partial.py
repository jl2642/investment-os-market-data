#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd

PROGRAM_ID = "HKCU-P2B-E2-D2"
TRADE_AUTHORITY = "NONE"
AS_OF = pd.Timestamp("2026-08-07")
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


def rebuild_d1(root: Path, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        sys.executable,
        str(root / "pipeline/hkcu_p2b_e2_deepen_negative_catalyst.py"),
        "--repo-root", str(root),
        "--output", str(out),
    ], check=True)
    subprocess.run([
        sys.executable,
        str(root / "scripts/validate_hkcu_p2b_e2_deepening_d1.py"),
        "--output", str(out),
    ], check=True)


def contains(text: str, *tokens: str) -> bool:
    t = text.lower()
    return any(token.lower() in t for token in tokens)


def governance_synthesis(title: str, summary: str) -> dict:
    text = f"{title} {summary}"
    if contains(text, "auditor", "核数师"):
        return {
            "evidence_sufficiency": "TARGETED_DEEPENING_REQUIRED",
            "finding_direction": "MIXED",
            "materiality": "HIGH",
            "graduation_blocker": True,
            "finding": "AUDITOR_CHANGE_OR_AUDIT_GOVERNANCE_EVENT",
            "counterevidence_needed": "Audit-change rationale, predecessor/successor auditor statements, control findings and audit-committee oversight.",
            "monitor_trigger": "Auditor transition disclosures, qualified opinion/control finding, or additional audit-committee change.",
        }
    if contains(text, "connected transaction", "continuing connected", "related-party", "related party"):
        return {
            "evidence_sufficiency": "TARGETED_DEEPENING_REQUIRED",
            "finding_direction": "MIXED",
            "materiality": "HIGH",
            "graduation_blocker": True,
            "finding": "RELATED_PARTY_OR_CONNECTED_TRANSACTION_REVIEW_REQUIRED",
            "counterevidence_needed": "Pricing/fairness basis, independent-board opinion, transaction caps, economic materiality and recurring exposure.",
            "monitor_trigger": "New connected transaction, cap increase, independent-board objection or material completion update.",
        }
    if contains(text, "cfo", "ceo", "chief executive", "chairman", "senior-management", "senior management"):
        return {
            "evidence_sufficiency": "TARGETED_DEEPENING_REQUIRED",
            "finding_direction": "NEUTRAL",
            "materiality": "MEDIUM",
            "graduation_blocker": True,
            "finding": "SENIOR_LEADERSHIP_TRANSITION",
            "counterevidence_needed": "Succession plan, tenure/independence, strategic continuity and control-accountability evidence.",
            "monitor_trigger": "Successor appointment, strategy reset, control remediation or additional senior departure.",
        }
    if contains(text, "ined", "independent", "director", "committee", "board change", "board/committee"):
        return {
            "evidence_sufficiency": "LIMITED_CONFIDENCE",
            "finding_direction": "NEUTRAL",
            "materiality": "MEDIUM",
            "graduation_blocker": False,
            "finding": "BOARD_OR_COMMITTEE_CHANGE_MONITOR",
            "counterevidence_needed": "Board independence, committee composition and subsequent governance effectiveness evidence.",
            "monitor_trigger": "Further director turnover, committee reconstitution or governance-control disclosure.",
        }
    return {
        "evidence_sufficiency": "SUFFICIENT_FOR_PRELIMINARY_DECISION",
        "finding_direction": "NEUTRAL",
        "materiality": "LOW",
        "graduation_blocker": False,
        "finding": "NO_SPECIFIC_HIGH_MATERIALITY_GOVERNANCE_RED_FLAG_IN_CAPTURED_EVENT",
        "counterevidence_needed": "Continue routine annual governance and capital-allocation monitoring.",
        "monitor_trigger": "New auditor, related-party, control, board or capital-allocation event.",
    }


def earnings_synthesis(title: str, summary: str, evidence_date: str) -> dict:
    text = f"{title} {summary}"
    date = pd.to_datetime(evidence_date, errors="coerce")
    age = 9999 if pd.isna(date) else int((AS_OF - date).days)
    direct_tokens = ("profit alert", "profit warning", "profit increase", "estimated results", "results forecast")
    if contains(text, *direct_tokens):
        # Defensive guard: a partial row should not contain direct expectation-change evidence.
        return {
            "evidence_sufficiency": "TARGETED_DEEPENING_REQUIRED",
            "finding_direction": "UNKNOWN",
            "materiality": "HIGH",
            "graduation_blocker": True,
            "finding": "DIRECT_EXPECTATION_SIGNAL_MISCLASSIFIED_UPSTREAM",
            "counterevidence_needed": "Reconcile upstream evidence status and issuer expectation-change disclosure.",
            "monitor_trigger": "Upstream evidence-status correction.",
        }
    current_update = contains(text, "first quarter", "q1", "q2", "h1", "interim management", "operational update", "business update", "quarterly statement", "financial and business review", "traffic figures")
    if current_update or age <= 100:
        return {
            "evidence_sufficiency": "LIMITED_CONFIDENCE",
            "finding_direction": "UNKNOWN",
            "materiality": "MEDIUM",
            "graduation_blocker": False,
            "finding": "CURRENT_OPERATING_EVIDENCE_WITHOUT_RELIABLE_REVISION_SERIES",
            "counterevidence_needed": "Reliable dated consensus revisions or explicit management guidance; trailing/actual results must not substitute.",
            "monitor_trigger": "Next results/guidance release or reliable consensus-revision update.",
        }
    return {
        "evidence_sufficiency": "TARGETED_DEEPENING_REQUIRED",
        "finding_direction": "UNKNOWN",
        "materiality": "MEDIUM",
        "graduation_blocker": True,
        "finding": "STALE_OR_ANNUAL_ONLY_OPERATING_EVIDENCE_NO_DIRECT_REVISION_SERIES",
        "counterevidence_needed": "Current-period operating update, explicit management guidance, or reliable dated consensus revisions.",
        "monitor_trigger": "Current-period results/guidance or consensus-revision evidence.",
    }


def catalyst_synthesis(title: str, summary: str) -> dict:
    text = f"{title} {summary}"
    if contains(text, "profit increase", "positive profit"):
        return {
            "evidence_sufficiency": "SUFFICIENT_FOR_PRELIMINARY_DECISION",
            "finding_direction": "POSITIVE",
            "materiality": "HIGH",
            "graduation_blocker": False,
            "finding": "ACTIVE_POSITIVE_EARNINGS_CATALYST",
            "counterevidence_needed": "Magnitude, quality, one-off contribution and valuation response.",
            "monitor_trigger": "Formal interim/final result and management explanation of profit drivers.",
        }
    if contains(text, "profit warning"):
        return {
            "evidence_sufficiency": "SUFFICIENT_FOR_PRELIMINARY_DECISION",
            "finding_direction": "NEGATIVE",
            "materiality": "HIGH",
            "graduation_blocker": True,
            "finding": "ACTIVE_NEGATIVE_EARNINGS_CATALYST",
            "counterevidence_needed": "Magnitude, one-off versus structural drivers and recovery evidence.",
            "monitor_trigger": "Formal results and evidence that warning drivers are reversing.",
        }
    if contains(text, "spin-off", "spin off", "listing application", "proposed subsidiary listing", "distribution in specie"):
        return {
            "evidence_sufficiency": "TARGETED_DEEPENING_REQUIRED",
            "finding_direction": "MIXED",
            "materiality": "HIGH",
            "graduation_blocker": True,
            "finding": "ACTIVE_SPINOFF_OR_LISTING_EVENT",
            "counterevidence_needed": "Transaction structure, ownership retained, timetable, valuation, distribution mechanics and completion conditions.",
            "monitor_trigger": "Listing approval, prospectus/terms, completion or withdrawal.",
        }
    if contains(text, "disposal", "acquisition", "transaction", "sell singapore", "sale of"):
        return {
            "evidence_sufficiency": "TARGETED_DEEPENING_REQUIRED",
            "finding_direction": "MIXED",
            "materiality": "HIGH",
            "graduation_blocker": True,
            "finding": "ACTIVE_STRATEGIC_TRANSACTION",
            "counterevidence_needed": "Consideration, valuation/fairness, completion conditions, proceeds use and earnings impact.",
            "monitor_trigger": "Completion, termination, regulatory approval or quantified proceeds/earnings effect.",
        }
    if contains(text, "traffic figures", "operational update", "monthly revenue", "business update"):
        return {
            "evidence_sufficiency": "LIMITED_CONFIDENCE",
            "finding_direction": "UNKNOWN",
            "materiality": "MEDIUM",
            "graduation_blocker": False,
            "finding": "RECURRING_OPERATING_CATALYST_SERIES",
            "counterevidence_needed": "Trend versus prior period, margin/earnings translation and management guidance.",
            "monitor_trigger": "Next operating update and formal results.",
        }
    if contains(text, "board meeting", "date of board meeting"):
        return {
            "evidence_sufficiency": "LIMITED_CONFIDENCE",
            "finding_direction": "NEUTRAL",
            "materiality": "LOW",
            "graduation_blocker": False,
            "finding": "ROUTINE_RESULTS_CYCLE_TRIGGER",
            "counterevidence_needed": "Actual results and surprise magnitude.",
            "monitor_trigger": "Results publication following the board meeting.",
        }
    if contains(text, "buyback", "repurchase", "share repurchase"):
        return {
            "evidence_sufficiency": "LIMITED_CONFIDENCE",
            "finding_direction": "POSITIVE",
            "materiality": "LOW",
            "graduation_blocker": False,
            "finding": "CAPITAL_RETURN_SIGNAL",
            "counterevidence_needed": "Repurchase scale, pace, valuation discipline and cancellation/treasury treatment.",
            "monitor_trigger": "Material acceleration/cessation of buybacks or capital-return policy change.",
        }
    if contains(text, "completion"):
        return {
            "evidence_sufficiency": "LIMITED_CONFIDENCE",
            "finding_direction": "NEUTRAL",
            "materiality": "LOW",
            "graduation_blocker": False,
            "finding": "EVENT_LARGELY_COMPLETED_LIMITED_FORWARD_CATALYST",
            "counterevidence_needed": "Post-completion economic impact and next unresolved event.",
            "monitor_trigger": "Post-completion financial impact or new corporate action.",
        }
    return {
        "evidence_sufficiency": "LIMITED_CONFIDENCE",
        "finding_direction": "UNKNOWN",
        "materiality": "MEDIUM",
        "graduation_blocker": False,
        "finding": "ACTIVE_EVENT_REQUIRES_MONITORING",
        "counterevidence_needed": "Quantified impact, completion/status and valuation transmission.",
        "monitor_trigger": "Next issuer update on event status or economics.",
    }


def synthesize(row: pd.Series) -> dict:
    dim = str(row["research_dimension"])
    if dim == "GOVERNANCE_VALUE_TRAP":
        return governance_synthesis(str(row["evidence_title"]), str(row["evidence_summary"]))
    if dim == "EARNINGS_EXPECTATION_REVISION":
        return earnings_synthesis(str(row["evidence_title"]), str(row["evidence_summary"]), str(row["evidence_date"]))
    if dim == "CATALYST":
        return catalyst_synthesis(str(row["evidence_title"]), str(row["evidence_summary"]))
    raise RuntimeError("UNEXPECTED_DIMENSION:" + dim)


def build(root: Path, out: Path) -> None:
    contract_path = root / "config/hkcu_p2b_e2_deepening_d2_contract.json"
    contract = read_json(contract_path)
    out.mkdir(parents=True, exist_ok=True)
    d1 = out / "_d1_rebuild"
    rebuild_d1(root, d1)

    d1_decision = read_json(d1 / "HKCU_P2B_E2_D1_DECISION.json")
    if d1_decision.get("status") != "PASS_P2B_E2_D1_NEGATIVE_CATALYST_CLOSURE":
        raise SystemExit("UPSTREAM_D1_NOT_PASS")

    ledger = pd.read_csv(
        d1 / "HKCU_P2B_E2_D1_CURRENT_EVIDENCE_LEDGER.csv",
        dtype={"stock_code_5d": str},
        keep_default_na=False,
    )
    partial = ledger[
        (pd.to_numeric(ledger["p2a_overall_rank"], errors="coerce").between(
            int(contract["selection_policy"]["rank_start"]),
            int(contract["selection_policy"]["rank_end"]),
            inclusive="both",
        ))
        & (ledger["research_dimension"].isin(DIMS))
        & (ledger["evidence_status"] == contract["selection_policy"]["required_prior_status"])
    ].copy().sort_values(["p2a_overall_rank", "research_dimension", "security_id"]).reset_index(drop=True)

    failures: list[str] = []
    sel = contract["selection_policy"]
    if len(partial) != int(sel["expected_partial_rows"]):
        failures.append(f"PARTIAL_ROW_COUNT:{len(partial)}")
    counts = partial["research_dimension"].value_counts().to_dict()
    expected_dim_counts = {
        "GOVERNANCE_VALUE_TRAP": int(sel["expected_governance_rows"]),
        "EARNINGS_EXPECTATION_REVISION": int(sel["expected_earnings_rows"]),
        "CATALYST": int(sel["expected_catalyst_rows"]),
    }
    for dim, expected in expected_dim_counts.items():
        if int(counts.get(dim, 0)) != expected:
            failures.append(f"DIM_COUNT:{dim}:{int(counts.get(dim,0))}")
    if partial["security_id"].nunique() != 20:
        failures.append(f"SECURITY_COUNT:{partial['security_id'].nunique()}")
    if partial.duplicated(["security_id", "research_dimension"]).any():
        failures.append("DUPLICATE_SECURITY_DIMENSION")

    synthesis_rows = []
    for _, row in partial.iterrows():
        s = synthesize(row)
        synthesis_rows.append({
            "p2a_overall_rank": int(row["p2a_overall_rank"]),
            "security_id": row["security_id"],
            "stock_code_5d": str(row["stock_code_5d"]).zfill(5),
            "security_name": row["security_name"],
            "research_dimension": row["research_dimension"],
            "prior_evidence_status": row["evidence_status"],
            "source_url": row["source_url"],
            "evidence_date": row["evidence_date"],
            "evidence_title": row["evidence_title"],
            "evidence_summary": row["evidence_summary"],
            **s,
            "alpha_score": pd.NA,
            "trade_authority": TRADE_AUTHORITY,
        })
    synthesis = pd.DataFrame(synthesis_rows).sort_values(
        ["p2a_overall_rank", "research_dimension", "security_id"]
    ).reset_index(drop=True)
    synthesis.insert(0, "synthesis_row_id", range(1, len(synthesis) + 1))

    allowed = contract["synthesis_policy"]
    if not set(synthesis["materiality"]).issubset(set(allowed["materiality_vocabulary"])):
        failures.append("MATERIALITY_VOCABULARY")
    if not set(synthesis["finding_direction"]).issubset(set(allowed["direction_vocabulary"])):
        failures.append("DIRECTION_VOCABULARY")
    if not set(synthesis["evidence_sufficiency"]).issubset(set(allowed["sufficiency_vocabulary"])):
        failures.append("SUFFICIENCY_VOCABULARY")
    if synthesis["alpha_score"].notna().any():
        failures.append("ALPHA_SCORE_PRESENT")
    if (synthesis["trade_authority"] != TRADE_AUTHORITY).any():
        failures.append("TRADE_AUTHORITY_NOT_NONE")

    # Critical semantic guards.
    earnings = synthesis[synthesis["research_dimension"] == "EARNINGS_EXPECTATION_REVISION"]
    if not earnings["finding_direction"].eq("UNKNOWN").all():
        failures.append("PARTIAL_EARNINGS_DIRECTION_INFERRED")
    if earnings["evidence_title"].str.contains(
        "profit alert|profit warning|profit increase|estimated results|results forecast",
        case=False, regex=True,
    ).any():
        failures.append("DIRECT_EXPECTATION_SIGNAL_LEFT_PARTIAL")

    governance = synthesis[synthesis["research_dimension"] == "GOVERNANCE_VALUE_TRAP"]
    audit_or_connected = governance[
        governance["evidence_title"].str.contains(
            "auditor|connected transaction", case=False, regex=True
        )
        | governance["evidence_summary"].str.contains(
            "auditor|connected transaction|related-party", case=False, regex=True
        )
    ]
    if not audit_or_connected["graduation_blocker"].astype(bool).all():
        failures.append("AUDIT_CONNECTED_BLOCKER_GUARD")

    # Aggregate into one security-level decision-readiness surface.
    security_rows = []
    for security_id, grp in synthesis.groupby("security_id", sort=False):
        rank = int(grp["p2a_overall_rank"].iloc[0])
        blocker_count = int(grp["graduation_blocker"].astype(bool).sum())
        high_count = int((grp["materiality"] == "HIGH").sum())
        limited_count = int((grp["evidence_sufficiency"] == "LIMITED_CONFIDENCE").sum())
        targeted_count = int((grp["evidence_sufficiency"] == "TARGETED_DEEPENING_REQUIRED").sum())
        if blocker_count > 0:
            readiness = "TARGETED_DEEPENING_REQUIRED"
        elif limited_count > 0:
            readiness = "READY_WITH_CONFIDENCE_CAP"
        else:
            readiness = "READY_FOR_P2B_SYNTHESIS"
        security_rows.append({
            "p2a_overall_rank": rank,
            "security_id": security_id,
            "stock_code_5d": str(grp["stock_code_5d"].iloc[0]).zfill(5),
            "security_name": grp["security_name"].iloc[0],
            "partial_dimension_count": int(len(grp)),
            "graduation_blocker_count": blocker_count,
            "high_materiality_partial_count": high_count,
            "limited_confidence_count": limited_count,
            "targeted_deepening_count": targeted_count,
            "d2_readiness": readiness,
            "confidence_cap": "MEDIUM" if (limited_count > 0 or targeted_count > 0) else "NONE",
            "formal_candidate_graduation_allowed": False,
            "trade_authority": TRADE_AUTHORITY,
        })
    security = pd.DataFrame(security_rows).sort_values("p2a_overall_rank").reset_index(drop=True)
    if len(security) != int(contract["acceptance"]["required_security_rows"]):
        failures.append(f"SECURITY_SUMMARY_ROWS:{len(security)}")
    if not set(security["d2_readiness"]).issubset(set(allowed["readiness_vocabulary"])):
        failures.append("READINESS_VOCABULARY")

    priority = synthesis[synthesis["graduation_blocker"].astype(bool)].copy()
    materiality_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    priority["_materiality_order"] = priority["materiality"].map(materiality_order).fillna(9)
    priority = priority.sort_values(
        ["_materiality_order", "p2a_overall_rank", "research_dimension", "security_id"]
    ).drop(columns=["_materiality_order"]).reset_index(drop=True)
    priority.insert(0, "deepening_priority_rank", range(1, len(priority) + 1))

    synthesis_path = out / "HKCU_P2B_E2_D2_TOP20_PARTIAL_SYNTHESIS.csv"
    security_path = out / "HKCU_P2B_E2_D2_TOP20_SECURITY_READINESS.csv"
    priority_path = out / "HKCU_P2B_E2_D2_TOP20_BLOCKER_QUEUE.csv"
    decision_path = out / "HKCU_P2B_E2_D2_DECISION.json"
    quality_path = out / "HKCU_P2B_E2_D2_QUALITY_REPORT.json"
    synthesis.to_csv(synthesis_path, index=False)
    security.to_csv(security_path, index=False)
    priority.to_csv(priority_path, index=False)

    readiness_counts = {str(k): int(v) for k, v in security["d2_readiness"].value_counts().items()}
    sufficiency_counts = {str(k): int(v) for k, v in synthesis["evidence_sufficiency"].value_counts().items()}
    direction_counts = {str(k): int(v) for k, v in synthesis["finding_direction"].value_counts().items()}
    materiality_counts = {str(k): int(v) for k, v in synthesis["materiality"].value_counts().items()}
    decision = {
        "program_id": PROGRAM_ID,
        "phase": contract["phase"],
        "status": "PASS_P2B_E2_D2_TOP20_SYNTHESIS" if not failures else "FAIL_P2B_E2_D2",
        "rank_start": 1,
        "rank_end": 20,
        "security_count": int(len(security)),
        "partial_synthesis_rows": int(len(synthesis)),
        "graduation_blocker_rows": int(len(priority)),
        "securities_with_blockers": int((security["graduation_blocker_count"] > 0).sum()),
        "readiness_counts": readiness_counts,
        "sufficiency_counts": sufficiency_counts,
        "direction_counts": direction_counts,
        "materiality_counts": materiality_counts,
        "formal_candidate_graduation_allowed": False,
        "next_gate": contract["next_gate"] if not failures else "BLOCKED_REPAIR",
        "hard_failures": sorted(set(failures)),
        "candidate_pool_mutations": 0,
        "simulation_mutations": 0,
        "real_account_mutations": 0,
        "orders_created": 0,
        "trade_authority": TRADE_AUTHORITY,
    }
    quality = {
        "program_id": PROGRAM_ID,
        "status": "PASS" if not failures else "FAIL",
        "upstream_d1_status": d1_decision.get("status"),
        "partial_synthesis_rows": int(len(synthesis)),
        "security_rows": int(len(security)),
        "blocker_rows": int(len(priority)),
        "earnings_partial_rows": int(len(earnings)),
        "earnings_unknown_direction_rows": int((earnings["finding_direction"] == "UNKNOWN").sum()),
        "audit_or_connected_governance_rows": int(len(audit_or_connected)),
        "score_non_null_count": int(synthesis["alpha_score"].notna().sum()),
        "hard_failures": sorted(set(failures)),
        "warnings": [
            "D2 is evidence synthesis, not an alpha score or Candidate graduation.",
            "Ordinary results remain operating evidence only; missing consensus revision data caps confidence but is not treated as bearish.",
            "Governance audit/connected-transaction and material strategic-event blockers are prioritized for targeted deepening."
        ],
        "trade_authority": TRADE_AUTHORITY,
    }
    write_json(decision_path, decision)
    write_json(quality_path, quality)

    outputs = [synthesis_path, security_path, priority_path, decision_path, quality_path]
    manifest = {
        "program_id": PROGRAM_ID,
        "inputs": {
            str(contract_path.relative_to(root)): sha256_file(contract_path),
            "upstream_d1_decision_sha256": sha256_file(d1 / "HKCU_P2B_E2_D1_DECISION.json"),
            "upstream_d1_current_ledger_sha256": sha256_file(d1 / "HKCU_P2B_E2_D1_CURRENT_EVIDENCE_LEDGER.csv"),
        },
        "outputs": {p.name: sha256_file(p) for p in outputs},
        "trade_authority": TRADE_AUTHORITY,
    }
    write_json(out / "HKCU_P2B_E2_D2_MANIFEST.json", manifest)

    if failures:
        raise SystemExit("P2B_E2_D2_FAILED:" + "|".join(sorted(set(failures))))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--repo-root", default=".")
    p.add_argument("--output", required=True)
    args = p.parse_args()
    build(Path(args.repo_root).resolve(), Path(args.output).resolve())


if __name__ == "__main__":
    main()
