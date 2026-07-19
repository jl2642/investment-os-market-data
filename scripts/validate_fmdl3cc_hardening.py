from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fmdl3cc_hardening.json"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    cfg = load_json(CONFIG)
    root = ROOT / cfg["publication"]["candidate_root"]
    decision = load_json(root / "FMDL3CC_DECISION.json")
    manifest = load_json(root / "FMDL3CC_MANIFEST.json")
    hardened = pd.read_parquet(root / "FMDL3CC_HARDENED_FACTOR_CURRENT.parquet")
    factor_registry = pd.read_csv(
        root / "FMDL3CC_FACTOR_REGISTRY.csv", encoding="utf-8-sig"
    )
    distributions = pd.read_csv(
        root / "FMDL3CC_DISTRIBUTION_DIAGNOSTICS.csv", encoding="utf-8-sig"
    )
    tails = pd.read_parquet(root / "FMDL3CC_TAIL_EVENTS.parquet")
    profiles = pd.read_csv(
        root / "FMDL3CC_PROFILE_RECONCILIATION.csv",
        encoding="utf-8-sig",
        dtype={"symbol": str},
    )

    hash_errors = []
    for entry in manifest["files"]:
        path = root / entry["path"]
        if (
            not path.exists()
            or sha256(path) != entry["sha256"]
            or path.stat().st_size != int(entry["bytes"])
        ):
            hash_errors.append(entry["path"])

    allowed_states = set(cfg["hardening"]["allowed_hardening_states"])
    allowed_eligibility = set(cfg["hardening"]["allowed_production_eligibility"])
    accepted = hardened["hardening_state"].isin(
        ["ACCEPTED", "ACCEPTED_WITH_WARNING"]
    )
    production = hardened["production_eligibility"].isin(
        ["ELIGIBLE", "CONDITIONAL"]
    )

    bound_errors = 0
    production_distributions = distributions[
        distributions["sector_profile"].eq(cfg["hardening"]["production_profile"])
    ].set_index("factor_id")
    for factor_id, group in hardened.loc[accepted].groupby("factor_id"):
        if factor_id not in production_distributions.index:
            bound_errors += len(group)
            continue
        row = production_distributions.loc[factor_id]
        lower = float(row["q01"])
        upper = float(row["q99"])
        values = pd.to_numeric(group["factor_value_winsorized"], errors="coerce")
        bound_errors += int((values.lt(lower - 1e-12) | values.gt(upper + 1e-12)).sum())

    tail_replay = hardened[hardened["tail_flag"].ne("NONE")][
        ["symbol", "factor_id", "tail_flag"]
    ].sort_values(["symbol", "factor_id"]).reset_index(drop=True)
    tail_asset = tails[["symbol", "factor_id", "tail_flag"]].sort_values(
        ["symbol", "factor_id"]
    ).reset_index(drop=True)

    metrics = decision["metrics"]
    checks = {
        "DECISION_ACCEPTED": decision.get("status") == cfg["exit_status"],
        "DECISION_HARD_FAILURES_EMPTY": decision.get("hard_failures") == [],
        "MANIFEST_FILES_PRESENT": all(
            (root / item["path"]).exists() for item in manifest["files"]
        ),
        "MANIFEST_HASHES_MATCH": not hash_errors,
        "HARDENED_KEYS_UNIQUE": not hardened.duplicated(
            ["symbol", "factor_id"]
        ).any(),
        "FACTOR_REGISTRY_EXACT_29": len(factor_registry) == 29
        and not factor_registry["factor_id"].duplicated().any(),
        "FACTOR_STATUS_COUNTS_EXACT": int(
            factor_registry["factor_status"].eq("PRODUCTION_CORE").sum()
        )
        == 18
        and int(factor_registry["factor_status"].eq("DIAGNOSTIC_ONLY").sum())
        == 9
        and int(factor_registry["factor_status"].eq("DEFERRED_HISTORY").sum())
        == 2,
        "PRODUCTION_COVERAGE_GATES_PASS": factor_registry.loc[
            factor_registry["factor_status"].eq("PRODUCTION_CORE"),
            "factor_gate_status",
        ].eq("ACCEPTED_PRODUCTION_CORE").all(),
        "HARDENING_STATES_CONTROLLED": set(
            hardened["hardening_state"].dropna().astype(str)
        ).issubset(allowed_states),
        "PRODUCTION_ELIGIBILITY_CONTROLLED": set(
            hardened["production_eligibility"].dropna().astype(str)
        ).issubset(allowed_eligibility),
        "PRODUCTION_ROWS_PROFILE_CONTROLLED": hardened.loc[
            production, "sector_profile"
        ].eq(cfg["hardening"]["production_profile"]).all(),
        "PRODUCTION_ROWS_CORE_ONLY": hardened.loc[
            production, "factor_status"
        ].eq("PRODUCTION_CORE").all(),
        "ACCEPTED_VALUES_PRESENT_AND_FINITE": hardened.loc[
            accepted, "factor_value_winsorized"
        ].notna().all()
        and np.isfinite(
            pd.to_numeric(
                hardened.loc[accepted, "factor_value_winsorized"], errors="coerce"
            )
        ).all(),
        "ACCEPTED_VALUES_WITHIN_WINSOR_BOUNDS": bound_errors == 0,
        "DIRECTIONAL_PERCENTILES_BOUNDED": hardened.loc[
            hardened["directional_percentile"].notna(),
            "directional_percentile",
        ].between(0, 1, inclusive="both").all(),
        "ROBUST_ZSCORES_BOUNDED": hardened.loc[
            hardened["robust_zscore"].notna(), "robust_zscore"
        ].between(
            -float(cfg["hardening"]["robust_zscore_clip"]),
            float(cfg["hardening"]["robust_zscore_clip"]),
            inclusive="both",
        ).all(),
        "TAIL_REGISTRY_REPLAYS": tail_replay.equals(tail_asset),
        "DEFERRED_FACTORS_HAVE_NO_PRODUCTION_ROWS": not hardened.loc[
            hardened["factor_status"].eq("DEFERRED_HISTORY"),
            "production_eligibility",
        ].isin(["ELIGIBLE", "CONDITIONAL"]).any(),
        "DIAGNOSTICS_HAVE_NO_PRODUCTION_ROWS": not hardened.loc[
            hardened["factor_status"].eq("DIAGNOSTIC_ONLY"),
            "production_eligibility",
        ].isin(["ELIGIBLE", "CONDITIONAL"]).any(),
        "FINANCIAL_PROFILES_CONTROLLED_EXCLUSION": profiles.loc[
            profiles["sector_profile"].isin(
                ["BANK", "INSURANCE", "SECURITIES_AND_BROKERAGE"]
            ),
            "profile_reconciliation_status",
        ].eq("CONTROLLED_EXCLUSION_PENDING_SECTOR_FACTOR_PACK").all(),
        "UNRESOLVED_PROFILE_CONTROLLED_EXCLUSION": profiles.loc[
            profiles["sector_profile"].eq("UNRESOLVED"),
            "profile_reconciliation_status",
        ].eq("CONTROLLED_EXCLUSION_UNRESOLVED").all(),
        "INDUSTRY_NEUTRAL_SCORING_BLOCKED": not profiles[
            "industry_neutral_scoring_authorized"
        ].astype(bool).any(),
        "METRICS_REPLAY": int(metrics["hardened_factor_current_row_count"])
        == len(hardened)
        and int(metrics["tail_event_count"]) == len(tails)
        and int(metrics["profile_symbol_count"]) == len(profiles),
        "NO_COMPOSITE_SCORE_OR_SIGNAL": not (
            {
                "score",
                "composite_score",
                "investment_signal",
                "trade_signal",
                "target_weight",
            }
            & set(hardened.columns)
        ),
        "ZERO_TRADE_AUTHORITY": set(
            hardened["trade_authority"].dropna().astype(str)
        ).issubset({"NONE"})
        and set(profiles["trade_authority"].dropna().astype(str)).issubset(
            {"NONE"}
        ),
        "NEXT_GATE_FMDL3C_D": decision.get("next_gate") == cfg["next_gate"],
    }
    failures = [name for name, passed in checks.items() if not bool(passed)]
    validation = {
        "validation_version": "1.0.0",
        "release_id": decision["release_id"],
        "status": "PASS" if not failures else "FAIL",
        "hard_failures": failures,
        "checks": [
            {"check_id": name, "status": "PASS" if passed else "FAIL"}
            for name, passed in checks.items()
        ],
        "metrics": {
            **metrics,
            "manifest_hash_error_count": len(hash_errors),
            "winsor_bound_error_count": bound_errors,
            "duplicate_hardened_key_count": int(
                hardened.duplicated(["symbol", "factor_id"]).sum()
            ),
        },
        "manifest_hash_errors": hash_errors,
        "authority": cfg["authority"],
        "trade_authority": "NONE",
        "next_gate": cfg["next_gate"],
    }
    write_json(root / "FMDL3CC_VALIDATION.json", validation)
    print(json.dumps(validation, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
