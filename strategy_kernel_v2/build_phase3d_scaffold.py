import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from strategy_kernel_v2.historical_replay import (
    CachingRegisteredSourceLoader,
    build_phase3c_replay,
    load_default_phase3c_inputs,
)
from strategy_kernel_v2.phase3d_measurement import build_measurability_scaffold

registry, points = load_default_phase3c_inputs(ROOT)
loader = CachingRegisteredSourceLoader(ROOT)
replay = build_phase3c_replay(registry, points, source_loader=loader)
scaffold = build_measurability_scaffold(replay)
if scaffold["legacy_evaluable_instance_count"] != 29:
    raise AssertionError("PHASE3D_EXPECTED_29_LEGACY_INSTANCES")
print("PHASE3D_SCAFFOLD_PASS legacy_instances=29 source_reads=%d candidate_records=%d orders=0 trade_authority=NONE" % (loader.read_count, scaffold["candidate_record_count"]))
for row in scaffold["legacy_instances"]:
    print("INSTANCE|{decision_point_id}|{checkpoint_at}|{security_id}|{legacy_status}|{legacy_disposition}".format(**row))
