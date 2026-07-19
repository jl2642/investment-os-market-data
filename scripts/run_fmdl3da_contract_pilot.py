from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from scripts.fmdl3da_core import (
    VALID_METRIC_STATES,
    build_capitalization_snapshot,
    build_event_contract_samples,
    evaluate_metric,
)

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("Asia/Shanghai")
CONFIG = ROOT / "config/fmdl3da_contract.json"


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
        if path.is_file() and path.name != "FMDL3DA_MANIFEST.json":
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


def main() -> int:
    cfg = load_json(CONFIG)
    score_pointer = load_json(ROOT / cfg["entry_gates"]["financial_score_pointer"])
    source_release = load_json(ROOT / cfg["entry_gates"]["source_benchmark_release"])
    factor_release = load_json(ROOT / cfg["entry_gates"]["factor_engine_release"])
    if score_pointer.get("status") != cfg["entry_gates"]["financial_score_status"]:
        raise SystemExit("FMDL-3C-D entry gate not accepted")
    if source_release.get("status") != cfg["entry_gates"]["source_benchmark_status"]:
        raise SystemExit("FMDL-3A source benchmark entry gate not accepted")
    if factor_release.get("status") != cfg["entry_gates"]["factor_engine_status"]:
        raise SystemExit("FMDL-3C-B factor engine entry gate not accepted")

    pilot = pd.read_csv(
        ROOT / cfg["inputs"]["pilot_universe"],
        encoding="utf-8-sig",
        dtype=str,
    )
    metric_registry = pd.read_csv(
        ROOT / cfg["inputs"]["valuation_metric_registry"], encoding="utf-8-sig"
    )
    event_registry = pd.read_csv(
        ROOT / cfg["inputs"]["shareholder_event_registry"], encoding="utf-8-sig"
    ).fillna("NONE")
    capitalization_evidence = pd.read_csv(
        ROOT / cfg["inputs"]["capitalization_evidence"],
        encoding="utf-8-sig",
        dtype={"symbol": str},
    )
    support_map = pd.read_csv(
        ROOT / cfg["inputs"]["support_quarantine_map"],
        encoding="utf-8-sig",
        dtype={"symbol": str},
    )

    pilot_symbols = set(pilot["symbol"].astype(str))
    derived_parts: list[pd.DataFrame] = []
    for relative in factor_release["derived_input_shards"]:
        frame = pd.read_parquet(ROOT / relative)
        if len(frame):
            selected = frame[frame["symbol"].astype(str).isin(pilot_symbols)]
            if len(selected):
                derived_parts.append(selected)
    derived = pd.concat(derived_parts, ignore_index=True) if derived_parts else pd.DataFrame()
    if len(derived):
        derived["symbol"] = derived["symbol"].astype(str)
    derived_groups = {
        symbol: frame for symbol, frame in derived.groupby("symbol", sort=False)
    } if len(derived) else {}

    candidate = ROOT / cfg["publication"]["candidate_root"]
    if candidate.exists():
        shutil.rmtree(candidate)
    candidate.mkdir(parents=True, exist_ok=True)
    release_id = f"FMDL3DA_{datetime.now(TZ).strftime('%Y%m%dT%H%M%S%z')}"
    source_identity = (
        f"{source_release['release_id']}|{factor_release['release_id']}|"
        f"{score_pointer['release_id']}"
    )

    cap = build_capitalization_snapshot(
        pilot,
        capitalization_evidence,
        source_release["release_id"],
    )
    cap.to_csv(
        candidate / "FMDL3DA_CAPITALIZATION_PILOT.csv",
        index=False,
        encoding="utf-8-sig",
    )

    metric_rows: list[dict] = []
    for _, cap_row in cap.iterrows():
        symbol_rows = derived_groups.get(str(cap_row["symbol"]), pd.DataFrame())
        for _, metric in metric_registry.iterrows():
            metric_rows.append(
                evaluate_metric(metric, cap_row, symbol_rows, source_identity)
            )
    details = pd.DataFrame(metric_rows).sort_values(
        ["symbol", "metric_id"]
    ).reset_index(drop=True)
    details.to_parquet(
        candidate / "FMDL3DA_VALUATION_METRIC_DETAIL.parquet",
        index=False,
        compression="zstd",
    )

    value_wide = details.pivot(index="symbol", columns="metric_id", values="metric_value")
    state_wide = details.pivot(index="symbol", columns="metric_id", values="metric_state")
    value_wide.columns = [f"{column}__value" for column in value_wide.columns]
    state_wide.columns = [f"{column}__state" for column in state_wide.columns]
    snapshot = cap.merge(
        value_wide.reset_index(), on="symbol", how="left", validate="one_to_one"
    ).merge(state_wide.reset_index(), on="symbol", how="left", validate="one_to_one")
    snapshot.to_parquet(
        candidate / "FMDL3DA_VALUATION_PILOT_CURRENT.parquet",
        index=False,
        compression="zstd",
    )

    events = build_event_contract_samples(event_registry)
    events.to_csv(
        candidate / "FMDL3DA_SHAREHOLDER_EVENT_CONTRACT_SAMPLES.csv",
        index=False,
        encoding="utf-8-sig",
    )

    coverage = (
        details.groupby(
            ["metric_id", "metric_family", "sector_profile", "metric_state"],
            dropna=False,
        )
        .size()
        .reset_index(name="row_count")
        .sort_values(["metric_id", "sector_profile", "metric_state"])
    )
    coverage.to_csv(
        candidate / "FMDL3DA_PILOT_COVERAGE.csv",
        index=False,
        encoding="utf-8-sig",
    )
    source_matrix = support_map[
        support_map["symbol"].astype(str).isin(pilot_symbols)
    ].copy()
    source_matrix.to_csv(
        candidate / "FMDL3DA_SOURCE_SUPPORT_SNAPSHOT.csv",
        index=False,
        encoding="utf-8-sig",
    )

    supported_cap = cap[cap["capitalization_state"].isin(["VALID", "VALID_WITH_WARNING"])]
    quarantined_cap = cap[cap["capitalization_state"].eq("CONTROLLED_QUARANTINE")]
    pilot_metric_rows = details[
        details["metric_id"].isin(
            metric_registry.loc[
                metric_registry["build_stage"].eq("3D_A_PILOT"), "metric_id"
            ].astype(str)
        )
        & details["symbol"].isin(supported_cap["symbol"])
        & details["metric_state"].ne("NOT_APPLICABLE_SECTOR")
    ]
    valid_pilot_ratio = (
        float(pilot_metric_rows["metric_state"].isin(VALID_METRIC_STATES).mean())
        if len(pilot_metric_rows)
        else 0.0
    )
    valid_detail = details[details["metric_state"].isin(VALID_METRIC_STATES)]
    invalid_detail = details[~details["metric_state"].isin(VALID_METRIC_STATES)]
    event_lookup = {
        (str(row.event_type), str(row.event_stage)): row
        for row in events.itertuples(index=False)
    }
    checks = {
        "ENTRY_FMDL3CD_ACCEPTED": score_pointer.get("status")
        == cfg["entry_gates"]["financial_score_status"],
        "ENTRY_FMDL3A_ACCEPTED": source_release.get("status")
        == cfg["entry_gates"]["source_benchmark_status"],
        "ENTRY_FMDL3CB_ACCEPTED": factor_release.get("status")
        == cfg["entry_gates"]["factor_engine_status"],
        "PILOT_EXACT_SYMBOL_COUNT": len(pilot)
        == int(cfg["pilot"]["expected_symbol_count"])
        and not pilot["symbol"].duplicated().any(),
        "PILOT_REQUIRED_PROFILES_PRESENT": set(cfg["pilot"]["required_profiles"]).issubset(
            set(pilot["sector_profile"].astype(str))
        ),
        "PILOT_REQUIRED_BOARDS_PRESENT": set(cfg["pilot"]["required_boards"]).issubset(
            set(pilot["board"].astype(str))
        ),
        "CAPITALIZATION_SUPPORTED_COUNT": len(supported_cap)
        == int(cfg["pilot"]["expected_supported_capitalization_count"]),
        "CAPITALIZATION_QUARANTINE_COUNT": len(quarantined_cap)
        == int(cfg["pilot"]["expected_controlled_quarantine_count"]),
        "ZERO_FUTURE_EFFECTIVE_SHARE_COUNT": not cap["capitalization_state"].eq(
            "FUTURE_EFFECTIVE_SHARE_BLOCKED"
        ).any(),
        "CAPITALIZATION_REPLAYS": np.allclose(
            supported_cap["close"] * supported_cap["total_shares"],
            supported_cap["total_market_cap_cny"],
            rtol=0,
            atol=1e-6,
        )
        and np.allclose(
            supported_cap["close"] * supported_cap["float_a_shares"],
            supported_cap["float_market_cap_cny"],
            rtol=0,
            atol=1e-6,
        ),
        "METRIC_REGISTRY_UNIQUE": not metric_registry["metric_id"].duplicated().any(),
        "METRIC_DETAIL_EXACT_GRID": len(details) == len(pilot) * len(metric_registry)
        and not details.duplicated(["symbol", "metric_id"]).any(),
        "METRIC_STATES_CONTROLLED": set(details["metric_state"]).issubset(
            set(cfg["valuation"]["controlled_metric_states"])
        ),
        "VALID_METRICS_HAVE_VALUES": valid_detail["metric_value"].notna().all(),
        "INVALID_METRICS_HAVE_NO_VALUES": invalid_detail["metric_value"].isna().all(),
        "CORE_PILOT_METRIC_COVERAGE_GATE": valid_pilot_ratio
        >= float(cfg["pilot"]["minimum_valid_core_metric_ratio_supported_symbols"]),
        "PROVIDER_RATIOS_NOT_DECISION_GRADE": not details[
            "capitalization_source_id"
        ].fillna("").str.contains("CURRENT_VALUATION|PROVIDER_PE|PROVIDER_PB").any(),
        "NON_POSITIVE_EARNINGS_NEVER_VALID_PE": not details[
            details["metric_id"].eq("VAL_PE_TTM")
            & details["metric_state"].eq("NON_POSITIVE_EARNINGS")
        ]["decision_grade_eligible"].any(),
        "ANNOUNCED_BUYBACK_NOT_COMPLETED": not bool(
            event_lookup[("BUYBACK", "ANNOUNCED")].shareholder_yield_effective
        ),
        "COMPLETED_BUYBACK_EFFECTIVE": bool(
            event_lookup[("BUYBACK", "COMPLETED")].shareholder_yield_effective
        ),
        "APPROVED_ISSUANCE_NOT_EFFECTIVE": not bool(
            event_lookup[("PRIVATE_PLACEMENT", "REGULATORY_APPROVED")].share_count_effective
        ),
        "COMPLETED_ISSUANCE_EFFECTIVE": bool(
            event_lookup[("PRIVATE_PLACEMENT", "COMPLETED")].share_count_effective
        ),
        "IMPLEMENTED_DIVIDEND_ONLY_YIELD_EFFECTIVE": not bool(
            event_lookup[("CASH_DIVIDEND", "ANNOUNCED")].shareholder_yield_effective
        )
        and bool(
            event_lookup[("CASH_DIVIDEND", "IMPLEMENTED")].shareholder_yield_effective
        ),
        "NO_COMPOSITE_VALUATION_SCORE": not any(
            column in details.columns
            for column in ["valuation_score", "investment_signal", "target_price"]
        ),
        "ZERO_TRADE_AUTHORITY": set(details["trade_authority"]).issubset({"NONE"})
        and set(cap["trade_authority"]).issubset({"NONE"})
        and set(events["trade_authority"]).issubset({"NONE"}),
    }
    failures = [name for name, passed in checks.items() if not bool(passed)]
    metrics = {
        "source_benchmark_release_id": source_release["release_id"],
        "factor_engine_release_id": factor_release["release_id"],
        "financial_score_release_id": score_pointer["release_id"],
        "pilot_symbol_count": len(pilot),
        "supported_capitalization_count": len(supported_cap),
        "controlled_capitalization_quarantine_count": len(quarantined_cap),
        "valuation_metric_count": len(metric_registry),
        "valuation_metric_detail_row_count": len(details),
        "valid_or_warning_metric_row_count": int(
            details["metric_state"].isin(VALID_METRIC_STATES).sum()
        ),
        "decision_grade_metric_row_count": int(details["decision_grade_eligible"].sum()),
        "core_pilot_metric_valid_ratio_supported_symbols": valid_pilot_ratio,
        "event_type_count": len(event_registry),
        "event_contract_sample_count": len(events),
        "future_share_count_error_count": int(
            cap["capitalization_state"].eq("FUTURE_EFFECTIVE_SHARE_BLOCKED").sum()
        ),
        "automatic_action_authorized_count": 0,
    }
    decision = {
        "decision_version": "1.0.0",
        "release_id": release_id,
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "program_id": "FMDL-3D-A",
        "status": cfg["exit_status"] if not failures else "FMDL3DA_REMEDIATION_REQUIRED",
        "hard_failures": failures,
        "checks": [
            {"check_id": name, "status": "PASS" if passed else "FAIL"}
            for name, passed in checks.items()
        ],
        "metrics": metrics,
        "controlled_limitations": [
            "PILOT_ONLY_NOT_FULL_UNIVERSE_CAPITALIZATION_OR_VALUATION_CURRENT",
            "BSE_PILOT_SYMBOLS_REMAIN_CONTROLLED_CAPITALIZATION_QUARANTINE",
            "PROVIDER_SUPPLIED_PE_PB_PS_REMAIN_CROSS_CHECK_ONLY",
            "DIVIDEND_BUYBACK_AND_DILUTION_EVENTS_ARE_CONTRACT_FIXTURES_IN_3D_A_AND_REQUIRE_REAL_EVENT_BUILD_IN_3D_D",
            "EV_METRICS_REQUIRE_COMPLETE_DEBT_AND_CASH_COMPONENTS_AND_MAY_HAVE_LIMITED_COVERAGE",
            "NO_COMPOSITE_VALUATION_SCORE_TARGET_PRICE_OR_TRADE_PERMISSION",
        ],
        "authority": cfg["authority"],
        "trade_authority": "NONE",
        "next_gate": cfg["next_gate"],
    }
    write_json(candidate / "FMDL3DA_DECISION.json", decision)
    write_json(candidate / "FMDL3DA_CONTRACT_SNAPSHOT.json", cfg)
    write_json(candidate / "FMDL3DA_SOURCE_BENCHMARK_RELEASE.json", source_release)
    write_json(candidate / "FMDL3DA_FACTOR_ENGINE_RELEASE.json", factor_release)
    write_json(candidate / "FMDL3DA_FINANCIAL_SCORE_POINTER.json", score_pointer)
    write_json(candidate / "FMDL3DA_MANIFEST.json", manifest(candidate, release_id))
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
