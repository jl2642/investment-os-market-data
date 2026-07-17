from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import jsonschema
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config/fmdl3a_benchmark.json"
DEFAULT_SCHEMA = ROOT / "schemas/fmdl3a_benchmark.schema.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def add_check(checks: list[dict[str, Any]], failures: list[str], check_id: str, passed: bool, detail: Any) -> None:
    checks.append({"check_id": check_id, "status": "PASS" if passed else "FAIL", "detail": detail})
    if not passed:
        failures.append(check_id)


def decision_for(decision: dict[str, Any], source_id: str) -> dict[str, Any]:
    return next((item for item in decision.get("source_decisions", []) if item.get("source_id") == source_id), {})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    args = parser.parse_args()
    config = load_json(args.config)
    schema = load_json(args.schema)
    root = ROOT / config["publication"]["candidate_root"]
    validation_path = root / "FMDL3A_VALIDATION.json"
    checks: list[dict[str, Any]] = []
    failures: list[str] = []

    try:
        jsonschema.validate(config, schema, format_checker=jsonschema.FormatChecker())
        add_check(checks, failures, "CONFIG_SCHEMA", True, "config conforms to schema")
    except Exception as exc:
        add_check(checks, failures, "CONFIG_SCHEMA", False, str(exc))

    required = [
        "FMDL3A_BENCHMARK_ROWS.csv",
        "FMDL3A_SOURCE_SUMMARY.csv",
        "FMDL3A_COVERAGE_MAP.csv",
        "FMDL3A_POINT_IN_TIME_EVIDENCE.csv",
        "FMDL3A_SUPPORT_QUARANTINE_MAP.csv",
        "FMDL3A_CAPITALIZATION_EVIDENCE.csv",
        "FMDL3_SOURCE_INDEX.csv",
        "FMDL3A_SOURCE_DECISION.json",
        "FMDL3A_MANIFEST.json",
    ]
    missing = [name for name in required if not (root / name).exists()]
    add_check(checks, failures, "REQUIRED_OUTPUTS", not missing, f"missing={missing}")
    if missing:
        payload = {"validation_version": "1.4.0", "program_id": "FMDL-3A", "status": "FAIL", "checks": checks, "hard_failures": failures}
        write_json(validation_path, payload)
        return 2

    decision = load_json(root / "FMDL3A_SOURCE_DECISION.json")
    manifest = load_json(root / "FMDL3A_MANIFEST.json")
    rows = pd.read_csv(root / "FMDL3A_BENCHMARK_ROWS.csv")
    coverage = pd.read_csv(root / "FMDL3A_COVERAGE_MAP.csv")
    pit = pd.read_csv(root / "FMDL3A_POINT_IN_TIME_EVIDENCE.csv")
    support = pd.read_csv(root / "FMDL3A_SUPPORT_QUARANTINE_MAP.csv")
    capitalization = pd.read_csv(root / "FMDL3A_CAPITALIZATION_EVIDENCE.csv")
    source_index = pd.read_csv(root / "FMDL3_SOURCE_INDEX.csv")
    policy = config["acceptance_policy"]

    add_check(checks, failures, "SOURCE_DECISION_STATUS", decision.get("status") == "FMDL3A_ACCEPTED_SOURCE_ROUTE_AND_COVERAGE_GATES_FROZEN", str(decision.get("status")))
    add_check(checks, failures, "DECISION_HARD_FAILURES", not decision.get("hard_failures"), str(decision.get("hard_failures")))

    trade_values = set(rows.get("trade_authority", pd.Series(dtype=str)).dropna().astype(str).unique())
    source_trade_values = set(source_index.get("trade_authority", pd.Series(dtype=str)).dropna().astype(str).unique())
    support_trade_values = set(support.get("trade_authority", pd.Series(dtype=str)).dropna().astype(str).unique())
    cap_trade_values = set(capitalization.get("trade_authority", pd.Series(dtype=str)).dropna().astype(str).unique())
    trade_none = config.get("trade_authority") == "NONE" and decision.get("trade_authority") == "NONE" and trade_values <= {"NONE"} and source_trade_values <= {"NONE"} and support_trade_values <= {"NONE"} and cap_trade_values <= {"NONE"}
    add_check(checks, failures, "ZERO_TRADE_AUTHORITY", trade_none, f"rows={trade_values}; source_index={source_trade_values}; support={support_trade_values}; capitalization={cap_trade_values}")

    source_ids_missing = int(rows["source_id"].isna().sum()) + int((rows["source_id"].astype(str).str.strip() == "").sum())
    add_check(checks, failures, "ZERO_MISSING_SOURCE_ID", source_ids_missing == 0, f"missing={source_ids_missing}")

    expected_symbols = {item["symbol"] for item in config["sample_design"]["symbols"]}
    observed_symbols = set(support["symbol"].astype(str))
    add_check(checks, failures, "SUPPORT_MAP_ALL_SAMPLE_SYMBOLS", observed_symbols == expected_symbols, f"missing={sorted(expected_symbols - observed_symbols)}; extra={sorted(observed_symbols - expected_symbols)}")
    allowed_statuses = {"SUPPORTED", "QUARANTINED"}
    statuses_valid = set(support["statement_status"].astype(str)) <= allowed_statuses
    add_check(checks, failures, "ALL_SYMBOLS_SUPPORTED_OR_QUARANTINED", statuses_valid, f"statuses={sorted(set(support['statement_status'].astype(str)))}")

    quarantined = support["statement_status"].eq("QUARANTINED")
    supported = support["statement_status"].eq("SUPPORTED")
    quarantine_ratio = float(quarantined.mean()) if len(support) else 1.0
    eligible_denominator = int((~quarantined).sum())
    supported_ratio = float(supported.sum() / eligible_denominator) if eligible_denominator else 0.0
    add_check(checks, failures, "SUPPORTED_UNIVERSE_STATEMENT_GATE", supported_ratio >= policy["minimum_supported_universe_statement_bundle_success_ratio"], f"ratio={supported_ratio:.6f}")
    add_check(checks, failures, "STATEMENT_QUARANTINE_CAP", quarantine_ratio <= policy["maximum_full_sample_statement_quarantine_ratio"], f"ratio={quarantine_ratio:.6f}")

    bse = support[support["board"] == "BSE"]
    bse_controlled = bool(len(bse) and bse["statement_status"].eq("QUARANTINED").all() and bse["official_document_source_available"].astype(str).str.lower().isin({"true", "1"}).all() and bse["status_reason"].astype(str).str.contains("CNINFO", na=False).all())
    add_check(checks, failures, "BSE_CONTROLLED_QUARANTINE_WITH_OFFICIAL_DOCUMENTS", bse_controlled, bse[["symbol", "statement_status", "official_document_source_available", "status_reason"]].to_dict(orient="records") if len(bse) else "missing BSE rows")

    profile_complete = support.groupby("profile")["statement_status"].apply(lambda series: series.isin(allowed_statuses).all()).all()
    board_complete = support.groupby("board")["statement_status"].apply(lambda series: series.isin(allowed_statuses).all()).all()
    add_check(checks, failures, "EACH_PROFILE_SUPPORTED_OR_QUARANTINED", bool(profile_complete), "all required profiles represented")
    add_check(checks, failures, "EACH_BOARD_SUPPORTED_OR_QUARANTINED", bool(board_complete), "all required boards represented")

    future_count = int(pit.get("future_information_flag", pd.Series(dtype=bool)).fillna(False).astype(str).str.lower().isin({"true", "1"}).sum()) if not pit.empty else 0
    add_check(checks, failures, "ZERO_POINT_IN_TIME_LEAKAGE", future_count == 0, f"future_information_count={future_count}")
    if not pit.empty:
        available = pd.to_datetime(pit["available_from"], errors="coerce", utc=True)
        announced = pd.to_datetime(pit["announcement_timestamp_raw"], errors="coerce", utc=True)
        comparable = available.notna() & announced.notna()
        ordering_violations = int((available[comparable] <= announced[comparable]).sum())
        official_ratio = float(pit["match_status"].eq("OFFICIAL_MATCHED").mean())
    else:
        ordering_violations = 0
        official_ratio = 0.0
    add_check(checks, failures, "AVAILABILITY_AFTER_ANNOUNCEMENT", ordering_violations == 0, f"violations={ordering_violations}")
    add_check(checks, failures, "OFFICIAL_PIT_MATCH_GATE", official_ratio >= policy["minimum_point_in_time_match_ratio"], f"ratio={official_ratio:.6f}")

    supported_symbols = set(support.loc[support["statement_status"] == "SUPPORTED", "symbol"].astype(str))
    cap_symbols = set(capitalization["symbol"].astype(str))
    cap_coverage = len(cap_symbols & supported_symbols) / len(supported_symbols) if supported_symbols else 0.0
    add_check(checks, failures, "SUPPORTED_UNIVERSE_CURRENT_CAPITALIZATION_GATE", cap_coverage >= policy["minimum_supported_universe_current_capitalization_coverage"], f"coverage={cap_coverage:.6f}; missing={sorted(supported_symbols - cap_symbols)}")
    required_cap_columns = {"price_as_of_date", "close", "share_effective_date", "total_shares", "float_a_shares", "total_market_cap_cny", "float_market_cap_cny", "price_source_id", "share_source_id", "capitalization_source_id"}
    add_check(checks, failures, "CAPITALIZATION_EVIDENCE_FIELDS", required_cap_columns <= set(capitalization.columns), f"missing={sorted(required_cap_columns - set(capitalization.columns))}")
    price_dates = pd.to_datetime(capitalization["price_as_of_date"], errors="coerce")
    share_dates = pd.to_datetime(capitalization["share_effective_date"], errors="coerce")
    future_share_count = int((share_dates > price_dates).sum())
    positive_values = bool((pd.to_numeric(capitalization["close"], errors="coerce") > 0).all() and (pd.to_numeric(capitalization["total_shares"], errors="coerce") > 0).all() and (pd.to_numeric(capitalization["float_a_shares"], errors="coerce") > 0).all() and (pd.to_numeric(capitalization["total_market_cap_cny"], errors="coerce") > 0).all() and (pd.to_numeric(capitalization["float_market_cap_cny"], errors="coerce") > 0).all())
    add_check(checks, failures, "ZERO_FUTURE_EFFECTIVE_SHARE_COUNT", future_share_count == 0, f"future={future_share_count}")
    add_check(checks, failures, "POSITIVE_CAPITALIZATION_INPUTS_AND_OUTPUTS", positive_values, "price, shares and market caps are positive")
    formula_total = pd.to_numeric(capitalization["close"], errors="coerce") * pd.to_numeric(capitalization["total_shares"], errors="coerce")
    formula_float = pd.to_numeric(capitalization["close"], errors="coerce") * pd.to_numeric(capitalization["float_a_shares"], errors="coerce")
    total_match = ((formula_total - pd.to_numeric(capitalization["total_market_cap_cny"], errors="coerce")).abs() <= 0.01).all()
    float_match = ((formula_float - pd.to_numeric(capitalization["float_market_cap_cny"], errors="coerce")).abs() <= 0.01).all()
    add_check(checks, failures, "CAPITALIZATION_FORMULA_REPLAY", bool(total_match and float_match), f"total={total_match}; float={float_match}")

    semantics_ok = decision.get("valuation_semantics") == config.get("valuation_semantics") and config["valuation_semantics"]["provider_pe_pb_role"] == "SUPPORT_ONLY_NOT_DECISION_GRADE"
    add_check(checks, failures, "RECOMPUTED_VALUATION_SEMANTICS", semantics_ok, decision.get("valuation_semantics"))

    route_expectations = {
        "CNINFO_OFFICIAL_DISCLOSURE": "PRIMARY_ANNOUNCEMENT_REVISION_AND_BSE_DOCUMENT_SOURCE",
        "EASTMONEY_STATEMENTS": "PRIMARY_STRUCTURED_THREE_STATEMENT_SOURCE_SH_SZ",
        "EASTMONEY_BSE_PERIODIC_STATEMENTS": "REJECTED_EMPTY_STRUCTURED_ROUTE; BSE_QUARANTINED_FOR_FMDL3B_OFFICIAL_DOCUMENT_EXTRACTION",
        "SINA_STATEMENTS": "FALLBACK_STRUCTURED_THREE_STATEMENT_SOURCE_SH_SZ",
        "FMDL1_ACCEPTED_CURRENT_PRICE": "PRIMARY_LATEST_COMPLETED_SESSION_CLOSE_SOURCE",
        "EASTMONEY_EFFECTIVE_SHARE_CAPITAL": "PRIMARY_PIT_EFFECTIVE_TOTAL_AND_FLOAT_A_SHARE_SOURCE_SUPPORTED_UNIVERSE",
        "COMPOSITE_CURRENT_CAPITALIZATION": "PRIMARY_DERIVED_TOTAL_AND_FLOAT_MARKET_CAP_SOURCE_SUPPORTED_UNIVERSE",
        "EASTMONEY_INDIVIDUAL_INFO": "REJECTED_GITHUB_RUNNER_NON_JSON_ROUTE; EVIDENCE_ONLY",
        "XUEQIU_CURRENT_VALUATION": "REJECTED_GITHUB_RUNNER_RESPONSE_ROUTE; EVIDENCE_ONLY",
        "EASTMONEY_CURRENT_VALUATION": "REJECTED_GITHUB_RUNNER_UNSTABLE_ROUTE; EVIDENCE_ONLY",
    }
    for source_id, expected in route_expectations.items():
        observed = decision_for(decision, source_id).get("decision")
        add_check(checks, failures, f"ROUTE_{source_id}", observed == expected, f"observed={observed}; expected={expected}")

    configured_sources = {item["source_id"] for item in config["source_candidates"]}
    indexed_sources = set(source_index["source_id"].dropna().astype(str))
    add_check(checks, failures, "SOURCE_INDEX_COMPLETENESS", configured_sources <= indexed_sources, f"missing={sorted(configured_sources - indexed_sources)}")

    manifest_errors: list[str] = []
    for name, metadata in manifest.get("files", {}).items():
        path = ROOT / metadata["path"]
        if not path.exists():
            manifest_errors.append(f"{name}:missing")
            continue
        if sha256(path) != metadata["sha256"]:
            manifest_errors.append(f"{name}:hash")
        if path.stat().st_size != metadata["size_bytes"]:
            manifest_errors.append(f"{name}:size")
    add_check(checks, failures, "MANIFEST_INTEGRITY", not manifest_errors, str(manifest_errors))

    dimensions = set(coverage["dimension_type"].dropna().astype(str).unique())
    add_check(checks, failures, "COVERAGE_MAP_DIMENSIONS", {"PROFILE", "BOARD"} <= dimensions, f"observed={sorted(dimensions)}")
    add_check(checks, failures, "NUMERIC_GATES_FROZEN", decision.get("frozen_numeric_gates") == policy, "decision gates equal config acceptance policy")

    status = "PASS" if not failures else "FAIL"
    payload = {
        "validation_version": "1.4.0",
        "run_id": decision.get("run_id"),
        "generated_at": pd.Timestamp.now(tz="Asia/Shanghai").isoformat(),
        "program_id": "FMDL-3A",
        "status": status,
        "checks": checks,
        "hard_failures": failures,
        "decision_status": decision.get("status"),
        "measured_metrics": decision.get("measured_metrics"),
        "source_decision_path": str((root / "FMDL3A_SOURCE_DECISION.json").relative_to(ROOT)),
        "coverage_map_path": str((root / "FMDL3A_COVERAGE_MAP.csv").relative_to(ROOT)),
        "support_quarantine_map_path": str((root / "FMDL3A_SUPPORT_QUARANTINE_MAP.csv").relative_to(ROOT)),
        "capitalization_evidence_path": str((root / "FMDL3A_CAPITALIZATION_EVIDENCE.csv").relative_to(ROOT)),
        "point_in_time_evidence_path": str((root / "FMDL3A_POINT_IN_TIME_EVIDENCE.csv").relative_to(ROOT)),
        "authority": decision.get("authority"),
        "trade_authority": decision.get("trade_authority"),
        "next_phase": decision.get("next_phase"),
    }
    write_json(validation_path, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
