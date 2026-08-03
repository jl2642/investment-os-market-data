#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CONTROL = Path("investment_os_runtime/00_CONTROL")
STATE = Path("investment_os_runtime/30_STATE_CURRENT")
PRODUCTS = Path("investment_os_runtime/50_OPERATING_PRODUCTS/OBSERVATION")
PROD = Path("investment_os_runtime/80_PRODUCTION_ACCEPTANCE/P0_I1")

REQUIRED_INPUTS = {
    "real": STATE / "10_REAL_ACCOUNT/REAL_ACCOUNT_POSITIONS_CURRENT.json",
    "simulation": STATE / "20_SIMULATION/SIMULATION_POSITIONS_CURRENT.json",
    "candidate": STATE / "40_CANDIDATE/CANDIDATE_CURRENT.json",
    "marks": STATE / "25_PORTFOLIO_MARKS/PORTFOLIO_MARKS_CURRENT.json",
    "delta": STATE / "15_PORTFOLIO_INPUT/USER_TRANSACTION_DELTA_LEDGER_CURRENT.json",
}


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


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def require_none_authority(label: str, payload: Any) -> None:
    values = authority_values(payload)
    if not values:
        raise ValueError(f"MISSING_TRADE_AUTHORITY:{label}")
    bad = [value for value in values if value != "NONE"]
    if bad:
        raise ValueError(f"TRADE_AUTHORITY_VIOLATION:{label}:{bad}")


def iso_date(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text[:10] if len(text) >= 10 else text


def account_position_watermark(payload: dict[str, Any]) -> str | None:
    values = sorted({str(row.get("position_source_as_of")) for row in payload.get("holdings", []) if row.get("position_source_as_of")})
    if not values:
        return iso_date(payload.get("as_of") or payload.get("position_watermark"))
    if len(values) == 1:
        return values[0]
    return f"MIXED:{values[0]}..{values[-1]}"


def numeric(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def candidate_counts(candidate: dict[str, Any]) -> dict[str, int]:
    counts = candidate.get("counts", {})
    lanes = {
        "candidate_core": "candidate_core_members",
        "research_queue": "research_queue_members",
        "shadow_track": "shadow_track_members",
        "ready_for_user_decision": "ready_for_user_decision_members",
    }
    out: dict[str, int] = {}
    for name, members_key in lanes.items():
        declared = counts.get(name)
        members = candidate.get(members_key, [])
        if not isinstance(members, list):
            raise ValueError(f"CANDIDATE_LANE_NOT_LIST:{members_key}")
        actual = len(members)
        if declared is not None and int(declared) != actual:
            raise ValueError(f"CANDIDATE_COUNT_MISMATCH:{name}:{declared}!={actual}")
        out[name] = actual
    return out


def snapshot_for_account(
    account: dict[str, Any],
    *,
    marks: dict[str, Any],
    delta: dict[str, Any],
    source_commit: str,
    upstream_run_id: str,
    observed_at: str,
    upstream_conclusion: str,
) -> dict[str, Any]:
    account_name = str(account.get("account") or "UNKNOWN")
    summary = account.get("summary", {})
    holdings = account.get("holdings", [])
    if not isinstance(holdings, list):
        raise ValueError(f"HOLDINGS_NOT_LIST:{account_name}")

    mark_watermark = iso_date(marks.get("data_watermark", {}).get("latest_mark_date"))
    continuity = iso_date(delta.get("continuity_confirmed_through"))
    position_watermark = account_position_watermark(account)
    execution_cash = numeric(summary.get("execution_cash_balance", summary.get("cash")))
    total_assets = numeric(summary.get("account_total_assets", summary.get("total_assets")))
    marked_value = round(sum(numeric(row.get("market_value")) or 0.0 for row in holdings), 8)
    tie_out = None if execution_cash is None or total_assets is None else round(total_assets - execution_cash - marked_value, 8)

    blockers: list[str] = []
    if upstream_conclusion != "success":
        blockers.append("UPSTREAM_WORKFLOW_NOT_SUCCESS")
    if marks.get("status") != "CURRENT_COMPLETE":
        blockers.append("MARKS_NOT_CURRENT_COMPLETE")
    if any(row.get("mark_freshness_status") != "FRESH" for row in holdings):
        blockers.append("ACCOUNT_CONTAINS_NON_FRESH_MARK")
    if mark_watermark and continuity and continuity < mark_watermark:
        blockers.append("POSITION_CONTINUITY_LAGS_MARK_WATERMARK")
    if tie_out is None:
        blockers.append("ASSET_TIE_OUT_INPUT_MISSING")
    elif abs(tie_out) > 0.01:
        blockers.append("ASSET_TIE_OUT_FAILED")
    blockers.extend(["CORPORATE_ACTIONS_NOT_UNIFIED", "INCOME_AND_FEES_NOT_UNIFIED"])

    if "UPSTREAM_WORKFLOW_NOT_SUCCESS" in blockers or "MARKS_NOT_CURRENT_COMPLETE" in blockers:
        quality = "BLOCKED_UPSTREAM_OR_MARKS"
    elif "ASSET_TIE_OUT_FAILED" in blockers or "ASSET_TIE_OUT_INPUT_MISSING" in blockers:
        quality = "BLOCKED_TIE_OUT"
    else:
        quality = "PROVISIONAL_INPUT_GAPS"

    position_rows = [
        {
            "security_id": row.get("security_id"),
            "security_name": row.get("security_name"),
            "asset_class": row.get("asset_class"),
            "quantity": row.get("quantity"),
            "available_quantity": row.get("available_quantity"),
            "cost_basis": row.get("cost_basis"),
            "unit_cost": row.get("unit_cost"),
            "mark": row.get("mark"),
            "mark_as_of": row.get("mark_as_of"),
            "market_value": row.get("market_value"),
            "unrealized_pnl": row.get("unrealized_pnl"),
            "mark_freshness_status": row.get("mark_freshness_status"),
        }
        for row in holdings
    ]

    payload: dict[str, Any] = {
        "account": account_name,
        "as_of": mark_watermark,
        "canonical_source_commit": source_commit,
        "observed_at": observed_at,
        "upstream_run_id": upstream_run_id,
        "positions": position_rows,
        "position_count": len(position_rows),
        "execution_cash": execution_cash,
        "external_flows": {
            "status": "CURRENT_DELTA_LEDGER_READ",
            "applied_delta_count": delta.get("applied_delta_count"),
            "pending_user_confirmation_count": delta.get("pending_user_confirmation_count"),
            "continuity_confirmed_through": delta.get("continuity_confirmed_through"),
        },
        "income_and_fees": {"status": "NOT_UNIFIED", "amount": None},
        "corporate_actions": {"status": "NOT_UNIFIED", "items": []},
        "market_data_watermark": mark_watermark,
        "position_watermark": position_watermark,
        "total_assets": total_assets,
        "marked_position_value": marked_value,
        "tie_out_difference": tie_out,
        "quality_status": quality,
        "blockers": sorted(set(blockers)),
        "orders": 0,
        "trade_authority": "NONE",
    }
    payload["snapshot_id"] = stable_id("EODSNAP", payload)
    return payload


def report_payload(
    report_type: str,
    *,
    mark_watermark: str | None,
    position_watermark: str | None,
    candidate_watermark: str | None,
    source_commit: str,
    observed_at: str,
    inputs: list[str],
    blockers: list[str],
    product_path: str,
) -> dict[str, Any]:
    publication_status = "PROVISIONAL" if not any(item.startswith("UPSTREAM_") or "TIE_OUT_FAILED" in item for item in blockers) else "BLOCKED"
    payload: dict[str, Any] = {
        "report_type": report_type,
        "period_start": mark_watermark,
        "period_end": mark_watermark,
        "generated_at": observed_at,
        "canonical_commit_sha": source_commit,
        "market_data_watermark": mark_watermark,
        "position_watermark": position_watermark,
        "candidate_watermark": candidate_watermark,
        "input_assets": sorted(inputs),
        "output_asset": product_path,
        "exceptions": sorted(set(blockers)),
        "publication_status": publication_status,
        "operating_activation": False,
        "orders": 0,
        "trade_authority": "NONE",
    }
    payload["report_id"] = stable_id(report_type, payload)
    return payload


def build(args: argparse.Namespace) -> dict[str, Any]:
    repo = Path(args.repo_root).resolve()
    output = Path(args.output_root).resolve() if args.output_root else repo
    inputs = {name: repo / path for name, path in REQUIRED_INPUTS.items()}
    missing = [str(path.relative_to(repo)) for path in inputs.values() if not path.exists()]
    if missing:
        raise FileNotFoundError("MISSING_INPUTS:" + ",".join(missing))

    real = read_json(inputs["real"])
    simulation = read_json(inputs["simulation"])
    candidate = read_json(inputs["candidate"])
    marks = read_json(inputs["marks"])
    delta = read_json(inputs["delta"])
    for label, payload in [("real", real), ("simulation", simulation), ("candidate", candidate), ("marks", marks), ("delta", delta)]:
        require_none_authority(label, payload)

    cand_counts = candidate_counts(candidate)
    observed_at = args.observed_at or datetime.now(timezone.utc).isoformat()
    mark_watermark = iso_date(marks.get("data_watermark", {}).get("latest_mark_date"))
    candidate_watermark = str(candidate.get("as_of") or candidate.get("accepted_at") or candidate.get("current_operating_stage") or "UNKNOWN")
    upstream_run_id = str(args.upstream_run_id)
    token = f"{upstream_run_id}_a{args.upstream_run_attempt}"

    snapshots: dict[str, dict[str, Any]] = {}
    if args.upstream_conclusion == "success":
        for payload in (real, simulation):
            snap = snapshot_for_account(
                payload,
                marks=marks,
                delta=delta,
                source_commit=args.source_commit,
                upstream_run_id=upstream_run_id,
                observed_at=observed_at,
                upstream_conclusion=args.upstream_conclusion,
            )
            snapshots[snap["account"]] = snap

    all_blockers = sorted({item for snap in snapshots.values() for item in snap.get("blockers", [])})
    if args.upstream_conclusion != "success":
        all_blockers.append("UPSTREAM_WORKFLOW_NOT_SUCCESS")
    if not snapshots:
        all_blockers.append("NO_EOD_SNAPSHOT_CREATED")
    all_blockers = sorted(set(all_blockers))

    status_product_rel = PRODUCTS / "STATUS_CURRENT.json"
    daily_product_rel = PRODUCTS / "DAILY_CURRENT.json"
    position_watermark = str(delta.get("continuity_confirmed_through") or "UNKNOWN")
    common = {
        "as_of": mark_watermark,
        "observed_at": observed_at,
        "canonical_source_commit": args.source_commit,
        "upstream_workflow": args.upstream_workflow,
        "upstream_run_id": upstream_run_id,
        "upstream_run_attempt": args.upstream_run_attempt,
        "upstream_conclusion": args.upstream_conclusion,
        "market_data_watermark": mark_watermark,
        "position_continuity_confirmed_through": delta.get("continuity_confirmed_through"),
        "candidate_watermark": candidate_watermark,
        "real": {
            "position_count": len(real.get("holdings", [])),
            "total_assets": real.get("summary", {}).get("account_total_assets"),
            "snapshot_id": snapshots.get("REAL", {}).get("snapshot_id"),
        },
        "simulation": {
            "position_count": len(simulation.get("holdings", [])),
            "total_assets": simulation.get("summary", {}).get("account_total_assets"),
            "snapshot_id": snapshots.get("SIMULATION", {}).get("snapshot_id"),
        },
        "candidate": cand_counts,
        "blockers": all_blockers,
        "operating_activation": False,
        "orders": 0,
        "trade_authority": "NONE",
    }
    status_product = {"product_id": "P0_I1_STATUS_OBSERVATION", "status": "OBSERVATION_PROVISIONAL" if args.upstream_conclusion == "success" else "OBSERVATION_BLOCKED", **common}
    daily_product = {"product_id": "P0_I1_DAILY_OBSERVATION", "status": status_product["status"], "material_state_changes": [], "action_gate": "NO_LIVE_ACTION", **common}

    input_paths = [str(path) for path in REQUIRED_INPUTS.values()]
    status_manifest = report_payload(
        "STATUS",
        mark_watermark=mark_watermark,
        position_watermark=position_watermark,
        candidate_watermark=candidate_watermark,
        source_commit=args.source_commit,
        observed_at=observed_at,
        inputs=input_paths,
        blockers=all_blockers,
        product_path=str(status_product_rel),
    )
    daily_manifest = report_payload(
        "DAILY",
        mark_watermark=mark_watermark,
        position_watermark=position_watermark,
        candidate_watermark=candidate_watermark,
        source_commit=args.source_commit,
        observed_at=observed_at,
        inputs=input_paths,
        blockers=all_blockers,
        product_path=str(daily_product_rel),
    )

    run_status = "FAIL" if args.upstream_conclusion != "success" else ("PASS_WITH_EXCEPTIONS" if all_blockers else "PASS")
    snapshot_outputs: list[str] = []
    for account_name, snapshot in snapshots.items():
        rel = PROD / "EOD_SNAPSHOTS" / str(mark_watermark or "UNKNOWN") / f"{account_name}_{token}.json"
        write_json(output / rel, snapshot)
        snapshot_outputs.append(str(rel))

    report_manifest_rels = [
        PROD / "REPORT_MANIFESTS" / f"STATUS_{str(mark_watermark or 'UNKNOWN')}_{token}.json",
        PROD / "REPORT_MANIFESTS" / f"DAILY_{str(mark_watermark or 'UNKNOWN')}_{token}.json",
    ]
    write_json(output / status_product_rel, status_product)
    write_json(output / daily_product_rel, daily_product)
    write_json(output / report_manifest_rels[0], status_manifest)
    write_json(output / report_manifest_rels[1], daily_manifest)

    run_manifest_rel = PROD / "RUN_MANIFESTS" / f"WP2R_{token}.json"
    run_manifest: dict[str, Any] = {
        "workflow_name": args.upstream_workflow,
        "trigger_type": args.trigger_type,
        "started_at": args.upstream_started_at,
        "completed_at": args.upstream_completed_at,
        "observed_at": observed_at,
        "canonical_commit_before": args.source_commit,
        "canonical_commit_after": args.source_commit,
        "canonical_commit_semantics": "OBSERVED_UPSTREAM_OUTPUT_COMMIT_BEFORE_OBSERVER_EVIDENCE_COMMIT",
        "market_data_watermark": mark_watermark,
        "position_watermark": position_watermark,
        "inputs": sorted(input_paths),
        "outputs": sorted(snapshot_outputs + [str(status_product_rel), str(daily_product_rel)] + [str(path) for path in report_manifest_rels]),
        "exceptions": all_blockers,
        "idempotency_key": f"{args.upstream_workflow}:{upstream_run_id}:{args.upstream_run_attempt}",
        "upstream_run_id": upstream_run_id,
        "upstream_run_attempt": args.upstream_run_attempt,
        "upstream_conclusion": args.upstream_conclusion,
        "upstream_run_url": args.upstream_run_url,
        "status": run_status,
        "orders": 0,
        "trade_authority": "NONE",
    }
    run_manifest["run_id"] = stable_id("RUN", run_manifest)
    write_json(output / run_manifest_rel, run_manifest)

    ledger_rel = PROD / "OPERATING_RUN_LEDGER_CURRENT.json"
    ledger_path = output / ledger_rel
    ledger = read_json(ledger_path) if ledger_path.exists() else {
        "ledger_id": "P0_I1_OPERATING_RUN_LEDGER_V1",
        "status": "OBSERVATION_ACTIVE_NOT_PRODUCTION_ACCEPTED",
        "entries": [],
        "trade_authority": "NONE",
    }
    require_none_authority("existing_ledger", ledger)
    entries = [entry for entry in ledger.get("entries", []) if entry.get("idempotency_key") != run_manifest["idempotency_key"]]
    duplicate_replaced = len(entries) != len(ledger.get("entries", []))
    entry = {
        "run_id": run_manifest["run_id"],
        "idempotency_key": run_manifest["idempotency_key"],
        "upstream_run_id": upstream_run_id,
        "upstream_run_attempt": args.upstream_run_attempt,
        "upstream_conclusion": args.upstream_conclusion,
        "observed_at": observed_at,
        "canonical_source_commit": args.source_commit,
        "market_data_watermark": mark_watermark,
        "position_watermark": position_watermark,
        "snapshot_ids": {name: row["snapshot_id"] for name, row in snapshots.items()},
        "report_ids": {"STATUS": status_manifest["report_id"], "DAILY": daily_manifest["report_id"]},
        "run_manifest": str(run_manifest_rel),
        "status": run_status,
        "exceptions": all_blockers,
        "trade_authority": "NONE",
    }
    entries.append(entry)
    entries = sorted(entries, key=lambda row: (str(row.get("observed_at")), str(row.get("run_id"))))
    ledger.update({
        "status": "OBSERVATION_ACTIVE_NOT_PRODUCTION_ACCEPTED",
        "entries": entries,
        "run_count": len(entries),
        "success_count": sum(1 for row in entries if row.get("upstream_conclusion") == "success"),
        "failure_count": sum(1 for row in entries if row.get("upstream_conclusion") != "success"),
        "blocked_or_exception_count": sum(1 for row in entries if row.get("exceptions")),
        "duplicate_replaced_on_latest_build": duplicate_replaced,
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
        "run_manifest": str(run_manifest_rel),
        "ledger": str(ledger_rel),
        "snapshots": snapshot_outputs,
        "reports": [str(status_product_rel), str(daily_product_rel)],
        "report_manifests": [str(path) for path in report_manifest_rels],
        "status": run_status,
        "exceptions": all_blockers,
        "orders": 0,
        "trade_authority": "NONE",
    }
    if args.summary_output:
        write_json(Path(args.summary_output), summary)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return summary


def validate_output(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.output_root).resolve()
    prod = root / PROD
    ledger_path = prod / "OPERATING_RUN_LEDGER_CURRENT.json"
    if not ledger_path.exists():
        raise FileNotFoundError("MISSING_LEDGER")
    ledger = read_json(ledger_path)
    require_none_authority("ledger", ledger)
    if not ledger.get("entries"):
        raise ValueError("EMPTY_LEDGER")
    latest = ledger["entries"][-1]
    run_manifest_path = root / latest["run_manifest"]
    run_manifest = read_json(run_manifest_path)
    require_none_authority("run_manifest", run_manifest)
    if run_manifest.get("status") not in {"PASS", "PASS_WITH_EXCEPTIONS", "FAIL", "BLOCKED", "NO_OP"}:
        raise ValueError("INVALID_RUN_STATUS")
    for manifest_name in ("STATUS", "DAILY"):
        report_id = latest.get("report_ids", {}).get(manifest_name)
        if not report_id:
            raise ValueError(f"MISSING_REPORT_ID:{manifest_name}")
    for product in [root / PRODUCTS / "STATUS_CURRENT.json", root / PRODUCTS / "DAILY_CURRENT.json"]:
        payload = read_json(product)
        require_none_authority(product.name, payload)
        if payload.get("operating_activation") is not False or payload.get("orders") != 0:
            raise ValueError(f"PRODUCT_AUTHORITY_BOUNDARY:{product.name}")
    result = {
        "status": "PASS",
        "run_id": latest["run_id"],
        "run_count": ledger["run_count"],
        "orders": 0,
        "trade_authority": "NONE",
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return result


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="command", required=True)
    build_parser = sub.add_parser("build")
    build_parser.add_argument("--repo-root", default=".")
    build_parser.add_argument("--output-root")
    build_parser.add_argument("--upstream-workflow", required=True)
    build_parser.add_argument("--upstream-run-id", required=True)
    build_parser.add_argument("--upstream-run-attempt", type=int, default=1)
    build_parser.add_argument("--upstream-conclusion", required=True)
    build_parser.add_argument("--upstream-started-at", required=True)
    build_parser.add_argument("--upstream-completed-at", required=True)
    build_parser.add_argument("--upstream-run-url", default="")
    build_parser.add_argument("--source-commit", required=True)
    build_parser.add_argument("--trigger-type", choices=["workflow_run", "workflow_dispatch", "pull_request", "manual"], required=True)
    build_parser.add_argument("--observed-at")
    build_parser.add_argument("--summary-output")
    validate_parser = sub.add_parser("validate")
    validate_parser.add_argument("--output-root", required=True)
    return ap


def main() -> int:
    args = parser().parse_args()
    if args.command == "build":
        build(args)
        return 0
    validate_output(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
