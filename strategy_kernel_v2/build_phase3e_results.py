import json
from pathlib import Path

from strategy_kernel_v2.phase3e_ablation import build_default

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "strategy_kernel_v2/PHASE3E_ABLATION_RESULTS.json"


def main() -> None:
    result = build_default(ROOT)
    OUT.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(
        "PHASE3E_ABLATION_BUILD_PASS "
        f"checkpoints={result['checkpoint_count']} "
        f"feature_instances={result['feature_security_instance_count']} "
        f"source_reads={result['historical_source_reads']} "
        f"single_component_unlocks={result['single_component_ablation_unlock_count']} "
        f"finding={result['finding']} "
        f"orders={result['controls']['orders']} "
        f"trade_authority={result['controls']['trade_authority']}"
    )
    print("PHASE2_ABLATION=" + json.dumps(result["phase2_ablation"], sort_keys=True))
    print("SIMPLE_ABLATION=" + json.dumps(result["simple_ablation"], sort_keys=True))
    print("ADJACENT_OBSERVABLES=" + json.dumps(result["adjacent_observable_inventory"], sort_keys=True))


if __name__ == "__main__":
    main()
