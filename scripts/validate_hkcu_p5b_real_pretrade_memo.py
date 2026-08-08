#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import pandas as pd

TRADE_AUTHORITY = "NONE"
FIXED_MULTIPLE_RE = re.compile(r"(?:<=|>=|<|>)\s*\d+(?:\.\d+)?x\b", re.I)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def is_official_hkex_url(v: object) -> bool:
    s = str(v).strip()
    return s.startswith("https://www1.hkexnews.hk/") or s.startswith("https://www.hkexnews.hk/")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--p5a-dir", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    root = Path(args.repo_root).resolve()
    p5a = Path(args.p5a_dir).resolve()
    out = Path(args.output).resolve()

    contract_path = root / "config/hkcu_p5b_real_pretrade_memo_contract.json"
    contract = read_json(contract_path)
    p5a_contract = read_json(root / contract["authoritative_inputs"]["p5a_contract"])
    p5a_prefix = p5a_contract["output_prefix"]
    prefix = contract["output_prefix"]
    acceptance = contract["acceptance"]
    policy = contract["memo_policy"]

    decision = read_json(out / f"{prefix}_DECISION.json")
    quality = read_json(out / f"{prefix}_QUALITY_REPORT.json")
    summary = read_json(out / f"{prefix}_SUMMARY.json")
    manifest = read_json(out / f"{prefix}_MANIFEST.json")
    memo = pd.read_csv(out / f"{prefix}_SECURITY_MEMOS.csv", dtype={"stock_code_5d": str}, keep_default_na=False)
    evidence_path = root / contract["authoritative_inputs"]["evidence_registry"]
    evidence = pd.read_csv(evidence_path, dtype={"stock_code_5d": str}, keep_default_na=False)
    p5a_decision = read_json(p5a / f"{p5a_prefix}_DECISION.json")
    p5a_alloc = pd.read_csv(p5a / f"{p5a_prefix}_ALLOCATIONS.csv", dtype={"stock_code_5d": str}, keep_default_na=False)
    real_alloc = p5a_alloc[
        (p5a_alloc["account"].astype(str).eq("REAL"))
        & (p5a_alloc["proposal_scenario_id"].astype(str).eq(contract["entry_contract"]["required_real_scenario"]))
    ]

    errors: list[str] = []
    if decision.get("status") != acceptance["pass_status"]:
        errors.append("DECISION_STATUS")
    if quality.get("status") != "PASS" or quality.get("hard_failures") != []:
        errors.append("QUALITY")
    if p5a_decision.get("status") != contract["entry_contract"]["required_p5a_status"]:
        errors.append("P5A_STATUS")
    if p5a_decision.get("next_gate") != "P5B_REAL_PRETRADE_MEMO":
        errors.append("P5A_NEXT")
    if len(memo) != acceptance["security_memo_count"]:
        errors.append("MEMO_COUNT")
    if len(evidence) != acceptance["security_memo_count"]:
        errors.append("EVIDENCE_COUNT")
    if set(memo["security_id"]) != set(real_alloc["security_id"]):
        errors.append("SECURITY_SET")
    if int(memo["memo_state"].eq("ADVANCE_WITH_PRICE_GATE").sum()) != acceptance["advanced_with_price_gate_count"]:
        errors.append("ADVANCE_COUNT")
    if int(memo["memo_state"].eq("DEFER_SECURITY").sum()) != acceptance["deferred_security_count"]:
        errors.append("DEFER_COUNT")
    if int(memo["memo_state"].eq("REJECT_SECURITY").sum()) != acceptance["rejected_security_count"]:
        errors.append("REJECT_COUNT")
    if summary.get("aggregate_memo_state") != policy["aggregate_expected_state"]:
        errors.append("AGGREGATE_STATE")
    if decision.get("next_gate") != policy["next_gate_on_pass"]:
        errors.append("NEXT_GATE")
    if decision.get("permission") != "USER_DECISION_REQUIRED":
        errors.append("PERMISSION")
    if decision.get("trade_authority") != TRADE_AUTHORITY:
        errors.append("AUTHORITY")
    if abs(float(summary["original_real_sleeve"]) - acceptance["preferred_original_weight"]) > 1e-9:
        errors.append("ORIGINAL_SLEEVE")
    if not float(summary["memo_real_sleeve"]) < float(summary["original_real_sleeve"]):
        errors.append("NO_MODIFICATION")
    if abs(float(summary["memo_real_sleeve"]) + float(summary["deferred_or_rejected_weight"]) - float(summary["original_real_sleeve"])) > 1e-9:
        errors.append("WEIGHT_RECONCILIATION")

    advanced = memo[memo["memo_state"].eq("ADVANCE_WITH_PRICE_GATE")]
    deferred = memo[memo["memo_state"].eq("DEFER_SECURITY")]
    if not advanced["price_recheck_required_at_p5c"].astype(str).str.lower().isin({"true", "1"}).all():
        errors.append("PRICE_GATE")
    if len(deferred) != 1 or str(deferred.iloc[0]["security_id"]) != "HKEX:02698":
        errors.append("SOFTCARE_DEFER")
    if len(deferred) and not deferred["fresh_interim_results_required"].astype(str).str.lower().isin({"true", "1"}).all():
        errors.append("INTERIM_TRIGGER")
    if len(deferred) and pd.to_numeric(deferred["memo_proposed_weight"], errors="coerce").fillna(-1).ne(0).any():
        errors.append("DEFER_WEIGHT_NONZERO")
    for _, row in advanced.iterrows():
        if abs(float(row["memo_proposed_weight"]) - float(row["original_proposed_weight"])) > 1e-12:
            errors.append("ADVANCED_WEIGHT_CHANGED")
    if abs(float(memo["memo_proposed_weight"].sum()) - float(summary["memo_real_sleeve"])) > 1e-9:
        errors.append("MEMO_WEIGHT_SUM")

    if not memo["official_source_url"].map(is_official_hkex_url).all():
        errors.append("SOURCE_AUTHORITY")
    if "supporting_official_source_url" not in memo.columns:
        errors.append("SUPPORTING_SOURCE_COLUMN")
    else:
        supporting = memo["supporting_official_source_url"].astype(str).str.strip()
        if not supporting.map(lambda x: (not x) or is_official_hkex_url(x)).all():
            errors.append("SUPPORTING_SOURCE_AUTHORITY")
        sitc = memo[memo["security_id"].astype(str).eq("HKEX:01308")]
        if len(sitc) != 1 or not is_official_hkex_url(sitc.iloc[0]["supporting_official_source_url"]):
            errors.append("SITC_ANNUAL_SOURCE_LINEAGE")
        elif "2026031000179.pdf" not in str(sitc.iloc[0]["supporting_official_source_url"]):
            errors.append("SITC_ANNUAL_SOURCE_WRONG")
    if (pd.to_datetime(memo["disclosure_date"], errors="coerce") > pd.Timestamp(contract["as_of_date"])).any():
        errors.append("SOURCE_DATE")

    if policy.get("undocumented_fixed_valuation_multiple_allowed") is not False:
        errors.append("FIXED_MULTIPLE_POLICY")
    if memo["valuation_gate"].astype(str).map(lambda x: bool(FIXED_MULTIPLE_RE.search(x))).any():
        errors.append("UNDOCUMENTED_FIXED_VALUATION_MULTIPLE")
    required_context = {"LIVE_EXECUTABLE_PRICE", "LATEST_OFFICIAL_EARNINGS", "COMPANY_HISTORICAL_VALUATION", "RELEVANT_PEER_CONTEXT"}
    if set(policy.get("valuation_context_required_at_p5c", [])) != required_context:
        errors.append("VALUATION_CONTEXT_POLICY")

    for col in (
        "key_metrics",
        "valuation_gate",
        "thesis_update",
        "principal_falsifier_y",
        "review_triggers_y",
        "portfolio_role",
        "funding_source_class",
    ):
        if col not in memo.columns or memo[col].astype(str).str.strip().eq("").any():
            errors.append(f"MISSING:{col}")
    for col in ("candidate_portfolio_correlation", "downside_correlation", "historical_drawdown_loss_weight"):
        if pd.to_numeric(memo[col], errors="coerce").isna().any():
            errors.append(f"NONFINITE:{col}")
    if memo["portfolio_mutation"].astype(str).str.lower().isin({"true", "1"}).any():
        errors.append("MEMO_MUTATION")
    if pd.to_numeric(memo["orders_created"], errors="coerce").fillna(0).ne(0).any():
        errors.append("ORDERS")
    if not memo["trade_authority"].astype(str).eq(TRADE_AUTHORITY).all():
        errors.append("ROW_AUTHORITY")

    for key, expected in {
        "pretrade_memo_produced": True,
        "user_trade_confirmation_recorded": False,
        "manual_execution_checklist_produced": False,
        "target_portfolio_writeback": False,
        "deferred_weight_reallocated": False,
    }.items():
        if decision.get(key) is not expected:
            errors.append(f"BOUNDARY:{key}")
    for key in ("candidate_pool_mutations", "simulation_mutations", "real_account_mutations", "orders_created"):
        if int(decision.get(key, -1)) != 0:
            errors.append(f"MUTATION:{key}")
    if quality.get("exact_asof_close_fabricated") is not False:
        errors.append("FAKE_PRICE")
    if quality.get("undocumented_fixed_valuation_multiple_used") is not False:
        errors.append("FIXED_MULTIPLE_USED")
    if quality.get("supporting_official_source_lineage_complete") is not True:
        errors.append("SUPPORTING_LINEAGE_QUALITY")
    if quality.get("valuation_context_requires_live_price_latest_earnings_history_and_peers") is not True:
        errors.append("VALUATION_CONTEXT_QUALITY")
    if quality.get("technical_pass_substitutes_user_approval") is not False:
        errors.append("TECHNICAL_APPROVAL")

    expected_hashes = {
        "contract_sha256": sha(contract_path),
        "evidence_registry_sha256": sha(evidence_path),
        "p5a_decision_sha256": sha(p5a / f"{p5a_prefix}_DECISION.json"),
        "p5a_proposals_sha256": sha(p5a / f"{p5a_prefix}_PROPOSALS.csv"),
        "p5a_allocations_sha256": sha(p5a / f"{p5a_prefix}_ALLOCATIONS.csv"),
        "p5a_manifest_sha256": sha(p5a / f"{p5a_prefix}_MANIFEST.json"),
        "security_memos_sha256": sha(out / f"{prefix}_SECURITY_MEMOS.csv"),
        "memo_markdown_sha256": sha(out / f"{prefix}.md"),
    }
    for k, v in expected_hashes.items():
        if manifest.get(k) != v:
            errors.append(f"HASH:{k}")

    result = {
        "program_id": "HKCU-P5B",
        "status": "PASS" if not errors else "FAIL",
        "operational_status": decision.get("status"),
        "aggregate_memo_state": decision.get("aggregate_memo_state"),
        "security_memo_count": len(memo),
        "memo_real_sleeve": summary.get("memo_real_sleeve"),
        "advanced_with_price_gate_count": int(memo["memo_state"].eq("ADVANCE_WITH_PRICE_GATE").sum()),
        "deferred_security_count": int(memo["memo_state"].eq("DEFER_SECURITY").sum()),
        "next_gate": decision.get("next_gate"),
        "errors": errors,
        "trade_authority": decision.get("trade_authority"),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    if errors:
        raise SystemExit("P5B_VALIDATION_FAILED:" + "|".join(errors))


if __name__ == "__main__":
    main()
