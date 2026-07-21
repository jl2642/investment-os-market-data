#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
from jsonschema import Draft202012Validator, FormatChecker

from run_fmdl5f_public_equity_research import run, stable_hash

ACCEPTED_STATUS = "FMDL5F_PUBLIC_EQUITY_RESEARCH_ADAPTER_ACCEPTED"
DETERMINISTIC_FILES = [
    "FMDL5F_RESEARCH_PRIORITY_REGISTRY.csv",
    "FMDL5F_RESEARCH_OBJECTS.jsonl",
    "FMDL5F_RESEARCH_OBJECT_INDEX.csv",
    "FMDL5F_SOURCE_LEDGER.csv",
    "FMDL5F_GRADUATION_REGISTRY.csv",
    "FMDL5F_CASE_ROUTE_COVERAGE.csv",
    "FMDL5F_QUALITY_REPORT.json",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def as_bool(value: object) -> bool:
    return value is True or str(value).strip().lower() in {"1", "true", "yes", "y"}


def read_objects(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def validate_manifest(candidate: Path, manifest: dict, contract: dict) -> None:
    expected = set(contract["outputs"]) - {"FMDL5F_MANIFEST.json"}
    assert set(manifest["files"]) == expected
    for name, metadata in manifest["files"].items():
        path = candidate / name
        assert path.is_file(), name
        assert path.stat().st_size == metadata["size_bytes"], name
        assert sha256_file(path) == metadata["sha256"], name
    deterministic = {
        name: {"sha256": sha256_file(candidate / name), "size_bytes": (candidate / name).stat().st_size}
        for name in sorted(DETERMINISTIC_FILES)
    }
    assert stable_hash(deterministic) == manifest["canonical_sha256"]


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
    registry = pd.read_csv(candidate / "FMDL5F_RESEARCH_PRIORITY_REGISTRY.csv", dtype={"stock_code_5d": str}, encoding="utf-8-sig")
    index = pd.read_csv(candidate / "FMDL5F_RESEARCH_OBJECT_INDEX.csv", dtype={"stock_code_5d": str}, encoding="utf-8-sig")
    sources = pd.read_csv(candidate / "FMDL5F_SOURCE_LEDGER.csv", dtype={"stock_code_5d": str}, encoding="utf-8-sig")
    graduation = pd.read_csv(candidate / "FMDL5F_GRADUATION_REGISTRY.csv", dtype={"stock_code_5d": str}, encoding="utf-8-sig")
    cases = pd.read_csv(candidate / "FMDL5F_CASE_ROUTE_COVERAGE.csv", encoding="utf-8-sig")
    objects = read_objects(candidate / "FMDL5F_RESEARCH_OBJECTS.jsonl")

    schema = json.loads((root / "schemas/fmdl5f_research_object_v1.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for obj in objects:
        validator.validate(obj)
        stored = obj["object_sha256"]
        payload = dict(obj)
        payload.pop("object_sha256")
        assert stable_hash(payload) == stored

    assert decision["status"] == ACCEPTED_STATUS
    assert quality["status"] == "PASS"
    assert not decision["hard_failures"] and not quality["hard_failures"]
    assert decision["release_id"] == manifest["release_id"]
    assert decision["canonical_sha256"] == manifest["canonical_sha256"]
    assert decision["source_release_ids"] == contract["source_release_ids"] == manifest["source_release_ids"]
    validate_manifest(candidate, manifest, contract)

    assert len(registry) == 100 and registry["security_id"].nunique() == 100
    assert registry["overall_rank"].tolist() == list(range(1, 101))
    active = registry[registry["active_research_cohort"].map(as_bool)]
    assert len(active) == 20
    assert len(objects) == len(index) == 20
    assert {obj["security_id"] for obj in objects} == set(active["security_id"])
    assert index["research_id"].nunique() == 20
    assert graduation["security_id"].nunique() == 100

    decisions = pd.Series([obj["research_decision"] for obj in objects]).value_counts().to_dict()
    grad_shadow = decisions.get("GRADUATED", 0) + decisions.get("SHADOW_TRACK", 0)
    low, high = contract["decision_policy"]["graduated_or_shadow_target_range"]
    assert low <= grad_shadow <= high
    assert set(cases["case_type"]) == set(contract["decision_policy"]["required_case_types"])
    assert (cases["coverage_count"] > 0).all() and set(cases["coverage_status"]) == {"PASS"}

    required_bindings = {"FMDL5E_ACCEPTED_SCREENING_ROW", "FMDL5E_ACCEPTED_FACTOR_ROW", "FMDL5D_ACCEPTED_FINANCIAL_CURRENT"}
    as_of = pd.Timestamp(decision["as_of_date"]).tz_localize("Asia/Hong_Kong") + pd.Timedelta(hours=23, minutes=59)
    for obj in objects:
        assert required_bindings.issubset({x["source_type"] for x in obj["evidence_bindings"]})
        assert len(obj["public_sources"]) >= 1
        if obj["research_decision"] == "GRADUATED":
            assert len(obj["public_sources"]) >= 2
        for source in obj["public_sources"]:
            assert urlparse(source["url"]).netloc == contract["source_policy"]["official_domain"]
            assert pd.to_datetime(source["available_from"], utc=True) <= as_of.tz_convert("UTC")
    public = sources[sources["source_class"] == "PUBLIC_OFFICIAL"]
    assert len(public) == quality["metrics"]["official_source_row_count"]
    assert not public[["research_id", "source_id", "url"]].duplicated().any()

    mutation_cols = ["candidate_pool_admission", "simulation_admission", "real_account_admission", "order_generation"]
    assert registry[mutation_cols].apply(lambda c: c.map(as_bool)).to_numpy().sum() == 0
    assert set(registry["trade_authority"]) == {"NONE"}
    assert decision["candidate_pool_mutation_count"] == 0
    assert decision["simulation_mutation_count"] == 0
    assert decision["real_account_mutation_count"] == 0
    assert decision["order_generation_count"] == 0
    assert decision["trade_authority"] == "NONE"

    with tempfile.TemporaryDirectory(prefix="fmdl5f-replay-") as tmp:
        replay = Path(tmp) / "candidate"
        replay_decision = run(root, replay)
        assert replay_decision["release_id"] == decision["release_id"]
        assert replay_decision["canonical_sha256"] == decision["canonical_sha256"]
        for name in DETERMINISTIC_FILES:
            assert sha256_file(replay / name) == sha256_file(candidate / name), name

    print(json.dumps({
        "status": "PASS",
        "release_id": decision["release_id"],
        "registry_count": len(registry),
        "formal_research_object_count": len(objects),
        "graduated_or_shadow_count": grad_shadow,
        "official_source_row_count": len(public),
        "same_input_idempotence": True,
        "trade_authority": "NONE"
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
