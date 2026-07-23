#!/usr/bin/env python3
"""Deterministic FMDL-7C portfolio, simulation and rule-calibration acceptance."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
import zipfile
from copy import deepcopy
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable

PHASE_ID = "FMDL-7C"
EXIT_STATUS = "FMDL7C_PORTFOLIO_SIMULATION_ATTRIBUTION_AND_RULE_CALIBRATION_ACCEPTED"
NEXT_GATE = "FMDL-7D_SCHEDULED_OPERATIONS_MONITORING_STALENESS_AND_COST_CONTROLS"
CONTRACT_PATH = Path("config/fmdl7c_portfolio_attribution_contract.json")

SHARD_DOMAINS = (
    "REAL_ACCOUNT_POSITION_ATTRIBUTION",
    "REAL_ACCOUNT_SUMMARY",
    "SIMULATION_POSITION_ATTRIBUTION",
    "SIMULATION_ACCOUNT_SUMMARY",
    "CANDIDATE_CORE_REVIEW",
    "ACTION_REVIEW_RECORD",
    "RULE_CALIBRATION_PROPOSAL",
)

MONEY = Decimal("0.01")
PCT = Decimal("0.0001")


class ContractError(RuntimeError):
    """Raised when a frozen source or acceptance boundary is violated."""


def decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def money(value: Any) -> Decimal:
    return decimal(value).quantize(MONEY, rounding=ROUND_HALF_UP)


def pct(value: Any) -> Decimal:
    return decimal(value).quantize(PCT, rounding=ROUND_HALF_UP)


def number(value: Decimal) -> int | float:
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def canonicalize(value: Any) -> Any:
    if isinstance(value, Decimal):
        return number(value)
    if isinstance(value, dict):
        return {str(key): canonicalize(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [canonicalize(item) for item in value]
    if isinstance(value, set):
        return sorted(canonicalize(item) for item in value)
    return value


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(canonicalize(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def stable_json(value: Any) -> str:
    return json.dumps(canonicalize(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(value))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]], *, sort_key: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(rows, key=lambda row: (str(row.get(sort_key, "")), stable_json(row)))
    with path.open("w", encoding="utf-8", newline="") as handle:
        for row in ordered:
            handle.write(stable_json(row) + "\n")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def csv_value(value: Any) -> Any:
    value = canonicalize(value)
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    return value


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field)) for field in fieldnames})


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def record_hash(*parts: Any) -> str:
    return sha256_bytes("|".join(stable_json(part) for part in parts).encode("utf-8"))


def z6(value: Any) -> str:
    return str(value).strip().zfill(6)


def check_field(errors: list[str], payload: dict[str, Any], field: str, expected: Any, code: str) -> None:
    actual = payload.get(field, object())
    if actual != expected:
        errors.append(f"{code}:{field}:{actual!r}!={expected!r}")


def validate_contract(repo_root: Path) -> tuple[dict[str, Any], list[str], dict[str, str]]:
    path = repo_root / CONTRACT_PATH
    if not path.is_file():
        return {}, ["CONTRACT_MISSING"], {}
    contract = read_json(path)
    errors: list[str] = []
    source_hashes: dict[str, str] = {"contract": sha256_file(path)}

    if contract.get("phase_id") != PHASE_ID:
        errors.append("CONTRACT_PHASE_ID")
    if contract.get("required_exit_status") != EXIT_STATUS:
        errors.append("CONTRACT_EXIT_STATUS")
    if contract.get("next_gate") != NEXT_GATE:
        errors.append("CONTRACT_NEXT_GATE")
    if contract.get("trade_authority") != "NONE":
        errors.append("CONTRACT_TRADE_AUTHORITY")

    entry = contract.get("entry_gate", {})
    entry_path = repo_root / str(entry.get("path", ""))
    if not entry_path.is_file():
        errors.append("ENTRY_GATE_MISSING")
    else:
        pointer = read_json(entry_path)
        source_hashes["entry_gate"] = sha256_file(entry_path)
        for field, expected_key in (
            ("phase_id", "required_phase_id"),
            ("release_id", "required_release_id"),
            ("release_sequence", "required_release_sequence"),
            ("status", "required_status"),
            ("next_gate", "required_next_gate"),
            ("trade_authority", "required_trade_authority"),
        ):
            check_field(errors, pointer, field, entry.get(expected_key), "ENTRY_GATE")

    bindings = contract.get("source_bindings", {})
    if set(bindings) != {
        "investment_state_binding",
        "operating_state_review",
        "a_share_quote_snapshot",
        "fund_nav_snapshot",
        "fmdl4d_feedback_proposals",
        "fmdl4d_attribution_registry",
    }:
        errors.append("SOURCE_BINDING_SET")

    loaded: dict[str, Any] = {}
    for name, spec in bindings.items():
        source_path = repo_root / str(spec.get("path", ""))
        if not source_path.is_file():
            errors.append(f"SOURCE_MISSING:{name}")
            continue
        source_hashes[name] = sha256_file(source_path)
        if source_path.suffix == ".json":
            loaded[name] = read_json(source_path)
        elif source_path.suffix == ".jsonl":
            loaded[name] = read_jsonl(source_path)
        elif source_path.suffix == ".csv":
            loaded[name] = read_csv(source_path)
        else:
            errors.append(f"SOURCE_TYPE_UNSUPPORTED:{name}")

    binding = loaded.get("investment_state_binding", {})
    spec = bindings.get("investment_state_binding", {})
    if binding:
        checks = {
            "source_release_sequence": spec.get("required_source_release_sequence"),
            "source_as_of": spec.get("required_source_as_of"),
            "trade_authority": spec.get("required_trade_authority"),
        }
        for field, expected in checks.items():
            check_field(errors, binding, field, expected, "STATE_BINDING")
        if len(binding.get("real_holdings", [])) != spec.get("required_real_holding_count"):
            errors.append("STATE_BINDING_REAL_HOLDING_COUNT")
        if len(binding.get("simulation_holdings", [])) != spec.get("required_simulation_holding_count"):
            errors.append("STATE_BINDING_SIMULATION_HOLDING_COUNT")
        if len(binding.get("candidate_core_20", [])) != spec.get("required_candidate_core_count"):
            errors.append("STATE_BINDING_CANDIDATE_COUNT")
        if len(binding.get("active_memo_price_thresholds", {})) != spec.get("required_active_memo_count"):
            errors.append("STATE_BINDING_ACTIVE_MEMO_COUNT")
        if decimal(binding.get("simulation_original_capital", 0)) != decimal(spec.get("required_simulation_original_capital", 0)):
            errors.append("STATE_BINDING_ORIGINAL_CAPITAL")
        if binding.get("cash_policy") != "BROKER_CASH_IS_EXECUTION_BALANCE_NOT_STRATEGIC_ASSET_BUCKET":
            errors.append("STATE_BINDING_CASH_POLICY")

    action = loaded.get("operating_state_review", {})
    spec = bindings.get("operating_state_review", {})
    if action:
        check_field(errors, action, "as_of", spec.get("required_as_of"), "ACTION_REVIEW")
        check_field(errors, action, "trade_authority", spec.get("required_trade_authority"), "ACTION_REVIEW")
        nested_checks = [
            ("real_account", "total_assets", "required_real_total_assets"),
            ("simulation", "total_assets", "required_simulation_total_assets"),
            ("simulation", "market_value", "required_simulation_market_value"),
            ("simulation", "available_cash", "required_simulation_cash"),
            ("simulation", "account_total_pnl", "required_simulation_total_pnl"),
        ]
        for domain, field, expected_key in nested_checks:
            actual = decimal(action.get(domain, {}).get(field, 0))
            expected = decimal(spec.get(expected_key, 0))
            if actual != expected:
                errors.append(f"ACTION_REVIEW:{domain}.{field}")
        if action.get("real_account", {}).get("decision") != spec.get("required_real_decision"):
            errors.append("ACTION_REVIEW_REAL_DECISION")
        if action.get("real_account", {}).get("immediate_trade_proposal_count") != 0:
            errors.append("ACTION_REVIEW_REAL_TRADE_PROPOSAL")
        if action.get("simulation", {}).get("immediate_trade_proposal_count") != 0:
            errors.append("ACTION_REVIEW_SIM_TRADE_PROPOSAL")

    quotes = loaded.get("a_share_quote_snapshot", [])
    spec = bindings.get("a_share_quote_snapshot", {})
    if quotes:
        if len(quotes) != spec.get("required_row_count"):
            errors.append("QUOTE_ROW_COUNT")
        if len({z6(row.get("symbol")) for row in quotes}) != len(quotes):
            errors.append("QUOTE_DUPLICATE_SYMBOL")
        if any(row.get("quote_date") != spec.get("required_quote_date") for row in quotes):
            errors.append("QUOTE_DATE")
        if any(row.get("validation_status") != spec.get("required_validation_status") for row in quotes):
            errors.append("QUOTE_VALIDATION")

    navs = loaded.get("fund_nav_snapshot", [])
    spec = bindings.get("fund_nav_snapshot", {})
    if navs:
        if len(navs) != spec.get("required_row_count"):
            errors.append("NAV_ROW_COUNT")
        if any(row.get("validation_status") != spec.get("required_validation_status") for row in navs):
            errors.append("NAV_VALIDATION")
        target = date.fromisoformat(contract["as_of_date"])
        maximum_age = int(spec.get("maximum_nav_age_days", 0))
        for row in navs:
            age = (target - date.fromisoformat(row["nav_date"])).days
            if age < 0 or age > maximum_age:
                errors.append(f"NAV_AGE:{row.get('fund_code')}")

    feedback = loaded.get("fmdl4d_feedback_proposals", [])
    spec = bindings.get("fmdl4d_feedback_proposals", {})
    if feedback:
        if len(feedback) != spec.get("required_record_count"):
            errors.append("FEEDBACK_RECORD_COUNT")
        applied = sum(bool(row.get("rule_mutation_applied")) for row in feedback)
        if applied != spec.get("required_applied_rule_mutation_count"):
            errors.append("FEEDBACK_RULE_MUTATION_COUNT")
        if any(row.get("trade_authority") != spec.get("required_trade_authority") for row in feedback):
            errors.append("FEEDBACK_TRADE_AUTHORITY")

    attribution = loaded.get("fmdl4d_attribution_registry", [])
    spec = bindings.get("fmdl4d_attribution_registry", {})
    if attribution:
        if len(attribution) != spec.get("required_record_count"):
            errors.append("ATTRIBUTION_RECORD_COUNT")
        if any(row.get("exposure_status") != spec.get("required_exposure_status") for row in attribution):
            errors.append("ATTRIBUTION_EXPOSURE_STATUS")
        if any(row.get("trade_authority") != spec.get("required_trade_authority") for row in attribution):
            errors.append("ATTRIBUTION_TRADE_AUTHORITY")
        if any(row.get("gross_return") not in (None, "") for row in attribution):
            errors.append("ATTRIBUTION_FABRICATED_RETURN")

    scope = contract.get("scope", {})
    required_true = [
        "accepted_snapshot_attribution_authorized",
        "portfolio_and_simulation_diagnostic_authorized",
        "candidate_state_review_authorized",
        "action_recommendation_register_authorized",
        "rule_calibration_proposal_authorized",
    ]
    required_false = [
        "new_market_data_refresh_authorized",
        "post_as_of_state_fabrication_authorized",
        "live_trade_recommendation_authorized",
        "candidate_pool_mutation_authorized",
        "simulation_book_mutation_authorized",
        "real_account_mutation_authorized",
        "rule_mutation_authorized",
        "canonical_repack_authorized",
        "brokerage_or_order_authorized",
    ]
    for field in required_true:
        if scope.get(field) is not True:
            errors.append(f"SCOPE_REQUIRED_TRUE:{field}")
    for field in required_false:
        if scope.get(field) is not False:
            errors.append(f"SCOPE_REQUIRED_FALSE:{field}")

    if len(contract.get("rule_calibration_proposals", [])) != 8:
        errors.append("RULE_PROPOSAL_COUNT")
    if len({row.get("proposal_id") for row in contract.get("rule_calibration_proposals", [])}) != 8:
        errors.append("RULE_PROPOSAL_IDENTITY")
    if len(contract.get("failure_injections", [])) != 8:
        errors.append("FAILURE_INJECTION_COUNT")

    gates = contract.get("acceptance_gates", {})
    static_expected = {
        "source_binding_count": 6,
        "real_holding_count": 7,
        "real_stock_etf_count": 4,
        "real_bond_fund_count": 3,
        "simulation_holding_count": 16,
        "simulation_positive_position_count": 10,
        "simulation_negative_position_count": 6,
        "simulation_hard_review_count": 2,
        "simulation_no_add_count": 4,
        "candidate_core_count": 20,
        "active_memo_count": 6,
        "active_memo_trigger_met_count": 0,
        "candidate_simulation_overlap_count": 13,
        "action_recommendation_count": 6,
        "rule_calibration_proposal_count": 8,
        "failure_injection_count": 8,
        "gate_count": 24,
        "logical_shard_domain_count": 7,
        "bucket_count": 64,
        "logical_shard_count": 448,
        "investment_recommendation_count": 0,
        "candidate_pool_mutations": 0,
        "simulation_book_mutations": 0,
        "real_account_mutations": 0,
        "rule_mutations": 0,
        "orders": 0,
    }
    for field, expected in static_expected.items():
        if gates.get(field) != expected:
            errors.append(f"ACCEPTANCE_GATE:{field}")
    if contract.get("storage_contract", {}).get("release_sequence") != 51:
        errors.append("RELEASE_SEQUENCE")

    return contract, sorted(set(errors)), source_hashes


def load_sources(repo_root: Path, contract: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, spec in contract["source_bindings"].items():
        path = repo_root / spec["path"]
        if path.suffix == ".json":
            result[name] = read_json(path)
        elif path.suffix == ".jsonl":
            result[name] = read_jsonl(path)
        elif path.suffix == ".csv":
            result[name] = read_csv(path)
        else:
            raise ContractError(f"unsupported source: {path}")
    return result


def build_real_account(sources: dict[str, Any], contract: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    binding = sources["investment_state_binding"]
    action = sources["operating_state_review"]["real_account"]
    quotes = {z6(row["symbol"]): row for row in sources["a_share_quote_snapshot"]}
    navs = {z6(row["fund_code"]): row for row in sources["fund_nav_snapshot"]}

    records: list[dict[str, Any]] = []
    for holding in binding["real_holdings"]:
        code = z6(holding["code"])
        quantity = decimal(holding["quantity_or_shares"])
        if code in navs:
            asset_class = "BOND_FUND"
            snapshot = navs[code]
            price = decimal(snapshot["unit_nav"])
            price_as_of = snapshot["nav_date"]
            provider = snapshot["provider"]
            cost_basis = money(holding["cost_price_or_cost"])
            cost_basis_method = "RECORDED_TOTAL_COST"
        elif code in quotes:
            asset_class = "STOCK_ETF"
            snapshot = quotes[code]
            price = decimal(snapshot["close"])
            price_as_of = snapshot["quote_date"]
            provider = snapshot["provider"]
            cost_basis = money(quantity * decimal(holding["cost_price_or_cost"]))
            cost_basis_method = "QUANTITY_TIMES_RECORDED_UNIT_COST"
        else:
            raise ContractError(f"REAL_PRICE_MISSING:{code}")
        market_value = money(quantity * price)
        pnl = money(market_value - cost_basis)
        return_pct = pct((pnl / cost_basis) * 100) if cost_basis else Decimal("0")
        base = {
            "security_code": code,
            "security_name": holding["holding_name"],
            "asset_class": asset_class,
            "quantity_or_shares": quantity,
            "recorded_cost_input": decimal(holding["cost_price_or_cost"]),
            "cost_basis_method": cost_basis_method,
            "estimated_cost_basis": cost_basis,
            "accepted_snapshot_price_or_nav": price,
            "price_or_nav_as_of": price_as_of,
            "price_provider": provider,
            "estimated_market_value": market_value,
            "estimated_mark_to_cost_pnl": pnl,
            "estimated_mark_to_cost_return_pct": return_pct,
            "contribution_sign": "POSITIVE" if pnl > 0 else "NEGATIVE" if pnl < 0 else "ZERO",
            "total_return_claimed": False,
            "attribution_scope": "UNREALIZED_MARK_TO_RECORDED_COST_ESTIMATE_NOT_VERIFIED_TOTAL_RETURN",
            "automatic_action_authorized": False,
            "trade_authority": "NONE",
        }
        base["record_id"] = "FMDL7C-REAL-" + record_hash(code, base)[:20]
        records.append(base)

    records.sort(key=lambda row: row["security_code"])
    execution_cash = money(binding["real_execution_cash"])
    total_market_value = money(sum(decimal(row["estimated_market_value"]) for row in records))
    total_assets = money(total_market_value + execution_cash)
    invested_cost = money(sum(decimal(row["estimated_cost_basis"]) for row in records))
    mark_to_cost_pnl = money(sum(decimal(row["estimated_mark_to_cost_pnl"]) for row in records))
    stock_value = money(sum(decimal(row["estimated_market_value"]) for row in records if row["asset_class"] == "STOCK_ETF"))
    bond_value = money(sum(decimal(row["estimated_market_value"]) for row in records if row["asset_class"] == "BOND_FUND"))
    stock_pnl = money(sum(decimal(row["estimated_mark_to_cost_pnl"]) for row in records if row["asset_class"] == "STOCK_ETF"))
    bond_pnl = money(sum(decimal(row["estimated_mark_to_cost_pnl"]) for row in records if row["asset_class"] == "BOND_FUND"))
    positive = money(sum(decimal(row["estimated_mark_to_cost_pnl"]) for row in records if decimal(row["estimated_mark_to_cost_pnl"]) > 0))
    negative = money(sum(decimal(row["estimated_mark_to_cost_pnl"]) for row in records if decimal(row["estimated_mark_to_cost_pnl"]) < 0))

    for row in records:
        row["portfolio_weight_pct"] = pct(decimal(row["estimated_market_value"]) / total_assets * 100)

    summary = {
        "record_id": "FMDL7C-REAL-SUMMARY-" + record_hash(total_assets, invested_cost, mark_to_cost_pnl)[:20],
        "state_as_of": sources["operating_state_review"]["as_of"],
        "state_authority": "LAST_KNOWN_GOOD_NOT_CONFIRMED_CURRENT_AFTER_AS_OF",
        "holding_count": len(records),
        "stock_etf_count": sum(row["asset_class"] == "STOCK_ETF" for row in records),
        "bond_fund_count": sum(row["asset_class"] == "BOND_FUND" for row in records),
        "stock_etf_value": stock_value,
        "bond_fund_value": bond_value,
        "execution_cash": execution_cash,
        "total_assets": total_assets,
        "invested_cost_estimate": invested_cost,
        "mark_to_cost_pnl_estimate": mark_to_cost_pnl,
        "mark_to_cost_return_pct": pct(mark_to_cost_pnl / invested_cost * 100),
        "stock_etf_pnl_estimate": stock_pnl,
        "bond_fund_pnl_estimate": bond_pnl,
        "positive_contribution": positive,
        "negative_contribution": negative,
        "stock_etf_weight_pct": pct(stock_value / total_assets * 100),
        "bond_fund_weight_pct": pct(bond_value / total_assets * 100),
        "execution_cash_weight_pct": pct(execution_cash / total_assets * 100),
        "cash_policy": binding["cash_policy"],
        "operating_decision": contract["action_review_contract"]["real_account_posture"],
        "accepted_action_review_total_assets": money(action["total_assets"]),
        "snapshot_reconciliation_difference": money(total_assets - decimal(action["total_assets"])),
        "duplicate_sp500_etf_codes": ["159612", "159655"],
        "live_trade_recommendation_status": contract["action_review_contract"]["live_action_status"],
        "total_return_claimed": False,
        "automatic_action_authorized": False,
        "trade_authority": "NONE",
    }
    return records, summary


def parse_review_codes(items: list[str]) -> set[str]:
    return {str(item).strip().split()[0] for item in items if str(item).strip()}


def build_simulation(sources: dict[str, Any], contract: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    binding = sources["investment_state_binding"]
    action = sources["operating_state_review"]["simulation"]
    quotes = {z6(row["symbol"]): row for row in sources["a_share_quote_snapshot"]}
    candidate_codes = {z6(row[0]) for row in binding["candidate_core_20"]}
    no_add_codes = parse_review_codes(action["no_add_observation"])
    hard_review_codes = parse_review_codes(action["hard_reviews"])

    records: list[dict[str, Any]] = []
    for holding in binding["simulation_holdings"]:
        code = z6(holding["security_code"])
        if code not in quotes:
            raise ContractError(f"SIMULATION_PRICE_MISSING:{code}")
        quote = quotes[code]
        quantity = decimal(holding["quantity"])
        cost_price = decimal(holding["cost_price"])
        close = decimal(quote["close"])
        cost_basis = money(quantity * cost_price)
        market_value = money(quantity * close)
        pnl = money(market_value - cost_basis)
        return_pct = pct(pnl / cost_basis * 100) if cost_basis else Decimal("0")
        base = {
            "security_code": code,
            "security_name": holding["security_name"],
            "quantity": quantity,
            "cost_price": cost_price,
            "accepted_close": close,
            "price_as_of": quote["quote_date"],
            "price_provider": quote["provider"],
            "cost_basis": cost_basis,
            "market_value": market_value,
            "open_position_unrealized_pnl": pnl,
            "open_position_return_pct": return_pct,
            "contribution_sign": "POSITIVE" if pnl > 0 else "NEGATIVE" if pnl < 0 else "ZERO",
            "status_note": holding["status_note"],
            "positive_sample_label": "POSITIVE" in holding["status_note"],
            "candidate_core_member": code in candidate_codes,
            "no_add_control_active": code in no_add_codes,
            "hard_review_control_active": code in hard_review_codes,
            "incremental_exposure_authorized": False if code in no_add_codes else None,
            "automatic_real_capital_migration_authorized": False,
            "trade_authority": "NONE",
        }
        base["record_id"] = "FMDL7C-SIM-" + record_hash(code, base)[:20]
        records.append(base)

    records.sort(key=lambda row: row["security_code"])
    market_value = money(sum(decimal(row["market_value"]) for row in records))
    cost_basis = money(sum(decimal(row["cost_basis"]) for row in records))
    open_pnl = money(sum(decimal(row["open_position_unrealized_pnl"]) for row in records))
    cash = money(binding["simulation_available_cash"])
    total_assets = money(market_value + cash)
    original_capital = money(binding["simulation_original_capital"])
    account_total_pnl = money(total_assets - original_capital)
    accepted_account_total_pnl = money(action["account_total_pnl"])
    residual = money(account_total_pnl - open_pnl)
    positive = [row for row in records if decimal(row["open_position_unrealized_pnl"]) > 0]
    negative = [row for row in records if decimal(row["open_position_unrealized_pnl"]) < 0]
    positive_sum = money(sum(decimal(row["open_position_unrealized_pnl"]) for row in positive))
    negative_sum = money(sum(decimal(row["open_position_unrealized_pnl"]) for row in negative))

    for row in records:
        row["account_weight_pct"] = pct(decimal(row["market_value"]) / total_assets * 100)

    top_positive = [
        {"security_code": row["security_code"], "security_name": row["security_name"], "pnl": row["open_position_unrealized_pnl"]}
        for row in sorted(positive, key=lambda item: decimal(item["open_position_unrealized_pnl"]), reverse=True)[:5]
    ]
    top_negative = [
        {"security_code": row["security_code"], "security_name": row["security_name"], "pnl": row["open_position_unrealized_pnl"]}
        for row in sorted(negative, key=lambda item: decimal(item["open_position_unrealized_pnl"]))[:5]
    ]

    summary = {
        "record_id": "FMDL7C-SIM-SUMMARY-" + record_hash(total_assets, open_pnl, residual)[:20],
        "state_as_of": sources["operating_state_review"]["as_of"],
        "state_authority": "LAST_KNOWN_GOOD_NOT_CONFIRMED_CURRENT_AFTER_AS_OF",
        "holding_count": len(records),
        "cost_basis": cost_basis,
        "market_value": market_value,
        "available_cash": cash,
        "total_assets": total_assets,
        "original_capital": original_capital,
        "account_total_pnl": account_total_pnl,
        "account_return_pct": pct(account_total_pnl / original_capital * 100),
        "open_position_unrealized_pnl": open_pnl,
        "closed_fee_other_residual": residual,
        "pnl_bridge_check": money(open_pnl + residual - account_total_pnl),
        "positive_position_count": len(positive),
        "negative_position_count": len(negative),
        "positive_contribution": positive_sum,
        "negative_contribution": negative_sum,
        "positive_sample_label_count": sum(bool(row["positive_sample_label"]) for row in records),
        "no_add_count": sum(bool(row["no_add_control_active"]) for row in records),
        "hard_review_count": sum(bool(row["hard_review_control_active"]) for row in records),
        "candidate_core_overlap_count": sum(bool(row["candidate_core_member"]) for row in records),
        "invested_weight_pct": pct(market_value / total_assets * 100),
        "cash_weight_pct": pct(cash / total_assets * 100),
        "top_positive_contributors": top_positive,
        "top_negative_contributors": top_negative,
        "residual_interpretation": contract["attribution_contract"]["simulation_residual_label"],
        "accepted_action_review_market_value": money(action["market_value"]),
        "accepted_action_review_total_assets": money(action["total_assets"]),
        "accepted_action_review_total_pnl": accepted_account_total_pnl,
        "market_value_reconciliation_difference": money(market_value - decimal(action["market_value"])),
        "total_assets_reconciliation_difference": money(total_assets - decimal(action["total_assets"])),
        "total_pnl_reconciliation_difference": money(account_total_pnl - accepted_account_total_pnl),
        "operating_posture": contract["action_review_contract"]["simulation_posture"],
        "live_trade_recommendation_status": contract["action_review_contract"]["live_action_status"],
        "automatic_action_authorized": False,
        "trade_authority": "NONE",
    }
    return records, summary


def build_candidate_review(
    sources: dict[str, Any],
    simulation_records: list[dict[str, Any]],
    contract: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    binding = sources["investment_state_binding"]
    action = sources["operating_state_review"]["candidate_pool"]
    quotes = {z6(row["symbol"]): row for row in sources["a_share_quote_snapshot"]}
    simulation_by_code = {row["security_code"]: row for row in simulation_records}
    thresholds = {z6(code): decimal(value) for code, value in binding["active_memo_price_thresholds"].items()}

    records: list[dict[str, Any]] = []
    for code_value, name, state in binding["candidate_core_20"]:
        code = z6(code_value)
        if code not in quotes:
            raise ContractError(f"CANDIDATE_PRICE_MISSING:{code}")
        quote = quotes[code]
        close = decimal(quote["close"])
        threshold = thresholds.get(code)
        trigger_met = bool(threshold is not None and close <= threshold)
        sim = simulation_by_code.get(code)
        base = {
            "security_code": code,
            "security_name": name,
            "candidate_state": state,
            "accepted_close": close,
            "price_as_of": quote["quote_date"],
            "active_memo_threshold": threshold,
            "active_memo_trigger_met": trigger_met,
            "simulation_exposure_present": sim is not None,
            "simulation_open_position_pnl": sim.get("open_position_unrealized_pnl") if sim else None,
            "outcome_attribution_state": (
                "SIMULATION_OPEN_POSITION_OBSERVABLE_LKG_ONLY"
                if sim
                else "NO_APPROVED_EXPOSURE_BASELINE_RETURN_NOT_OBSERVABLE"
            ),
            "formal_membership_action": "NO_CHANGE",
            "trigger_route": "MEMO_REVIEW_ONLY" if trigger_met else "NO_TRIGGER",
            "automatic_candidate_admission_authorized": False,
            "automatic_simulation_admission_authorized": False,
            "automatic_real_account_admission_authorized": False,
            "trade_authority": "NONE",
        }
        base["record_id"] = "FMDL7C-CAND-" + record_hash(code, base)[:20]
        records.append(base)
    records.sort(key=lambda row: row["security_code"])

    summary = {
        "record_id": "FMDL7C-CAND-SUMMARY-" + record_hash(records)[:20],
        "state_as_of": sources["operating_state_review"]["as_of"],
        "formal_core_count": len(records),
        "active_memo_count": sum(row["active_memo_threshold"] is not None for row in records),
        "active_memo_trigger_met_count": sum(bool(row["active_memo_trigger_met"]) for row in records),
        "simulation_overlap_count": sum(bool(row["simulation_exposure_present"]) for row in records),
        "no_exposure_baseline_count": sum(not bool(row["simulation_exposure_present"]) for row in records),
        "accepted_action_review_conclusion": action["conclusion"],
        "operating_posture": contract["action_review_contract"]["candidate_pool_posture"],
        "formal_membership_change_count": 0,
        "simulation_admission_count": 0,
        "real_account_admission_count": 0,
        "candidate_alpha_claimed": False,
        "live_action_status": contract["action_review_contract"]["live_action_status"],
        "trade_authority": "NONE",
    }
    return records, summary


def build_action_records(
    real_summary: dict[str, Any],
    simulation_summary: dict[str, Any],
    candidate_summary: dict[str, Any],
    contract: dict[str, Any],
) -> list[dict[str, Any]]:
    raw = [
        {
            "record_code": "FACT_REAL_ACCOUNT_LKG",
            "record_class": "FACT",
            "subject": "REAL_ACCOUNT",
            "statement": "Seven real-account holdings reconcile to the accepted 2026-07-20 LKG snapshot.",
            "supporting_values": {
                "total_assets": real_summary["total_assets"],
                "stock_etf_weight_pct": real_summary["stock_etf_weight_pct"],
                "bond_fund_weight_pct": real_summary["bond_fund_weight_pct"],
                "mark_to_cost_pnl_estimate": real_summary["mark_to_cost_pnl_estimate"],
            },
            "action_status": "OBSERVED_LKG_ONLY",
        },
        {
            "record_code": "FACT_SIMULATION_ACCOUNT_LKG",
            "record_class": "FACT",
            "subject": "SIMULATION_BOOK",
            "statement": "Sixteen simulation holdings reconcile to the accepted account total and PnL bridge.",
            "supporting_values": {
                "total_assets": simulation_summary["total_assets"],
                "account_total_pnl": simulation_summary["account_total_pnl"],
                "open_position_unrealized_pnl": simulation_summary["open_position_unrealized_pnl"],
                "closed_fee_other_residual": simulation_summary["closed_fee_other_residual"],
            },
            "action_status": "OBSERVED_LKG_ONLY",
        },
        {
            "record_code": "JUDGMENT_REAL_ACCOUNT_HOLD_MONITOR",
            "record_class": "JUDGMENT",
            "subject": "REAL_ACCOUNT",
            "statement": "The accepted snapshot supports hold-and-monitor, not a new live trade instruction.",
            "supporting_values": {"posture": contract["action_review_contract"]["real_account_posture"]},
            "action_status": "HOLD_AND_MONITOR_LKG_ONLY",
        },
        {
            "record_code": "JUDGMENT_SIMULATION_HOLD_OBSERVE",
            "record_class": "JUDGMENT",
            "subject": "SIMULATION_BOOK",
            "statement": "The simulation book remains an observation laboratory with active no-add and hard-review controls.",
            "supporting_values": {
                "no_add_count": simulation_summary["no_add_count"],
                "hard_review_count": simulation_summary["hard_review_count"],
            },
            "action_status": "HOLD_AND_OBSERVE_LKG",
        },
        {
            "record_code": "CONTROLLED_RECOMMENDATION_DUPLICATE_ETF_REVIEW",
            "record_class": "CONTROLLED_PROCESS_RECOMMENDATION",
            "subject": "REAL_ACCOUNT_DUPLICATE_EXPOSURE",
            "statement": "Compare the two S&P 500 ETFs only after fresh cost, tracking, liquidity, tax and execution evidence; do not consolidate automatically.",
            "supporting_values": {"security_codes": ["159612", "159655"]},
            "action_status": "REVIEW_ONLY_NO_TRADE_PROPOSAL",
        },
        {
            "record_code": "CONTROLLED_RECOMMENDATION_LIVE_ACTION_GATE",
            "record_class": "CONTROLLED_PROCESS_RECOMMENDATION",
            "subject": "CROSS_DOMAIN_LIVE_ACTION",
            "statement": "Confirm all post-2026-07-20 state changes and refresh the latest completed market session before issuing any live adjustment recommendation.",
            "supporting_values": {
                "candidate_core_count": candidate_summary["formal_core_count"],
                "active_memo_trigger_met_count": candidate_summary["active_memo_trigger_met_count"],
            },
            "action_status": contract["action_review_contract"]["live_action_status"],
        },
    ]
    records: list[dict[str, Any]] = []
    for row in raw:
        enriched = {
            **row,
            "record_id": "FMDL7C-ACTION-" + record_hash(row["record_code"], row)[:20],
            "security_level_investment_recommendation": False,
            "immediate_trade_proposal": False,
            "automatic_state_mutation_authorized": False,
            "human_confirmation_required_for_live_action": True,
            "trade_authority": "NONE",
        }
        records.append(enriched)
    return sorted(records, key=lambda row: row["record_code"])


def build_rule_proposals(contract: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for proposal in contract["rule_calibration_proposals"]:
        records.append({
            **proposal,
            "status": "PROPOSED_NOT_APPLIED",
            "rule_mutation_applied": False,
            "regression_required": True,
            "human_approval_required": True,
            "automatic_portfolio_action": False,
            "authority": "RULE_CALIBRATION_PROPOSAL_ONLY",
            "trade_authority": "NONE",
        })
    return sorted(records, key=lambda row: row["proposal_id"])


def validate_control_record(record: dict[str, Any], contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required_live_status = contract["action_review_contract"]["live_action_status"]
    if record.get("claims_post_as_of_current") or record.get("state_as_of") != contract["attribution_contract"]["lkg_as_of"]:
        errors.append("POST_AS_OF_STATE_FABRICATION")
    if record.get("live_action_status") != required_live_status:
        errors.append("STALE_PRICE_LIVE_ACTION")
    if record.get("duplicate_etf_automatic_consolidation"):
        errors.append("DUPLICATE_ETF_AUTOMATIC_ACTION")
    bridge = money(decimal(record.get("open_position_pnl", 0)) + decimal(record.get("closed_fee_other_residual", 0)) - decimal(record.get("account_total_pnl", 0)))
    if bridge != 0:
        errors.append("SIMULATION_PNL_BRIDGE")
    if int(record.get("no_add_bypass_count", 0)) > 0 or int(record.get("hard_review_bypass_count", 0)) > 0:
        errors.append("NO_ADD_OR_HARD_REVIEW_BYPASS")
    if int(record.get("rule_mutation_applied_count", 0)) > 0:
        errors.append("UNAUTHORIZED_RULE_MUTATION")
    if int(record.get("reported_trigger_met_count", 0)) != int(record.get("actual_trigger_met_count", 0)):
        errors.append("CANDIDATE_TRIGGER_FABRICATION")
    if record.get("trade_authority") != "NONE":
        errors.append("TRADE_AUTHORITY")
    return sorted(set(errors))


def run_failure_injections(simulation_summary: dict[str, Any], candidate_summary: dict[str, Any], contract: dict[str, Any]) -> list[dict[str, Any]]:
    baseline = {
        "state_as_of": contract["attribution_contract"]["lkg_as_of"],
        "claims_post_as_of_current": False,
        "live_action_status": contract["action_review_contract"]["live_action_status"],
        "duplicate_etf_automatic_consolidation": False,
        "open_position_pnl": simulation_summary["open_position_unrealized_pnl"],
        "closed_fee_other_residual": simulation_summary["closed_fee_other_residual"],
        "account_total_pnl": simulation_summary["account_total_pnl"],
        "no_add_bypass_count": 0,
        "hard_review_bypass_count": 0,
        "rule_mutation_applied_count": 0,
        "reported_trigger_met_count": candidate_summary["active_memo_trigger_met_count"],
        "actual_trigger_met_count": candidate_summary["active_memo_trigger_met_count"],
        "trade_authority": "NONE",
    }
    fixtures: list[tuple[str, dict[str, Any], set[str]]] = []

    row = deepcopy(baseline)
    row["claims_post_as_of_current"] = True
    row["state_as_of"] = "2026-07-23_CURRENT"
    fixtures.append(("POST_AS_OF_STATE_FABRICATED_AS_CURRENT", row, {"POST_AS_OF_STATE_FABRICATION"}))

    row = deepcopy(baseline)
    row["live_action_status"] = "LIVE_TRADE_RECOMMENDATION_ALLOWED"
    fixtures.append(("STALE_PRICE_USED_FOR_LIVE_TRADE_RECOMMENDATION", row, {"STALE_PRICE_LIVE_ACTION"}))

    row = deepcopy(baseline)
    row["duplicate_etf_automatic_consolidation"] = True
    fixtures.append(("DUPLICATE_SP500_ETF_AUTOMATIC_CONSOLIDATION", row, {"DUPLICATE_ETF_AUTOMATIC_ACTION"}))

    row = deepcopy(baseline)
    row["closed_fee_other_residual"] = money(decimal(row["closed_fee_other_residual"]) + Decimal("1"))
    fixtures.append(("SIMULATION_ACCOUNT_PNL_BRIDGE_MISMATCH", row, {"SIMULATION_PNL_BRIDGE"}))

    row = deepcopy(baseline)
    row["no_add_bypass_count"] = 1
    row["hard_review_bypass_count"] = 1
    fixtures.append(("NO_ADD_OR_HARD_REVIEW_BYPASS", row, {"NO_ADD_OR_HARD_REVIEW_BYPASS"}))

    row = deepcopy(baseline)
    row["rule_mutation_applied_count"] = 1
    fixtures.append(("SINGLE_OBSERVATION_RULE_MUTATION", row, {"UNAUTHORIZED_RULE_MUTATION"}))

    row = deepcopy(baseline)
    row["reported_trigger_met_count"] = int(row["actual_trigger_met_count"]) + 1
    fixtures.append(("CANDIDATE_PRICE_TRIGGER_FABRICATION", row, {"CANDIDATE_TRIGGER_FABRICATION"}))

    row = deepcopy(baseline)
    row["trade_authority"] = "EXECUTE"
    fixtures.append(("TRADE_AUTHORITY_ESCALATION", row, {"TRADE_AUTHORITY"}))

    results: list[dict[str, Any]] = []
    for fixture_id, fixture, expected in fixtures:
        observed = set(validate_control_record(fixture, contract))
        results.append({
            "fixture_id": fixture_id,
            "expected_error_codes": sorted(expected),
            "observed_error_codes": sorted(observed),
            "status": "REJECTED_AS_REQUIRED" if expected.issubset(observed) else "FAILURE_INJECTION_NOT_CAUGHT",
            "current_replacement_authorized": False,
            "lkg_replacement_authorized": False,
            "state_mutation_authorized": False,
            "trade_authority": "NONE",
        })
    return results


def bucket_hex(record_id: str, bucket_count: int) -> str:
    value = int(hashlib.sha256(record_id.encode("utf-8")).hexdigest(), 16) % bucket_count
    return f"{value:02X}"


def deterministic_zip(entries: dict[str, bytes]) -> bytes:
    from io import BytesIO

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(entries):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, entries[name], compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return buffer.getvalue()


def jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    return "".join(stable_json(row) + "\n" for row in rows).encode("utf-8")


def build_shards(
    real_records: list[dict[str, Any]],
    real_summary: dict[str, Any],
    simulation_records: list[dict[str, Any]],
    simulation_summary: dict[str, Any],
    candidate_records: list[dict[str, Any]],
    action_records: list[dict[str, Any]],
    rule_records: list[dict[str, Any]],
    bucket_count: int,
    generated_at: str,
) -> tuple[bytes, list[dict[str, Any]]]:
    domains = [
        ("REAL_ACCOUNT_POSITION_ATTRIBUTION", real_records, "record_id"),
        ("REAL_ACCOUNT_SUMMARY", [real_summary], "record_id"),
        ("SIMULATION_POSITION_ATTRIBUTION", simulation_records, "record_id"),
        ("SIMULATION_ACCOUNT_SUMMARY", [simulation_summary], "record_id"),
        ("CANDIDATE_CORE_REVIEW", candidate_records, "record_id"),
        ("ACTION_REVIEW_RECORD", action_records, "record_id"),
        ("RULE_CALIBRATION_PROPOSAL", rule_records, "proposal_id"),
    ]
    entries: dict[str, bytes] = {}
    manifest: list[dict[str, Any]] = []
    for domain, rows, key in domains:
        for index in range(bucket_count):
            bucket = f"{index:02X}"
            shard = sorted(
                (row for row in rows if bucket_hex(str(row[key]), bucket_count) == bucket),
                key=lambda row: (str(row[key]), stable_json(row)),
            )
            payload = jsonl_bytes(shard)
            name = f"{domain}/{bucket}.jsonl"
            entries[name] = payload
            manifest.append({
                "domain": domain,
                "shard_id": f"{domain}-{bucket}",
                "bucket": bucket,
                "row_count": len(shard),
                "payload_sha256": sha256_bytes(payload),
                "generated_at": generated_at,
                "quality_status": "PASS",
            })
    return deterministic_zip(entries), manifest


def build_gate_matrix(
    contract: dict[str, Any],
    source_hashes: dict[str, str],
    real_records: list[dict[str, Any]],
    real_summary: dict[str, Any],
    simulation_records: list[dict[str, Any]],
    simulation_summary: dict[str, Any],
    candidate_records: list[dict[str, Any]],
    candidate_summary: dict[str, Any],
    action_records: list[dict[str, Any]],
    rule_records: list[dict[str, Any]],
    failure_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    gates = contract["acceptance_gates"]
    checks = [
        ("ENTRY_RELEASE50_ACCEPTED", "entry_gate" in source_hashes),
        ("SIX_SOURCE_BINDINGS_VERIFIED", len([key for key in source_hashes if key not in {"contract", "entry_gate"}]) == 6),
        ("QUOTE30_VALIDATED", len(source_hashes) >= 8),
        ("FUND_NAV3_VALIDATED", True),
        ("REAL_HOLDINGS_RECONCILED", len(real_records) == gates["real_holding_count"]),
        ("REAL_TOTAL_ASSETS_RECONCILED", decimal(real_summary["snapshot_reconciliation_difference"]) == 0),
        ("REAL_MARK_TO_COST_RECONCILED", decimal(real_summary["mark_to_cost_pnl_estimate"]) == decimal(gates["real_mark_to_cost_pnl_estimate"])),
        ("SIMULATION_HOLDINGS_RECONCILED", len(simulation_records) == gates["simulation_holding_count"]),
        ("SIMULATION_MARKET_VALUE_RECONCILED", decimal(simulation_summary["market_value_reconciliation_difference"]) == 0),
        ("SIMULATION_TOTAL_ASSETS_RECONCILED", decimal(simulation_summary["total_assets_reconciliation_difference"]) == 0),
        ("SIMULATION_PNL_BRIDGE_RECONCILED", decimal(simulation_summary["pnl_bridge_check"]) == 0 and decimal(simulation_summary["total_pnl_reconciliation_difference"]) == 0),
        ("SIMULATION_POSITIVE_NEGATIVE_COUNTS_RECONCILED", simulation_summary["positive_position_count"] == gates["simulation_positive_position_count"] and simulation_summary["negative_position_count"] == gates["simulation_negative_position_count"]),
        ("NO_ADD_AND_HARD_REVIEW_CONTROLS_RECONCILED", simulation_summary["no_add_count"] == gates["simulation_no_add_count"] and simulation_summary["hard_review_count"] == gates["simulation_hard_review_count"]),
        ("CANDIDATE_CORE20_RECONCILED", len(candidate_records) == gates["candidate_core_count"]),
        ("ACTIVE_MEMO6_RECONCILED", candidate_summary["active_memo_count"] == gates["active_memo_count"]),
        ("ACTIVE_MEMO_TRIGGER_ZERO_RECONCILED", candidate_summary["active_memo_trigger_met_count"] == gates["active_memo_trigger_met_count"]),
        ("CANDIDATE_SIMULATION_OVERLAP13_RECONCILED", candidate_summary["simulation_overlap_count"] == gates["candidate_simulation_overlap_count"]),
        ("SIX_ACTION_RECORDS_SEPARATED", len(action_records) == gates["action_recommendation_count"]),
        ("EIGHT_RULE_PROPOSALS_REGISTERED", len(rule_records) == gates["rule_calibration_proposal_count"]),
        ("ZERO_RULE_PROPOSALS_APPLIED", sum(bool(row["rule_mutation_applied"]) for row in rule_records) == 0),
        ("LIVE_ACTION_FAIL_CLOSED", all(not row["security_level_investment_recommendation"] for row in action_records) and contract["action_review_contract"]["live_action_status"].startswith("BLOCKED_")),
        ("EIGHT_FAILURE_INJECTIONS_REJECTED", len(failure_results) == gates["failure_injection_count"] and all(row["status"] == "REJECTED_AS_REQUIRED" for row in failure_results)),
        ("SEVEN_SHARD_DOMAINS_FROZEN", len(SHARD_DOMAINS) == gates["logical_shard_domain_count"]),
        ("ZERO_MUTATION_AND_TRADE_AUTHORITY", all(gates[key] == 0 for key in ["investment_recommendation_count", "candidate_pool_mutations", "simulation_book_mutations", "real_account_mutations", "rule_mutations", "orders"]) and contract["trade_authority"] == "NONE"),
    ]
    return [
        {
            "gate_id": f"FMDL7C-GATE-{index:02d}",
            "gate_name": name,
            "status": "PASS" if passed else "FAIL",
            "trade_authority": "NONE",
        }
        for index, (name, passed) in enumerate(checks, start=1)
    ]


def ensure_metric(actual: Any, expected: Any, name: str) -> None:
    if decimal(actual) != decimal(expected):
        raise ContractError(f"METRIC_MISMATCH:{name}:{actual}!={expected}")


def build_candidate(repo_root: Path, output: Path, generated_at: str, source_commit: str) -> dict[str, Any]:
    contract, errors, source_hashes = validate_contract(repo_root)
    if errors:
        raise ContractError("CONTRACT_ERRORS:" + "|".join(errors))
    sources = load_sources(repo_root, contract)

    real_records, real_summary = build_real_account(sources, contract)
    simulation_records, simulation_summary = build_simulation(sources, contract)
    candidate_records, candidate_summary = build_candidate_review(sources, simulation_records, contract)
    action_records = build_action_records(real_summary, simulation_summary, candidate_summary, contract)
    rule_records = build_rule_proposals(contract)
    failure_results = run_failure_injections(simulation_summary, candidate_summary, contract)
    gate_matrix = build_gate_matrix(
        contract,
        source_hashes,
        real_records,
        real_summary,
        simulation_records,
        simulation_summary,
        candidate_records,
        candidate_summary,
        action_records,
        rule_records,
        failure_results,
    )
    gates = contract["acceptance_gates"]

    metric_checks = {
        "real_total_assets": real_summary["total_assets"],
        "real_invested_cost_estimate": real_summary["invested_cost_estimate"],
        "real_mark_to_cost_pnl_estimate": real_summary["mark_to_cost_pnl_estimate"],
        "real_stock_etf_pnl_estimate": real_summary["stock_etf_pnl_estimate"],
        "real_bond_fund_pnl_estimate": real_summary["bond_fund_pnl_estimate"],
        "simulation_market_value": simulation_summary["market_value"],
        "simulation_cash": simulation_summary["available_cash"],
        "simulation_total_assets": simulation_summary["total_assets"],
        "simulation_account_total_pnl": simulation_summary["account_total_pnl"],
        "simulation_open_position_unrealized_pnl": simulation_summary["open_position_unrealized_pnl"],
        "simulation_closed_fee_other_residual": simulation_summary["closed_fee_other_residual"],
        "simulation_positive_contribution": simulation_summary["positive_contribution"],
        "simulation_negative_contribution": simulation_summary["negative_contribution"],
    }
    for name, actual in metric_checks.items():
        ensure_metric(actual, gates[name], name)

    if len(gate_matrix) != gates["gate_count"]:
        raise ContractError("GATE_COUNT")
    if any(row["status"] != "PASS" for row in gate_matrix):
        raise ContractError("GATE_FAILURE")

    semantic_payload = {
        "phase_id": PHASE_ID,
        "contract_sha256": source_hashes["contract"],
        "source_hashes": source_hashes,
        "real_records": real_records,
        "real_summary": real_summary,
        "simulation_records": simulation_records,
        "simulation_summary": simulation_summary,
        "candidate_records": candidate_records,
        "candidate_summary": candidate_summary,
        "action_records": action_records,
        "rule_records": rule_records,
        "failure_results": failure_results,
        "gate_matrix": gate_matrix,
    }
    release_id = f"FMDL7C_{contract['acceptance_run_date'].replace('-', '')}_{record_hash(semantic_payload)[:12]}"

    bucket_count = int(gates["bucket_count"])
    shard_bytes, shard_manifest = build_shards(
        real_records,
        real_summary,
        simulation_records,
        simulation_summary,
        candidate_records,
        action_records,
        rule_records,
        bucket_count,
        generated_at,
    )
    if len(shard_manifest) != gates["logical_shard_count"]:
        raise ContractError("LOGICAL_SHARD_COUNT")

    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    source_binding = {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "entry_release_id": contract["entry_gate"]["required_release_id"],
        "source_hashes": source_hashes,
        "source_binding_count": gates["source_binding_count"],
        "accepted_snapshot_as_of": contract["attribution_contract"]["lkg_as_of"],
        "post_as_of_user_confirmation_required": True,
        "trade_authority": "NONE",
    }
    failure_payload = {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "all_rejected_as_required": all(row["status"] == "REJECTED_AS_REQUIRED" for row in failure_results),
        "results": failure_results,
        "trade_authority": "NONE",
    }
    quality = {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "quality_status": "PASS",
        "contract_error_count": 0,
        "source_binding_count": gates["source_binding_count"],
        "real_holding_count": len(real_records),
        "real_total_assets": real_summary["total_assets"],
        "real_mark_to_cost_pnl_estimate": real_summary["mark_to_cost_pnl_estimate"],
        "simulation_holding_count": len(simulation_records),
        "simulation_total_assets": simulation_summary["total_assets"],
        "simulation_account_total_pnl": simulation_summary["account_total_pnl"],
        "simulation_open_position_unrealized_pnl": simulation_summary["open_position_unrealized_pnl"],
        "simulation_closed_fee_other_residual": simulation_summary["closed_fee_other_residual"],
        "candidate_core_count": len(candidate_records),
        "active_memo_count": candidate_summary["active_memo_count"],
        "active_memo_trigger_met_count": candidate_summary["active_memo_trigger_met_count"],
        "candidate_simulation_overlap_count": candidate_summary["simulation_overlap_count"],
        "action_recommendation_count": len(action_records),
        "rule_calibration_proposal_count": len(rule_records),
        "applied_rule_mutation_count": sum(bool(row["rule_mutation_applied"]) for row in rule_records),
        "failure_injection_count": len(failure_results),
        "acceptance_gate_count": len(gate_matrix),
        "acceptance_gate_pass_count": sum(row["status"] == "PASS" for row in gate_matrix),
        "logical_shard_domain_count": len(SHARD_DOMAINS),
        "bucket_count": bucket_count,
        "logical_shard_count": len(shard_manifest),
        "investment_recommendation_count": 0,
        "candidate_pool_mutations": 0,
        "simulation_book_mutations": 0,
        "real_account_mutations": 0,
        "rule_mutations": 0,
        "orders": 0,
        "trade_authority": "NONE",
    }
    decision = {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "release_sequence": contract["storage_contract"]["release_sequence"],
        "status": EXIT_STATUS,
        "accepted_snapshot_as_of": contract["attribution_contract"]["lkg_as_of"],
        "state_posture": "LAST_KNOWN_GOOD_NOT_CONFIRMED_CURRENT_AFTER_AS_OF",
        "real_account_posture": contract["action_review_contract"]["real_account_posture"],
        "simulation_posture": contract["action_review_contract"]["simulation_posture"],
        "candidate_pool_posture": contract["action_review_contract"]["candidate_pool_posture"],
        "live_action_status": contract["action_review_contract"]["live_action_status"],
        "attribution_conclusions": {
            "real_account_mark_to_cost_pnl_estimate": real_summary["mark_to_cost_pnl_estimate"],
            "simulation_account_total_pnl": simulation_summary["account_total_pnl"],
            "simulation_open_position_unrealized_pnl": simulation_summary["open_position_unrealized_pnl"],
            "simulation_closed_fee_other_residual": simulation_summary["closed_fee_other_residual"],
            "candidate_alpha_claimed": False,
            "persistent_alpha_proven": False,
        },
        "immediate_trade_proposal_count": 0,
        "investment_recommendation_count": 0,
        "rule_proposal_count": len(rule_records),
        "rule_mutation_count": 0,
        "zero_mutation_proof": {
            "candidate_pool_mutations": 0,
            "simulation_book_mutations": 0,
            "real_account_mutations": 0,
            "rule_mutations": 0,
            "orders": 0,
        },
        "next_gate": NEXT_GATE,
        "trade_authority": "NONE",
    }
    handoff = {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "next_gate": NEXT_GATE,
        "accepted_inputs_for_next_stage": [
            "FMDL7C_REAL_ACCOUNT_SUMMARY.json",
            "FMDL7C_SIMULATION_ACCOUNT_SUMMARY.json",
            "FMDL7C_CANDIDATE_POOL_SUMMARY.json",
            "FMDL7C_ACTION_REVIEW_REGISTER.jsonl",
            "FMDL7C_RULE_CALIBRATION_PROPOSALS.jsonl",
            "FMDL7C_FAILURE_INJECTION_RESULTS.json",
        ],
        "operating_boundaries": [
            "SCHEDULED_OPERATIONS_MUST_PRESERVE_LKG_AND_STALENESS_GATES",
            "NO_LIVE_ACTION_WITHOUT_CURRENT_STATE_CONFIRMATION_AND_MARKET_REFRESH",
            "RULE_PROPOSALS_REMAIN_NOT_APPLIED",
            "TRADE_AUTHORITY_REMAINS_NONE",
        ],
        "trade_authority": "NONE",
    }
    release = {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "release_sequence": contract["storage_contract"]["release_sequence"],
        "generated_at": generated_at,
        "source_commit": source_commit,
        "status": EXIT_STATUS,
        "next_gate": NEXT_GATE,
        "trade_authority": "NONE",
    }

    write_csv(output / "FMDL7C_REAL_ACCOUNT_POSITION_ATTRIBUTION.csv", real_records, list(real_records[0].keys()))
    write_json(output / "FMDL7C_REAL_ACCOUNT_SUMMARY.json", {"phase_id": PHASE_ID, "release_id": release_id, **real_summary})
    write_csv(output / "FMDL7C_SIMULATION_POSITION_ATTRIBUTION.csv", simulation_records, list(simulation_records[0].keys()))
    write_json(output / "FMDL7C_SIMULATION_ACCOUNT_SUMMARY.json", {"phase_id": PHASE_ID, "release_id": release_id, **simulation_summary})
    write_csv(output / "FMDL7C_CANDIDATE_CORE_REVIEW.csv", candidate_records, list(candidate_records[0].keys()))
    write_json(output / "FMDL7C_CANDIDATE_POOL_SUMMARY.json", {"phase_id": PHASE_ID, "release_id": release_id, **candidate_summary})
    write_jsonl(output / "FMDL7C_ACTION_REVIEW_REGISTER.jsonl", action_records, sort_key="record_id")
    write_jsonl(output / "FMDL7C_RULE_CALIBRATION_PROPOSALS.jsonl", rule_records, sort_key="proposal_id")
    write_json(output / "FMDL7C_FAILURE_INJECTION_RESULTS.json", failure_payload)
    write_json(output / "FMDL7C_GATE_MATRIX.json", {"phase_id": PHASE_ID, "release_id": release_id, "gates": gate_matrix, "trade_authority": "NONE"})
    write_json(output / "FMDL7C_SOURCE_BINDING.json", source_binding)
    (output / "FMDL7C_ATTRIBUTION_SHARDS.zip").write_bytes(shard_bytes)
    write_json(output / "FMDL7C_SHARD_MANIFEST.json", {"phase_id": PHASE_ID, "release_id": release_id, "shards": shard_manifest, "trade_authority": "NONE"})
    write_json(output / "FMDL7C_QUALITY_REPORT.json", quality)
    write_json(output / "FMDL7C_DECISION.json", decision)
    write_json(output / "FMDL7C_FMDL7D_HANDOFF.json", handoff)
    write_json(output / "FMDL7C_RELEASE.json", release)

    files = []
    for path in sorted(item for item in output.iterdir() if item.is_file() and item.name != "FMDL7C_MANIFEST.json"):
        files.append({"filename": path.name, "sha256": sha256_file(path), "bytes": path.stat().st_size})
    manifest = {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "release_sequence": contract["storage_contract"]["release_sequence"],
        "generated_at": generated_at,
        "source_commit": source_commit,
        "contract_sha256": source_hashes["contract"],
        "source_hashes": source_hashes,
        "files": files,
        "logical_shard_count": len(shard_manifest),
        "status": EXIT_STATUS,
        "trade_authority": "NONE",
    }
    write_json(output / "FMDL7C_MANIFEST.json", manifest)
    return decision


def validate_candidate(candidate: Path, contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = [
        "FMDL7C_REAL_ACCOUNT_POSITION_ATTRIBUTION.csv",
        "FMDL7C_REAL_ACCOUNT_SUMMARY.json",
        "FMDL7C_SIMULATION_POSITION_ATTRIBUTION.csv",
        "FMDL7C_SIMULATION_ACCOUNT_SUMMARY.json",
        "FMDL7C_CANDIDATE_CORE_REVIEW.csv",
        "FMDL7C_CANDIDATE_POOL_SUMMARY.json",
        "FMDL7C_ACTION_REVIEW_REGISTER.jsonl",
        "FMDL7C_RULE_CALIBRATION_PROPOSALS.jsonl",
        "FMDL7C_FAILURE_INJECTION_RESULTS.json",
        "FMDL7C_GATE_MATRIX.json",
        "FMDL7C_SOURCE_BINDING.json",
        "FMDL7C_ATTRIBUTION_SHARDS.zip",
        "FMDL7C_SHARD_MANIFEST.json",
        "FMDL7C_QUALITY_REPORT.json",
        "FMDL7C_DECISION.json",
        "FMDL7C_FMDL7D_HANDOFF.json",
        "FMDL7C_RELEASE.json",
        "FMDL7C_MANIFEST.json",
    ]
    for name in required:
        if not (candidate / name).is_file():
            errors.append(f"MISSING:{name}")
    if errors:
        return errors

    decision = read_json(candidate / "FMDL7C_DECISION.json")
    quality = read_json(candidate / "FMDL7C_QUALITY_REPORT.json")
    gates = read_json(candidate / "FMDL7C_GATE_MATRIX.json")
    manifest = read_json(candidate / "FMDL7C_MANIFEST.json")
    failure = read_json(candidate / "FMDL7C_FAILURE_INJECTION_RESULTS.json")

    if decision.get("status") != EXIT_STATUS:
        errors.append("DECISION_STATUS")
    if decision.get("next_gate") != NEXT_GATE:
        errors.append("DECISION_NEXT_GATE")
    if quality.get("quality_status") != "PASS":
        errors.append("QUALITY_STATUS")
    if quality.get("acceptance_gate_pass_count") != contract["acceptance_gates"]["gate_count"]:
        errors.append("GATE_PASS_COUNT")
    if any(row.get("status") != "PASS" for row in gates.get("gates", [])):
        errors.append("GATE_FAILURE")
    if not failure.get("all_rejected_as_required"):
        errors.append("FAILURE_INJECTION")
    if decision.get("trade_authority") != "NONE" or quality.get("trade_authority") != "NONE":
        errors.append("TRADE_AUTHORITY")
    if any(value != 0 for value in decision.get("zero_mutation_proof", {}).values()):
        errors.append("ZERO_MUTATION")
    if manifest.get("release_id") != decision.get("release_id"):
        errors.append("MANIFEST_RELEASE_ID")
    for item in manifest.get("files", []):
        path = candidate / item["filename"]
        if not path.is_file() or sha256_file(path) != item["sha256"] or path.stat().st_size != item["bytes"]:
            errors.append(f"MANIFEST_FILE:{item['filename']}")
    return sorted(set(errors))


def replace_tree(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination)


def publish(repo_root: Path, candidate: Path) -> dict[str, Any]:
    contract, contract_errors, _ = validate_contract(repo_root)
    if contract_errors:
        raise ContractError("CONTRACT_ERRORS:" + "|".join(contract_errors))
    candidate_errors = validate_candidate(candidate, contract)
    if candidate_errors:
        raise ContractError("CANDIDATE_ERRORS:" + "|".join(candidate_errors))

    decision = read_json(candidate / "FMDL7C_DECISION.json")
    manifest_sha = sha256_file(candidate / "FMDL7C_MANIFEST.json")
    release_id = decision["release_id"]
    storage = contract["storage_contract"]
    current = repo_root / storage["current_root"]
    immutable = repo_root / storage["release_root"].replace("<release_id>", release_id)
    normalized = repo_root / storage["normalized_root"].replace("<release_id>", release_id)
    archive = repo_root / storage["archive_root"] / release_id

    if immutable.exists():
        existing = immutable / "FMDL7C_MANIFEST.json"
        if not existing.is_file() or sha256_file(existing) != manifest_sha:
            raise ContractError("IMMUTABLE_RELEASE_ID_COLLISION")
    else:
        immutable.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(candidate, immutable)
    replace_tree(candidate, current)
    replace_tree(candidate, normalized)
    if not archive.exists():
        archive.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(candidate, archive)

    published_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    quality = read_json(candidate / "FMDL7C_QUALITY_REPORT.json")
    pointer = {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "release_sequence": storage["release_sequence"],
        "published_at": published_at,
        "source_commit": read_json(candidate / "FMDL7C_RELEASE.json")["source_commit"],
        "status": EXIT_STATUS,
        "accepted_snapshot_as_of": decision["accepted_snapshot_as_of"],
        "state_posture": decision["state_posture"],
        "live_action_status": decision["live_action_status"],
        "real_account_total_assets": quality["real_total_assets"],
        "simulation_total_assets": quality["simulation_total_assets"],
        "simulation_account_total_pnl": quality["simulation_account_total_pnl"],
        "candidate_core_count": quality["candidate_core_count"],
        "rule_calibration_proposal_count": quality["rule_calibration_proposal_count"],
        "applied_rule_mutation_count": quality["applied_rule_mutation_count"],
        "manifest_sha256": manifest_sha,
        "current_path": storage["current_root"],
        "release_path": storage["release_root"].replace("<release_id>", release_id),
        "normalized_path": storage["normalized_root"].replace("<release_id>", release_id),
        "next_gate": NEXT_GATE,
        "zero_mutation_proof": decision["zero_mutation_proof"],
        "trade_authority": "NONE",
    }
    write_json(repo_root / storage["last_success"], pointer)
    write_json(repo_root / storage["last_known_good"], {**pointer, "lkg_status": "ACTIVE_LAST_KNOWN_GOOD"})
    return pointer


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--repo-root", default=".")

    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("--repo-root", default=".")
    build_parser.add_argument("--output", required=True)
    build_parser.add_argument("--generated-at", required=True)
    build_parser.add_argument("--source-commit", required=True)

    publish_parser = subparsers.add_parser("publish")
    publish_parser.add_argument("--repo-root", default=".")
    publish_parser.add_argument("--candidate", required=True)

    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()

    if args.command == "validate":
        _, errors, source_hashes = validate_contract(repo_root)
        print(json.dumps({"status": "PASS" if not errors else "FAIL", "errors": errors, "source_hashes": source_hashes}, ensure_ascii=False, indent=2))
        return 0 if not errors else 1
    if args.command == "build":
        decision = build_candidate(repo_root, Path(args.output).resolve(), args.generated_at, args.source_commit)
        print(json.dumps(canonicalize(decision), ensure_ascii=False, indent=2))
        return 0
    if args.command == "publish":
        pointer = publish(repo_root, Path(args.candidate).resolve())
        print(json.dumps(canonicalize(pointer), ensure_ascii=False, indent=2))
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    sys.exit(main())
