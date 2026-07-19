from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from scripts.fmdl3cd_core import (
    FAMILY_ORDER,
    build_factor_contributions,
    build_family_scores,
    build_financial_scores,
    build_investment_os_evidence,
    validate_weight_table,
)

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("Asia/Shanghai")
CONFIG = ROOT / "config/fmdl3cd_score.json"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest(root: Path, release_id: str) -> dict:
    files = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "FMDL3CD_MANIFEST.json":
            files.append(
                {
                    "path": str(path.relative_to(root)),
                    "sha256": sha256(path),
                    "bytes": path.stat().st_size,
                }
            )
    return {
        "manifest_version": "1.0.0",
        "release_id": release_id,
        "files": files,
        "authority": "DATA_AND_RESEARCH_EVIDENCE_ONLY",
        "trade_authority": "NONE",
    }


def score_distribution(scores: pd.DataFrame) -> pd.DataFrame:
    valid = scores[scores["financial_score"].notna()].copy()
    rows: list[dict] = []
    for confidence, group in valid.groupby("score_confidence", dropna=False):
        values = pd.to_numeric(group["financial_score"], errors="coerce").dropna()
        rows.append(
            {
                "distribution_type": "CONFIDENCE",
                "distribution_key": str(confidence),
                "symbol_count": int(len(group)),
                "minimum": float(values.min()) if len(values) else None,
                "q10": float(values.quantile(0.10)) if len(values) else None,
                "q25": float(values.quantile(0.25)) if len(values) else None,
                "median": float(values.median()) if len(values) else None,
                "q75": float(values.quantile(0.75)) if len(values) else None,
                "q90": float(values.quantile(0.90)) if len(values) else None,
                "maximum": float(values.max()) if len(values) else None,
            }
        )
    for band, group in scores.groupby("score_band", dropna=False):
        values = pd.to_numeric(group["financial_score"], errors="coerce").dropna()
        rows.append(
            {
                "distribution_type": "SCORE_BAND",
                "distribution_key": str(band),
                "symbol_count": int(len(group)),
                "minimum": float(values.min()) if len(values) else None,
                "q10": float(values.quantile(0.10)) if len(values) else None,
                "q25": float(values.quantile(0.25)) if len(values) else None,
                "median": float(values.median()) if len(values) else None,
                "q75": float(values.quantile(0.75)) if len(values) else None,
                "q90": float(values.quantile(0.90)) if len(values) else None,
                "maximum": float(values.max()) if len(values) else None,
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["distribution_type", "distribution_key"]
    ).reset_index(drop=True)


def main() -> int:
    cfg = load_json(CONFIG)
    pointer = load_json(ROOT / cfg["entry_gate"]["pointer"])
    if pointer.get("status") != cfg["entry_gate"]["required_status"]:
        raise SystemExit("FMDL-3C-C entry gate not accepted")
    source_release = load_json(ROOT / pointer["current_release_path"])
    market_interface = load_json(ROOT / cfg["inputs"]["market_data_interface"])
    hardened = pd.read_parquet(ROOT / cfg["inputs"]["hardened_factor_current"])
    registry = pd.read_csv(
        ROOT / cfg["inputs"]["factor_registry"], encoding="utf-8-sig"
    )
    profiles = pd.read_csv(
        ROOT / cfg["inputs"]["profile_reconciliation"],
        encoding="utf-8-sig",
        dtype={"symbol": str},
    )
    weights = pd.read_csv(
        ROOT / cfg["inputs"]["factor_weights"], encoding="utf-8-sig"
    )
    validate_weight_table(weights, cfg)
    source_policy_overlap = [
        column
        for column in weights.columns
        if column != "factor_id" and column in hardened.columns
    ]
    if source_policy_overlap:
        hardened = hardened.drop(columns=source_policy_overlap)

    candidate = ROOT / cfg["publication"]["candidate_root"]
    if candidate.exists():
        shutil.rmtree(candidate)
    candidate.mkdir(parents=True, exist_ok=True)
    release_id = f"FMDL3CD_{datetime.now(TZ).strftime('%Y%m%dT%H%M%S%z')}"

    family_scores, component = build_family_scores(hardened, profiles, weights, cfg)
    scores = build_financial_scores(
        family_scores,
        component,
        profiles,
        cfg,
        pointer["release_id"],
    )
    contributions = build_factor_contributions(component, family_scores, scores)
    evidence = build_investment_os_evidence(scores, cfg)
    distribution = score_distribution(scores)

    score_path = candidate / "FMDL3CD_FINANCIAL_SCORE_CURRENT.parquet"
    family_path = candidate / "FMDL3CD_FAMILY_SCORES.parquet"
    contribution_path = candidate / "FMDL3CD_FACTOR_CONTRIBUTIONS.parquet"
    evidence_path = candidate / "FMDL3CD_INVESTMENT_OS_EVIDENCE.parquet"
    distribution_path = candidate / "FMDL3CD_SCORE_DISTRIBUTION.csv"
    weight_path = candidate / "FMDL3CD_SCORE_WEIGHTS.csv"
    scores.to_parquet(score_path, index=False, compression="zstd")
    family_scores.to_parquet(family_path, index=False, compression="zstd")
    contributions.to_parquet(contribution_path, index=False, compression="zstd")
    evidence.to_parquet(evidence_path, index=False, compression="zstd")
    distribution.to_csv(distribution_path, index=False, encoding="utf-8-sig")
    weights.to_csv(weight_path, index=False, encoding="utf-8-sig")

    current_root = cfg["publication"]["current_root"]
    interface = {
        "interface_version": "1.0.0",
        "interface_id": "FMDL_FINANCIAL_SCORE_INVESTMENT_OS_INTERFACE",
        "status": "ACTIVE_RESEARCH_ONLY",
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "source_release_id": pointer["release_id"],
        "market_data_interface_id": market_interface.get("interface_id"),
        "market_data_run_id": market_interface.get("current_release", {}).get("run_id"),
        "datasets": [
            {
                "dataset_id": "financial_score_current",
                "path": f"{current_root}/FMDL3CD_FINANCIAL_SCORE_CURRENT.parquet",
                "required_for": [
                    "PUBLIC_EQUITY_RESEARCH_PRIORITY",
                    "INVESTMENT_OS_RESEARCH_SCORE",
                    "CANDIDATE_POOL_FINANCIAL_EVIDENCE",
                ],
            },
            {
                "dataset_id": "financial_family_scores",
                "path": f"{current_root}/FMDL3CD_FAMILY_SCORES.parquet",
                "required_for": [
                    "FINANCIAL_SCORE_EXPLANATION",
                    "MISSING_FAMILY_REVIEW",
                ],
            },
            {
                "dataset_id": "financial_factor_contributions",
                "path": f"{current_root}/FMDL3CD_FACTOR_CONTRIBUTIONS.parquet",
                "required_for": [
                    "SCORE_REPLAY",
                    "FACTOR_CONTRIBUTION_EXPLANATION",
                ],
            },
            {
                "dataset_id": "investment_os_financial_evidence",
                "path": f"{current_root}/FMDL3CD_INVESTMENT_OS_EVIDENCE.parquet",
                "required_for": [
                    "CANDIDATE_POOL_EVIDENCE",
                    "SIMULATION_LAB_EVIDENCE",
                    "REAL_ACCOUNT_FINANCIAL_REVIEW",
                ],
            },
        ],
        "role_separation": {
            "candidate_pool": "Broad discovery and observation universe; the financial score changes research priority only and cannot automatically promote or remove a candidate.",
            "simulation_lab": "Strategy experiment and error-exposure environment; lower-score or lower-confidence names may remain for controlled experiments and are not treated as real-account previews.",
            "real_account": "Strict steady-compounding capital allocation; financial evidence is only one gate and cannot replace owner quality, valuation, ETF alternative, track record, portfolio fit, pre-trade memo or user confirmation.",
        },
        "consumer_contract": {
            "allowed_consumers": ["INVESTMENT_OS", "PUBLIC_EQUITY_INVESTING"],
            "required_prechecks": [
                "validate interface and release schemas",
                "validate FMDL-3C-C source release and hashes",
                "use only SCORE_ACCEPTED rows with controlled confidence",
                "surface family coverage, warning weight and all controlled exclusions",
                "retain candidate, simulation and real-account role separation",
            ],
            "prohibited_actions": [
                "creating BUY ADD REDUCE SELL permission from the financial score",
                "automatic candidate-pool promotion or deletion",
                "automatic simulation admission or graduation",
                "automatic real-account admission",
                "treating the financial score as owner quality, valuation or portfolio fit",
                "using financial-sector or unresolved-profile exclusions as zero scores",
                "automatic brokerage execution",
            ],
        },
        "downstream_reentry": (
            "FINANCIAL_RESEARCH_EVIDENCE -> PUBLIC_EQUITY_RESEARCH -> OWNER_QUALITY -> "
            "INVESTMENT_ATTRACTIVENESS -> ETF_ALTERNATIVE -> CANDIDATE_RACE -> "
            "SIMULATION_OR_SHADOW_TRACK -> PORTFOLIO_FIT -> CAPITAL_MIGRATION -> "
            "PRE_TRADE_MEMO -> USER_CONFIRMATION"
        ),
        "authority_boundary": "FINANCIAL_RESEARCH_EVIDENCE_ONLY_NO_PORTFOLIO_ACTION",
        "trade_authority": "NONE",
    }
    write_json(candidate / "FMDL3CD_INVESTMENT_OS_INTERFACE.json", interface)

    contribution_sum = (
        contributions[contributions["contribution_points"].notna()]
        .groupby("symbol")["contribution_points"]
        .sum()
    )
    scored = scores[scores["financial_score"].notna()].set_index("symbol")
    replay_error_count = int(
        sum(
            not np.isclose(
                float(contribution_sum.get(symbol, np.nan)),
                float(row.financial_score),
                atol=1e-8,
            )
            for symbol, row in scored.iterrows()
        )
    )
    strict_real = evidence[
        evidence["real_account_financial_evidence"].eq(
            "STRICT_FINANCIAL_REVIEW_FLOOR_MET"
        )
    ]
    expected_contribution_rows = len(profiles) * len(weights)
    weighted_factors = set(weights["factor_id"].astype(str))
    accepted_registry = set(
        registry.loc[
            registry["factor_gate_status"].eq("ACCEPTED_PRODUCTION_CORE"),
            "factor_id",
        ].astype(str)
    )
    checks = {
        "ENTRY_FMDL3CC_ACCEPTED": pointer.get("status")
        == cfg["entry_gate"]["required_status"],
        "SOURCE_RELEASE_ALIGNED": source_release.get("release_id")
        == pointer.get("release_id"),
        "WEIGHTED_FACTORS_ACCEPTED_CORE": weighted_factors.issubset(accepted_registry),
        "WEIGHT_TABLE_EXACT_18": len(weights) == 18
        and not weights["factor_id"].duplicated().any(),
        "FAMILY_WEIGHTS_SUM_ONE": np.isclose(
            sum(cfg["score"]["family_weights"].values()), 1.0, atol=1e-10
        ),
        "GLOBAL_FACTOR_WEIGHTS_SUM_ONE": np.isclose(
            pd.to_numeric(weights["global_weight"]).sum(), 1.0, atol=1e-10
        ),
        "SCORE_CURRENT_EXACT_UNIVERSE": len(scores) == len(profiles)
        and not scores["symbol"].duplicated().any(),
        "FAMILY_ROWS_EXACT_UNIVERSE_X4": len(family_scores)
        == len(profiles) * len(FAMILY_ORDER),
        "CONTRIBUTION_ROWS_EXACT_UNIVERSE_X18": len(contributions)
        == expected_contribution_rows,
        "INTERFACE_EVIDENCE_EXACT_UNIVERSE": len(evidence) == len(profiles)
        and not evidence["symbol"].duplicated().any(),
        "SCORES_BOUNDED": scores.loc[
            scores["financial_score"].notna(), "financial_score"
        ].between(0, 100, inclusive="both").all(),
        "FAMILY_SCORES_BOUNDED": family_scores.loc[
            family_scores["family_score"].notna(), "family_score"
        ].between(0, 100, inclusive="both").all(),
        "SCORE_CONTRIBUTIONS_REPLAY": replay_error_count == 0,
        "RANKING_ROWS_GENERAL_NON_FINANCIAL_ONLY": scores.loc[
            scores["ranking_eligible"], "sector_profile"
        ].eq(cfg["score"]["authorized_profile"]).all(),
        "STRICT_REAL_FLOOR_REPLAY": (
            strict_real["financial_score"]
            .ge(cfg["investment_os"]["strict_real_account_financial_floor"])
            .all()
            and strict_real["score_confidence"]
            .eq(cfg["investment_os"]["strict_real_account_required_confidence"])
            .all()
            and strict_real["available_family_count"].eq(4).all()
        ),
        "ZERO_AUTOMATIC_ACTION_AUTHORITY": not evidence[
            [
                "candidate_pool_action_authorized",
                "simulation_admission_authorized",
                "real_account_admission_authorized",
                "portfolio_action_authorized",
                "order_execution_authorized",
            ]
        ].any().any(),
        "ZERO_TRADE_AUTHORITY": set(
            scores["trade_authority"].dropna().astype(str)
        ).issubset({"NONE"})
        and set(evidence["trade_authority"].dropna().astype(str)).issubset(
            {"NONE"}
        ),
    }
    failures = [name for name, passed in checks.items() if not bool(passed)]
    metrics = {
        "source_hardening_release_id": pointer["release_id"],
        "universe_symbol_count": len(profiles),
        "financial_score_row_count": len(scores),
        "family_score_row_count": len(family_scores),
        "factor_contribution_row_count": len(contributions),
        "interface_evidence_row_count": len(evidence),
        "weighted_factor_count": len(weights),
        "score_available_symbol_count": int(scores["financial_score"].notna().sum()),
        "ranking_eligible_symbol_count": int(scores["ranking_eligible"].sum()),
        "high_confidence_symbol_count": int(scores["score_confidence"].eq("HIGH").sum()),
        "medium_confidence_symbol_count": int(scores["score_confidence"].eq("MEDIUM").sum()),
        "low_confidence_symbol_count": int(scores["score_confidence"].eq("LOW").sum()),
        "score_unavailable_symbol_count": int(scores["financial_score"].isna().sum()),
        "strict_real_account_financial_floor_met_count": len(strict_real),
        "positive_candidate_evidence_count": int(
            evidence["candidate_pool_financial_evidence"].eq(
                "POSITIVE_FINANCIAL_QUALITY_EVIDENCE"
            ).sum()
        ),
        "supportive_candidate_evidence_count": int(
            evidence["candidate_pool_financial_evidence"].eq(
                "SUPPORTIVE_FINANCIAL_QUALITY_EVIDENCE"
            ).sum()
        ),
        "score_contribution_replay_error_count": replay_error_count,
        "automatic_action_authorized_count": 0,
    }
    decision = {
        "decision_version": "1.0.0",
        "release_id": release_id,
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "program_id": "FMDL-3C-D",
        "status": cfg["exit_status"]
        if not failures
        else "FMDL3CD_REMEDIATION_REQUIRED",
        "hard_failures": failures,
        "checks": [
            {"check_id": name, "status": "PASS" if passed else "FAIL"}
            for name, passed in checks.items()
        ],
        "metrics": metrics,
        "controlled_limitations": [
            "SCORE_IS_CROSS_SECTIONAL_GENERAL_NON_FINANCIAL_NOT_INDUSTRY_NEUTRAL",
            "BANK_INSURANCE_AND_BROKERAGE_SCORE_PACKS_NOT_YET_AVAILABLE",
            "TWO_THREE_YEAR_CAGR_FACTORS_REMAIN_DEFERRED",
            "NINE_DIAGNOSTIC_FACTORS_DO_NOT_ENTER_THE_SCORE",
            "MISSING_FACTORS_ARE_REWEIGHTED_ONLY_AFTER_MINIMUM_COVERAGE_GATES",
            "FINANCIAL_SCORE_IS_NOT_OWNER_QUALITY_VALUATION_PORTFOLIO_FIT_OR_TRADE_PERMISSION",
        ],
        "authority": cfg["authority"],
        "trade_authority": "NONE",
        "next_gate": cfg["next_gate"],
    }
    write_json(candidate / "FMDL3CD_DECISION.json", decision)
    write_json(candidate / "FMDL3CD_SOURCE_POINTER.json", pointer)
    write_json(candidate / "FMDL3CD_SOURCE_RELEASE.json", source_release)
    write_json(candidate / "FMDL3CD_MARKET_INTERFACE_SNAPSHOT.json", market_interface)
    write_json(candidate / "FMDL3CD_MANIFEST.json", manifest(candidate, release_id))
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
