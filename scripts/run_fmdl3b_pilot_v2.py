from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from scripts import fmdl3b_core as core
from scripts import fmdl3b_semantic_overrides as semantic
from scripts import run_fmdl3b_pilot as base


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def patched_load_registry(path: Path):
    index, payload = ORIGINAL_LOAD_REGISTRY(path)
    return semantic.apply_overrides(index, payload)


ORIGINAL_LOAD_REGISTRY = core.load_registry


def main() -> int:
    core.load_registry = patched_load_registry
    result = base.main()
    cfg = json.loads(base.CONFIG.read_text(encoding="utf-8"))
    candidate = base.ROOT / cfg["publication"]["candidate_root"]
    raw = pd.read_csv(candidate / "FMDL3B_RAW_FACTS.csv", encoding="utf-8-sig")
    ambiguous = semantic.ambiguous_source_mapping_groups(raw)
    ambiguous.to_csv(candidate / "FMDL3B_AMBIGUOUS_MAPPING_GROUPS.csv", index=False, encoding="utf-8-sig")
    decision_path = candidate / "FMDL3B1_DECISION.json"
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    decision["decision_version"] = "1.1.0"
    decision["metrics"]["ambiguous_source_mapping_group_count"] = len(ambiguous)
    decision["semantic_override_version"] = "1.0.0"
    if len(ambiguous) > cfg["acceptance_policy"]["maximum_ambiguous_source_mapping_group_count"]:
        decision["status"] = "FMDL3B1_REMEDIATION_REQUIRED"
    decision_path.write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest_path = candidate / "FMDL3B1_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["manifest_version"] = "1.1.0"
    manifest["files"] = []
    for path in sorted(candidate.iterdir()):
        if path.name != manifest_path.name:
            manifest["files"].append({"path": path.name, "sha256": sha256(path), "bytes": path.stat().st_size})
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0 if decision["status"] == "FMDL3B1_ACCEPTED_NORMALIZATION_PILOT" else 1


if __name__ == "__main__":
    raise SystemExit(main())
