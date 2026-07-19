from __future__ import annotations

import hashlib
import json
from pathlib import Path

import jsonschema
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fmdl3dd_engine.json"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean(row: dict) -> dict:
    return {key: (None if pd.isna(value) else value) for key, value in row.items()}


def main() -> int:
    cfg = load_json(CONFIG)
    root = ROOT / cfg["publication"]["candidate_root"]
    decision = load_json(root / "FMDL3DD_DECISION.json")
    manifest = load_json(root / "FMDL3DD_MANIFEST.json")
    current = pd.read_parquet(root / "FMDL3DD_SHAREHOLDER_RETURN_CURRENT.parquet")
    events = pd.read_parquet(root / "FMDL3DD_EVENT_LEDGER.parquet")
    attempts = pd.read_csv(root / "FMDL3DD_DIVIDEND_SOURCE_ATTEMPTS.csv", encoding="utf-8-sig", dtype={"symbol": str})
    event_schema = load_json(ROOT / "schemas/fmdl3dd_shareholder_return_event_v1.schema.json")
    current_schema = load_json(ROOT / "schemas/fmdl3dd_shareholder_return_current_v1.schema.json")

    manifest_errors = []
    for item in manifest.get("files", []):
        path = root / item["path"]
        if not path.exists():
            manifest_errors.append(f"MISSING:{item['path']}")
        elif sha256(path) != item["sha256"]:
            manifest_errors.append(f"HASH:{item['path']}")
    schema_errors = []
    for frame, schema, label in [(current, current_schema, "current"), (events, event_schema, "event")]:
        validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
        for record in frame.to_dict(orient="records"):
            for error in validator.iter_errors(clean(record)):
                schema_errors.append(f"{label}:{record.get('symbol')}:{error.message}")

    market_date = pd.Timestamp(current["market_as_of_date"].astype(str).max())
    event_dates = pd.to_datetime(events["effective_date"], errors="coerce") if len(events) else pd.Series(dtype="datetime64[ns]")
    future_effective = int(((event_dates > market_date) & events["shareholder_yield_effective"].eq(True)).sum()) if len(events) else 0
    complete = current[current["complete_shareholder_yield"]].copy()
    replay = complete["dividend_yield_ttm"] + complete["completed_buyback_yield_ttm"] - complete["completed_issuance_dilution_yield_ttm"]
    replay_errors = int((replay.sub(complete["shareholder_yield_ttm"]).abs() > 1e-12).sum())
    dividend_events = events[events["event_type"].eq("CASH_DIVIDEND")]
    cash_effective = dividend_events[dividend_events["shareholder_yield_effective"]]
    issuance_types = {"PRIVATE_PLACEMENT", "RIGHTS_ISSUE", "CONVERTIBLE_CONVERSION", "EQUITY_INCENTIVE_ISSUANCE"}
    early_issuance = events[
        events["event_type"].isin(issuance_types)
        & events["event_stage"].isin(["ANNOUNCED", "BOARD_APPROVED", "SHAREHOLDER_APPROVED", "REGULATORY_APPROVED"])
        & events["shareholder_yield_effective"]
    ] if len(events) else pd.DataFrame()
    announced_buyback = events[
        events["event_type"].eq("BUYBACK")
        & events["event_stage"].eq("ANNOUNCED")
        & events["shareholder_yield_effective"]
    ] if len(events) else pd.DataFrame()
    allowed_event_states = {"VALID", "VALID_WITH_WARNING", "NON_CASH_DISTRIBUTION", "UNCLASSIFIED_SHARE_CHANGE", "FUTURE_EVENT_BLOCKED", "MISSING_REQUIRED_VALUE", "SOURCE_EMPTY"}
    allowed_current_states = {"COMPLETE", "PARTIAL", "UNAVAILABLE"}
    allowed_source_states = {"SUCCESS", "SUCCESS_EMPTY", "FAILED"}
    checks = {
        "DECISION_ACCEPTED": decision.get("status") == cfg["exit_status"],
        "DECISION_HARD_FAILURES_EMPTY": decision.get("hard_failures") == [],
        "MANIFEST_VALID": not manifest_errors,
        "SCHEMAS_VALID": not schema_errors,
        "CURRENT_KEYS_UNIQUE": not current["symbol"].duplicated().any(),
        "CURRENT_EXACT_UNIVERSE": len(current) == int(decision["metrics"]["universe_symbol_count"]),
        "ATTEMPT_KEYS_UNIQUE": not attempts["symbol"].duplicated().any(),
        "ATTEMPTS_EXACT_UNIVERSE": len(attempts) == len(current) and set(attempts["symbol"]) == set(current["symbol"].astype(str)),
        "ATTEMPT_STATES_CONTROLLED": set(attempts["source_state"].astype(str)).issubset(allowed_source_states),
        "EVENT_KEYS_UNIQUE": events.empty or not events["event_id"].duplicated().any(),
        "EVENT_STATES_CONTROLLED": events.empty or set(events["event_state"].astype(str)).issubset(allowed_event_states),
        "CURRENT_STATES_CONTROLLED": set(current["shareholder_return_state"].astype(str)).issubset(allowed_current_states),
        "IMPLEMENTED_CASH_EVENTS_HAVE_POSITIVE_CASH": cash_effective.empty or (pd.to_numeric(cash_effective["cash_amount_per_share"], errors="coerce") > 0).all(),
        "ZERO_FUTURE_EFFECTIVE_EVENTS": future_effective == 0,
        "ZERO_ANNOUNCED_BUYBACK_COMPLETED": announced_buyback.empty,
        "ZERO_EARLY_ISSUANCE_EFFECTIVE": early_issuance.empty,
        "FORMULA_REPLAY": replay_errors == 0,
        "COMPLETE_ROWS_HAVE_COMPONENTS": complete[["dividend_yield_ttm", "completed_buyback_yield_ttm", "completed_issuance_dilution_yield_ttm", "shareholder_yield_ttm"]].notna().all().all(),
        "INCOMPLETE_ROWS_NOT_MARKED_COMPLETE": not current.loc[current["shareholder_return_state"].ne("COMPLETE"), "complete_shareholder_yield"].any(),
        "NO_SCORE_TARGET_OR_ACTION": not ({"shareholder_return_score", "investment_signal", "target_price", "target_weight", "order_quantity"} & set(current.columns)),
        "ZERO_TRADE_AUTHORITY": set(current["trade_authority"].astype(str)).issubset({"NONE"}) and (events.empty or set(events["trade_authority"].astype(str)).issubset({"NONE"})),
        "NEXT_GATE_FMDL3D_FINAL": decision.get("next_gate") == cfg["next_gate"],
    }
    failures = [key for key, value in checks.items() if not bool(value)]
    result = {
        "validation_version": "1.0.0",
        "release_id": decision.get("release_id"),
        "program_id": "FMDL-3D-D",
        "status": "PASS" if not failures else "FAIL",
        "hard_failures": failures,
        "checks": [{"check_id": key, "status": "PASS" if value else "FAIL"} for key, value in checks.items()],
        "metrics": {
            **decision.get("metrics", {}),
            "manifest_error_count": len(manifest_errors),
            "schema_error_count": len(schema_errors),
            "duplicate_event_key_count": int(events["event_id"].duplicated().sum()) if len(events) else 0,
            "future_effective_event_count_independent": future_effective,
            "formula_replay_error_count_independent": replay_errors,
        },
        "manifest_errors": manifest_errors,
        "schema_errors": schema_errors[:50],
        "authority": cfg["authority"],
        "trade_authority": "NONE",
        "next_gate": cfg["next_gate"],
    }
    (root / "FMDL3DD_VALIDATION.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
