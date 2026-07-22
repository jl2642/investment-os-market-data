from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from fmdl6e_quality_benchmark import (  # noqa: E402
    audit_bundle,
    benchmark_documents,
    build_candidate,
    load_bundle,
    load_json,
    publish_candidate,
    sha256_file,
    validate_candidate,
    validate_contract,
    write_json,
)

CONTRACT_REL = Path("config/fmdl6e_quality_failure_cost_benchmark_contract.json")
INPUT_REL = Path("outputs/fmdl6d/current")
POINTER_REL = Path("outputs/status/FMDL6D_LAST_SUCCESS.json")


def _copy_runtime(repo: Path) -> None:
    for relative in (CONTRACT_REL, POINTER_REL):
        target = repo / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    shutil.copytree(ROOT / INPUT_REL, repo / INPUT_REL)


def test_contract_and_accepted_fmdl6d_baseline_pass() -> None:
    checks, errors = validate_contract(ROOT, ROOT / CONTRACT_REL)
    assert not errors
    assert all(row["status"] == "PASS" for row in checks)
    contract = load_json(ROOT / CONTRACT_REL)
    bundle = load_bundle(ROOT / INPUT_REL)
    quality_checks, quality_errors, metrics = audit_bundle(contract, bundle, ROOT / INPUT_REL)
    assert not quality_errors
    assert metrics["market_security_count"] == 8
    assert metrics["market_daily_observation_count"] >= 2000
    assert metrics["fx_observation_count"] >= 200
    assert metrics["financial_fact_count"] >= 10
    assert all(row["status"] == "PASS" for row in quality_checks)


def test_build_validate_and_same_input_replay(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate"
    acceptance = tmp_path / "acceptance.json"
    release = build_candidate(ROOT, ROOT / CONTRACT_REL, candidate)
    result = validate_candidate(ROOT, ROOT / CONTRACT_REL, candidate, acceptance)
    assert release["status"] == "FMDL6E_QUALITY_FAILURE_AND_COST_BENCHMARK_ACCEPTED"
    assert result["validation"] == "PASS"
    assert result["same_input_replay"] == "PASS"
    assert load_json(candidate / "FMDL6E_FAILURE_INJECTION.json")["false_negative_count"] == 0
    assert load_json(candidate / "FMDL6E_LKG_PROOF.json")["upstream_lkg_unchanged"] is True


def test_all_declared_failure_injections_are_detected() -> None:
    documents = benchmark_documents(ROOT, ROOT / CONTRACT_REL)
    report = documents["FMDL6E_FAILURE_INJECTION.json"]
    assert report["injection_count"] >= 16
    assert report["detected_count"] == report["injection_count"]
    assert report["false_negative_count"] == 0
    assert all(row["expected_detected"] is True for row in report["injections"])
    assert all(row["mutation_scope"] == "DEEP_COPY_ONLY" for row in report["injections"])


def test_guarded_publish_rejects_tamper_and_preserves_lkg(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _copy_runtime(repo)
    contract_path = repo / CONTRACT_REL
    candidate = repo / "outputs/fmdl6e/candidate"
    build_candidate(repo, contract_path, candidate)
    first = publish_candidate(repo, contract_path, candidate)
    current_manifest = repo / "outputs/fmdl6e/current/FMDL6E_MANIFEST.json"
    before = sha256_file(current_manifest)
    decision_path = candidate / "FMDL6E_DECISION.json"
    decision = load_json(decision_path)
    decision["candidate_pool_mutation_count"] = 1
    write_json(decision_path, decision)
    with pytest.raises(ValueError):
        publish_candidate(repo, contract_path, candidate)
    after = sha256_file(current_manifest)
    assert before == after
    assert load_json(repo / "outputs/status/FMDL6E_LAST_SUCCESS.json")["release_id"] == first["release_id"]


def test_cost_report_keeps_full_universe_closed() -> None:
    documents = benchmark_documents(ROOT, ROOT / CONTRACT_REL)
    cost = documents["FMDL6E_COST_AND_SCALING.json"]
    assert cost["observed_sample"]["provider_cash_cost_observed_usd"] == 0
    assert cost["bounded_24_security_projection"]["security_count"] == 24
    assert cost["bounded_24_security_projection"]["published_output_bytes_high"] >= cost["bounded_24_security_projection"]["published_output_bytes_low"]
    assert cost["full_universe_projection"]["status"] == "DEFERRED_NOT_AUTHORIZED"
    assert cost["full_universe_projection"]["numeric_projection_prohibited"] is True
