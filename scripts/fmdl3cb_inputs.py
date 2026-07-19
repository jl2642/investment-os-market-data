from __future__ import annotations

import json
from typing import Any

import pandas as pd

from scripts.fmdl3cb_common import VALID_STATES, combine_states, max_timestamp


def infer_sector_profile(frame: pd.DataFrame) -> str:
    fields = set(frame.get("line_item_id", pd.Series(dtype=str)).dropna().astype(str))
    bank = {"net_interest_income", "loans_advances", "customer_deposits"}
    insurance = {"insurance_revenue", "insurance_contract_liabilities"}
    brokerage = {"fee_commission_net"}
    general = {
        "revenue",
        "cogs",
        "operating_income",
        "cfo",
        "total_assets",
        "parent_equity",
    }
    if fields & insurance:
        return "INSURANCE"
    if fields & bank:
        return "BANK"
    if fields & brokerage:
        return "SECURITIES_AND_BROKERAGE"
    if fields & general:
        return "GENERAL_NON_FINANCIAL"
    return "UNRESOLVED"


def input_state(
    row: pd.Series | None,
    period_status: pd.Series | None,
) -> tuple[float | None, str, str | None, str | None]:
    if row is None:
        return None, "MISSING_REQUIRED_INPUT", None, None
    quality = str(row.get("record_quality") or "")
    eligible = bool(row.get("decision_grade_eligible"))
    fact_id = str(row.get("normalized_fact_id") or "")
    if not eligible:
        if "CONFLICT" in quality:
            return None, "CONFLICTED_INPUT", None, fact_id
        return None, "QUARANTINED_INPUT", None, fact_id
    if period_status is None:
        return None, "QUARANTINED_INPUT", None, fact_id
    if str(period_status.get("restatement_status") or "") == (
        "UNRESOLVED_NO_CANONICAL_PERIODIC_DOCUMENT"
    ):
        return None, "QUARANTINED_INPUT", None, fact_id
    value = pd.to_numeric(pd.Series([row.get("normalized_value")]), errors="coerce").iloc[0]
    if pd.isna(value):
        return None, "MISSING_REQUIRED_INPUT", None, fact_id
    authoritative = period_status.get("authoritative_available_from")
    available = authoritative if pd.notna(authoritative) else row.get("available_from")
    state = (
        "VALID_WITH_WARNING"
        if str(period_status.get("restatement_status")) == "RESTATED_OR_CORRECTED"
        else "VALID"
    )
    return float(value), state, str(available) if pd.notna(available) else None, fact_id


def period_key(year: int, fiscal_period_type: str) -> str:
    dates = {"Q1": "03-31", "H1": "06-30", "Q3": "09-30", "FY": "12-31"}
    suffix = dates.get(fiscal_period_type)
    return f"{year}-{suffix}" if suffix else ""


def lookup(
    index: dict[tuple[str, str], pd.Series],
    line_item: str,
    period_end: str,
) -> pd.Series | None:
    return index.get((line_item, period_end))


def component_comparability(
    rows: list[pd.Series | None],
    allow_basis_mixture: bool = False,
) -> str:
    valid = [row for row in rows if row is not None]
    if not valid:
        return "MISSING_REQUIRED_INPUT"
    hard_fields = ["currency", "units"] + ([] if allow_basis_mixture else ["basis"])
    for field in hard_fields:
        values = {str(row.get(field)) for row in valid if pd.notna(row.get(field))}
        if len(values) > 1:
            return "NON_COMPARABLE_INPUT"
    for field in ["line_item_original", "source_route_id"]:
        values = {str(row.get(field)) for row in valid if pd.notna(row.get(field))}
        if len(values) > 1:
            return "VALID_WITH_WARNING"
    return "VALID"


def bridge_comparability_state(
    bridge: pd.DataFrame | None,
    line_item_id: str,
    fiscal_period_type: str,
    current_period: str,
    prior_period: str,
) -> str:
    if bridge is None or bridge.empty:
        return "VALID"
    match = bridge[
        bridge["line_item_id"].astype(str).eq(str(line_item_id))
        & bridge["fiscal_period_type"].astype(str).eq(str(fiscal_period_type))
        & bridge["current_period"].astype(str).eq(str(current_period))
        & bridge["prior_period"].astype(str).eq(str(prior_period))
    ]
    if match.empty:
        return "VALID"
    statuses = set(match["comparison_status"].astype(str))
    if "NOT_COMPARABLE" in statuses:
        return "NON_COMPARABLE_INPUT"
    if "COMPARABLE_WITH_WARNING" in statuses:
        return "VALID_WITH_WARNING"
    return "VALID"


def _flow_token(
    index: dict[tuple[str, str], pd.Series],
    status_index: dict[str, pd.Series],
    line_item: str,
    period: str,
    fiscal_type: str,
) -> tuple[float | None, str, str | None, list[str]]:
    year = pd.Timestamp(period).year
    if fiscal_type == "FY":
        components = [(lookup(index, line_item, period), status_index.get(period), 1.0)]
    elif fiscal_type in {"Q1", "H1", "Q3"}:
        prior_fy = period_key(year - 1, "FY")
        prior_same = period_key(year - 1, fiscal_type)
        components = [
            (lookup(index, line_item, period), status_index.get(period), 1.0),
            (lookup(index, line_item, prior_fy), status_index.get(prior_fy), 1.0),
            (lookup(index, line_item, prior_same), status_index.get(prior_same), -1.0),
        ]
    else:
        components = [(None, None, 1.0)]
    values: list[float] = []
    states: list[str] = []
    available: list[str | None] = []
    ids: list[str] = []
    for fact, status, sign in components:
        value, state, timestamp, fact_id = input_state(fact, status)
        states.append(state)
        available.append(timestamp)
        if fact_id:
            ids.append(fact_id)
        if value is not None:
            values.append(sign * value)
    state = combine_states(states)
    if state in VALID_STATES:
        state = combine_states(
            [
                state,
                component_comparability(
                    [fact for fact, _, _ in components],
                    allow_basis_mixture=True,
                ),
            ]
        )
    value = float(sum(values)) if state in VALID_STATES and len(values) == len(components) else None
    return value, state, max_timestamp(available), ids


def build_period_inputs(
    symbol_facts: pd.DataFrame,
    period_status: pd.DataFrame,
    flow_map: dict[str, str],
    balance_map: dict[str, str],
    comparison_bridge: pd.DataFrame | None = None,
) -> pd.DataFrame:
    facts = symbol_facts.copy()
    facts["period_end"] = facts["period_end"].astype(str)
    facts = facts.sort_values(
        ["line_item_id", "period_end", "available_from"],
        na_position="last",
    )
    facts = facts.groupby(["line_item_id", "period_end"], as_index=False).tail(1)
    index = {(str(row.line_item_id), str(row.period_end)): row for _, row in facts.iterrows()}

    statuses = period_status.copy()
    statuses["report_period_end"] = statuses["report_period_end"].astype(str)
    status_index = {str(row.report_period_end): row for _, row in statuses.iterrows()}

    rows: list[dict[str, Any]] = []
    for period in sorted(set(facts["period_end"])):
        period_facts = facts[facts["period_end"].eq(period)]
        fiscal_type = (
            str(period_facts["fiscal_period_type"].dropna().iloc[0])
            if period_facts["fiscal_period_type"].notna().any()
            else "STUB"
        )
        year = pd.Timestamp(period).year
        row: dict[str, Any] = {
            "symbol": str(facts.iloc[0]["symbol"]),
            "period_end": period,
            "fiscal_period_type": fiscal_type,
        }
        states: dict[str, str] = {}
        available: dict[str, str | None] = {}
        fact_ids: dict[str, list[str]] = {}

        for token, line_item in balance_map.items():
            value, state, timestamp, fact_id = input_state(
                lookup(index, line_item, period),
                status_index.get(period),
            )
            row[token] = value
            states[token] = state
            available[token] = timestamp
            fact_ids[token] = [fact_id] if fact_id else []

        for token, line_item in flow_map.items():
            value, state, timestamp, ids = _flow_token(
                index,
                status_index,
                line_item,
                period,
                fiscal_type,
            )
            row[token] = value
            states[token] = state
            available[token] = timestamp
            fact_ids[token] = ids

        for token, source in {
            "avg_total_assets": "total_assets",
            "avg_parent_equity": "parent_equity",
        }.items():
            prior_period = period_key(year - 1, fiscal_type)
            current_value = row.get(source)
            current_state = states.get(source, "MISSING_REQUIRED_INPUT")
            prior_fact = lookup(index, source, prior_period)
            prior_value, prior_state, prior_available, prior_fact_id = input_state(
                prior_fact,
                status_index.get(prior_period),
            )
            state = combine_states([current_state, prior_state])
            if state in VALID_STATES:
                state = combine_states(
                    [
                        state,
                        component_comparability(
                            [lookup(index, source, period), prior_fact]
                        ),
                        bridge_comparability_state(
                            comparison_bridge,
                            source,
                            fiscal_type,
                            period,
                            prior_period,
                        ),
                    ]
                )
            row[token] = (
                (float(current_value) + float(prior_value)) / 2.0
                if state in VALID_STATES
                and current_value is not None
                and prior_value is not None
                else None
            )
            states[token] = state
            available[token] = max_timestamp([available.get(source), prior_available])
            fact_ids[token] = fact_ids.get(source, []) + (
                [prior_fact_id] if prior_fact_id else []
            )

        row["input_states_json"] = json.dumps(states, sort_keys=True, ensure_ascii=False)
        row["input_available_from_json"] = json.dumps(
            available,
            sort_keys=True,
            ensure_ascii=False,
        )
        row["input_fact_ids_json"] = json.dumps(
            fact_ids,
            sort_keys=True,
            ensure_ascii=False,
        )
        rows.append(row)

    out = pd.DataFrame(rows).sort_values("period_end").reset_index(drop=True) if rows else pd.DataFrame()
    if out.empty:
        return out

    state_maps = [json.loads(value) for value in out["input_states_json"]]
    available_maps = [json.loads(value) for value in out["input_available_from_json"]]
    fact_id_maps = [json.loads(value) for value in out["input_fact_ids_json"]]
    period_lookup = {
        (str(row.period_end), str(row.fiscal_period_type)): index
        for index, row in out.iterrows()
    }

    lag_specs = {
        "prior_revenue_same_period": ("revenue_ttm", "revenue", 1),
        "prior_net_income_parent_same_period": (
            "net_income_parent_ttm",
            "net_income_parent",
            1,
        ),
        "prior_cfo_same_period": ("cfo_ttm", "cfo", 1),
        "revenue_3y_ago": ("revenue_ttm", "revenue", 3),
        "net_income_parent_3y_ago": (
            "net_income_parent_ttm",
            "net_income_parent",
            3,
        ),
    }
    for row_index, current in out.iterrows():
        year = pd.Timestamp(str(current.period_end)).year
        fiscal = str(current.fiscal_period_type)
        for token, (source, line_item, lag) in lag_specs.items():
            if source not in out.columns:
                out.at[row_index, token] = None
                state_maps[row_index][token] = "MISSING_REQUIRED_INPUT"
                available_maps[row_index][token] = None
                fact_id_maps[row_index][token] = []
                continue
            prior_period = period_key(year - lag, fiscal)
            prior_index = period_lookup.get((prior_period, fiscal))
            if prior_index is None:
                out.at[row_index, token] = None
                state_maps[row_index][token] = "MISSING_REQUIRED_INPUT"
                available_maps[row_index][token] = None
                fact_id_maps[row_index][token] = []
                continue
            out.at[row_index, token] = out.at[prior_index, source]
            prior_states = json.loads(out.at[prior_index, "input_states_json"])
            prior_available = json.loads(
                out.at[prior_index, "input_available_from_json"]
            )
            prior_ids = json.loads(out.at[prior_index, "input_fact_ids_json"])
            state = prior_states.get(source, "MISSING_REQUIRED_INPUT")
            if state in VALID_STATES:
                chain = []
                for step in range(lag):
                    chain.append(
                        bridge_comparability_state(
                            comparison_bridge,
                            line_item,
                            fiscal,
                            period_key(year - step, fiscal),
                            period_key(year - step - 1, fiscal),
                        )
                    )
                state = combine_states([state] + chain)
            state_maps[row_index][token] = state
            available_maps[row_index][token] = prior_available.get(source)
            fact_id_maps[row_index][token] = prior_ids.get(source, [])

        margin_specs = {
            "prior_gross_margin_same_period": (
                "revenue_ttm",
                "cogs_ttm",
                ["revenue", "cogs"],
            ),
            "prior_operating_margin_same_period": (
                "revenue_ttm",
                "operating_income_ttm",
                ["revenue", "operating_income"],
            ),
        }
        for token, (revenue_token, other_token, line_items) in margin_specs.items():
            if revenue_token not in out.columns or other_token not in out.columns:
                out.at[row_index, token] = None
                state_maps[row_index][token] = "MISSING_REQUIRED_INPUT"
                available_maps[row_index][token] = None
                fact_id_maps[row_index][token] = []
                continue
            prior_period = period_key(year - 1, fiscal)
            prior_index = period_lookup.get((prior_period, fiscal))
            if prior_index is None:
                out.at[row_index, token] = None
                state_maps[row_index][token] = "MISSING_REQUIRED_INPUT"
                available_maps[row_index][token] = None
                fact_id_maps[row_index][token] = []
                continue
            revenue = out.at[prior_index, revenue_token]
            other = out.at[prior_index, other_token]
            prior_states = json.loads(out.at[prior_index, "input_states_json"])
            state = combine_states(
                [
                    prior_states.get(revenue_token, "MISSING_REQUIRED_INPUT"),
                    prior_states.get(other_token, "MISSING_REQUIRED_INPUT"),
                ]
            )
            if state in VALID_STATES and revenue is not None and float(revenue) > 0:
                out.at[row_index, token] = (
                    (float(revenue) - float(other)) / float(revenue)
                    if token.startswith("prior_gross")
                    else float(other) / float(revenue)
                )
                bridge_states = [
                    bridge_comparability_state(
                        comparison_bridge,
                        line_item,
                        fiscal,
                        str(current.period_end),
                        prior_period,
                    )
                    for line_item in line_items
                ]
                state = combine_states([state] + bridge_states)
                if state not in VALID_STATES:
                    out.at[row_index, token] = None
            else:
                out.at[row_index, token] = None
                if state in VALID_STATES:
                    state = "INVALID_DENOMINATOR"
            prior_available = json.loads(
                out.at[prior_index, "input_available_from_json"]
            )
            prior_ids = json.loads(out.at[prior_index, "input_fact_ids_json"])
            state_maps[row_index][token] = state
            available_maps[row_index][token] = max_timestamp(
                [
                    prior_available.get(revenue_token),
                    prior_available.get(other_token),
                ]
            )
            fact_id_maps[row_index][token] = prior_ids.get(
                revenue_token,
                [],
            ) + prior_ids.get(other_token, [])

    out["input_states_json"] = [
        json.dumps(value, sort_keys=True, ensure_ascii=False) for value in state_maps
    ]
    out["input_available_from_json"] = [
        json.dumps(value, sort_keys=True, ensure_ascii=False)
        for value in available_maps
    ]
    out["input_fact_ids_json"] = [
        json.dumps(value, sort_keys=True, ensure_ascii=False) for value in fact_id_maps
    ]
    return out
