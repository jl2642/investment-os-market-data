"""Materialize the Phase 3A Canonical point-in-time evidence ledger."""

from __future__ import annotations

import json
from pathlib import Path

from strategy_kernel_v2.point_in_time_ledger import build_point_in_time_ledger

ROOT = Path(__file__).resolve().parent
REGISTRY = ROOT / "PHASE3A_EVIDENCE_REGISTRY.json"
POINTS = ROOT / "PHASE3A_DECISION_POINTS.json"
OUTPUT = ROOT / "generated" / "PHASE3A_POINT_IN_TIME_EVIDENCE_LEDGER.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build() -> dict:
    registry = load_json(REGISTRY)
    points = load_json(POINTS)
    return build_point_in_time_ledger(
        registry["records"],
        points["decision_points"],
        allowed_authority_domains=("CANONICAL_MAIN",),
    )


def main() -> int:
    out = build()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        "PHASE3A_LEDGER_BUILT",
        f"records={out['evidence_record_count']}",
        f"checkpoints={out['decision_point_count']}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
