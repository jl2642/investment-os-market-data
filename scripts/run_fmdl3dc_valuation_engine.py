from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from scripts import fmdl3dc_core as core

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fmdl3dc_engine.json"
TZ = ZoneInfo("Asia/Shanghai")


def load_json(path: Path) -> dict:
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
        if path.is_file() and path.name != "FMDL3DC_MANIFEST.json":
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
        "program_id": "FMDL-3D-C",
        "files": files,
        "authority": core.AUTHORITY,
        "trade_authority": core.TRADE_AUTHORITY,
    }


def resolved_state(state: str) -> bool:
    return state in {
        "VALID",
        "VALID_WITH_WARNING",
        "NOT_APPLICABLE_SECTOR",
        "NON_POSITIVE_EARNINGS",
        "NON_POSITIVE_BOOK_EQUITY",
        "NON_POSITIVE_REVENUE",
        "NON_POSITIVE_OPERATING_INCOME",
        "INVALID_ENTERPRISE_VALUE",
    }


def main() -> int:
    cfg = load_json(CONFIG)
    valuation_contract_pointer = load_json(
        ROOT / cfg["entry_gates"]["valuation_contract_pointer"]
    )
    capitalization_pointer = load_json(
        ROOT / cfg["entry_gates"]["capitalization_pointer"]
    )
    factor_pointer = load_json(ROOT / cfg["entry_gates"]["factor_engine_pointer"])

    if valuation_contract_pointer.get("status") != cfg["entry_gates"]["valuation_contract_status"]:
        raise SystemExit("FMDL-3D-A entry gate not satisfied")
    if capitalization_pointer.get("status") != cfg["entry_gates"]["capitalization_status"]:
        raise SystemExit("FMDL-3D-B entry gate not satisfied")
    if factor_pointer.get("status") != cfg["entry_gates"]["factor_engine_status"]:
        raise SystemExit("FMDL-3C-B entry gate not satisfied")

    cap_release = load_json(ROOT / cfg["inputs"]["capitalization_release"])
    factor_release = load_json(ROOT / cfg["inputs"]["factor_engine_release"])
    capitalization = pd.read_parquet(ROOT / cap_release["capitalization_current_path"])
    profiles = pd.read_csv(ROOT / cfg["inputs"]["sector_profiles"], encoding="utf-8-sig")
    registry = pd.read_csv(
        ROOT / cfg["inputs"]["valuation_metric_registry"], encoding="utf-8-sig"
    )
    derived_parts = [pd.read_parquet(ROOT / path) for path in factor_release["derived_input_shards"]]
    derived = pd.concat(derived_parts, ignore_index=True) if derived_parts else pd.DataFrame()

    candidate = ROOT / cfg["publication"]["candidate_root"]
    shutil.rmtree(candidate, ignore_errors=True)
    candidate.mkdir(parents=True)
    release_id = f"FMDL3DC_{datetime.now(TZ).strftime('%Y%m%dT%H%M%S%z')}"

    detail, current = core.build_outputs(
        capitalization,
        profiles,
        derived,
        registry,
        cfg,
    )
    expected_metrics = cfg["engine"]["expected_valuation_metric_ids"]
    selected_registry = registry[
        registry["metric_id"].astype(str).isin(expected_metrics)
        & registry["metric_family"].astype(str).eq("VALUATION")
    ].copy()

    coverage = (
        detail.groupby(["metric_id", "sector_profile", "quality_state"], dropna=False)
        .size()
        .reset_index(name="row_count")
    )
    totals = detail.groupby(["metric_id", "sector_profile"]).size().rename("group_total")
    coverage = coverage.join(totals, on=["metric_id", "sector_profile"])
    coverage["row_ratio"] = coverage["row_count"] / coverage["group_total"]
    coverage["authority"] = core.AUTHORITY
    coverage["trade_authority"] = core.TRADE_AUTHORITY

    denominator_validity = (
        detail.assign(
            denominator_resolved=detail["quality_state"].astype(str).map(resolved_state),
            denominator_decision_grade=detail["decision_grade"].astype(bool),
        )
        .groupby(
            ["metric_id", "sector_profile", "denominator_resolved", "denominator_decision_grade"],
            dropna=False,
        )
        .size()
        .reset_index(name="row_count")
    )
    denominator_validity["authority"] = core.AUTHORITY
    denominator_validity["trade_authority"] = core.TRADE_AUTHORITY

    quarantine = current[
        ~current["capitalization_state"].astype(str).isin(core.VALID_STATES)
    ].copy()

    detail.to_parquet(
        candidate / "FMDL3DC_VALUATION_METRIC_DETAIL.parquet",
        index=False,
        compression="zstd",
    )
    current.to_parquet(
        candidate / "FMDL3DC_VALUATION_CURRENT.parquet",
        index=False,
        compression="zstd",
    )
    coverage.to_csv(
        candidate / "FMDL3DC_COVERAGE.csv", index=False, encoding="utf-8-sig"
    )
    denominator_validity.to_csv(
        candidate / "FMDL3DC_DENOMINATOR_VALIDITY.csv",
        index=False,
        encoding="utf-8-sig",
    )
    quarantine.to_csv(
        candidate / "FMDL3DC_QUARANTINE.csv", index=False, encoding="utf-8-sig"
    )
    selected_registry.to_csv(
        candidate / "FMDL3DC_METRIC_REGISTRY.csv", index=False, encoding="utf-8-sig"
    )

    valid_metric_count = int(detail["quality_state"].isin(core.VALID_STATES).sum())
    decision_grade_count = int(detail["decision_grade"].astype(bool).sum())
    future_denominator_count = int(
        detail["quality_state"].astype(str).eq("FUTURE_DENOMINATOR_BLOCKED").sum()
    )
    future_selected_count = 0
    for _, row in detail[detail["denominator_available_from"].notna()].iterrows():
        available = core.normalize_timestamp(
            row["denominator_available_from"], cfg["business_timezone"]
        )
        cutoff = core.market_cutoff(
            str(row["market_as_of_date"]),
            cfg["engine"]["market_cutoff_time"],
            cfg["business_timezone"],
        )
        if available is not None and available > cutoff:
            future_selected_count += 1

    cap_supported = detail[
        detail["total_market_cap_cny"].notna()
        & (pd.to_numeric(detail["total_market_cap_cny"], errors="coerce") > 0)
    ]
    core_rows = cap_supported[cap_supported["metric_id"].isin(cfg["engine"]["core_metric_ids"])]
    core_resolved_ratio = (
        float(core_rows["quality_state"].astype(str).map(resolved_state).mean())
        if len(core_rows)
        else 0.0
    )
    capitalization_coverage = float(
        current["capitalization_state"].astype(str).isin(core.VALID_STATES).mean()
    )

    metrics = {
        "valuation_contract_release_id": valuation_contract_pointer["release_id"],
        "capitalization_release_id": capitalization_pointer["release_id"],
        "factor_engine_release_id": factor_pointer["release_id"],
        "market_source_release_id": cap_release["source_release"]["run_id"],
        "market_as_of_date": cap_release["source_release"]["as_of_date"],
        "universe_symbol_count": int(len(current)),
        "valuation_current_row_count": int(len(current)),
        "valuation_metric_count": int(len(selected_registry)),
        "valuation_metric_detail_row_count": int(len(detail)),
        "derived_input_row_count": int(len(derived)),
        "valid_or_warning_metric_count": valid_metric_count,
        "decision_grade_metric_count": decision_grade_count,
        "controlled_capitalization_quarantine_count": int(len(quarantine)),
        "capitalization_coverage_ratio": capitalization_coverage,
        "core_resolved_ratio": core_resolved_ratio,
        "future_denominator_blocked_count": future_denominator_count,
        "future_selected_denominator_count": future_selected_count,
        "automatic_action_authorized_count": 0,
        "state_counts": {
            str(key): int(value)
            for key, value in detail["quality_state"].value_counts(dropna=False).items()
        },
        "metric_valid_counts": {
            str(metric_id): int(group["quality_state"].isin(core.VALID_STATES).sum())
            for metric_id, group in detail.groupby("metric_id")
        },
    }

    checks = {
        "ENTRY_FMDL3DA_ACCEPTED": valuation_contract_pointer.get("status")
        == cfg["entry_gates"]["valuation_contract_status"],
        "ENTRY_FMDL3DB_ACCEPTED": capitalization_pointer.get("status")
        == cfg["entry_gates"]["capitalization_status"],
        "ENTRY_FMDL3CB_ACCEPTED": factor_pointer.get("status")
        == cfg["entry_gates"]["factor_engine_status"],
        "EXACT_VALUATION_METRIC_REGISTRY": set(selected_registry["metric_id"].astype(str))
        == set(expected_metrics)
        and len(selected_registry) == len(expected_metrics),
        "CURRENT_EXACT_CAPITALIZATION_UNIVERSE": len(current) == len(capitalization)
        and set(current["symbol"].astype(str)) == set(capitalization["symbol"].astype(str)),
        "DETAIL_EXACT_UNIVERSE_METRIC_MATRIX": len(detail)
        == len(current) * len(expected_metrics),
        "CURRENT_KEYS_UNIQUE": not current.duplicated(["symbol"]).any(),
        "DETAIL_KEYS_UNIQUE": not detail.duplicated(["symbol", "metric_id"]).any(),
        "METRIC_STATES_CONTROLLED": set(detail["quality_state"].astype(str)).issubset(
            set(cfg["engine"]["allowed_metric_states"])
        ),
        "VALID_ROWS_HAVE_VALUES": detail.loc[
            detail["quality_state"].isin(core.VALID_STATES), "metric_value"
        ].notna().all(),
        "INVALID_ROWS_HAVE_NULL_VALUES": detail.loc[
            ~detail["quality_state"].isin(core.VALID_STATES), "metric_value"
        ].isna().all(),
        "ZERO_FUTURE_SELECTED_DENOMINATOR": future_selected_count == 0,
        "CAPITALIZATION_COVERAGE_GATE": capitalization_coverage
        >= float(cfg["engine"]["minimum_capitalization_coverage"]),
        "CORE_RESOLVED_RATIO_GATE": core_resolved_ratio
        >= float(cfg["engine"]["minimum_core_resolved_ratio"]),
        "ZERO_AUTOMATIC_ACTION": metrics["automatic_action_authorized_count"] == 0,
        "ZERO_TRADE_AUTHORITY": set(detail["trade_authority"].astype(str)) == {"NONE"}
        and set(current["trade_authority"].astype(str)) == {"NONE"},
    }
    failures = [name for name, passed in checks.items() if not bool(passed)]
    decision = {
        "decision_version": "1.0.0",
        "release_id": release_id,
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "program_id": "FMDL-3D-C",
        "status": cfg["exit_status"] if not failures else "FMDL3DC_REMEDIATION_REQUIRED",
        "exit_gate": "VALUATION_ENGINE_CURRENT_ACCEPTED" if not failures else "NOT_MET",
        "hard_failures": failures,
        "checks": [
            {"check_id": key, "status": "PASS" if bool(value) else "FAIL"}
            for key, value in checks.items()
        ],
        "metrics": metrics,
        "controlled_limitations": [
            "VALUATION_USES_LATEST_COMPLETED_SESSION_CAPITALIZATION_NOT_INTRADAY_PRICE",
            "FINANCIAL_DENOMINATORS_MUST_BE_AVAILABLE_NOT_LATER_THAN_MARKET_CLOSE_CUTOFF",
            "NEGATIVE_OR_ZERO_EARNINGS_DO_NOT_PRODUCE_VALID_PE",
            "NEGATIVE_OR_ZERO_BOOK_EQUITY_DOES_NOT_PRODUCE_VALID_PB",
            "EV_METRICS_REQUIRE_COMPLETE_DEBT_AND_CASH_COMPONENTS",
            "GENERAL_COMPANY_PS_FCF_AND_EV_METRICS_ARE_NOT_FORCED_ONTO_FINANCIAL_PROFILES",
            "PROVIDER_VALUATION_RATIOS_REMAIN_CROSS_CHECK_ONLY",
            "NO_COMPOSITE_VALUATION_SCORE_TARGET_PRICE_PORTFOLIO_ACTION_OR_TRADE_AUTHORITY",
        ],
        "authority": core.AUTHORITY,
        "trade_authority": core.TRADE_AUTHORITY,
        "next_gate": cfg["next_gate"],
    }
    write_json(candidate / "FMDL3DC_DECISION.json", decision)
    write_json(candidate / "FMDL3DC_MANIFEST.json", manifest(candidate, release_id))
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
