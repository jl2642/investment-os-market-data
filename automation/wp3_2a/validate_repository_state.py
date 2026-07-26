from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    args = parser.parse_args()
    repo = Path(args.repo_root)
    errors: list[str] = []
    proposals: list[str] = []

    proposal_root = repo / "investment_os_runtime/40_EVIDENCE_AND_LINEAGE/WP3_2A/PROPOSALS"
    if proposal_root.exists():
        for proposal in sorted(path for path in proposal_root.iterdir() if path.is_dir()):
            required = [
                "A_SHARE_FULL_UNIVERSE.csv",
                "ACQUISITION_MANIFEST.json",
                "LINEAGE_ACCEPTANCE.json",
                "PROPOSAL_MANIFEST.json",
                "ZERO_INVESTMENT_MUTATION_PROOF.json",
            ]
            missing = [name for name in required if not (proposal / name).exists()]
            if missing:
                errors.append(f"{proposal.name}: missing {missing}")
                continue
            manifest = json.loads((proposal / "PROPOSAL_MANIFEST.json").read_text(encoding="utf-8"))
            lineage = json.loads((proposal / "LINEAGE_ACCEPTANCE.json").read_text(encoding="utf-8"))
            if lineage.get("status") != "PASS":
                errors.append(f"{proposal.name}: lineage not PASS")
            if sha(proposal / "A_SHARE_FULL_UNIVERSE.csv") != manifest.get("data_sha256"):
                errors.append(f"{proposal.name}: data hash mismatch")
            if manifest.get("trade_authority") != "NONE" or manifest.get("orders") != 0:
                errors.append(f"{proposal.name}: authority violation")
            proposals.append(proposal.name)

    current = repo / "investment_os_runtime/40_EVIDENCE_AND_LINEAGE/WP3_2A/CURRENT"
    binding_path = repo / "investment_os_runtime/50_MARKET_CAPABILITY_BINDINGS/A_SHARE_CURRENT.json"
    acceptance_path = repo / "investment_os_runtime/00_CONTROL/WP3_2A_UNIVERSE_ACCEPTANCE_RECORD.json"
    if current.exists():
        for name in [
            "A_SHARE_FULL_UNIVERSE.csv",
            "LINEAGE_ACCEPTANCE.json",
            "PROPOSAL_MANIFEST.json",
            "ZERO_INVESTMENT_MUTATION_PROOF.json",
        ]:
            if not (current / name).exists():
                errors.append(f"CURRENT missing {name}")

        if binding_path.exists() and acceptance_path.exists():
            binding = json.loads(binding_path.read_text(encoding="utf-8"))
            acceptance = json.loads(acceptance_path.read_text(encoding="utf-8"))
            manifest = json.loads((current / "PROPOSAL_MANIFEST.json").read_text(encoding="utf-8"))
            lineage = json.loads((current / "LINEAGE_ACCEPTANCE.json").read_text(encoding="utf-8"))
            data_path = current / "A_SHARE_FULL_UNIVERSE.csv"
            data_hash = sha(data_path)
            with data_path.open(encoding="utf-8-sig", newline="") as handle:
                row_count = sum(1 for _ in csv.DictReader(handle))

            if binding.get("status") != "ACCEPTED_ON_MAIN":
                errors.append("A_SHARE_CURRENT binding is not ACCEPTED_ON_MAIN")
            if acceptance.get("status") != "ACCEPTED_ON_MAIN":
                errors.append("WP3-2A acceptance record is not ACCEPTED_ON_MAIN")
            if lineage.get("status") != "PASS":
                errors.append("CURRENT lineage not PASS")
            if binding.get("as_of_date") != manifest.get("session"):
                errors.append("CURRENT binding session mismatch")
            if data_hash != binding.get("datasets", {}).get("universe", {}).get("sha256"):
                errors.append("CURRENT binding data hash mismatch")
            if data_hash != acceptance.get("data_sha256"):
                errors.append("CURRENT acceptance data hash mismatch")
            if row_count != binding.get("datasets", {}).get("universe", {}).get("rows"):
                errors.append("CURRENT binding row count mismatch")
            if row_count != acceptance.get("rows"):
                errors.append("CURRENT acceptance row count mismatch")
            if binding.get("trade_authority") != "NONE" or acceptance.get("trade_authority") != "NONE":
                errors.append("CURRENT authority violation")
            if acceptance.get("orders") != 0:
                errors.append("CURRENT order violation")
        else:
            errors.append("CURRENT binding or acceptance record missing")

    result = {
        "status": "PASS" if not errors else "FAIL",
        "proposal_count": len(proposals),
        "proposals": proposals,
        "current_present": current.exists(),
        "current_status": "ACCEPTED_ON_MAIN" if current.exists() and not errors else "INVALID_OR_ABSENT",
        "errors": errors,
        "orders": 0,
        "trade_authority": "NONE",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if not errors else 2)


if __name__ == "__main__":
    main()
