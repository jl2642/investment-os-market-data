#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

import run_fmdl5e_hk_factor_screening as engine

REPAIR_ROUND = "FMDL-5E-R1"

_ORIGINAL_ENRICH = engine.enrich
_ORIGINAL_QUALITY = engine.quality

INSURANCE_TOKENS = (
    "INSURANCE",
    "ASSURANCE",
    "AIA GROUP",
    "PRUDENTIAL",
    "PICC",
    "PING AN INSURANCE",
    "FWD GROUP",
    "CHINA LIFE",
    "ZA ONLINE",
    "SUNSHINE INS",
    "CHINA TAIPING",
    "NEW CHINA LIFE",
)
SECURITIES_TOKENS = (
    "SECURITIES",
    "CHINA INTERNATIONAL CAPITAL CORPORATION",
    " CICC ",
    "CSC FINANCIAL",
    "CHINA CINDA ASSET MANAGEMENT",
    "CITIC FINANCIAL ASSET MANAGEMENT",
)
BANK_TOKENS = (
    "BANK",
    "BANKING",
    "HSBC",
    "STANDARD CHARTERED",
    "BOC HONG KONG",
    "DAH SING FINANCIAL",
)
REIT_TOKENS = ("REAL ESTATE INVESTMENT TRUST", " REIT ")


def normalized_name_text(row: pd.Series | dict[str, Any]) -> str:
    security = str(row.get("official_security_name_en") or "").upper().strip()
    issuer = str(row.get("official_issuer_name_en") or "").upper().strip()
    return f" {security} | {issuer} "


def derive_screening_profile(row: pd.Series | dict[str, Any]) -> tuple[str, str]:
    if str(row.get("security_type") or "") != "COMMON_EQUITY":
        return "CONTROLLED_NON_FINANCIAL", "CONTROLLED_NON_EQUITY"
    if not engine.as_bool(row.get("financial_decision_grade")):
        return "CONTROLLED_NON_FINANCIAL", "NO_DECISION_GRADE_FINANCIAL_CURRENT"
    text = normalized_name_text(row)
    if any(token in text for token in INSURANCE_TOKENS):
        return "INSURANCE", "OFFICIAL_NAME_INSURANCE"
    if any(token in text for token in SECURITIES_TOKENS):
        return "SECURITIES_AND_BROKERAGE", "OFFICIAL_NAME_SECURITIES"
    if any(token in text for token in BANK_TOKENS):
        return "BANK", "OFFICIAL_NAME_BANK"
    if any(token in text for token in REIT_TOKENS):
        return "REIT", "OFFICIAL_NAME_REIT"
    return "GENERAL_NON_FINANCIAL", "DEFAULT_GENERAL_NON_FINANCIAL"


def enrich(
    frame: pd.DataFrame,
    dividends: pd.DataFrame,
    latest_fx: dict[str, float],
    dictionary: list[dict[str, Any]],
) -> pd.DataFrame:
    corrected = frame.copy()
    corrected["source_profile"] = corrected["profile"].fillna("CONTROLLED_NON_FINANCIAL")
    derived = corrected.apply(derive_screening_profile, axis=1)
    corrected["profile"] = [item[0] for item in derived]
    corrected["profile_basis"] = [item[1] for item in derived]
    corrected["profile_override_applied"] = corrected["source_profile"] != corrected["profile"]
    return _ORIGINAL_ENRICH(corrected, dividends, latest_fx, dictionary)


def build_longlist(
    frame: pd.DataFrame,
    detail: pd.DataFrame,
    contract: dict[str, Any],
) -> pd.DataFrame:
    funnel = contract["funnel"]
    target = int(funnel["longlist_count"])
    if detail.empty:
        raise RuntimeError("NO_FORMAL_SLEEVE_CANDIDATES")
    distinct = int(detail["security_id"].astype(str).nunique())
    if distinct < target:
        raise RuntimeError(f"INSUFFICIENT_FORMAL_SLEEVE_COVERAGE:{distinct}:{target}")

    eligible = frame[
        frame["investability_status"].isin({"ELIGIBLE_CORE", "ELIGIBLE_WATCH"})
    ].copy()
    rows: list[dict[str, Any]] = []
    for security_id, group in detail.groupby("security_id", sort=True):
        ordered = group.sort_values(
            ["sleeve_rank_percentile", "sleeve_score", "sleeve_id"],
            ascending=[False, False, True],
        )
        best = ordered.iloc[0]
        sleeves = ordered["sleeve_id"].astype(str).tolist()
        bonus = min(
            float(funnel["cross_sleeve_bonus_maximum"]),
            max(0, len(sleeves) - 1)
            * float(funnel["cross_sleeve_bonus_per_extra_sleeve"]),
        )
        rows.append(
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
                "screening_basis": "FORMAL_SLEEVE_ONLY",
            }
        )

    ranked = pd.DataFrame(rows).merge(
        eligible, on="security_id", how="left", validate="one_to_one"
    )
    if ranked["investability_status"].isna().any():
        raise RuntimeError("FORMAL_SLEEVE_SECURITY_NOT_INVESTABLE")
    ranked = (
        ranked.sort_values(
            [
                "aggregate_score",
                "normalized_primary_score",
                "best_sleeve_score",
                "avg_turnover_hkd_20d",
                "security_id",
            ],
            ascending=[False, False, False, False, True],
        )
        .drop_duplicates("security_id")
        .head(target)
        .reset_index(drop=True)
    )
    if len(ranked) != target:
        raise RuntimeError(f"FORMAL_SLEEVE_LONGLIST_COUNT:{len(ranked)}:{target}")

    ranked["overall_rank"] = range(1, len(ranked) + 1)
    a_end = int(funnel["priority_bucket_counts"]["A_IMMEDIATE_RESEARCH"])
    b_end = a_end + int(funnel["priority_bucket_counts"]["B_WATCH_OR_TRIGGER"])
    ranked["research_priority"] = ranked["overall_rank"].map(
        lambda rank: (
            "A_IMMEDIATE_RESEARCH"
            if rank <= a_end
            else "B_WATCH_OR_TRIGGER"
            if rank <= b_end
            else "C_SCREEN_FLAG_ONLY"
        )
    )
    ranked["next_workflow"] = funnel["next_workflow"]
    ranked["authority"] = contract["authority"]
    ranked["trade_authority"] = "NONE"
    ordered_columns = [
        "as_of_date",
        "overall_rank",
        "research_priority",
        "security_id",
        "stock_code_5d",
        "official_security_name_en",
        "official_issuer_name_en",
        "primary_sleeve",
        "sleeves",
        "sleeve_count",
        "screening_basis",
        "aggregate_score",
        "normalized_primary_score",
        "best_sleeve_score",
        "cross_sleeve_bonus",
        "investability_status",
        "factor_record_quality",
        "confidence_grade",
        "profile",
        "source_profile",
        "profile_basis",
        "profile_override_applied",
        "latest_close",
        "latest_quote_currency",
        "avg_turnover_hkd_20d",
        "return_20d",
        "return_60d",
        "return_120d",
        "return_250d",
        "volatility_60d",
        "max_drawdown_120d",
        "roe",
        "roa",
        "operating_margin",
        "revenue_yoy",
        "net_income_yoy",
        "earnings_yield",
        "pe_ratio",
        "dividend_yield_365d",
        "corporate_action_count_365d",
        "a_share_class_exists",
        "h_share_flag",
        "wvr_flag",
        "dual_counter_flag",
        "secondary_listing_flag",
        "biotech_chapter18a_flag",
        "next_workflow",
        "authority",
        "trade_authority",
    ]
    return ranked[[column for column in ordered_columns if column in ranked.columns]]


def quality(
    frame: pd.DataFrame,
    detail: pd.DataFrame,
    longlist: pd.DataFrame,
    cases: pd.DataFrame,
    contract: dict[str, Any],
    data: dict[str, Any],
    as_of: pd.Timestamp,
) -> dict[str, Any]:
    payload = _ORIGINAL_QUALITY(frame, detail, longlist, cases, contract, data, as_of)
    acceptance = contract["acceptance"]
    formal_sleeves = set(contract["sleeves"])
    primary_counts = (
        longlist["primary_sleeve"].value_counts().astype(int).to_dict()
        if not longlist.empty
        else {}
    )
    fallback_count = int(
        longlist["primary_sleeve"].astype(str).str.contains("FALLBACK").sum()
        if not longlist.empty
        else 0
    )
    distinct_sleeve_securities = int(
        detail["security_id"].astype(str).nunique() if not detail.empty else 0
    )
    profile_expected = frame.apply(derive_screening_profile, axis=1).map(lambda item: item[0])
    profile_mismatch = int((profile_expected.astype(str) != frame["profile"].astype(str)).sum())
    anchors = contract["profile_policy"]["anchor_expectations"]
    by_code = frame.set_index(frame["stock_code_5d"].astype(str).str.zfill(5))
    anchor_mismatch = 0
    for code, expected in anchors.items():
        if code not in by_code.index or str(by_code.loc[code, "profile"]) != expected:
            anchor_mismatch += 1
    minimum_primary = min((int(primary_counts.get(name, 0)) for name in formal_sleeves), default=0)
    maximum_primary_share = (
        max(primary_counts.values()) / len(longlist) if primary_counts and len(longlist) else 0.0
    )

    metrics = payload["metrics"]
    metrics.update(
        {
            "repair_round": REPAIR_ROUND,
            "profile_override_count": int(frame["profile_override_applied"].map(engine.as_bool).sum()),
            "profile_semantic_mismatch_count": profile_mismatch,
            "profile_anchor_mismatch_count": anchor_mismatch,
            "profile_counts": frame["profile"].value_counts().astype(int).to_dict(),
            "distinct_formal_sleeve_security_count": distinct_sleeve_securities,
            "formal_sleeve_longlist_count": int(
                longlist["primary_sleeve"].isin(formal_sleeves).sum()
                if not longlist.empty
                else 0
            ),
            "fallback_longlist_count": fallback_count,
            "minimum_primary_sleeve_count": minimum_primary,
            "maximum_primary_sleeve_share": maximum_primary_share,
        }
    )

    failures = payload["hard_failures"]
    checks = (
        (
            profile_mismatch
            > int(acceptance["maximum_profile_semantic_mismatch_count"]),
            "PROFILE_SEMANTIC_MISMATCH",
        ),
        (
            anchor_mismatch > int(acceptance["maximum_profile_anchor_mismatch_count"]),
            "PROFILE_ANCHOR_MISMATCH",
        ),
        (
            distinct_sleeve_securities
            < int(acceptance["minimum_distinct_formal_sleeve_security_count"]),
            "FORMAL_SLEEVE_COVERAGE",
        ),
        (
            fallback_count > int(acceptance["maximum_fallback_longlist_count"]),
            "FALLBACK_LONGLIST_PROHIBITED",
        ),
        (
            set(primary_counts) != formal_sleeves,
            "FORMAL_PRIMARY_SLEEVE_SET",
        ),
        (
            minimum_primary < int(acceptance["minimum_primary_sleeve_count_each"]),
            "PRIMARY_SLEEVE_MINIMUM_COUNT",
        ),
        (
            maximum_primary_share
            > float(acceptance["maximum_single_primary_sleeve_share"]),
            "PRIMARY_SLEEVE_CONCENTRATION",
        ),
    )
    for failed, code in checks:
        if failed and code not in failures:
            failures.append(code)
    payload["status"] = "PASS" if not failures else "FAIL"
    payload["repair_round"] = REPAIR_ROUND
    return payload


def install_hardening() -> None:
    engine.enrich = enrich
    engine.build_longlist = build_longlist
    engine.quality = quality


def finalize_candidate(output: Path) -> dict[str, Any]:
    quality_path = output / "FMDL5E_QUALITY_REPORT.json"
    dictionary_path = output / "FMDL5E_FACTOR_DICTIONARY.json"
    registry_path = output / "FMDL5E_SOURCE_REGISTRY.json"
    decision_path = output / "FMDL5E_DECISION.json"
    manifest_path = output / "FMDL5E_MANIFEST.json"

    quality_payload = engine.read_json(quality_path)
    factor_dictionary = engine.read_json(dictionary_path)
    source_registry = engine.read_json(registry_path)
    decision = engine.read_json(decision_path)
    factor_dictionary["repair_round"] = REPAIR_ROUND
    source_registry["repair_round"] = REPAIR_ROUND
    decision["repair_round"] = REPAIR_ROUND
    quality_payload["repair_round"] = REPAIR_ROUND
    quality_path.write_text(
        json.dumps(quality_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    dictionary_path.write_text(
        json.dumps(factor_dictionary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    registry_path.write_text(
        json.dumps(source_registry, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    base_files = [
        path
        for path in output.iterdir()
        if path.is_file() and path.name not in {"FMDL5E_DECISION.json", "FMDL5E_MANIFEST.json"}
    ]
    base_hashes = {
        path.name: {"sha256": engine.sha256_file(path), "size_bytes": path.stat().st_size}
        for path in base_files
    }
    canonical = engine.stable_hash(base_hashes)
    as_of = pd.Timestamp(decision["as_of_date"])
    release_id = f"FMDL5E_{as_of.strftime('%Y%m%d')}_{canonical[:12]}"
    decision["canonical_sha256"] = canonical
    decision["release_id"] = release_id
    decision_path.write_text(
        json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest_files = [path for path in output.iterdir() if path.is_file() and path.name != "FMDL5E_MANIFEST.json"]
    manifest = {
        "program_id": engine.PROGRAM_ID,
        "repair_round": REPAIR_ROUND,
        "release_id": release_id,
        "release_sequence": decision["release_sequence"],
        "source_release_ids": decision["source_release_ids"],
        "as_of_date": decision["as_of_date"],
        "canonical_sha256": canonical,
        "files": {
            path.name: {
                "sha256": engine.sha256_file(path),
                "size_bytes": path.stat().st_size,
            }
            for path in manifest_files
        },
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return decision


def run(root: Path, output: Path) -> dict[str, Any]:
    install_hardening()
    engine.run(root, output)
    return finalize_candidate(output)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--output", default="outputs/fmdl5e/candidate")
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    decision = run(root, root / args.output)
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0 if decision["status"] == engine.ACCEPTED_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
