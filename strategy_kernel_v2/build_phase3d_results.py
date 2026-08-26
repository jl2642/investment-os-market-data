import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from strategy_kernel_v2.historical_replay import CachingRegisteredSourceLoader, build_phase3c_replay, load_default_phase3c_inputs
from strategy_kernel_v2.phase3d_outcome_analysis import build_phase3d_outcomes

registry, points = load_default_phase3c_inputs(ROOT)
loader = CachingRegisteredSourceLoader(ROOT)
replay = build_phase3c_replay(registry, points, source_loader=loader)
manifest = json.loads((ROOT/'strategy_kernel_v2/PHASE3D_OUTCOME_SOURCE_MANIFEST.json').read_text(encoding='utf-8'))
results = build_phase3d_outcomes(replay, manifest)
out = ROOT/'strategy_kernel_v2/PHASE3D_INSTANCE_RESULTS.json'
out.write_text(json.dumps(results, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print('PHASE3D_RESULTS_BUILD_PASS legacy_instances=%d candidate_instances=%d candidate_groups=%d source_reads=%d orders=0 trade_authority=NONE' % (results['legacy_instance_count'], results['candidate_security_model_checkpoint_count'], results['candidate_group_record_count'], loader.read_count))
print('RETAINED_SUMMARY=' + json.dumps(results['retained_only_forward_price_summary'], sort_keys=True))
