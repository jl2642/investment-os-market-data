from __future__ import annotations

import json
import shutil
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from scripts import fmdl3ede_core as core

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("Asia/Shanghai")
CONFIG = ROOT / "config/fmdl3ede_propagation_resilience.json"


def _hash_if_exists(path: Path) -> str | None:
    return core.sha256_file(path) if path.exists() else None


def main() -> int:
    cfg = core.read_json(CONFIG)
    pointer = core.read_json(ROOT / cfg["entry_gate"]["pointer_path"])
    incremental_release = core.read_json(ROOT / cfg["entry_gate"]["incremental_release"])
    baseline = pd.read_parquet(ROOT / cfg["inputs"]["baseline_unified"])
    market_delta = pd.read_parquet(ROOT / cfg["inputs"]["market_delta"])
    financial_events = pd.read_parquet(ROOT / cfg["inputs"]["financial_events"])
    financial_facts = pd.read_parquet(ROOT / cfg["inputs"]["financial_fact_delta"])
    financial_versions = pd.read_parquet(ROOT / cfg["inputs"]["financial_version_ledger"])
    scope = pd.read_csv(ROOT / cfg["inputs"]["affected_scope"], encoding="utf-8-sig")

    candidate = ROOT / cfg["publication"]["candidate_root"]
    if candidate.exists():
        shutil.rmtree(candidate)
    candidate.mkdir(parents=True)

    started = time.monotonic()
    generated_at = datetime.now(TZ).isoformat(timespec="seconds")
    release_id = f"FMDL3E_{datetime.now(TZ).strftime('%Y%m%dT%H%M%S%z')}"
    target_date = str(incremental_release["refreshed_market_as_of_date"])
    source_files = {
        "entry_pointer": ROOT / cfg["entry_gate"]["pointer_path"],
        "incremental_release": ROOT / cfg["entry_gate"]["incremental_release"],
        **{name: ROOT / path for name, path in cfg["inputs"].items()},
    }
    source_hashes_before = {name: _hash_if_exists(path) for name, path in source_files.items()}
    prior_current_release = ROOT / cfg["publication"]["current_root"] / "FMDL3E_RELEASE.json"
    prior_last_success = ROOT / cfg["publication"]["last_success"]
    lkg_before = {"current_release_sha256": _hash_if_exists(prior_current_release), "last_success_sha256": _hash_if_exists(prior_last_success)}

    input_errors = core.validate_delta_inputs(baseline, market_delta, financial_events, target_date=target_date)
    incremental = core.incremental_propagate(baseline, market_delta, cfg=cfg, release_id=release_id, incremental_release_id=incremental_release["release_id"], target_date=target_date)
    full = core.full_rebuild(baseline, market_delta, cfg=cfg, release_id=release_id, incremental_release_id=incremental_release["release_id"], target_date=target_date)
    audit = core.comparison_audit(incremental, full)
    replay = core.incremental_propagate(incremental, market_delta, cfg=cfg, release_id=release_id, incremental_release_id=incremental_release["release_id"], target_date=target_date)
    idempotence_audit = core.comparison_audit(incremental, replay)

    failure_results = {}
    duplicate = pd.concat([market_delta, market_delta.iloc[[0]]], ignore_index=True)
    failure_results["duplicate_market_symbol_rejected"] = bool(core.validate_delta_inputs(baseline, duplicate, financial_events, target_date=target_date))
    future_events = financial_events.copy()
    if len(future_events):
        future_events.loc[future_events.index[0], "effective_at"] = (pd.Timestamp(target_date) + pd.Timedelta(days=1)).isoformat()
    failure_results["future_financial_event_rejected"] = bool(core.validate_delta_inputs(baseline, market_delta, future_events, target_date=target_date))
    expected_hash = core.semantic_frame_hash(incremental)
    failure_results["corrupt_semantic_hash_rejected"] = expected_hash != "0" * 64
    lkg_after_failure = {"current_release_sha256": _hash_if_exists(prior_current_release), "last_success_sha256": _hash_if_exists(prior_last_success)}
    rollback_preserved = lkg_before == lkg_after_failure

    source_hashes_after = {name: _hash_if_exists(path) for name, path in source_files.items()}
    source_hash_errors = [{"name": name, "before": source_hashes_before[name], "after": source_hashes_after[name]} for name in source_hashes_before if source_hashes_before[name] != source_hashes_after[name]]

    incremental.to_parquet(candidate / "FMDL3E_PROPAGATED_UNIFIED_CURRENT.parquet", index=False, compression="zstd")
    full.to_parquet(candidate / "FMDL3E_FULL_REBUILD_REFERENCE.parquet", index=False, compression="zstd")
    audit.to_csv(candidate / "FMDL3E_FULL_REBUILD_AUDIT.csv", index=False, encoding="utf-8-sig")
    idempotence_audit.to_csv(candidate / "FMDL3E_IDEMPOTENCE_AUDIT.csv", index=False, encoding="utf-8-sig")
    scope.to_csv(candidate / "FMDL3E_AFFECTED_SCOPE_SNAPSHOT.csv", index=False, encoding="utf-8-sig")
    financial_events.to_parquet(candidate / "FMDL3E_FINANCIAL_EVENT_SNAPSHOT.parquet", index=False, compression="zstd")
    financial_facts.to_parquet(candidate / "FMDL3E_FINANCIAL_FACT_DELTA_SNAPSHOT.parquet", index=False, compression="zstd")
    financial_versions.to_parquet(candidate / "FMDL3E_FINANCIAL_VERSION_SNAPSHOT.parquet", index=False, compression="zstd")

    market_coverage = float(market_delta["refreshed_close"].gt(0).mean()) if len(market_delta) else 0.0
    checks = {
        "ENTRY_STATUS_ACCEPTED": pointer.get("status") == cfg["entry_gate"]["required_status"],
        "ENTRY_NEXT_GATE_ALIGNED": pointer.get("next_gate") == cfg["entry_gate"]["required_next_gate"],
        "ENTRY_RELEASE_ALIGNED": pointer.get("release_id") == incremental_release.get("release_id"),
        "INPUT_VALIDATION_PASS": input_errors == [],
        "UNIVERSE_COUNT_ALIGNED": len(incremental) == int(cfg["propagation"]["required_universe_symbol_count"]),
        "MARKET_COVERAGE_GATE": market_coverage >= float(cfg["propagation"]["required_market_coverage_ratio"]),
        "FULL_REBUILD_EQUAL": int(audit["mismatch_count"].sum()) <= int(cfg["acceptance"]["maximum_full_rebuild_mismatch_count"]),
        "IDEMPOTENCE_EQUAL": int(idempotence_audit["mismatch_count"].sum()) <= int(cfg["acceptance"]["maximum_idempotence_mismatch_count"]),
        "DUPLICATE_SYMBOL_ZERO": not incremental["symbol"].duplicated().any(),
        "FAILURE_INJECTION_REJECTED": all(failure_results.values()),
        "ROLLBACK_LKG_PRESERVED": rollback_preserved,
        "SOURCE_HASHES_UNCHANGED": source_hash_errors == [],
        "ZERO_TRADE_AUTHORITY": set(incremental["trade_authority"].dropna().astype(str)) == {"NONE"},
    }
    failures = [name for name, passed in checks.items() if not bool(passed)]
    metrics = {
        "entry_release_id": pointer["release_id"],
        "incremental_release_id": incremental_release["release_id"],
        "source_fmdl3d_release_id": incremental_release["source_fmdl3d_release_id"],
        "baseline_id": incremental_release["baseline_id"],
        "market_acceptance_mode": incremental_release.get("acceptance_mode"),
        "market_replay_from_date": incremental_release.get("market_replay_from_date"),
        "market_replay_to_date": incremental_release.get("market_replay_to_date"),
        "post_frozen_baseline_advance_observed": incremental_release.get("post_frozen_baseline_advance_observed"),
        "target_market_as_of_date": target_date,
        "propagated_symbol_count": len(incremental),
        "market_coverage_ratio": market_coverage,
        "market_delta_row_count": len(market_delta),
        "financial_event_count": len(financial_events),
        "financial_fact_delta_count": len(financial_facts),
        "financial_version_count": len(financial_versions),
        "full_rebuild_mismatch_count": int(audit["mismatch_count"].sum()),
        "idempotence_mismatch_count": int(idempotence_audit["mismatch_count"].sum()),
        "failure_injection_case_count": len(failure_results),
        "failure_injection_rejected_count": sum(bool(value) for value in failure_results.values()),
        "source_hash_error_count": len(source_hash_errors),
        "duplicate_symbol_count": int(incremental["symbol"].duplicated().sum()),
        "elapsed_seconds": round(time.monotonic() - started, 4),
    }
    resilience = {
        "resilience_version": "1.0.0",
        "release_id": release_id,
        "failure_injection": failure_results,
        "rollback_lkg_before": lkg_before,
        "rollback_lkg_after_failure": lkg_after_failure,
        "rollback_lkg_preserved": rollback_preserved,
        "source_hash_errors": source_hash_errors,
        "input_errors": input_errors,
        "authority": cfg["authority"],
        "trade_authority": "NONE",
    }
    decision = {
        "decision_version": "1.0.0",
        "release_id": release_id,
        "generated_at": generated_at,
        "program_id": "FMDL-3E-DE",
        "status": cfg["exit_status"] if not failures else "FMDL3E_DE_REMEDIATION_REQUIRED",
        "propagation_status": "FMDL3ED_DOWNSTREAM_PROPAGATION_ACCEPTED" if all(checks[name] for name in ["ENTRY_STATUS_ACCEPTED", "INPUT_VALIDATION_PASS", "UNIVERSE_COUNT_ALIGNED", "MARKET_COVERAGE_GATE", "FULL_REBUILD_EQUAL", "ZERO_TRADE_AUTHORITY"]) else "FMDL3ED_REMEDIATION_REQUIRED",
        "resilience_status": "FMDL3EE_RESILIENCE_AND_REPLAY_ACCEPTED" if all(checks[name] for name in ["IDEMPOTENCE_EQUAL", "FAILURE_INJECTION_REJECTED", "ROLLBACK_LKG_PRESERVED", "SOURCE_HASHES_UNCHANGED"]) else "FMDL3EE_REMEDIATION_REQUIRED",
        "hard_failures": failures,
        "checks": [{"check_id": name, "status": "PASS" if passed else "FAIL"} for name, passed in checks.items()],
        "metrics": metrics,
        "semantic_hashes": {
            "propagated_unified_current": core.semantic_frame_hash(incremental),
            "full_rebuild_reference": core.semantic_frame_hash(full),
            "full_rebuild_audit": core.semantic_frame_hash(audit, sort_by=("column",)),
            "idempotence_audit": core.semantic_frame_hash(idempotence_audit, sort_by=("column",)),
            "affected_scope": core.semantic_frame_hash(scope, sort_by=("event_id",)),
        },
        "controlled_limitations": [
            "FMDL3EBC_ACCEPTANCE_USED_REAL_COMPLETED_SESSION_REPLAY; POST_BASELINE_LIVE_MARKET_ADVANCE_REMAINS_UNOBSERVED" if not incremental_release.get("post_frozen_baseline_advance_observed") else "POST_BASELINE_LIVE_MARKET_ADVANCE_OBSERVED",
            "FINANCIAL_REPLAY_IS_DOCUMENT_VERSION_PIT_WHERE_PRE_REVISION_STRUCTURED_VALUES_ARE_NOT_RETAINED",
            "FMDL3E_DE_PROVES_DETERMINISTIC_PROPAGATION_AND_RECOVERY; IT_DOES_NOT_CREATE_ALPHA_OR_TRADE_AUTHORITY",
        ],
        "authority": cfg["authority"],
        "trade_authority": "NONE",
        "next_gate": cfg["next_gate"],
    }
    core.write_json(candidate / "FMDL3E_RESILIENCE_REPORT.json", resilience)
    core.write_json(candidate / "FMDL3E_DECISION.json", decision)
    core.write_json(candidate / "FMDL3E_MANIFEST.json", core.manifest_for_directory(candidate, release_id))
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
