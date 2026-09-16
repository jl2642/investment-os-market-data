from __future__ import annotations

import json
import sys
import types
from datetime import datetime, timezone

from automation.research_queue_d2 import build_d2_queue as d2


def test_routed_objects_only_advance():
    d1 = {
        "research_objects": [
            {"security_id": "B", "d1_rank": 2, "d1_disposition": "HOLD_IN_D1"},
            {"security_id": "A", "d1_rank": 1, "d1_disposition": "ADVANCE_TO_D2_DEEP_RESEARCH"},
            {"security_id": "C", "d1_rank": 3, "d1_disposition": "ADVANCE_TO_D2_DEEP_RESEARCH_VALUATION_GATED"},
        ]
    }
    assert [row["security_id"] for row in d2.routed_objects(d1)] == ["A", "C"]


def test_canonical_hash_stable():
    assert d2.canonical_hash({"b": 2, "a": 1}) == d2.canonical_hash({"a": 1, "b": 2})


def test_baseline_sources_security_scoped():
    evidence = {"sources": [
        {"security_id": "A", "source_id": "1"},
        {"security_id": "B", "source_id": "2"},
    ]}
    assert [row["source_id"] for row in d2.baseline_sources(evidence, "A")] == ["1"]


def test_cninfo_discovery_retries_are_bounded(monkeypatch):
    calls = {"count": 0}

    def broken_cninfo(**_kwargs):
        calls["count"] += 1
        raise json.JSONDecodeError("bad upstream payload", "<html>", 0)

    monkeypatch.setitem(sys.modules, "akshare", types.SimpleNamespace(stock_zh_a_disclosure_report_cninfo=broken_cninfo))
    rows, error = d2.discover_cninfo("000001.SZ", start_date="2026-01-01", end_date="2026-09-15")
    assert rows == []
    assert calls["count"] == d2.CNINFO_MAX_ATTEMPTS == 2
    assert error == "CNINFO_DISCOVERY_FAILED:JSONDecodeError:ATTEMPTS_2"


def test_provider_incident_requires_batch_wide_identical_source_failure():
    errors = [
        {"provider": "CNINFO_VIA_AKSHARE", "security_id": sid, "error": "CNINFO_DISCOVERY_FAILED:JSONDecodeError:ATTEMPTS_2"}
        for sid in ["A", "B", "C"]
    ]
    incident = d2.provider_incident_summary(errors, 3)
    assert incident["active"] is True
    assert incident["scope"] == "BATCH_LEVEL"
    assert incident["classification"] == "PROVIDER_INTERFACE_OR_ACCESS_FAILURE"
    assert incident["semantic_fallback_allowed"] is True
    assert d2.provider_incident_summary(errors[:2], 3) == {"active": False}


def test_semantic_terminal_compatibility_uses_same_d1_state():
    d1 = {"state_id": "D1-X"}
    prior = {"source_d1_state_id": "D1-X"}
    previous = {"status": "D2_RESEARCH_COMPLETE"}
    assert d2.semantic_state_is_same_input(prior, previous, d1, "new-watermark") is True
    assert d2.semantic_state_is_same_input({"source_d1_state_id": "D1-OLD"}, previous, d1, "new-watermark") is False


def test_build_state_fail_closed_without_network(tmp_path, monkeypatch):
    d1_current = tmp_path / "D1.json"
    d1_current.write_text(
        '{"state_id":"D1-X","research_objects":[{"security_id":"000001.SZ","security_name":"X","d1_rank":1,"d1_disposition":"ADVANCE_TO_D2_DEEP_RESEARCH","d2_questions":["q"],"first_rejection":"kill"}]}',
        encoding="utf-8",
    )
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "RESEARCH_QUEUE_D1_EVIDENCE_1.json").write_text(
        '{"sources":[{"security_id":"000001.SZ","source_id":"s1"}]}',
        encoding="utf-8",
    )

    monkeypatch.setattr(d2, "D1_CURRENT", d1_current)
    monkeypatch.setattr(d2, "D1_EVIDENCE_DIR", evidence_dir)
    monkeypatch.setattr(d2, "D2_CURRENT", tmp_path / "D2.json")
    monkeypatch.setattr(d2, "D2_LIVENESS", tmp_path / "LIVE.json")
    monkeypatch.setattr(d2, "D2_EVIDENCE_DIR", tmp_path / "d2e")

    state, liveness, evidence_run = d2.build_state(
        discover_primary_sources=False,
        now=datetime(2026, 8, 13, 1, 0, tzinfo=timezone.utc),
    )
    assert state["summary"]["pending_count"] == 1
    assert state["summary"]["manual_trigger_required"] is False
    assert state["queue"][0]["status"] == "PENDING_AUTO_RESEARCH"
    assert state["controls"]["orders"] == 0
    assert liveness["manual_trigger_required"] is False
    assert evidence_run["policy"]["semantic_completion_prohibited"] is True


def test_build_state_records_batch_provider_incident(tmp_path, monkeypatch):
    d1_current = tmp_path / "D1.json"
    d1_current.write_text(
        json.dumps({
            "state_id": "D1-X",
            "research_objects": [
                {"security_id": sid, "security_name": sid, "d1_rank": rank, "d1_disposition": "ADVANCE_TO_D2_FAST_TRIAGE", "d2_questions": ["q"], "first_rejection": "kill"}
                for rank, sid in enumerate(["A.SZ", "B.SZ", "C.SZ"], 1)
            ],
        }),
        encoding="utf-8",
    )
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "RESEARCH_QUEUE_D1_EVIDENCE_1.json").write_text('{"sources":[]}', encoding="utf-8")

    monkeypatch.setattr(d2, "D1_CURRENT", d1_current)
    monkeypatch.setattr(d2, "D1_EVIDENCE_DIR", evidence_dir)
    monkeypatch.setattr(d2, "D2_CURRENT", tmp_path / "D2.json")
    monkeypatch.setattr(d2, "D2_LIVENESS", tmp_path / "LIVE.json")
    monkeypatch.setattr(d2, "D2_EVIDENCE_DIR", tmp_path / "d2e")
    monkeypatch.setattr(
        d2,
        "discover_cninfo",
        lambda *_args, **_kwargs: ([], "CNINFO_DISCOVERY_FAILED:JSONDecodeError:ATTEMPTS_2"),
    )

    state, liveness, evidence_run = d2.build_state(
        discover_primary_sources=True,
        now=datetime(2026, 9, 15, 15, 28, tzinfo=timezone.utc),
    )
    assert state["summary"]["blocked_count"] == 3
    assert state["summary"]["provider_incident_active"] is True
    assert liveness["provider_incident"]["active"] is True
    assert evidence_run["provider_incident"]["affected_count"] == 3
    assert evidence_run["policy"]["semantic_fallback"].startswith("CHATGPT_NATIVE_D2")


def test_build_state_reopens_complete_research_when_underwriting_is_missing(tmp_path, monkeypatch):
    d1_current = tmp_path / "D1.json"
    d1_current.write_text(
        '{"state_id":"D1-X","research_objects":[{"security_id":"000001.SZ","security_name":"X","d1_rank":1,"d1_disposition":"ADVANCE_TO_D2_DEEP_RESEARCH","d2_questions":["q"],"first_rejection":"kill"}]}',
        encoding="utf-8",
    )
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "RESEARCH_QUEUE_D1_EVIDENCE_1.json").write_text('{"sources":[]}', encoding="utf-8")
    d2_current = tmp_path / "D2.json"
    d2_current.write_text(
        '{"source_d1_state_id":"D1-X","queue":[{"security_id":"000001.SZ","status":"D2_RESEARCH_COMPLETE","research_disposition":"HOLD_RESEARCH_COMPLETE_NO_DECISION","semantic_artifact":"artifact.json","primary_source_count":20}]}',
        encoding="utf-8",
    )

    monkeypatch.setattr(d2, "D1_CURRENT", d1_current)
    monkeypatch.setattr(d2, "D1_EVIDENCE_DIR", evidence_dir)
    monkeypatch.setattr(d2, "D2_CURRENT", d2_current)
    monkeypatch.setattr(d2, "D2_LIVENESS", tmp_path / "LIVE.json")
    monkeypatch.setattr(d2, "D2_EVIDENCE_DIR", tmp_path / "d2e")

    state, liveness, _ = d2.build_state(
        discover_primary_sources=False,
        now=datetime(2026, 8, 18, 1, 0, tzinfo=timezone.utc),
    )
    row = state["queue"][0]
    assert row["status"] == "D2_UNDERWRITING_PENDING"
    assert row["semantic_research_required"] is True
    assert row["semantic_artifact"] == "artifact.json"
    assert state["summary"]["pending_count"] == 1
    assert state["summary"]["completed_count"] == 0
    assert liveness["d2_pending_count"] == 1


def test_build_state_preserves_complete_research_with_decision_grade_underwriting(tmp_path, monkeypatch):
    d1_current = tmp_path / "D1.json"
    d1_current.write_text(
        '{"state_id":"D1-X","research_objects":[{"security_id":"000001.SZ","security_name":"X","d1_rank":1,"d1_disposition":"ADVANCE_TO_D2_DEEP_RESEARCH","d2_questions":["q"],"first_rejection":"kill"}]}',
        encoding="utf-8",
    )
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "RESEARCH_QUEUE_D1_EVIDENCE_1.json").write_text('{"sources":[]}', encoding="utf-8")
    d2_current = tmp_path / "D2.json"
    d2_current.write_text(
        '{"source_d1_state_id":"D1-X","queue":[{"security_id":"000001.SZ","status":"D2_RESEARCH_COMPLETE","research_disposition":"COMPLETE","semantic_artifact":"artifact.json","primary_source_count":20,"underwriting":{"current_price":10,"entry_price":11,"confidence":"HIGH","scenarios":[{"name":"BEAR","value":8,"probability":0.25},{"name":"BASE","value":13,"probability":0.5},{"name":"BULL","value":18,"probability":0.25}]}}]}',
        encoding="utf-8",
    )

    monkeypatch.setattr(d2, "D1_CURRENT", d1_current)
    monkeypatch.setattr(d2, "D1_EVIDENCE_DIR", evidence_dir)
    monkeypatch.setattr(d2, "D2_CURRENT", d2_current)
    monkeypatch.setattr(d2, "D2_LIVENESS", tmp_path / "LIVE.json")
    monkeypatch.setattr(d2, "D2_EVIDENCE_DIR", tmp_path / "d2e")

    state, liveness, _ = d2.build_state(
        discover_primary_sources=False,
        now=datetime(2026, 8, 18, 1, 0, tzinfo=timezone.utc),
    )
    row = state["queue"][0]
    assert row["status"] == "D2_RESEARCH_COMPLETE"
    assert row["semantic_research_required"] is False
    assert row["underwriting"]["entry_price"] == 11
    assert state["summary"]["pending_count"] == 0
    assert state["summary"]["completed_count"] == 1
    assert liveness["d2_pending_count"] == 0
