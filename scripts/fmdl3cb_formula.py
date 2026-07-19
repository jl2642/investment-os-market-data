from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import pandas as pd

from scripts.fmdl3cb_common import FACTOR_VERSION, VALID_STATES, combine_states, max_timestamp, stable_hash

_TOKEN_RE = re.compile(
    r"\s*([A-Za-z_][A-Za-z0-9_]*|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|[(),])"
)


@dataclass
class FormulaParser:
    tokens: list[str]
    position: int = 0

    @classmethod
    def from_text(cls, text: str) -> "FormulaParser":
        tokens = _TOKEN_RE.findall(text)
        if "".join(tokens) != re.sub(r"\s+", "", text):
            raise ValueError(f"unsupported formula syntax: {text}")
        return cls(tokens)

    def parse(self) -> Any:
        value = self._expr()
        if self.position != len(self.tokens):
            raise ValueError("trailing formula tokens")
        return value

    def _expr(self) -> Any:
        if self.position >= len(self.tokens):
            raise ValueError("unexpected end of formula")
        token = self.tokens[self.position]
        self.position += 1
        if re.fullmatch(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?", token):
            return ("CONST", float(token))
        if self.position < len(self.tokens) and self.tokens[self.position] == "(":
            self.position += 1
            args = []
            if self.position < len(self.tokens) and self.tokens[self.position] != ")":
                while True:
                    args.append(self._expr())
                    if self.tokens[self.position] == ",":
                        self.position += 1
                        continue
                    break
            if self.position >= len(self.tokens) or self.tokens[self.position] != ")":
                raise ValueError("missing closing parenthesis")
            self.position += 1
            return (token, args)
        return ("VAR", token)


@lru_cache(maxsize=256)
def parse_formula(text: str) -> Any:
    return FormulaParser.from_text(text).parse()


def evaluate_formula(tree: Any, values: dict[str, float | None]) -> float:
    op = tree[0]
    if op == "CONST":
        return float(tree[1])
    if op == "VAR":
        value = values.get(tree[1])
        if value is None or pd.isna(value):
            raise ValueError(f"missing input {tree[1]}")
        return float(value)
    args = [evaluate_formula(arg, values) for arg in tree[1]]
    if op == "ADD":
        return sum(args)
    if op == "SUBTRACT":
        return args[0] - args[1]
    if op == "MULTIPLY":
        return math.prod(args)
    if op == "DIVIDE":
        if abs(args[1]) <= 1e-12:
            raise ZeroDivisionError
        return args[0] / args[1]
    if op == "ABS":
        return abs(args[0])
    if op == "MAX":
        return max(args)
    if op == "MIN":
        return min(args)
    if op == "POWER":
        return args[0] ** args[1]
    raise ValueError(f"unsupported operator {op}")


def denominator_state(
    rule: str,
    inputs: dict[str, float | None],
) -> tuple[str | None, str | None]:
    eps = 1e-9
    mapping = {
        "POSITIVE_REVENUE": "revenue_ttm",
        "POSITIVE_AVERAGE_PARENT_EQUITY": "avg_parent_equity",
        "POSITIVE_AVERAGE_TOTAL_ASSETS": "avg_total_assets",
        "POSITIVE_PARENT_NET_INCOME": "net_income_parent_ttm",
        "POSITIVE_PRIOR_REVENUE": "prior_revenue_same_period",
        "POSITIVE_CURRENT_LIABILITIES": "total_current_liabilities",
        "POSITIVE_TOTAL_ASSETS": "total_assets",
        "POSITIVE_PARENT_EQUITY": "parent_equity",
        "POSITIVE_SHORT_TERM_DEBT": "short_term_debt",
        "POSITIVE_INTEREST_BEARING_DEBT": "interest_bearing_debt",
        "POSITIVE_PRETAX_INCOME": "pretax_income_ttm",
    }
    if rule == "SAME_SIGN_POSITIVE_BASE":
        if "net_income_parent_ttm" in inputs:
            current = inputs.get("net_income_parent_ttm")
            prior = inputs.get("prior_net_income_parent_same_period")
        else:
            current = inputs.get("cfo_ttm")
            prior = inputs.get("prior_cfo_same_period")
        if current is None or prior is None:
            return "MISSING_REQUIRED_INPUT", "MISSING_SIGN_COMPARISON_INPUT"
        if current <= eps or prior <= eps:
            return (
                "INVALID_SIGN_TRANSITION",
                "NON_POSITIVE_OR_SIGN_TRANSITION_GROWTH_BASE",
            )
        return None, None
    if rule == "POSITIVE_START_AND_END":
        pairs = [
            ("revenue_ttm", "revenue_3y_ago"),
            ("net_income_parent_ttm", "net_income_parent_3y_ago"),
        ]
        pair = next(
            ((current, prior) for current, prior in pairs if current in inputs and prior in inputs),
            None,
        )
        if pair is None or inputs.get(pair[0]) is None or inputs.get(pair[1]) is None:
            return "MISSING_REQUIRED_INPUT", "MISSING_CAGR_INPUT"
        if inputs[pair[0]] <= eps or inputs[pair[1]] <= eps:
            return "INVALID_SIGN_TRANSITION", "CAGR_START_OR_END_NOT_POSITIVE"
        return None, None
    token = mapping.get(rule)
    if token:
        value = inputs.get(token)
        if value is None:
            return "MISSING_REQUIRED_INPUT", f"MISSING_DENOMINATOR:{token}"
        if value <= eps:
            reason = (
                "ZERO_DEBT_NOT_APPLICABLE"
                if token in {"short_term_debt", "interest_bearing_debt"}
                and abs(value) <= eps
                else f"NON_POSITIVE_DENOMINATOR:{token}"
            )
            return "INVALID_DENOMINATOR", reason
    return None, None


def evaluate_factors_for_period(
    period_row: pd.Series,
    factor_dictionary,
    sector_profile: str,
    factor_version: str = FACTOR_VERSION,
    return_records: bool = False,
):
    states = json.loads(period_row["input_states_json"])
    available = json.loads(period_row["input_available_from_json"])
    fact_ids = json.loads(period_row["input_fact_ids_json"])
    rows: list[dict[str, Any]] = []
    factors = (
        factor_dictionary.to_dict("records")
        if isinstance(factor_dictionary, pd.DataFrame)
        else factor_dictionary
    )
    for factor in factors:
        factor_id = str(factor["factor_id"])
        required = str(factor["required_inputs"]).split("|")
        applicable = set(str(factor["applicable_sector_profiles"]).split("|"))
        warnings: list[str] = []
        quality = "VALID"
        if sector_profile == "UNRESOLVED":
            quality = "SECTOR_PROFILE_UNRESOLVED"
        elif sector_profile not in applicable:
            quality = "NOT_APPLICABLE_SECTOR"

        input_values = {token: period_row.get(token) for token in required}
        if quality == "VALID":
            quality = combine_states(
                [states.get(token, "MISSING_REQUIRED_INPUT") for token in required]
            )
            if quality == "VALID_WITH_WARNING":
                warnings.append("INPUT_RESTATEMENT_OR_COMPARABILITY_WARNING")

        if quality in VALID_STATES:
            synthetic = dict(input_values)
            debt_components = ["short_term_debt", "long_term_debt", "bonds_payable"]
            synthetic["interest_bearing_debt"] = (
                sum(float(input_values[token]) for token in debt_components)
                if all(input_values.get(token) is not None for token in debt_components)
                else None
            )
            invalid_state, invalid_reason = denominator_state(
                str(factor["denominator_rule"]),
                synthetic,
            )
            if invalid_state:
                quality = invalid_state
                if invalid_reason:
                    warnings.append(invalid_reason)

        value: float | None = None
        if quality in VALID_STATES:
            try:
                value = float(
                    evaluate_formula(
                        parse_formula(str(factor["formula"])),
                        input_values,
                    )
                )
                if not math.isfinite(value):
                    raise ValueError("non-finite result")
            except ZeroDivisionError:
                quality = "INVALID_DENOMINATOR"
                warnings.append("DIVISION_BY_ZERO")
                value = None
            except (ValueError, OverflowError, TypeError) as exc:
                quality = "MISSING_REQUIRED_INPUT"
                warnings.append(f"FORMULA_EVALUATION:{type(exc).__name__}")
                value = None

        ranking_posture = str(factor["ranking_posture"])
        if quality == "VALID" and ranking_posture == "ELIGIBLE_WHEN_VALID":
            rank_eligibility = "ELIGIBLE"
        elif quality == "VALID_WITH_WARNING" and ranking_posture == "ELIGIBLE_WHEN_VALID":
            rank_eligibility = "CONDITIONAL"
        else:
            rank_eligibility = "INELIGIBLE"

        as_of = (
            max_timestamp([available.get(token) for token in required])
            if quality in VALID_STATES
            else None
        )
        lineage_ids = sorted(
            {
                fact_id
                for token in required
                for fact_id in fact_ids.get(token, [])
                if fact_id
            }
        )
        rows.append(
            {
                "factor_row_id": stable_hash(
                    {
                        "symbol": period_row["symbol"],
                        "factor_id": factor_id,
                        "period_end": period_row["period_end"],
                        "factor_version": factor_version,
                        "available_from": as_of,
                    }
                ),
                "symbol": period_row["symbol"],
                "factor_id": factor_id,
                "factor_name": factor["factor_name"],
                "family_id": factor["family_id"],
                "factor_version": factor_version,
                "period_end": period_row["period_end"],
                "fiscal_period_type": period_row["fiscal_period_type"],
                "as_of_timestamp": as_of,
                "factor_value": value,
                "output_unit": factor["output_unit"],
                "economic_direction": factor["economic_direction"],
                "sector_profile": sector_profile,
                "quality_state": quality,
                "rank_eligibility": rank_eligibility,
                "build_state": factor["build_state"],
                "warning_codes": (
                    "|".join(sorted(set(warnings))) if warnings else "NONE"
                ),
                "required_inputs": factor["required_inputs"],
                "input_fact_ids_json": json.dumps(lineage_ids, ensure_ascii=False),
                "lineage_id": stable_hash(
                    {
                        "symbol": period_row["symbol"],
                        "factor_id": factor_id,
                        "period_end": period_row["period_end"],
                        "inputs": lineage_ids,
                    }
                ),
                "authority": "DATA_AND_RESEARCH_EVIDENCE_ONLY",
                "trade_authority": "NONE",
            }
        )
    return rows if return_records else pd.DataFrame(rows)
