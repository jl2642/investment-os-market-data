#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PRODUCTS = Path("investment_os_runtime/50_OPERATING_PRODUCTS/OBSERVATION")
PROD = Path("investment_os_runtime/80_PRODUCTION_ACCEPTANCE/P0_I1")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def stable_id(prefix: str, payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return f"{prefix}_{hashlib.sha256(raw).hexdigest()[:20]}"


def safe_text(path: str | None) -> str:
    if not path:
        return "NORMAL_OBSERVATION_BUILD_FAILED"
    file_path = Path(path)
    if not file_path.exists():
        return "NORMAL_OBSERVATION_BUILD_FAILED_LOG_MISSING"
    text = file_path.read_text(encoding="utf-8", errors="replace").strip()
    return text[-4000:] if text else "NORMAL_OBSERVATION_BUILD_FAILED_EMPTY_LOG"


def safe_json(path: Path, default: Any) -> Any:
    try:
        return read_json(path) if path.exists() else default
    except Exception:
        return default


def build(args: argparse.Namespace) -> dict[str, Any]:
    output = Path(args.output_root).resolve()
    observed_at = args.observed_at or datetime.now(timezone.utc).isoformat()
    upstream_run_id = str(args.upstream_run_id)
    token = f"{upstream_run_id}_a{args.upstream_run_attempt}"
    build_error = safe_text(args.error_file)
    blockers = sorted({
        "NO_EOD_SNAPSHOT_CREATED",
        "OBSERVATION_BUILD_FAILED",
        "UPSTREAM_WORKFLOW_NOT_SUCCESS" if args.upstream_conclusion != "success" else "UPSTREAM_OUTPUT_NOT_OBSERVABLE",
    })

    common = {
        "as_of": None,
        "observed_at": observed_at,
        "canonical_source_commit": args.source_commit,
        "upstream_workflow": args.upstream_workflow,
        "upstream_run_id": upstream_run_id,
        "upstream_run_attempt": args.upstream_run_attempt,
        "upstream_conclusion": args.upstream_conclusion,
        "market_data_watermark": None,
        "position_continuity_confirmed_through": None,
        "candidate_watermark": None,
        "real": {"position_count": None, "total_assets": None, "snapshot_id": None},
        "simulation": {"position_count": None, "total_assets": None, "snapshot_id": None},
        "candidate": {},
        "blockers": blockers,
        "diagnostic": {
            "fallback_mode": "MINIMAL_FAIL_CLOSED_EVIDENCE",
            "normal_build_error": build_error,
        },
        "operating_activation": False,
        "orders": 0,
        "trade_authority": "NONE",
    }
    status_rel = PRODUCTS / "STATUS_CURRENT.json"
    daily_rel = PRODUCTS / "DAILY_CURRENT.json"
    status_product = {"product_id": "P0_I1_STATUS_OBSERVATION", "status": "OBSERVATION_BLOCKED", **common}
    daily_product = {
        "product_id": "P0_I1_DAILY_OBSERVATION",
        "status": "OBSERVATION_BLOCKED",
        "material_state_changes": [],
        "action_gate": "NO_LIVE_ACTION",
        **common,
    }
    write_json(output / status_rel, status_product)
    write_json(output / daily_rel, daily_product)

    report_ids: dict[str, str] = {}
    report_paths: list[str] = []
    for report_type, product_rel in (("STATUS", status_rel), ("DAILY", daily_rel)):
        payload = {
            "report_type": report_type,
            "period_start": None,
            "period_end": None,
            "generated_at": observed_at,
            "canonical_commit_sha": args.source_commit,
            "market_data_watermark": None,
            "position_watermark": None,
            "candidate_watermark": None,
            "input_assets": [],
            "output_asset": str(product_rel),
            "exceptions": blockers,
            "publication_status": "BLOCKED",
            "diagnostic": {"fallback_mode": True},
            "operating_activation": False,
            "orders": 0,
            "trade_authority": "NONE",
        }
        payload["report_id"] = stable_id(report_type, payload)
        rel = PROD / "REPORT_MANIFESTS" / f"{report_type}_UNKNOWN_{token}_FALLBACK.json"
        write_json(output / rel, payload)
        report_ids[report_type] = payload["report_id"]
        report_paths.append(str(rel))

    run_manifest_rel = PROD / "RUN_MANIFESTS" / f"WP2R_{token}_FALLBACK.json"
    run_manifest: dict[str, Any] = {
        "workflow_name": args.upstream_workflow,
        "trigger_type": args.trigger_type,
        "started_at": args.upstream_started_at,
        "completed_at": args.upstream_completed_at,
        "observed_at": observed_at,
        "canonical_commit_before": args.source_commit,
        "canonical_commit_after": args.source_commit,
        "canonical_commit_semantics": "FAIL_CLOSED_OBSERVATION_SOURCE_COMMIT",
        "market_data_watermark": None,
        "position_watermark": None,
        "inputs": [],
        "outputs": sorted([str(status_rel), str(daily_rel), *report_paths]),
        "exceptions": blockers,
        "diagnostic": {
            "fallback_mode": "MINIMAL_FAIL_CLOSED_EVIDENCE",
            "normal_build_error": build_error,
        },
        "idempotency_key": f"{args.upstream_workflow}:{upstream_run_id}:{args.upstream_run_attempt}",
        "upstream_run_id": upstream_run_id,
        "upstream_run_attempt": args.upstream_run_attempt,
        "upstream_conclusion": args.upstream_conclusion,
        "upstream_run_url": args.upstream_run_url,
        "status": "FAIL",
        "orders": 0,
        "trade_authority": "NONE",
    }
    run_manifest["run_id"] = stable_id("RUN", run_manifest)
    write_json(output / run_manifest_rel, run_manifest)

    ledger_rel = PROD / "OPERATING_RUN_LEDGER_CURRENT.json"
    ledger_path = output / ledger_rel
    ledger_default = {
        "ledger_id": "P0_I1_OPERATING_RUN_LEDGER_V1",
        "status": "OBSERVATION_ACTIVE_NOT_PRODUCTION_ACCEPTED",
        "entries": [],
        "trade_authority": "NONE",
    }
    ledger = safe_json(ledger_path, ledger_default)
    if not isinstance(ledger, dict) or ledger.get("trade_authority") not in {None, "NONE"}:
        ledger = ledger_default
        blockers.append("EXISTING_LEDGER_UNREADABLE_OR_AUTHORITY_INVALID")
        blockers = sorted(set(blockers))

    entries = ledger.get("entries", [])
    if not isinstance(entries, list):
        entries = []
    entries = [row for row in entries if row.get("idempotency_key") != run_manifest["idempotency_key"]]
    entry = {
        "run_id": run_manifest["run_id"],
        "idempotency_key": run_manifest["idempotency_key"],
        "upstream_run_id": upstream_run_id,
        "upstream_run_attempt": args.upstream_run_attempt,
        "upstream_conclusion": args.upstream_conclusion,
        "observed_at": observed_at,
        "canonical_source_commit": args.source_commit,
        "market_data_watermark": None,
        "position_watermark": None,
        "snapshot_ids": {},
        "report_ids": report_ids,
        "run_manifest": str(run_manifest_rel),
        "status": "FAIL",
        "exceptions": blockers,
        "trade_authority": "NONE",
    }
    entries.append(entry)
    entries = sorted(entries, key=lambda row: (str(row.get("observed_at")), str(row.get("run_id"))))
    ledger.update({
        "status": "OBSERVATION_ACTIVE_NOT_PRODUCTION_ACCEPTED",
        "entries": entries,
        "run_count": len(entries),
        "success_count": sum(1 for row in entries if row.get("upstream_conclusion") == "success" and row.get("status") != "FAIL"),
        "failure_count": sum(1 for row in entries if row.get("status") == "FAIL" or row.get("upstream_conclusion") != "success"),
        "blocked_or_exception_count": sum(1 for row in entries if row.get("exceptions")),
        "duplicate_replaced_on_latest_build": False,
        "latest_run_id": run_manifest["run_id"],
        "latest_observed_at": observed_at,
        "missed_run_detection": "PARTIAL_REQUIRES_EXCHANGE_CALENDAR_INTEGRATION",
        "recovery_sla": "PENDING_R6_EVIDENCE",
        "operating_activation": False,
        "orders": 0,
        "trade_authority": "NONE",
    })
    write_json(ledger_path, ledger)

    summary = {
        "fallback": True,
        "run_manifest": str(run_manifest_rel),
        "ledger": str(ledger_rel),
        "snapshots": [],
        "reports": [str(status_rel), str(daily_rel)],
        "report_manifests": report_paths,
        "status": "FAIL",
        "exceptions": blockers,
        "orders": 0,
        "trade_authority": "NONE",
    }
    if args.summary_output:
        write_json(Path(args.summary_output), summary)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return summary


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-root", required=True)
    ap.add_argument("--upstream-workflow", required=True)
    ap.add_argument("--upstream-run-id", required=True)
    ap.add_argument("--upstream-run-attempt", type=int, default=1)
    ap.add_argument("--upstream-conclusion", required=True)
    ap.add_argument("--upstream-started-at", required=True)
    ap.add_argument("--upstream-completed-at", required=True)
    ap.add_argument("--upstream-run-url", default="")
    ap.add_argument("--source-commit", required=True)
    ap.add_argument("--trigger-type", required=True)
    ap.add_argument("--observed-at")
    ap.add_argument("--error-file")
    ap.add_argument("--summary-output")
    return ap


if __name__ == "__main__":
    build(parser().parse_args())
