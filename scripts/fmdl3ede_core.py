from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable

import pandas as pd


VOLATILE_COLUMNS = {"generated_at", "published_at", "elapsed_seconds"}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _clean(value: Any) -> Any:
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


def _canonical(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _canonical(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    if isinstance(value, set):
        return sorted(_canonical(item) for item in value)
    return _clean(value)


def stable_hash(payload: Any) -> str:
    text = json.dumps(_canonical(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def semantic_frame_hash(frame: pd.DataFrame, *, sort_by: Iterable[str] = ("symbol",)) -> str:
    clean = frame.copy()
    clean = clean.drop(columns=[column for column in VOLATILE_COLUMNS if column in clean.columns], errors="ignore")
    available = [column for column in sort_by if column in clean.columns]
    if available:
        clean = clean.sort_values(available, kind="stable")
    records = [{key: _clean(value) for key, value in row.items()} for row in clean.to_dict(orient="records")]
    return stable_hash(records)


def row_hash(row: pd.Series | dict[str, Any]) -> str:
    payload = dict(row)
    payload.pop("row_hash", None)
    return stable_hash({key: _clean(value) for key, value in payload.items()})


def _safe_ratio(new: Any, old: Any) -> float | None:
    try:
        new_value, old_value = float(new), float(old)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(new_value) or not math.isfinite(old_value) or old_value <= 0 or new_value <= 0:
        return None
    return new_value / old_value


def _scaled(value: Any, ratio: float | None, *, inverse: bool = False) -> Any:
    if ratio is None:
        return value
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return value
    if not math.isfinite(numeric):
        return value
    return numeric / ratio if inverse else numeric * ratio


def validate_delta_inputs(baseline: pd.DataFrame, market_delta: pd.DataFrame, financial_events: pd.DataFrame, *, target_date: str) -> list[str]:
    errors: list[str] = []
    if baseline["symbol"].duplicated().any():
        errors.append("DUPLICATE_BASELINE_SYMBOL")
    if market_delta["symbol"].duplicated().any():
        errors.append("DUPLICATE_MARKET_SYMBOL")
    if "event_id" in financial_events and financial_events["event_id"].duplicated().any():
        errors.append("DUPLICATE_FINANCIAL_EVENT_ID")
    if "trade_authority" in market_delta and not set(market_delta["trade_authority"].dropna().astype(str)).issubset({"NONE"}):
        errors.append("MARKET_TRADE_AUTHORITY_PRESENT")
    if "trade_authority" in financial_events and not set(financial_events["trade_authority"].dropna().astype(str)).issubset({"NONE"}):
        errors.append("FINANCIAL_TRADE_AUTHORITY_PRESENT")
    if len(financial_events) and "effective_at" in financial_events:
        effective = pd.to_datetime(financial_events["effective_at"], errors="coerce", utc=True)
        target = pd.Timestamp(target_date, tz="Asia/Shanghai").tz_convert("UTC")
        future = int((effective.notna() & effective.gt(target)).sum())
        if future:
            errors.append(f"FUTURE_FINANCIAL_EVENT:{future}")
    return errors


def _component_ids(value: Any, release_id: str, incremental_release_id: str) -> str:
    try:
        payload = json.loads(value) if isinstance(value, str) and value else {}
    except json.JSONDecodeError:
        payload = {}
    payload["FMDL-3E-BC"] = incremental_release_id
    payload["FMDL-3E-DE"] = release_id
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _apply_row(row: pd.Series, delta: dict[str, Any], *, cfg: dict[str, Any], release_id: str, incremental_release_id: str, target_date: str) -> dict[str, Any]:
    result = row.to_dict()
    old_close = result.get("close")
    refreshed_close = delta.get("refreshed_close")
    ratio = _safe_ratio(refreshed_close, old_close)
    if ratio is not None:
        result["close"] = float(refreshed_close)
        total_shares = result.get("total_shares")
        float_shares = result.get("float_a_shares")
        result["total_market_cap_cny"] = float(total_shares) * float(refreshed_close) if pd.notna(total_shares) and float(total_shares) >= 0 else result.get("total_market_cap_cny")
        result["float_market_cap_cny"] = float(float_shares) * float(refreshed_close) if pd.notna(float_shares) and float(float_shares) >= 0 else result.get("float_market_cap_cny")
        for field in cfg["propagation"]["price_multiple_fields"]:
            if field in result:
                result[field] = _scaled(result.get(field), ratio)
        for field in cfg["propagation"]["inverse_price_fields"]:
            if field in result:
                result[field] = _scaled(result.get(field), ratio, inverse=True)
        components = [result.get(field) for field in cfg["propagation"]["shareholder_yield_components"]]
        if all(pd.notna(value) for value in components):
            result["shareholder_yield_ttm"] = float(sum(float(value) for value in components))
    result["market_as_of_date"] = target_date
    result["component_release_ids_json"] = _component_ids(result.get("component_release_ids_json"), release_id, incremental_release_id)
    result["capitalization_lineage_id"] = stable_hash({"symbol": result.get("symbol"), "close": result.get("close"), "total_shares": result.get("total_shares"), "float_a_shares": result.get("float_a_shares"), "release_id": release_id})
    result["valuation_row_hash"] = stable_hash({"symbol": result.get("symbol"), "pe_ttm": result.get("pe_ttm"), "pb": result.get("pb"), "ps_ttm": result.get("ps_ttm"), "fcf_yield_ttm": result.get("fcf_yield_ttm"), "ev_sales_ttm": result.get("ev_sales_ttm"), "ev_operating_income_ttm": result.get("ev_operating_income_ttm"), "release_id": release_id})
    result["authority"] = cfg["authority"]
    result["trade_authority"] = "NONE"
    result["row_hash"] = row_hash(result)
    return result


def incremental_propagate(baseline: pd.DataFrame, market_delta: pd.DataFrame, *, cfg: dict[str, Any], release_id: str, incremental_release_id: str, target_date: str) -> pd.DataFrame:
    delta_index = market_delta.set_index("symbol").to_dict(orient="index")
    rows = [_apply_row(row, delta_index.get(str(row["symbol"]), {}), cfg=cfg, release_id=release_id, incremental_release_id=incremental_release_id, target_date=target_date) for _, row in baseline.sort_values("symbol").iterrows()]
    return pd.DataFrame(rows, columns=baseline.columns).sort_values("symbol").reset_index(drop=True)


def full_rebuild(baseline: pd.DataFrame, market_delta: pd.DataFrame, *, cfg: dict[str, Any], release_id: str, incremental_release_id: str, target_date: str) -> pd.DataFrame:
    base = baseline.sort_values("symbol").reset_index(drop=True).copy()
    delta = market_delta[["symbol", "refreshed_close"]].copy()
    rebuilt = base.merge(delta, on="symbol", how="left")
    old_close = pd.to_numeric(rebuilt["close"], errors="coerce")
    new_close = pd.to_numeric(rebuilt["refreshed_close"], errors="coerce")
    valid = old_close.gt(0) & new_close.gt(0)
    ratio = new_close / old_close
    rebuilt.loc[valid, "close"] = new_close[valid]
    if "total_shares" in rebuilt:
        shares = pd.to_numeric(rebuilt["total_shares"], errors="coerce")
        mask = valid & shares.ge(0)
        rebuilt.loc[mask, "total_market_cap_cny"] = shares[mask] * new_close[mask]
    if "float_a_shares" in rebuilt:
        shares = pd.to_numeric(rebuilt["float_a_shares"], errors="coerce")
        mask = valid & shares.ge(0)
        rebuilt.loc[mask, "float_market_cap_cny"] = shares[mask] * new_close[mask]
    for field in cfg["propagation"]["price_multiple_fields"]:
        if field in rebuilt:
            numeric = pd.to_numeric(rebuilt[field], errors="coerce")
            mask = valid & numeric.notna()
            rebuilt.loc[mask, field] = numeric[mask] * ratio[mask]
    for field in cfg["propagation"]["inverse_price_fields"]:
        if field in rebuilt:
            numeric = pd.to_numeric(rebuilt[field], errors="coerce")
            mask = valid & numeric.notna()
            rebuilt.loc[mask, field] = numeric[mask] / ratio[mask]
    components = [field for field in cfg["propagation"]["shareholder_yield_components"] if field in rebuilt]
    if components:
        complete = rebuilt[components].notna().all(axis=1)
        rebuilt.loc[complete, "shareholder_yield_ttm"] = rebuilt.loc[complete, components].sum(axis=1)
    rebuilt["market_as_of_date"] = target_date
    rebuilt["component_release_ids_json"] = rebuilt["component_release_ids_json"].map(lambda value: _component_ids(value, release_id, incremental_release_id))
    rebuilt["capitalization_lineage_id"] = rebuilt.apply(lambda row: stable_hash({"symbol": row.get("symbol"), "close": row.get("close"), "total_shares": row.get("total_shares"), "float_a_shares": row.get("float_a_shares"), "release_id": release_id}), axis=1)
    rebuilt["valuation_row_hash"] = rebuilt.apply(lambda row: stable_hash({"symbol": row.get("symbol"), "pe_ttm": row.get("pe_ttm"), "pb": row.get("pb"), "ps_ttm": row.get("ps_ttm"), "fcf_yield_ttm": row.get("fcf_yield_ttm"), "ev_sales_ttm": row.get("ev_sales_ttm"), "ev_operating_income_ttm": row.get("ev_operating_income_ttm"), "release_id": release_id}), axis=1)
    rebuilt["authority"] = cfg["authority"]
    rebuilt["trade_authority"] = "NONE"
    rebuilt = rebuilt.drop(columns=["refreshed_close"])
    rebuilt["row_hash"] = rebuilt.apply(row_hash, axis=1)
    return rebuilt[baseline.columns].sort_values("symbol").reset_index(drop=True)


def comparison_audit(left: pd.DataFrame, right: pd.DataFrame) -> pd.DataFrame:
    left = left.sort_values("symbol").reset_index(drop=True)
    right = right.sort_values("symbol").reset_index(drop=True)
    rows = []
    for column in left.columns:
        a, b = left[column], right[column]
        if pd.api.types.is_bool_dtype(a) or pd.api.types.is_bool_dtype(b):
            equal = a.eq(b) | (a.isna() & b.isna())
        elif pd.api.types.is_numeric_dtype(a) and pd.api.types.is_numeric_dtype(b):
            numeric_a = pd.to_numeric(a, errors="coerce").astype(float)
            numeric_b = pd.to_numeric(b, errors="coerce").astype(float)
            equal = (numeric_a - numeric_b).abs().le(1e-10) | (numeric_a.isna() & numeric_b.isna())
        else:
            equal = a.eq(b) | (a.isna() & b.isna())
        rows.append({"column": column, "row_count": len(left), "mismatch_count": int((~equal).sum()), "left_null_count": int(a.isna().sum()), "right_null_count": int(b.isna().sum())})
    return pd.DataFrame(rows)


def manifest_for_directory(root: Path, release_id: str) -> dict[str, Any]:
    files = []
    for path in sorted(root.iterdir()):
        if path.name == "FMDL3E_MANIFEST.json":
            continue
        files.append({"path": path.name, "sha256": sha256_file(path), "bytes": path.stat().st_size})
    return {"manifest_version": "1.0.0", "release_id": release_id, "files": files}
