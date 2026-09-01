from __future__ import annotations

import hashlib
from pathlib import Path

from scripts.materialize_fmdl_history_dependencies import (
    missing_dependency_rows,
    rebase_branch_for_release_id,
)


def test_rebase_release_maps_to_governed_branch() -> None:
    assert (
        rebase_branch_for_release_id("FMDL2B4_REBASE_33205823259_A1")
        == "automation/fmdl2b4-rebase-33205823259-a1"
    )
    assert rebase_branch_for_release_id("FMDL2B4_20260807T162547+0800") is None


def test_missing_dependency_detects_absent_rebase_file(tmp_path: Path) -> None:
    manifest = {
        "release_id": "FMDL2B4_REBASE_33205823259_A1",
        "repair_files": [
            {
                "path": "datasets/history/repair/FMDL2B4_REBASE_33205823259_A1/shard_00_full_rebase.parquet",
                "sha256": "abc",
                "recovery_release_id": "FMDL2B4_REBASE_33205823259_A1",
            }
        ],
    }
    rows = missing_dependency_rows(tmp_path, manifest)
    assert rows == [
        {
            "path": "datasets/history/repair/FMDL2B4_REBASE_33205823259_A1/shard_00_full_rebase.parquet",
            "sha256": "abc",
            "recovery_release_id": "FMDL2B4_REBASE_33205823259_A1",
            "source_branch": "automation/fmdl2b4-rebase-33205823259-a1",
        }
    ]


def test_existing_dependency_requires_matching_sha(tmp_path: Path) -> None:
    rel = Path("datasets/history/incremental/example/daily_delta.parquet")
    target = tmp_path / rel
    target.parent.mkdir(parents=True)
    target.write_bytes(b"accepted")
    digest = hashlib.sha256(b"accepted").hexdigest()
    manifest = {"delta_files": [{"path": rel.as_posix(), "sha256": digest}]}
    assert missing_dependency_rows(tmp_path, manifest) == []

    manifest["delta_files"][0]["sha256"] = hashlib.sha256(b"other").hexdigest()
    rows = missing_dependency_rows(tmp_path, manifest)
    assert len(rows) == 1
    assert rows[0]["source_branch"] is None
