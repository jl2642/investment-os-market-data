from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "config/fmdl3_program_contract.json"
SCHEMA_PATH = ROOT / "schemas/fmdl3_program_contract.schema.json"
ARCHITECTURE_DOC = ROOT / "docs/FMDL-3_ARCHITECTURE.md"
PIT_DOC = ROOT / "docs/FMDL-3_POINT_IN_TIME_POLICY.md"
PLAN_DOC = ROOT / "docs/FMDL-3_PHASED_PLAN.md"
DEFAULT_OUTPUT = ROOT / "outputs/architecture/candidate/FMDL3_ARCHITECTURE_VALIDATION.json"

EXPECTED_PHASES = ["FMDL-3A", "FMDL-3B", "FMDL-3C", "FMDL-3D", "FMDL-3E"]
REQUIRED_PROFILES = {
    "GENERAL_NON_FINANCIAL",
    "BANK",
    "INSURANCE",
    "SECURITIES_AND_BROKERAGE",
    "PRE_PROFIT_OR_NEGATIVE_EARNINGS",
}
REQUIRED_TEMPORAL_FIELDS = {
    "report_period_start",
    "report_period_end",
    "fiscal_period_type",
    "announcement_date",
    "announcement_timestamp",
    "available_from",
    "source_retrieved_at",
    "revision_sequence",
    "effective_from",
    "superseded_at",
}
REQUIRED_DATASETS = {
    "fmdl3_source_index",
    "fmdl3_financial_fact_raw",
    "fmdl3_financial_statement_normalized_long",
    "fmdl3_comparability_bridge",
    "fmdl3_financial_factor_detail",
    "fmdl3_valuation_snapshot",
    "fmdl3_shareholder_return_event",
    "fmdl3_final_release",
}
REQUIRED_GATES = {
    "ZERO_POINT_IN_TIME_LEAKAGE",
    "ZERO_SILENT_RESTATEMENT_OVERWRITE",
    "ZERO_INVALID_RATIO_DENOMINATOR_PUBLISHED_AS_VALID",
    "ZERO_NEUTRAL_FILL_FOR_MISSING_FINANCIAL_DATA",
    "ZERO_DECISION_GRADE_ROWS_WITHOUT_SOURCE_LINEAGE",
    "ZERO_FAILED_OR_QUARANTINED_RELEASE_REPLACING_CURRENT",
    "ZERO_TRADE_AUTHORITY",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_contract(contract: dict[str, Any], schema: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []

    def check(check_id: str, passed: bool, detail: str) -> None:
        checks.append({"check_id": check_id, "status": "PASS" if passed else "FAIL", "detail": detail})
        if not passed:
            failures.append(f"{check_id}: {detail}")

    schema_errors = sorted(Draft202012Validator(schema).iter_errors(contract), key=lambda e: list(e.absolute_path))
    check(
        "SCHEMA_VALIDATION",
        not schema_errors,
        "schema valid" if not schema_errors else "; ".join(error.message for error in schema_errors),
    )

    phase_ids = [row.get("phase_id") for row in contract.get("phase_sequence", [])]
    check("PHASE_SEQUENCE", phase_ids == EXPECTED_PHASES, f"observed={phase_ids}")

    profiles = {row.get("profile_id") for row in contract.get("sector_profiles", [])}
    check("SECTOR_PROFILES", REQUIRED_PROFILES.issubset(profiles), f"observed={sorted(profiles)}")

    temporal = set(contract.get("point_in_time_contract", {}).get("required_temporal_fields", []))
    check("TEMPORAL_FIELDS", REQUIRED_TEMPORAL_FIELDS.issubset(temporal), f"observed={sorted(temporal)}")

    datasets = {row.get("dataset_id") for row in contract.get("canonical_datasets", [])}
    check("CANONICAL_DATASETS", REQUIRED_DATASETS.issubset(datasets), f"observed={sorted(datasets)}")

    gates = set(contract.get("global_hard_gates", []))
    check("GLOBAL_HARD_GATES", REQUIRED_GATES.issubset(gates), f"observed={sorted(gates)}")

    check(
        "PUBLICATION_LKG",
        contract.get("publication_contract", {}).get("last_known_good_required") is True
        and contract.get("publication_contract", {}).get("candidate_cannot_replace_current_on_failure") is True,
        "Last-known-good and fail-closed Current replacement must both be true",
    )
    check(
        "POINT_IN_TIME_REPLAY",
        contract.get("publication_contract", {}).get("point_in_time_replay_required_before_final_acceptance") is True,
        "PIT replay is required before FMDL-3 final acceptance",
    )
    check(
        "AUTHORITY_BOUNDARY",
        contract.get("authority") == "DATA_AND_RESEARCH_EVIDENCE_ONLY"
        and contract.get("trade_authority") == "NONE",
        f"authority={contract.get('authority')}; trade_authority={contract.get('trade_authority')}",
    )
    check("NEXT_PHASE", contract.get("next_phase") == "FMDL-3A", f"next_phase={contract.get('next_phase')}")

    return checks, failures


def validate_documents() -> tuple[list[dict[str, Any]], list[str]]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []

    def check(check_id: str, passed: bool, detail: str) -> None:
        checks.append({"check_id": check_id, "status": "PASS" if passed else "FAIL", "detail": detail})
        if not passed:
            failures.append(f"{check_id}: {detail}")

    required_files = [ARCHITECTURE_DOC, PIT_DOC, PLAN_DOC]
    check("DOCUMENTS_EXIST", all(path.exists() for path in required_files), ", ".join(str(path.relative_to(ROOT)) for path in required_files))
    if not all(path.exists() for path in required_files):
        return checks, failures

    architecture = ARCHITECTURE_DOC.read_text(encoding="utf-8")
    pit = PIT_DOC.read_text(encoding="utf-8")
    plan = PLAN_DOC.read_text(encoding="utf-8")

    architecture_tokens = [
        "Point-in-time before breadth",
        "Canonical dataset stack",
        "Sector-profile routing",
        "Valuation semantics",
        "Handoff to FMDL-4",
        "trade authority",
    ]
    check("ARCHITECTURE_CONTENT", all(token in architecture for token in architecture_tokens), f"required_tokens={architecture_tokens}")

    pit_tokens = [
        "report_period_end",
        "announcement_date",
        "available_from",
        "revision_sequence",
        "zero silent restatement overwrites",
    ]
    check("PIT_POLICY_CONTENT", all(token in pit for token in pit_tokens), f"required_tokens={pit_tokens}")

    plan_tokens = EXPECTED_PHASES + [
        "Full-market first",
        "Candidate before Current",
        "Failure preserves LKG",
        "No hidden manual patch",
    ]
    check("PHASED_PLAN_CONTENT", all(token in plan for token in plan_tokens), f"required_tokens={plan_tokens}")

    return checks, failures


def build_validation_payload() -> dict[str, Any]:
    contract = load_json(CONTRACT_PATH)
    schema = load_json(SCHEMA_PATH)
    contract_checks, contract_failures = validate_contract(contract, schema)
    document_checks, document_failures = validate_documents()
    hard_failures = contract_failures + document_failures
    now = datetime.now(ZoneInfo("Asia/Shanghai"))

    return {
        "validation_version": "1.0.0",
        "run_id": f"FMDL3_ARCH_{now.strftime('%Y%m%dT%H%M%S%z')}",
        "generated_at": now.isoformat(timespec="seconds"),
        "program_id": "FMDL-3",
        "architecture_state": contract.get("architecture_state"),
        "status": "PASS" if not hard_failures else "FAIL",
        "checks": contract_checks + document_checks,
        "hard_failures": hard_failures,
        "artifacts": {
            "contract": str(CONTRACT_PATH.relative_to(ROOT)),
            "contract_sha256": sha256_file(CONTRACT_PATH),
            "schema": str(SCHEMA_PATH.relative_to(ROOT)),
            "schema_sha256": sha256_file(SCHEMA_PATH),
            "architecture_document": str(ARCHITECTURE_DOC.relative_to(ROOT)),
            "architecture_document_sha256": sha256_file(ARCHITECTURE_DOC),
            "point_in_time_policy": str(PIT_DOC.relative_to(ROOT)),
            "point_in_time_policy_sha256": sha256_file(PIT_DOC),
            "phased_plan": str(PLAN_DOC.relative_to(ROOT)),
            "phased_plan_sha256": sha256_file(PLAN_DOC),
        },
        "phase_sequence": EXPECTED_PHASES,
        "next_phase": "FMDL-3A",
        "authority": "DATA_AND_RESEARCH_EVIDENCE_ONLY",
        "trade_authority": "NONE",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the frozen FMDL-3 architecture and phased plan.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    payload = build_validation_payload()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
