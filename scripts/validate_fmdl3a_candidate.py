from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import jsonschema
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "fmdl3a_benchmark.json"
DEFAULT_SCHEMA = ROOT / "schemas" / "fmdl3a_benchmark.schema.json"


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def add_check(checks: list[dict[str, Any]], check_id: str, passed: bool, detail: str) -> None:
    checks.append({"check_id": check_id, "status": "PASS" if passed else "FAIL", "detail": detail})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate FMDL-3A benchmark candidate.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cfg = load_json(args.config)
    schema = load_json(args.schema)
    candidate_root = ROOT / cfg["publication"]["candidate_root"]
    validation_path = candidate_root / "FMDL3A_VALIDATION.json"
    checks: list[dict[str, Any]] = []
    hard_failures: list[str] = []

    try:
        jsonschema.validate(cfg, schema)
        add_check(checks, "CONFIG_SCHEMA", True, "config conforms to FMDL-3A schema")
    except Exception as exc:
        add_check(checks, "CONFIG_SCHEMA", False, str(exc))
        hard_failures.append("CONFIG_SCHEMA")

    required_files = [
        "FMDL3A_BENCHMARK_ROWS.csv",
        "FMDL3A_SOURCE_SUMMARY.csv",
        "FMDL3A_COVERAGE_MAP.csv",
        "FMDL3A_POINT_IN_TIME_EVIDENCE.csv",
        "FMDL3_SOURCE_INDEX.csv",
        "FMDL3A_SOURCE_DECISION.json",
        "FMDL3A_MANIFEST.json",
    ]
    missing = [name for name in required_files if not (candidate_root / name).exists()]
    add_check(checks, "REQUIRED_OUTPUTS", not missing, f"missing={missing}")
    if missing:
        hard_failures.append("REQUIRED_OUTPUTS")
        write_json(validation_path, {"validation_version": "1.0.0", "program_id": "FMDL-3A", "status": "FAIL", "checks": checks, "hard_failures": hard_failures})
        return 2

    decision = load_json(candidate_root / "FMDL3A_SOURCE_DECISION.json")
    manifest = load_json(candidate_root / "FMDL3A_MANIFEST.json")
    rows = pd.read_csv(candidate_root / "FMDL3A_BENCHMARK_ROWS.csv")
    coverage = pd.read_csv(candidate_root / "FMDL3A_COVERAGE_MAP.csv")
    pit = pd.read_csv(candidate_root / "FMDL3A_POINT_IN_TIME_EVIDENCE.csv")
    source_index = pd.read_csv(candidate_root / "FMDL3_SOURCE_INDEX.csv")

    decision_ok = decision.get("status") == "FMDL3A_ACCEPTED_SOURCE_ROUTE_AND_COVERAGE_GATES_FROZEN"
    add_check(checks, "SOURCE_DECISION_STATUS", decision_ok, str(decision.get("status")))
    if not decision_ok: hard_failures.append("SOURCE_DECISION_STATUS")

    no_decision_failures = not decision.get("hard_failures")
    add_check(checks, "DECISION_HARD_FAILURES", no_decision_failures, str(decision.get("hard_failures")))
    if not no_decision_failures: hard_failures.append("DECISION_HARD_FAILURES")

    trade_none = cfg.get("trade_authority") == "NONE" and decision.get("trade_authority") == "NONE" and set(source_index.get("trade_authority", pd.Series(dtype=str)).dropna().astype(str).unique()) <= {"NONE"}
    add_check(checks, "ZERO_TRADE_AUTHORITY", trade_none, "config, decision and source index")
    if not trade_none: hard_failures.append("ZERO_TRADE_AUTHORITY")

    required_profiles = set(cfg["sample_design"]["minimum_profiles"])
    required_boards = set(cfg["sample_design"]["minimum_boards"])
    observed_profiles = set(rows.loc[rows["symbol"] != "*", "profile"].dropna().astype(str).unique())
    observed_boards = set(rows.loc[rows["symbol"] != "*", "board"].dropna().astype(str).unique())
    profiles_ok = required_profiles <= observed_profiles
    boards_ok = required_boards <= observed_boards
    add_check(checks, "PROFILE_COVERAGE_DESIGN", profiles_ok, f"observed={sorted(observed_profiles)}")
    add_check(checks, "BOARD_COVERAGE_DESIGN", boards_ok, f"observed={sorted(observed_boards)}")
    if not profiles_ok: hard_failures.append("PROFILE_COVERAGE_DESIGN")
    if not boards_ok: hard_failures.append("BOARD_COVERAGE_DESIGN")

    primary_bundle = rows[(rows["source_id"] == "EASTMONEY_STATEMENTS") & (rows["component"] == "THREE_STATEMENT_BUNDLE")]
    successful_profiles = set(primary_bundle.loc[primary_bundle["status"] == "SUCCESS", "profile"].astype(str))
    profile_statement_ok = required_profiles <= successful_profiles
    add_check(checks, "PRIMARY_STATEMENT_EACH_PROFILE", profile_statement_ok, f"successful_profiles={sorted(successful_profiles)}")
    if not profile_statement_ok: hard_failures.append("PRIMARY_STATEMENT_EACH_PROFILE")

    pit_future = int(pd.to_numeric(pit.get("future_information_flag"), errors="coerce").fillna(0).astype(bool).sum()) if not pit.empty else 0
    add_check(checks, "ZERO_POINT_IN_TIME_LEAKAGE", pit_future == 0, f"future_information_count={pit_future}")
    if pit_future: hard_failures.append("ZERO_POINT_IN_TIME_LEAKAGE")

    if not pit.empty:
        available = pd.to_datetime(pit["available_from"], errors="coerce", utc=True)
        announced = pd.to_datetime(pit["announcement_timestamp_raw"], errors="coerce", utc=True)
        comparable = available.notna() & announced.notna()
        ordering_violations = int((available[comparable] <= announced[comparable]).sum())
    else:
        ordering_violations = 0
    add_check(checks, "AVAILABILITY_AFTER_ANNOUNCEMENT", ordering_violations == 0, f"ordering_violations={ordering_violations}")
    if ordering_violations: hard_failures.append("AVAILABILITY_AFTER_ANNOUNCEMENT")

    def source_decision(source_id: str) -> dict[str, Any]:
        return next((item for item in decision.get("source_decisions", []) if item.get("source_id") == source_id), {})

    official = source_decision("CNINFO_OFFICIAL_DISCLOSURE")
    official_ok = official.get("decision") == "PRIMARY_ANNOUNCEMENT_AND_REVISION_METADATA"
    add_check(checks, "OFFICIAL_DISCLOSURE_ROUTE", official_ok, str(official))
    if not official_ok: hard_failures.append("OFFICIAL_DISCLOSURE_ROUTE")

    statements = source_decision("EASTMONEY_STATEMENTS")
    statement_ok = statements.get("decision") == "PRIMARY_STRUCTURED_THREE_STATEMENT_SOURCE"
    add_check(checks, "PRIMARY_STATEMENT_ROUTE", statement_ok, str(statements))
    if not statement_ok: hard_failures.append("PRIMARY_STATEMENT_ROUTE")

    valuation = source_decision("EASTMONEY_CURRENT_VALUATION")
    valuation_ok = valuation.get("decision") == "PRIMARY_CURRENT_MARKET_CAP_PE_PB_SOURCE"
    add_check(checks, "CURRENT_VALUATION_ROUTE", valuation_ok, str(valuation))
    if not valuation_ok: hard_failures.append("CURRENT_VALUATION_ROUTE")

    required_source_ids = {item["source_id"] for item in cfg["source_candidates"]}
    indexed_source_ids = set(source_index["source_id"].dropna().astype(str))
    source_index_ok = required_source_ids <= indexed_source_ids
    add_check(checks, "SOURCE_INDEX_COMPLETENESS", source_index_ok, f"missing={sorted(required_source_ids - indexed_source_ids)}")
    if not source_index_ok: hard_failures.append("SOURCE_INDEX_COMPLETENESS")

    manifest_errors: list[str] = []
    for name, meta in manifest.get("files", {}).items():
        path = ROOT / meta["path"]
        if not path.exists():
            manifest_errors.append(f"{name}:missing")
            continue
        if sha256_file(path) != meta["sha256"]: manifest_errors.append(f"{name}:hash")
        if path.stat().st_size != meta["size_bytes"]: manifest_errors.append(f"{name}:size")
    add_check(checks, "MANIFEST_INTEGRITY", not manifest_errors, str(manifest_errors))
    if manifest_errors: hard_failures.append("MANIFEST_INTEGRITY")

    coverage_dimensions = set(coverage["dimension_type"].dropna().astype(str).unique())
    coverage_ok = {"PROFILE", "BOARD"} <= coverage_dimensions
    add_check(checks, "COVERAGE_MAP_DIMENSIONS", coverage_ok, f"observed={sorted(coverage_dimensions)}")
    if not coverage_ok: hard_failures.append("COVERAGE_MAP_DIMENSIONS")

    status = "PASS" if not hard_failures else "FAIL"
    payload = {
        "validation_version": "1.0.0",
        "run_id": decision.get("run_id"),
        "generated_at": pd.Timestamp.now(tz="Asia/Shanghai").isoformat(),
        "program_id": "FMDL-3A",
        "status": status,
        "checks": checks,
        "hard_failures": hard_failures,
        "decision_status": decision.get("status"),
        "source_decision_path": str((candidate_root / "FMDL3A_SOURCE_DECISION.json").relative_to(ROOT)),
        "coverage_map_path": str((candidate_root / "FMDL3A_COVERAGE_MAP.csv").relative_to(ROOT)),
        "point_in_time_evidence_path": str((candidate_root / "FMDL3A_POINT_IN_TIME_EVIDENCE.csv").relative_to(ROOT)),
        "authority": decision.get("authority"),
        "trade_authority": decision.get("trade_authority"),
        "next_phase": decision.get("next_phase"),
    }
    write_json(validation_path, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
