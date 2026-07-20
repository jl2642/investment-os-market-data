from pathlib import Path
import zipfile

from scripts import fmdl4a_core as core
from scripts.run_fmdl4a_adapter import deterministic_zip


def cfg():
    return {
        "public_equity_routing": {
            "priority_routes": {
                "A_IMMEDIATE_RESEARCH": ["idea-generation", "company-tearsheet"],
                "DEFAULT": ["idea-generation"],
            }
        },
        "evidence_envelope": {"authority": "DATA_AND_RESEARCH_EVIDENCE_ONLY"},
    }


def test_route_default_and_priority():
    assert core.route_for_priority("A_IMMEDIATE_RESEARCH", cfg()) == ["idea-generation", "company-tearsheet"]
    assert core.route_for_priority("UNKNOWN", cfg()) == ["idea-generation"]


def test_envelope_is_deterministic_and_valid():
    unified = {
        "symbol": "600000.SH", "name": "浦发银行", "market_as_of_date": "2026-07-17",
        "exchange": "SH", "board": "SH_MAIN", "sector_profile": "GENERAL_NON_FINANCIAL",
        "close": 10.0, "capitalization_state": "COMPLETE", "valuation_valid_metric_count": 3,
        "valuation_decision_grade_metric_count": 3, "shareholder_return_state": "COMPLETE",
    }
    financial = {"score_state": "SCORE_ACCEPTED", "score_confidence": "HIGH", "financial_score": 88.0}
    releases = {"FMDL-2": "r2", "FMDL-3C-D": "r3", "FMDL-3E-FINAL": "r4"}
    first = core.envelope_record(unified, financial, None, release_ids=releases, cfg=cfg())
    second = core.envelope_record(unified, financial, None, release_ids=releases, cfg=cfg())
    assert first == second
    assert core.validate_envelope_shape(first) == []
    assert first["trade_authority"] == "NONE"


def test_quality_state_degrades_missing_evidence():
    quality, limitations = core.quality_state(
        {"close": 1.0, "capitalization_state": "PARTIAL", "valuation_valid_metric_count": 0, "shareholder_return_state": "UNAVAILABLE"},
        {"score_state": "INSUFFICIENT_FACTOR_COVERAGE", "score_confidence": "UNAVAILABLE"},
    )
    assert quality == "RESEARCH_USABLE_WITH_LIMITATIONS"
    assert "VALUATION_EVIDENCE_THIN" in limitations


def test_stable_hash_ignores_dict_order():
    assert core.stable_hash({"a": 1, "b": 2}) == core.stable_hash({"b": 2, "a": 1})


def test_deterministic_zip_is_byte_identical(tmp_path: Path):
    source = tmp_path / "source"
    (source / "CORE_STATIC").mkdir(parents=True)
    (source / "EVIDENCE").mkdir(parents=True)
    (source / "CORE_STATIC/a.json").write_text('{"a":1}\n', encoding="utf-8")
    (source / "EVIDENCE/b.csv").write_text("x\n1\n", encoding="utf-8")
    first = tmp_path / "first.zip"
    second = tmp_path / "second.zip"
    deterministic_zip(source, first)
    deterministic_zip(source, second)
    assert core.sha256_file(first) == core.sha256_file(second)
    with zipfile.ZipFile(first) as archive:
        assert archive.namelist() == ["CORE_STATIC/a.json", "EVIDENCE/b.csv"]


def test_evidence_id_changes_when_evidence_changes():
    unified = {
        "symbol": "000001.SZ", "name": "平安银行", "market_as_of_date": "2026-07-17",
        "exchange": "SZ", "board": "SZ_MAIN", "sector_profile": "GENERAL_NON_FINANCIAL",
        "close": 10.0, "capitalization_state": "COMPLETE", "valuation_valid_metric_count": 3,
        "shareholder_return_state": "COMPLETE",
    }
    releases = {"FMDL-2": "r2", "FMDL-3C-D": "r3", "FMDL-3E-FINAL": "r4"}
    first = core.envelope_record(unified, {"score_state": "SCORE_ACCEPTED", "score_confidence": "HIGH", "financial_score": 80.0}, None, release_ids=releases, cfg=cfg())
    second = core.envelope_record(unified, {"score_state": "SCORE_ACCEPTED", "score_confidence": "HIGH", "financial_score": 81.0}, None, release_ids=releases, cfg=cfg())
    assert first["evidence_id"] != second["evidence_id"]
    assert first["semantic_hash"] != second["semantic_hash"]
