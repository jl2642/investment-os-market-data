from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fmdl3dc_engine.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    cfg = load_json(CONFIG)
    contract_pointer = load_json(ROOT / cfg["entry_gates"]["valuation_contract_pointer"])
    cap_pointer = load_json(ROOT / cfg["entry_gates"]["capitalization_pointer"])
    factor_pointer = load_json(ROOT / cfg["entry_gates"]["factor_engine_pointer"])
    cap_release = load_json(ROOT / cfg["inputs"]["capitalization_release"])
    factor_release = load_json(ROOT / cfg["inputs"]["factor_engine_release"])
    registry = pd.read_csv(
        ROOT / cfg["inputs"]["valuation_metric_registry"], encoding="utf-8-sig"
    )
    expected = cfg["engine"]["expected_valuation_metric_ids"]
    selected = registry[
        registry["metric_id"].astype(str).isin(expected)
        & registry["metric_family"].astype(str).eq("VALUATION")
    ]

    checks = {
        "ENTRY_FMDL3DA_ACCEPTED": contract_pointer.get("status")
        == cfg["entry_gates"]["valuation_contract_status"],
        "ENTRY_FMDL3DB_ACCEPTED": cap_pointer.get("status")
        == cfg["entry_gates"]["capitalization_status"],
        "ENTRY_FMDL3CB_ACCEPTED": factor_pointer.get("status")
        == cfg["entry_gates"]["factor_engine_status"],
        "CAPITALIZATION_RELEASE_BOUND": cap_release.get("status")
        == cfg["entry_gates"]["capitalization_status"]
        and cap_release.get("release_id") == cap_pointer.get("release_id"),
        "FACTOR_RELEASE_BOUND": factor_release.get("status")
        == cfg["entry_gates"]["factor_engine_status"]
        and factor_release.get("release_id") == factor_pointer.get("release_id"),
        "CAPITALIZATION_CURRENT_EXISTS": (ROOT / cap_release["capitalization_current_path"]).exists(),
        "SECTOR_PROFILE_EXISTS": (ROOT / cfg["inputs"]["sector_profiles"]).exists(),
        "DERIVED_INPUT_SHARDS_EXIST": len(factor_release.get("derived_input_shards", [])) == 32
        and all((ROOT / path).exists() for path in factor_release.get("derived_input_shards", [])),
        "EXACT_SEVEN_VALUATION_METRICS": len(selected) == 7
        and set(selected["metric_id"].astype(str)) == set(expected),
        "NO_SHAREHOLDER_RETURN_METRICS": set(selected["metric_family"].astype(str)) == {"VALUATION"},
        "NO_SCORE_OR_TARGET_AUTHORITY": cfg["engine"]["composite_valuation_score_authorized"] is False
        and cfg["engine"]["target_price_authorized"] is False
        and cfg["engine"]["automatic_action_authorized"] is False,
        "TRADE_AUTHORITY_NONE": cfg["trade_authority"] == "NONE",
        "NEXT_GATE_FMDL3DD": cfg["next_gate"] == "FMDL-3D-D_SHAREHOLDER_RETURN_EVENT_CURRENT",
    }
    failures = [key for key, value in checks.items() if not bool(value)]
    payload = {
        "status": "PASS" if not failures else "FAIL",
        "hard_failures": failures,
        "checks": [
            {"check_id": key, "status": "PASS" if bool(value) else "FAIL"}
            for key, value in checks.items()
        ],
        "capitalization_release_id": cap_pointer.get("release_id"),
        "factor_engine_release_id": factor_pointer.get("release_id"),
        "valuation_metric_ids": expected,
        "authority": cfg["authority"],
        "trade_authority": cfg["trade_authority"],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
