from __future__ import annotations

import hashlib
import json
from typing import Any

import numpy as np
import pandas as pd

VALID_INPUT_STATES = {"VALID", "VALID_WITH_WARNING"}
VALID_METRIC_STATES = {"VALID", "VALID_WITH_WARNING"}


def stable_hash(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()


def parse_json_map(value: Any) -> dict[str, Any]:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return {}
    if isinstance(value, dict):
        return value
    return json.loads(str(value))


def timestamp_not_later(value: str | None, cutoff: str | None) -> bool:
    if not value or not cutoff:
        return False
    left = pd.to_datetime(value, utc=True, errors="coerce")
    right = pd.to_datetime(cutoff, utc=True, errors="coerce")
    return bool(pd.notna(left) and pd.notna(right) and left <= right)


def max_timestamp(values: list[str | None]) -> str | None:
    parsed = [pd.to_datetime(value, utc=True, errors="coerce") for value in values if value]
    parsed = [value for value in parsed if pd.notna(value)]
    if not parsed:
        return None
    return max(parsed).isoformat()


def build_capitalization_snapshot(
    pilot: pd.DataFrame,
    evidence: pd.DataFrame,
    source_release_id: str,
) -> pd.DataFrame:
    evidence = evidence.copy()
    evidence["symbol"] = evidence["symbol"].astype(str)
    evidence_index = {str(row.symbol): row for row in evidence.itertuples(index=False)}
    rows: list[dict[str, Any]] = []
    for item in pilot.itertuples(index=False):
        symbol = str(item.symbol)
        source = evidence_index.get(symbol)
        if source is None:
            state = "CONTROLLED_QUARANTINE"
            row = {
                "symbol": symbol,
                "name": item.name,
                "sector_profile": item.sector_profile,
                "board": item.board,
                "market_as_of_date": None,
                "market_cutoff_timestamp": None,
                "close": None,
                "share_effective_date": None,
                "total_shares": None,
                "float_a_shares": None,
                "total_market_cap_cny": None,
                "float_market_cap_cny": None,
                "capitalization_state": state,
                "price_source_id": None,
                "share_source_id": None,
                "capitalization_source_id": None,
                "warning_codes": "CONTROLLED_BSE_OR_SOURCE_QUARANTINE",
            }
        else:
            price_date = pd.to_datetime(source.price_as_of_date, errors="coerce")
            share_date = pd.to_datetime(source.share_effective_date, errors="coerce")
            close = pd.to_numeric(pd.Series([source.close]), errors="coerce").iloc[0]
            total_shares = pd.to_numeric(pd.Series([source.total_shares]), errors="coerce").iloc[0]
            float_shares = pd.to_numeric(pd.Series([source.float_a_shares]), errors="coerce").iloc[0]
            future = bool(source.future_effective_share_flag) or (
                pd.notna(price_date) and pd.notna(share_date) and share_date > price_date
            )
            valid = (
                pd.notna(close)
                and pd.notna(total_shares)
                and pd.notna(float_shares)
                and float(close) > 0
                and float(total_shares) > 0
                and float(float_shares) > 0
                and not future
            )
            if future:
                state = "FUTURE_EFFECTIVE_SHARE_BLOCKED"
            elif not valid:
                state = "MISSING_REQUIRED_INPUT"
            else:
                state = "VALID"
            total_market_cap = (
                float(close) * float(total_shares) if valid else None
            )
            float_market_cap = (
                float(close) * float(float_shares) if valid else None
            )
            row = {
                "symbol": symbol,
                "name": item.name,
                "sector_profile": item.sector_profile,
                "board": item.board,
                "market_as_of_date": str(source.price_as_of_date) if pd.notna(source.price_as_of_date) else None,
                "market_cutoff_timestamp": str(source.price_source_timestamp) if pd.notna(source.price_source_timestamp) else None,
                "close": float(close) if pd.notna(close) else None,
                "share_effective_date": str(source.share_effective_date) if pd.notna(source.share_effective_date) else None,
                "total_shares": float(total_shares) if pd.notna(total_shares) else None,
                "float_a_shares": float(float_shares) if pd.notna(float_shares) else None,
                "total_market_cap_cny": total_market_cap,
                "float_market_cap_cny": float_market_cap,
                "capitalization_state": state,
                "price_source_id": str(source.price_source_id) if pd.notna(source.price_source_id) else None,
                "share_source_id": str(source.share_source_id) if pd.notna(source.share_source_id) else None,
                "capitalization_source_id": str(source.capitalization_source_id) if pd.notna(source.capitalization_source_id) else None,
                "warning_codes": "NONE" if state == "VALID" else state,
            }
        row["source_release_id"] = source_release_id
        row["lineage_id"] = stable_hash(
            {
                "symbol": symbol,
                "market_as_of_date": row["market_as_of_date"],
                "share_effective_date": row["share_effective_date"],
                "price_source_id": row["price_source_id"],
                "share_source_id": row["share_source_id"],
            }
        )
        row["authority"] = "DATA_AND_RESEARCH_EVIDENCE_ONLY"
        row["trade_authority"] = "NONE"
        rows.append(row)
    return pd.DataFrame(rows).sort_values("symbol").reset_index(drop=True)


def select_pit_denominator_row(
    symbol_rows: pd.DataFrame,
    tokens: list[str],
    cutoff: str | None,
) -> tuple[pd.Series | None, str, list[str]]:
    if symbol_rows.empty:
        return None, "MISSING_REQUIRED_INPUT", ["NO_DERIVED_INPUT_ROWS"]
    warnings: list[str] = []
    future_seen = False
    ordered = symbol_rows.sort_values("period_end", ascending=False)
    for _, row in ordered.iterrows():
        states = parse_json_map(row.get("input_states_json"))
        available = parse_json_map(row.get("input_available_from_json"))
        all_valid = True
        row_warning = False
        for token in tokens:
            state = str(states.get(token, "MISSING_REQUIRED_INPUT"))
            value = row.get(token)
            timestamp = available.get(token)
            if state not in VALID_INPUT_STATES or value is None or pd.isna(value):
                all_valid = False
                break
            if not timestamp_not_later(timestamp, cutoff):
                future_seen = True
                all_valid = False
                break
            if state == "VALID_WITH_WARNING":
                row_warning = True
        if all_valid:
            if row_warning:
                warnings.append("DENOMINATOR_VALID_WITH_WARNING")
            return row, "VALID_WITH_WARNING" if row_warning else "VALID", warnings
    return (
        None,
        "FUTURE_DENOMINATOR_BLOCKED" if future_seen else "MISSING_REQUIRED_INPUT",
        ["NO_ELIGIBLE_POINT_IN_TIME_DENOMINATOR"],
    )


def _formula_value(metric_id: str, cap: pd.Series, denominator: pd.Series | None) -> float:
    market_cap = float(cap["total_market_cap_cny"])
    if metric_id == "CAP_TOTAL_MARKET_CAP":
        return market_cap
    if metric_id == "CAP_FLOAT_A_MARKET_CAP":
        return float(cap["float_market_cap_cny"])
    if denominator is None:
        raise ValueError("missing denominator row")
    if metric_id == "VAL_PE_TTM":
        return market_cap / float(denominator["net_income_parent_ttm"])
    if metric_id == "VAL_EARNINGS_YIELD_TTM":
        return float(denominator["net_income_parent_ttm"]) / market_cap
    if metric_id == "VAL_PB":
        return market_cap / float(denominator["parent_equity"])
    if metric_id == "VAL_PS_TTM":
        return market_cap / float(denominator["revenue_ttm"])
    if metric_id == "VAL_FCF_YIELD_TTM":
        return (
            float(denominator["cfo_ttm"]) + float(denominator["capex_ttm"])
        ) / market_cap
    debt = (
        float(denominator["short_term_debt"])
        + float(denominator["long_term_debt"])
        + float(denominator["bonds_payable"])
    )
    enterprise_value = market_cap + debt - float(denominator["cash_equivalents"])
    if metric_id == "VAL_EV_SALES_TTM":
        return enterprise_value / float(denominator["revenue_ttm"])
    if metric_id == "VAL_EV_OPERATING_INCOME_TTM":
        return enterprise_value / float(denominator["operating_income_ttm"])
    raise ValueError(f"unsupported pilot metric {metric_id}")


def evaluate_metric(
    metric: pd.Series,
    cap: pd.Series,
    symbol_rows: pd.DataFrame,
    source_release_id: str,
) -> dict[str, Any]:
    metric_id = str(metric["metric_id"])
    profile = str(cap["sector_profile"])
    applicable = set(str(metric["applicable_sector_profiles"]).split("|"))
    required = str(metric["required_inputs"]).split("|")
    financial_tokens = [
        token
        for token in required
        if token not in {"close", "total_shares", "float_a_shares", "total_market_cap_cny", "enterprise_value_cny", "implemented_cash_dividend_ttm", "dividend_yield_ttm", "completed_net_buyback_yield_ttm", "completed_net_issuance_yield_ttm"}
    ]
    state = "VALID"
    warnings: list[str] = []
    denominator_row: pd.Series | None = None
    if str(cap["capitalization_state"]) not in {"VALID", "VALID_WITH_WARNING"}:
        state = "CONTROLLED_CAPITALIZATION_QUARANTINE"
    elif profile not in applicable:
        state = "NOT_APPLICABLE_SECTOR"
    elif str(metric["build_stage"]) == "3D_D":
        state = "DEFERRED_TO_SHAREHOLDER_RETURN_LAYER"
    elif financial_tokens:
        denominator_row, state, denominator_warnings = select_pit_denominator_row(
            symbol_rows,
            financial_tokens,
            cap.get("market_cutoff_timestamp"),
        )
        warnings.extend(denominator_warnings)

    input_values: dict[str, Any] = {}
    input_states: dict[str, Any] = {}
    input_fact_ids: list[str] = []
    denominator_available: list[str | None] = []
    if denominator_row is not None:
        states = parse_json_map(denominator_row.get("input_states_json"))
        available = parse_json_map(denominator_row.get("input_available_from_json"))
        fact_ids = parse_json_map(denominator_row.get("input_fact_ids_json"))
        for token in financial_tokens:
            value = denominator_row.get(token)
            input_values[token] = None if value is None or pd.isna(value) else float(value)
            input_states[token] = states.get(token)
            denominator_available.append(available.get(token))
            input_fact_ids.extend(fact_ids.get(token, []))

    metric_value: float | None = None
    if state in VALID_METRIC_STATES:
        if metric_id in {"VAL_PE_TTM", "VAL_EARNINGS_YIELD_TTM"} and float(denominator_row["net_income_parent_ttm"]) <= 0:
            state = "NON_POSITIVE_EARNINGS"
        elif metric_id == "VAL_PB" and float(denominator_row["parent_equity"]) <= 0:
            state = "NON_POSITIVE_BOOK_EQUITY"
        elif metric_id in {"VAL_PS_TTM", "VAL_EV_SALES_TTM"} and float(denominator_row["revenue_ttm"]) <= 0:
            state = "NON_POSITIVE_REVENUE"
        elif metric_id == "VAL_EV_OPERATING_INCOME_TTM" and float(denominator_row["operating_income_ttm"]) <= 0:
            state = "MISSING_REQUIRED_INPUT"
            warnings.append("NON_POSITIVE_OPERATING_INCOME")
        else:
            try:
                metric_value = float(_formula_value(metric_id, cap, denominator_row))
                if not np.isfinite(metric_value):
                    metric_value = None
                    state = "MISSING_REQUIRED_INPUT"
                if metric_id.startswith("VAL_EV_") and denominator_row is not None:
                    enterprise_value = (
                        float(cap["total_market_cap_cny"])
                        + float(denominator_row["short_term_debt"])
                        + float(denominator_row["long_term_debt"])
                        + float(denominator_row["bonds_payable"])
                        - float(denominator_row["cash_equivalents"])
                    )
                    input_values["enterprise_value_cny"] = enterprise_value
                    if enterprise_value <= 0:
                        metric_value = None
                        state = "INVALID_ENTERPRISE_VALUE"
            except (ValueError, ZeroDivisionError, TypeError, KeyError):
                metric_value = None
                state = "MISSING_REQUIRED_INPUT"
    if state not in VALID_METRIC_STATES:
        metric_value = None

    decision_grade = bool(
        state in VALID_METRIC_STATES
        and str(metric["decision_grade_policy"]).startswith("DECISION_GRADE")
    )
    denominator_period = (
        str(denominator_row["period_end"]) if denominator_row is not None else None
    )
    denominator_available_from = max_timestamp(denominator_available)
    lineage_payload = {
        "symbol": cap["symbol"],
        "metric_id": metric_id,
        "market_as_of_date": cap.get("market_as_of_date"),
        "denominator_period": denominator_period,
        "fact_ids": sorted(set(input_fact_ids)),
        "capitalization_lineage": cap.get("lineage_id"),
    }
    return {
        "symbol": cap["symbol"],
        "name": cap.get("name"),
        "sector_profile": profile,
        "board": cap.get("board"),
        "metric_id": metric_id,
        "metric_name": metric["metric_name"],
        "metric_family": metric["metric_family"],
        "market_as_of_date": cap.get("market_as_of_date"),
        "market_cutoff_timestamp": cap.get("market_cutoff_timestamp"),
        "metric_value": metric_value,
        "output_unit": metric["output_unit"],
        "metric_state": state,
        "decision_grade_eligible": decision_grade,
        "denominator_period_end": denominator_period,
        "denominator_available_from": denominator_available_from,
        "required_inputs": metric["required_inputs"],
        "input_values_json": json.dumps(input_values, sort_keys=True, ensure_ascii=False),
        "input_states_json": json.dumps(input_states, sort_keys=True, ensure_ascii=False),
        "input_fact_ids_json": json.dumps(sorted(set(input_fact_ids)), ensure_ascii=False),
        "capitalization_source_id": cap.get("capitalization_source_id"),
        "source_release_id": source_release_id,
        "lineage_id": stable_hash(lineage_payload),
        "warning_codes": "|".join(sorted(set(warnings))) if warnings else "NONE",
        "authority": "DATA_AND_RESEARCH_EVIDENCE_ONLY",
        "trade_authority": "NONE",
    }


def build_event_contract_samples(registry: pd.DataFrame) -> pd.DataFrame:
    fixtures = [
        ("CASH_DIVIDEND", "ANNOUNCED"),
        ("CASH_DIVIDEND", "IMPLEMENTED"),
        ("BUYBACK", "ANNOUNCED"),
        ("BUYBACK", "COMPLETED"),
        ("SHARE_CANCELLATION", "COMPLETED"),
        ("PRIVATE_PLACEMENT", "REGULATORY_APPROVED"),
        ("PRIVATE_PLACEMENT", "COMPLETED"),
        ("STOCK_DIVIDEND_OR_SPLIT", "IMPLEMENTED"),
    ]
    index = {str(row.event_type): row for row in registry.itertuples(index=False)}
    rows = []
    for sequence, (event_type, stage) in enumerate(fixtures, start=1):
        policy = index[event_type]
        share_effective = stage == str(policy.effective_stage_for_share_count)
        yield_effective = stage == str(policy.effective_stage_for_shareholder_yield)
        event_id = stable_hash({"event_type": event_type, "stage": stage, "sequence": sequence})
        row = {
            "event_id": event_id,
            "symbol": "600000.SH",
            "event_type": event_type,
            "event_stage": stage,
            "announcement_date": "2026-01-01",
            "effective_date": "2026-02-01" if share_effective else None,
            "implementation_date": "2026-02-01" if stage == "IMPLEMENTED" else None,
            "completion_date": "2026-02-01" if stage == "COMPLETED" else None,
            "source_document_id": f"FMDL3DA_FIXTURE_{sequence:02d}",
            "source_location": "DETERMINISTIC_CONTRACT_FIXTURE",
            "cash_amount_total_cny": 1000000.0 if event_type == "CASH_DIVIDEND" else None,
            "cash_amount_per_share": 0.1 if event_type == "CASH_DIVIDEND" else None,
            "completed_cash_amount_cny": 1000000.0 if event_type == "BUYBACK" and stage == "COMPLETED" else None,
            "completed_share_count": 10000.0 if event_type in {"BUYBACK", "SHARE_CANCELLATION"} and stage == "COMPLETED" else None,
            "issued_share_count": 10000.0 if event_type == "PRIVATE_PLACEMENT" and stage == "COMPLETED" else None,
            "gross_proceeds_cny": 1000000.0 if event_type == "PRIVATE_PLACEMENT" and stage == "COMPLETED" else None,
            "converted_share_count": None,
            "share_multiplier": 1.1 if event_type == "STOCK_DIVIDEND_OR_SPLIT" and stage == "IMPLEMENTED" else None,
            "share_count_effective": share_effective,
            "shareholder_yield_effective": yield_effective,
            "lineage_id": event_id,
            "authority": "DATA_AND_RESEARCH_EVIDENCE_ONLY",
            "trade_authority": "NONE",
        }
        rows.append(row)
    return pd.DataFrame(rows)
