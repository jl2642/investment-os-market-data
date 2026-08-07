import json
from pathlib import Path

from pipeline.hkcu1_r2f_validate import validate_changed_paths, validate_frozen_r2e_core


def test_diff_scope_accepts_hkcu_only_paths():
    assert validate_changed_paths([
        "pipeline/hkcu1_r2f_validate.py",
        "outputs/hkcu1/current/HKCU1_R2E_DECISION.json",
        ".github/workflows/hkcu-1-r2f-release-validation.yml",
    ]) == []


def test_diff_scope_rejects_non_hkcu_path():
    errors = validate_changed_paths(["outputs/real_account/current.json"])
    assert errors == ["OUT_OF_SCOPE_PR_PATH:outputs/real_account/current.json"]


def test_frozen_r2e_core_rejects_post_acceptance_logic_change():
    errors = validate_frozen_r2e_core(["pipeline/hkcu1_r2e_merge_fmdl5e.py"])
    assert errors == ["R2E_CORE_CHANGED_AFTER_ACCEPTED_RUN:pipeline/hkcu1_r2e_merge_fmdl5e.py"]


def test_frozen_r2e_core_allows_r2f_and_evidence_only_change():
    assert validate_frozen_r2e_core([
        "pipeline/hkcu1_r2f_validate.py",
        "outputs/hkcu1/HKCU1_R2E_ACCEPTANCE_20260807.json",
        "outputs/hkcu1/current/HKCU1_R2E_DECISION.json",
    ]) == []


def test_r2f_release_contract_explicitly_binds_r2e_gate_contract():
    root = Path(__file__).resolve().parents[1]
    release = json.loads((root / "config/hkcu1_r2f_release_contract.json").read_text(encoding="utf-8"))
    source = release["source_r2e_contract"]
    assert source == "config/hkcu1_r2e_universe_contract.json"
    r2e = json.loads((root / source).read_text(encoding="utf-8"))
    assert r2e["investable_gate"]["allowed_fmdl5e_investability_status"] == ["ELIGIBLE_CORE", "ELIGIBLE_WATCH"]
    assert r2e["investable_gate"]["allowed_security_types"] == ["COMMON_EQUITY"]
    assert r2e["freshness"]["maximum_fmdl5e_age_stock_connect_service_days"] == 5
