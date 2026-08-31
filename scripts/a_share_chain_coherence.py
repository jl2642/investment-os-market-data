#!/usr/bin/env python3
"""Assess A-share Market -> History -> Factor -> Screening production coherence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

PATHS = {
    "market": Path("outputs/current/CURRENT_RELEASE.json"),
    "history": Path("outputs/history/current/HISTORY_CURRENT_RELEASE.json"),
    "factor": Path("outputs/factors/current/FACTOR_CURRENT_RELEASE.json"),
    "screening": Path("outputs/screens/current/SCREENING_CURRENT_RELEASE.json"),
}


def _read_json(root: Path, relative: Path) -> dict[str, Any] | None:
    path = root / relative
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return value if isinstance(value, dict) else None


def assess_chain_coherence(root: Path = ROOT, *, target_date: str | None = None) -> dict[str, Any]:
    layers = {name: _read_json(root, path) for name, path in PATHS.items()}
    market_date = str((layers["market"] or {}).get("as_of_date") or "")
    expected = str(target_date or market_date or "")

    dates = {
        name: str((payload or {}).get("as_of_date") or "")
        for name, payload in layers.items()
    }
    release_ids = {
        "history": str((layers["history"] or {}).get("release_id") or ""),
        "factor": str((layers["factor"] or {}).get("release_id") or ""),
        "screening": str((layers["screening"] or {}).get("release_id") or ""),
    }
    lineage = {
        "factor_history_release_id": str((layers["factor"] or {}).get("history_release_id") or ""),
        "screening_factor_release_id": str((layers["screening"] or {}).get("factor_release_id") or ""),
    }

    reasons: list[str] = []
    for name in ("market", "history", "factor", "screening"):
        if layers[name] is None:
            reasons.append(f"{name.upper()}_CURRENT_MISSING")
        elif expected and dates[name] != expected:
            reasons.append(f"{name.upper()}_AS_OF_MISMATCH:{dates[name]}:{expected}")

    if layers["factor"] is not None and layers["history"] is not None:
        if not release_ids["history"] or lineage["factor_history_release_id"] != release_ids["history"]:
            reasons.append(
                "FACTOR_HISTORY_LINEAGE_MISMATCH:"
                f"{lineage['factor_history_release_id']}:{release_ids['history']}"
            )

    if layers["screening"] is not None and layers["factor"] is not None:
        if not release_ids["factor"] or lineage["screening_factor_release_id"] != release_ids["factor"]:
            reasons.append(
                "SCREENING_FACTOR_LINEAGE_MISMATCH:"
                f"{lineage['screening_factor_release_id']}:{release_ids['factor']}"
            )

    coherent = bool(expected) and not reasons
    screening_refresh_required = any(
        reason.startswith("SCREENING_") or reason.startswith("FACTOR_")
        for reason in reasons
    )
    return {
        "schema_version": "1.0.0",
        "status": "PASS_COHERENT" if coherent else "DEGRADED_CHAIN_MISMATCH",
        "target_as_of_date": expected or None,
        "layer_as_of_dates": dates,
        "release_ids": release_ids,
        "lineage": lineage,
        "reasons": reasons,
        "screening_refresh_required": screening_refresh_required,
        "trade_authority": "NONE",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expect-date", default="")
    parser.add_argument("--write", default="")
    parser.add_argument("--fail-on-incoherent", action="store_true")
    args = parser.parse_args()

    result = assess_chain_coherence(ROOT, target_date=args.expect_date or None)
    if args.write:
        path = ROOT / args.write
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    if args.fail_on_incoherent and result["status"] != "PASS_COHERENT":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
