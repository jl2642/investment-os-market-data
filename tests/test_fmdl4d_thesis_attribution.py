from pathlib import Path
import zipfile

from scripts import fmdl4d_core as core


def cfg():
    return {
        "tracking": {
            "thesis_version": "FMDL4D-TV1-20260717",
            "maximum_review_days_from_source_as_of": 45,
            "post_catalyst_update_sla_business_days": 3,
            "company_thesis_status_by_queue": {
                "CANDIDATE_POOL_REENTRY_REVIEW_READY": "INTACT_UNTESTED_BASELINE",
                "SHADOW_TRACK_REENTRY_REVIEW_READY": "WATCH_UNTESTED_EXPECTATIONS_OR_QUALITY_GATE",
            },
            "security_thesis_readiness": "NOT_DECISION_GRADE_PENDING_CURRENT_PRICE_AND_SCENARIO",
            "position_action": "WAIT_FOR_PROOF",
            "portfolio_role": "UNASSIGNED_NO_EXPOSURE",
            "exposure_status": "NO_POSITION",
            "attribution_status": "NOT_YET_OBSERVABLE_NO_POSITION",
            "threshold_origin": "DRAFT_THRESHOLD_FOR_PM_CONFIRMATION",
            "threshold_approval_status": "NOT_APPROVED",
        },
        "feedback_proposals": [
            {"proposal_id": "FMDL4D-FB-001", "scope_symbols": ["600900.SH"]},
            {"proposal_id": "FMDL4D-FB-005", "scope_symbols": ["ALL"]},
        ],
        "authority": "THESIS_TRACKING_ATTRIBUTION_AND_FEEDBACK_PROPOSALS_ONLY",
    }


def queue_row():
    return {
        "transition_id": "FMDL4C-TR-600900.SH-test",
        "symbol": "600900.SH",
        "name": "长江电力",
        "queue_state": "CANDIDATE_POOL_REENTRY_REVIEW_READY",
        "research_id": "FMDL4B-RSCH-600900.SH-test",
        "evidence_ids_json": '["FMDL4A-EV-600900.SH-test"]',
        "open_gates_json": '["ENTRY_VALUATION","PORTFOLIO_FIT","DIVIDEND_COVERAGE"]',
        "required_follow_on": "initiating-coverage",
    }


def research_row():
    return {
        "as_of": "2026-07-17",
        "business_model": "Owner and operator of large-scale hydropower assets.",
        "competitive_position": "Scarce river-basin hydropower portfolio with long asset lives.",
        "variant_perception": "Durable cash yield may be attractive only if valuation compensates for hydrology and policy risk.",
        "earnings_drivers_json": '["hydrology","generation","power pricing","interest expense","dividend policy"]',
        "catalysts_json": '["normal water inflows","generation recovery","continued cash distributions"]',
        "risks_json": '["weak hydrology","power policy","leverage","valuation"]',
        "prove_kill_checks_json": '["generation and utilization hours","operating cash flow versus dividends","net debt and interest burden","realized power price","dividend coverage"]',
    }


def test_feedback_ids_include_symbol_and_global():
    assert core.feedback_ids_for_symbol("600900.SH", cfg()) == ["FMDL4D-FB-001", "FMDL4D-FB-005"]


def test_threshold_cash_flow_is_quality_of_cash():
    prove, kill, category = core.threshold_condition("operating cash flow versus dividends")
    assert category == "CASH_QUALITY"
    assert "covers" in prove
    assert "weak" in kill


def test_catalyst_rows_are_deterministic():
    first = core.build_catalyst_rows(queue_row(), research_row(), cfg())
    second = core.build_catalyst_rows(queue_row(), research_row(), cfg())
    assert first == second
    assert len(first) == 3
    assert all(row["trade_authority"] == "NONE" for row in first)


def test_thesis_record_is_valid_and_not_decision_grade():
    catalysts = core.build_catalyst_rows(queue_row(), research_row(), cfg())
    prove_kill = core.build_prove_kill_rows(queue_row(), research_row(), cfg())
    record = core.build_thesis_record(queue_row(), research_row(), catalysts, prove_kill, cfg())
    assert core.validate_thesis_record(record, cfg()) == []
    assert record["security_thesis_readiness"] == "NOT_DECISION_GRADE_PENDING_CURRENT_PRICE_AND_SCENARIO"
    assert record["return_attribution"]["status"] == "NOT_YET_OBSERVABLE_NO_POSITION"


def test_attribution_row_has_no_fabricated_returns():
    row = core.build_attribution_row(queue_row(), research_row(), cfg())
    assert row["exposure_status"] == "NO_POSITION"
    assert row["gross_return"] is None
    assert row["selection_attribution"] is None
    assert row["failure_classification"] == "NO_OBSERVATION"


def test_deterministic_zip_is_byte_identical(tmp_path: Path):
    source = tmp_path / "source"
    (source / "STATE_CURRENT").mkdir(parents=True)
    (source / "CORE_STATIC").mkdir(parents=True)
    (source / "STATE_CURRENT/a.csv").write_text("x\n1\n", encoding="utf-8")
    (source / "CORE_STATIC/b.json").write_text('{"b":1}\n', encoding="utf-8")
    first = tmp_path / "first.zip"
    second = tmp_path / "second.zip"
    core.deterministic_zip(source, first)
    core.deterministic_zip(source, second)
    assert core.sha256_file(first) == core.sha256_file(second)
    with zipfile.ZipFile(first) as archive:
        assert archive.namelist() == ["CORE_STATIC/b.json", "STATE_CURRENT/a.csv"]
