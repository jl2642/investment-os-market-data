from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fmdl3da_contract.json"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    cfg = load_json(CONFIG)
    metrics = pd.read_csv(
        ROOT / cfg["inputs"]["valuation_metric_registry"], encoding="utf-8-sig"
    )
    events = pd.read_csv(
        ROOT / cfg["inputs"]["shareholder_event_registry"], encoding="utf-8-sig"
    ).fillna("NONE")
    pilot = pd.read_csv(
        ROOT / cfg["inputs"]["pilot_universe"], encoding="utf-8-sig", dtype=str
    )
    errors: list[str] = []

    for path in [
        cfg["entry_gates"]["financial_score_pointer"],
        cfg["entry_gates"]["source_benchmark_release"],
        cfg["entry_gates"]["factor_engine_release"],
        cfg["inputs"]["capitalization_evidence"],
        cfg["inputs"]["support_quarantine_map"],
        "schemas/fmdl3da_valuation_metric_detail_v1.schema.json",
        "schemas/fmdl3da_capitalization_snapshot_v1.schema.json",
        "schemas/fmdl3da_shareholder_return_event_v1.schema.json",
    ]:
        if not (ROOT / path).exists():
            errors.append(f"MISSING_CONTRACT_INPUT:{path}")

    if len(metrics) != 11 or metrics["metric_id"].duplicated().any():
        errors.append("VALUATION_METRIC_REGISTRY_MUST_HAVE_11_UNIQUE_ROWS")
    if len(events) != 8 or events["event_type"].duplicated().any():
        errors.append("SHAREHOLDER_EVENT_REGISTRY_MUST_HAVE_8_UNIQUE_ROWS")
    if len(pilot) != int(cfg["pilot"]["expected_symbol_count"]):
        errors.append("PILOT_SYMBOL_COUNT_MISMATCH")
    if pilot["symbol"].duplicated().any():
        errors.append("DUPLICATE_PILOT_SYMBOL")
    if not set(cfg["pilot"]["required_profiles"]).issubset(
        set(pilot["sector_profile"].astype(str))
    ):
        errors.append("REQUIRED_PROFILE_MISSING_FROM_PILOT")
    if not set(cfg["pilot"]["required_boards"]).issubset(
        set(pilot["board"].astype(str))
    ):
        errors.append("REQUIRED_BOARD_MISSING_FROM_PILOT")
    if set(metrics["trade_authority"].astype(str)) != {"NONE"}:
        errors.append("METRIC_TRADE_AUTHORITY_NOT_NONE")
    if set(events["trade_authority"].astype(str)) != {"NONE"}:
        errors.append("EVENT_TRADE_AUTHORITY_NOT_NONE")
    if cfg.get("trade_authority") != "NONE":
        errors.append("CONTRACT_TRADE_AUTHORITY_NOT_NONE")
    if cfg["valuation"].get("composite_valuation_score_authorized"):
        errors.append("COMPOSITE_VALUATION_SCORE_MUST_BE_DISABLED")
    if cfg["valuation"].get("target_price_authorized"):
        errors.append("TARGET_PRICE_MUST_BE_DISABLED")
    if cfg["point_in_time"].get("provider_ratio_rule") != (
        "PROVIDER_PE_PB_PS_ARE_CROSS_CHECK_ONLY_NOT_DECISION_GRADE"
    ):
        errors.append("PROVIDER_RATIO_ROLE_NOT_FROZEN")
    if cfg["shareholder_return"].get("announced_buyback_counts_as_completed"):
        errors.append("ANNOUNCED_BUYBACK_CANNOT_COUNT_AS_COMPLETED")
    if cfg["shareholder_return"].get("approved_issuance_counts_as_effective"):
        errors.append("APPROVED_ISSUANCE_CANNOT_COUNT_AS_EFFECTIVE")
    if not np.isclose(
        float(cfg["capitalization"]["minimum_supported_pilot_coverage"]),
        11 / 13,
        atol=0.01,
    ):
        errors.append("PILOT_CAPITALIZATION_GATE_NOT_ALIGNED_TO_FROZEN_SAMPLE")

    for path in [
        "schemas/fmdl3da_valuation_metric_detail_v1.schema.json",
        "schemas/fmdl3da_capitalization_snapshot_v1.schema.json",
        "schemas/fmdl3da_shareholder_return_event_v1.schema.json",
    ]:
        try:
            jsonschema.Draft202012Validator.check_schema(load_json(ROOT / path))
        except Exception as exc:
            errors.append(f"INVALID_SCHEMA:{path}:{exc}")

    allowed_stages = {
        "ANNOUNCED",
        "BOARD_APPROVED",
        "SHAREHOLDER_APPROVED",
        "REGULATORY_APPROVED",
        "IN_PROGRESS",
        "IMPLEMENTED",
        "COMPLETED",
        "CANCELLED",
    }
    for row in events.itertuples(index=False):
        stages = set(str(row.allowed_stages).split("|"))
        if not stages.issubset(allowed_stages):
            errors.append(f"UNCONTROLLED_EVENT_STAGE:{row.event_type}")
        for field in [
            "effective_stage_for_share_count",
            "effective_stage_for_shareholder_yield",
        ]:
            stage = str(getattr(row, field))
            if stage != "NONE" and stage not in stages:
                errors.append(f"EFFECTIVE_STAGE_NOT_ALLOWED:{row.event_type}:{field}")

    result = {
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "metric_count": len(metrics),
        "event_type_count": len(events),
        "pilot_symbol_count": len(pilot),
        "authority": cfg["authority"],
        "trade_authority": cfg["trade_authority"],
        "next_gate": cfg["next_gate"],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
