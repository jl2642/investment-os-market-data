#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from fmdl5d_core import (
    assign_filing_periods,
    build_unmapped_catalog,
    count_duplicate_keys,
    file_sha256,
    latest_filing_map,
    load_field_registry,
    normalize_raw_facts,
    stable_hash,
)
from run_fmdl5d_disclosure_financial_store import balance_sheet_tie_outs, build_current, now_utc, write_json


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv_optional(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path, dtype=str)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--contract", default="config/fmdl5d_hkex_disclosure_financial_contract.json")
    parser.add_argument("--registry", default="config/fmdl5d_hk_financial_field_registry.json")
    parser.add_argument("--expected-shards", type=int, default=12)
    args = parser.parse_args()

    source = Path(args.input)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    contract = read_json(Path(args.contract))
    _, registry_payload = load_field_registry(Path(args.registry))
    source_decision = read_json(Path(contract["source_release"]["decision_path"]))
    if source_decision.get("status") != contract["source_release"]["required_status"]:
        raise ValueError(f"SOURCE_RELEASE_NOT_ACCEPTED:{source_decision.get('status')}")

    overlay = pd.read_csv(contract["source_release"]["semantic_overlay_path"], dtype={"stock_code_5d": str})
    overlay["stock_code_5d"] = overlay["stock_code_5d"].astype(str).str.zfill(5)
    prices = pd.read_parquet(contract["source_release"]["price_store_path"], columns=["observation_date"])
    trading_days = sorted(pd.to_datetime(prices["observation_date"], errors="coerce").dropna().dt.date.unique())
    market_max_date = max(trading_days)
    securities = overlay.to_dict(orient="records")
    equity_securities = [row for row in securities if str(row.get("security_type")) == "COMMON_EQUITY"]
    fund_securities = [row for row in securities if str(row.get("security_type")) != "COMMON_EQUITY"]

    status_paths = sorted(source.rglob("FMDL5D_R1_SHARD_*_STATUS.json"))
    result_paths = sorted(source.rglob("FMDL5D_R1_SHARD_*_RESULTS.json"))
    raw_paths = sorted(source.rglob("FMDL5D_R1_SHARD_*_RAW.parquet"))
    unmapped_paths = sorted(source.rglob("FMDL5D_R1_SHARD_*_UNMAPPED.csv"))
    disclosure_path = next(iter(source.rglob("FMDL5D_R1_DISCLOSURES.json")), None)
    disclosure_status_path = next(iter(source.rglob("FMDL5D_R1_DISCLOSURE_STATUS.json")), None)

    runtime_failures: list[str] = []
    if len(status_paths) != args.expected_shards:
        runtime_failures.append(f"SHARD_STATUS_COUNT_MISMATCH:{len(status_paths)}:{args.expected_shards}")
    if len(result_paths) != args.expected_shards:
        runtime_failures.append(f"SHARD_RESULT_COUNT_MISMATCH:{len(result_paths)}:{args.expected_shards}")
    if len(raw_paths) != args.expected_shards:
        runtime_failures.append(f"SHARD_RAW_COUNT_MISMATCH:{len(raw_paths)}:{args.expected_shards}")
    if disclosure_path is None or disclosure_status_path is None:
        runtime_failures.append("DISCLOSURE_ARTIFACT_MISSING")

    shard_statuses = [read_json(path) for path in status_paths]
    results = [row for path in result_paths for row in read_json(path)]
    raw_frames = [pd.read_parquet(path) for path in raw_paths]
    raw = pd.concat(raw_frames, ignore_index=True) if raw_frames else pd.DataFrame()
    if "raw_fact_id" in raw.columns:
        raw = raw[raw["raw_fact_id"].notna()].copy()
    unmapped_frames: list[pd.DataFrame] = []
    for path in unmapped_paths:
        frame = read_csv_optional(path)
        if not frame.empty:
            unmapped_frames.append(frame)
    unmapped_rows = pd.concat(unmapped_frames, ignore_index=True).to_dict(orient="records") if unmapped_frames else []
    filings = read_json(disclosure_path) if disclosure_path else []
    disclosure_status = read_json(disclosure_status_path) if disclosure_status_path else {"warnings": []}

    expected_ids = {row["security_id"] for row in equity_securities}
    actual_ids = [row["security_id"] for row in results]
    actual_id_set = set(actual_ids)
    counts: dict[str, int] = {}
    for security_id in actual_ids:
        counts[security_id] = counts.get(security_id, 0) + 1
    duplicate_result_security_ids = sorted(security_id for security_id, count in counts.items() if count > 1)
    missing_security_ids = sorted(expected_ids - actual_id_set)
    unexpected_security_ids = sorted(actual_id_set - expected_ids)
    if duplicate_result_security_ids:
        runtime_failures.append(f"DUPLICATE_RESULT_SECURITY_IDS:{len(duplicate_result_security_ids)}")
    if missing_security_ids:
        runtime_failures.append(f"MISSING_RESULT_SECURITY_IDS:{len(missing_security_ids)}")
    if unexpected_security_ids:
        runtime_failures.append(f"UNEXPECTED_RESULT_SECURITY_IDS:{len(unexpected_security_ids)}")
    for status in shard_statuses:
        if status.get("missing_security_ids") or status.get("unexpected_security_ids"):
            runtime_failures.append(f"SHARD_BOUNDARY_FAILURE:{status.get('shard_index')}")

    periods_by_code = {result["stock_code_5d"]: result.get("periods", []) for result in results}
    fiscal_year_by_code = {result["stock_code_5d"]: result.get("fiscal_year_end") for result in results}
    assigned_filings = assign_filing_periods(filings, periods_by_code, fiscal_year_by_code, trading_days)
    latest_filings = latest_filing_map(assigned_filings)
    raw_rows = raw.to_dict(orient="records") if not raw.empty else []
    normalized_rows = normalize_raw_facts(raw_rows, latest_filings)
    normalized = pd.DataFrame(normalized_rows)
    disclosure_frame = pd.DataFrame(assigned_filings)
    unmapped_catalog = pd.DataFrame(build_unmapped_catalog(unmapped_rows))
    current = build_current(normalized) if not normalized.empty else pd.DataFrame()

    if not raw.empty:
        raw.to_parquet(output / "FMDL5D_MAPPED_RAW_FACTS.parquet", index=False)
    else:
        pd.DataFrame(columns=["raw_fact_id"]).to_parquet(output / "FMDL5D_MAPPED_RAW_FACTS.parquet", index=False)
    if not normalized.empty:
        normalized.to_parquet(output / "FMDL5D_NORMALIZED_FINANCIAL_FACTS.parquet", index=False)
    else:
        pd.DataFrame(columns=["normalized_fact_id"]).to_parquet(output / "FMDL5D_NORMALIZED_FINANCIAL_FACTS.parquet", index=False)
    disclosure_frame.to_csv(output / "FMDL5D_HKEX_FINANCIAL_DISCLOSURES.csv", index=False, encoding="utf-8-sig")
    current.to_csv(output / "FMDL5D_ISSUER_FINANCIAL_CURRENT.csv", index=False, encoding="utf-8-sig")
    unmapped_catalog.to_csv(output / "FMDL5D_UNMAPPED_FIELD_CATALOG.csv", index=False, encoding="utf-8-sig")

    structured_success = {
        result["security_id"]
        for result in results
        if result.get("successful_statement_count", 0) >= 2 and result["security_id"] in expected_ids
    }
    official_codes = {row["stock_code_5d"] for row in assigned_filings if row.get("report_period_end")}
    decision_grade_securities = set(normalized.loc[normalized["decision_grade_eligible"], "security_id"]) if not normalized.empty else set()
    duplicate_fact_keys = count_duplicate_keys(normalized, ["security_id", "statement", "period_end", "field_id"]) if not normalized.empty else 0
    invalid_numeric = int((~pd.to_numeric(normalized["normalized_value"], errors="coerce").notna()).sum()) if not normalized.empty else 0
    future_available = 0
    if not normalized.empty:
        available_dates = pd.to_datetime(normalized["available_from"], errors="coerce", utc=True)
        future_available = int((available_dates.dt.date > market_max_date).fillna(False).sum())
    missing_lineage = 0
    if not normalized.empty:
        eligible = normalized[normalized["decision_grade_eligible"]]
        missing_lineage = int((eligible["official_filing_id"].isna() | eligible["official_filing_url"].isna()).sum())
    tie_out_checked, tie_out_failed = balance_sheet_tie_outs(normalized)

    failures: list[dict[str, Any]] = []
    for result in sorted(results, key=lambda item: item["stock_code_5d"]):
        if result.get("successful_statement_count", 0) < 2:
            failures.append(
                {
                    "security_id": result["security_id"],
                    "stock_code_5d": result["stock_code_5d"],
                    "failure_type": "STRUCTURED_FINANCIAL_DATA_INSUFFICIENT",
                    "details": json.dumps(result.get("statement_status", {}), ensure_ascii=False, sort_keys=True),
                }
            )
    for security in fund_securities:
        failures.append(
            {
                "security_id": security["security_id"],
                "stock_code_5d": security["stock_code_5d"],
                "failure_type": "NOT_APPLICABLE_FUND_CONTROLLED_EXCLUSION",
                "details": str(security.get("security_type", "")),
            }
        )
    pd.DataFrame(failures).to_csv(output / "FMDL5D_FAILURES.csv", index=False, encoding="utf-8-sig")

    equity_count = len(equity_securities)
    metrics = {
        "source_security_count": len(securities),
        "equity_security_count": equity_count,
        "fund_controlled_exclusion_count": len(fund_securities),
        "structured_statement_security_count": len(structured_success),
        "structured_statement_security_ratio": round(len(structured_success) / equity_count, 6) if equity_count else 0.0,
        "official_financial_disclosure_count": len(assigned_filings),
        "official_financial_disclosure_security_count": len(official_codes),
        "official_financial_disclosure_security_ratio": round(len(official_codes) / equity_count, 6) if equity_count else 0.0,
        "matched_official_disclosure_count": sum(bool(row.get("report_period_end")) for row in assigned_filings),
        "unmatched_official_disclosure_count": sum(not bool(row.get("report_period_end")) for row in assigned_filings),
        "mapped_raw_fact_count": len(raw),
        "normalized_fact_count": len(normalized),
        "decision_grade_fact_count": int(normalized["decision_grade_eligible"].sum()) if not normalized.empty else 0,
        "decision_grade_security_count": len(decision_grade_securities),
        "decision_grade_security_ratio": round(len(decision_grade_securities) / equity_count, 6) if equity_count else 0.0,
        "unmapped_field_catalog_count": len(unmapped_catalog),
        "duplicate_fact_key_count": duplicate_fact_keys,
        "invalid_numeric_row_count": invalid_numeric,
        "future_available_row_count": future_available,
        "decision_grade_missing_lineage_count": missing_lineage,
        "balance_sheet_tie_out_checked_count": tie_out_checked,
        "balance_sheet_tie_out_failed_count": tie_out_failed,
        "structured_failure_security_count": equity_count - len(structured_success),
        "hkex_chunk_warning_count": len(disclosure_status.get("warnings", [])),
        "market_max_date": market_max_date.isoformat(),
        "r1_expected_shard_count": args.expected_shards,
        "r1_completed_shard_count": len(shard_statuses),
        "r1_completed_security_count": len(actual_id_set),
    }

    acceptance = contract["acceptance"]
    hard_failures = list(runtime_failures)
    if metrics["source_security_count"] != acceptance["expected_security_count"]:
        hard_failures.append("SOURCE_SECURITY_COUNT_MISMATCH")
    if metrics["equity_security_count"] < acceptance["minimum_equity_count"]:
        hard_failures.append("EQUITY_SECURITY_COUNT_BELOW_MINIMUM")
    if metrics["structured_statement_security_ratio"] < acceptance["minimum_structured_statement_security_ratio"]:
        hard_failures.append("STRUCTURED_STATEMENT_COVERAGE_BELOW_MINIMUM")
    if metrics["official_financial_disclosure_security_ratio"] < acceptance["minimum_official_financial_disclosure_security_ratio"]:
        hard_failures.append("OFFICIAL_DISCLOSURE_COVERAGE_BELOW_MINIMUM")
    if metrics["decision_grade_security_ratio"] < acceptance["minimum_decision_grade_security_ratio"]:
        hard_failures.append("DECISION_GRADE_SECURITY_COVERAGE_BELOW_MINIMUM")
    if metrics["normalized_fact_count"] < acceptance["minimum_normalized_fact_count"]:
        hard_failures.append("NORMALIZED_FACT_COUNT_BELOW_MINIMUM")
    if metrics["duplicate_fact_key_count"] > acceptance["maximum_duplicate_fact_keys"]:
        hard_failures.append("DUPLICATE_NORMALIZED_FACT_KEYS")
    if metrics["future_available_row_count"] > acceptance["maximum_future_available_rows"]:
        hard_failures.append("FUTURE_INFORMATION_LEAKAGE")
    if metrics["invalid_numeric_row_count"] > acceptance["maximum_invalid_numeric_rows"]:
        hard_failures.append("INVALID_NUMERIC_VALUES")
    if metrics["decision_grade_missing_lineage_count"] > acceptance["maximum_decision_grade_missing_lineage"]:
        hard_failures.append("DECISION_GRADE_LINEAGE_MISSING")
    hard_failures = sorted(set(hard_failures))

    runtime_report = {
        "program_id": "FMDL-5D-R1",
        "generated_at_utc": now_utc(),
        "expected_shard_count": args.expected_shards,
        "completed_shard_count": len(shard_statuses),
        "shard_statuses": shard_statuses,
        "missing_security_ids": missing_security_ids,
        "unexpected_security_ids": unexpected_security_ids,
        "duplicate_result_security_ids": duplicate_result_security_ids,
        "disclosure_status": disclosure_status,
        "runtime_failures": runtime_failures,
        "trade_authority": "NONE",
    }
    write_json(output / "FMDL5D_R1_RUNTIME_REPORT.json", runtime_report)

    quality = {
        **metrics,
        "hard_failures": hard_failures,
        "controlled_limitations": [
            "HKEXnews supplies official disclosure identity and timing; structured statement values remain explicitly vendor-tier evidence.",
            "Exact normalized alias mapping leaves unmapped fields null and auditable rather than forcing semantic matches.",
            "Funds and ETFs are controlled not-applicable exclusions from issuer financial normalization.",
            "A filing released on a trading date becomes available only at the next accepted Hong Kong trading-session open.",
            "FMDL-5D-R1 executes disclosure and structured financial collection as independently restartable artifacts before deterministic aggregation.",
        ],
        "hkex_warnings": disclosure_status.get("warnings", []),
    }
    write_json(output / "FMDL5D_QUALITY_REPORT.json", quality)

    source_registry = {
        "program_id": "FMDL-5D",
        "generated_at": now_utc(),
        "source_release_id": source_decision["release_id"],
        "field_registry_version": registry_payload["registry_version"],
        "source_routes": contract["source_routes"],
        "hkex_financial_disclosure_scan": {
            "start_date": disclosure_status.get("start_date"),
            "end_date": disclosure_status.get("end_date"),
            "record_count": len(assigned_filings),
            "warnings": disclosure_status.get("warnings", []),
        },
        "structured_financial_security_count": len(structured_success),
        "source_hashes_by_security": {
            result["stock_code_5d"]: result.get("source_hashes", {}) for result in results if result.get("source_hashes")
        },
        "runtime_orchestration": "FMDL-5D-R1_SHARDED_CHECKPOINTED_AGGREGATION",
        "trade_authority": "NONE",
    }
    write_json(output / "FMDL5D_SOURCE_REGISTRY.json", source_registry)

    primary_files = [
        "FMDL5D_HKEX_FINANCIAL_DISCLOSURES.csv",
        "FMDL5D_MAPPED_RAW_FACTS.parquet",
        "FMDL5D_NORMALIZED_FINANCIAL_FACTS.parquet",
        "FMDL5D_ISSUER_FINANCIAL_CURRENT.csv",
        "FMDL5D_UNMAPPED_FIELD_CATALOG.csv",
        "FMDL5D_FAILURES.csv",
        "FMDL5D_QUALITY_REPORT.json",
        "FMDL5D_SOURCE_REGISTRY.json",
        "FMDL5D_R1_RUNTIME_REPORT.json",
    ]
    data_hashes = {name: file_sha256(output / name) for name in primary_files}
    canonical_sha256 = stable_hash(
        {
            "program_id": "FMDL-5D",
            "source_release_id": source_decision["release_id"],
            "metrics": metrics,
            "data_hashes": data_hashes,
            "contract_version": contract["contract_version"],
            "registry_version": registry_payload["registry_version"],
            "runtime_orchestration": "R1_SHARDED_CHECKPOINTED",
        }
    )
    release_id = f"FMDL5D_{market_max_date.strftime('%Y%m%d')}_{canonical_sha256[:12]}"
    status = "FMDL5D_HKEX_DISCLOSURE_AND_FINANCIAL_NORMALIZATION_ACCEPTED_WITH_CONTROLLED_QUARANTINE" if not hard_failures else "FMDL5D_REJECTED"
    decision = {
        "program_id": "FMDL-5D",
        "repair_round": "FMDL-5D-R1",
        "status": status,
        "authority": contract["authority"],
        "trade_authority": "NONE",
        "release_id": release_id,
        "release_sequence": 14,
        "source_release_id": source_decision["release_id"],
        "canonical_sha256": canonical_sha256,
        "hard_failures": hard_failures,
        "metrics": metrics,
        "limitations": quality["controlled_limitations"],
        "candidate_pool_mutation_count": 0,
        "simulation_mutation_count": 0,
        "real_account_mutation_count": 0,
        "order_generation_count": 0,
        "next_gate": contract["publication"]["next_gate"],
    }
    write_json(output / "FMDL5D_DECISION.json", decision)

    manifest_files = primary_files + ["FMDL5D_DECISION.json"]
    manifest = {
        "program_id": "FMDL-5D",
        "repair_round": "FMDL-5D-R1",
        "release_id": release_id,
        "release_sequence": 14,
        "source_release_id": source_decision["release_id"],
        "canonical_sha256": canonical_sha256,
        "generated_at_utc": now_utc(),
        "files": {
            name: {"sha256": file_sha256(output / name), "size_bytes": (output / name).stat().st_size}
            for name in manifest_files
        },
    }
    write_json(output / "FMDL5D_MANIFEST.json", manifest)
    print(json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not hard_failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
