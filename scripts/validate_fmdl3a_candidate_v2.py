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
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def add_check(checks: list[dict[str, Any]], failures: list[str], check_id: str, passed: bool, detail: str) -> None:
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
        "FMDL3A_BENCHMARK_ROWS.csv", "FMDL3A_SOURCE_SUMMARY.csv", "FMDL3A_COVERAGE_MAP.csv",
        "FMDL3A_POINT_IN_TIME_EVIDENCE.csv", "FMDL3_SOURCE_INDEX.csv",
        "FMDL3A_SOURCE_DECISION.json", "FMDL3A_MANIFEST.json",
    ]
    missing = [name for name in required if not (root / name).exists()]
    add_check(checks, failures, "REQUIRED_OUTPUTS", not missing, f"missing={missing}")
    if missing:
        payload = {"validation_version": "1.1.0", "program_id": "FMDL-3A", "status": "FAIL", "checks": checks, "hard_failures": failures}
        write_json(validation_path, payload)
        return 2

    decision = load_json(root / "FMDL3A_SOURCE_DECISION.json")
    manifest = load_json(root / "FMDL3A_MANIFEST.json")
    rows = pd.read_csv(root / "FMDL3A_BENCHMARK_ROWS.csv")
    coverage = pd.read_csv(root / "FMDL3A_COVERAGE_MAP.csv")
    pit = pd.read_csv(root / "FMDL3A_POINT_IN_TIME_EVIDENCE.csv")
    source_index = pd.read_csv(root / "FMDL3_SOURCE_INDEX.csv")

    accepted_status = decision.get("status") == "FMDL3A_ACCEPTED_SOURCE_ROUTE_AND_COVERAGE_GATES_FROZEN"
    add_check(checks, failures, "SOURCE_DECISION_STATUS", accepted_status, str(decision.get("status")))
    add_check(checks, failures, "DECISION_HARD_FAILURES", not decision.get("hard_failures"), str(decision.get("hard_failures")))

    trade_values = set(rows.get("trade_authority", pd.Series(dtype=str)).dropna().astype(str).unique())
    source_trade_values = set(source_index.get("trade_authority", pd.Series(dtype=str)).dropna().astype(str).unique())
    trade_none = config.get("trade_authority") == "NONE" and decision.get("trade_authority") == "NONE" and trade_values <= {"NONE"} and source_trade_values <= {"NONE"}
    add_check(checks, failures, "ZERO_TRADE_AUTHORITY", trade_none, f"rows={trade_values}; source_index={source_trade_values}")

    source_ids_missing = int(rows["source_id"].isna().sum()) + int((rows["source_id"].astype(str).str.strip() == "").sum())
    add_check(checks, failures, "ZERO_MISSING_SOURCE_ID", source_ids_missing == 0, f"missing={source_ids_missing}")

    required_profiles = set(config["sample_design"]["minimum_profiles"])
    required_boards = set(config["sample_design"]["minimum_boards"])
    samples = pd.DataFrame(config["sample_design"]["symbols"])
    composite_records: list[dict[str, Any]] = []
    for sample in config["sample_design"]["symbols"]:
        source_id = "EASTMONEY_BSE_PERIODIC_STATEMENTS" if sample["board"] == "BSE" else "EASTMONEY_STATEMENTS"
        selected = rows[(rows["source_id"] == source_id) & (rows["component"] == "THREE_STATEMENT_BUNDLE") & (rows["symbol"] == sample["symbol"])]
        composite_records.append({**sample, "source_id": source_id, "success": bool(len(selected) and selected["status"].iloc[0] == "SUCCESS")})
    composite = pd.DataFrame(composite_records)
    successful_profiles = set(composite.loc[composite["success"], "profile"].astype(str))
    successful_boards = set(composite.loc[composite["success"], "board"].astype(str))
    add_check(checks, failures, "COMPOSITE_STATEMENT_EACH_PROFILE", required_profiles <= successful_profiles, f"successful={sorted(successful_profiles)}")
    add_check(checks, failures, "COMPOSITE_STATEMENT_EACH_BOARD", required_boards <= successful_boards, f"successful={sorted(successful_boards)}")
    add_check(checks, failures, "COMPOSITE_STATEMENT_ALL_SAMPLES", bool(composite["success"].all()), f"failed={composite.loc[~composite['success'], 'symbol'].tolist()}")

    bse_bundle = rows[(rows["source_id"] == "EASTMONEY_BSE_PERIODIC_STATEMENTS") & (rows["component"] == "THREE_STATEMENT_BUNDLE")]
    expected_bse = set(samples.loc[samples["board"] == "BSE", "symbol"])
    successful_bse = set(bse_bundle.loc[bse_bundle["status"] == "SUCCESS", "symbol"])
    add_check(checks, failures, "BSE_PERIODIC_STATEMENT_ROUTE", expected_bse <= successful_bse, f"successful={sorted(successful_bse)}")

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
    add_check(checks, failures, "OFFICIAL_PIT_MATCH_GATE", official_ratio >= config["acceptance_policy"]["minimum_point_in_time_match_ratio"], f"ratio={official_ratio:.6f}")

    route_expectations = {
        "CNINFO_OFFICIAL_DISCLOSURE": "PRIMARY_ANNOUNCEMENT_AND_REVISION_METADATA",
        "EASTMONEY_STATEMENTS": "PRIMARY_STRUCTURED_THREE_STATEMENT_SOURCE_SH_SZ",
        "EASTMONEY_BSE_PERIODIC_STATEMENTS": "PRIMARY_STRUCTURED_THREE_STATEMENT_SOURCE_BSE",
        "SINA_STATEMENTS": "FALLBACK_STRUCTURED_THREE_STATEMENT_SOURCE_SH_SZ",
        "EASTMONEY_CURRENT_VALUATION": "PRIMARY_CURRENT_MARKET_CAP_PE_PB_SOURCE_SPLIT_BY_EXCHANGE",
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
    measured_gates_match = decision.get("frozen_numeric_gates") == config["acceptance_policy"]
    add_check(checks, failures, "NUMERIC_GATES_FROZEN", measured_gates_match, "decision gates equal config acceptance policy")

    status = "PASS" if not failures else "FAIL"
    payload = {
        "validation_version": "1.1.0",
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
