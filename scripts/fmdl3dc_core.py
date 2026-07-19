from __future__ import annotations

import hashlib
import json
from typing import Any

import pandas as pd

AUTHORITY = "DATA_AND_RESEARCH_EVIDENCE_ONLY"
TRADE_AUTHORITY = "NONE"
VALID_STATES = {"VALID", "VALID_WITH_WARNING"}

METRIC_COLUMN_MAP = {
    "VAL_PE_TTM": ("pe_ttm", "pe_ttm_state"),
    "VAL_EARNINGS_YIELD_TTM": ("earnings_yield_ttm", "earnings_yield_ttm_state"),
    "VAL_PB": ("pb", "pb_state"),
    "VAL_PS_TTM": ("ps_ttm", "ps_ttm_state"),
    "VAL_FCF_YIELD_TTM": ("fcf_yield_ttm", "fcf_yield_ttm_state"),
    "VAL_EV_SALES_TTM": ("ev_sales_ttm", "ev_sales_ttm_state"),
    "VAL_EV_OPERATING_INCOME_TTM": (
        "ev_operating_income_ttm",
        "ev_operating_income_ttm_state",
    ),
}

METRIC_TOKENS = {
    "VAL_PE_TTM": ["net_income_parent_ttm"],
    "VAL_EARNINGS_YIELD_TTM": ["net_income_parent_ttm"],
    "VAL_PB": ["parent_equity"],
    "VAL_PS_TTM": ["revenue_ttm"],
    "VAL_FCF_YIELD_TTM": ["cfo_ttm", "capex_ttm"],
    "VAL_EV_SALES_TTM": [
        "short_term_debt",
        "long_term_debt",
        "bonds_payable",
        "cash_equivalents",
        "revenue_ttm",
    ],
    "VAL_EV_OPERATING_INCOME_TTM": [
        "short_term_debt",
        "long_term_debt",
        "bonds_payable",
        "cash_equivalents",
        "operating_income_ttm",
    ],
}

FAILURE_PRIORITY = [
    "CONFLICTED_INPUT",
    "QUARANTINED_INPUT",
    "NON_COMPARABLE_INPUT",
    "STALE_INPUT",
    "RESTATEMENT_REPLAY_BLOCKED",
    "MISSING_REQUIRED_INPUT",
]


def stable_hash(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def parse_json_map(value: Any) -> dict[str, Any]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return {}
    if isinstance(value, dict):
        return value
    text = str(value).strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def normalize_timestamp(value: Any, timezone: str) -> pd.Timestamp | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        timestamp = pd.Timestamp(value)
    except Exception:
        return None
    if pd.isna(timestamp):
        return None
    if timestamp.tzinfo is None:
        return timestamp.tz_localize(timezone)
    return timestamp.tz_convert(timezone)


def market_cutoff(as_of_date: str, cutoff_time: str, timezone: str) -> pd.Timestamp:
    return pd.Timestamp(f"{as_of_date} {cutoff_time}", tz=timezone)


def _failure_state(states: list[str], future_seen: bool) -> str:
    if future_seen:
        return "FUTURE_DENOMINATOR_BLOCKED"
    for candidate in FAILURE_PRIORITY:
        if candidate in states:
            return candidate
    return "MISSING_REQUIRED_INPUT"


def select_denominator(
    symbol_rows: pd.DataFrame,
    required_tokens: list[str],
    cutoff: pd.Timestamp,
    valid_input_states: set[str],
    timezone: str,
) -> tuple[pd.Series | None, str, dict[str, Any], dict[str, Any], dict[str, Any]]:
    if symbol_rows.empty:
        return None, "MISSING_REQUIRED_INPUT", {}, {}, {}

    ordered = symbol_rows.copy()
    ordered["__period_sort"] = pd.to_datetime(ordered["period_end"], errors="coerce")
    ordered = ordered.sort_values(["__period_sort", "period_end"], ascending=False)
    future_seen = False
    observed_states: list[str] = []

    for _, row in ordered.iterrows():
        states = parse_json_map(row.get("input_states_json"))
        available = parse_json_map(row.get("input_available_from_json"))
        fact_ids = parse_json_map(row.get("input_fact_ids_json"))
        values: dict[str, Any] = {}
        row_states: list[str] = []
        row_valid = True

        for token in required_tokens:
            value = pd.to_numeric(pd.Series([row.get(token)]), errors="coerce").iloc[0]
            state = str(states.get(token) or "MISSING_REQUIRED_INPUT")
            available_at = normalize_timestamp(available.get(token), timezone)
            values[token] = None if pd.isna(value) else float(value)
            row_states.append(state)
            observed_states.append(state)
            if available_at is not None and available_at > cutoff:
                future_seen = True
                row_valid = False
            elif available_at is None or state not in valid_input_states or pd.isna(value):
                row_valid = False

        if row_valid:
            quality = "VALID_WITH_WARNING" if "VALID_WITH_WARNING" in row_states else "VALID"
            return row, quality, values, available, fact_ids

    return None, _failure_state(observed_states, future_seen), {}, {}, {}


def _applicable_profiles(metric: pd.Series) -> set[str]:
    return {
        item.strip()
        for item in str(metric.get("applicable_sector_profiles") or "").split("|")
        if item.strip()
    }


def _base_detail(
    cap: pd.Series,
    profile: str,
    metric: pd.Series,
    cutoff: pd.Timestamp,
    valuation_version: str,
) -> dict[str, Any]:
    market_cap = pd.to_numeric(
        pd.Series([cap.get("total_market_cap_cny")]), errors="coerce"
    ).iloc[0]
    return {
        "symbol": str(cap.get("symbol")),
        "name": str(cap.get("name") or cap.get("symbol")),
        "sector_profile": profile,
        "metric_id": str(metric.get("metric_id")),
        "metric_name": str(metric.get("metric_name")),
        "metric_family": "VALUATION",
        "valuation_version": valuation_version,
        "market_as_of_date": str(cap.get("price_as_of_date")),
        "market_cutoff_timestamp": cutoff.isoformat(),
        "total_market_cap_cny": None if pd.isna(market_cap) else float(market_cap),
        "metric_value": None,
        "output_unit": str(metric.get("output_unit") or "RATIO"),
        "quality_state": "MISSING_REQUIRED_INPUT",
        "warning_codes": "",
        "denominator_period_end": None,
        "denominator_available_from": None,
        "required_inputs": str(metric.get("required_inputs") or ""),
        "input_values_json": "{}",
        "input_states_json": "{}",
        "input_available_from_json": "{}",
        "input_fact_ids_json": "{}",
        "formula": str(metric.get("formula") or ""),
        "capitalization_lineage_id": None
        if pd.isna(cap.get("lineage_id"))
        else str(cap.get("lineage_id")),
        "metric_lineage_id": "",
        "decision_grade": False,
        "authority": AUTHORITY,
        "trade_authority": TRADE_AUTHORITY,
    }


def evaluate_metric(
    cap: pd.Series,
    profile: str,
    symbol_rows: pd.DataFrame,
    metric: pd.Series,
    config: dict[str, Any],
) -> dict[str, Any]:
    metric_id = str(metric["metric_id"])
    as_of_date = str(cap.get("price_as_of_date"))
    cutoff = market_cutoff(
        as_of_date,
        config["engine"]["market_cutoff_time"],
        config["business_timezone"],
    )
    detail = _base_detail(
        cap,
        profile,
        metric,
        cutoff,
        config["engine"]["valuation_version"],
    )

    cap_state = str(cap.get("capitalization_state") or "")
    market_cap = detail["total_market_cap_cny"]
    input_states: dict[str, Any] = {"total_market_cap_cny": cap_state}
    input_available: dict[str, Any] = {
        "total_market_cap_cny": cutoff.isoformat()
    }
    input_fact_ids: dict[str, Any] = {
        "total_market_cap_cny": [detail["capitalization_lineage_id"]]
        if detail["capitalization_lineage_id"]
        else []
    }
    input_values: dict[str, Any] = {"total_market_cap_cny": market_cap}

    if cap_state not in VALID_STATES or market_cap is None or market_cap <= 0:
        detail["quality_state"] = "CONTROLLED_CAPITALIZATION_QUARANTINE"
    elif profile == "UNRESOLVED":
        detail["quality_state"] = "SECTOR_PROFILE_UNRESOLVED"
    elif profile not in _applicable_profiles(metric):
        detail["quality_state"] = "NOT_APPLICABLE_SECTOR"
    else:
        required_tokens = METRIC_TOKENS[metric_id]
        selected, input_quality, values, available, fact_ids = select_denominator(
            symbol_rows,
            required_tokens,
            cutoff,
            set(config["engine"]["valid_input_states"]),
            config["business_timezone"],
        )
        if selected is None:
            detail["quality_state"] = input_quality
        else:
            states = parse_json_map(selected.get("input_states_json"))
            for token in required_tokens:
                input_values[token] = values.get(token)
                input_states[token] = states.get(token, "MISSING_REQUIRED_INPUT")
                input_available[token] = available.get(token)
                input_fact_ids[token] = fact_ids.get(token, [])
            detail["denominator_period_end"] = str(selected.get("period_end"))
            available_timestamps = [
                normalize_timestamp(available.get(token), config["business_timezone"])
                for token in required_tokens
            ]
            available_timestamps = [item for item in available_timestamps if item is not None]
            detail["denominator_available_from"] = (
                max(available_timestamps).isoformat() if available_timestamps else None
            )

            quality = input_quality
            warning_codes: list[str] = []
            value: float | None = None

            if metric_id in {"VAL_PE_TTM", "VAL_EARNINGS_YIELD_TTM"}:
                earnings = float(values["net_income_parent_ttm"])
                if earnings <= 0:
                    quality = "NON_POSITIVE_EARNINGS"
                elif metric_id == "VAL_PE_TTM":
                    value = market_cap / earnings
                else:
                    value = earnings / market_cap
            elif metric_id == "VAL_PB":
                equity = float(values["parent_equity"])
                if equity <= 0:
                    quality = "NON_POSITIVE_BOOK_EQUITY"
                else:
                    value = market_cap / equity
            elif metric_id == "VAL_PS_TTM":
                revenue = float(values["revenue_ttm"])
                if revenue <= 0:
                    quality = "NON_POSITIVE_REVENUE"
                else:
                    value = market_cap / revenue
            elif metric_id == "VAL_FCF_YIELD_TTM":
                fcf = float(values["cfo_ttm"]) + float(values["capex_ttm"])
                input_values["free_cash_flow_ttm"] = fcf
                value = fcf / market_cap
                if fcf < 0:
                    quality = "VALID_WITH_WARNING"
                    warning_codes.append("NEGATIVE_FREE_CASH_FLOW")
            elif metric_id in {
                "VAL_EV_SALES_TTM",
                "VAL_EV_OPERATING_INCOME_TTM",
            }:
                enterprise_value = (
                    market_cap
                    + float(values["short_term_debt"])
                    + float(values["long_term_debt"])
                    + float(values["bonds_payable"])
                    - float(values["cash_equivalents"])
                )
                input_values["enterprise_value_cny"] = enterprise_value
                if enterprise_value <= 0:
                    quality = "INVALID_ENTERPRISE_VALUE"
                elif metric_id == "VAL_EV_SALES_TTM":
                    revenue = float(values["revenue_ttm"])
                    if revenue <= 0:
                        quality = "NON_POSITIVE_REVENUE"
                    else:
                        value = enterprise_value / revenue
                else:
                    operating_income = float(values["operating_income_ttm"])
                    if operating_income <= 0:
                        quality = "NON_POSITIVE_OPERATING_INCOME"
                    else:
                        value = enterprise_value / operating_income

            detail["quality_state"] = quality
            detail["metric_value"] = float(value) if value is not None else None
            detail["warning_codes"] = "|".join(warning_codes)

    detail["input_values_json"] = json.dumps(
        input_values, ensure_ascii=False, sort_keys=True, default=str
    )
    detail["input_states_json"] = json.dumps(
        input_states, ensure_ascii=False, sort_keys=True, default=str
    )
    detail["input_available_from_json"] = json.dumps(
        input_available, ensure_ascii=False, sort_keys=True, default=str
    )
    detail["input_fact_ids_json"] = json.dumps(
        input_fact_ids, ensure_ascii=False, sort_keys=True, default=str
    )
    detail["decision_grade"] = detail["quality_state"] in VALID_STATES
    detail["metric_lineage_id"] = stable_hash(
        {
            "symbol": detail["symbol"],
            "metric_id": detail["metric_id"],
            "market_as_of_date": detail["market_as_of_date"],
            "capitalization_lineage_id": detail["capitalization_lineage_id"],
            "denominator_period_end": detail["denominator_period_end"],
            "denominator_available_from": detail["denominator_available_from"],
            "input_fact_ids_json": detail["input_fact_ids_json"],
            "quality_state": detail["quality_state"],
            "valuation_version": detail["valuation_version"],
        }
    )
    return detail


def build_outputs(
    capitalization: pd.DataFrame,
    sector_profiles: pd.DataFrame,
    derived_inputs: pd.DataFrame,
    registry: pd.DataFrame,
    config: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    expected_metrics = config["engine"]["expected_valuation_metric_ids"]
    metrics = registry[
        registry["metric_id"].astype(str).isin(expected_metrics)
        & registry["metric_family"].astype(str).eq("VALUATION")
    ].copy()
    metrics["__order"] = metrics["metric_id"].map(
        {metric_id: index for index, metric_id in enumerate(expected_metrics)}
    )
    metrics = metrics.sort_values("__order")

    profiles = sector_profiles.set_index("symbol")["sector_profile"].astype(str).to_dict()
    derived = derived_inputs.copy()
    derived["symbol"] = derived["symbol"].astype(str)
    derived_groups = {
        symbol: frame.drop(columns=["__period_sort"], errors="ignore")
        for symbol, frame in derived.groupby("symbol", sort=False)
    }

    details: list[dict[str, Any]] = []
    current_rows: list[dict[str, Any]] = []
    capitalization = capitalization.sort_values("symbol").reset_index(drop=True)

    for _, cap in capitalization.iterrows():
        symbol = str(cap["symbol"])
        profile = profiles.get(symbol, "UNRESOLVED")
        symbol_rows = derived_groups.get(symbol, derived.iloc[0:0])
        metric_rows = [
            evaluate_metric(cap, profile, symbol_rows, metric, config)
            for _, metric in metrics.iterrows()
        ]
        details.extend(metric_rows)

        current: dict[str, Any] = {
            "symbol": symbol,
            "name": str(cap.get("name") or symbol),
            "exchange": str(cap.get("exchange") or symbol.split(".")[-1]),
            "board": str(cap.get("board") or "UNKNOWN"),
            "sector_profile": profile,
            "market_as_of_date": str(cap.get("price_as_of_date")),
            "total_market_cap_cny": None
            if pd.isna(cap.get("total_market_cap_cny"))
            else float(cap.get("total_market_cap_cny")),
            "float_market_cap_cny": None
            if pd.isna(cap.get("float_market_cap_cny"))
            else float(cap.get("float_market_cap_cny")),
            "capitalization_state": str(cap.get("capitalization_state")),
            "valuation_version": config["engine"]["valuation_version"],
            "authority": AUTHORITY,
            "trade_authority": TRADE_AUTHORITY,
        }
        for metric_row in metric_rows:
            value_column, state_column = METRIC_COLUMN_MAP[metric_row["metric_id"]]
            current[value_column] = metric_row["metric_value"]
            current[state_column] = metric_row["quality_state"]
        current["valid_metric_count"] = sum(
            row["quality_state"] in VALID_STATES for row in metric_rows
        )
        current["decision_grade_metric_count"] = sum(
            bool(row["decision_grade"]) for row in metric_rows
        )
        current["row_hash"] = stable_hash(
            {
                key: value
                for key, value in current.items()
                if key not in {"row_hash"}
            }
        )
        current_rows.append(current)

    detail_frame = pd.DataFrame(details).sort_values(["symbol", "metric_id"]).reset_index(drop=True)
    current_frame = pd.DataFrame(current_rows).sort_values("symbol").reset_index(drop=True)
    return detail_frame, current_frame
