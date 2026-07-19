from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable_hash(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()


def canonical_symbol_set_digest(symbols: list[str]) -> str:
    payload = "\n".join(sorted(str(symbol) for symbol in symbols))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def canonical_row_hash_digest(frame: pd.DataFrame) -> str:
    required = {"symbol", "row_hash"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"missing row-hash columns: {sorted(missing)}")
    ordered = frame[["symbol", "row_hash"]].copy()
    ordered["symbol"] = ordered["symbol"].astype(str)
    ordered["row_hash"] = ordered["row_hash"].astype(str)
    ordered = ordered.sort_values("symbol")
    payload = "\n".join(
        f"{row.symbol}|{row.row_hash}" for row in ordered.itertuples(index=False)
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_file_inventory(root: Path, relative_paths: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for relative in relative_paths:
        path = root / relative
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(relative)
        rows.append(
            {
                "path": relative,
                "sha256": sha256_file(path),
                "bytes": int(path.stat().st_size),
            }
        )
    return sorted(rows, key=lambda row: row["path"])


def baseline_watermarks(
    final_release: dict[str, Any],
    interface: dict[str, Any],
    component_release_ids: dict[str, str],
    symbol_set_sha256: str,
) -> dict[str, Any]:
    return {
        "market": {
            "market_as_of_date": str(interface["market_as_of_date"]),
            "source_fmdl3d_release_id": str(final_release["release_id"]),
        },
        "universe": {
            "symbol_set_sha256": symbol_set_sha256,
            "universe_symbol_count": int(final_release["metrics"]["universe_symbol_count"]),
        },
        "financial": {
            "valuation_component_release_id": str(component_release_ids["FMDL-3D-C"]),
            "watermark_type": "PIT_FINANCIAL_DENOMINATOR_RELEASE_BINDING",
        },
        "capitalization": {
            "component_release_id": str(component_release_ids["FMDL-3D-B"]),
            "market_as_of_date": str(interface["market_as_of_date"]),
        },
        "valuation": {
            "component_release_id": str(component_release_ids["FMDL-3D-C"]),
            "market_as_of_date": str(interface["market_as_of_date"]),
        },
        "shareholder_return": {
            "component_release_id": str(component_release_ids["FMDL-3D-D"]),
            "market_as_of_date": str(interface["market_as_of_date"]),
        },
    }


def validate_delta_catalog(catalog: pd.DataFrame) -> list[str]:
    required_columns = {
        "event_type",
        "domain",
        "detection_key",
        "effective_time_rule",
        "affected_scope",
        "recompute_targets",
        "full_rebuild_trigger",
        "requires_pit_replay",
        "incremental_allowed",
        "authority",
        "trade_authority",
    }
    errors: list[str] = []
    missing = required_columns - set(catalog.columns)
    if missing:
        errors.append(f"MISSING_COLUMNS:{sorted(missing)}")
        return errors
    if catalog["event_type"].duplicated().any():
        errors.append("DUPLICATE_EVENT_TYPE")
    if set(catalog["authority"].astype(str)) != {"DATA_AND_RESEARCH_EVIDENCE_ONLY"}:
        errors.append("UNCONTROLLED_AUTHORITY")
    if set(catalog["trade_authority"].astype(str)) != {"NONE"}:
        errors.append("TRADE_AUTHORITY_NOT_NONE")
    full_rebuild = catalog["full_rebuild_trigger"].astype(str).str.lower().eq("true")
    incremental = catalog["incremental_allowed"].astype(str).str.lower().eq("true")
    if (full_rebuild & incremental).any():
        errors.append("FULL_REBUILD_EVENT_MARKED_INCREMENTAL")
    if not catalog.loc[
        catalog["event_type"].eq("BASELINE_INTEGRITY_FAILURE"),
        "full_rebuild_trigger",
    ].astype(str).str.lower().eq("true").all():
        errors.append("BASELINE_INTEGRITY_MUST_FORCE_FULL_REBUILD")
    return errors


def promotion_policy_is_fail_closed(policy: dict[str, Any]) -> bool:
    required_true = [
        "candidate_before_current",
        "all_required_shards_complete",
        "independent_validation_required",
        "hard_failures_must_be_empty",
        "source_and_output_hashes_required",
        "exact_expected_universe_required",
        "future_information_error_count_must_be_zero",
        "last_success_update_after_current_and_release_written",
        "atomic_pointer_promotion_required",
    ]
    return all(bool(policy.get(key)) for key in required_true) and not bool(
        policy.get("automatic_partial_promotion_allowed")
    )


def rollback_policy_preserves_last_good(policy: dict[str, Any]) -> bool:
    required_true = [
        "last_known_good_preserved_until_promotion",
        "failed_candidate_must_not_modify_current",
        "failed_candidate_must_not_modify_last_success",
        "release_and_archive_immutable",
        "rollback_target_must_be_previously_accepted_release",
        "rollback_changes_pointer_only",
        "candidate_artifacts_retained_for_diagnosis",
    ]
    return all(bool(policy.get(key)) for key in required_true)
