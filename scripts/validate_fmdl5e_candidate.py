#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd
from jsonschema import Draft202012Validator, FormatChecker

ACCEPTED_STATUS = "FMDL5E_HONG_KONG_FACTOR_AND_SCREENING_ADAPTER_ACCEPTED"
REPAIR_ROUND = "FMDL-5E-R1"
FORMAL_SLEEVES = {
    "QUALITY_COMPOUNDER",
    "HIGH_DIVIDEND_VALUE",
    "TREND_LIQUIDITY",
    "DEFENSIVE_STABILITY",
    "RECOVERY_WATCH",
}
PROFILE_ANCHORS = {
    "00005": "BANK",
    "00038": "GENERAL_NON_FINANCIAL",
    "00300": "GENERAL_NON_FINANCIAL",
    "00966": "INSURANCE",
    "02318": "INSURANCE",
    "03908": "SECURITIES_AND_BROKERAGE",
    "06030": "SECURITIES_AND_BROKERAGE",
    "06066": "SECURITIES_AND_BROKERAGE",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--candidate", default="outputs/fmdl5e/candidate")
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    candidate = root / args.candidate
    decision = json.loads((candidate / "FMDL5E_DECISION.json").read_text(encoding="utf-8"))
    quality = json.loads((candidate / "FMDL5E_QUALITY_REPORT.json").read_text(encoding="utf-8"))
    manifest = json.loads((candidate / "FMDL5E_MANIFEST.json").read_text(encoding="utf-8"))
    longlist = pd.read_csv(candidate / "FMDL5E_RESEARCH_LONGLIST.csv", dtype={"stock_code_5d": str}, encoding="utf-8-sig")
    screening = pd.read_csv(candidate / "FMDL5E_SCREENING_UNIVERSE.csv", dtype={"stock_code_5d": str}, encoding="utf-8-sig")
    factor_table = pd.read_parquet(candidate / "FMDL5E_FACTOR_TABLE.parquet")
    detail = pd.read_parquet(candidate / "FMDL5E_FACTOR_DETAIL.parquet")
    sleeve_detail = pd.read_csv(candidate / "FMDL5E_SLEEVE_DETAIL.csv", dtype={"stock_code_5d": str}, encoding="utf-8-sig")
    schema = json.loads((root / "schemas/fmdl5e_longlist_v1.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for row in json.loads(longlist.to_json(orient="records")):
        validator.validate(row)

    assert decision["status"] == ACCEPTED_STATUS
    assert decision["repair_round"] == REPAIR_ROUND
    assert quality["repair_round"] == REPAIR_ROUND
    assert manifest["repair_round"] == REPAIR_ROUND
    assert quality["status"] == "PASS"
    assert not decision["hard_failures"]
    assert not quality["hard_failures"]
    assert decision["release_id"] == manifest["release_id"]
    assert decision["canonical_sha256"] == manifest["canonical_sha256"]
    assert len(factor_table) == quality["metrics"]["source_security_count"] == 644
    assert factor_table["security_id"].nunique() == 644
    assert len(detail) == quality["metrics"]["factor_detail_row_count"]
    assert len(longlist) == 100
    assert longlist["security_id"].nunique() == 100
    assert longlist["overall_rank"].tolist() == list(range(1, 101))
    assert longlist["research_priority"].value_counts().to_dict() == {
        "B_WATCH_OR_TRIGGER": 40,
        "C_SCREEN_FLAG_ONLY": 40,
        "A_IMMEDIATE_RESEARCH": 20,
    }
    assert set(longlist["investability_status"]).issubset({"ELIGIBLE_CORE", "ELIGIBLE_WATCH"})
    assert set(longlist["primary_sleeve"]) == FORMAL_SLEEVES
    assert set(longlist["screening_basis"]) == {"FORMAL_SLEEVE_ONLY"}
    assert not longlist["primary_sleeve"].str.contains("FALLBACK").any()
    assert set(longlist["trade_authority"]) == {"NONE"}

    metrics = quality["metrics"]
    assert metrics["future_price_row_count"] == 0
    assert metrics["future_action_row_count"] == 0
    assert metrics["future_financial_row_count"] == 0
    assert metrics["invalid_numeric_factor_count"] == 0
    assert metrics["profile_semantic_mismatch_count"] == 0
    assert metrics["profile_anchor_mismatch_count"] == 0
    assert metrics["distinct_formal_sleeve_security_count"] >= 150
    assert metrics["formal_sleeve_longlist_count"] == 100
    assert metrics["fallback_longlist_count"] == 0
    assert metrics["minimum_primary_sleeve_count"] >= 10
    assert metrics["maximum_primary_sleeve_share"] <= 0.35
    assert sleeve_detail["security_id"].nunique() == metrics["distinct_formal_sleeve_security_count"]

    screening_by_code = screening.assign(stock_code_5d=screening["stock_code_5d"].astype(str).str.zfill(5)).set_index("stock_code_5d")
    for code, expected_profile in PROFILE_ANCHORS.items():
        assert code in screening_by_code.index
        assert screening_by_code.loc[code, "profile"] == expected_profile
    assert "source_profile" in screening.columns
    assert "profile_basis" in screening.columns
    assert "profile_override_applied" in screening.columns

    for name, meta in manifest["files"].items():
        path = candidate / name
        assert path.is_file()
        assert path.stat().st_size == meta["size_bytes"]
        assert sha256_file(path) == meta["sha256"]

    assert decision["candidate_pool_mutation_count"] == 0
    assert decision["simulation_mutation_count"] == 0
    assert decision["real_account_mutation_count"] == 0
    assert decision["order_generation_count"] == 0
    assert decision["trade_authority"] == "NONE"
    print(json.dumps({"status": "PASS", "release_id": decision["release_id"], "repair_round": REPAIR_ROUND, "longlist_count": len(longlist)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
