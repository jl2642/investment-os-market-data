from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
MODULE_PATH = SCRIPTS / "fmdl5d_r1_shard.py"
spec = importlib.util.spec_from_file_location("fmdl5d_r1_shard", MODULE_PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_partition_rows_is_deterministic_complete_and_disjoint() -> None:
    rows = [
        {"stock_code_5d": str(code).zfill(5), "security_id": f"HKEX:{code:05d}"}
        for code in range(1, 614)
    ]
    shards = [module.partition_rows(rows, index, 12) for index in range(12)]
    flattened = [row["security_id"] for shard in shards for row in shard]
    assert len(flattened) == len(rows)
    assert len(set(flattened)) == len(rows)
    assert sorted(flattened) == sorted(row["security_id"] for row in rows)
    assert max(len(shard) for shard in shards) - min(len(shard) for shard in shards) <= 1
    assert shards == [module.partition_rows(rows, index, 12) for index in range(12)]


def test_partition_rows_rejects_invalid_boundaries() -> None:
    rows = [{"stock_code_5d": "00001", "security_id": "HKEX:00001"}]
    for shard_index, shard_count in [(-1, 12), (12, 12), (0, 0)]:
        try:
            module.partition_rows(rows, shard_index, shard_count)
        except ValueError:
            pass
        else:
            raise AssertionError((shard_index, shard_count))
