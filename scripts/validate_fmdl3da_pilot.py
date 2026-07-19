from __future__ import annotations

import hashlib
import json
from pathlib import Path

import jsonschema
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fmdl3da_contract.json"
TOLERANCE = ROOT / "config/fmdl3da_numeric_tolerance.json"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean_record(row: dict) -> dict:
    return {key: (None if pd.isna(value) else value) for key, value in row.items()}


def main() -> int:
    cfg = load_json(CONFIG)
    tolerance = load_json(TOLERANCE)["capitalization_replay"]
    replay_rtol = float(tolerance["relative_tolerance"])
    replay_atol = float(tolerance["absolute_tolerance_cny"])
    root = ROOT / cfg["publication"]["candidate_root"]
    decision = load_json(root / "FMDL3DA_DECISION.json")
    manifest = load_json(root / "FMDL3DA_MANIFEST.json")
    cap = pd.read_csv(
        root / "FMDL3DA_CAPITALIZATION_PILOT.csv",
        encoding="utf-8-sig",
        dtype={"symbol": str},
    )
    details = pd.read_parquet(root / "FMDL3DA_VALUATION_METRIC_DETAIL.parquet")
    snapshot = pd.read_parquet(root / "FMDL3DA_VALUATION_PILOT_CURRENT.parquet")
    events = pd.read_csv(
        root / "FMDL3DA_SHAREHOLDER_EVENT_CONTRACT_SAMPLES.csv",
        encoding="utf-8-sig",
        dtype={"symbol": str},
    )
    metric_registry = pd.read_csv(
        ROOT / cfg["inputs"]["valuation_metric_registry"], encoding="utf-8-sig"
    )

    manifest_errors: list[str] = []
    for item in manifest.get("files", []):
        path = root / item["path"]
        if not path.exists():
            manifest_errors.append(f"MISSING:{item['path']}")
        elif sha256(path) != item["sha256"]:
            manifest_errors.append(f"HASH:{item['path']}")

    schema_errors: list[str] = []
    schemas = [
        (
            cap,
            load_json(ROOT / "schemas/fmdl3da_capitalization_snapshot_v1.schema.json"),
            "capitalization",
        ),
        (
            details,
            load_json(ROOT / "schemas/fmdl3da_valuation_metric_detail_v1.schema.json"),
            "valuation",
        ),
        (
            events,
            load_json(ROOT / "schemas/fmdl3da_shareholder_return_event_v1.schema.json"),
            "event",
        ),
    ]
    for frame, schema, label in schemas:
        validator = jsonschema.Draft202012Validator(
            schema, format_checker=jsonschema.FormatChecker()
        )
        for record in frame.to_dict(orient="records"):
            cleaned = clean_record(record)
            for error in validator.iter_errors(cleaned):
                schema_errors.append(
                    f"{label}:{cleaned.get('symbol')}:{error.message}"
                )

    valid_states = set(cfg["valuation"]["valid_metric_states"])
    valid = details[details["metric_state"].isin(valid_states)]
    invalid = details[~details["metric_state"].isin(valid_states)]
    supported = cap[cap["capitalization_state"].isin(["VALID", "VALID_WITH_WARNING"])]
    future_share_count = (
        pd.to_datetime(supported["share_effective_date"], errors="coerce")
        > pd.to_datetime(supported["market_as_of_date"], errors="coerce")
    )
    replay_total = supported["close"] * supported["total_shares"]
    replay_float = supported["close"] * supported["float_a_shares"]
    total_absolute_difference = (
        replay_total - supported["total_market_cap_cny"]
    ).abs()
    float_absolute_difference = (
        replay_float - supported["float_market_cap_cny"]
    ).abs()

    pe = details[details["metric_id"].eq("VAL_PE_TTM")]
    pb = details[details["metric_id"].eq("VAL_PB")]
    ps_financial = details[
        details["metric_id"].eq("VAL_PS_TTM")
        & details["sector_profile"].isin(
            ["BANK", "INSURANCE", "SECURITIES_AND_BROKERAGE"]
        )
    ]
    event_index = {
        (str(row.event_type), str(row.event_stage)): row
        for row in events.itertuples(index=False)
    }
    checks = {
        "DECISION_ACCEPTED": decision.get("status") == cfg["exit_status"],
        "DECISION_HARD_FAILURES_EMPTY": decision.get("hard_failures") == [],
        "MANIFEST_VALID": not manifest_errors,
        "ROW_SCHEMAS_VALID": not schema_errors,
        "CAPITALIZATION_KEYS_UNIQUE": not cap["symbol"].duplicated().any(),
        "CAPITALIZATION_EXACT_PILOT": len(cap)
        == int(cfg["pilot"]["expected_symbol_count"]),
        "VALUATION_GRID_EXACT": len(details) == len(cap) * len(metric_registry)
        and not details.duplicated(["symbol", "metric_id"]).any(),
        "SNAPSHOT_KEYS_UNIQUE": len(snapshot) == len(cap)
        and not snapshot["symbol"].duplicated().any(),
        "VALID_METRICS_HAVE_VALUES": valid["metric_value"].notna().all(),
        "INVALID_METRICS_ARE_NULL": invalid["metric_value"].isna().all(),
        "METRIC_STATES_CONTROLLED": set(details["metric_state"]).issubset(
            set(cfg["valuation"]["controlled_metric_states"])
        ),
        "ZERO_FUTURE_EFFECTIVE_SHARES": not future_share_count.any(),
        "TOTAL_MARKET_CAP_REPLAYS": np.allclose(
            replay_total,
            supported["total_market_cap_cny"],
            rtol=replay_rtol,
            atol=replay_atol,
        ),
        "FLOAT_MARKET_CAP_REPLAYS": np.allclose(
            replay_float,
            supported["float_market_cap_cny"],
            rtol=replay_rtol,
            atol=replay_atol,
        ),
        "PE_VALID_ONLY_POSITIVE": not pe[
            pe["metric_state"].eq("NON_POSITIVE_EARNINGS")
        ]["decision_grade_eligible"].any(),
        "PB_VALID_ONLY_POSITIVE": not pb[
            pb["metric_state"].eq("NON_POSITIVE_BOOK_EQUITY")
        ]["decision_grade_eligible"].any(),
        "FINANCIAL_PS_NOT_APPLICABLE": ps_financial["metric_state"].eq(
            "NOT_APPLICABLE_SECTOR"
        ).all(),
        "BUYBACK_STAGE_CONTROL": not bool(
            event_index[("BUYBACK", "ANNOUNCED")].shareholder_yield_effective
        )
        and bool(
            event_index[("BUYBACK", "COMPLETED")].shareholder_yield_effective
        ),
        "ISSUANCE_STAGE_CONTROL": not bool(
            event_index[("PRIVATE_PLACEMENT", "REGULATORY_APPROVED")].share_count_effective
        )
        and bool(
            event_index[("PRIVATE_PLACEMENT", "COMPLETED")].share_count_effective
        ),
        "DIVIDEND_STAGE_CONTROL": not bool(
            event_index[("CASH_DIVIDEND", "ANNOUNCED")].shareholder_yield_effective
        )
        and bool(
            event_index[("CASH_DIVIDEND", "IMPLEMENTED")].shareholder_yield_effective
        ),
        "NO_SCORE_SIGNAL_OR_TARGET_PRICE": not (
            {"valuation_score", "investment_signal", "target_price", "target_weight"}
            & set(details.columns)
        ),
        "ZERO_TRADE_AUTHORITY": set(details["trade_authority"]).issubset({"NONE"})
        and set(cap["trade_authority"]).issubset({"NONE"})
        and set(events["trade_authority"]).issubset({"NONE"}),
        "NEXT_GATE_FMDL3DB": decision.get("next_gate") == cfg["next_gate"],
    }
    failures = [name for name, passed in checks.items() if not bool(passed)]
    result = {
        "validation_version": "1.0.0",
        "release_id": decision.get("release_id"),
        "status": "PASS" if not failures else "FAIL",
        "hard_failures": failures,
        "checks": [
            {"check_id": name, "status": "PASS" if passed else "FAIL"}
            for name, passed in checks.items()
        ],
        "metrics": {
            **decision.get("metrics", {}),
            "manifest_error_count": len(manifest_errors),
            "schema_error_count": len(schema_errors),
            "duplicate_metric_key_count": int(
                details.duplicated(["symbol", "metric_id"]).sum()
            ),
            "future_effective_share_count": int(future_share_count.sum()),
            "capitalization_replay_absolute_tolerance_cny": replay_atol,
            "capitalization_replay_relative_tolerance": replay_rtol,
            "total_market_cap_max_absolute_difference_cny": float(
                total_absolute_difference.max()
            ) if len(total_absolute_difference) else 0.0,
            "float_market_cap_max_absolute_difference_cny": float(
                float_absolute_difference.max()
            ) if len(float_absolute_difference) else 0.0,
        },
        "manifest_errors": manifest_errors,
        "schema_errors": schema_errors[:50],
        "authority": cfg["authority"],
        "trade_authority": "NONE",
        "next_gate": cfg["next_gate"],
    }
    (root / "FMDL3DA_VALIDATION.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
