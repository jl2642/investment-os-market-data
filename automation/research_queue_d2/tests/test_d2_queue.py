from __future__ import annotations

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
