from __future__ import annotations

from automation.operating_current.hydrate_a_share_runtime import choose_source
from automation.operating_current.hydrate_domain_source import source_for


def test_a_share_source_uses_newest_valid_runtime():
    current={
        "label":"OPERATING_CURRENT","source_branch":"old","commit":"a","watermark":"2026-08-10"
    }
    recovery={
        "label":"LEGACY_RECOVERY:rebase","source_branch":"recovery","commit":"b","watermark":"2026-08-26"
    }
    assert choose_source([current,recovery])["commit"]=="b"


def test_a_share_equal_watermark_prefers_formal_operating_current():
    current={
        "label":"OPERATING_CURRENT","source_branch":"current","commit":"a","watermark":"2026-08-26"
    }
    recovery={
        "label":"LEGACY_RECOVERY:rebase","source_branch":"recovery","commit":"b","watermark":"2026-08-26"
    }
    assert choose_source([recovery,current])["commit"]=="a"


def test_retryable_domain_hydration_uses_newer_attempt():
    current={
        "published_at_utc":"2026-08-28T01:00:00Z",
        "source_run_id":"1",
    }
    latest={
        "published_at_utc":"2026-08-28T02:00:00Z",
        "source_run_id":"2",
        "status":"BLOCKED",
    }
    source,used_latest=source_for({"domain_id":"X","current":current,"latest_attempt":latest},True)
    assert source["source_run_id"]=="2"
    assert used_latest is True


def test_retryable_domain_hydration_keeps_newer_current():
    current={
        "published_at_utc":"2026-08-28T03:00:00Z",
        "source_run_id":"3",
    }
    latest={
        "published_at_utc":"2026-08-28T02:00:00Z",
        "source_run_id":"2",
    }
    source,used_latest=source_for({"domain_id":"X","current":current,"latest_attempt":latest},True)
    assert source["source_run_id"]=="3"
    assert used_latest is False
