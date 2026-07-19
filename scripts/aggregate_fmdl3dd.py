from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from scripts.fmdl3dd_core import (
    EVENT_COLUMNS,
    build_shareholder_return_current,
    derive_share_change_events,
    shares_at_date,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fmdl3dd_engine.json"
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


def build_manifest(root: Path, release_id: str) -> dict:
    files = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "FMDL3DD_MANIFEST.json":
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


def read_shards(
    input_root: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, list[dict]]:
    event_parts: list[pd.DataFrame] = []
    attempt_parts: list[pd.DataFrame] = []
    validations: list[dict] = []
    validation_paths = sorted(input_root.rglob("SHARD_VALIDATION.json"))
    if not validation_paths:
        raise RuntimeError(
            f"no FMDL-3D-D shard validation packages discovered under {input_root}"
        )
    for validation_path in validation_paths:
        directory = validation_path.parent
        attempts_path = directory / "DIVIDEND_SOURCE_ATTEMPTS.csv"
        event_path = directory / "DIVIDEND_EVENTS.parquet"
        if not attempts_path.exists():
            raise FileNotFoundError(
                f"missing dividend source attempts beside {validation_path}"
            )
        validations.append(load_json(validation_path))
        attempt_parts.append(
            pd.read_csv(
                attempts_path,
                encoding="utf-8-sig",
                dtype={"symbol": str},
            )
        )
        if event_path.exists():
            frame = pd.read_parquet(event_path)
            if len(frame):
                event_parts.append(frame)
    attempts = pd.concat(attempt_parts, ignore_index=True)
    events = (
        pd.concat(event_parts, ignore_index=True)
        if event_parts
        else pd.DataFrame(columns=EVENT_COLUMNS)
    )
    return events, attempts, validations


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", required=True)
    args = parser.parse_args()
    cfg = load_json(CONFIG)
    contract_pointer = load_json(
        ROOT / cfg["entry_gates"]["valuation_contract_pointer"]
    )
    cap_pointer = load_json(ROOT / cfg["entry_gates"]["capitalization_pointer"])
    valuation_pointer = load_json(
        ROOT / cfg["entry_gates"]["valuation_pointer"]
    )
    cap_release = load_json(ROOT / cfg["inputs"]["capitalization_release"])
    valuation_release = load_json(ROOT / cfg["inputs"]["valuation_release"])
    if (
        contract_pointer.get("status")
        != cfg["entry_gates"]["valuation_contract_status"]
    ):
        raise SystemExit("FMDL-3D-A entry gate not accepted")
    if cap_pointer.get("status") != cfg["entry_gates"]["capitalization_status"]:
        raise SystemExit("FMDL-3D-B entry gate not accepted")
    if valuation_pointer.get("status") != cfg["entry_gates"]["valuation_status"]:
        raise SystemExit("FMDL-3D-C entry gate not accepted")

    dividend_events, attempts, shard_validations = read_shards(
        Path(args.input_root)
    )
    capitalization = pd.read_parquet(ROOT / cfg["inputs"]["universe"])
    ledger = pd.read_parquet(ROOT / cfg["inputs"]["effective_share_ledger"])
    valuation_current = pd.read_parquet(
        ROOT / cfg["inputs"]["valuation_current"]
    )
    capitalization["symbol"] = capitalization["symbol"].astype(str)
    ledger["symbol"] = ledger["symbol"].astype(str)
    attempts["symbol"] = attempts["symbol"].astype(str)
    dividend_events["symbol"] = dividend_events["symbol"].astype(str)

    market_as_of_date = str(cap_release["source_release"]["as_of_date"])
    market_date = pd.Timestamp(market_as_of_date)
    share_events = derive_share_change_events(ledger, cfg, market_as_of_date)
    ledger_groups = {
        str(key): value for key, value in ledger.groupby("symbol", sort=False)
    }
    if len(dividend_events):
        dividend_events = dividend_events.copy()
        dividend_effective_dates = pd.to_datetime(
            dividend_events["effective_date"], errors="coerce"
        )
        future_dividend_mask = dividend_effective_dates > market_date
        dividend_events.loc[
            future_dividend_mask, "event_state"
        ] = "FUTURE_EVENT_BLOCKED"
        dividend_events.loc[
            future_dividend_mask, "shareholder_yield_effective"
        ] = False
        totals = []
        for row in dividend_events.itertuples(index=False):
            shares = shares_at_date(
                ledger_groups.get(str(row.symbol), pd.DataFrame()),
                str(row.effective_date),
            )
            amount = None
            if (
                shares is not None
                and row.cash_amount_per_share is not None
                and not pd.isna(row.cash_amount_per_share)
            ):
                amount = float(shares) * float(row.cash_amount_per_share)
            totals.append(amount)
        dividend_events["cash_amount_total_cny"] = totals
    event_parts = [
        frame
        for frame in [dividend_events, share_events]
        if frame is not None and len(frame)
    ]
    events = (
        pd.concat(event_parts, ignore_index=True)
        if event_parts
        else pd.DataFrame(columns=EVENT_COLUMNS)
    )
    if len(events):
        events = (
            events.drop_duplicates("event_id")
            .sort_values(["symbol", "effective_date", "event_type", "event_id"])
            .reset_index(drop=True)
        )

    release_ids = {
        "valuation_contract_release_id": contract_pointer["release_id"],
        "capitalization_release_id": cap_pointer["release_id"],
        "valuation_release_id": valuation_pointer["release_id"],
        "market_source_release_id": cap_release["source_release"]["run_id"],
    }
    current = build_shareholder_return_current(
        capitalization, attempts, events, ledger, cfg, release_ids
    )
    candidate = ROOT / cfg["publication"]["candidate_root"]
    if candidate.exists():
        shutil.rmtree(candidate)
    candidate.mkdir(parents=True, exist_ok=True)
    release_id = f"FMDL3DD_{datetime.now(TZ).strftime('%Y%m%dT%H%M%S%z')}"

    events.to_parquet(
        candidate / "FMDL3DD_EVENT_LEDGER.parquet",
        index=False,
        compression="zstd",
    )
    current.to_parquet(
        candidate / "FMDL3DD_SHAREHOLDER_RETURN_CURRENT.parquet",
        index=False,
        compression="zstd",
    )
    attempts.to_csv(
        candidate / "FMDL3DD_DIVIDEND_SOURCE_ATTEMPTS.csv",
        index=False,
        encoding="utf-8-sig",
    )
    coverage = (
        current.groupby(
            [
                "shareholder_return_state",
                "dividend_source_state",
                "share_ledger_state",
            ],
            dropna=False,
        )
        .size()
        .reset_index(name="symbol_count")
        .sort_values(
            [
                "shareholder_return_state",
                "dividend_source_state",
                "share_ledger_state",
            ]
        )
    )
    coverage.to_csv(
        candidate / "FMDL3DD_COVERAGE.csv",
        index=False,
        encoding="utf-8-sig",
    )
    event_coverage = (
        events.groupby(
            [
                "event_type",
                "event_stage",
                "event_state",
                "shareholder_yield_effective",
            ],
            dropna=False,
        )
        .size()
        .reset_index(name="event_count")
        .sort_values(["event_type", "event_stage", "event_state"])
        if len(events)
        else pd.DataFrame(
            columns=[
                "event_type",
                "event_stage",
                "event_state",
                "shareholder_yield_effective",
                "event_count",
            ]
        )
    )
    event_coverage.to_csv(
        candidate / "FMDL3DD_EVENT_COVERAGE.csv",
        index=False,
        encoding="utf-8-sig",
    )
    quarantine = current[
        current["shareholder_return_state"].ne("COMPLETE")
    ].copy()
    quarantine.to_csv(
        candidate / "FMDL3DD_QUARANTINE.csv",
        index=False,
        encoding="utf-8-sig",
    )

    source_success_ratio = (
        float(
            attempts["source_state"].isin(["SUCCESS", "SUCCESS_EMPTY"]).mean()
        )
        if len(attempts)
        else 0.0
    )
    event_dates = pd.to_datetime(events["effective_date"], errors="coerce")
    future_effective = int(
        (
            (event_dates > market_date)
            & events["shareholder_yield_effective"].eq(True)
        ).sum()
    )
    announced_buyback_completed = int(
        (
            events["event_type"].eq("BUYBACK")
            & events["event_stage"].eq("ANNOUNCED")
            & events["shareholder_yield_effective"].eq(True)
        ).sum()
    )
    approved_issuance_effective = int(
        (
            events["event_type"].isin(["PRIVATE_PLACEMENT", "RIGHTS_ISSUE"])
            & events["event_stage"].isin(
                [
                    "ANNOUNCED",
                    "BOARD_APPROVED",
                    "SHAREHOLDER_APPROVED",
                    "REGULATORY_APPROVED",
                ]
            )
            & events["shareholder_yield_effective"].eq(True)
        ).sum()
    )
    formula_replay = current[current["complete_shareholder_yield"]].copy()
    replay = (
        formula_replay["dividend_yield_ttm"]
        + formula_replay["completed_buyback_yield_ttm"]
        - formula_replay["completed_issuance_dilution_yield_ttm"]
    )
    replay_errors = int(
        (
            replay.sub(formula_replay["shareholder_yield_ttm"]).abs() > 1e-12
        ).sum()
    )
    checks = {
        "ENTRY_FMDL3DA_ACCEPTED": contract_pointer.get("status")
        == cfg["entry_gates"]["valuation_contract_status"],
        "ENTRY_FMDL3DB_ACCEPTED": cap_pointer.get("status")
        == cfg["entry_gates"]["capitalization_status"],
        "ENTRY_FMDL3DC_ACCEPTED": valuation_pointer.get("status")
        == cfg["entry_gates"]["valuation_status"],
        "ALL_SHARDS_VALIDATED": len(shard_validations)
        == int(cfg["sharding"]["shard_count"])
        and all(item.get("status") == "PASS" for item in shard_validations),
        "ATTEMPTS_EXACT_UNIVERSE": len(attempts) == len(capitalization)
        and not attempts["symbol"].duplicated().any()
        and set(attempts["symbol"]) == set(capitalization["symbol"]),
        "DIVIDEND_SOURCE_SUCCESS_GATE": source_success_ratio
        >= float(
            cfg["quality_gates"]["minimum_dividend_source_attempt_success_ratio"]
        ),
        "CURRENT_EXACT_UNIVERSE": len(current) == len(capitalization)
        and not current["symbol"].duplicated().any(),
        "VALUATION_CURRENT_ALIGNED": len(valuation_current)
        == len(capitalization)
        and set(valuation_current["symbol"].astype(str))
        == set(capitalization["symbol"]),
        "EVENT_KEYS_UNIQUE": not events["event_id"].duplicated().any(),
        "ZERO_FUTURE_EFFECTIVE_EVENTS": future_effective == 0,
        "ZERO_ANNOUNCED_BUYBACK_COMPLETED": announced_buyback_completed == 0,
        "ZERO_APPROVED_ISSUANCE_EFFECTIVE": approved_issuance_effective == 0,
        "FORMULA_REPLAY": replay_errors == 0,
        "COMPLETE_ROWS_HAVE_VALUES": current.loc[
            current["complete_shareholder_yield"],
            [
                "dividend_yield_ttm",
                "completed_buyback_yield_ttm",
                "completed_issuance_dilution_yield_ttm",
                "shareholder_yield_ttm",
            ],
        ]
        .notna()
        .all()
        .all(),
        "INCOMPLETE_ROWS_NOT_CLAIMED_COMPLETE": not current.loc[
            current["shareholder_return_state"].ne("COMPLETE"),
            "complete_shareholder_yield",
        ].any(),
        "ZERO_SCORE_TARGET_OR_ACTION": not (
            {
                "shareholder_return_score",
                "investment_signal",
                "target_price",
                "target_weight",
                "order_quantity",
            }
            & set(current.columns)
        ),
        "ZERO_TRADE_AUTHORITY": set(
            current["trade_authority"].astype(str)
        ).issubset({"NONE"})
        and set(events["trade_authority"].astype(str)).issubset({"NONE"}),
    }
    failures = [key for key, value in checks.items() if not bool(value)]
    state_counts = {
        str(key): int(value)
        for key, value in current["shareholder_return_state"]
        .value_counts(dropna=False)
        .items()
    }
    event_type_counts = {
        str(key): int(value)
        for key, value in events["event_type"].value_counts(dropna=False).items()
    }
    metrics = {
        **release_ids,
        "market_as_of_date": market_as_of_date,
        "universe_symbol_count": int(len(capitalization)),
        "shareholder_return_current_row_count": int(len(current)),
        "event_ledger_row_count": int(len(events)),
        "dividend_event_row_count": int(
            events["event_type"].eq("CASH_DIVIDEND").sum()
        ),
        "share_change_event_row_count": int(
            events["event_type"].ne("CASH_DIVIDEND").sum()
        ),
        "dividend_source_attempt_count": int(len(attempts)),
        "dividend_source_success_ratio": source_success_ratio,
        "complete_shareholder_yield_count": int(
            current["complete_shareholder_yield"].sum()
        ),
        "partial_or_unavailable_count": int(
            (~current["complete_shareholder_yield"]).sum()
        ),
        "positive_dividend_yield_count": int(
            pd.to_numeric(current["dividend_yield_ttm"], errors="coerce")
            .gt(0)
            .sum()
        ),
        "positive_buyback_yield_count": int(
            pd.to_numeric(
                current["completed_buyback_yield_ttm"], errors="coerce"
            )
            .gt(0)
            .sum()
        ),
        "positive_issuance_dilution_count": int(
            pd.to_numeric(
                current["completed_issuance_dilution_yield_ttm"], errors="coerce"
            )
            .gt(0)
            .sum()
        ),
        "future_effective_event_count": future_effective,
        "announced_buyback_treated_completed_count": announced_buyback_completed,
        "approved_issuance_treated_effective_count": approved_issuance_effective,
        "formula_replay_error_count": replay_errors,
        "state_counts": state_counts,
        "event_type_counts": event_type_counts,
        "automatic_action_authorized_count": 0,
    }
    decision = {
        "decision_version": "1.0.0",
        "release_id": release_id,
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "program_id": "FMDL-3D-D",
        "status": (
            cfg["exit_status"] if not failures else "FMDL3DD_REMEDIATION_REQUIRED"
        ),
        "hard_failures": failures,
        "checks": [
            {"check_id": key, "status": "PASS" if value else "FAIL"}
            for key, value in checks.items()
        ],
        "metrics": metrics,
        "controlled_limitations": [
            "DIVIDEND_EVENTS_USE_FREE_EASTMONEY_REPORT_PERIOD_ROUTE_WITH_RETRY_AND_EXPLICIT_FAILURE_STATE",
            "DIVIDEND_YIELD_USES_IMPLEMENTED_CASH_DIVIDEND_PER_SHARE_OVER_LATEST_COMPLETED_SESSION_CLOSE",
            "BUYBACK_AND_DILUTION_YIELDS_USE_COMPLETED_EFFECTIVE_SHARE_CHANGE_RATIOS_NOT_UNVERIFIED_ANNOUNCEMENT_CASH_AMOUNTS",
            "UNCLASSIFIED_SHARE_CHANGES_DO_NOT_ENTER_SHAREHOLDER_YIELD",
            "SHAREHOLDER_YIELD_IS_COMPONENT_EVIDENCE_NOT_A_VALUATION_SCORE_OR_TRADE_SIGNAL",
            "NO_TARGET_PRICE_PORTFOLIO_ACTION_OR_TRADE_AUTHORITY",
        ],
        "authority": cfg["authority"],
        "trade_authority": "NONE",
        "next_gate": cfg["next_gate"],
    }
    write_json(candidate / "FMDL3DD_DECISION.json", decision)
    write_json(
        candidate / "FMDL3DD_SOURCE_RELEASES.json",
        {
            "valuation_contract_pointer": contract_pointer,
            "capitalization_pointer": cap_pointer,
            "valuation_pointer": valuation_pointer,
            "capitalization_release": cap_release,
            "valuation_release": valuation_release,
        },
    )
    write_json(
        candidate / "FMDL3DD_MANIFEST.json",
        build_manifest(candidate, release_id),
    )
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
