from pathlib import Path
import zipfile

from scripts import fmdl4_final_core as core


def sample_record():
    return {
        "symbol": "600900.SH",
        "evidence_as_of": "2026-07-17",
        "research_id": "FMDL4B-RSCH-600900.SH-test",
        "state_domain": "FMDL4C_REENTRY_REVIEW_QUEUE",
        "candidate_pool_mutation_count": 0,
        "simulation_mutation_count": 0,
        "real_account_mutation_count": 0,
        "order_generation_count": 0,
        "trade_authority": "NONE"
    }


def test_stable_hash_ignores_dict_order():
    assert core.stable_hash({"a": 1, "b": 2}) == core.stable_hash({"b": 2, "a": 1})


def test_valid_operational_record_passes():
    assert core.validate_operational_record(sample_record(), "2026-07-17") == []


def test_all_failure_injections_are_rejected():
    results = core.run_failure_injections(sample_record(), "2026-07-17")
    assert len(results) == 4
    assert all(row["status"] == "REJECTED_AS_REQUIRED" for row in results)
    assert all(row["current_replacement_authorized"] is False for row in results)


def test_capability_matrix_preserves_disabled_execution():
    cfg = {
        "capability_matrix": [
            ["ORDER_EXECUTION", "INTENTIONALLY_DISABLED", "No broker execution"],
            ["FILE_LIBRARY_SINGLE_PACKAGE_CANONICAL", "REFRESH_REQUIRED_POST_FMDL4", "Import base bytes"]
        ]
    }
    matrix = {row["capability"]: row["status"] for row in core.capability_matrix(cfg)}
    assert matrix["ORDER_EXECUTION"] == "INTENTIONALLY_DISABLED"
    assert matrix["FILE_LIBRARY_SINGLE_PACKAGE_CANONICAL"] == "REFRESH_REQUIRED_POST_FMDL4"


def test_file_library_plan_never_deletes_release4_early():
    cfg = {
        "file_library_audit": {
            "audit_date": "2026-07-20",
            "verification_posture": "TEST",
            "canonical_release_sequence": 4,
            "observed_pointer_release_sequences": [2, 3, 4],
            "cleanup_rule": "DO_NOT_DELETE_RELEASE4_UNTIL_RELEASE8_SINGLE_PACKAGE_IS_IMPORTED_VALIDATED_AND_OPENABLE"
        }
    }
    plan = core.file_library_maintenance_plan(cfg)
    assert plan["automatic_deletion_performed"] is False
    assert "RELEASE4" in plan["safety_rule"]
    assert any("RELEASE2" in item for item in plan["delete_only_after_release8_single_package_acceptance"])


def test_deterministic_zip_is_byte_identical(tmp_path: Path):
    source = tmp_path / "source"
    (source / "CORE_STATIC").mkdir(parents=True)
    (source / "STATE_CURRENT").mkdir(parents=True)
    (source / "CORE_STATIC/a.json").write_text('{"a":1}\n', encoding="utf-8")
    (source / "STATE_CURRENT/b.csv").write_text("x\n1\n", encoding="utf-8")
    first = tmp_path / "first.zip"
    second = tmp_path / "second.zip"
    core.deterministic_zip(source, first)
    core.deterministic_zip(source, second)
    assert core.sha256_file(first) == core.sha256_file(second)
    with zipfile.ZipFile(first) as archive:
        assert archive.namelist() == ["CORE_STATIC/a.json", "STATE_CURRENT/b.csv"]
