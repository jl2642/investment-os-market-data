#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

TRADE_AUTHORITY = "NONE"
BLOCKED_IDS: set[str] = set()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def as_bool(value: Any) -> bool:
    return value is True or str(value).strip().lower() in {"1", "true", "yes", "y"}


def has_nonempty(series: pd.Series) -> bool:
    return series.astype(str).str.strip().ne("").any()


def expected_route(row: pd.Series) -> str:
    if str(row["security_id"]) in BLOCKED_IDS:
        return "HOLD_RETAINED_INVESTMENT_BLOCKER"
    if (
        not as_bool(row["all_applicable_hard_rules_pass"])
        or not as_bool(row["all_applicable_decision_rules_pass"])
        or int(row["material_confidence_cap_count"]) > 0
    ):
        return "DEFER_RESEARCH_MONITOR"
    if (
        str(row["valuation_support_state"]) == "SUPPORTIVE"
        and int(row["bounded_confidence_cap_count"]) == 0
        and int(row["negative_dimension_count"]) == 0
        and int(row["positive_dimension_count"]) >= 1
    ):
        return "PROPOSE_CORE_CANDIDATE"
    return "PROPOSE_WATCH_CANDIDATE"


def validate(output: Path, repo_root: Path) -> None:
    global BLOCKED_IDS
    contract = read_json(repo_root / "config/hkcu_p3_1_candidate_graduation_assessment_contract.json")
    p3_0 = read_json(repo_root / contract["authoritative_inputs"]["p3_0_contract"])
    fmdl5e = read_json(repo_root / contract["authoritative_inputs"]["fmdl5e_contract"])
    maximum_age_days = int(fmdl5e["investability"]["maximum_price_age_calendar_days"])
    prefix = contract["output_prefix"]
    assessment = pd.read_csv(output / f"{prefix}_SECURITY_ASSESSMENT.csv", dtype={"stock_code_5d": str}, keep_default_na=False)
    rules = pd.read_csv(output / f"{prefix}_RULE_ASSESSMENT.csv", dtype={"stock_code_5d": str}, keep_default_na=False)
    blockers = pd.read_csv(output / f"{prefix}_RETAINED_BLOCKERS.csv", dtype={"stock_code_5d": str}, keep_default_na=False)
    decision = read_json(output / f"{prefix}_DECISION.json")
    quality = read_json(output / f"{prefix}_QUALITY_REPORT.json")
    manifest = read_json(output / f"{prefix}_MANIFEST.json")

    failures: list[str] = []
    entry = contract["entry_contract"]
    BLOCKED_IDS = set(entry["retained_blocker_security_ids"])

    if len(assessment) != int(entry["entry_security_count"]):
        failures.append(f"ASSESSMENT_COUNT:{len(assessment)}")
    if assessment["security_id"].duplicated().any():
        failures.append("DUPLICATE_SECURITY")
    if len(rules) != int(entry["rule_assessment_row_count"]):
        failures.append(f"RULE_ROWS:{len(rules)}")
    if rules.duplicated(["security_id", "rule_id"]).any():
        failures.append("DUPLICATE_RULE")
    if set(rules["rule_id"]) != {f"P3R{i:02d}" for i in range(1, 13)}:
        failures.append("RULE_ID_SET")
    per_security = rules.groupby("security_id")["rule_id"].nunique()
    if len(per_security) != len(assessment) or not per_security.eq(12).all():
        failures.append("TWELVE_RULES_PER_SECURITY")

    if not set(rules["rule_state"]).issubset(set(contract["rule_states"])):
        failures.append("RULE_STATE_VOCABULARY")
    if not set(assessment["proposal_state"]).issubset(set(contract["proposal_states"])):
        failures.append("PROPOSAL_VOCABULARY")
    if has_nonempty(assessment["alpha_score"]) or has_nonempty(rules["alpha_score"]):
        failures.append("ALPHA_SCORE_PRESENT")
    if assessment["formal_candidate_graduation"].map(as_bool).any():
        failures.append("FORMAL_GRADUATION")
    if assessment["candidate_pool_mutation"].map(as_bool).any():
        failures.append("CANDIDATE_MUTATION")
    if not assessment["trade_authority"].astype(str).eq(TRADE_AUTHORITY).all():
        failures.append("TRADE_AUTHORITY_ASSESSMENT")
    if not rules["trade_authority"].astype(str).eq(TRADE_AUTHORITY).all():
        failures.append("TRADE_AUTHORITY_RULES")

    observed_blocked = set(
        assessment.loc[
            assessment["proposal_state"].eq("HOLD_RETAINED_INVESTMENT_BLOCKER"),
            "security_id",
        ]
    )
    if observed_blocked != BLOCKED_IDS:
        failures.append("BLOCKER_SET")
    if set(blockers["security_id"]) != BLOCKED_IDS:
        failures.append("BLOCKER_FILE_SET")

    r02 = rules[rules["rule_id"].eq("P3R02")]
    r02_fail = set(r02.loc[r02["rule_state"].eq("FAIL"), "security_id"])
    if r02_fail != BLOCKED_IDS:
        failures.append("P3R02_FAIL_SET")

    r04 = rules[rules["rule_id"].eq("P3R04")].set_index("security_id")
    for r in assessment.itertuples(index=False):
        try:
            price_age = int(r.price_age_days)
            factor_age = int(r.factor_age_days)
        except (TypeError, ValueError):
            failures.append(f"FRESHNESS_AGE_MISSING:{r.security_id}")
            continue
        expected_fresh = (
            str(r.freshness_status) == "CURRENT"
            and 0 <= price_age <= maximum_age_days
            and 0 <= factor_age <= maximum_age_days
        )
        observed_state = r04.loc[r.security_id, "rule_state"]
        expected_state = "PASS" if expected_fresh else "FAIL"
        if observed_state != expected_state:
            failures.append(f"P3R04_STATE:{r.security_id}:{observed_state}:{expected_state}")

    r12 = rules[rules["rule_id"].eq("P3R12")].set_index("security_id")
    for r in assessment.itertuples(index=False):
        state = r12.loc[r.security_id, "rule_state"]
        expected = "PASS" if str(r.ah_pair_status) == "TRUE_AH_PAIR" else "NOT_APPLICABLE"
        if state != expected:
            failures.append(f"P3R12_STATE:{r.security_id}:{state}:{expected}")

    for _, row in assessment.iterrows():
        er = expected_route(row)
        if row["proposal_state"] != er:
            failures.append(f"ROUTING:{row['security_id']}:{row['proposal_state']}:{er}")
        if row["proposal_state"] == "PROPOSE_CORE_CANDIDATE":
            if str(row["valuation_support_state"]) != "SUPPORTIVE":
                failures.append(f"CORE_VALUATION:{row['security_id']}")
            if int(row["bounded_confidence_cap_count"]) != 0 or int(row["material_confidence_cap_count"]) != 0:
                failures.append(f"CORE_CAPS:{row['security_id']}")
            if int(row["negative_dimension_count"]) != 0 or int(row["positive_dimension_count"]) < 1:
                failures.append(f"CORE_SIGNAL:{row['security_id']}")

    counts = assessment["proposal_state"].value_counts().astype(int).to_dict()
    if decision.get("proposal_state_counts") != counts:
        failures.append("DECISION_COUNT_TIEOUT")
    if int(decision.get("security_assessment_count", -1)) != len(assessment):
        failures.append("DECISION_SECURITY_COUNT")
    if int(decision.get("rule_assessment_row_count", -1)) != len(rules):
        failures.append("DECISION_RULE_COUNT")
    if int(decision.get("retained_blocker_security_count", -1)) != len(BLOCKED_IDS):
        failures.append("DECISION_BLOCKER_COUNT")
    if set(decision.get("retained_blocker_security_ids", [])) != BLOCKED_IDS:
        failures.append("DECISION_BLOCKER_SET")
    if decision.get("status") != contract["acceptance"]["pass_status"]:
        failures.append("DECISION_STATUS")
    if decision.get("next_gate") != contract["acceptance"]["next_gate"]:
        failures.append("NEXT_GATE")
    if decision.get("trade_authority") != TRADE_AUTHORITY:
        failures.append("DECISION_TRADE_AUTHORITY")
    for key in ("formal_candidate_graduation_count", "candidate_pool_mutations", "simulation_mutations", "real_account_mutations", "orders_created", "alpha_score_non_null_count"):
        if int(decision.get(key, -1)) != 0:
            failures.append(f"ZERO_GATE:{key}")

    if quality.get("status") != "PASS" or quality.get("hard_failures"):
        failures.append("QUALITY_NOT_PASS")
    if not quality.get("p2b_final_real_rebuild_and_independent_validation"):
        failures.append("P2B_FINAL_LINEAGE_NOT_BOUND")
    if quality.get("freshness_maximum_age_calendar_days") != maximum_age_days:
        failures.append("FRESHNESS_CONTRACT_MISMATCH")
    if quality.get("exact_same_day_factor_date_required") is not False:
        failures.append("FRESHNESS_SAME_DAY_TIGHTENING")
    if not quality.get("no_weighted_score") or not quality.get("no_neutral_fill") or not quality.get("no_fixed_top_n"):
        failures.append("GOVERNANCE_PHILOSOPHY")
    if manifest.get("program_id") != contract["program_id"] or manifest.get("trade_authority") != TRADE_AUTHORITY:
        failures.append("MANIFEST_IDENTITY")

    p3_ids = {r["rule_id"] for r in p3_0["graduation_rules"]}
    if p3_ids != set(rules["rule_id"]):
        failures.append("P3_0_RULE_LINEAGE")

    if failures:
        raise SystemExit("P3_1_VALIDATION_FAILED:" + "|".join(sorted(set(failures))))
    print("PASS_P3_1_CANDIDATE_GRADUATION_ASSESSMENT_VALIDATION")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--repo-root", default=".")
    p.add_argument("--output", required=True)
    args = p.parse_args()
    validate(Path(args.output).resolve(), Path(args.repo_root).resolve())


if __name__ == "__main__":
    main()
