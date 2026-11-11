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


def test_semantic_terminal_compatibility_uses_same_d1_state_for_legacy_hold():
    d1 = {"state_id": "D1-X"}
    prior = {"source_d1_state_id": "D1-X"}
    previous = {"status": "D2_RESEARCH_HOLD_EVIDENCE_GAP"}
    assert d2.semantic_state_is_same_input(prior, previous, d1, "new-watermark") is True
    assert d2.semantic_state_is_same_input({"source_d1_state_id": "D1-OLD"}, previous, d1, "new-watermark") is False


def test_completed_semantic_reuse_ignores_daily_rank_and_market_signal_changes():
    previous = {
        "security_id": "300230.SZ",
        "archetype": "DEFENSIVE_STABILITY",
        "d1_disposition": "ADVANCE_TO_D2_FAST_TRIAGE",
        "d2_questions": ["q"],
        "first_rejection": "kill",
        "status": "D2_RESEARCH_COMPLETE",
        "underwriting": {
            "current_price": 4.3,
            "entry_price": 3.94,
            "confidence": "MEDIUM_HIGH",
            "scenarios": [{"name": "BEAR"}, {"name": "BASE"}, {"name": "BULL"}],
        },
    }
    obj = {
        "security_id": "300230.SZ",
        "archetype": "DEFENSIVE_STABILITY",
        "d1_disposition": "ADVANCE_TO_D2_FAST_TRIAGE",
        "d1_rank": 4,
        "d2_questions": ["q"],
        "first_rejection": "kill",
        "market_signal": {"return_20d": 0.02, "aggregate_score": 0.98},
    }
    assert d2.completed_semantic_reusable(previous, obj) is True


def test_completed_semantic_reuse_reopens_only_on_explicit_refresh_signal():
    previous = {
        "security_id": "600660.SH",
        "archetype": "QUALITY_GROWTH",
        "status": "D2_RESEARCH_COMPLETE",
        "underwriting": {
            "current_price": 54,
            "entry_price": 55,
            "confidence": "HIGH",
            "scenarios": [{"name": "BEAR"}, {"name": "BASE"}, {"name": "BULL"}],
        },
    }
    obj = {
        "security_id": "600660.SH",
        "archetype": "QUALITY_GROWTH",
        "d1_disposition": "LIFECYCLE_REUNDERWRITE_REQUIRED",
        "semantic_refresh_required": True,
    }
    assert d2.completed_semantic_reusable(previous, obj) is False


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


def test_build_state_recovers_completed_semantic_artifact_after_rolling_current_was_overwritten(tmp_path, monkeypatch):
    d1_current = tmp_path / "D1.json"
    d1_current.write_text(
        json.dumps({
            "state_id": "D1-NEW",
            "research_objects": [{
                "security_id": "300230.SZ",
                "security_name": "永利股份",
                "d1_rank": 4,
                "d1_disposition": "ADVANCE_TO_D2_FAST_TRIAGE",
                "archetype": "DEFENSIVE_STABILITY",
                "d2_questions": ["q"],
                "first_rejection": "kill",
                "market_signal": {"aggregate_score": 0.98},
            }],
        }),
        encoding="utf-8",
    )
    evidence_dir = tmp_path / "d1e"
    evidence_dir.mkdir()
    (evidence_dir / "RESEARCH_QUEUE_D1_EVIDENCE_1.json").write_text('{"sources":[]}', encoding="utf-8")

    d2_current = tmp_path / "D2.json"
    d2_current.write_text(
        json.dumps({
            "source_d1_state_id": "D1-NEW",
            "queue": [{
                "security_id": "300230.SZ",
                "status": "PRIMARY_EVIDENCE_DISCOVERED_SEMANTIC_RESEARCH_PENDING",
                "input_watermark": "rolling-daily-hash",
            }],
        }),
        encoding="utf-8",
    )

    d2e = tmp_path / "d2e"
    d2e.mkdir()
    (d2e / "D2_RESEARCH_300230_20260921_R1.json").write_text(
        json.dumps({
            "artifact_id": "D2_SEMANTIC_RESEARCH_20260921_R1_300230",
            "security_id": "300230.SZ",
            "security_name": "永利股份",
            "archetype": "DEFENSIVE_STABILITY",
            "status": "D2_RESEARCH_COMPLETE",
            "research_disposition": "BUY_BELOW_RESEARCH_COMPLETE",
            "first_rejection_test": "gate",
            "next_gate": "price_at_or_below_3_94",
            "evidence_gap": {"material": False, "manual_user_input_required": False},
            "sources": [{"title": "H1"}],
            "underwriting": {
                "current_price": 4.3,
                "entry_price": 3.94,
                "confidence": "MEDIUM_HIGH",
                "scenarios": [{"name": "BEAR"}, {"name": "BASE"}, {"name": "BULL"}],
            },
        }),
        encoding="utf-8",
    )

    monkeypatch.setattr(d2, "D1_CURRENT", d1_current)
    monkeypatch.setattr(d2, "D1_EVIDENCE_DIR", evidence_dir)
    monkeypatch.setattr(d2, "D2_CURRENT", d2_current)
    monkeypatch.setattr(d2, "D2_LIVENESS", tmp_path / "LIVE.json")
    monkeypatch.setattr(d2, "D2_EVIDENCE_DIR", d2e)

    state, liveness, _ = d2.build_state(
        discover_primary_sources=False,
        now=datetime(2026, 9, 22, 1, 0, tzinfo=timezone.utc),
    )
    row = state["queue"][0]
    assert row["status"] == "D2_RESEARCH_COMPLETE"
    assert row["semantic_research_required"] is False
    assert row["semantic_reuse_source"] == "DURABLE_SEMANTIC_ARTIFACT"
    assert row["research_disposition"] == "BUY_BELOW_RESEARCH_COMPLETE"
    assert state["summary"]["pending_count"] == 0
    assert state["summary"]["reused_completed_count"] == 1
    assert liveness["d2_pending_count"] == 0
    assert liveness["d2_reused_completed_count"] == 1


def test_semantic_gate_requires_reconciled_underwriting_economics():
    from automation.research_queue_d2 import validate_d2_queue as gate

    good = {"underwriting": {
        "current_price": 10.0,
        "price_as_of": "2026-11-09",
        "entry_price": 8.0,
        "confidence": "MEDIUM",
        "normalized_earnings_basis": "Reported 2026Q3 earnings adjusted for one-offs.",
        "action": "WATCH",
        "kill_thesis": ["Cash conversion fails"],
        "catalysts": ["Cash conversion improves"],
        "scenarios": [
            {"name": "BEAR", "value_per_share": 5.0, "probability": 0.25},
            {"name": "BASE", "value_per_share": 10.0, "probability": 0.50},
            {"name": "BULL", "value_per_share": 15.0, "probability": 0.25},
        ],
        "probability_weighted_value": 10.0,
        "expected_return": 0.0,
    }}
    assert gate.underwriting_complete(good)
    import copy
    bad_probability = copy.deepcopy(good)
    bad_probability["underwriting"]["scenarios"][0]["probability"] = 0.15
    assert not gate.underwriting_complete(bad_probability)
    bad_valuation = copy.deepcopy(good)
    bad_valuation["underwriting"]["probability_weighted_value"] = 15.0
    assert not gate.underwriting_complete(bad_valuation)
    missing_return = copy.deepcopy(good)
    del missing_return["underwriting"]["expected_return"]
    assert not gate.underwriting_complete(missing_return)
    bad_action = copy.deepcopy(good)
    bad_action["underwriting"]["action"] = "BUY_WITHOUT_UNDERWRITING"
    assert not gate.underwriting_complete(bad_action)
    fake_labels_only = {"underwriting": {
        "current_price": 10, "entry_price": 8, "confidence": "HIGH",
        "scenarios": [{"name": name} for name in ("BEAR", "BASE", "BULL")]
    }}
    assert not gate.underwriting_complete(fake_labels_only)


def test_evidence_ready_pending_d2_survives_d1_rerank_with_fresh_slot(tmp_path, monkeypatch):
    d1 = tmp_path / "D1.json"
    d1.write_text(json.dumps({
        "state_id": "D1-NEW",
        "research_objects": [
            {"security_id": s, "security_name": s, "d1_rank": idx,
             "d1_disposition": "ADVANCE_TO_D2_FAST_TRIAGE", "d2_questions": ["verify"],
             "first_rejection": "reject weak earnings"}
            for idx, s in enumerate(["NEW1.SZ", "NEW2.SZ", "NEW3.SZ"], 1)
        ],
    }), encoding="utf-8")
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "RESEARCH_QUEUE_D1_EVIDENCE_1.json").write_text(
        '{"sources":[]}', encoding="utf-8"
    )
    prior = {
        "source_d1_state_id": "D1-OLD",
        "queue": [
            {"security_id": symbol, "security_name": symbol, "status":
             "PRIMARY_EVIDENCE_DISCOVERED_SEMANTIC_RESEARCH_PENDING",
             "semantic_research_required": True, "primary_source_count": 20,
             "last_attempt_at": timestamp, "d2_questions": ["verify"],
             "candidate_membership_mutation_authorized": False,
             "real_account_mutation_authorized": False,
             "simulation_mutation_authorized": False,
             "decision_mutation_authorized": False,
             "order_generation_authorized": False, "trade_authority": "NONE"}
            for symbol, timestamp in [
                ("OLD1.SH", "2026-11-08T12:00:00Z"),
                ("OLD2.SZ", "2026-11-09T12:00:00Z"),
                ("OLD3.SH", "2026-11-10T12:00:00Z"),
            ]
        ],
    }
    existing = tmp_path / "D2.json"
    existing.write_text(json.dumps(prior), encoding="utf-8")
    monkeypatch.setattr(d2, "D1_CURRENT", d1)
    monkeypatch.setattr(d2, "D1_EVIDENCE_DIR", evidence_dir)
    monkeypatch.setattr(d2, "D2_CURRENT", existing)
    monkeypatch.setattr(d2, "D2_LIVENESS", tmp_path / "LIVE.json")
    monkeypatch.setattr(d2, "D2_EVIDENCE_DIR", tmp_path / "d2e")
    state, live, _ = d2.build_state(
        discover_primary_sources=False,
        now=datetime(2026, 11, 10, 13, 0, tzinfo=timezone.utc),
    )
    assert [x["security_id"] for x in state["queue"]] == [
        "OLD1.SH", "OLD2.SZ", "NEW1.SZ"
    ]
    assert state["source_d1_state_id"] == "D1-NEW"
    assert state["queue"][0]["carried_forward_from_d1_state_id"] == "D1-OLD"
    assert state["queue"][0]["primary_source_count"] == 0
    assert state["queue"][0]["source_inventory_status"] == "MISSING_DURABLE_DISCOVERY_RECORDS"
    assert state["queue"][0]["status"] == "PENDING_AUTO_RESEARCH"
    assert state["summary"]["pending_count"] == 3
    assert live["d2_pending_count"] == 3
    assert state["controls"]["orders"] == 0


def test_pending_backlog_without_evidence_not_carried_forever(tmp_path, monkeypatch):
    d1 = tmp_path / "D1.json"
    d1.write_text('{"state_id":"D1-N","research_objects":[]}', encoding="utf-8")
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "RESEARCH_QUEUE_D1_EVIDENCE_1.json").write_text(
        '{"sources":[]}', encoding="utf-8"
    )
    old = tmp_path / "D2.json"
    old.write_text(json.dumps({"source_d1_state_id": "D1-OLD", "queue": [
        {"security_id":"OLD.SZ", "status":"AUTO_RESEARCH_BLOCKED_PRIMARY_SOURCE_DISCOVERY",
         "semantic_research_required":True, "primary_source_count":0}
    ]}), encoding="utf-8")
    monkeypatch.setattr(d2, "D1_CURRENT", d1)
    monkeypatch.setattr(d2, "D1_EVIDENCE_DIR", evidence_dir)
    monkeypatch.setattr(d2, "D2_CURRENT", old)
    monkeypatch.setattr(d2, "D2_LIVENESS", tmp_path / "LIVE.json")
    monkeypatch.setattr(d2, "D2_EVIDENCE_DIR", tmp_path / "d2e")
    state, live, _ = d2.build_state(
        discover_primary_sources=False,
        now=datetime(2026, 11, 10, 13, 0, tzinfo=timezone.utc),
    )
    assert state["queue"] == []
    assert live["d2_pending_count"] == 0



def test_old_pending_without_durable_source_rows_is_rediscovered(tmp_path, monkeypatch):
    d1 = tmp_path / "D1.json"
    d1.write_text(json.dumps({
        "state_id": "D1-NEW",
        "research_objects": [
            {"security_id": s, "security_name": s, "d1_rank": idx,
             "d1_disposition": "ADVANCE_TO_D2_FAST_TRIAGE", "d2_questions": ["verify"],
             "first_rejection": "reject weak earnings"}
            for idx, s in enumerate(["NEW1.SZ", "NEW2.SZ", "NEW3.SZ"], 1)
        ],
    }), encoding="utf-8")
    d1e = tmp_path / "d1e"
    d1e.mkdir()
    (d1e / "RESEARCH_QUEUE_D1_EVIDENCE_1.json").write_text('{"sources":[]}', encoding="utf-8")
    prior = {
        "source_d1_state_id": "D1-OLD",
        "queue": [
            {"security_id": sid, "security_name": sid,
             "status": "PRIMARY_EVIDENCE_DISCOVERED_SEMANTIC_RESEARCH_PENDING",
             "semantic_research_required": True, "primary_source_count": 20,
             "attempt_count": 1, "last_attempt_at": "2026-11-10T06:22:17Z",
             "d2_questions": ["verify"], "trade_authority": "NONE"}
            for sid in ["OLD1.SZ", "OLD2.SZ"]
        ],
    }
    d2_current = tmp_path / "D2.json"
    d2_current.write_text(json.dumps(prior), encoding="utf-8")
    d2e = tmp_path / "d2e"
    d2e.mkdir()
    calls = []

    def discover(security_id, **_kwargs):
        calls.append(security_id)
        return [
            {"primary_source": True, "security_id": security_id,
             "source_type": "CNINFO_DISCLOSURE", "title": f"report-{i}",
             "publication_time": "2026-10-30", "url": f"https://cninfo.example/{security_id}/{i}"}
            for i in (1, 2)
        ], None

    monkeypatch.setattr(d2, "D1_CURRENT", d1)
    monkeypatch.setattr(d2, "D1_EVIDENCE_DIR", d1e)
    monkeypatch.setattr(d2, "D2_CURRENT", d2_current)
    monkeypatch.setattr(d2, "D2_LIVENESS", tmp_path / "LIVE.json")
    monkeypatch.setattr(d2, "D2_EVIDENCE_DIR", d2e)
    monkeypatch.setattr(d2, "discover_cninfo", discover)

    state, _live, evidence_run = d2.build_state(
        discover_primary_sources=True,
        now=datetime(2026, 11, 11, 1, 0, tzinfo=timezone.utc),
    )
    assert [row["security_id"] for row in state["queue"]] == ["OLD1.SZ", "OLD2.SZ", "NEW1.SZ"]
    assert calls == ["OLD1.SZ", "OLD2.SZ", "NEW1.SZ"]
    for row in state["queue"][:2]:
        assert row["primary_source_count"] == 2
        assert row["source_inventory_status"] == "DISCOVERY_RECORDS_WRITTEN_THIS_RUN"
        assert row["status"] == "PRIMARY_EVIDENCE_DISCOVERED_SEMANTIC_RESEARCH_PENDING"
    assert len(evidence_run["primary_sources"]) == 6
    assert evidence_run["policy"]["discovery_records_are_metadata_only"] is True
    assert evidence_run["policy"]["document_body_retrieval"] == "NOT_PERFORMED_BY_THIS_DISCOVERY_STEP"


def test_old_pending_uses_durable_source_rows_instead_of_stale_count(tmp_path, monkeypatch):
    d1 = tmp_path / "D1.json"
    d1.write_text(json.dumps({
        "state_id": "D1-NEW",
        "research_objects": [
            {"security_id": s, "security_name": s, "d1_rank": idx,
             "d1_disposition": "ADVANCE_TO_D2_FAST_TRIAGE", "d2_questions": ["verify"],
             "first_rejection": "reject weak earnings"}
            for idx, s in enumerate(["NEW1.SZ", "NEW2.SZ", "NEW3.SZ"], 1)
        ],
    }), encoding="utf-8")
    d1e = tmp_path / "d1e"
    d1e.mkdir()
    (d1e / "RESEARCH_QUEUE_D1_EVIDENCE_1.json").write_text('{"sources":[]}', encoding="utf-8")
    prior = {
        "source_d1_state_id": "D1-OLD",
        "queue": [{
            "security_id": "OLD1.SZ", "security_name": "OLD1.SZ",
            "status": "AUTO_RESEARCH_BLOCKED_PRIMARY_SOURCE_DISCOVERY",
            "semantic_research_required": True, "primary_source_count": 20,
            "attempt_count": 3, "last_attempt_at": "2026-11-10T06:22:17Z",
            "d2_questions": ["verify"], "trade_authority": "NONE"
        }],
    }
    d2_current = tmp_path / "D2.json"
    d2_current.write_text(json.dumps(prior), encoding="utf-8")
    d2e = tmp_path / "d2e"
    d2e.mkdir()
    sources = [
        {"primary_source": True, "security_id": "OLD1.SZ",
         "source_type": "CNINFO_DISCLOSURE", "title": f"report-{i}",
         "publication_time": "2026-10-30", "url": f"https://cninfo.example/OLD1.SZ/{i}"}
        for i in (1, 2)
    ]
    sources.extend([
        {
            "primary_source": True, "security_id": "OLD1.SZ",
            "source_type": "CNINFO_DISCLOSURE", "title": "invalid-url",
            "publication_time": "2026-10-30", "url": "not-a-url"
        },
        {
            "security_id": "OLD1.SZ", "source_type": "CNINFO_DISCLOSURE",
            "title": "missing-primary-flag", "publication_time": "2026-10-30",
            "url": "https://cninfo.example/OLD1.SZ/missing-flag"
        },
        {
            "primary_source": False, "security_id": "OLD1.SZ",
            "source_type": "CNINFO_DISCLOSURE", "title": "non-primary",
            "publication_time": "2026-10-30",
            "url": "https://cninfo.example/OLD1.SZ/non-primary"
        }
    ])
    (d2e / "RESEARCH_QUEUE_D2_EVIDENCE_20261110T000000Z.json").write_text(
        json.dumps({"captured_at": "2026-11-10T00:00:00Z", "primary_sources": sources}),
        encoding="utf-8",
    )
    calls = []

    def discover(security_id, **_kwargs):
        calls.append(security_id)
        return [], "CNINFO_DISCOVERY_EMPTY"

    monkeypatch.setattr(d2, "D1_CURRENT", d1)
    monkeypatch.setattr(d2, "D1_EVIDENCE_DIR", d1e)
    monkeypatch.setattr(d2, "D2_CURRENT", d2_current)
    monkeypatch.setattr(d2, "D2_LIVENESS", tmp_path / "LIVE.json")
    monkeypatch.setattr(d2, "D2_EVIDENCE_DIR", d2e)
    monkeypatch.setattr(d2, "discover_cninfo", discover)

    state, _live, _evidence_run = d2.build_state(
        discover_primary_sources=True,
        now=datetime(2026, 11, 11, 1, 0, tzinfo=timezone.utc),
    )
    old = state["queue"][0]
    assert old["security_id"] == "OLD1.SZ"
    assert old["primary_source_count"] == 2
    assert old["source_inventory_status"] == "DURABLE_DISCOVERY_RECORDS_PRESENT"
    assert old["status"] == "PRIMARY_EVIDENCE_DISCOVERED_SEMANTIC_RESEARCH_PENDING"
    assert old["source_inventory_evidence_files"] == [
        str((d2e / "RESEARCH_QUEUE_D2_EVIDENCE_20261110T000000Z.json"))
    ]
    assert "OLD1.SZ" not in calls



def test_consumer_restores_exact_published_d2_evidence_before_rebuild():
    workflow = (
        d2.ROOT / ".github/workflows/research-queue-d2-auto-consumer.yml"
    ).read_text(encoding="utf-8")
    assert 'git restore --source="$D2_COMMIT" --worktree investment_os_runtime/40_EVIDENCE_AND_LINEAGE/RESEARCH_QUEUE_D2/' in workflow
    assert 'git show "$D2_COMMIT":investment_os_runtime/30_STATE_CURRENT/30_RESEARCH/RESEARCH_QUEUE_D2_CURRENT.json' in workflow



def test_unresolved_old_pending_items_are_preserved_and_retried(tmp_path, monkeypatch):
    d1 = tmp_path / "D1.json"
    d1.write_text(json.dumps({
        "state_id": "D1-NEW",
        "research_objects": [
            {"security_id": s, "security_name": s, "d1_rank": idx,
             "d1_disposition": "ADVANCE_TO_D2_FAST_TRIAGE", "d2_questions": ["verify"],
             "first_rejection": "reject weak earnings"}
            for idx, s in enumerate(["NEW1.SZ", "NEW2.SZ", "NEW3.SZ"], 1)
        ],
    }), encoding="utf-8")
    d1e = tmp_path / "d1e"
    d1e.mkdir()
    (d1e / "RESEARCH_QUEUE_D1_EVIDENCE_1.json").write_text(
        '{"sources":[]}', encoding="utf-8"
    )
    prior = {
        "source_d1_state_id": "D1-OLD",
        "queue": [
            {
                "security_id": "OLD_PENDING.SZ", "security_name": "OLD_PENDING",
                "status": "PENDING_AUTO_RESEARCH", "semantic_research_required": True,
                "primary_source_count": 0, "attempt_count": 1,
                "last_attempt_at": "2026-11-08T12:00:00Z",
                "d2_questions": ["verify"], "trade_authority": "NONE",
            },
            {
                "security_id": "OLD_BLOCKED.SZ", "security_name": "OLD_BLOCKED",
                "status": "AUTO_RESEARCH_BLOCKED_PRIMARY_SOURCE_DISCOVERY",
                "semantic_research_required": True, "primary_source_count": 0,
                "attempt_count": 2, "last_attempt_at": "2026-11-09T12:00:00Z",
                "d2_questions": ["verify"], "trade_authority": "NONE",
            },
            {
                "security_id": "OLD_EXHAUSTED.SZ", "security_name": "OLD_EXHAUSTED",
                "status": "AUTO_RESEARCH_BLOCKED_PRIMARY_SOURCE_DISCOVERY",
                "semantic_research_required": True, "primary_source_count": 0,
                "attempt_count": 3, "last_attempt_at": "2026-11-07T12:00:00Z",
                "d2_questions": ["verify"], "trade_authority": "NONE",
            },
        ],
    }
    d2_current = tmp_path / "D2.json"
    d2_current.write_text(json.dumps(prior), encoding="utf-8")
    d2e = tmp_path / "d2e"
    d2e.mkdir()
    calls = []

    def discover(security_id, **_kwargs):
        calls.append(security_id)
        return [], "CNINFO_DISCOVERY_EMPTY"

    monkeypatch.setattr(d2, "D1_CURRENT", d1)
    monkeypatch.setattr(d2, "D1_EVIDENCE_DIR", d1e)
    monkeypatch.setattr(d2, "D2_CURRENT", d2_current)
    monkeypatch.setattr(d2, "D2_LIVENESS", tmp_path / "LIVE.json")
    monkeypatch.setattr(d2, "D2_EVIDENCE_DIR", d2e)
    monkeypatch.setattr(d2, "discover_cninfo", discover)

    state, _live, evidence_run = d2.build_state(
        discover_primary_sources=True,
        now=datetime(2026, 11, 11, 1, 0, tzinfo=timezone.utc),
    )
    queued = {row["security_id"]: row for row in state["queue"]}
    assert "OLD_PENDING.SZ" in queued
    assert "OLD_BLOCKED.SZ" in queued
    assert "OLD_EXHAUSTED.SZ" not in queued
    assert queued["OLD_PENDING.SZ"]["status"] == "AUTO_RESEARCH_BLOCKED_PRIMARY_SOURCE_DISCOVERY"
    assert queued["OLD_BLOCKED.SZ"]["status"] == "AUTO_RESEARCH_BLOCKED_PRIMARY_SOURCE_DISCOVERY"
    assert queued["OLD_PENDING.SZ"]["attempt_count"] == 2
    assert queued["OLD_BLOCKED.SZ"]["attempt_count"] == 3
    assert calls == ["OLD_PENDING.SZ", "OLD_BLOCKED.SZ", "NEW1.SZ"]
    assert len(evidence_run["discovery_errors"]) == 3
    assert state["summary"]["pending_count"] == 3
    assert state["controls"]["orders"] == 0



def test_consumer_runs_after_its_code_or_workflow_is_merged_to_main():
    workflow = (
        d2.ROOT / ".github/workflows/research-queue-d2-auto-consumer.yml"
    ).read_text(encoding="utf-8")
    push_block = workflow.split("  push:", 1)[1].split("  workflow_dispatch:", 1)[0]
    assert '"automation/research_queue_d2/**"' in push_block
    assert '".github/workflows/research-queue-d2-auto-consumer.yml"' in push_block
    fetch_step = workflow.split(
        "- name: Fetch S2 rolling D1 Current and prior D2 authority", 1
    )[1].split("      - name:", 1)[0]
    assert "if: github.event_name != 'pull_request'" in fetch_step
