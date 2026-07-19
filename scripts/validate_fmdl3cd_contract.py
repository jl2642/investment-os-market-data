from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pandas as pd

from scripts.fmdl3cd_core import FAMILY_ORDER, validate_weight_table

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fmdl3cd_score.json"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    cfg = load_json(CONFIG)
    weights = pd.read_csv(
        ROOT / cfg["inputs"]["factor_weights"], encoding="utf-8-sig"
    )
    errors: list[str] = []
    try:
        validate_weight_table(weights, cfg)
    except Exception as exc:
        errors.append(str(exc))
    for path in [
        cfg["entry_gate"]["pointer"],
        cfg["inputs"]["hardened_factor_current"],
        cfg["inputs"]["factor_registry"],
        cfg["inputs"]["profile_reconciliation"],
        cfg["inputs"]["market_data_interface"],
        "schemas/fmdl3cd_financial_score_v1.schema.json",
        "schemas/fmdl3cd_investment_os_interface_v1.schema.json",
    ]:
        if not (ROOT / path).exists():
            errors.append(f"missing contract input: {path}")
    try:
        jsonschema.Draft202012Validator.check_schema(
            load_json(ROOT / "schemas/fmdl3cd_financial_score_v1.schema.json")
        )
        jsonschema.Draft202012Validator.check_schema(
            load_json(
                ROOT / "schemas/fmdl3cd_investment_os_interface_v1.schema.json"
            )
        )
    except Exception as exc:
        errors.append(f"invalid schema: {exc}")
    if set(cfg["score"]["family_weights"]) != set(FAMILY_ORDER):
        errors.append("family weight keys do not match frozen family order")
    if set(cfg["score"]["family_minimum_factor_count"]) != set(FAMILY_ORDER):
        errors.append("family minimum-count keys do not match frozen family order")
    if cfg.get("authority") != "DATA_AND_RESEARCH_EVIDENCE_ONLY":
        errors.append("uncontrolled authority")
    if cfg.get("trade_authority") != "NONE":
        errors.append("trade authority must remain NONE")
    if any(
        cfg["investment_os"].get(key)
        for key in [
            "automatic_candidate_promotion",
            "automatic_simulation_admission",
            "automatic_real_account_admission",
            "portfolio_action_authorized",
            "order_execution_authorized",
        ]
    ):
        errors.append("automatic action authority must remain false")
    result = {
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "weighted_factor_count": len(weights),
        "family_count": len(FAMILY_ORDER),
        "next_gate": cfg["next_gate"],
        "authority": cfg["authority"],
        "trade_authority": cfg["trade_authority"],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
