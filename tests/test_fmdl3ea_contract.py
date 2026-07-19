from __future__ import annotations

import pandas as pd

from scripts.fmdl3ea_core import (
    canonical_row_hash_digest,
    canonical_symbol_set_digest,
    promotion_policy_is_fail_closed,
    rollback_policy_preserves_last_good,
    validate_delta_catalog,
)


def test_symbol_and_row_hash_digests_are_order_independent():
    left = pd.DataFrame(
        [
            {"symbol": "000002.SZ", "row_hash": "b" * 64},
            {"symbol": "000001.SZ", "row_hash": "a" * 64},
        ]
    )
    right = left.iloc[::-1].reset_index(drop=True)
    assert canonical_symbol_set_digest(left["symbol"].tolist()) == canonical_symbol_set_digest(
        right["symbol"].tolist()
    )
    assert canonical_row_hash_digest(left) == canonical_row_hash_digest(right)


def test_promotion_policy_is_fail_closed():
    policy = {
        "candidate_before_current": True,
        "all_required_shards_complete": True,
        "independent_validation_required": True,
        "hard_failures_must_be_empty": True,
        "source_and_output_hashes_required": True,
        "exact_expected_universe_required": True,
        "future_information_error_count_must_be_zero": True,
        "automatic_partial_promotion_allowed": False,
        "last_success_update_after_current_and_release_written": True,
        "atomic_pointer_promotion_required": True,
    }
    assert promotion_policy_is_fail_closed(policy)
    policy["automatic_partial_promotion_allowed"] = True
    assert not promotion_policy_is_fail_closed(policy)


def test_rollback_policy_preserves_last_good():
    policy = {
        "last_known_good_preserved_until_promotion": True,
        "failed_candidate_must_not_modify_current": True,
        "failed_candidate_must_not_modify_last_success": True,
        "release_and_archive_immutable": True,
        "rollback_target_must_be_previously_accepted_release": True,
        "rollback_changes_pointer_only": True,
        "candidate_artifacts_retained_for_diagnosis": True,
    }
    assert rollback_policy_preserves_last_good(policy)
    policy["failed_candidate_must_not_modify_last_success"] = False
    assert not rollback_policy_preserves_last_good(policy)


def test_delta_catalog_rejects_full_rebuild_as_incremental():
    catalog = pd.DataFrame(
        [
            {
                "event_type": "BASELINE_INTEGRITY_FAILURE",
                "domain": "OPERATIONS",
                "detection_key": "baseline_id|failed_hash",
                "effective_time_rule": "DETECTED_AT",
                "affected_scope": "FULL_BASELINE",
                "recompute_targets": "ALL_DOWNSTREAM_LAYERS",
                "full_rebuild_trigger": True,
                "requires_pit_replay": True,
                "incremental_allowed": False,
                "authority": "DATA_AND_RESEARCH_EVIDENCE_ONLY",
                "trade_authority": "NONE",
            }
        ]
    )
    assert validate_delta_catalog(catalog) == []
    catalog.loc[0, "incremental_allowed"] = True
    assert "FULL_REBUILD_EVENT_MARKED_INCREMENTAL" in validate_delta_catalog(catalog)
