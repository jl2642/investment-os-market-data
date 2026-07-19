from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from scripts.fmdl3db_core import (
    AUTHORITY,
    TRADE_AUTHORITY,
    VALID_CAP_STATES,
    ROOT,
    create_manifest,
    load_json,
    sha256_file,
    write_json,
)

TZ = ZoneInfo("Asia/Shanghai")
CONFIG = ROOT / "config/fmdl3db_engine.json"


def _discover(input_root: Path, filename: str) -> list[Path]:
    return sorted(path for path in input_root.rglob(filename) if path.is_file())


def _load_frames(paths: list[Path], reader) -> pd.DataFrame:
    frames = [reader(path) for path in paths]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=CONFIG)
    args = parser.parse_args()
    config = load_json(args.config)
    shard_count = int(config["sharding"]["shard_count"])
    current_paths = _discover(args.input_root, "SHARD_CAPITALIZATION_CURRENT.parquet")
    ledger_paths = _discover(args.input_root, "SHARD_EFFECTIVE_SHARE_LEDGER.parquet")
    retry_paths = _discover(args.input_root, "SHARD_RETRY_LEDGER.csv")
    membership_paths = _discover(args.input_root, "SHARD_MEMBERSHIP.csv")
    decision_paths = _discover(args.input_root, "SHARD_DECISION.json")
    validation_paths = _discover(args.input_root, "SHARD_VALIDATION.json")

    current = _load_frames(current_paths, pd.read_parquet)
    ledger = _load_frames(ledger_paths, pd.read_parquet)
    retry = _load_frames(
        retry_paths,
        lambda path: pd.read_csv(path, encoding="utf-8-sig", dtype={"symbol": str}),
    )
    membership = _load_frames(
        membership_paths,
        lambda path: pd.read_csv(path, encoding="utf-8-sig", dtype={"symbol": str}),
    )
    shard_decisions = [load_json(path) for path in decision_paths]
    shard_validations = [load_json(path) for path in validation_paths]

    entry = load_json(ROOT / config["entry_gate"]["pointer_path"])
    release = load_json(ROOT / config["market_inputs"]["current_release_path"])
    universe_manifest = load_json(ROOT / config["market_inputs"]["universe_manifest_path"])
    snapshot_manifest = load_json(ROOT / config["market_inputs"]["snapshot_manifest_path"])
    universe_path = ROOT / config["market_inputs"]["universe_path"]
    snapshot_path = ROOT / config["market_inputs"]["snapshot_path"]
    universe = pd.read_csv(universe_path, encoding="utf-8-sig", dtype={"symbol": str})
    snapshot = pd.read_csv(snapshot_path, encoding="utf-8-sig", dtype={"symbol": str})
    universe_symbols = set(universe["symbol"].astype(str))

    candidate = ROOT / config["publication"]["candidate_root"]
    shutil.rmtree(candidate, ignore_errors=True)
    candidate.mkdir(parents=True, exist_ok=True)
    release_id = f"FMDL3DB_{datetime.now(TZ).strftime('%Y%m%dT%H%M%S%z')}"

    if len(current):
        current["symbol"] = current["symbol"].astype(str)
        current = current.sort_values("symbol").reset_index(drop=True)
    if len(ledger):
        ledger["symbol"] = ledger["symbol"].astype(str)
        ledger = ledger.sort_values(
            ["symbol", "source_effective_date", "source_row_hash"]
        ).reset_index(drop=True)
    if len(retry):
        retry["symbol"] = retry["symbol"].astype(str)
        retry = retry.sort_values("symbol").reset_index(drop=True)
    if len(membership):
        membership["symbol"] = membership["symbol"].astype(str)
        membership = membership.sort_values("symbol").reset_index(drop=True)

    valid = current[current["capitalization_state"].isin(VALID_CAP_STATES)] if len(current) else current
    invalid = current[~current["capitalization_state"].isin(VALID_CAP_STATES)] if len(current) else current
    selected = ledger[ledger["selected_for_current"].eq(True)] if len(ledger) else ledger
    accepted_price = (
        current["close"].notna()
        & (current["close"] > 0)
        & current["price_row_hash"].notna()
    ) if len(current) else pd.Series(dtype=bool)
    price_coverage = float(accepted_price.mean()) if len(current) else 0.0
    share_coverage = float(len(valid) / len(current)) if len(current) else 0.0
    non_bse = current[current["board"].ne("BSE")] if len(current) else current
    non_bse_valid = non_bse[non_bse["capitalization_state"].isin(VALID_CAP_STATES)] if len(non_bse) else non_bse
    non_bse_coverage = float(len(non_bse_valid) / len(non_bse)) if len(non_bse) else 0.0

    coverage_rows: list[dict] = []
    for board, frame in current.groupby("board", dropna=False) if len(current) else []:
        valid_count = int(frame["capitalization_state"].isin(VALID_CAP_STATES).sum())
        price_count = int(
            (
                frame["close"].notna()
                & (frame["close"] > 0)
                & frame["price_row_hash"].notna()
            ).sum()
        )
        coverage_rows.append(
            {
                "dimension": "BOARD",
                "dimension_value": str(board),
                "symbol_count": int(len(frame)),
                "accepted_price_count": price_count,
                "accepted_price_ratio": float(price_count / len(frame)),
                "valid_capitalization_count": valid_count,
                "valid_capitalization_ratio": float(valid_count / len(frame)),
                "controlled_quarantine_count": int(len(frame) - valid_count),
                "authority": AUTHORITY,
                "trade_authority": TRADE_AUTHORITY,
            }
        )
    for state, frame in current.groupby("capitalization_state", dropna=False) if len(current) else []:
        coverage_rows.append(
            {
                "dimension": "STATE",
                "dimension_value": str(state),
                "symbol_count": int(len(frame)),
                "accepted_price_count": int(frame["close"].notna().sum()),
                "accepted_price_ratio": float(frame["close"].notna().mean()),
                "valid_capitalization_count": int(
                    frame["capitalization_state"].isin(VALID_CAP_STATES).sum()
                ),
                "valid_capitalization_ratio": float(
                    frame["capitalization_state"].isin(VALID_CAP_STATES).mean()
                ),
                "controlled_quarantine_count": int(
                    (~frame["capitalization_state"].isin(VALID_CAP_STATES)).sum()
                ),
                "authority": AUTHORITY,
                "trade_authority": TRADE_AUTHORITY,
            }
        )
    coverage = pd.DataFrame(coverage_rows)

    quarantine_columns = [
        "symbol",
        "name",
        "exchange",
        "board",
        "price_as_of_date",
        "close",
        "capitalization_state",
        "state_reason",
        "attempt_count",
        "source_error_type",
        "source_error_message",
        "provider_row_count",
        "normalized_ledger_row_count",
        "future_share_row_count",
        "lineage_id",
        "authority",
        "trade_authority",
    ]
    quarantine = invalid[[column for column in quarantine_columns if column in invalid.columns]].copy()

    current.to_parquet(
        candidate / "FMDL3DB_CAPITALIZATION_CURRENT.parquet",
        index=False,
        compression="zstd",
    )
    ledger.to_parquet(
        candidate / "FMDL3DB_EFFECTIVE_SHARE_LEDGER.parquet",
        index=False,
        compression="zstd",
    )
    retry.to_csv(
        candidate / "FMDL3DB_RETRY_LEDGER.csv",
        index=False,
        encoding="utf-8-sig",
    )
    coverage.to_csv(
        candidate / "FMDL3DB_COVERAGE.csv",
        index=False,
        encoding="utf-8-sig",
    )
    quarantine.to_csv(
        candidate / "FMDL3DB_QUARANTINE.csv",
        index=False,
        encoding="utf-8-sig",
    )

    acceptance = config["acceptance"]
    replay_total = valid["close"] * valid["total_shares"] if len(valid) else pd.Series(dtype=float)
    replay_float = valid["close"] * valid["float_a_shares"] if len(valid) else pd.Series(dtype=float)
    board_ratios = {
        str(row["dimension_value"]): float(row["valid_capitalization_ratio"])
        for row in coverage_rows
        if row["dimension"] == "BOARD"
    }
    board_gates = {
        board: board_ratios.get(board, 0.0) >= float(threshold)
        for board, threshold in acceptance["minimum_effective_share_coverage_by_board"].items()
    }
    selected_trace = set(selected["source_row_hash"]) if len(selected) else set()
    valid_trace = set(valid["share_source_row_hash"].dropna()) if len(valid) else set()
    current_symbols = set(current["symbol"]) if len(current) else set()
    membership_symbols = set(membership["symbol"]) if len(membership) else set()
    future_selected = int(
        selected["eligibility_state"].eq("FUTURE_EFFECTIVE").sum()
    ) if len(selected) else 0
    non_positive_selected = int(
        ((selected["total_shares"] <= 0) | (selected["float_a_shares"] <= 0)).sum()
    ) if len(selected) else 0
    future_current = int(
        (
            pd.to_datetime(valid["share_effective_date"], errors="coerce")
            > pd.to_datetime(valid["price_as_of_date"], errors="coerce")
        ).sum()
    ) if len(valid) else 0
    all_shards_pass = len(shard_validations) == shard_count and all(
        item.get("status") == "PASS" and item.get("hard_failures") == []
        for item in shard_validations
    )

    checks = {
        "ENTRY_FMDL3DA_ACCEPTED": entry.get("status") == config["entry_gate"]["required_status"],
        "SOURCE_CURRENT_HAS_NO_HARD_FAILURES": release.get("hard_failures") == [],
        "SOURCE_DATASET_HASHES_MATCH": sha256_file(universe_path)
        == release["current_files"]["a_share_universe"]["sha256"]
        and sha256_file(snapshot_path)
        == release["current_files"]["daily_market_snapshot"]["sha256"],
        "EXPECTED_SHARD_PACKAGE_COUNT": len(current_paths) == shard_count
        and len(ledger_paths) == shard_count
        and len(retry_paths) == shard_count
        and len(membership_paths) == shard_count
        and len(decision_paths) == shard_count
        and len(validation_paths) == shard_count,
        "ALL_SHARD_VALIDATIONS_PASS": all_shards_pass,
        "MEMBERSHIP_KEYS_UNIQUE": not membership["symbol"].duplicated().any(),
        "MEMBERSHIP_EXACT_UNIVERSE": len(membership) == len(universe)
        and membership_symbols == universe_symbols,
        "CURRENT_EXACT_UNIVERSE": len(current) == len(universe)
        and current_symbols == universe_symbols,
        "CURRENT_KEYS_UNIQUE": not current["symbol"].duplicated().any(),
        "RETRY_LEDGER_EXACT_UNIVERSE": len(retry) == len(universe)
        and set(retry["symbol"]) == universe_symbols,
        "LEDGER_KEYS_UNIQUE": not ledger.duplicated(
            ["symbol", "source_effective_date", "source_row_hash"]
        ).any() if len(ledger) else True,
        "ACCEPTED_PRICE_COVERAGE_GATE": price_coverage
        >= float(acceptance["minimum_accepted_price_coverage"]),
        "EFFECTIVE_SHARE_COVERAGE_GATE": share_coverage
        >= float(acceptance["minimum_effective_share_coverage_overall"]),
        "NON_BSE_EFFECTIVE_SHARE_COVERAGE_GATE": non_bse_coverage
        >= float(acceptance["minimum_effective_share_coverage_non_bse"]),
        "BOARD_COVERAGE_GATES": all(board_gates.values()),
        "VALID_ROWS_HAVE_COMPLETE_VALUES": valid[
            ["close", "share_effective_date", "total_shares", "float_a_shares", "total_market_cap_cny", "float_market_cap_cny", "share_source_row_hash"]
        ].notna().all().all(),
        "INVALID_ROWS_HAVE_NULL_CAPITALIZATION": invalid[
            ["total_market_cap_cny", "float_market_cap_cny"]
        ].isna().all().all(),
        "ZERO_FUTURE_SELECTED_SHARE_ROWS": future_selected
        <= int(acceptance["maximum_future_selected_share_rows"]),
        "ZERO_FUTURE_CURRENT_SHARE_ROWS": future_current == 0,
        "ZERO_NON_POSITIVE_SELECTED_SHARES": non_positive_selected
        <= int(acceptance["maximum_non_positive_selected_share_rows"]),
        "FLOAT_SHARES_NOT_GREATER_THAN_TOTAL": (
            valid["float_a_shares"] <= valid["total_shares"]
        ).all(),
        "FLOAT_MARKET_CAP_NOT_GREATER_THAN_TOTAL": (
            valid["float_market_cap_cny"] <= valid["total_market_cap_cny"]
        ).all(),
        "ONE_SELECTED_LEDGER_ROW_PER_VALID_CURRENT": len(selected) == len(valid)
        and not selected["symbol"].duplicated().any(),
        "CURRENT_SHARE_LINEAGE_TRACEABLE": selected_trace == valid_trace,
        "TOTAL_MARKET_CAP_REPLAYS": np.allclose(
            replay_total,
            valid["total_market_cap_cny"],
            rtol=float(acceptance["capitalization_relative_tolerance"]),
            atol=float(acceptance["capitalization_absolute_tolerance_cny"]),
        ),
        "FLOAT_MARKET_CAP_REPLAYS": np.allclose(
            replay_float,
            valid["float_market_cap_cny"],
            rtol=float(acceptance["capitalization_relative_tolerance"]),
            atol=float(acceptance["capitalization_absolute_tolerance_cny"]),
        ),
        "PRICE_AND_SHARE_TIMESTAMPS_PRESERVED": valid[
            ["price_as_of_date", "price_source_timestamp", "share_effective_date"]
        ].notna().all().all(),
        "INVALID_STATES_HAVE_REASON": invalid["state_reason"].fillna("").str.len().gt(0).all(),
        "NO_PROVIDER_VALUATION_AUTHORITY": not any(
            column in current.columns
            for column in ["provider_pe", "provider_pb", "provider_ps", "valuation_score", "target_price"]
        ),
        "ZERO_TRADE_AUTHORITY": set(current["trade_authority"]) == {"NONE"}
        and (ledger.empty or set(ledger["trade_authority"]) == {"NONE"})
        and set(retry["trade_authority"]) == {"NONE"},
    }
    failures = [key for key, passed in checks.items() if not bool(passed)]
    state_counts = {
        str(key): int(value)
        for key, value in current["capitalization_state"].value_counts(dropna=False).items()
    }
    board_metrics = {
        board: {
            "valid_capitalization_ratio": board_ratios.get(board, 0.0),
            "minimum_required": float(threshold),
            "gate_status": "PASS" if board_gates[board] else "FAIL",
        }
        for board, threshold in acceptance["minimum_effective_share_coverage_by_board"].items()
    }
    metrics = {
        "source_market_release_id": release["run_id"],
        "source_as_of_date": release["as_of_date"],
        "universe_symbol_count": len(universe),
        "snapshot_row_count": len(snapshot),
        "shard_count": shard_count,
        "capitalization_current_row_count": len(current),
        "effective_share_ledger_row_count": len(ledger),
        "retry_ledger_row_count": len(retry),
        "accepted_price_count": int(accepted_price.sum()),
        "accepted_price_coverage_ratio": price_coverage,
        "valid_or_warning_capitalization_count": len(valid),
        "effective_share_coverage_ratio": share_coverage,
        "non_bse_effective_share_coverage_ratio": non_bse_coverage,
        "controlled_quarantine_count": len(invalid),
        "future_source_ledger_row_count": int(
            ledger["eligibility_state"].eq("FUTURE_EFFECTIVE").sum()
        ) if len(ledger) else 0,
        "future_selected_share_row_count": future_selected,
        "future_current_share_row_count": future_current,
        "non_positive_selected_share_row_count": non_positive_selected,
        "duplicate_current_key_count": int(current["symbol"].duplicated().sum()),
        "duplicate_ledger_key_count": int(
            ledger.duplicated(["symbol", "source_effective_date", "source_row_hash"]).sum()
        ) if len(ledger) else 0,
        "maximum_attempt_count": int(retry["attempt_count"].max()) if len(retry) else 0,
        "total_source_attempt_count": int(retry["attempt_count"].sum()) if len(retry) else 0,
        "source_elapsed_seconds_sum": float(retry["elapsed_seconds"].sum()) if len(retry) else 0.0,
        "automatic_action_authorized_count": 0,
        "state_counts": state_counts,
        "board_coverage": board_metrics,
    }
    decision = {
        "decision_version": "1.0.0",
        "release_id": release_id,
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "program_id": "FMDL-3D-B",
        "status": config["exit_status"] if not failures else "FMDL3DB_REMEDIATION_REQUIRED",
        "hard_failures": failures,
        "checks": [
            {"check_id": key, "status": "PASS" if passed else "FAIL"}
            for key, passed in checks.items()
        ],
        "metrics": metrics,
        "controlled_limitations": [
            "EFFECTIVE_SHARE_COUNT_PRIMARY_ROUTE_IS_SINGLE_FREE_PROVIDER_WITH_RETRY_AND_EXPLICIT_QUARANTINE",
            "CURRENT_CAPITALIZATION_USES_LATEST_COMPLETED_SESSION_CLOSE_NOT_INTRADAY_PRICE",
            "FUTURE_PROVIDER_SHARE_ROWS_ARE_PRESERVED_AS_LEDGER_EVIDENCE_BUT_NEVER_SELECTED",
            "PROVIDER_MARKET_CAP_AND_VALUATION_FIELDS_ARE_NOT_DECISION_GRADE",
            "VALUATION_RATIOS_REMAIN_FMDL_3D_C_WORK",
            "DIVIDEND_BUYBACK_AND_DILUTION_EVENT_CURRENT_REMAINS_FMDL_3D_D_WORK",
            "NO_SCORE_TARGET_PRICE_PORTFOLIO_ACTION_OR_TRADE_AUTHORITY",
        ],
        "source_release": {
            "run_id": release["run_id"],
            "as_of_date": release["as_of_date"],
            "universe_dataset_version": release["dataset_versions"]["a_share_universe"],
            "snapshot_dataset_version": release["dataset_versions"]["daily_market_snapshot"],
            "universe_sha256": release["current_files"]["a_share_universe"]["sha256"],
            "snapshot_sha256": release["current_files"]["daily_market_snapshot"]["sha256"],
        },
        "authority": AUTHORITY,
        "trade_authority": TRADE_AUTHORITY,
        "next_gate": config["next_gate"],
    }
    write_json(candidate / "FMDL3DB_DECISION.json", decision)
    write_json(candidate / "FMDL3DB_CONTRACT_SNAPSHOT.json", config)
    write_json(candidate / "FMDL3DB_SOURCE_MARKET_RELEASE.json", release)
    write_json(candidate / "FMDL3DB_SOURCE_UNIVERSE_MANIFEST.json", universe_manifest)
    write_json(candidate / "FMDL3DB_SOURCE_SNAPSHOT_MANIFEST.json", snapshot_manifest)
    write_json(candidate / "FMDL3DB_SHARD_DECISIONS.json", shard_decisions)
    write_json(candidate / "FMDL3DB_SHARD_VALIDATIONS.json", shard_validations)
    write_json(candidate / "FMDL3DB_MANIFEST.json", create_manifest(candidate, release_id, "FMDL-3D-B"))
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
