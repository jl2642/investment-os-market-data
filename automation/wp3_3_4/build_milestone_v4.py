#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd


HERE = Path(__file__).resolve()
SPEC = importlib.util.spec_from_file_location("wp3_3_4_v3", HERE.with_name("build_milestone_v3.py"))
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load WP3-3/4 v3 engine")
v3 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = v3
SPEC.loader.exec_module(v3)
base = v3.base

ORIGINAL_APPLY = v3.apply_strategy_sleeves
ORIGINAL_CORE_REVIEW = base.core20_review


def enhanced_apply_strategy_sleeves(assessment: pd.DataFrame, cfg: dict[str, Any]) -> pd.DataFrame:
    frame = ORIGINAL_APPLY(assessment, cfg)
    override_path = HERE.with_name("core20_strategy_sleeve_overrides.json")
    payload = json.loads(override_path.read_text(encoding="utf-8"))
    overrides = {str(code): str(sleeve) for code, sleeve in payload["overrides"].items()}
    mask = frame["historical_core20"].astype(bool) & frame["security_code"].astype(str).isin(overrides)
    frame.loc[mask, "strategy_sleeve"] = frame.loc[mask, "security_code"].astype(str).map(overrides)

    gates = frame.loc[mask].apply(lambda row: v3.sleeve_gate(row, cfg), axis=1)
    frame.loc[mask, "financial_gate_pass"] = [item[0] for item in gates]
    frame.loc[mask, "financial_gate_reasons"] = ["|".join(item[1]) for item in gates]

    for idx in frame.index[mask]:
        row = frame.loc[idx]
        sleeve = str(row["strategy_sleeve"])
        gate_pass = bool(row["financial_gate_pass"])
        size_pass = bool(row["institutional_size_gate"])
        liquidity_pass = bool(row["research_liquidity_gate"])
        prior_rejected = str(row.get("prior_graduation_decision") or "") == "REJECTED"
        if sleeve == "FINANCIAL_SEPARATE_PROFILE":
            disposition = "SEPARATE_PROFILE_REVIEW_REQUIRED"
        elif prior_rejected:
            disposition = "DEFER_PRIOR_REJECTION_REQUIRES_NEW_EVIDENCE"
        elif gate_pass and size_pass and liquidity_pass:
            disposition = "MULTIDIMENSIONAL_ELIGIBLE"
        elif gate_pass and liquidity_pass:
            disposition = "WATCH_SMALL_CAP_OR_CAPITALIZATION_REVIEW"
        elif str(row.get("score_state") or "").startswith("SCORE_ACCEPTED"):
            disposition = "DEFER_BELOW_STRATEGY_SLEEVE_OR_INVESTABILITY_GATE"
        else:
            disposition = "DEFER_FINANCIAL_EVIDENCE_OR_PROFILE"
        frame.at[idx, "multidimensional_disposition"] = disposition
        frame.at[idx, "core20_sleeve_override_applied"] = True
    frame["core20_sleeve_override_applied"] = frame["core20_sleeve_override_applied"].fillna(False).astype(bool)
    return frame.sort_values(
        ["research_priority_score", "financial_score", "current_market_cap_cny", "security_code"],
        ascending=[False, False, False, True],
        na_position="last",
    ).reset_index(drop=True)


def enhanced_core_review(assessment: pd.DataFrame, cfg: dict[str, Any]) -> pd.DataFrame:
    review = ORIGINAL_CORE_REVIEW(assessment, cfg)
    mask = review["core20_review_disposition"].eq("DEPRIORITIZE_PENDING_THESIS_REBUILD")
    review.loc[mask, "core20_review_disposition"] = "THESIS_REBUILD_REQUIRED_BEFORE_CANDIDATE_DECISION"
    review.loc[mask, "core20_review_reason"] = "CURRENT_EVIDENCE_BELOW_GATE_REQUIRES_THESIS_REBUILD_NOT_AUTOMATIC_REMOVAL"
    review["automatic_removal"] = False
    review["automatic_readmission"] = False
    review["candidate_membership_mutation"] = 0
    review["trade_authority"] = "NONE"
    return review


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--config", default="automation/wp3_3_4/config.json")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    cfg = base.read_json(root / args.config)
    v3.apply_strategy_sleeves = enhanced_apply_strategy_sleeves
    base.core20_review = enhanced_core_review
    result = v3.write_outputs(root, root / args.output_dir, cfg)
    result["contract_version"] = "4.0.0"
    result["core20_strategy_sleeve_overrides"] = "HISTORICAL_CORE20_REVIEW_ROUTING_ONLY"
    result["files"]["core20_strategy_sleeve_overrides"] = {
        "path": "automation/wp3_3_4/core20_strategy_sleeve_overrides.json",
        "sha256": base.sha256_file(HERE.with_name("core20_strategy_sleeve_overrides.json")),
    }
    base.write_json(root / args.output_dir / "WP3_3_4_MANIFEST.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
