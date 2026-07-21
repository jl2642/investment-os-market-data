from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load_module(name: str, filename: str):
    module_path = SCRIPTS / filename
    spec = importlib.util.spec_from_file_location(name, module_path)
    assert spec and spec.loader
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


financial_module = load_module("fmdl5d_r1_shard", "fmdl5d_r1_shard.py")
disclosure_module = load_module("fmdl5d_r1_disclosure", "fmdl5d_r1_disclosure.py")


def test_partition_rows_is_deterministic_complete_and_disjoint() -> None:
    rows = [
        {"stock_code_5d": str(code).zfill(5), "security_id": f"HKEX:{code:05d}"}
        for code in range(1, 614)
    ]
    shards = [financial_module.partition_rows(rows, index, 12) for index in range(12)]
    flattened = [row["security_id"] for shard in shards for row in shard]
    assert len(flattened) == len(rows)
    assert len(set(flattened)) == len(rows)
    assert sorted(flattened) == sorted(row["security_id"] for row in rows)
    assert max(len(shard) for shard in shards) - min(len(shard) for shard in shards) <= 1
    assert shards == [financial_module.partition_rows(rows, index, 12) for index in range(12)]


def test_partition_rows_rejects_invalid_boundaries() -> None:
    rows = [{"stock_code_5d": "00001", "security_id": "HKEX:00001"}]
    for shard_index, shard_count in [(-1, 12), (12, 12), (0, 0)]:
        try:
            financial_module.partition_rows(rows, shard_index, shard_count)
        except ValueError:
            pass
        else:
            raise AssertionError((shard_index, shard_count))


def test_partition_disclosure_chunks_is_complete_disjoint_and_balanced() -> None:
    chunks = [
        (date(2023 + offset // 12, offset % 12 + 1, 1), date(2023 + offset // 12, offset % 12 + 1, 28))
        for offset in range(43)
    ]
    shards = [disclosure_module.partition_chunks(chunks, index, 12) for index in range(12)]
    flattened = [chunk for shard in shards for chunk in shard]
    assert len(flattened) == len(chunks)
    assert len(set(flattened)) == len(chunks)
    assert sorted(flattened) == sorted(chunks)
    assert max(len(shard) for shard in shards) - min(len(shard) for shard in shards) <= 1
    assert shards == [disclosure_module.partition_chunks(chunks, index, 12) for index in range(12)]


def test_partition_disclosure_chunks_rejects_invalid_boundaries() -> None:
    chunks = [(date(2023, 1, 1), date(2023, 1, 31))]
    for shard_index, shard_count in [(-1, 12), (12, 12), (0, 0)]:
        try:
            disclosure_module.partition_chunks(chunks, shard_index, shard_count)
        except ValueError:
            pass
        else:
            raise AssertionError((shard_index, shard_count))
