from __future__ import annotations

import json

import pandas as pd

from scripts import fmdl3b_semantic_overrides as semantic
from scripts import validate_fmdl3b_candidate as base


def main() -> int:
    base_result = base.main()
    cfg = base.load(base.CFG)
    root = base.ROOT / cfg["publication"]["candidate_root"]
    validation_path = root / "FMDL3B1_VALIDATION.json"
    payload = base.load(validation_path)
    raw = pd.read_csv(root / "FMDL3B_RAW_FACTS.csv", encoding="utf-8-sig")
    ambiguous = semantic.ambiguous_source_mapping_groups(raw)
    expected = cfg["acceptance_policy"]["maximum_ambiguous_source_mapping_group_count"]
    status = "PASS" if len(ambiguous) <= expected else "FAIL"
    payload["validation_version"] = "1.1.0"
    payload["checks"].append({
        "check_id": "ZERO_AMBIGUOUS_SOURCE_MAPPING_GROUPS",
        "status": status,
        "detail": {"observed": len(ambiguous), "maximum": expected},
    })
    payload["metrics"]["ambiguous_source_mapping_group_count"] = len(ambiguous)
    failures = [check["check_id"] for check in payload["checks"] if check["status"] != "PASS"]
    payload["hard_failures"] = failures
    payload["status"] = "PASS" if not failures else "FAIL"
    base.dump(validation_path, payload)
    return 0 if payload["status"] == "PASS" and base_result == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
