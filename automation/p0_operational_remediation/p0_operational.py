#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CONTROL = Path("investment_os_runtime/00_CONTROL")
SCHEMAS = Path("investment_os_runtime/20_SCHEMAS_AND_INTERFACES")

REQUIRED_NEW = [
    "CORE_STATIC_CONSTITUTION_CURRENT.md",
    "CORE_RULE_CATALOG_CURRENT.json",
    "CANONICAL_IO_CONTRACT_CURRENT.json",
    "MARKET_DATA_EOD_CONTRACT_CURRENT.json",
    "PORTFOLIO_SNAPSHOT_CONTRACT_CURRENT.json",
    "PERFORMANCE_ATTRIBUTION_CONTRACT_CURRENT.json",
    "REPORTING_MANIFEST_CONTRACT_CURRENT.json",
    "RESEARCH_FUNNEL_CONTRACT_CURRENT.json",
    "OBSERVABILITY_CONTRACT_CURRENT.json",
    "P0_ACCEPTANCE_REGISTER_CURRENT.json",
    "R6_P0_ACCEPTANCE_CHECKLIST_CURRENT.md",
]

REQUIRED_EXISTING = [
    "investment_os_runtime/00_CONTROL/EXECUTION_REGISTER_CURRENT.json",
    "investment_os_runtime/00_CONTROL/R4_OPERATING_PRODUCT_CONTRACT_CURRENT.json",
    "investment_os_runtime/00_CONTROL/R5_ATTRIBUTION_CONTRACT_CURRENT.json",
    "investment_os_runtime/00_CONTROL/R6_PRODUCTION_ACCEPTANCE_CONTRACT_CURRENT.json",
    "investment_os_runtime/80_PRODUCTION_ACCEPTANCE/R6_OBSERVATION_LEDGER_CURRENT.json",
    "investment_os_runtime/30_STATE_CURRENT/10_REAL_ACCOUNT/REAL_ACCOUNT_POSITIONS_CURRENT.json",
    "investment_os_runtime/30_STATE_CURRENT/20_SIMULATION/SIMULATION_POSITIONS_CURRENT.json",
    "investment_os_runtime/30_STATE_CURRENT/40_CANDIDATE/CANDIDATE_CURRENT.json",
]

CANDIDATE_LANES = {
    "candidate_core": "candidate_core_members",
    "research_queue": "research_queue_members",
    "shadow_track": "shadow_track_members",
    "ready_for_user_decision": "ready_for_user_decision_members",
}


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def stable_id(prefix: str, payload: dict[str, Any]) -> str:
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return f"{prefix}_{hashlib.sha256(raw).hexdigest()[:16]}"


def authority_values(value: Any) -> list[Any]:
    out: list[Any] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "trade_authority":
                out.append(item)
            else:
                out.extend(authority_values(item))
    elif isinstance(value, list):
        for item in value:
            out.extend(authority_values(item))
    return out


def list_value(
    payload: dict[str, Any],
    key: str,
    label: str,
    errors: list[str],
) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list):
        errors.append(f"{label}_NOT_LIST")
        return []
    return value


def validate(repo: Path) -> dict[str, Any]:
    errors: list[str] = []
    blockers: list[str] = []
    facts: dict[str, Any] = {}

    for name in REQUIRED_NEW:
        if not (repo / CONTROL / name).exists():
            errors.append(f"MISSING_P0_ASSET:{name}")

    for rel in REQUIRED_EXISTING:
        if not (repo / rel).exists():
            errors.append(f"MISSING_CANONICAL_ASSET:{rel}")

    contract_names = [
        "CORE_RULE_CATALOG_CURRENT.json",
        "CANONICAL_IO_CONTRACT_CURRENT.json",
        "MARKET_DATA_EOD_CONTRACT_CURRENT.json",
        "PORTFOLIO_SNAPSHOT_CONTRACT_CURRENT.json",
        "PERFORMANCE_ATTRIBUTION_CONTRACT_CURRENT.json",
        "REPORTING_MANIFEST_CONTRACT_CURRENT.json",
        "RESEARCH_FUNNEL_CONTRACT_CURRENT.json",
        "OBSERVABILITY_CONTRACT_CURRENT.json",
        "P0_ACCEPTANCE_REGISTER_CURRENT.json",
    ]
    for name in contract_names:
        path = repo / CONTROL / name
        if not path.exists():
            continue
        try:
            payload = load(path)
            if payload.get("trade_authority") != "NONE":
                errors.append(f"TRADE_AUTHORITY_VIOLATION:{name}")
        except Exception as exc:
            errors.append(f"INVALID_JSON:{name}:{exc}")

    schema_names = [
        "canonical_run_manifest.schema.json",
        "report_manifest.schema.json",
        "p0_acceptance_register.schema.json",
    ]
    for name in schema_names:
        path = repo / SCHEMAS / name
        if not path.exists():
            errors.append(f"MISSING_SCHEMA:{name}")
            continue
        try:
            if load(path).get("$schema") != "https://json-schema.org/draft/2020-12/schema":
                errors.append(f"SCHEMA_DIALECT:{name}")
        except Exception as exc:
            errors.append(f"INVALID_SCHEMA:{name}:{exc}")

    if errors:
        return {
            "status": "FAIL",
            "errors": errors,
            "blockers": blockers,
            "facts": facts,
            "trade_authority": "NONE",
        }

    execution = load(repo / REQUIRED_EXISTING[0])
    r4 = load(repo / REQUIRED_EXISTING[1])
    r5 = load(repo / REQUIRED_EXISTING[2])
    r6 = load(repo / REQUIRED_EXISTING[3])
    ledger = load(repo / REQUIRED_EXISTING[4])
    real = load(repo / REQUIRED_EXISTING[5])
    simulation = load(repo / REQUIRED_EXISTING[6])
    candidate = load(repo / REQUIRED_EXISTING[7])

    canonical_payloads = [
        ("execution", execution),
        ("r4", r4),
        ("r5", r5),
        ("r6", r6),
        ("ledger", ledger),
        ("real", real),
        ("simulation", simulation),
        ("candidate", candidate),
    ]
    for label, payload in canonical_payloads:
        values = authority_values(payload)
        if not values:
            errors.append(f"CANONICAL_TRADE_AUTHORITY_MISSING:{label}")
            continue
        bad = [value for value in values if value != "NONE"]
        if bad:
            errors.append(f"CANONICAL_TRADE_AUTHORITY_VIOLATION:{label}:{bad}")

    real_holdings = list_value(real, "holdings", "REAL_HOLDINGS", errors)
    simulation_holdings = list_value(
        simulation,
        "holdings",
        "SIMULATION_HOLDINGS",
        errors,
    )
    facts["real"] = len(real_holdings)
    facts["simulation"] = len(simulation_holdings)

    candidate_counts = candidate.get("counts")
    if not isinstance(candidate_counts, dict):
        errors.append("CANDIDATE_COUNTS_NOT_OBJECT")
        candidate_counts = {}

    for count_key, members_key in CANDIDATE_LANES.items():
        members = list_value(
            candidate,
            members_key,
            f"CANDIDATE_{members_key.upper()}",
            errors,
        )
        declared = candidate_counts.get(count_key)
        if not isinstance(declared, int) or declared < 0:
            errors.append(f"CANDIDATE_COUNT_INVALID:{count_key}:{declared}")
        elif declared != len(members):
            errors.append(
                f"CANDIDATE_COUNT_MISMATCH:{count_key}:declared={declared}:actual={len(members)}"
            )
        facts[count_key] = len(members)

    checkpoint_passed = ledger.get("checkpoint_passed", 0)
    checkpoint_total = ledger.get("checkpoint_total", 0)
    facts["r6_checkpoint"] = f"{checkpoint_passed}/{checkpoint_total}"
    if checkpoint_passed < checkpoint_total:
        blockers.append("R6_CHECKPOINTS_INCOMPLETE")
    if not r6.get("production_completion_definition", {}).get("full_month_complete"):
        blockers.append("R6_FULL_MONTH_NOT_COMPLETE")
    if r4.get("development_mode") is True:
        blockers.append("OPERATING_PRODUCTS_NOT_LIVE")
    if any(
        "BLOCKED" in str(layer.get("status"))
        or "PARTIAL" in str(layer.get("status"))
        for layer in r5.get("layers", [])
    ):
        blockers.append("EXACT_PERIOD_ATTRIBUTION_INPUTS_INCOMPLETE")

    market_data_contract = load(repo / CONTROL / "MARKET_DATA_EOD_CONTRACT_CURRENT.json")
    blockers.extend(market_data_contract.get("current_blockers", []))

    status = "FAIL" if errors else ("PASS_WITH_BLOCKERS" if blockers else "PASS")
    return {
        "status": status,
        "errors": errors,
        "blockers": sorted(set(blockers)),
        "facts": facts,
        "trade_authority": "NONE",
    }


def build_run(args: argparse.Namespace) -> dict[str, Any]:
    payload = {
        "workflow_name": args.workflow_name,
        "trigger_type": args.trigger_type,
        "started_at": args.started_at,
        "completed_at": args.completed_at,
        "canonical_commit_before": args.commit_before,
        "canonical_commit_after": args.commit_after,
        "market_data_watermark": args.market_watermark,
        "position_watermark": args.position_watermark,
        "inputs": sorted(args.input),
        "outputs": sorted(args.output_asset),
        "exceptions": args.exception,
        "idempotency_key": args.idempotency_key,
        "status": args.status,
        "trade_authority": "NONE",
    }
    payload["run_id"] = stable_id("RUN", payload)
    return payload


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    if not 0 <= args.completeness <= 1:
        raise ValueError("completeness must be between 0 and 1")

    exceptions = list(args.exception)
    watermarks = {
        "market_data_watermark": args.market_watermark,
        "position_watermark": args.position_watermark,
        "candidate_watermark": args.candidate_watermark,
    }
    for field, value in watermarks.items():
        if not value:
            exceptions.append(f"MISSING_{field.upper()}")

    if args.completeness == 1 and not exceptions:
        status = "FORMAL"
    elif args.completeness < 0.5 or any(
        item.startswith("MISSING_") for item in exceptions
    ):
        status = "BLOCKED"
    else:
        status = "PROVISIONAL"

    payload = {
        "report_type": args.report_type,
        "period_start": args.period_start,
        "period_end": args.period_end,
        "generated_at": args.generated_at,
        "canonical_commit_sha": args.commit,
        **watermarks,
        "input_assets": sorted(args.input),
        "exceptions": sorted(set(exceptions)),
        "publication_status": status,
        "trade_authority": "NONE",
    }
    payload["report_id"] = stable_id(args.report_type, payload)
    return payload


def write_or_print(payload: dict[str, Any], path: str | None) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path:
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text, encoding="utf-8")
    print(text, end="")


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--repo-root", default=".")
    validate_parser.add_argument("--output")

    run_parser = subparsers.add_parser("build-run-manifest")
    for name in [
        "workflow-name",
        "trigger-type",
        "started-at",
        "completed-at",
        "commit-before",
        "commit-after",
        "idempotency-key",
        "status",
    ]:
        run_parser.add_argument("--" + name, required=True)
    run_parser.add_argument("--market-watermark")
    run_parser.add_argument("--position-watermark")
    run_parser.add_argument("--input", action="append", default=[])
    run_parser.add_argument("--output-asset", action="append", default=[])
    run_parser.add_argument("--exception", action="append", default=[])
    run_parser.add_argument("--output")

    report_parser = subparsers.add_parser("build-report-manifest")
    report_parser.add_argument(
        "--report-type",
        choices=["STATUS", "DAILY", "WEEKLY", "MONTHLY", "QUARTERLY", "ANNUAL", "EVENT"],
        required=True,
    )
    report_parser.add_argument("--period-start", required=True)
    report_parser.add_argument("--period-end", required=True)
    report_parser.add_argument(
        "--generated-at",
        default=datetime.now(timezone.utc).isoformat(),
    )
    report_parser.add_argument("--commit", required=True)
    report_parser.add_argument("--market-watermark")
    report_parser.add_argument("--position-watermark")
    report_parser.add_argument("--candidate-watermark")
    report_parser.add_argument("--completeness", type=float, required=True)
    report_parser.add_argument("--input", action="append", default=[])
    report_parser.add_argument("--exception", action="append", default=[])
    report_parser.add_argument("--output")

    args = parser.parse_args()
    if args.cmd == "validate":
        result = validate(Path(args.repo_root))
        write_or_print(result, args.output)
        return 1 if result["status"] == "FAIL" else 0
    if args.cmd == "build-run-manifest":
        write_or_print(build_run(args), args.output)
        return 0
    write_or_print(build_report(args), args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
