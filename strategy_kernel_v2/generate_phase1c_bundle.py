"""Generate the governed Phase 1C shadow underwriting bundle.

This script is deterministic and has no network or repository writeback side effects.
It only serializes objects produced from the explicit Canonical extraction registry.
"""
from __future__ import annotations

import json
from pathlib import Path

from strategy_kernel_v2.source_registry import build_all


def main() -> None:
    out = Path(__file__).resolve().parent / "generated" / "UNDERWRITING_OBJECTS_PHASE1C.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "phase": "1C",
        "status": "SHADOW_RESEARCH_ONLY",
        "object_count": 8,
        "objects": build_all(),
        "orders": 0,
        "trade_authority": "NONE",
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
