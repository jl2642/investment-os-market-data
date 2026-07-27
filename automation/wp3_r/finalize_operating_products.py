#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def digest(payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def normalize_security_id(value: Any) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    raw = str(value).strip().upper()
    if not raw:
        return None
    if "." in raw:
        code, suffix = raw.split(".", 1)
        return f"{code.zfill(6)}.{suffix}"
    code = raw.zfill(6)
    if code.startswith(("4", "8", "92")):
        return f"{code}.BJ"
    if code.startswith(("5", "6")):
        return f"{code}.SH"
    return f"{code}.SZ"


def collect_candidate_rows(value: Any, route: str = "ROOT") -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if isinstance(value, dict):
        raw = None
        for key in ("security_id", "security_code", "stock_code", "code", "symbol"):
            if key in value:
                raw = value[key]
                break
        sid = normalize_security_id(raw)
        if sid:
            rows.append(
                {
                    "security_id": sid,
                    "security_name": str(value.get("security_name") or value.get("stock_name") or ""),
                    "route": route,
                }
            )
        for key, child in value.items():
            if isinstance(child, (dict, list)):
                rows.extend(collect_candidate_rows(child, key.upper()))
    elif isinstance(value, list):
        for child in value:
            rows.extend(collect_candidate_rows(child, route))
    return rows


def tracked_candidates(candidate: dict[str, Any]) -> list[dict[str, str]]:
    allowed = {"CANDIDATE_CORE_MEMBERS", "SHADOW_TRACK_MEMBERS", "RESEARCH_QUEUE_MEMBERS"}
    result: dict[str, dict[str, str]] = {}
    for row in collect_candidate_rows(candidate):
        if row["route"] in allowed:
            result[row["security_id"]] = row
    return sorted(result.values(), key=lambda row: (row["route"], row["security_id"]))


def weekly_screen(
    candidate: dict[str, Any],
    market: pd.DataFrame,
    as_of: date,
    max_age_days: int,
) -> dict[str, Any]:
    tracked = tracked_candidates(candidate)
    frame = market.copy()
    frame["security_id"] = frame["security_code"].map(normalize_security_id)
    lookup = {row["security_id"]: row for _, row in frame.iterrows() if row["security_id"]}
    rows, missing, stale = [], [], []
    for target in tracked:
        source = lookup.get(target["security_id"])
        if source is None:
            missing.append(target["security_id"])
            continue
        mark_date = pd.Timestamp(source["provider_session_date"]).date()
        age = (as_of - mark_date).days
        status = "FRESH" if age <= max_age_days else "STALE"
        if status != "FRESH":
            stale.append(target["security_id"])
        rows.append(
            {
                "security_id": target["security_id"],
                "security_name": target["security_name"] or str(source.get("security_name") or ""),
                "candidate_route": target["route"],
                "price": float(source["last_price"]),
                "price_as_of": mark_date.isoformat(),
                "price_age_calendar_days": age,
                "one_day_change_pct": float(source["change_pct"]),
                "turnover_amount": float(source["turnover_amount"]),
                "turnover_rate_pct": float(source["turnover_rate_pct"]),
                "pe_ttm": float(source["pe_ttm"]) if pd.notna(source["pe_ttm"]) else None,
                "pb": float(source["pb"]) if pd.notna(source["pb"]) else None,
                "freshness_status": status,
                "screen_role": "PRICE_VALUATION_AND_LIQUIDITY_MONITOR_ONLY",
            }
        )
    return {
        "state_id": "WP3R_WEEKLY_PRICE_SCREEN_CURRENT",
        "status": "PASS_WEEKLY_PRICE_SCREEN_NO_MEMBERSHIP_MUTATION" if not missing and not stale and len(rows) == 73 else "PARTIAL_WEEKLY_PRICE_SCREEN",
        "as_of_date": as_of.isoformat(),
        "tracked_count": len(tracked),
        "covered_count": len(rows),
        "missing_security_ids": missing,
        "stale_security_ids": stale,
        "rows": rows,
        "candidate_membership_mutations": 0,
        "research_object_mutations": 0,
        "buy_signals": 0,
        "orders": 0,
        "trade_authority": "NONE",
    }


def industry_quality(
    market: pd.DataFrame,
    industry: pd.DataFrame,
    profiles: pd.DataFrame,
) -> dict[str, Any]:
    market_ids = set(market["security_code"].map(normalize_security_id).dropna())
    industry["security_id"] = industry["security_id"].map(normalize_security_id)
    current = industry[industry["security_id"].isin(market_ids)].copy()
    resolved = current["industry_name"].fillna("").astype(str).str.strip().ne("") & current["industry_name"].ne("UNRESOLVED")
    coverage = float(resolved.mean()) if len(current) else 0.0
    missing_ids = sorted(market_ids - set(current["security_id"]))
    profile_frame = profiles[["symbol", "sector_profile"]].copy()
    profile_frame["security_id"] = profile_frame["symbol"].map(normalize_security_id)
    merged = profile_frame.merge(current[["security_id", "industry_name"]], on="security_id", how="left")
    conflicts = []
    for _, row in merged.iterrows():
        name = str(row.get("industry_name") or "")
        profile = str(row.get("sector_profile") or "")
        expected = {
            "BANK": ("银行",),
            "INSURANCE": ("保险",),
            "SECURITIES_AND_BROKERAGE": ("证券", "多元金融"),
        }.get(profile)
        if expected and name and not any(token in name for token in expected):
            conflicts.append({"security_id": row["security_id"], "sector_profile": profile, "industry_name": name})
    status = "PASS_CANONICAL_INDUSTRY_QUALITY_GATE" if coverage >= 0.99 and not missing_ids and not conflicts else "PARTIAL_INDUSTRY_MASTER_REVIEW_REQUIRED"
    return {
        "state_id": "WP3R_INDUSTRY_CLASSIFICATION_QUALITY_CURRENT",
        "status": status,
        "market_security_count": len(market_ids),
        "industry_master_rows_in_market": int(len(current)),
        "resolved_industry_count": int(resolved.sum()),
        "industry_coverage": round(coverage, 8),
        "missing_security_ids": missing_ids,
        "financial_profile_conflicts": conflicts,
        "financial_profile_conflict_count": len(conflicts),
        "industry_relative_ranking_allowed": status == "PASS_CANONICAL_INDUSTRY_QUALITY_GATE",
        "classification_source": "EASTMONEY_F100_INDUSTRY",
        "strategy_sleeve_as_industry_substitute_forbidden": True,
        "candidate_membership_mutations": 0,
        "orders": 0,
        "trade_authority": "NONE",
    }


def percentile_rank(series: pd.Series, *, lower_is_better: bool = False) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    rank = numeric.rank(pct=True, method="average") * 100.0
    return 100.0 - rank if lower_is_better else rank


def financial_screening_scores(
    family: pd.DataFrame,
    profiles: pd.DataFrame,
    market: pd.DataFrame,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    profile_names = {"BANK", "INSURANCE", "SECURITIES_AND_BROKERAGE"}
    family = family.copy()
    family["security_id"] = family["symbol"].map(normalize_security_id)
    pivot = family.pivot_table(index=["security_id", "sector_profile"], columns="family_id", values="family_score", aggfunc="first").reset_index()
    profile_frame = profiles[["symbol", "sector_profile"]].copy()
    profile_frame["security_id"] = profile_frame["symbol"].map(normalize_security_id)
    profile_frame = profile_frame[profile_frame["sector_profile"].isin(profile_names)]
    market_frame = market[["security_code", "security_name", "pb", "total_market_cap", "turnover_amount"]].copy()
    market_frame["security_id"] = market_frame["security_code"].map(normalize_security_id)
    merged = profile_frame[["security_id", "sector_profile"]].merge(pivot, on=["security_id", "sector_profile"], how="left").merge(market_frame, on="security_id", how="left")
    rows = []
    profile_summary = {}
    weights = {
        "BANK": (0.50, 0.20, 0.30),
        "INSURANCE": (0.40, 0.35, 0.25),
        "SECURITIES_AND_BROKERAGE": (0.35, 0.40, 0.25),
    }
    for profile, group in merged.groupby("sector_profile"):
        group = group.copy()
        group["profitability_score"] = pd.to_numeric(group.get("PROFITABILITY_RETURNS"), errors="coerce")
        group["growth_score"] = pd.to_numeric(group.get("GROWTH_MOMENTUM"), errors="coerce")
        group["pb_value"] = pd.to_numeric(group["pb"], errors="coerce")
        group["valuation_score"] = percentile_rank(group["pb_value"].where(group["pb_value"] > 0), lower_is_better=True)
        wp, wg, wv = weights[profile]
        group["screening_score"] = wp * group["profitability_score"] + wg * group["growth_score"] + wv * group["valuation_score"]
        valid = group[["profitability_score", "growth_score", "pb_value", "screening_score"]].notna().all(axis=1) & group["pb_value"].gt(0)
        group["profile_percentile"] = percentile_rank(group["screening_score"])
        for _, row in group.iterrows():
            ready = bool(valid.loc[row.name])
            rows.append(
                {
                    "security_id": row["security_id"],
                    "security_name": str(row.get("security_name") or ""),
                    "sector_profile": profile,
                    "profitability_score": float(row["profitability_score"]) if pd.notna(row["profitability_score"]) else None,
                    "growth_score": float(row["growth_score"]) if pd.notna(row["growth_score"]) else None,
                    "pb": float(row["pb_value"]) if pd.notna(row["pb_value"]) else None,
                    "valuation_score_within_profile": float(row["valuation_score"]) if pd.notna(row["valuation_score"]) else None,
                    "financial_screening_score": float(row["screening_score"]) if ready else None,
                    "profile_percentile": float(row["profile_percentile"]) if ready and pd.notna(row["profile_percentile"]) else None,
                    "score_status": "SCREENING_SCORE_READY_LIMITED_CONFIDENCE" if ready else "INSUFFICIENT_SCREENING_INPUTS",
                    "research_grade_profile_status": "BLOCKED_SPECIALIZED_FINANCIAL_METRICS_INCOMPLETE",
                    "cross_profile_ranking_allowed": False,
                    "candidate_promotion_authorized": False,
                    "trade_authority": "NONE",
                }
            )
        valid_count = int(valid.sum())
        total = int(len(group))
        profile_summary[profile] = {
            "issuer_count": total,
            "screening_score_ready_count": valid_count,
            "coverage": round(valid_count / total if total else 0.0, 8),
            "screening_status": "READY_FOR_PROFILE_INTERNAL_SCREENING" if valid_count / total >= 0.90 else "PARTIAL_SCREENING_INPUTS",
            "research_grade_status": "BLOCKED_SPECIALIZED_FINANCIAL_METRICS_INCOMPLETE",
        }
    manifest = {
        "state_id": "WP3R_FINANCIAL_SECTOR_SCREENING_SCORE_CURRENT",
        "status": "PASS_INDEPENDENT_FINANCIAL_PROFILE_SCREENING_V1" if all(item["coverage"] >= 0.90 for item in profile_summary.values()) else "PARTIAL_INDEPENDENT_FINANCIAL_PROFILE_SCREENING_V1",
        "profile_summaries": profile_summary,
        "row_count": len(rows),
        "scoring_scope": "PROFILE_INTERNAL_SCREENING_ONLY",
        "research_grade_underwriting_allowed": False,
        "cross_profile_ranking_allowed": False,
        "candidate_promotion_authorized": False,
        "orders": 0,
        "trade_authority": "NONE",
    }
    return rows, manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--config", default="automation/wp3_r/config.json")
    parser.add_argument("--as-of", default="2026-07-26")
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    cfg = read_json(root / args.config)
    as_of = date.fromisoformat(args.as_of)
    candidate = read_json(root / cfg["inputs"]["candidate_current"])
    market = pd.read_csv(root / cfg["inputs"]["a_share_current"], low_memory=False)
    family = pd.read_parquet(root / cfg["inputs"]["financial_family_scores"])
    profiles = pd.read_csv(root / cfg["inputs"]["financial_profile_reconciliation"], low_memory=False)
    industry = pd.read_csv(root / "investment_os_runtime/40_EVIDENCE_AND_LINEAGE/WP3_R/INDUSTRY_MASTER/SECURITY_INDUSTRY_MASTER_CURRENT.csv", low_memory=False)

    weekly = weekly_screen(candidate, market, as_of, int(cfg["freshness_policy"]["price_current_max_calendar_days"]))
    industry_product = industry_quality(market, industry, profiles)
    score_rows, score_manifest = financial_screening_scores(family, profiles, market)

    outputs = cfg["outputs"]
    write_json(root / outputs["weekly_price_screen"], weekly)
    write_json(root / outputs["industry_quality"], industry_product)
    score_dir = root / "investment_os_runtime/40_EVIDENCE_AND_LINEAGE/WP3_R/FINANCIAL_SECTOR_SCREENING"
    score_csv = score_dir / "FINANCIAL_SECTOR_SCREENING_SCORE_CURRENT.csv"
    score_json = score_dir / "FINANCIAL_SECTOR_SCREENING_SCORE_CURRENT.json"
    write_csv(score_csv, score_rows)
    score_manifest["csv_path"] = str(score_csv.relative_to(root))
    write_json(score_json, score_manifest)

    readiness = read_json(root / outputs["financial_profile_readiness"])
    readiness["screening_profile_v1"] = score_manifest
    readiness["status"] = "INDEPENDENT_FINANCIAL_SCREENING_PROFILE_ACTIVE_RESEARCH_GRADE_INPUTS_PENDING"
    for profile in readiness.get("financial_profiles", []):
        summary = score_manifest["profile_summaries"].get(profile["profile"], {})
        profile["screening_score_coverage"] = summary.get("coverage", 0.0)
        profile["composite_score_status"] = summary.get("screening_status", "PARTIAL_SCREENING_INPUTS")
        profile["research_grade_profile_status"] = "BLOCKED_SPECIALIZED_FINANCIAL_METRICS_INCOMPLETE"
    write_json(root / outputs["financial_profile_readiness"], readiness)

    operating = read_json(root / outputs["operating_current"])
    operating["weekly_price_screen_status"] = weekly["status"]
    operating["industry_classification_status"] = industry_product["status"]
    operating["financial_profile_status"] = readiness["status"]
    operating["financial_profile_screening_status"] = score_manifest["status"]
    operating["financial_research_grade_status"] = "BLOCKED_SPECIALIZED_METRICS_INCOMPLETE"
    operating["candidate_membership_mutations"] = 0
    operating["orders"] = 0
    operating["trade_authority"] = "NONE"
    write_json(root / outputs["operating_current"], operating)

    acceptance = read_json(root / outputs["acceptance"])
    acceptance["operating_product_controls"] = {
        "weekly_price_screen_coverage": weekly["covered_count"],
        "weekly_price_screen_status": weekly["status"],
        "industry_coverage": industry_product["industry_coverage"],
        "industry_status": industry_product["status"],
        "financial_screening_profile_status": score_manifest["status"],
        "financial_research_grade_status": "BLOCKED_SPECIALIZED_FINANCIAL_METRICS_INCOMPLETE",
        "cross_profile_ranking_allowed": False,
        "candidate_membership_mutations": 0,
        "orders": 0,
        "trade_authority": "NONE",
    }
    acceptance["status"] = "WP3R_OPERATING_SCREENING_PRODUCTS_READY_CADENCE_FINALIZATION_PENDING"
    for key in ("weekly_price_screen", "industry_quality", "financial_profile_readiness", "operating_current"):
        payload = read_json(root / outputs[key])
        acceptance.setdefault("outputs", {})[key] = {"path": outputs[key], "semantic_hash": digest(payload)}
    acceptance["outputs"]["financial_sector_screening"] = {"path": str(score_json.relative_to(root)), "semantic_hash": digest(score_manifest)}
    acceptance["wp5_unblocked"] = False
    write_json(root / outputs["acceptance"], acceptance)

    print(json.dumps({
        "weekly": weekly["status"],
        "weekly_coverage": weekly["covered_count"],
        "industry": industry_product["status"],
        "industry_coverage": industry_product["industry_coverage"],
        "financial_screening": score_manifest["status"],
        "profiles": score_manifest["profile_summaries"],
        "candidate_mutations": 0,
        "orders": 0,
        "trade_authority": "NONE",
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
