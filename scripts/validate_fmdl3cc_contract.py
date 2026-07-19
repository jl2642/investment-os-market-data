from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fmdl3cc_hardening.json"
SCHEMA = ROOT / "schemas/fmdl3cc_hardened_factor_v1.schema.json"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    cfg = load_json(CONFIG)
    schema = load_json(SCHEMA)
    jsonschema.Draft202012Validator.check_schema(schema)
    pointer = load_json(ROOT / cfg["entry_gate"]["pointer"])
    policy = pd.read_csv(
        ROOT / cfg["inputs"]["factor_policy"], encoding="utf-8-sig"
    )
    errors: list[str] = []
    if pointer.get("status") != cfg["entry_gate"]["required_status"]:
        errors.append("ENTRY_GATE_NOT_ACCEPTED")
    required_columns = {
        "factor_id",
        "factor_status",
        "minimum_coverage_ratio",
        "winsor_lower_quantile",
        "winsor_upper_quantile",
        "percentile_authorized",
        "policy_reason",
    }
    if not required_columns.issubset(set(policy.columns)):
        errors.append("FACTOR_POLICY_COLUMNS_MISSING")
    if len(policy) != 29 or policy["factor_id"].duplicated().any():
        errors.append("FACTOR_POLICY_NOT_EXACT_29_UNIQUE")
    if not set(policy["factor_status"]).issubset(
        set(cfg["hardening"]["allowed_factor_statuses"])
    ):
        errors.append("UNCONTROLLED_FACTOR_STATUS")
    if int(policy["factor_status"].eq("PRODUCTION_CORE").sum()) != 18:
        errors.append("PRODUCTION_CORE_COUNT_NOT_18")
    if int(policy["factor_status"].eq("DIAGNOSTIC_ONLY").sum()) != 9:
        errors.append("DIAGNOSTIC_COUNT_NOT_9")
    if int(policy["factor_status"].eq("DEFERRED_HISTORY").sum()) != 2:
        errors.append("DEFERRED_COUNT_NOT_2")
    if set(
        policy.loc[
            policy["factor_status"].eq("DEFERRED_HISTORY"), "factor_id"
        ]
    ) != {"FIN_REVENUE_CAGR_3Y", "FIN_PARENT_NI_CAGR_3Y"}:
        errors.append("DEFERRED_HISTORY_FACTOR_SET_MISMATCH")
    if not policy["winsor_lower_quantile"].between(0, 0.5).all():
        errors.append("INVALID_LOWER_QUANTILE")
    if not policy["winsor_upper_quantile"].between(0.5, 1).all():
        errors.append("INVALID_UPPER_QUANTILE")
    if cfg.get("trade_authority") != "NONE":
        errors.append("NONZERO_TRADE_AUTHORITY")
    result = {"status": "PASS" if not errors else "FAIL", "errors": errors}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
