from __future__ import annotations

import hashlib
import json
import math
import zipfile
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

VOLATILE_FIELDS = {"generated_at", "published_at", "created_at", "elapsed_seconds"}


def clean(value: Any) -> Any:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            value = value.item()
        except (AttributeError, ValueError):
            pass
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return round(value, 12)
    return value


def canonical(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): canonical(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [canonical(item) for item in value]
    if isinstance(value, set):
        return sorted(canonical(item) for item in value)
    return clean(value)


def stable_hash(payload: Any) -> str:
    text = json.dumps(canonical(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(canonical(payload), ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in sorted(records, key=lambda item: (item.get("symbol", ""), item.get("transition_id", ""))):
            handle.write(json.dumps(canonical(record), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    return records


def parse_json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value:
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []
    return []


def semantic_frame_hash(frame: pd.DataFrame, *, sort_by: Iterable[str] = ("symbol",)) -> str:
    clean_frame = frame.copy()
    clean_frame = clean_frame.drop(columns=[column for column in VOLATILE_FIELDS if column in clean_frame.columns], errors="ignore")
    available = [column for column in sort_by if column in clean_frame.columns]
    if available:
        clean_frame = clean_frame.sort_values(available, kind="stable")
    return stable_hash(clean_frame.to_dict(orient="records"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def deterministic_zip(source_root: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(item for item in source_root.rglob("*") if item.is_file()):
            relative = path.relative_to(source_root).as_posix()
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def route_for_symbol(symbol: str, cfg: dict[str, Any]) -> dict[str, Any]:
    routes = cfg["reentry_routes"]
    if symbol not in routes:
        raise KeyError(f"No FMDL-4C route for {symbol}")
    return routes[symbol]


def build_gate_results(route: dict[str, Any]) -> dict[str, str]:
    return {
        "EVIDENCE_BINDING": "PASS",
        "RESEARCH_GRADUATION": "PASS",
        "PUBLIC_SOURCE_BASELINE": "PASS",
        "RELEASE4_METADATA_IDENTITY": "PASS",
        "RELEASE4_BASE_BYTE_ACCESS": "PENDING_CONTROLLED_LIMITATION",
        "EXISTING_CANDIDATE_MEMBERSHIP_RECONCILIATION": "PENDING_BASE_CONTENT",
        "FOLLOW_ON_RESEARCH": f"PENDING:{route['required_follow_on']}",
        "OPEN_RESEARCH_GATES": "PENDING:" + ",".join(route["open_gates"]),
        "SIMULATION_ADMISSION": "BLOCKED",
        "REAL_ACCOUNT_RCM": "BLOCKED",
        "USER_CONFIRMATION": "NOT_REQUESTED",
    }


def build_transition(
    row: dict[str, Any],
    research: dict[str, Any],
    cfg: dict[str, Any],
    *,
    created_at: str,
    research_version: str,
) -> dict[str, Any]:
    symbol = str(row["symbol"])
    route = route_for_symbol(symbol, cfg)
    reason_codes = parse_json_list(row.get("decision_reason_codes_json")) + [
        "REENTRY_QUEUE_ONLY",
        "NO_CANDIDATE_SIMULATION_REAL_ACCOUNT_MUTATION",
    ]
    evidence_ids = parse_json_list(research.get("evidence_ids_json"))
    state_payload = {
        "symbol": symbol,
        "queue_state": route["queue_state"],
        "route_class": route["route_class"],
        "priority": route["priority"],
        "research_id": str(row["research_id"]),
    }
    from_state_hash = stable_hash({"symbol": symbol, "state": "NOT_PRESENT_IN_FMDL4C_OVERLAY"})
    to_state_hash = stable_hash(state_payload)
    base = {
        "symbol": symbol,
        "name": str(route["name"]),
        "state_domain": cfg["state_domains"]["overlay_reentry_queue"],
        "from_state": "NOT_PRESENT_IN_FMDL4C_OVERLAY",
        "to_state": route["queue_state"],
        "reason_codes": reason_codes,
        "evidence_ids": evidence_ids,
        "research_id": str(row["research_id"]),
        "research_version": research_version,
        "gate_results": build_gate_results(route),
        "approval_state": "ACCEPTED_TO_REENTRY_REVIEW_QUEUE_ONLY",
        "applied": True,
        "transition_scope": "ADDITIVE_OVERLAY_REENTRY_QUEUE_ONLY",
        "rollback_token": f"ROLLBACK-FMDL4C-{symbol}-{to_state_hash[:12]}",
        "from_state_hash": from_state_hash,
        "to_state_hash": to_state_hash,
        "created_at": created_at,
        "authority": cfg["authority"],
        "trade_authority": "NONE",
    }
    semantic = stable_hash({key: value for key, value in base.items() if key not in {"created_at"}})
    base["transition_id"] = f"FMDL4C-TR-{symbol}-{semantic[:16]}"
    base["semantic_hash"] = semantic
    return base


def validate_transition(record: dict[str, Any], cfg: dict[str, Any]) -> list[str]:
    required = {
        "transition_id", "symbol", "name", "state_domain", "from_state", "to_state",
        "reason_codes", "evidence_ids", "research_id", "research_version", "gate_results",
        "approval_state", "applied", "transition_scope", "rollback_token", "from_state_hash",
        "to_state_hash", "semantic_hash", "created_at", "authority", "trade_authority",
    }
    errors: list[str] = []
    missing = sorted(required - set(record))
    if missing:
        errors.append("MISSING_FIELDS:" + ",".join(missing))
    if record.get("state_domain") != cfg["state_domains"]["overlay_reentry_queue"]:
        errors.append("STATE_DOMAIN")
    if record.get("to_state") not in {"CANDIDATE_POOL_REENTRY_REVIEW_READY", "SHADOW_TRACK_REENTRY_REVIEW_READY"}:
        errors.append("TO_STATE")
    if record.get("approval_state") != "ACCEPTED_TO_REENTRY_REVIEW_QUEUE_ONLY":
        errors.append("APPROVAL_STATE")
    if record.get("applied") is not True:
        errors.append("APPLIED")
    if record.get("trade_authority") != "NONE":
        errors.append("TRADE_AUTHORITY")
    semantic = stable_hash({key: value for key, value in record.items() if key not in {"transition_id", "semantic_hash", "created_at"}})
    if semantic != record.get("semantic_hash"):
        errors.append("SEMANTIC_HASH")
    expected = f"FMDL4C-TR-{record.get('symbol')}-{semantic[:16]}"
    if record.get("transition_id") != expected:
        errors.append("TRANSITION_ID")
    return errors
