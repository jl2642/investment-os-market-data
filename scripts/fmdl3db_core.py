from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("Asia/Shanghai")
AUTHORITY = "DATA_AND_RESEARCH_EVIDENCE_ONLY"
TRADE_AUTHORITY = "NONE"
VALID_CAP_STATES = {"VALID", "VALID_WITH_WARNING"}


def now_iso() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def stable_hash(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def shard_for_symbol(symbol: str, shard_count: int) -> int:
    digest = hashlib.sha256(str(symbol).encode("utf-8")).hexdigest()
    return int(digest[:16], 16) % int(shard_count)


def find_column(frame: pd.DataFrame, candidates: list[str]) -> str | None:
    normalized = {str(column).strip(): str(column) for column in frame.columns}
    for candidate in candidates:
        if candidate in normalized:
            return normalized[candidate]
    for column in frame.columns:
        text = str(column).strip()
        for candidate in candidates:
            if candidate in text:
                return str(column)
    return None


def _json_value(value: Any) -> Any:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return value


def _raw_json(record: pd.Series) -> str:
    payload = {str(key): _json_value(value) for key, value in record.items()}
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)


def invoke_share_source(
    symbol: str,
    maximum_attempts: int,
    retry_backoff_seconds: list[float],
    provider: Callable[..., pd.DataFrame] | None = None,
) -> tuple[pd.DataFrame, int, str | None, str | None, float]:
    if provider is None:
        import akshare as ak

        provider = ak.stock_zh_a_gbjg_em
    started = time.monotonic()
    error_type: str | None = None
    error_message: str | None = None
    for attempt in range(1, maximum_attempts + 1):
        try:
            frame = provider(symbol=symbol)
            if frame is None:
                frame = pd.DataFrame()
            if not isinstance(frame, pd.DataFrame):
                frame = pd.DataFrame(frame)
            if len(frame):
                return frame, attempt, None, None, time.monotonic() - started
            error_type = "EMPTY_RESPONSE"
            error_message = "Effective-share source returned no rows."
        except Exception as exc:  # provider boundary
            error_type = type(exc).__name__
            error_message = str(exc)[:1000]
        if attempt < maximum_attempts:
            delay = retry_backoff_seconds[min(attempt - 1, len(retry_backoff_seconds) - 1)]
            time.sleep(float(delay))
    return pd.DataFrame(), maximum_attempts, error_type, error_message, time.monotonic() - started


def normalize_share_history(
    frame: pd.DataFrame,
    security: dict[str, Any],
    price_as_of_date: str,
    config: dict[str, Any],
    retrieved_at: str,
) -> tuple[list[dict[str, Any]], int, str | None]:
    route = config["source_route"]
    date_col = find_column(frame, route["date_columns"])
    total_col = find_column(frame, route["total_share_columns"])
    float_col = find_column(frame, route["float_a_share_columns"])
    limited_col = find_column(frame, route["limited_a_share_columns"])
    reason_col = find_column(frame, route["change_reason_columns"])
    missing = [
        name
        for name, column in [
            ("effective_date", date_col),
            ("total_shares", total_col),
            ("float_a_shares", float_col),
        ]
        if column is None
    ]
    if missing:
        return [], len(frame), "MISSING_REQUIRED_SOURCE_COLUMNS:" + "|".join(missing)

    as_of = pd.Timestamp(price_as_of_date)
    normalized: list[dict[str, Any]] = []
    invalid_count = 0
    for _, raw in frame.iterrows():
        effective = pd.to_datetime(raw.get(date_col), errors="coerce")
        total = pd.to_numeric(pd.Series([raw.get(total_col)]), errors="coerce").iloc[0]
        float_a = pd.to_numeric(pd.Series([raw.get(float_col)]), errors="coerce").iloc[0]
        limited = (
            pd.to_numeric(pd.Series([raw.get(limited_col)]), errors="coerce").iloc[0]
            if limited_col
            else None
        )
        if pd.isna(effective) or pd.isna(total) or pd.isna(float_a) or float(total) <= 0 or float(float_a) <= 0:
            invalid_count += 1
            continue
        raw_json = _raw_json(raw)
        effective_date = effective.date().isoformat()
        eligibility = "EFFECTIVE_ELIGIBLE" if effective <= as_of else "FUTURE_EFFECTIVE"
        payload = {
            "symbol": str(security["symbol"]),
            "name": security.get("name"),
            "exchange": security.get("exchange"),
            "board": security.get("board"),
            "source_effective_date": effective_date,
            "price_as_of_date": price_as_of_date,
            "total_shares": float(total),
            "float_a_shares": float(float_a),
            "limited_a_shares": None if limited is None or pd.isna(limited) or float(limited) < 0 else float(limited),
            "change_reason": None if reason_col is None or pd.isna(raw.get(reason_col)) else str(raw.get(reason_col)),
            "eligibility_state": eligibility,
            "selected_for_current": False,
            "raw_fields_json": raw_json,
            "source_id": route["source_id"],
            "source_adapter": route["adapter"],
            "retrieved_at": retrieved_at,
            "authority": AUTHORITY,
            "trade_authority": TRADE_AUTHORITY,
        }
        payload["source_row_hash"] = stable_hash(
            {
                "symbol": payload["symbol"],
                "source_effective_date": effective_date,
                "total_shares": payload["total_shares"],
                "float_a_shares": payload["float_a_shares"],
                "limited_a_shares": payload["limited_a_shares"],
                "raw_fields_json": raw_json,
                "source_id": payload["source_id"],
            }
        )
        normalized.append(payload)

    normalized.sort(
        key=lambda row: (row["source_effective_date"], row["source_row_hash"])
    )
    eligible_indexes = [
        index
        for index, row in enumerate(normalized)
        if row["eligibility_state"] == "EFFECTIVE_ELIGIBLE"
    ]
    if eligible_indexes:
        selected_index = eligible_indexes[-1]
        normalized[selected_index]["selected_for_current"] = True
    return normalized, invalid_count, None


def _accepted_price(
    snapshot_rows: pd.DataFrame,
    expected_as_of_date: str,
) -> tuple[dict[str, Any], str | None]:
    if len(snapshot_rows) != 1:
        return {}, "SNAPSHOT_ROW_COUNT_NOT_ONE"
    row = snapshot_rows.iloc[0]
    close = pd.to_numeric(pd.Series([row.get("close")]), errors="coerce").iloc[0]
    as_of = pd.to_datetime(row.get("as_of_date"), errors="coerce")
    quality = str(row.get("record_quality"))
    status = str(row.get("data_status"))
    if pd.isna(as_of) or as_of.date().isoformat() != expected_as_of_date:
        return {}, "SNAPSHOT_AS_OF_DATE_MISMATCH"
    if pd.isna(close) or float(close) <= 0:
        return {}, "NON_POSITIVE_OR_MISSING_CLOSE"
    if quality not in {"VALID", "PARTIAL"}:
        return {}, "SNAPSHOT_RECORD_QUALITY_NOT_ACCEPTED"
    if status in {"NO_DATA", "NOT_LISTED"}:
        return {}, "SNAPSHOT_DATA_STATUS_NOT_ACCEPTED"
    return {
        "price_as_of_date": expected_as_of_date,
        "price_source_timestamp": None if pd.isna(row.get("source_timestamp")) else str(row.get("source_timestamp")),
        "close": float(close),
        "price_row_hash": None if pd.isna(row.get("row_hash")) else str(row.get("row_hash")),
        "price_record_quality": quality,
        "price_data_status": status,
    }, None


def build_symbol_result(
    security: dict[str, Any],
    snapshot_rows: pd.DataFrame,
    config: dict[str, Any],
    source_release_id: str,
    source_universe_version: str,
    source_snapshot_version: str,
    provider: Callable[..., pd.DataFrame] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    symbol = str(security["symbol"])
    expected_as_of = str(security["as_of_date"])
    price, price_error = _accepted_price(snapshot_rows, expected_as_of)
    retrieved_at = now_iso()
    frame, attempt_count, error_type, error_message, elapsed = invoke_share_source(
        symbol,
        int(config["source_route"]["maximum_attempts"]),
        [float(value) for value in config["source_route"]["retry_backoff_seconds"]],
        provider=provider,
    )
    ledger, invalid_source_rows, normalization_error = normalize_share_history(
        frame,
        security,
        expected_as_of,
        config,
        retrieved_at,
    ) if len(frame) else ([], 0, None)
    selected = [row for row in ledger if row["selected_for_current"]]
    future_count = sum(row["eligibility_state"] == "FUTURE_EFFECTIVE" for row in ledger)

    state = "VALID"
    reason = "ACCEPTED_PRICE_AND_PIT_EFFECTIVE_SHARES"
    if price_error:
        state = "PRICE_UNAVAILABLE"
        reason = price_error
    elif error_type or not len(frame):
        state = "SHARE_SOURCE_UNAVAILABLE"
        reason = error_type or "EMPTY_RESPONSE"
    elif normalization_error:
        state = "INVALID_SHARE_VALUES"
        reason = normalization_error
    elif len(selected) != 1:
        if ledger and future_count == len(ledger):
            state = "FUTURE_ONLY_SHARE_ROWS"
            reason = "NO_SHARE_ROW_EFFECTIVE_NOT_LATER_THAN_PRICE_DATE"
        else:
            state = "NO_EFFECTIVE_SHARE_ROW"
            reason = "NO_POSITIVE_EFFECTIVE_SHARE_ROW"
    elif str(price.get("price_data_status")) == "SUSPENDED":
        state = "VALID_WITH_WARNING"
        reason = "SUSPENDED_SECURITY_USING_ACCEPTED_LAST_CLOSE"

    share = selected[0] if len(selected) == 1 else None
    total_market_cap = None
    float_market_cap = None
    if state in VALID_CAP_STATES and share is not None:
        total_market_cap = float(price["close"]) * float(share["total_shares"])
        float_market_cap = float(price["close"]) * float(share["float_a_shares"])

    current = {
        "symbol": symbol,
        "name": str(security.get("name") or symbol),
        "exchange": str(security.get("exchange") or symbol.split(".")[-1]),
        "board": str(security.get("board") or "UNKNOWN"),
        "price_as_of_date": expected_as_of,
        "price_source_timestamp": price.get("price_source_timestamp"),
        "close": price.get("close"),
        "price_row_hash": price.get("price_row_hash"),
        "price_record_quality": price.get("price_record_quality"),
        "price_data_status": price.get("price_data_status"),
        "share_effective_date": share.get("source_effective_date") if share else None,
        "total_shares": share.get("total_shares") if share else None,
        "float_a_shares": share.get("float_a_shares") if share else None,
        "limited_a_shares": share.get("limited_a_shares") if share else None,
        "total_market_cap_cny": total_market_cap,
        "float_market_cap_cny": float_market_cap,
        "share_source_id": share.get("source_id") if share else None,
        "share_source_row_hash": share.get("source_row_hash") if share else None,
        "capitalization_state": state,
        "state_reason": reason,
        "attempt_count": int(attempt_count),
        "source_error_type": normalization_error or error_type,
        "source_error_message": error_message,
        "provider_row_count": int(len(frame)),
        "normalized_ledger_row_count": int(len(ledger)),
        "invalid_source_row_count": int(invalid_source_rows),
        "future_share_row_count": int(future_count),
        "universe_row_hash": None if pd.isna(security.get("row_hash")) else str(security.get("row_hash")),
        "source_release_id": source_release_id,
        "source_universe_version": source_universe_version,
        "source_snapshot_version": source_snapshot_version,
        "authority": AUTHORITY,
        "trade_authority": TRADE_AUTHORITY,
    }
    current["lineage_id"] = stable_hash(
        {
            "symbol": symbol,
            "price_as_of_date": current["price_as_of_date"],
            "price_row_hash": current["price_row_hash"],
            "share_effective_date": current["share_effective_date"],
            "share_source_row_hash": current["share_source_row_hash"],
            "contract_version": config["contract_version"],
        }
    )
    retry = {
        "symbol": symbol,
        "board": current["board"],
        "attempt_count": int(attempt_count),
        "elapsed_seconds": round(float(elapsed), 6),
        "provider_row_count": int(len(frame)),
        "normalized_ledger_row_count": int(len(ledger)),
        "invalid_source_row_count": int(invalid_source_rows),
        "future_share_row_count": int(future_count),
        "capitalization_state": state,
        "source_error_type": current["source_error_type"],
        "source_error_message": error_message,
        "retrieved_at": retrieved_at,
        "authority": AUTHORITY,
        "trade_authority": TRADE_AUTHORITY,
    }
    return current, ledger, retry


def create_manifest(root: Path, release_id: str, program_id: str) -> dict[str, Any]:
    files = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and not path.name.endswith("MANIFEST.json"):
            files.append(
                {
                    "path": str(path.relative_to(root)),
                    "sha256": sha256_file(path),
                    "bytes": path.stat().st_size,
                }
            )
    return {
        "manifest_version": "1.0.0",
        "release_id": release_id,
        "program_id": program_id,
        "files": files,
        "authority": AUTHORITY,
        "trade_authority": TRADE_AUTHORITY,
    }
