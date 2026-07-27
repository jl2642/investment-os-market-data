#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


PATH = Path(__file__).resolve().parent / "build_candidate_refresh_current.py"
OLD = '''    status = (
        "PASS_CANONICAL_INDUSTRY_QUALITY_GATE"
        if complete_fields
        and coverage >= float(contract["quality_gates"]["security_id_coverage_min"])
        and unresolved / total <= float(contract["quality_gates"]["unresolved_industry_max"]) if total else False
        else "BLOCKED_SECURITY_MASTER_INDUSTRY_FIELDS_INCOMPLETE"
    )'''
NEW = '''    passes_quality = bool(
        total
        and complete_fields
        and coverage >= float(contract["quality_gates"]["security_id_coverage_min"])
        and unresolved / total <= float(contract["quality_gates"]["unresolved_industry_max"])
    )
    status = (
        "PASS_CANONICAL_INDUSTRY_QUALITY_GATE"
        if passes_quality
        else "BLOCKED_SECURITY_MASTER_INDUSTRY_FIELDS_INCOMPLETE"
    )'''


def main() -> None:
    text = PATH.read_text(encoding="utf-8")
    if OLD in text:
        PATH.write_text(text.replace(OLD, NEW), encoding="utf-8")
        print("WP3_R_SOURCE_REPAIRED")
        return
    if NEW in text:
        print("WP3_R_SOURCE_ALREADY_VALID")
        return
    raise SystemExit("WP3_R_EXPECTED_INDUSTRY_PREDICATE_NOT_FOUND")


if __name__ == "__main__":
    main()
