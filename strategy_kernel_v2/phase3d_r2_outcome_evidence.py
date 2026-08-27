"""Phase 3D-R2 Outcome Evidence Acquisition.

Acquire only the frozen calendar, unadjusted close, and corporate-action-status
inputs needed by the accepted Round 1 measurability contract. This module does
not calculate returns, edge spreads, concordance, PnL, or any performance metric.
"""
from __future__ import annotations

from datetime import date, datetime, time
import hashlib
import json
from pathlib import Path
import time as time_module
from typing import Any, Callable, Mapping
from zoneinfo import ZoneInfo

import akshare as ak
import pandas as pd

from scripts.benchmark_historical_sources import normalize_history, prefixed_symbol, timed_call
from strategy_kernel_v2.phase3d_r2_measurability import build_measurability_audit

ROOT = Path(__file__).resolve().parent
CONTRACT_FILE = ROOT / "PHASE3D_R2_OUTCOME_EVIDENCE_ACQUISITION_CONTRACT.json"
OUTPUT_FILE = ROOT / "generated/PHASE3D_R2_OUTCOME_EVIDENCE_LEDGER.json"
FROZEN_PACK_FILE = ROOT / "PHASE3D_R2_OUTCOME_EVIDENCE_FROZEN_COMPACT.json"
BUSINESS_TZ = ZoneInfo("Asia/Shanghai")

CONTROLS = {
    "return_calculation_count": 0,
    "edge_spread_calculation_count": 0,
    "concordance_calculation_count": 0,
    "performance_metric_count": 0,
    "portfolio_pnl_count": 0,
    "model_mutation_count": 0,
    "dominance_relation_mutation_count": 0,
    "result_based_drop_count": 0,
    "orders": 0,
    "trade_authority": "NONE",
}


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def load_contract(path: str | Path = CONTRACT_FILE) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_contract(contract: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if contract.get("status") != "FROZEN_BEFORE_R2_RETURN_OR_PERFORMANCE_CALCULATION":
        errors.append("R2_OUTCOME_EVIDENCE_CONTRACT_NOT_FROZEN")
    parent = contract.get("parent_round1", {})
    if parent.get("final_head") != "bfa6afe2bc0c7a349d82a7a91afe54daea82724c":
        errors.append("R2_OUTCOME_EVIDENCE_PARENT_HEAD_DRIFT")
    if parent.get("round1_status") != "PARTIAL_R2_MEASURABILITY_OUTCOME_EVIDENCE_ACQUISITION_REQUIRED":
        errors.append("R2_OUTCOME_EVIDENCE_PARENT_STATUS_DRIFT")
    if parent.get("frozen_dominance_edge_count") != 54:
        errors.append("R2_OUTCOME_EVIDENCE_EDGE_COUNT_DRIFT")
    if parent.get("required_edge_endpoint_instances") != 55:
        errors.append("R2_OUTCOME_EVIDENCE_ENDPOINT_COUNT_DRIFT")
    calendar = contract.get("calendar_policy", {})
    if calendar.get("settled_publication_cutoff_local") != "15:30:00":
        errors.append("R2_OUTCOME_EVIDENCE_SETTLED_CUTOFF_DRIFT")
    if calendar.get("fixed_horizon_sessions") != [1, 3, 5]:
        errors.append("R2_OUTCOME_EVIDENCE_HORIZON_DRIFT")
    price = contract.get("price_source_policy", {})
    if price.get("price_semantics") != "UNADJUSTED_LOCAL_CURRENCY_CLOSE":
        errors.append("R2_OUTCOME_EVIDENCE_PRICE_SEMANTICS_DRIFT")
    if price.get("provider_series_mixing_allowed") is not False:
        errors.append("R2_OUTCOME_EVIDENCE_PROVIDER_MIXING_OPEN")
    if price.get("qfq_companion_may_be_used_as_outcome_close") is not False:
        errors.append("R2_OUTCOME_EVIDENCE_QFQ_OUTCOME_OPEN")
    runtime = contract.get("acquisition_runtime_policy", {})
    if runtime.get("per_call_attempts") != 2:
        errors.append("R2_OUTCOME_EVIDENCE_ATTEMPT_COUNT_DRIFT")
    if runtime.get("per_attempt_timeout_seconds") != 15:
        errors.append("R2_OUTCOME_EVIDENCE_TIMEOUT_DRIFT")
    if runtime.get("retry_backoff_seconds") != 1.0:
        errors.append("R2_OUTCOME_EVIDENCE_BACKOFF_DRIFT")
    ca = contract.get("corporate_action_status_policy", {})
    if ca.get("unresolved_blocks_performance") is not True:
        errors.append("R2_OUTCOME_EVIDENCE_UNRESOLVED_CA_NOT_BLOCKING")
    controls = contract.get("acquisition_only_controls", {})
    for key in (
        "return_calculation_allowed",
        "edge_spread_calculation_allowed",
        "concordance_calculation_allowed",
        "performance_summary_allowed",
        "model_mutation_allowed",
        "dominance_relation_mutation_allowed",
        "candidate_membership_mutation_allowed",
        "portfolio_mutation_allowed",
    ):
        if controls.get(key) is not False:
            errors.append("R2_OUTCOME_EVIDENCE_FORBIDDEN_CONTROL_OPEN:" + key)
    if controls.get("orders") != 0 or controls.get("trade_authority") != "NONE":
        errors.append("R2_OUTCOME_EVIDENCE_AUTHORITY_DRIFT")
    if contract.get("phase_boundary", {}).get("phase4_entry_allowed") is not False:
        errors.append("R2_OUTCOME_EVIDENCE_PREMATURE_PHASE4")
    return errors


def normalize_calendar(frame: pd.DataFrame) -> list[str]:
    if frame is None or not isinstance(frame, pd.DataFrame) or frame.empty:
        raise ValueError("TRADING_CALENDAR_EMPTY")
    column = next((name for name in ("trade_date", "交易日", "date") if name in frame.columns), None)
    if column is None:
        raise ValueError("TRADING_CALENDAR_DATE_COLUMN_MISSING")
    dates = pd.to_datetime(frame[column], errors="coerce").dropna().dt.date
    return sorted({item.isoformat() for item in dates})


def derive_observation_dates(
    checkpoint_at: str,
    calendar_dates: list[str],
    *,
    settled_cutoff: str = "15:30:00",
) -> dict[str, Any]:
    checkpoint = datetime.fromisoformat(checkpoint_at).astimezone(BUSINESS_TZ)
    cutoff = time.fromisoformat(settled_cutoff)
    sessions = [date.fromisoformat(item) for item in calendar_dates]
    local_date = checkpoint.date()
    if local_date in sessions and checkpoint.time() >= cutoff:
        entry_candidates = [item for item in sessions if item <= local_date]
    else:
        entry_candidates = [item for item in sessions if item < local_date]
    if not entry_candidates:
        raise ValueError("NO_SETTLED_ENTRY_SESSION:" + checkpoint_at)
    entry = entry_candidates[-1]
    future = [item for item in sessions if item > local_date]
    if len(future) < 5:
        raise ValueError("INSUFFICIENT_FUTURE_SESSIONS:" + checkpoint_at)
    return {
        "entry_date": entry.isoformat(),
        "horizon_1_date": future[0].isoformat(),
        "horizon_3_date": future[2].isoformat(),
        "horizon_5_date": future[4].isoformat(),
    }


def _fetch_frame(
    call: Callable[[], pd.DataFrame],
    *,
    attempts: int,
    timeout_seconds: int,
    backoff_seconds: float,
) -> tuple[pd.DataFrame | None, list[str]]:
    errors: list[str] = []
    for attempt in range(1, attempts + 1):
        try:
            frame, _latency = timed_call(call, timeout_seconds)
            normalized, _ = normalize_history(frame)
            if normalized.empty:
                raise ValueError("NORMALIZED_HISTORY_EMPTY")
            normalized["date"] = pd.to_datetime(normalized["date"]).dt.date.astype(str)
            return normalized, errors
        except Exception as exc:
            errors.append(f"attempt_{attempt}:{type(exc).__name__}:{str(exc)[:400]}")
            if attempt < attempts:
                time_module.sleep(backoff_seconds * attempt)
    return None, errors


def _provider_series(
    symbol: str,
    start_date: str,
    end_date: str,
    provider_id: str,
    *,
    attempts: int,
    timeout_seconds: int,
    backoff_seconds: float,
) -> dict[str, Any]:
    code = symbol.split(".")[0]
    start = start_date.replace("-", "")
    end = end_date.replace("-", "")
    if provider_id == "sina_daily":
        raw_call = lambda: ak.stock_zh_a_daily(
            symbol=prefixed_symbol(symbol), start_date=start, end_date=end, adjust=""
        )
        qfq_call = lambda: ak.stock_zh_a_daily(
            symbol=prefixed_symbol(symbol), start_date=start, end_date=end, adjust="qfq"
        )
        source_function = "stock_zh_a_daily"
    elif provider_id == "eastmoney_hist":
        raw_call = lambda: ak.stock_zh_a_hist(
            symbol=code, period="daily", start_date=start, end_date=end, adjust=""
        )
        qfq_call = lambda: ak.stock_zh_a_hist(
            symbol=code, period="daily", start_date=start, end_date=end, adjust="qfq"
        )
        source_function = "stock_zh_a_hist"
    else:
        raise ValueError("UNKNOWN_PROVIDER:" + provider_id)

    raw, raw_errors = _fetch_frame(
        raw_call,
        attempts=attempts,
        timeout_seconds=timeout_seconds,
        backoff_seconds=backoff_seconds,
    )
    qfq, qfq_errors = _fetch_frame(
        qfq_call,
        attempts=attempts,
        timeout_seconds=timeout_seconds,
        backoff_seconds=backoff_seconds,
    )
    def closes(frame: pd.DataFrame | None) -> dict[str, float]:
        if frame is None:
            return {}
        return {str(row["date"]): float(row["close"]) for _, row in frame.iterrows()}
    raw_closes = closes(raw)
    qfq_closes = closes(qfq)
    payload = {
        "provider_id": provider_id,
        "source_function": source_function,
        "raw_adjustment_mode": "UNADJUSTED",
        "qfq_adjustment_mode": "QFQ_SUPPORT_ONLY",
        "raw_closes": raw_closes,
        "qfq_closes": qfq_closes,
        "raw_errors": raw_errors,
        "qfq_errors": qfq_errors,
    }
    payload["series_sha256"] = _sha256(payload)
    return payload


def _reconcile(
    left: Mapping[str, float],
    right: Mapping[str, float],
    required_dates: list[str],
    *,
    abs_tol: float,
    rel_tol: float,
) -> dict[str, Any]:
    disagreements: list[dict[str, Any]] = []
    common = 0
    for d in required_dates:
        if d not in left or d not in right:
            continue
        common += 1
        a, b = float(left[d]), float(right[d])
        tol = max(abs_tol, max(abs(a), abs(b)) * rel_tol)
        if abs(a - b) > tol:
            disagreements.append({"date": d, "left": a, "right": b, "tolerance": tol})
    return {
        "common_required_dates": common,
        "disagreement_count": len(disagreements),
        "disagreements": disagreements,
        "passed": len(disagreements) == 0,
    }


def corporate_action_status(
    raw_closes: Mapping[str, float],
    qfq_closes: Mapping[str, float],
    window_dates: list[str],
    *,
    relative_range_tolerance: float,
) -> dict[str, Any]:
    factors: list[tuple[str, float]] = []
    for d in window_dates:
        raw = raw_closes.get(d)
        qfq = qfq_closes.get(d)
        if raw is None or qfq is None or raw <= 0 or qfq <= 0:
            continue
        factors.append((d, float(qfq) / float(raw)))
    if len(factors) != len(window_dates):
        return {
            "status": "CORPORATE_ACTION_STATUS_UNRESOLVED",
            "factor_observations": factors,
            "factor_relative_range": None,
        }
    values = [v for _, v in factors]
    rel_range = 0.0 if min(values) == 0 else max(values) / min(values) - 1.0
    status = (
        "NO_ADJUSTMENT_FACTOR_CHANGE_OBSERVED"
        if rel_range <= relative_range_tolerance
        else "ADJUSTMENT_FACTOR_CHANGE_OBSERVED"
    )
    return {
        "status": status,
        "factor_observations": factors,
        "factor_relative_range": rel_range,
    }


def _edge_population(audit: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [dict(row) for row in audit["frozen_edge_population"]]


def build_outcome_evidence_ledger() -> dict[str, Any]:
    contract = load_contract()
    contract_errors = validate_contract(contract)
    if contract_errors:
        raise ValueError("INVALID_OUTCOME_EVIDENCE_CONTRACT:" + ";".join(contract_errors))

    audit = build_measurability_audit()
    parent = contract["parent_round1"]
    integrity_errors: list[str] = []
    if audit["audit_sha256"] != parent["audit_sha256"]:
        integrity_errors.append("ROUND1_AUDIT_SHA_DRIFT")
    edges = _edge_population(audit)
    if len(edges) != parent["frozen_dominance_edge_count"]:
        integrity_errors.append("EDGE_POPULATION_COUNT_DRIFT")

    retrieved_at = datetime.now(tz=BUSINESS_TZ).isoformat(timespec="seconds")
    calendar_frame = ak.tool_trade_date_hist_sina()
    calendar_dates = normalize_calendar(calendar_frame)
    calendar_payload = {
        "provider_id": "sina_public",
        "source_function": "tool_trade_date_hist_sina",
        "retrieved_at": retrieved_at,
        "dates": calendar_dates,
    }
    calendar_payload["calendar_sha256"] = _sha256(calendar_payload)

    endpoint_map: dict[tuple[str, str], dict[str, Any]] = {}
    checkpoint_at_map: dict[str, str] = {}
    for edge in edges:
        checkpoint_at_map[edge["checkpoint_id"]] = edge["checkpoint_at"]
        for sid_key in ("dominator_security_id", "dominated_security_id"):
            sid = edge[sid_key]
            key = (edge["checkpoint_id"], sid)
            if key not in endpoint_map:
                dates = derive_observation_dates(
                    edge["checkpoint_at"],
                    calendar_dates,
                    settled_cutoff=contract["calendar_policy"]["settled_publication_cutoff_local"],
                )
                endpoint_map[key] = {
                    "checkpoint_id": edge["checkpoint_id"],
                    "checkpoint_at": edge["checkpoint_at"],
                    "security_id": sid,
                    **dates,
                }

    required_dates_by_security: dict[str, set[str]] = {}
    for row in endpoint_map.values():
        required_dates_by_security.setdefault(row["security_id"], set()).update([
            row["entry_date"], row["horizon_1_date"], row["horizon_3_date"], row["horizon_5_date"]
        ])
    all_required_dates = sorted({d for ds in required_dates_by_security.values() for d in ds})
    fetch_start = min(all_required_dates)
    fetch_end = max(all_required_dates)

    runtime_policy = contract["acquisition_runtime_policy"]
    provider_payloads: dict[str, dict[str, Any]] = {}
    for sid in sorted(required_dates_by_security):
        provider_payloads[sid] = {}
        for provider_id in ("sina_daily", "eastmoney_hist"):
            provider_payloads[sid][provider_id] = _provider_series(
                sid,
                fetch_start,
                fetch_end,
                provider_id,
                attempts=int(runtime_policy["per_call_attempts"]),
                timeout_seconds=int(runtime_policy["per_attempt_timeout_seconds"]),
                backoff_seconds=float(runtime_policy["retry_backoff_seconds"]),
            )

    price_policy = contract["price_source_policy"]
    ca_policy = contract["corporate_action_status_policy"]
    endpoint_rows: list[dict[str, Any]] = []
    endpoint_ready: dict[tuple[str, str], bool] = {}

    for key in sorted(endpoint_map):
        base = endpoint_map[key]
        sid = base["security_id"]
        required_dates = [
            base["entry_date"], base["horizon_1_date"], base["horizon_3_date"], base["horizon_5_date"]
        ]
        selected_provider = None
        for provider_id in ("sina_daily", "eastmoney_hist"):
            payload = provider_payloads[sid][provider_id]
            if all(d in payload["raw_closes"] and d in payload["qfq_closes"] for d in required_dates):
                selected_provider = provider_id
                break

        support = None
        if selected_provider:
            support = "eastmoney_hist" if selected_provider == "sina_daily" else "sina_daily"
        reconciliation = None
        if selected_provider and support:
            selected_payload = provider_payloads[sid][selected_provider]
            support_payload = provider_payloads[sid][support]
            reconciliation = _reconcile(
                selected_payload["raw_closes"],
                support_payload["raw_closes"],
                required_dates,
                abs_tol=float(price_policy["support_reconciliation"]["absolute_tolerance_cny"]),
                rel_tol=float(price_policy["support_reconciliation"]["relative_tolerance"]),
            )
        selected_payload = provider_payloads[sid][selected_provider] if selected_provider else None
        window_dates = [
            d for d in calendar_dates
            if base["entry_date"] <= d <= base["horizon_5_date"]
        ]
        ca = (
            corporate_action_status(
                selected_payload["raw_closes"],
                selected_payload["qfq_closes"],
                window_dates,
                relative_range_tolerance=float(ca_policy["factor_relative_range_tolerance"]),
            )
            if selected_payload
            else {
                "status": "CORPORATE_ACTION_STATUS_UNRESOLVED",
                "factor_observations": [],
                "factor_relative_range": None,
            }
        )
        close_values = {
            "entry_close": selected_payload["raw_closes"].get(base["entry_date"]) if selected_payload else None,
            "horizon_1_close": selected_payload["raw_closes"].get(base["horizon_1_date"]) if selected_payload else None,
            "horizon_3_close": selected_payload["raw_closes"].get(base["horizon_3_date"]) if selected_payload else None,
            "horizon_5_close": selected_payload["raw_closes"].get(base["horizon_5_date"]) if selected_payload else None,
        }
        support_disagreement = bool(
            reconciliation
            and reconciliation["common_required_dates"] == len(required_dates)
            and not reconciliation["passed"]
        )
        complete = (
            selected_provider is not None
            and all(value is not None for value in close_values.values())
            and ca["status"] != "CORPORATE_ACTION_STATUS_UNRESOLVED"
            and not support_disagreement
        )
        endpoint_ready[key] = complete
        endpoint_rows.append({
            **base,
            **close_values,
            "selected_provider_id": selected_provider,
            "support_provider_id": support if selected_provider else None,
            "support_reconciliation": reconciliation,
            "corporate_action_status": ca,
            "evidence_complete": complete,
        })

    complete_edges = 0
    edge_rows: list[dict[str, Any]] = []
    for edge in edges:
        dom_key = (edge["checkpoint_id"], edge["dominator_security_id"])
        sub_key = (edge["checkpoint_id"], edge["dominated_security_id"])
        complete = endpoint_ready.get(dom_key, False) and endpoint_ready.get(sub_key, False)
        complete_edges += int(complete)
        edge_rows.append({**edge, "evidence_complete": complete})

    required_edges = int(parent["frozen_dominance_edge_count"])
    if integrity_errors:
        status = contract["classification"]["fail_status"]
    elif complete_edges == required_edges:
        status = contract["classification"]["pass_status"]
    else:
        status = contract["classification"]["partial_status"]

    result = {
        "schema_version": "1.0.0",
        "phase": "PHASE_3D_R2",
        "subphase": "OUTCOME_EVIDENCE_ACQUISITION",
        "status": status,
        "retrieved_at": retrieved_at,
        "parent_round1_audit_sha256": audit["audit_sha256"],
        "frozen_dominance_edge_count": len(edges),
        "required_edge_endpoint_instances": len(endpoint_rows),
        "required_security_count": len(required_dates_by_security),
        "required_security_ids": sorted(required_dates_by_security),
        "fetch_start_date": fetch_start,
        "fetch_end_date": fetch_end,
        "calendar": calendar_payload,
        "provider_series": provider_payloads,
        "endpoint_evidence": endpoint_rows,
        "edge_evidence": edge_rows,
        "complete_endpoint_count": sum(bool(row["evidence_complete"]) for row in endpoint_rows),
        "incomplete_endpoint_count": sum(not bool(row["evidence_complete"]) for row in endpoint_rows),
        "complete_evidence_edge_count": complete_edges,
        "incomplete_evidence_edge_count": required_edges - complete_edges,
        "performance_calculation_authorized": complete_edges == required_edges and not integrity_errors,
        "return_calculation_count": 0,
        "performance_metric_count": 0,
        "integrity_errors": integrity_errors,
        "controls": dict(CONTROLS),
        "phase3d_r2_performance_started": False,
        "phase3d_r2_complete": False,
        "phase3e_r2_started": False,
        "repeat_phase3f_started": False,
        "phase3_historical_validation_complete": False,
        "phase4_entry_allowed": False,
    }
    result["ledger_sha256"] = _sha256({k: v for k, v in result.items() if k != "ledger_sha256"})
    return result


def write_default(result: Mapping[str, Any], path: str | Path = OUTPUT_FILE) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


if __name__ == "__main__":
    result = build_outcome_evidence_ledger()
    path = write_default(result)
    print(
        "PHASE3D_R2_OUTCOME_EVIDENCE_RESULT "
        f"status={result['status']} endpoints={result['required_edge_endpoint_instances']} "
        f"complete_endpoints={result['complete_endpoint_count']} "
        f"edges={result['frozen_dominance_edge_count']} "
        f"complete_edges={result['complete_evidence_edge_count']} "
        f"performance_authorized={str(result['performance_calculation_authorized']).lower()} "
        "returns=0 performance=0 phase4_entry_allowed=false orders=0 trade_authority=NONE "
        f"sha256={result['ledger_sha256']} path={path}"
    )


def load_frozen_pack(path: str | Path = FROZEN_PACK_FILE) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def edge_population_sha256(audit: Mapping[str, Any]) -> str:
    rows = [
        {
            "checkpoint_id": row["checkpoint_id"],
            "checkpoint_at": row["checkpoint_at"],
            "comparison_signature_sha256": row["comparison_signature_sha256"],
            "dominator_security_id": row["dominator_security_id"],
            "dominated_security_id": row["dominated_security_id"],
        }
        for row in audit["frozen_edge_population"]
    ]
    return _sha256(rows)


def validate_frozen_pack(pack: Mapping[str, Any], audit: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if pack.get("pack_id") != "PHASE3D_R2_OUTCOME_EVIDENCE_FROZEN_COMPACT_V1":
        errors.append("R2_OUTCOME_PACK_ID_DRIFT")
    if pack.get("status") != "PASS_R2_OUTCOME_EVIDENCE_READY_FOR_PERFORMANCE":
        errors.append("R2_OUTCOME_PACK_NOT_PASS")
    if pack.get("source_ledger_sha256") != "300db34b408e7ca2cfeb188b8c6177b62bdff70743a2cf6fb2c833bf3bda1d1b":
        errors.append("R2_OUTCOME_PACK_LEDGER_SHA_DRIFT")
    if pack.get("parent_round1_audit_sha256") != audit.get("audit_sha256"):
        errors.append("R2_OUTCOME_PACK_PARENT_AUDIT_DRIFT")
    if pack.get("holdout_replay_sha256") != audit.get("parent_holdout_replay_sha256"):
        errors.append("R2_OUTCOME_PACK_HOLDOUT_SHA_DRIFT")
    if pack.get("edge_population_sha256") != edge_population_sha256(audit):
        errors.append("R2_OUTCOME_PACK_EDGE_POPULATION_DRIFT")
    if pack.get("frozen_dominance_edge_count") != 54:
        errors.append("R2_OUTCOME_PACK_EDGE_COUNT_DRIFT")
    if pack.get("required_edge_endpoint_instances") != 55 or pack.get("complete_endpoint_count") != 55:
        errors.append("R2_OUTCOME_PACK_ENDPOINT_COUNT_DRIFT")
    if pack.get("complete_evidence_edge_count") != 54:
        errors.append("R2_OUTCOME_PACK_COMPLETE_EDGE_DRIFT")

    calendar = pack.get("calendar", {})
    if calendar.get("settled_publication_cutoff_local") != "15:30:00":
        errors.append("R2_OUTCOME_PACK_CUTOFF_DRIFT")
    if calendar.get("fixed_horizon_sessions") != [1, 3, 5]:
        errors.append("R2_OUTCOME_PACK_HORIZON_DRIFT")

    expected_ids = {
        "000719.SZ", "002039.SZ", "301215.SZ",
        "600036.SH", "600941.SH", "601088.SH", "601985.SH",
    }
    security = pack.get("security_evidence", {})
    if set(security) != expected_ids:
        errors.append("R2_OUTCOME_PACK_SECURITY_SCOPE_DRIFT")

    endpoint_pairs = set()
    for edge in audit["frozen_edge_population"]:
        endpoint_pairs.add((edge["checkpoint_id"], edge["dominator_security_id"]))
        endpoint_pairs.add((edge["checkpoint_id"], edge["dominated_security_id"]))
    if len(endpoint_pairs) != 55:
        errors.append("R2_OUTCOME_PACK_REBUILT_ENDPOINT_COUNT_DRIFT")

    schedules = pack.get("checkpoint_observation_dates", {})
    for checkpoint_id, sid in sorted(endpoint_pairs):
        schedule = schedules.get(checkpoint_id)
        sec = security.get(sid)
        if not schedule:
            errors.append("R2_OUTCOME_PACK_MISSING_CHECKPOINT_SCHEDULE:" + checkpoint_id)
            continue
        if not sec:
            errors.append("R2_OUTCOME_PACK_MISSING_SECURITY:" + sid)
            continue
        closes = sec.get("required_closes", {})
        for key in ("entry_date", "horizon_1_date", "horizon_3_date", "horizon_5_date"):
            d = schedule.get(key)
            if d not in closes:
                errors.append("R2_OUTCOME_PACK_MISSING_CLOSE:" + checkpoint_id + ":" + sid + ":" + key)

    if sum(int(row.get("endpoint_count", 0)) for row in security.values()) != 55:
        errors.append("R2_OUTCOME_PACK_ENDPOINT_ACCOUNTING_DRIFT")
    for sid, row in security.items():
        if row.get("selected_provider_id") != "sina_daily":
            errors.append("R2_OUTCOME_PACK_PROVIDER_DRIFT:" + sid)
        if row.get("source_function") != "stock_zh_a_daily":
            errors.append("R2_OUTCOME_PACK_SOURCE_FUNCTION_DRIFT:" + sid)
        if row.get("corporate_action_status") != "NO_ADJUSTMENT_FACTOR_CHANGE_OBSERVED":
            errors.append("R2_OUTCOME_PACK_CA_STATUS_DRIFT:" + sid)
        if row.get("support_reconciliation_disagreement_count") != 0:
            errors.append("R2_OUTCOME_PACK_RECONCILIATION_DISAGREEMENT:" + sid)

    ca = pack.get("corporate_action_status_counts", {})
    if ca != {
        "NO_ADJUSTMENT_FACTOR_CHANGE_OBSERVED": 55,
        "ADJUSTMENT_FACTOR_CHANGE_OBSERVED": 0,
        "CORPORATE_ACTION_STATUS_UNRESOLVED": 0,
    }:
        errors.append("R2_OUTCOME_PACK_CA_ACCOUNTING_DRIFT")
    if pack.get("support_reconciliation_disagreement_endpoint_count") != 0:
        errors.append("R2_OUTCOME_PACK_SUPPORT_DISAGREEMENT_NONZERO")
    if pack.get("performance_calculation_authorized") is not True:
        errors.append("R2_OUTCOME_PACK_PERFORMANCE_GATE_NOT_OPEN")
    if pack.get("return_calculation_count") != 0 or pack.get("performance_metric_count") != 0:
        errors.append("R2_OUTCOME_PACK_PREMATURE_PERFORMANCE")
    if pack.get("phase4_entry_allowed") is not False:
        errors.append("R2_OUTCOME_PACK_PREMATURE_PHASE4")
    if pack.get("orders") != 0 or pack.get("trade_authority") != "NONE":
        errors.append("R2_OUTCOME_PACK_AUTHORITY_DRIFT")
    return errors
