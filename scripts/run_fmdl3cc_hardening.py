from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from scripts.fmdl3cc_core import harden_factor_current

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("Asia/Shanghai")
CONFIG = ROOT / "config/fmdl3cc_hardening.json"


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
        if path.is_file() and path.name != "FMDL3CC_MANIFEST.json":
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
    pointer = load_json(ROOT / cfg["entry_gate"]["pointer"])
    if pointer.get("status") != cfg["entry_gate"]["required_status"]:
        raise SystemExit("FMDL-3C-B entry gate not accepted")
    release = load_json(ROOT / pointer["current_release_path"])

    current = pd.read_parquet(ROOT / cfg["inputs"]["factor_current"])
    profiles = pd.read_csv(
        ROOT / cfg["inputs"]["sector_profiles"],
        encoding="utf-8-sig",
        dtype={"symbol": str},
    )
    policy = pd.read_csv(
        ROOT / cfg["inputs"]["factor_policy"],
        encoding="utf-8-sig",
    )

    candidate = ROOT / cfg["publication"]["candidate_root"]
    if candidate.exists():
        shutil.rmtree(candidate)
    candidate.mkdir(parents=True, exist_ok=True)

    release_id = f"FMDL3CC_{datetime.now(TZ).strftime('%Y%m%dT%H%M%S%z')}"
    hardened, factor_registry, distributions, tails, profile_registry = (
        harden_factor_current(current, profiles, policy, cfg)
    )

    hardened_path = candidate / "FMDL3CC_HARDENED_FACTOR_CURRENT.parquet"
    factor_registry_path = candidate / "FMDL3CC_FACTOR_REGISTRY.csv"
    distribution_path = candidate / "FMDL3CC_DISTRIBUTION_DIAGNOSTICS.csv"
    tail_path = candidate / "FMDL3CC_TAIL_EVENTS.parquet"
    profile_path = candidate / "FMDL3CC_PROFILE_RECONCILIATION.csv"
    hardened.to_parquet(hardened_path, index=False, compression="zstd")
    factor_registry.to_csv(factor_registry_path, index=False, encoding="utf-8-sig")
    distributions.to_csv(distribution_path, index=False, encoding="utf-8-sig")
    tails.to_parquet(tail_path, index=False, compression="zstd")
    profile_registry.to_csv(profile_path, index=False, encoding="utf-8-sig")

    production_core = factor_registry["factor_status"].eq("PRODUCTION_CORE")
    diagnostic = factor_registry["factor_status"].eq("DIAGNOSTIC_ONLY")
    deferred = factor_registry["factor_status"].eq("DEFERRED_HISTORY")
    valid_hardened = hardened["hardening_state"].isin(
        ["ACCEPTED", "ACCEPTED_WITH_WARNING"]
    )
    checks = {
        "ENTRY_FMDL3CB_ACCEPTED": pointer.get("status")
        == cfg["entry_gate"]["required_status"],
        "SOURCE_RELEASE_ALIGNED": release.get("release_id") == pointer.get("release_id"),
        "FACTOR_POLICY_EXACT_29": len(policy) == 29
        and not policy["factor_id"].duplicated().any(),
        "POLICY_STATUS_COUNTS_18_9_2": int(
            policy["factor_status"].eq("PRODUCTION_CORE").sum()
        )
        == 18
        and int(policy["factor_status"].eq("DIAGNOSTIC_ONLY").sum()) == 9
        and int(policy["factor_status"].eq("DEFERRED_HISTORY").sum()) == 2,
        "HARDENED_CURRENT_ROW_COUNT_PRESERVED": len(hardened) == len(current),
        "HARDENED_KEYS_UNIQUE": not hardened.duplicated(
            ["symbol", "factor_id"]
        ).any(),
        "RAW_VALUES_PRESERVED": np.allclose(
            pd.to_numeric(hardened["factor_value_raw"], errors="coerce").fillna(0),
            pd.to_numeric(hardened["factor_value"], errors="coerce").fillna(0),
        )
        and hardened["factor_value_raw"].isna().equals(
            hardened["factor_value"].isna()
        ),
        "PROFILE_REGISTRY_EXACT_UNIVERSE": len(profile_registry) == len(profiles)
        and set(profile_registry["symbol"].astype(str))
        == set(profiles["symbol"].astype(str)),
        "ALL_PRODUCTION_CORE_COVERAGE_GATES_PASS": factor_registry.loc[
            production_core, "factor_gate_status"
        ].eq("ACCEPTED_PRODUCTION_CORE").all(),
        "ALL_DIAGNOSTICS_BLOCKED_FROM_PRODUCTION": hardened.loc[
            hardened["factor_status"].eq("DIAGNOSTIC_ONLY"),
            "production_eligibility",
        ].eq("INELIGIBLE").all(),
        "ALL_DEFERRED_FACTORS_BLOCKED": hardened.loc[
            hardened["factor_status"].eq("DEFERRED_HISTORY"),
            "hardening_state",
        ].eq("DEFERRED_HISTORY").all(),
        "PRODUCTION_ROWS_GENERAL_NON_FINANCIAL_ONLY": hardened.loc[
            hardened["production_eligibility"].isin(["ELIGIBLE", "CONDITIONAL"]),
            "sector_profile",
        ].eq(cfg["hardening"]["production_profile"]).all(),
        "PRODUCTION_ROWS_CORE_FACTORS_ONLY": hardened.loc[
            hardened["production_eligibility"].isin(["ELIGIBLE", "CONDITIONAL"]),
            "factor_status",
        ].eq("PRODUCTION_CORE").all(),
        "HARDENED_VALUES_PRESENT_FOR_ACCEPTED_ROWS": hardened.loc[
            valid_hardened, "factor_value_winsorized"
        ].notna().all(),
        "HARDENED_VALUES_FINITE": np.isfinite(
            pd.to_numeric(
                hardened.loc[valid_hardened, "factor_value_winsorized"],
                errors="coerce",
            )
        ).all(),
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
        "TAIL_EVENTS_REPLAY": int(
            hardened["tail_flag"].ne("NONE").sum()
        )
        == len(tails),
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
        and set(profile_registry["trade_authority"].dropna().astype(str)).issubset(
            {"NONE"}
        ),
    }
    failures = [name for name, passed in checks.items() if not bool(passed)]

    metrics = {
        "source_factor_engine_release_id": pointer["release_id"],
        "source_factor_current_row_count": len(current),
        "hardened_factor_current_row_count": len(hardened),
        "factor_count": int(hardened["factor_id"].nunique()),
        "production_core_factor_count": int(production_core.sum()),
        "diagnostic_only_factor_count": int(diagnostic.sum()),
        "deferred_history_factor_count": int(deferred.sum()),
        "accepted_row_count": int(hardened["hardening_state"].eq("ACCEPTED").sum()),
        "accepted_with_warning_row_count": int(
            hardened["hardening_state"].eq("ACCEPTED_WITH_WARNING").sum()
        ),
        "production_eligible_row_count": int(
            hardened["production_eligibility"].eq("ELIGIBLE").sum()
        ),
        "production_conditional_row_count": int(
            hardened["production_eligibility"].eq("CONDITIONAL").sum()
        ),
        "production_ineligible_row_count": int(
            hardened["production_eligibility"].eq("INELIGIBLE").sum()
        ),
        "diagnostic_row_count": int(
            hardened["hardening_state"].eq("DIAGNOSTIC_ONLY").sum()
        ),
        "deferred_history_row_count": int(
            hardened["hardening_state"].eq("DEFERRED_HISTORY").sum()
        ),
        "controlled_profile_exclusion_row_count": int(
            hardened["hardening_state"].eq("CONTROLLED_PROFILE_EXCLUSION").sum()
        ),
        "raw_factor_ineligible_row_count": int(
            hardened["hardening_state"].eq("RAW_FACTOR_INELIGIBLE").sum()
        ),
        "tail_event_count": len(tails),
        "profile_symbol_count": len(profile_registry),
        "industry_neutral_scoring_authorized": False,
        "financial_sector_factor_pack_authorized": False,
    }
    decision = {
        "decision_version": "1.0.0",
        "release_id": release_id,
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "program_id": "FMDL-3C-C",
        "status": cfg["exit_status"]
        if not failures
        else "FMDL3CC_REMEDIATION_REQUIRED",
        "hard_failures": failures,
        "checks": [
            {"check_id": name, "status": "PASS" if passed else "FAIL"}
            for name, passed in checks.items()
        ],
        "metrics": metrics,
        "controlled_limitations": [
            "CANONICAL_FULL_INDUSTRY_SECURITY_MASTER_NOT_YET_AVAILABLE",
            "INDUSTRY_NEUTRAL_SCORING_NOT_AUTHORIZED",
            "BANK_INSURANCE_AND_BROKER_FACTOR_PACKS_NOT_YET_AVAILABLE",
            "THREE_YEAR_CAGR_FACTORS_DEFERRED_PENDING_HISTORY_BACKFILL",
            "LOW_COVERAGE_DEBT_COMPONENT_FACTORS_RETAINED_AS_DIAGNOSTIC_ONLY",
            "HARDENED_VALUES_ARE_PRE_SCORING_RESEARCH_INPUTS_NOT_INVESTMENT_SIGNALS",
        ],
        "authority": cfg["authority"],
        "trade_authority": "NONE",
        "next_gate": cfg["next_gate"],
    }
    write_json(candidate / "FMDL3CC_DECISION.json", decision)
    write_json(candidate / "FMDL3CC_SOURCE_POINTER.json", pointer)
    write_json(candidate / "FMDL3CC_SOURCE_RELEASE.json", release)
    write_json(candidate / "FMDL3CC_MANIFEST.json", manifest(candidate, release_id))
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
