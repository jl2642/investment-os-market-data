#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

PROGRAM_ID = "HKCU-P2A"
TRADE_AUTHORITY = "NONE"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def as_bool(value: Any) -> bool:
    return value is True or str(value).strip().lower() in {"1", "true", "yes", "y"}


def finite(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def deterministic_kmeans_1d(values: pd.Series, k: int = 3) -> tuple[np.ndarray, np.ndarray]:
    x = pd.to_numeric(values, errors="coerce").to_numpy(dtype=float)
    if len(x) < k or not np.isfinite(x).all():
        raise RuntimeError("DISTRIBUTION_SCORE_INVALID")
    if float(np.nanmax(x) - np.nanmin(x)) <= 1e-12:
        raise RuntimeError("DISTRIBUTION_SCORE_NO_VARIANCE")
    qs = np.linspace(0.2, 0.8, k)
    centroids = np.quantile(x, qs)
    for _ in range(200):
        labels = np.abs(x[:, None] - centroids[None, :]).argmin(axis=1)
        updated = np.array(
            [x[labels == i].mean() if np.any(labels == i) else centroids[i] for i in range(k)],
            dtype=float,
        )
        updated.sort()
        if np.allclose(updated, centroids, rtol=0, atol=1e-12):
            centroids = updated
            break
        centroids = updated
    labels = np.abs(x[:, None] - centroids[None, :]).argmin(axis=1)
    return labels, centroids


def validate_canonical(
    frame: pd.DataFrame,
    hkcu_decision: dict[str, Any],
    hkcu_quality: dict[str, Any],
    contract: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    required = set(contract["required_input_columns"])
    missing = sorted(required - set(frame.columns))
    if missing:
        errors.append("MISSING_REQUIRED_COLUMNS:" + ",".join(missing))
        return errors
    expected = int(hkcu_decision.get("provisional_investable_count", -1))
    if hkcu_decision.get("status") != "PASS_CURRENT":
        errors.append("HKCU_DECISION_NOT_PASS_CURRENT")
    if hkcu_quality.get("status") != "PASS" or hkcu_quality.get("hard_failures"):
        errors.append("HKCU_QUALITY_NOT_PASS")
    if len(frame) != expected:
        errors.append(f"CANONICAL_COUNT_MISMATCH:{len(frame)}:{expected}")
    if int(frame["security_id"].astype(str).duplicated().sum()) != 0:
        errors.append("DUPLICATE_SECURITY_ID")
    gates = {
        "PUBLICATION_NOT_ELIGIBLE": frame["publication_eligible"].map(as_bool),
        "R2E_GATE_FAIL": frame["r2e_gate_pass"].map(as_bool),
        "NOT_BUY_ELIGIBLE": frame["buy_eligible"].map(as_bool),
        "SELL_ONLY_PRESENT": ~frame["sell_only"].map(as_bool),
        "FRESHNESS_NOT_CURRENT": frame["freshness_status"].astype(str).eq("CURRENT"),
        "TRADE_AUTHORITY_NOT_NONE": frame["trade_authority"].astype(str).eq(TRADE_AUTHORITY),
    }
    for code, mask in gates.items():
        if not bool(mask.all()):
            errors.append(f"{code}:{int((~mask).sum())}")
    allowed = set(contract["allowed_investability_status"])
    bad_status = ~frame["investability_status"].astype(str).isin(allowed)
    if bool(bad_status.any()):
        errors.append(f"INVESTABILITY_STATUS_NOT_ALLOWED:{int(bad_status.sum())}")
    return errors


def evaluate_sleeve(
    frame: pd.DataFrame,
    sleeve_id: str,
    sleeve: dict[str, Any],
) -> pd.DataFrame:
    allowed = {"ELIGIBLE_CORE"} if sleeve["route"] == "CORE" else {"ELIGIBLE_CORE", "ELIGIBLE_WATCH"}
    x = frame[frame["investability_status"].astype(str).isin(allowed)].copy()
    weights = {str(k): float(v) for k, v in sleeve["weights"].items()}
    if abs(sum(weights.values()) - 1.0) > 1e-9:
        raise RuntimeError(f"SLEEVE_WEIGHT_SUM:{sleeve_id}")
    pct_cols = [f"{f}__pct" for f in weights]
    missing = [c for c in pct_cols if c not in x.columns]
    if missing:
        raise RuntimeError(f"SLEEVE_PERCENTILES_MISSING:{sleeve_id}:{','.join(missing)}")
    x["component_count"] = x[pct_cols].notna().sum(axis=1)
    x["component_weight"] = sum(
        np.where(x[f"{factor}__pct"].notna(), weight, 0.0)
        for factor, weight in weights.items()
    )
    x = x[x["component_count"] >= int(sleeve["minimum_components"])].copy()
    if x.empty:
        return pd.DataFrame()
    weighted = sum(
        pd.to_numeric(x[f"{factor}__pct"], errors="coerce").fillna(0.0) * weight
        for factor, weight in weights.items()
    )
    x["sleeve_score"] = (
        weighted / x["component_weight"] * (0.85 + 0.15 * x["component_weight"])
    )
    x = (
        x[x["sleeve_score"] >= float(sleeve["minimum_score"])]
        .sort_values(
            ["sleeve_score", "avg_turnover_hkd_20d", "security_id"],
            ascending=[False, False, True],
        )
        .head(int(sleeve["maximum_candidates"]))
        .copy()
    )
    if x.empty:
        return pd.DataFrame()
    x["sleeve_rank"] = range(1, len(x) + 1)
    x["sleeve_population"] = len(x)
    x["sleeve_rank_percentile"] = (len(x) - x["sleeve_rank"] + 1) / max(1, len(x))
    x["sleeve_id"] = sleeve_id
    x["sleeve_route"] = sleeve["route"]
    x["component_score_json"] = x.apply(
        lambda row: json.dumps(
            {
                factor: {"percentile": finite(row.get(f"{factor}__pct")), "weight": weight}
                for factor, weight in weights.items()
                if finite(row.get(f"{factor}__pct")) is not None
            },
            sort_keys=True,
        ),
        axis=1,
    )
    keep = [
        "as_of_date_fmdl5e", "security_id", "stock_code_5d",
        "official_security_name_en", "official_issuer_name_en",
        "investability_status", "factor_record_quality", "confidence_grade",
        "profile", "sleeve_id", "sleeve_route", "sleeve_rank",
        "sleeve_population", "sleeve_rank_percentile", "sleeve_score",
        "component_count", "component_weight", "component_score_json",
        "avg_turnover_hkd_20d",
    ]
    return x[[c for c in keep if c in x.columns]]


def research_readiness(row: pd.Series, coverage_ratio: float) -> str:
    grade = str(row.get("confidence_grade") or "")
    quality = str(row.get("factor_record_quality") or "")
    if grade == "A" and quality == "VALID" and coverage_ratio >= 0.75:
        return "READY_HIGH"
    if grade in {"A", "B"} and quality in {"VALID", "VALID_WITH_CONTROLLED_NULLS"} and coverage_ratio >= 0.60:
        return "READY_CONTROLLED"
    return "READY_PARTIAL"


def build_longlist(
    frame: pd.DataFrame,
    sleeve_detail: pd.DataFrame,
    contract: dict[str, Any],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if sleeve_detail.empty:
        raise RuntimeError("NO_FORMAL_SLEEVE_CANDIDATES")
    factor_ids = [str(item["factor_id"]) for item in contract["factor_dictionary"]]
    pct_cols = [f"{factor}__pct" for factor in factor_ids]
    ranked_rows: list[dict[str, Any]] = []
    funnel = contract["selection_policy"]
    for security_id, group in sleeve_detail.groupby("security_id", sort=True):
        ordered = group.sort_values(
            ["sleeve_rank_percentile", "sleeve_score", "sleeve_id"],
            ascending=[False, False, True],
        )
        best = ordered.iloc[0]
        sleeves = ordered["sleeve_id"].astype(str).tolist()
        bonus = min(
            float(funnel["cross_sleeve_bonus_maximum"]),
            max(0, len(sleeves) - 1) * float(funnel["cross_sleeve_bonus_per_extra_sleeve"]),
        )
        ranked_rows.append(
            {
                "security_id": str(security_id),
                "primary_sleeve": str(best["sleeve_id"]),
                "sleeves": "|".join(sleeves),
                "sleeve_count": len(sleeves),
                "best_sleeve_score": float(best["sleeve_score"]),
                "normalized_primary_score": float(best["sleeve_rank_percentile"]),
                "cross_sleeve_bonus": bonus,
                "aggregate_score": float(best["sleeve_rank_percentile"])
                + 0.25 * float(best["sleeve_score"])
                + bonus,
            }
        )
    ranked = pd.DataFrame(ranked_rows).merge(
        frame, on="security_id", how="left", validate="one_to_one"
    )
    if ranked["stock_code_5d"].isna().any():
        raise RuntimeError("SLEEVE_SECURITY_NOT_IN_CANONICAL")
    available = ranked[pct_cols].notna().sum(axis=1)
    ranked["factor_available_count"] = available
    ranked["factor_total_count"] = len(pct_cols)
    ranked["factor_coverage_ratio"] = available / max(1, len(pct_cols))
    ranked["research_readiness"] = [
        research_readiness(row, float(cov))
        for (_, row), cov in zip(ranked.iterrows(), ranked["factor_coverage_ratio"])
    ]
    applicable_gaps = []
    for _, row in ranked.iterrows():
        gaps = [
            "GOVERNANCE_VALUE_TRAP",
            "EARNINGS_EXPECTATION_REVISION",
            "CATALYST",
            "TRANSACTION_COST_TAX",
        ]
        if as_bool(row.get("a_share_class_exists")) or as_bool(row.get("h_share_flag")):
            gaps.append("A_H_RELATIVE_VALUATION")
        applicable_gaps.append("|".join(gaps))
    ranked["p2b_required_dimensions"] = applicable_gaps

    ranked = ranked.sort_values(
        ["aggregate_score", "normalized_primary_score", "best_sleeve_score",
         "avg_turnover_hkd_20d", "security_id"],
        ascending=[False, False, False, False, True],
    ).reset_index(drop=True)
    labels, centroids = deterministic_kmeans_1d(
        ranked["aggregate_score"], int(funnel["distribution_clusters"])
    )
    ranked["_cluster"] = labels
    high_cluster = int(np.argmax(centroids))
    ranked["distribution_cluster"] = ranked["_cluster"].map(
        {i: ("HIGH" if i == high_cluster else f"NON_HIGH_{i}") for i in range(len(centroids))}
    )
    longlist = ranked[ranked["_cluster"] == high_cluster].copy()
    longlist = longlist.sort_values(
        ["aggregate_score", "factor_coverage_ratio", "avg_turnover_hkd_20d", "security_id"],
        ascending=[False, False, False, True],
    ).reset_index(drop=True)
    longlist["overall_rank"] = range(1, len(longlist) + 1)
    longlist["research_priority"] = "P2A_RESEARCH_LONGLIST"
    longlist["next_workflow"] = "HKCU-P2B_RESEARCH_ENRICHMENT"
    longlist["authority"] = "RESEARCH_PRIORITY_ONLY"
    longlist["trade_authority"] = TRADE_AUTHORITY
    longlist = longlist.drop(columns=["_cluster"], errors="ignore")

    distribution = {
        "method": "DETERMINISTIC_1D_KMEANS",
        "cluster_count": int(funnel["distribution_clusters"]),
        "centroids": [float(v) for v in centroids],
        "selected_cluster": high_cluster,
        "selected_cluster_centroid": float(centroids[high_cluster]),
        "candidate_count": int(len(ranked)),
        "longlist_count": int(len(longlist)),
        "longlist_share_of_canonical": float(len(longlist) / max(1, len(frame))),
        "fixed_target_count_used": False,
    }
    order = [
        "eligibility_as_of_date", "fmdl5e_as_of_date", "overall_rank",
        "research_priority", "security_id", "stock_code_5d",
        "official_security_name_en", "official_issuer_name_en",
        "primary_sleeve", "sleeves", "sleeve_count", "aggregate_score",
        "normalized_primary_score", "best_sleeve_score", "cross_sleeve_bonus",
        "distribution_cluster", "factor_available_count", "factor_total_count",
        "factor_coverage_ratio", "research_readiness", "p2b_required_dimensions",
        "investability_status", "factor_record_quality", "confidence_grade",
        "profile", "latest_close", "latest_quote_currency", "avg_turnover_hkd_20d",
        "return_20d", "return_60d", "return_120d", "return_250d",
        "volatility_60d", "max_drawdown_120d", "roe", "roa",
        "operating_margin", "revenue_yoy", "net_income_yoy",
        "earnings_yield", "pe_ratio", "dividend_yield_365d",
        "a_share_class_exists", "h_share_flag", "wvr_flag", "dual_counter_flag",
        "secondary_listing_flag", "biotech_chapter18a_flag",
        "next_workflow", "authority", "trade_authority",
    ]
    return longlist[[c for c in order if c in longlist.columns]], distribution


def build_missingness(longlist: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, row in longlist.iterrows():
        for dimension in str(row["p2b_required_dimensions"]).split("|"):
            rows.append(
                {
                    "security_id": row["security_id"],
                    "stock_code_5d": row["stock_code_5d"],
                    "overall_rank": int(row["overall_rank"]),
                    "research_dimension": dimension,
                    "status": "P2B_REQUIRED",
                    "score_contribution_in_p2a": 0,
                    "trade_authority": TRADE_AUTHORITY,
                }
            )
    return pd.DataFrame(rows)


def build_funnel(
    canonical_count: int,
    sleeve_detail: pd.DataFrame,
    longlist: pd.DataFrame,
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"stage": "CANONICAL_HKCU_CURRENT", "count": canonical_count},
            {"stage": "CANONICAL_SAFETY_GATE_PASS", "count": canonical_count},
            {
                "stage": "FORMAL_FIVE_SLEEVE_UNION",
                "count": int(sleeve_detail["security_id"].astype(str).nunique()),
            },
            {"stage": "DISTRIBUTION_HIGH_CLUSTER_LONGLIST", "count": len(longlist)},
        ]
    )


def build_quality(
    canonical: pd.DataFrame,
    sleeve_detail: pd.DataFrame,
    longlist: pd.DataFrame,
    distribution: dict[str, Any],
    contract: dict[str, Any],
    canonical_errors: list[str],
) -> dict[str, Any]:
    errors = list(canonical_errors)
    warnings: list[str] = []
    sleeve_ids = set(contract["sleeves"])
    observed_sleeves = set(sleeve_detail["sleeve_id"].astype(str)) if not sleeve_detail.empty else set()
    if observed_sleeves != sleeve_ids:
        errors.append("FORMAL_SLEEVE_SET_MISMATCH")
    if longlist.empty:
        errors.append("LONGLIST_EMPTY")
    if int(longlist["security_id"].astype(str).duplicated().sum()) != 0:
        errors.append("LONGLIST_DUPLICATE_SECURITY")
    mother = set(canonical["security_id"].astype(str))
    if not set(longlist["security_id"].astype(str)).issubset(mother):
        errors.append("LONGLIST_NOT_SUBSET_OF_CANONICAL")
    if not longlist.empty and not longlist["trade_authority"].astype(str).eq(TRADE_AUTHORITY).all():
        errors.append("TRADE_AUTHORITY_MUTATION")
    share = float(distribution["longlist_share_of_canonical"])
    safety = contract["acceptance"]["distribution_share_safety_envelope"]
    if not (float(safety["minimum"]) <= share <= float(safety["maximum"])):
        errors.append(
            f"DISTRIBUTION_SELECTION_OUTSIDE_SAFETY_ENVELOPE:{share:.6f}"
        )
    primary = (
        longlist["primary_sleeve"].value_counts().astype(int).to_dict()
        if not longlist.empty else {}
    )
    if len(primary) < int(contract["acceptance"]["minimum_primary_sleeves_in_longlist"]):
        warnings.append("LONGLIST_PRIMARY_SLEEVE_BREADTH_BELOW_FULL_FIVE")
    readiness = (
        longlist["research_readiness"].value_counts().astype(int).to_dict()
        if not longlist.empty else {}
    )
    return {
        "program_id": PROGRAM_ID,
        "phase": "P2A",
        "status": "PASS" if not errors else "FAIL",
        "canonical_count": int(len(canonical)),
        "formal_sleeve_union_count": int(
            sleeve_detail["security_id"].astype(str).nunique() if not sleeve_detail.empty else 0
        ),
        "longlist_count": int(len(longlist)),
        "longlist_share_of_canonical": share,
        "selection_distribution": distribution,
        "primary_sleeve_counts": primary,
        "research_readiness_counts": readiness,
        "duplicate_security_count": int(longlist["security_id"].astype(str).duplicated().sum())
        if not longlist.empty else 0,
        "candidate_pool_mutations": 0,
        "simulation_mutations": 0,
        "real_account_mutations": 0,
        "orders_created": 0,
        "trade_authority": TRADE_AUTHORITY,
        "warnings": warnings,
        "hard_failures": errors,
    }


def write_outputs(
    root: Path,
    output: Path,
    canonical_path: Path,
    canonical: pd.DataFrame,
    sleeve_detail: pd.DataFrame,
    longlist: pd.DataFrame,
    missingness: pd.DataFrame,
    funnel: pd.DataFrame,
    quality: dict[str, Any],
    hkcu_decision: dict[str, Any],
    hkcu_quality: dict[str, Any],
    contract_path: Path,
) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    paths = {
        "sleeve_detail": output / "HKCU_P2A_SLEEVE_DETAIL.csv",
        "longlist": output / "HKCU_P2A_RESEARCH_LONGLIST.csv",
        "missingness": output / "HKCU_P2A_RESEARCH_MISSINGNESS.csv",
        "funnel": output / "HKCU_P2A_FUNNEL_COUNTS.csv",
        "quality": output / "HKCU_P2A_QUALITY_REPORT.json",
        "decision": output / "HKCU_P2A_DECISION.json",
        "manifest": output / "HKCU_P2A_MANIFEST.json",
    }
    sleeve_detail.to_csv(paths["sleeve_detail"], index=False, encoding="utf-8-sig")
    longlist.to_csv(paths["longlist"], index=False, encoding="utf-8-sig")
    missingness.to_csv(paths["missingness"], index=False, encoding="utf-8-sig")
    funnel.to_csv(paths["funnel"], index=False, encoding="utf-8-sig")
    paths["quality"].write_text(
        json.dumps(quality, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    decision = {
        "program_id": PROGRAM_ID,
        "phase": "P2A",
        "status": "PASS_P2A_RESEARCH_LONGLIST" if quality["status"] == "PASS" else "BLOCKED",
        "canonical_hkcu_count": int(len(canonical)),
        "longlist_count": int(len(longlist)),
        "longlist_count_policy": "DISTRIBUTION_DERIVED_NO_FIXED_TARGET",
        "selection_method": quality["selection_distribution"]["method"],
        "eligibility_as_of_date": hkcu_decision.get("eligibility_as_of_date"),
        "fmdl5e_as_of_date": hkcu_decision.get("fmdl5e_as_of_date"),
        "next_gate": "P2B_RESEARCH_ENRICHMENT" if quality["status"] == "PASS" else "P2A_REPAIR",
        "candidate_pool_mutations": 0,
        "simulation_mutations": 0,
        "real_account_mutations": 0,
        "orders_created": 0,
        "trade_authority": TRADE_AUTHORITY,
    }
    paths["decision"].write_text(
        json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "program_id": PROGRAM_ID,
        "phase": "P2A",
        "inputs": {
            str(canonical_path.relative_to(root)): sha256_file(canonical_path),
            "outputs/hkcu1/current/HKCU1_R2E_DECISION.json": sha256_file(
                root / "outputs/hkcu1/current/HKCU1_R2E_DECISION.json"
            ),
            "outputs/hkcu1/current/HKCU1_R2E_QUALITY_REPORT.json": sha256_file(
                root / "outputs/hkcu1/current/HKCU1_R2E_QUALITY_REPORT.json"
            ),
            str(contract_path.relative_to(root)): sha256_file(contract_path),
        },
        "upstream": {
            "hkcu_decision_status": hkcu_decision.get("status"),
            "hkcu_quality_status": hkcu_quality.get("status"),
            "eligibility_as_of_date": hkcu_decision.get("eligibility_as_of_date"),
            "fmdl5e_as_of_date": hkcu_decision.get("fmdl5e_as_of_date"),
        },
        "outputs": {
            path.name: sha256_file(path)
            for key, path in paths.items()
            if key != "manifest" and path.exists()
        },
        "trade_authority": TRADE_AUTHORITY,
    }
    paths["manifest"].write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if quality["status"] != "PASS":
        raise RuntimeError("P2A_QUALITY_FAILED:" + ";".join(quality["hard_failures"]))
    return decision


def run(repo_root: Path, output: Path) -> dict[str, Any]:
    contract_path = repo_root / "config/hkcu_p2a_research_longlist_contract.json"
    contract = read_json(contract_path)
    canonical_path = repo_root / contract["authoritative_inputs"]["hkcu_current"]
    hkcu_decision_path = repo_root / contract["authoritative_inputs"]["hkcu_decision"]
    hkcu_quality_path = repo_root / contract["authoritative_inputs"]["hkcu_quality"]
    canonical = pd.read_csv(
        canonical_path,
        dtype={"stock_code_5d": str, "security_code": str},
        encoding="utf-8-sig",
    )
    hkcu_decision = read_json(hkcu_decision_path)
    hkcu_quality = read_json(hkcu_quality_path)
    errors = validate_canonical(canonical, hkcu_decision, hkcu_quality, contract)
    if errors:
        raise RuntimeError("P2A_CANONICAL_GATE_FAILED:" + ";".join(errors))
    sleeve_parts = [
        evaluate_sleeve(canonical, sleeve_id, sleeve)
        for sleeve_id, sleeve in contract["sleeves"].items()
    ]
    sleeve_detail = pd.concat(
        [part for part in sleeve_parts if not part.empty],
        ignore_index=True,
    ) if any(not part.empty for part in sleeve_parts) else pd.DataFrame()
    longlist, distribution = build_longlist(canonical, sleeve_detail, contract)
    missingness = build_missingness(longlist)
    funnel = build_funnel(len(canonical), sleeve_detail, longlist)
    quality = build_quality(
        canonical, sleeve_detail, longlist, distribution, contract, errors
    )
    return write_outputs(
        repo_root, output, canonical_path, canonical, sleeve_detail, longlist,
        missingness, funnel, quality, hkcu_decision, hkcu_quality, contract_path
    )


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--repo-root", type=Path, default=Path("."))
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    root = args.repo_root.resolve()
    output = args.output if args.output.is_absolute() else root / args.output
    decision = run(root, output)
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
