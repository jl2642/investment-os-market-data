from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from automation.wp3_2a.materialize_identity_baseline import (
    EXPECTED_PARTS,
    EXPECTED_RECORDS,
    EXPECTED_SHA256,
    EXPECTED_SIZE,
    PART_GLOB,
    materialize,
)


def test_identity_baseline_materializes_byte_exact(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    source_dir = (
        repo_root
        / "investment_os_runtime"
        / "40_EVIDENCE_AND_LINEAGE"
        / "WP3_2_R4"
    )
    target_dir = (
        tmp_path
        / "investment_os_runtime"
        / "40_EVIDENCE_AND_LINEAGE"
        / "WP3_2_R4"
    )
    target_dir.mkdir(parents=True)

    parts = sorted(source_dir.glob(PART_GLOB))
    assert len(parts) == EXPECTED_PARTS
    for part in parts:
        shutil.copyfile(part, target_dir / part.name)

    target = materialize(tmp_path)
    payload = target.read_bytes()
    assert len(payload) == EXPECTED_SIZE
    assert hashlib.sha256(payload).hexdigest() == EXPECTED_SHA256

    records = [json.loads(line) for line in payload.decode("utf-8").splitlines() if line]
    assert len(records) == EXPECTED_RECORDS
    assert len({record["symbol"] for record in records}) == EXPECTED_RECORDS
    assert all(set(record) == {"symbol", "name", "market_evidence"} for record in records)
    assert all(record["market_evidence"].get("exchange") for record in records)
