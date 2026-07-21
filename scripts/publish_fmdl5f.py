#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

ACCEPTED_STATUS = "FMDL5F_PUBLIC_EQUITY_RESEARCH_ADAPTER_ACCEPTED"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def copy_tree(source: Path, target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--candidate", default="outputs/fmdl5f/research/candidate")
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    candidate_arg = Path(args.candidate)
    candidate = candidate_arg if candidate_arg.is_absolute() else root / candidate_arg
    contract = json.loads((root / "config/fmdl5f_public_equity_research_contract.json").read_text(encoding="utf-8"))
    decision = json.loads((candidate / "FMDL5F_DECISION.json").read_text(encoding="utf-8"))
    quality = json.loads((candidate / "FMDL5F_QUALITY_REPORT.json").read_text(encoding="utf-8"))
    manifest = json.loads((candidate / "FMDL5F_MANIFEST.json").read_text(encoding="utf-8"))
    if decision.get("status") != ACCEPTED_STATUS or quality.get("status") != "PASS":
        raise RuntimeError("CANDIDATE_NOT_ACCEPTED")
    if decision.get("hard_failures") or quality.get("hard_failures"):
        raise RuntimeError("HARD_FAILURES")
    if decision.get("trade_authority") != "NONE":
        raise RuntimeError("TRADE_AUTHORITY_VIOLATION")
    for key in ("candidate_pool_mutation_count", "simulation_mutation_count", "real_account_mutation_count", "order_generation_count"):
        if decision.get(key) != 0:
            raise RuntimeError(f"STATE_MUTATION_VIOLATION:{key}")
    if decision["release_id"] != manifest["release_id"] or decision["canonical_sha256"] != manifest["canonical_sha256"]:
        raise RuntimeError("MANIFEST_IDENTITY_MISMATCH")
    for name, metadata in manifest["files"].items():
        path = candidate / name
        if not path.is_file() or path.stat().st_size != metadata["size_bytes"] or sha256_file(path) != metadata["sha256"]:
            raise RuntimeError(f"MANIFEST_FILE_MISMATCH:{name}")

    publication = contract["publication"]
    release_id = decision["release_id"]
    current = root / publication["current_root"]
    immutable = root / publication["release_root"] / release_id
    archive = root / publication["archive_root"] / release_id
    copy_tree(candidate, current)
    copy_tree(candidate, immutable)
    copy_tree(candidate, archive)
    metrics = decision["metrics"]
    last_success = {
        "program_id": "FMDL-5F",
        "status": decision["status"],
        "release_id": release_id,
        "release_sequence": decision["release_sequence"],
        "source_release_ids": decision["source_release_ids"],
        "as_of_date": decision["as_of_date"],
        "canonical_sha256": decision["canonical_sha256"],
        "registry_count": metrics["registry_count"],
        "active_research_cohort_count": metrics["active_research_cohort_count"],
        "formal_research_object_count": metrics["formal_research_object_count"],
        "decision_counts": metrics["decision_counts"],
        "graduated_or_shadow_count": metrics["graduated_or_shadow_count"],
        "official_source_row_count": metrics["official_source_row_count"],
        "required_case_type_missing_count": metrics["required_case_type_missing_count"],
        "candidate_pool_mutation_count": 0,
        "simulation_mutation_count": 0,
        "real_account_mutation_count": 0,
        "order_generation_count": 0,
        "current_path": str(current.relative_to(root)),
        "immutable_path": str(immutable.relative_to(root)),
        "archive_path": str(archive.relative_to(root)),
        "manifest_release_id": manifest["release_id"],
        "next_gate": decision["next_gate"],
        "trade_authority": "NONE"
    }
    last_path = root / publication["last_success"]
    last_path.parent.mkdir(parents=True, exist_ok=True)
    last_path.write_text(json.dumps(last_success, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(last_success, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
