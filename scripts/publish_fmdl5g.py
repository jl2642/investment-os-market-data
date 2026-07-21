from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from fmdl5g_core import load_json


def copy_clean(source: Path, target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target)


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish accepted FMDL-5G candidate")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--candidate", default="outputs/fmdl5g/integration/candidate")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    candidate = (repo_root / args.candidate).resolve() if not Path(args.candidate).is_absolute() else Path(args.candidate).resolve()
    contract = load_json(repo_root / "config/fmdl5g_investment_os_integration.json")
    decision = load_json(candidate / "FMDL5G_DECISION.json")
    validation = load_json(candidate / "FMDL5G_INDEPENDENT_VALIDATION.json")
    manifest = load_json(candidate / "FMDL5G_MANIFEST.json")

    if decision.get("status") != contract["exit_status"]:
        raise RuntimeError("FMDL-5G decision is not accepted")
    if validation.get("validation") != "PASS" or validation.get("error_count") != 0:
        raise RuntimeError("FMDL-5G independent validation is not PASS")
    if decision.get("trade_authority") != "NONE":
        raise RuntimeError("FMDL-5G trade authority violation")
    if manifest.get("release_id") != decision.get("release_id"):
        raise RuntimeError("FMDL-5G manifest identity mismatch")

    publication = contract["publication"]
    current = repo_root / publication["current_root"]
    archive = repo_root / publication["archive_root"] / decision["release_id"]
    immutable = repo_root / publication["release_root"] / decision["release_id"]
    copy_clean(candidate, current)
    copy_clean(candidate, archive)
    copy_clean(candidate, immutable)

    metrics = decision["metrics"]
    last_success = {
        "program_id": "FMDL-5G",
        "release_id": decision["release_id"],
        "manifest_release_id": manifest["release_id"],
        "release_sequence": decision["release_sequence"],
        "status": decision["status"],
        "as_of_date": decision["as_of_date"],
        "canonical_sha256": decision["canonical_sha256"],
        "current_path": publication["current_root"],
        "archive_path": str(Path(publication["archive_root"]) / decision["release_id"]),
        "immutable_path": str(Path(publication["release_root"]) / decision["release_id"]),
        "source_release_ids": decision["source_release_ids"],
        "state_transition_count": metrics["state_transition_count"],
        "candidate_reentry_review_count": metrics["candidate_reentry_review_count"],
        "shadow_track_review_count": metrics["shadow_track_review_count"],
        "cross_market_duplication_review_count": metrics["cross_market_duplication_review_count"],
        "candidate_pool_mutation_count": 0,
        "simulation_mutation_count": 0,
        "real_account_mutation_count": 0,
        "order_generation_count": 0,
        "next_gate": decision["next_gate"],
        "trade_authority": "NONE",
    }
    pointer = repo_root / publication["last_success"]
    pointer.parent.mkdir(parents=True, exist_ok=True)
    pointer.write_text(json.dumps(last_success, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Published {decision['release_id']} to Current, Archive and immutable Release")


if __name__ == "__main__":
    main()
