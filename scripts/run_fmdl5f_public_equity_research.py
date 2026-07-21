#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from fmdl5f_core import (
    ACCEPTED_STATUS, PROGRAM_ID, case_types, clean_text, disclosure_score,
    load_inputs, select_public_sources, sha256_file, stable_hash,
)
from fmdl5f_model import build_object, build_registry, quality

def run(root: Path, output: Path) -> dict[str, Any]:
    contract, data = load_inputs(root)
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)

    longlist = data["longlist"].sort_values("overall_rank").reset_index(drop=True)
    if len(longlist) != contract["research_cohort"]["required_registry_count"]:
        raise RuntimeError("INVALID_LONGLIST_COUNT")
    if longlist["security_id"].duplicated().any():
        raise RuntimeError("DUPLICATE_LONGLIST_SECURITY")
    as_of = pd.to_datetime(longlist["as_of_date"], errors="raise").max()
    profiles_pack = data["profiles"]
    profiles = profiles_pack["profiles"]
    required_profile_fields = {
        "decision", "business_model", "competitive_position", "owner_quality",
        "earnings_drivers", "catalysts", "risks", "variant_perception",
        "why_now", "first_rejection", "what_would_make_investable",
        "prove_kill_checks", "case_types",
    }
    for code, profile in profiles.items():
        missing = required_profile_fields - set(profile)
        if missing:
            raise RuntimeError(f"RESEARCH_PROFILE_FIELDS:{code}:{','.join(sorted(missing))}")
        if profile.get("decision") not in contract["decision_policy"]["allowed_decisions"]:
            raise RuntimeError(f"RESEARCH_PROFILE_DECISION:{code}")
    registry = build_registry(longlist, profiles, contract)
    active = longlist[longlist["research_priority"] == contract["research_cohort"]["active_priority"]].copy()
    factor_table = data["factor_table"].copy()
    factor_by_id = {str(row["security_id"]): row for _, row in factor_table.iterrows()}
    financial = data["financial_current"].copy()
    financial_by_id = {str(row["security_id"]): row for _, row in financial.iterrows()}
    disclosures = data["disclosures"].copy()

    objects: list[dict[str, Any]] = []
    missing_profiles: list[str] = []
    source_rows: list[dict[str, Any]] = []
    for _, long_row in active.iterrows():
        code = clean_text(long_row["stock_code_5d"]).zfill(5)
        profile = profiles.get(code)
        if profile is None:
            missing_profiles.append(code)
            continue
        factor_row = factor_by_id.get(clean_text(long_row["security_id"]))
        if factor_row is None:
            raise RuntimeError(f"MISSING_FACTOR_ROW:{code}")
        financial_row = financial_by_id.get(clean_text(long_row["security_id"]))
        public_sources = select_public_sources(code, disclosures, financial_row, as_of, contract)
        obj = build_object(long_row, factor_row, financial_row, profile, public_sources, contract, profiles_pack["profile_version"])
        objects.append(obj)
        for source in public_sources:
            source_rows.append({
                "research_id": obj["research_id"],
                "security_id": obj["security_id"],
                "stock_code_5d": code,
                "source_class": "PUBLIC_OFFICIAL",
                **source,
            })
        for source in obj["evidence_bindings"]:
            source_rows.append({
                "research_id": obj["research_id"],
                "security_id": obj["security_id"],
                "stock_code_5d": code,
                "source_class": "INTERNAL_ACCEPTED_EVIDENCE",
                "source_type": source["source_type"],
                "source_tier": "ACCEPTED_INTERNAL_RELEASE",
                "source_id": source["source_id"],
                "title": source["source_type"],
                "url": "",
                "filing_type": "",
                "report_period_end": "",
                "available_from": obj["as_of_date"],
                "source_record_sha256": source["source_hash"],
            })

    source_ledger = pd.DataFrame(source_rows)
    index_rows = [{
        "as_of_date": obj["as_of_date"],
        "research_id": obj["research_id"],
        "security_id": obj["security_id"],
        "stock_code_5d": obj["stock_code_5d"],
        "official_security_name_en": obj["official_security_name_en"],
        "research_decision": obj["research_decision"],
        "research_stage": obj["research_stage"],
        "case_types": "|".join(obj["case_types"]),
        "official_source_count": len(obj["public_sources"]),
        "total_source_count": len(obj["public_sources"]) + len(obj["evidence_bindings"]),
        "object_sha256": obj["object_sha256"],
        "next_workflow": obj["next_workflow"],
        "trade_authority": "NONE",
    } for obj in objects]
    object_index = pd.DataFrame(index_rows).sort_values(["research_decision", "stock_code_5d"]).reset_index(drop=True)
    graduation = registry[[
        "as_of_date", "overall_rank", "research_priority", "security_id", "stock_code_5d",
        "official_security_name_en", "research_stage", "research_decision", "decision_reason",
        "candidate_pool_admission", "simulation_admission", "real_account_admission", "order_generation", "trade_authority"
    ]].copy()

    graduate_shadow = [obj for obj in objects if obj["research_decision"] in {"GRADUATED", "SHADOW_TRACK"}]
    case_rows = []
    for case_type in contract["decision_policy"]["required_case_types"]:
        matched = [obj for obj in graduate_shadow if case_type in obj["case_types"]]
        case_rows.append({
            "case_type": case_type,
            "coverage_count": len(matched),
            "research_ids": "|".join(obj["research_id"] for obj in matched),
            "security_ids": "|".join(obj["security_id"] for obj in matched),
            "decisions": "|".join(obj["research_decision"] for obj in matched),
            "coverage_status": "PASS" if matched else "FAIL",
            "trade_authority": "NONE",
        })
    case_coverage = pd.DataFrame(case_rows)
    q = quality(registry, objects, source_ledger, case_coverage, contract, missing_profiles)

    registry.to_csv(output / "FMDL5F_RESEARCH_PRIORITY_REGISTRY.csv", index=False, encoding="utf-8-sig")
    with (output / "FMDL5F_RESEARCH_OBJECTS.jsonl").open("w", encoding="utf-8") as f:
        for obj in sorted(objects, key=lambda x: x["stock_code_5d"]):
            f.write(json.dumps(obj, ensure_ascii=False, sort_keys=True) + "\n")
    object_index.to_csv(output / "FMDL5F_RESEARCH_OBJECT_INDEX.csv", index=False, encoding="utf-8-sig")
    source_ledger.to_csv(output / "FMDL5F_SOURCE_LEDGER.csv", index=False, encoding="utf-8-sig")
    graduation.to_csv(output / "FMDL5F_GRADUATION_REGISTRY.csv", index=False, encoding="utf-8-sig")
    case_coverage.to_csv(output / "FMDL5F_CASE_ROUTE_COVERAGE.csv", index=False, encoding="utf-8-sig")
    (output / "FMDL5F_QUALITY_REPORT.json").write_text(json.dumps(q, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    deterministic_files = [p for p in output.iterdir() if p.is_file()]
    deterministic_hashes = {p.name: {"sha256": sha256_file(p), "size_bytes": p.stat().st_size} for p in sorted(deterministic_files)}
    canonical = stable_hash(deterministic_hashes)
    release_id = f"FMDL5F_{as_of.strftime('%Y%m%d')}_{canonical[:12]}"
    decision = {
        "program_id": PROGRAM_ID,
        "status": ACCEPTED_STATUS if not q["hard_failures"] else "FMDL5F_REJECTED",
        "release_id": release_id,
        "release_sequence": 16,
        "source_release_ids": contract["source_release_ids"],
        "as_of_date": as_of.date().isoformat(),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "canonical_sha256": canonical,
        "hard_failures": q["hard_failures"],
        "controlled_warnings": q["controlled_warnings"],
        "metrics": q["metrics"],
        "candidate_pool_mutation_count": 0,
        "simulation_mutation_count": 0,
        "real_account_mutation_count": 0,
        "order_generation_count": 0,
        "authority": contract["authority"],
        "trade_authority": "NONE",
        "next_gate": contract["next_gate"],
    }
    (output / "FMDL5F_DECISION.json").write_text(json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest_files = {p.name: {"sha256": sha256_file(p), "size_bytes": p.stat().st_size} for p in sorted(output.iterdir()) if p.is_file()}
    manifest = {
        "program_id": PROGRAM_ID,
        "release_id": release_id,
        "release_sequence": 16,
        "source_release_ids": contract["source_release_ids"],
        "as_of_date": as_of.date().isoformat(),
        "canonical_sha256": canonical,
        "files": manifest_files,
    }
    (output / "FMDL5F_MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return decision


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--output", default="outputs/fmdl5f/research/candidate")
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    decision = run(root, root / args.output)
    return 0 if decision["status"] == ACCEPTED_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
