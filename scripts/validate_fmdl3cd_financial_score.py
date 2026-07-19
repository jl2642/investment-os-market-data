from __future__ import annotations

import hashlib
import json
from pathlib import Path

import jsonschema
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fmdl3cd_score.json"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    cfg = load_json(CONFIG)
    root = ROOT / cfg["publication"]["candidate_root"]
    decision = load_json(root / "FMDL3CD_DECISION.json")
    manifest = load_json(root / "FMDL3CD_MANIFEST.json")
    score_schema = load_json(ROOT / "schemas/fmdl3cd_financial_score_v1.schema.json")
    interface_schema = load_json(
        ROOT / "schemas/fmdl3cd_investment_os_interface_v1.schema.json"
    )
    scores = pd.read_parquet(root / "FMDL3CD_FINANCIAL_SCORE_CURRENT.parquet")
    families = pd.read_parquet(root / "FMDL3CD_FAMILY_SCORES.parquet")
    contributions = pd.read_parquet(root / "FMDL3CD_FACTOR_CONTRIBUTIONS.parquet")
    evidence = pd.read_parquet(root / "FMDL3CD_INVESTMENT_OS_EVIDENCE.parquet")
    weights = pd.read_csv(root / "FMDL3CD_SCORE_WEIGHTS.csv", encoding="utf-8-sig")
    interface = load_json(root / "FMDL3CD_INVESTMENT_OS_INTERFACE.json")

    manifest_errors: list[str] = []
    for item in manifest.get("files", []):
        path = root / item["path"]
        if not path.exists():
            manifest_errors.append(f"MISSING:{item['path']}")
        elif sha256(path) != item["sha256"]:
            manifest_errors.append(f"HASH:{item['path']}")

    schema_errors: list[str] = []
    validator = jsonschema.Draft202012Validator(score_schema)
    for row in scores.to_dict(orient="records"):
        cleaned = {
            key: (None if pd.isna(value) else value)
            for key, value in row.items()
        }
        for error in validator.iter_errors(cleaned):
            schema_errors.append(f"{cleaned.get('symbol')}:{error.message}")
    interface_errors = [
        error.message
        for error in jsonschema.Draft202012Validator(interface_schema).iter_errors(
            interface
        )
    ]

    contribution_sum = (
        contributions[contributions["contribution_points"].notna()]
        .groupby("symbol")["contribution_points"]
        .sum()
    )
    replay_errors = []
    for row in scores[scores["financial_score"].notna()].itertuples(index=False):
        value = contribution_sum.get(str(row.symbol), np.nan)
        if not np.isclose(float(value), float(row.financial_score), atol=1e-8):
            replay_errors.append(str(row.symbol))

    accepted_components = contributions[
        contributions["component_state"].isin(["INCLUDED", "INCLUDED_WITH_WARNING"])
    ]
    strict_real = evidence[
        evidence["real_account_financial_evidence"].eq(
            "STRICT_FINANCIAL_REVIEW_FLOOR_MET"
        )
    ]
    action_columns = [
        "candidate_pool_action_authorized",
        "simulation_admission_authorized",
        "real_account_admission_authorized",
        "portfolio_action_authorized",
        "order_execution_authorized",
    ]
    controlled_score_states = {
        "SCORE_ACCEPTED",
        "SCORE_ACCEPTED_WITH_LIMITED_CONFIDENCE",
        "INSUFFICIENT_FACTOR_COVERAGE",
        "INSUFFICIENT_FAMILY_COVERAGE",
        "CONTROLLED_PROFILE_EXCLUSION",
    }
    controlled_component_states = {
        "INCLUDED",
        "INCLUDED_WITH_WARNING",
        "FACTOR_INELIGIBLE",
        "FAMILY_INSUFFICIENT",
        "OVERALL_SCORE_UNAVAILABLE",
        "CONTROLLED_PROFILE_EXCLUSION",
    }
    controlled_evidence = {
        "POSITIVE_FINANCIAL_QUALITY_EVIDENCE",
        "SUPPORTIVE_FINANCIAL_QUALITY_EVIDENCE",
        "NEUTRAL_FINANCIAL_QUALITY_EVIDENCE",
        "FINANCIAL_QUALITY_CAUTION",
        "OBSERVATION_ONLY_INSUFFICIENT_FINANCIAL_EVIDENCE",
    }
    checks = {
        "DECISION_ACCEPTED": decision.get("status") == cfg["exit_status"],
        "DECISION_HARD_FAILURES_EMPTY": decision.get("hard_failures") == [],
        "MANIFEST_FILES_PRESENT_AND_HASHED": not manifest_errors,
        "SCORE_SCHEMA_VALID": not schema_errors,
        "INTERFACE_SCHEMA_VALID": not interface_errors,
        "SCORE_KEYS_UNIQUE": not scores["symbol"].duplicated().any(),
        "SCORE_ROWS_MATCH_PROFILE_UNIVERSE": len(scores)
        == int(decision["metrics"]["universe_symbol_count"]),
        "FAMILY_ROWS_EXACT_X4": len(families) == len(scores) * 4,
        "CONTRIBUTION_ROWS_EXACT_X18": len(contributions) == len(scores) * 18,
        "EVIDENCE_ROWS_EXACT_UNIVERSE": len(evidence) == len(scores)
        and not evidence["symbol"].duplicated().any(),
        "WEIGHTS_EXACT_18_AND_SUM_ONE": len(weights) == 18
        and not weights["factor_id"].duplicated().any()
        and np.isclose(pd.to_numeric(weights["global_weight"]).sum(), 1.0),
        "SCORES_BOUNDED": scores.loc[
            scores["financial_score"].notna(), "financial_score"
        ].between(0, 100, inclusive="both").all(),
        "FAMILY_SCORES_BOUNDED": families.loc[
            families["family_score"].notna(), "family_score"
        ].between(0, 100, inclusive="both").all(),
        "CONFIDENCE_NUMERIC_BOUNDED": scores["score_confidence_numeric"].between(
            0, 100, inclusive="both"
        ).all(),
        "COVERAGE_BOUNDED": scores["global_factor_weight_coverage"].between(
            0, 1, inclusive="both"
        ).all()
        and scores["available_family_weight"].between(
            0, 1, inclusive="both"
        ).all()
        and scores["conditional_weight_share"].between(
            0, 1, inclusive="both"
        ).all(),
        "SCORE_STATES_CONTROLLED": set(scores["score_state"].astype(str)).issubset(
            controlled_score_states
        ),
        "COMPONENT_STATES_CONTROLLED": set(
            contributions["component_state"].astype(str)
        ).issubset(controlled_component_states),
        "SCORE_CONTRIBUTIONS_REPLAY": not replay_errors,
        "INCLUDED_COMPONENTS_HAVE_PERCENTILES": accepted_components[
            "directional_percentile"
        ].notna().all(),
        "INCLUDED_COMPONENTS_PRODUCTION_ELIGIBLE": accepted_components[
            "production_eligibility"
        ].isin(["ELIGIBLE", "CONDITIONAL"]).all(),
        "RANKING_ONLY_GENERAL_NON_FINANCIAL": scores.loc[
            scores["ranking_eligible"], "sector_profile"
        ].eq(cfg["score"]["authorized_profile"]).all(),
        "UNAVAILABLE_SCORES_NOT_RANKED": not scores.loc[
            scores["financial_score"].isna(), "ranking_eligible"
        ].any(),
        "FINANCIAL_PROFILES_FAIL_CLOSED": scores.loc[
            scores["sector_profile"].ne(cfg["score"]["authorized_profile"]),
            "score_state",
        ].eq("CONTROLLED_PROFILE_EXCLUSION").all(),
        "STRICT_REAL_FLOOR_REPLAYS": (
            strict_real["financial_score"]
            .ge(cfg["investment_os"]["strict_real_account_financial_floor"])
            .all()
            and strict_real["score_confidence"]
            .eq(cfg["investment_os"]["strict_real_account_required_confidence"])
            .all()
            and strict_real["available_family_count"].eq(4).all()
        ),
        "CANDIDATE_EVIDENCE_CONTROLLED": set(
            evidence["candidate_pool_financial_evidence"].astype(str)
        ).issubset(controlled_evidence),
        "ZERO_AUTOMATIC_ACTION_AUTHORITY": not evidence[action_columns].any().any(),
        "INTERFACE_ROLE_SEPARATION_PRESENT": set(
            interface.get("role_separation", {}).keys()
        ) == {"candidate_pool", "simulation_lab", "real_account"},
        "INTERFACE_PROHIBITS_SCORE_TO_TRADE": any(
            "BUY ADD REDUCE SELL" in item
            for item in interface.get("consumer_contract", {}).get(
                "prohibited_actions", []
            )
        ),
        "NO_TRADE_SIGNAL_OR_TARGET_WEIGHT_FIELDS": not (
            {"trade_signal", "investment_signal", "target_weight", "order_quantity"}
            & set(scores.columns)
        )
        and not (
            {"trade_signal", "investment_signal", "target_weight", "order_quantity"}
            & set(evidence.columns)
        ),
        "ZERO_TRADE_AUTHORITY": set(
            scores["trade_authority"].dropna().astype(str)
        ).issubset({"NONE"})
        and set(evidence["trade_authority"].dropna().astype(str)).issubset(
            {"NONE"}
        )
        and interface.get("trade_authority") == "NONE",
        "NEXT_GATE_FMDL3D": decision.get("next_gate") == cfg["next_gate"],
    }
    failures = [name for name, passed in checks.items() if not bool(passed)]
    result = {
        "validation_version": "1.0.0",
        "release_id": decision.get("release_id"),
        "status": "PASS" if not failures else "FAIL",
        "hard_failures": failures,
        "checks": [
            {"check_id": name, "status": "PASS" if passed else "FAIL"}
            for name, passed in checks.items()
        ],
        "metrics": {
            **decision.get("metrics", {}),
            "manifest_error_count": len(manifest_errors),
            "score_schema_error_count": len(schema_errors),
            "interface_schema_error_count": len(interface_errors),
            "score_replay_error_count": len(replay_errors),
            "duplicate_score_key_count": int(scores["symbol"].duplicated().sum()),
        },
        "manifest_errors": manifest_errors,
        "score_schema_errors": schema_errors[:50],
        "interface_schema_errors": interface_errors,
        "score_replay_errors": replay_errors[:50],
        "authority": cfg["authority"],
        "trade_authority": "NONE",
        "next_gate": cfg["next_gate"],
    }
    (root / "FMDL3CD_VALIDATION.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
