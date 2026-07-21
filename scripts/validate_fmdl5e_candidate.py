#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from jsonschema import Draft202012Validator, FormatChecker

ACCEPTED_STATUS = "FMDL5E_HONG_KONG_FACTOR_AND_SCREENING_ADAPTER_ACCEPTED"


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
    factor_table = pd.read_parquet(candidate / "FMDL5E_FACTOR_TABLE.parquet")
    detail = pd.read_parquet(candidate / "FMDL5E_FACTOR_DETAIL.parquet")
    schema = json.loads((root / "schemas/fmdl5e_longlist_v1.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for row in json.loads(longlist.to_json(orient="records")):
        validator.validate(row)

    assert decision["status"] == ACCEPTED_STATUS
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
    assert set(longlist["trade_authority"]) == {"NONE"}
    assert quality["metrics"]["future_price_row_count"] == 0
    assert quality["metrics"]["future_action_row_count"] == 0
    assert quality["metrics"]["future_financial_row_count"] == 0
    assert quality["metrics"]["invalid_numeric_factor_count"] == 0
    assert decision["candidate_pool_mutation_count"] == 0
    assert decision["simulation_mutation_count"] == 0
    assert decision["real_account_mutation_count"] == 0
    assert decision["order_generation_count"] == 0
    assert decision["trade_authority"] == "NONE"
    print(json.dumps({"status": "PASS", "release_id": decision["release_id"], "longlist_count": len(longlist)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
