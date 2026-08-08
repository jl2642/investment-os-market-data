#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

PROGRAM_ID = "HKCU-P5B"
TRADE_AUTHORITY = "NONE"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def truthy(v: Any) -> bool:
    return str(v).strip().lower() in {"true", "1", "yes"}


def build(root: Path, p5a_dir: Path, out: Path) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    contract_path = root / "config/hkcu_p5b_real_pretrade_memo_contract.json"
    contract = read_json(contract_path)
    p5a_contract = read_json(root / contract["authoritative_inputs"]["p5a_contract"])
    p5a_prefix = p5a_contract["output_prefix"]
    prefix = contract["output_prefix"]
    entry = contract["entry_contract"]
    policy = contract["memo_policy"]
    acceptance = contract["acceptance"]

    p5a_decision_path = p5a_dir / f"{p5a_prefix}_DECISION.json"
    p5a_proposals_path = p5a_dir / f"{p5a_prefix}_PROPOSALS.csv"
    p5a_allocations_path = p5a_dir / f"{p5a_prefix}_ALLOCATIONS.csv"
    p5a_manifest_path = p5a_dir / f"{p5a_prefix}_MANIFEST.json"
    p5a_decision = read_json(p5a_decision_path)
    proposals = pd.read_csv(p5a_proposals_path, keep_default_na=False)
    allocations = pd.read_csv(p5a_allocations_path, dtype={"stock_code_5d": str}, keep_default_na=False)
    p5a_manifest = read_json(p5a_manifest_path)
    evidence_path = root / contract["authoritative_inputs"]["evidence_registry"]
    evidence = pd.read_csv(evidence_path, dtype={"stock_code_5d": str}, keep_default_na=False)
    real_state_path = root / contract["authoritative_inputs"]["real_positions_current"]

    errors: list[str] = []
    if p5a_decision.get("status") != entry["required_p5a_status"]: errors.append("P5A_STATUS")
    if p5a_decision.get("next_gate") != entry["required_p5a_next_gate"]: errors.append("P5A_NEXT_GATE")
    if int(p5a_decision.get("phase_5_gate_count", -1)) != entry["required_phase_5_gate_count"]: errors.append("P5A_GATE_COUNT")
    if p5a_decision.get("trade_authority") != TRADE_AUTHORITY: errors.append("P5A_AUTHORITY")
    if p5a_manifest.get("real_positions_current_sha256") != sha256_file(real_state_path): errors.append("REAL_CURRENT_DRIFT_FROM_P5A")

    rp = proposals[proposals["account"].astype(str).eq("REAL")].copy()
    if len(rp) != 1: errors.append("REAL_PROPOSAL_COUNT")
    else:
        r = rp.iloc[0]
        if str(r["preferred_scenario_id"]) != entry["required_real_scenario"]: errors.append("REAL_SCENARIO")
        if abs(float(r["hk_sleeve_proposed"]) - entry["required_real_hk_sleeve"]) > 1e-9: errors.append("REAL_SLEEVE")
        if int(float(r["position_count"])) != entry["required_real_position_count"]: errors.append("REAL_POSITION_COUNT")

    ra = allocations[(allocations["account"].astype(str).eq("REAL")) & (allocations["proposal_scenario_id"].astype(str).eq(entry["required_real_scenario"]))].copy()
    if len(ra) != entry["required_real_position_count"]: errors.append("REAL_ALLOCATION_COUNT")
    if len(evidence) != entry["required_real_position_count"]: errors.append("EVIDENCE_COUNT")
    if evidence["security_id"].duplicated().any(): errors.append("DUPLICATE_EVIDENCE")
    if set(ra["security_id"].astype(str)) != set(evidence["security_id"].astype(str)): errors.append("EVIDENCE_SECURITY_SET")
    if not evidence["official_source_url"].astype(str).str.startswith("https://www1.hkexnews.hk/").all(): errors.append("NONOFFICIAL_PRIMARY_SOURCE")
    disclosure_dates = pd.to_datetime(evidence["disclosure_date"], errors="coerce")
    if disclosure_dates.isna().any() or (disclosure_dates > pd.Timestamp(contract["as_of_date"])).any(): errors.append("EVIDENCE_DATE")

    memo = ra.merge(evidence, on=["security_id", "stock_code_5d", "security_name"], how="left", validate="one_to_one")
    if memo["memo_state"].astype(str).str.strip().eq("").any(): errors.append("MISSING_MEMO_STATE")
    allowed_states = set(policy["allowed_security_states"])
    if not set(memo["memo_state"].astype(str)).issubset(allowed_states): errors.append("INVALID_MEMO_STATE")

    memo["original_proposed_weight"] = pd.to_numeric(memo["proposed_weight"], errors="coerce")
    memo["memo_proposed_weight"] = memo.apply(lambda x: float(x["original_proposed_weight"]) if x["memo_state"] == "ADVANCE_WITH_PRICE_GATE" else 0.0, axis=1)
    memo["deferred_or_rejected_weight"] = memo["original_proposed_weight"] - memo["memo_proposed_weight"]
    memo["permission_after_p5b"] = memo["memo_state"].map({"ADVANCE_WITH_PRICE_GATE": policy["exit_permission_on_pass"], "DEFER_SECURITY": "RESEARCH_ONLY", "REJECT_SECURITY": "RESEARCH_ONLY"})
    memo["execution_status"] = "NOT_AUTHORIZED_FOR_EXECUTION"
    memo["user_trade_confirmation_recorded"] = False
    memo["manual_execution_checklist_produced"] = False
    memo["target_writeback"] = False
    memo["portfolio_mutation"] = False
    memo["orders_created"] = 0
    memo["trade_authority"] = TRADE_AUTHORITY

    advanced = int(memo["memo_state"].eq("ADVANCE_WITH_PRICE_GATE").sum())
    deferred = int(memo["memo_state"].eq("DEFER_SECURITY").sum())
    rejected = int(memo["memo_state"].eq("REJECT_SECURITY").sum())
    original_weight = float(memo["original_proposed_weight"].sum())
    modified_weight = float(memo["memo_proposed_weight"].sum())
    removed_weight = float(memo["deferred_or_rejected_weight"].sum())
    if abs(original_weight - acceptance["preferred_original_weight"]) > 1e-9: errors.append("ORIGINAL_WEIGHT")
    if advanced != acceptance["advanced_with_price_gate_count"]: errors.append("ADVANCE_COUNT")
    if deferred != acceptance["deferred_security_count"]: errors.append("DEFER_COUNT")
    if rejected != acceptance["rejected_security_count"]: errors.append("REJECT_COUNT")
    if modified_weight >= original_weight: errors.append("EXPECTED_MODIFICATION_NOT_PRESENT")
    advanced_rows = memo[memo["memo_state"].eq("ADVANCE_WITH_PRICE_GATE")]
    if not advanced_rows["price_recheck_required_at_p5c"].map(truthy).all(): errors.append("ADVANCE_WITHOUT_PRICE_RECHECK")
    deferred_rows = memo[memo["memo_state"].eq("DEFER_SECURITY")]
    if len(deferred_rows) and not deferred_rows["fresh_interim_results_required"].map(truthy).all(): errors.append("DEFER_WITHOUT_EVIDENCE_TRIGGER")

    aggregate_state = policy["aggregate_expected_state"] if not errors else "P5B_INTEGRITY_FAIL"
    memo_path = out / f"{prefix}_SECURITY_MEMOS.csv"
    memo.to_csv(memo_path, index=False)

    retained_loss = pd.to_numeric(advanced_rows["historical_drawdown_loss_weight"], errors="coerce").fillna(0).sum() if len(advanced_rows) else 0.0
    summary = {
        "program_id": PROGRAM_ID,
        "phase": contract["phase"],
        "as_of_date": contract["as_of_date"],
        "aggregate_memo_state": aggregate_state,
        "original_real_sleeve": original_weight,
        "memo_real_sleeve": modified_weight,
        "deferred_or_rejected_weight": removed_weight,
        "security_memo_count": len(memo),
        "advanced_with_price_gate_count": advanced,
        "deferred_security_count": deferred,
        "rejected_security_count": rejected,
        "retained_historical_drawdown_loss_weight": float(retained_loss),
        "deferred_weight_reallocated": False,
        "price_recheck_required_at_p5c": True,
        "permission": policy["exit_permission_on_pass"] if advanced else "RESEARCH_ONLY",
        "execution_status": "NOT_AUTHORIZED_FOR_EXECUTION",
        "review_date": policy["review_date"],
        "trade_authority": TRADE_AUTHORITY,
    }
    write_json(out / f"{prefix}_SUMMARY.json", summary)

    md = [
        "# HKCU P5B REAL Pre-trade Memo",
        "",
        f"As of: {contract['as_of_date']}",
        f"Aggregate state: **{aggregate_state}**",
        f"Original REAL sleeve: **{original_weight:.4%}**; memo sleeve after evidence review: **{modified_weight:.4%}**; deferred/rejected: **{removed_weight:.4%}**.",
        "",
        "No exact 2026-08-07 closing price is fabricated. Every advanced security requires a fresh executable-price/valuation recheck at P5C. Deferred weight is not redistributed automatically.",
        "",
    ]
    for row in memo.sort_values("security_id").itertuples(index=False):
        md += [
            f"## {row.security_id} {row.security_name}",
            f"- Memo state: **{row.memo_state}**",
            f"- Original / memo weight: {float(row.original_proposed_weight):.4%} / {float(row.memo_proposed_weight):.4%}",
            f"- Evidence: {row.evidence_maturity}; {row.disclosure_date}; {row.official_source_url}",
            f"- Key metrics: {row.key_metrics}",
            f"- Thesis update: {row.thesis_update}",
            f"- Valuation gate: {row.valuation_gate}",
            f"- Funding: {row.funding_source_class}",
            f"- Historical drawdown-loss contribution: {float(row.historical_drawdown_loss_weight):.4%}",
            f"- Portfolio role: {row.portfolio_role}; corr={float(row.candidate_portfolio_correlation):.4f}; downside corr={float(row.downside_correlation):.4f}",
            f"- Principal falsifier: {row.principal_falsifier_y if hasattr(row, 'principal_falsifier_y') else row.principal_falsifier}",
            f"- Review triggers: {row.review_triggers_y if hasattr(row, 'review_triggers_y') else row.review_triggers}",
            "",
        ]
    (out / f"{prefix}.md").write_text("\n".join(md), encoding="utf-8")

    status = acceptance["pass_status"] if not errors else acceptance["fail_status"]
    decision = {
        "program_id": PROGRAM_ID,
        "phase": contract["phase"],
        "as_of_date": contract["as_of_date"],
        "status": status,
        "entry_p5a_status": p5a_decision.get("status"),
        "aggregate_memo_state": aggregate_state,
        "original_real_sleeve": original_weight,
        "memo_real_sleeve": modified_weight,
        "deferred_or_rejected_weight": removed_weight,
        "security_memo_count": len(memo),
        "advanced_with_price_gate_count": advanced,
        "deferred_security_count": deferred,
        "rejected_security_count": rejected,
        "deferred_weight_reallocated": False,
        "pretrade_memo_produced": not errors,
        "user_trade_confirmation_recorded": False,
        "manual_execution_checklist_produced": False,
        "target_portfolio_writeback": False,
        "candidate_pool_mutations": 0,
        "simulation_mutations": 0,
        "real_account_mutations": 0,
        "orders_created": 0,
        "next_gate": policy["next_gate_on_pass"] if not errors else acceptance["repair_gate"],
        "permission": policy["exit_permission_on_pass"] if not errors else "RESEARCH_ONLY",
        "integrity_failures": errors,
        "trade_authority": TRADE_AUTHORITY,
    }
    quality = {
        "program_id": PROGRAM_ID,
        "status": "PASS" if not errors else "FAIL",
        "official_primary_evidence_only_for_company_fundamentals": True,
        "exact_asof_close_fabricated": False,
        "advanced_securities_require_fresh_price_gate": True,
        "deferred_weight_reallocated": False,
        "weighted_score": False,
        "fixed_top_n": False,
        "technical_pass_substitutes_user_approval": False,
        "user_trade_confirmation_recorded": False,
        "manual_execution_checklist_produced": False,
        "portfolio_mutations": 0,
        "orders_created": 0,
        "trade_authority": TRADE_AUTHORITY,
        "hard_failures": errors,
    }
    write_json(out / f"{prefix}_DECISION.json", decision)
    write_json(out / f"{prefix}_QUALITY_REPORT.json", quality)
    manifest = {
        "program_id": PROGRAM_ID,
        "contract_sha256": sha256_file(contract_path),
        "evidence_registry_sha256": sha256_file(evidence_path),
        "p5a_decision_sha256": sha256_file(p5a_decision_path),
        "p5a_proposals_sha256": sha256_file(p5a_proposals_path),
        "p5a_allocations_sha256": sha256_file(p5a_allocations_path),
        "p5a_manifest_sha256": sha256_file(p5a_manifest_path),
        "real_positions_current_sha256": sha256_file(real_state_path),
        "security_memos_sha256": sha256_file(memo_path),
        "memo_markdown_sha256": sha256_file(out / f"{prefix}.md"),
        "trade_authority": TRADE_AUTHORITY,
    }
    write_json(out / f"{prefix}_MANIFEST.json", manifest)
    if errors:
        raise SystemExit("P5B_PRETRADE_MEMO_FAILED:" + "|".join(errors))
    return decision


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--p5a-dir", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    build(Path(args.repo_root).resolve(), Path(args.p5a_dir).resolve(), Path(args.output).resolve())


if __name__ == "__main__":
    main()
