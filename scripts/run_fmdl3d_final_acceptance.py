from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from scripts.fmdl3d_final_core import (
    build_unified_current,
    cross_layer_numeric_mismatch_count,
    market_cap_replay_error_count,
    shareholder_yield_replay_error_count,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fmdl3d_final_contract.json"
TZ = ZoneInfo("Asia/Shanghai")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest(root: Path, release_id: str) -> dict:
    files = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "FMDL3D_FINAL_MANIFEST.json":
            files.append(
                {
                    "path": str(path.relative_to(root)),
                    "sha256": sha256(path),
                    "bytes": path.stat().st_size,
                }
            )
    return {
        "manifest_version": "1.0.0",
        "release_id": release_id,
        "files": files,
        "authority": "DATA_AND_RESEARCH_EVIDENCE_ONLY",
        "trade_authority": "NONE",
    }


def get_path(payload: dict, *keys, default=None):
    current = payload
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def component_metric_rows(
    pointers: dict[str, dict],
    releases: dict[str, dict],
    validations: dict[str, dict],
) -> pd.DataFrame:
    rows = []
    for stage in ["FMDL-3D-A", "FMDL-3D-B", "FMDL-3D-C", "FMDL-3D-D"]:
        pointer = pointers[stage]
        release = releases[stage]
        validation = validations[stage]
        metrics = release.get("metrics", {})
        rows.append(
            {
                "stage": stage,
                "release_id": pointer.get("release_id"),
                "pointer_status": pointer.get("status"),
                "release_status": release.get("status"),
                "validation_status": validation.get("status"),
                "hard_failure_count": len(validation.get("hard_failures", [])),
                "market_as_of_date": pointer.get("market_as_of_date")
                or metrics.get("market_as_of_date")
                or metrics.get("source_as_of_date"),
                "universe_symbol_count": metrics.get("universe_symbol_count"),
                "automatic_action_authorized_count": metrics.get(
                    "automatic_action_authorized_count", 0
                ),
                "trade_authority": pointer.get("trade_authority"),
                "next_gate": pointer.get("next_gate"),
            }
        )
    return pd.DataFrame(rows)


def main() -> int:
    cfg = load_json(CONFIG)
    pointer_specs = cfg["entry_gates"]
    stage_map = {
        "FMDL-3D-A": "valuation_contract_pointer",
        "FMDL-3D-B": "capitalization_pointer",
        "FMDL-3D-C": "valuation_pointer",
        "FMDL-3D-D": "shareholder_return_pointer",
    }
    pointers = {
        stage: load_json(ROOT / pointer_specs[key]["path"])
        for stage, key in stage_map.items()
    }
    release_paths = {
        "FMDL-3D-A": cfg["inputs"]["valuation_contract_release"],
        "FMDL-3D-B": cfg["inputs"]["capitalization_release"],
        "FMDL-3D-C": cfg["inputs"]["valuation_release"],
        "FMDL-3D-D": cfg["inputs"]["shareholder_return_release"],
    }
    validation_paths = {
        "FMDL-3D-A": cfg["inputs"]["valuation_contract_validation"],
        "FMDL-3D-B": cfg["inputs"]["capitalization_validation"],
        "FMDL-3D-C": cfg["inputs"]["valuation_validation"],
        "FMDL-3D-D": cfg["inputs"]["shareholder_return_validation"],
    }
    releases = {
        stage: load_json(ROOT / path) for stage, path in release_paths.items()
    }
    validations = {
        stage: load_json(ROOT / path) for stage, path in validation_paths.items()
    }
    capitalization = pd.read_parquet(ROOT / cfg["inputs"]["capitalization_current"])
    valuation = pd.read_parquet(ROOT / cfg["inputs"]["valuation_current"])
    valuation_detail = pd.read_parquet(ROOT / cfg["inputs"]["valuation_detail"])
    shareholder_return = pd.read_parquet(
        ROOT / cfg["inputs"]["shareholder_return_current"]
    )
    shareholder_events = pd.read_parquet(
        ROOT / cfg["inputs"]["shareholder_return_events"]
    )
    for frame in [capitalization, valuation, shareholder_return, shareholder_events]:
        if "symbol" in frame.columns:
            frame["symbol"] = frame["symbol"].astype(str)

    component_release_ids = {
        stage: pointers[stage]["release_id"]
        for stage in ["FMDL-3D-A", "FMDL-3D-B", "FMDL-3D-C", "FMDL-3D-D"]
    }
    unified = build_unified_current(
        capitalization,
        valuation,
        shareholder_return,
        component_release_ids,
    )
    universe_count = int(cfg["unified_current"]["required_universe_count"])
    symbol_sets = {
        "capitalization": set(capitalization["symbol"]),
        "valuation": set(valuation["symbol"]),
        "shareholder_return": set(shareholder_return["symbol"]),
    }
    market_dates = {
        "capitalization": set(capitalization["price_as_of_date"].dropna().astype(str)),
        "valuation": set(valuation["market_as_of_date"].dropna().astype(str)),
        "shareholder_return": set(
            shareholder_return["market_as_of_date"].dropna().astype(str)
        ),
    }
    common_market_dates = set.intersection(*market_dates.values())
    market_as_of_date = (
        sorted(common_market_dates)[-1] if len(common_market_dates) == 1 else None
    )
    cap_replay_errors, max_cap_diff = market_cap_replay_error_count(
        capitalization,
        float(cfg["unified_current"]["market_cap_replay_tolerance_cny"]),
    )
    shareholder_replay_errors, max_shareholder_diff = (
        shareholder_yield_replay_error_count(
            shareholder_return,
            float(cfg["unified_current"]["formula_replay_tolerance"]),
        )
    )
    cross_mismatches = cross_layer_numeric_mismatch_count(
        capitalization,
        valuation,
        shareholder_return,
        float(cfg["unified_current"]["market_cap_replay_tolerance_cny"]),
    )
    forbidden_fields = {
        "valuation_score",
        "shareholder_return_score",
        "investment_signal",
        "target_price",
        "target_weight",
        "order_quantity",
        "buy_signal",
        "sell_signal",
        "portfolio_action",
    }
    component_validations_pass = all(
        item.get("status") == "PASS" for item in validations.values()
    )
    component_failures_empty = all(
        item.get("hard_failures") == [] for item in validations.values()
    )
    pointer_statuses_pass = all(
        pointers[stage].get("status")
        == pointer_specs[stage_map[stage]]["required_status"]
        for stage in stage_map
    )
    pointer_release_alignment = all(
        pointers[stage].get("release_id") == releases[stage].get("release_id")
        for stage in stage_map
    )
    gate_chain = {
        "A_TO_B": pointers["FMDL-3D-A"].get("next_gate")
        == "FMDL-3D-B_EFFECTIVE_SHARE_COUNT_AND_CAPITALIZATION_ENGINE",
        "B_TO_C": pointers["FMDL-3D-B"].get("next_gate")
        == "FMDL-3D-C_VALUATION_ENGINE_CURRENT",
        "C_TO_D": pointers["FMDL-3D-C"].get("next_gate")
        == "FMDL-3D-D_SHAREHOLDER_RETURN_EVENT_CURRENT",
        "D_TO_FINAL": pointers["FMDL-3D-D"].get("next_gate")
        == "FMDL-3D-FINAL_UNIFIED_ACCEPTANCE_AND_PUBLICATION",
    }
    c_sources = releases["FMDL-3D-C"].get("source_releases", {})
    d_metrics = releases["FMDL-3D-D"].get("metrics", {})
    source_binding = {
        "C_BINDS_A": c_sources.get("valuation_contract_release_id")
        == pointers["FMDL-3D-A"].get("release_id"),
        "C_BINDS_B": c_sources.get("capitalization_release_id")
        == pointers["FMDL-3D-B"].get("release_id"),
        "D_BINDS_A": d_metrics.get("valuation_contract_release_id")
        == pointers["FMDL-3D-A"].get("release_id"),
        "D_BINDS_B": d_metrics.get("capitalization_release_id")
        == pointers["FMDL-3D-B"].get("release_id"),
        "D_BINDS_C": d_metrics.get("valuation_release_id")
        == pointers["FMDL-3D-C"].get("release_id"),
    }
    b_metrics = validations["FMDL-3D-B"].get("metrics", {})
    c_metrics = validations["FMDL-3D-C"].get("metrics", {})
    d_validation_metrics = validations["FMDL-3D-D"].get("metrics", {})
    future_controls = {
        "B_FUTURE_SELECTED_SHARE_ZERO": int(
            b_metrics.get("future_selected_share_count_independent", -1)
        )
        == 0,
        "B_FUTURE_CURRENT_SHARE_ZERO": int(
            b_metrics.get("future_current_share_count_independent", -1)
        )
        == 0,
        "C_FUTURE_SELECTED_DENOMINATOR_ZERO": int(
            c_metrics.get("future_selected_denominator_count_independent", -1)
        )
        == 0,
        "D_FUTURE_EFFECTIVE_EVENT_ZERO": int(
            d_validation_metrics.get("future_effective_event_count_independent", -1)
        )
        == 0,
    }
    component_formula_controls = {
        "B_MARKET_CAP_REPLAY_ZERO": float(
            b_metrics.get("total_market_cap_max_absolute_replay_difference_cny", -1)
        )
        == 0.0
        and float(
            b_metrics.get("float_market_cap_max_absolute_replay_difference_cny", -1)
        )
        == 0.0,
        "C_FORMULA_REPLAY_ZERO": int(c_metrics.get("formula_replay_error_count", -1))
        == 0,
        "C_DENOMINATOR_SIGN_ERRORS_ZERO": int(
            c_metrics.get("denominator_sign_error_count", -1)
        )
        == 0,
        "D_FORMULA_REPLAY_ZERO": int(
            d_validation_metrics.get("formula_replay_error_count_independent", -1)
        )
        == 0,
    }
    action_authority_zero = all(
        int(releases[stage].get("metrics", {}).get("automatic_action_authorized_count", 0))
        == 0
        for stage in stage_map
    )
    trade_authority_none = all(
        pointers[stage].get("trade_authority") == "NONE"
        and releases[stage].get("trade_authority") == "NONE"
        and validations[stage].get("trade_authority") == "NONE"
        for stage in stage_map
    ) and set(unified["trade_authority"].astype(str)).issubset({"NONE"})

    checks = {
        "ALL_ENTRY_POINTER_STATUSES_ACCEPTED": pointer_statuses_pass,
        "ALL_POINTERS_MATCH_CURRENT_RELEASES": pointer_release_alignment,
        "ALL_COMPONENT_VALIDATIONS_PASS": component_validations_pass,
        "ALL_COMPONENT_HARD_FAILURES_EMPTY": component_failures_empty,
        "GATE_CHAIN_A_TO_D_FINAL_COHERENT": all(gate_chain.values()),
        "COMPONENT_SOURCE_BINDINGS_COHERENT": all(source_binding.values()),
        "EXACT_UNIVERSE_COUNT": len(unified) == universe_count,
        "EXACT_SYMBOL_SET_ALIGNMENT": symbol_sets["capitalization"]
        == symbol_sets["valuation"]
        == symbol_sets["shareholder_return"],
        "CURRENT_KEYS_UNIQUE": not unified["symbol"].duplicated().any(),
        "MARKET_DATE_EXACT_ALIGNMENT": all(len(values) == 1 for values in market_dates.values())
        and market_dates["capitalization"]
        == market_dates["valuation"]
        == market_dates["shareholder_return"],
        "CROSS_LAYER_MARKET_CAP_ALIGNED": sum(cross_mismatches.values()) == 0,
        "CAPITALIZATION_FORMULA_REPLAY": cap_replay_errors == 0,
        "SHAREHOLDER_YIELD_FORMULA_REPLAY": shareholder_replay_errors == 0,
        "VALUATION_DETAIL_KEYS_UNIQUE": not valuation_detail.duplicated(
            ["symbol", "metric_id"]
        ).any(),
        "SHAREHOLDER_EVENT_KEYS_UNIQUE": shareholder_events.empty
        or not shareholder_events["event_id"].duplicated().any(),
        "FUTURE_INFORMATION_CONTROLS_PASS": all(future_controls.values()),
        "COMPONENT_FORMULA_CONTROLS_PASS": all(
            component_formula_controls.values()
        ),
        "NO_SCORE_TARGET_OR_ACTION_FIELDS": not (
            forbidden_fields
            & (
                set(capitalization.columns)
                | set(valuation.columns)
                | set(shareholder_return.columns)
                | set(unified.columns)
            )
        ),
        "ZERO_AUTOMATIC_ACTION_AUTHORITY": action_authority_zero,
        "ZERO_TRADE_AUTHORITY": trade_authority_none,
    }
    failures = [key for key, value in checks.items() if not bool(value)]
    release_id = f"FMDL3D_FINAL_{datetime.now(TZ).strftime('%Y%m%dT%H%M%S%z')}"
    candidate = ROOT / cfg["publication"]["candidate_root"]
    if candidate.exists():
        shutil.rmtree(candidate)
    candidate.mkdir(parents=True, exist_ok=True)
    unified.to_parquet(
        candidate / "FMDL3D_UNIFIED_CURRENT.parquet",
        index=False,
        compression="zstd",
    )
    component_metrics = component_metric_rows(pointers, releases, validations)
    component_metrics.to_csv(
        candidate / "FMDL3D_COMPONENT_RELEASE_MATRIX.csv",
        index=False,
        encoding="utf-8-sig",
    )
    interface = {
        "interface_version": "1.0.0",
        "interface_id": "FMDL3D_VALUATION_CAPITALIZATION_SHAREHOLDER_RETURN_INTERFACE",
        "status": "ACTIVE_RESEARCH_EVIDENCE_ONLY",
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "market_as_of_date": market_as_of_date,
        "component_releases": component_release_ids,
        "datasets": [
            {
                "dataset_id": "fmdl3d_unified_current",
                "path": "outputs/fmdl3d/final/current/FMDL3D_UNIFIED_CURRENT.parquet",
                "purpose": "One-row-per-symbol capitalization, valuation and shareholder-return research evidence",
            },
            {
                "dataset_id": "capitalization_current",
                "path": cfg["inputs"]["capitalization_current"],
                "purpose": "Effective shares and recomputed market capitalization",
            },
            {
                "dataset_id": "valuation_current",
                "path": cfg["inputs"]["valuation_current"],
                "purpose": "Point-in-time valuation metric Current",
            },
            {
                "dataset_id": "shareholder_return_current",
                "path": cfg["inputs"]["shareholder_return_current"],
                "purpose": "Implemented dividend and completed effective-share return evidence",
            },
            {
                "dataset_id": "shareholder_return_event_ledger",
                "path": cfg["inputs"]["shareholder_return_events"],
                "purpose": "Canonical event lineage and stage evidence",
            },
        ],
        "consumer_contract": {
            "allowed_consumers": ["PUBLIC_EQUITY_INVESTING", "INVESTMENT_OS"],
            "required_prechecks": [
                "validate FMDL3D_LAST_SUCCESS and unified interface schemas",
                "surface component states and controlled nulls",
                "preserve point-in-time price, shares, denominator and event dates",
                "apply valuation and shareholder-return evidence only inside later research and portfolio gates",
            ],
            "prohibited_actions": [
                "creating a valuation score or target price from the unified Current",
                "creating BUY ADD REDUCE SELL permission",
                "automatic candidate-pool, simulation or real-account mutation",
                "automatic portfolio action or brokerage execution",
                "treating missing or inapplicable metrics as zero",
            ],
        },
        "authority_boundary": "VALUATION_CAPITALIZATION_AND_SHAREHOLDER_RETURN_RESEARCH_EVIDENCE_ONLY",
        "trade_authority": "NONE",
    }
    write_json(candidate / "FMDL3D_UNIFIED_CURRENT_INTERFACE.json", interface)
    release_index = {
        "index_version": "1.0.0",
        "release_id": release_id,
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "market_as_of_date": market_as_of_date,
        "components": {
            stage: {
                "release_id": pointers[stage]["release_id"],
                "status": pointers[stage]["status"],
                "current_release_path": pointers[stage]["current_release_path"],
                "validation_status": validations[stage]["status"],
                "trade_authority": pointers[stage]["trade_authority"],
            }
            for stage in stage_map
        },
        "authority": cfg["authority"],
        "trade_authority": "NONE",
    }
    write_json(candidate / "FMDL3D_UNIFIED_RELEASE_INDEX.json", release_index)
    metrics = {
        "market_as_of_date": market_as_of_date,
        "universe_symbol_count": int(len(unified)),
        "capitalization_valid_or_warning_count": int(
            capitalization["capitalization_state"]
            .isin(["VALID", "VALID_WITH_WARNING"])
            .sum()
        ),
        "valuation_valid_metric_count": int(
            pd.to_numeric(unified["valuation_valid_metric_count"], errors="coerce").sum()
        ),
        "valuation_symbol_with_any_valid_metric_count": int(
            pd.to_numeric(unified["valuation_valid_metric_count"], errors="coerce")
            .gt(0)
            .sum()
        ),
        "shareholder_yield_complete_count": int(
            unified["complete_shareholder_yield"].sum()
        ),
        "positive_dividend_yield_count": int(
            pd.to_numeric(unified["dividend_yield_ttm"], errors="coerce")
            .gt(0)
            .sum()
        ),
        "positive_buyback_component_count": int(
            pd.to_numeric(unified["completed_buyback_yield_ttm"], errors="coerce")
            .gt(0)
            .sum()
        ),
        "positive_dilution_component_count": int(
            pd.to_numeric(
                unified["completed_issuance_dilution_yield_ttm"], errors="coerce"
            )
            .gt(0)
            .sum()
        ),
        "shareholder_event_count": int(len(shareholder_events)),
        "valuation_detail_row_count": int(len(valuation_detail)),
        "capitalization_replay_error_count": cap_replay_errors,
        "capitalization_maximum_replay_difference_cny": max_cap_diff,
        "shareholder_yield_replay_error_count": shareholder_replay_errors,
        "shareholder_yield_maximum_replay_difference": max_shareholder_diff,
        "cross_layer_numeric_mismatch_count": int(sum(cross_mismatches.values())),
        "duplicate_current_key_count": int(unified["symbol"].duplicated().sum()),
        "duplicate_valuation_detail_key_count": int(
            valuation_detail.duplicated(["symbol", "metric_id"]).sum()
        ),
        "duplicate_shareholder_event_key_count": int(
            shareholder_events["event_id"].duplicated().sum()
        )
        if len(shareholder_events)
        else 0,
        "future_selected_share_count": int(
            b_metrics.get("future_selected_share_count_independent", -1)
        ),
        "future_selected_denominator_count": int(
            c_metrics.get("future_selected_denominator_count_independent", -1)
        ),
        "future_effective_shareholder_event_count": int(
            d_validation_metrics.get("future_effective_event_count_independent", -1)
        ),
        "automatic_action_authorized_count": 0,
    }
    decision = {
        "decision_version": "1.0.0",
        "release_id": release_id,
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "program_id": "FMDL-3D-FINAL",
        "status": (
            cfg["exit_status"]
            if not failures
            else "FMDL3D_FINAL_REMEDIATION_REQUIRED"
        ),
        "hard_failures": failures,
        "checks": [
            {"check_id": key, "status": "PASS" if value else "FAIL"}
            for key, value in checks.items()
        ],
        "metrics": metrics,
        "component_release_ids": component_release_ids,
        "gate_chain": gate_chain,
        "source_binding": source_binding,
        "future_controls": future_controls,
        "component_formula_controls": component_formula_controls,
        "cross_layer_numeric_mismatches": cross_mismatches,
        "controlled_limitations": [
            "FMDL3D_CURRENT_IS_RESEARCH_EVIDENCE_NOT_A_VALUATION_SCORE_OR_INVESTMENT_CONCLUSION",
            "LATEST_COMPLETED_SESSION_PRICE_IS_USED_NOT_INTRADAY_PRICE",
            "EV_METRIC_COVERAGE_REMAINS_LIMITED_BY_COMPLETE_DEBT_AND_CASH_INPUTS",
            "SHAREHOLDER_BUYBACK_AND_DILUTION_COMPONENTS_USE_EFFECTIVE_SHARE_CHANGE_RATIOS",
            "UNCLASSIFIED_SHARE_CHANGES_DO_NOT_ENTER_SHAREHOLDER_YIELD",
            "NO_TARGET_PRICE_CANDIDATE_SIMULATION_REAL_ACCOUNT_OR_PORTFOLIO_MUTATION",
        ],
        "authority": cfg["authority"],
        "trade_authority": "NONE",
        "next_gate": cfg["next_gate"],
    }
    write_json(candidate / "FMDL3D_FINAL_DECISION.json", decision)
    write_json(
        candidate / "FMDL3D_COMPONENT_SOURCE_SNAPSHOT.json",
        {
            "pointers": pointers,
            "releases": releases,
            "validations": validations,
        },
    )
    write_json(
        candidate / "FMDL3D_FINAL_MANIFEST.json", manifest(candidate, release_id)
    )
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
