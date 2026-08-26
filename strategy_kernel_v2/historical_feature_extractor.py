"""Strategy Kernel v2 Phase 3C point-in-time historical feature extraction.

Research/shadow-only. The extractor reads only Phase 3A selected evidence records at
their exact registered commit/path. Extraction is model-neutral: it preserves explicit
historical fields and provenance, but does not invent probabilities, scenario values,
confidence scores, execution-friction scores, target weights, or user decisions.
"""
from __future__ import annotations

from copy import deepcopy
import csv
import io
import json
from pathlib import Path
import re
import subprocess
from typing import Any, Callable, Mapping

_SHA40 = re.compile(r"^[0-9a-f]{40}$")

LEGACY_PRIORITY = {
    "FORMAL_PLAN": 100,
    "CONDITIONAL_PORTFOLIO_DECISION": 95,
    "REAL_ACCOUNT_ACTION": 90,
    "RESEARCH_DISPOSITION": 70,
    "CANDIDATE_CORE_REVIEW": 60,
    "CANDIDATE_ARCHIVE_ACTION": 50,
}

FALSE_CONTROLS = {
    "hindsight_allowed": False,
    "model_specific_evidence_fetch_allowed": False,
    "retrospective_probability_backfill_allowed": False,
    "retrospective_scenario_backfill_allowed": False,
    "subjective_feature_fill_allowed": False,
    "candidate_mutation_allowed": False,
    "real_position_mutation_allowed": False,
    "simulation_position_mutation_allowed": False,
    "target_portfolio_writeback_allowed": False,
    "user_decision_generation_allowed": False,
    "investment_recommendation_generation_allowed": False,
    "order_authorized": False,
    "orders": 0,
    "trade_authority": "NONE",
}


def _validate_registered_source(record: Mapping[str, Any]) -> tuple[str, str]:
    source = record.get("source")
    if not isinstance(source, Mapping):
        raise ValueError("REGISTERED_SOURCE_REQUIRED")
    commit = str(source.get("commit_sha", ""))
    path = str(source.get("path", ""))
    if not _SHA40.fullmatch(commit):
        raise ValueError("REGISTERED_COMMIT_SHA40_REQUIRED")
    pure = Path(path)
    if not path or pure.is_absolute() or ".." in pure.parts:
        raise ValueError("REGISTERED_PATH_MUST_BE_REPOSITORY_RELATIVE")
    if source.get("provenance_status") != "CANONICAL_MAIN":
        raise ValueError("PHASE3C_REQUIRES_CANONICAL_MAIN_PROVENANCE")
    return commit, path


def git_show_registered_source(
    record: Mapping[str, Any],
    *,
    repo_root: str | Path = ".",
) -> Any:
    """Load one exact Phase 3A registered historical source with git-show."""
    commit, path = _validate_registered_source(record)
    completed = subprocess.run(
        ["git", "show", f"{commit}:{path}"],
        cwd=str(repo_root),
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise FileNotFoundError(
            f"REGISTERED_SOURCE_UNREADABLE:{record.get('evidence_id')}:{commit}:{path}"
        )
    raw = completed.stdout
    suffix = Path(path).suffix.lower()
    if suffix == ".json":
        return json.loads(raw)
    if suffix == ".csv":
        return list(csv.DictReader(io.StringIO(raw)))
    return raw


def _security_code(security_id: str) -> str:
    if security_id.startswith("HKEX:"):
        return security_id.split(":", 1)[1]
    return security_id.split(".", 1)[0]


def _row_matches_security(row: Mapping[str, Any], security_id: str) -> bool:
    code = _security_code(security_id)
    direct = row.get("security_id")
    if direct == security_id:
        return True
    for key in ("security_code", "stock_code", "stock_code_5d", "code", "object_id"):
        value = row.get(key)
        if value is not None and str(value).lstrip("0") == code.lstrip("0"):
            return True
    return False


def _ensure_row(rows: dict[str, dict[str, Any]], security_id: str) -> dict[str, Any]:
    return rows.setdefault(
        security_id,
        {
            "security_id": security_id,
            "security_name": security_id,
            "provenance_evidence_ids": [],
            "feature_provenance": {},
            "features": {},
            "legacy_disposition": None,
            "legacy_disposition_source": None,
            "legacy_disposition_priority": -1,
            "legacy_reason_codes": [],
        },
    )


def _add_provenance(row: dict[str, Any], evidence_id: str) -> None:
    if evidence_id not in row["provenance_evidence_ids"]:
        row["provenance_evidence_ids"].append(evidence_id)


def _set_feature(
    row: dict[str, Any],
    key: str,
    value: Any,
    evidence_id: str,
) -> None:
    if value is None:
        return
    row["features"][key] = deepcopy(value)
    row["feature_provenance"][key] = [evidence_id]
    _add_provenance(row, evidence_id)


def _set_legacy(
    row: dict[str, Any],
    *,
    disposition: Any,
    source_kind: str,
    evidence_id: str,
    reason_codes: list[str] | None = None,
) -> None:
    if not isinstance(disposition, str) or not disposition:
        return
    priority = LEGACY_PRIORITY[source_kind]
    if priority < row["legacy_disposition_priority"]:
        return
    row["legacy_disposition"] = disposition
    row["legacy_disposition_source"] = source_kind
    row["legacy_disposition_priority"] = priority
    row["legacy_reason_codes"] = list(reason_codes or [source_kind])
    _add_provenance(row, evidence_id)
    row["feature_provenance"]["legacy_disposition"] = [evidence_id]


def _extract_candidate_state(
    data: Mapping[str, Any],
    *,
    evidence_id: str,
    opportunity_ids: set[str],
    rows: dict[str, dict[str, Any]],
) -> None:
    for member in data.get("candidate_core_members", []):
        if not isinstance(member, Mapping):
            continue
        for sid in opportunity_ids:
            if not _row_matches_security(member, sid):
                continue
            row = _ensure_row(rows, sid)
            row["security_name"] = member.get("security_name", row["security_name"])
            _set_feature(row, "candidate_buy_signal", member.get("buy_signal"), evidence_id)
            _set_feature(row, "candidate_research_gap_count", member.get("research_gap_count"), evidence_id)
            _set_feature(row, "candidate_valuation_status", member.get("valuation_status"), evidence_id)
            _set_feature(row, "candidate_strategy_sleeve", member.get("strategy_sleeve"), evidence_id)
            _set_legacy(
                row,
                disposition=member.get("core20_review_disposition"),
                source_kind="CANDIDATE_CORE_REVIEW",
                evidence_id=evidence_id,
                reason_codes=[
                    "CANDIDATE_CORE_REVIEW",
                    str(member.get("buy_signal", "UNKNOWN")),
                ],
            )

    for archived in data.get("historical_core20_archive", []):
        if not isinstance(archived, Mapping):
            continue
        for sid in opportunity_ids:
            if not _row_matches_security(archived, sid):
                continue
            row = _ensure_row(rows, sid)
            row["security_name"] = archived.get("stock_name", row["security_name"])
            for key in (
                "buy_signal",
                "current_sim_pnl_pct",
                "legacy_60d_return_pct_20260624",
                "proxy_return_20260624_to_20260710_pct",
                "evidence_score",
                "quality_score",
                "portfolio_fit_score",
                "risk_penalty",
                "race_confidence",
                "race_gate",
                "valuation_score_coarse",
            ):
                _set_feature(row, f"candidate_archive_{key}", archived.get(key), evidence_id)
            _set_legacy(
                row,
                disposition=archived.get("current_action") or archived.get("b2_decision"),
                source_kind="CANDIDATE_ARCHIVE_ACTION",
                evidence_id=evidence_id,
                reason_codes=["CANDIDATE_ARCHIVE_ACTION"],
            )


def _extract_real_account(
    data: Mapping[str, Any],
    *,
    evidence_id: str,
    opportunity_ids: set[str],
    rows: dict[str, dict[str, Any]],
) -> None:
    total_assets = (data.get("summary") or {}).get("consolidated_assets_including_bank_cash")
    holdings = data.get("holdings", [])
    for holding in holdings if isinstance(holdings, list) else []:
        if not isinstance(holding, Mapping):
            continue
        for sid in opportunity_ids:
            if not _row_matches_security(holding, sid):
                continue
            row = _ensure_row(rows, sid)
            row["security_name"] = holding.get("holding_name", row["security_name"])
            _set_feature(row, "real_market_value", holding.get("market_value"), evidence_id)
            _set_feature(row, "real_quantity", holding.get("quantity_or_shares"), evidence_id)
            _set_feature(row, "real_holding_pnl_pct", holding.get("holding_pnl_pct"), evidence_id)
            if total_assets and holding.get("market_value") is not None:
                _set_feature(
                    row,
                    "real_account_weight_mechanical",
                    float(holding["market_value"]) / float(total_assets),
                    evidence_id,
                )

    actions = data.get("historical_action_records", [])
    for action in actions if isinstance(actions, list) else []:
        if not isinstance(action, Mapping):
            continue
        for sid in opportunity_ids:
            if not _row_matches_security(action, sid):
                continue
            row = _ensure_row(rows, sid)
            row["security_name"] = action.get("object_name", row["security_name"])
            for key in ("current_weight", "execution_status", "permission", "constraints", "reason"):
                _set_feature(row, f"real_action_{key}", action.get(key), evidence_id)
            _set_legacy(
                row,
                disposition=action.get("decision"),
                source_kind="REAL_ACCOUNT_ACTION",
                evidence_id=evidence_id,
                reason_codes=["REAL_ACCOUNT_HISTORICAL_ACTION"],
            )


def _extract_core2_research(
    data: Mapping[str, Any],
    *,
    evidence_id: str,
    opportunity_ids: set[str],
    rows: dict[str, dict[str, Any]],
) -> None:
    records = data.get("records", [])
    for record in records if isinstance(records, list) else []:
        if not isinstance(record, Mapping):
            continue
        sid = record.get("security_id")
        if sid not in opportunity_ids:
            continue
        row = _ensure_row(rows, sid)
        row["security_name"] = record.get("security_name", row["security_name"])
        _set_feature(row, "core2_market_facts", record.get("current_market_facts"), evidence_id)
        _set_feature(row, "core2_research_grade", record.get("research_grade"), evidence_id)
        _set_feature(
            row,
            "core2_decision_grade_limitation_count",
            len(record.get("decision_grade_limitations", [])),
            evidence_id,
        )
        _set_feature(row, "core2_ready_for_user_decision", record.get("ready_for_user_decision"), evidence_id)


def _extract_wp5_p0(
    data: Mapping[str, Any],
    *,
    evidence_id: str,
    opportunity_ids: set[str],
    rows: dict[str, dict[str, Any]],
) -> None:
    objects = data.get("research_objects", {})
    if not isinstance(objects, Mapping):
        return
    for sid in opportunity_ids:
        obj = objects.get(sid)
        if not isinstance(obj, Mapping):
            continue
        row = _ensure_row(rows, sid)
        row["security_name"] = obj.get("security_name", row["security_name"])
        decision = obj.get("conditional_portfolio_decision") or {}
        scenarios = obj.get("driver_based_scenarios") or {}
        source_quality = obj.get("source_quality") or {}
        implementation = obj.get("implementation_readiness") or {}
        _set_feature(row, "wp5_base_case_expected_return", decision.get("base_case_expected_return"), evidence_id)
        _set_feature(row, "wp5_current_weight", decision.get("current_weight"), evidence_id)
        _set_feature(row, "wp5_unweighted_scenarios", scenarios.get("cases"), evidence_id)
        _set_feature(row, "wp5_completed_close_mark", scenarios.get("completed_close_mark"), evidence_id)
        _set_feature(row, "wp5_source_count", source_quality.get("source_count"), evidence_id)
        _set_feature(row, "wp5_all_primary_documents", source_quality.get("all_primary_documents"), evidence_id)
        _set_feature(row, "wp5_broker_verified", implementation.get("broker_verified"), evidence_id)
        _set_feature(row, "wp5_implementation_ready", implementation.get("implementation_ready"), evidence_id)
        _set_legacy(
            row,
            disposition=decision.get("action_posture") or decision.get("research_judgment"),
            source_kind="CONDITIONAL_PORTFOLIO_DECISION",
            evidence_id=evidence_id,
            reason_codes=[
                "CONDITIONAL_PORTFOLIO_DECISION",
                "BASE_HURDLE_" + ("PASS" if decision.get("base_case_hurdle_passed") else "NOT_PASS"),
            ],
        )


def _extract_00669_decision(
    data: Mapping[str, Any],
    *,
    evidence_id: str,
    opportunity_ids: set[str],
    rows: dict[str, dict[str, Any]],
) -> None:
    sid = data.get("security_id")
    if sid not in opportunity_ids:
        return
    row = _ensure_row(rows, sid)
    row["security_name"] = data.get("security_name", row["security_name"])
    lineage = data.get("source_lineage") or {}
    valuation = data.get("valuation_review") or {}
    sizing = data.get("portfolio_sizing_review") or {}
    formal = data.get("formal_plan") or {}
    _set_feature(row, "00669_review_anchor_close_hkd", lineage.get("review_anchor_completed_close_hkd"), evidence_id)
    _set_feature(row, "00669_historical_pe_context", lineage.get("historical_pe_context"), evidence_id)
    _set_feature(row, "00669_reference_pe_context", lineage.get("reference_pe_context"), evidence_id)
    _set_feature(row, "00669_valuation_interpretation", valuation.get("current_interpretation"), evidence_id)
    _set_feature(row, "00669_research_weight", sizing.get("p5b_governed_research_weight"), evidence_id)
    _set_feature(row, "00669_board_lot_sizing_mismatch", sizing.get("board_lot_sizing_mismatch"), evidence_id)
    _set_feature(row, "00669_implementation_ready", formal.get("implementation_ready"), evidence_id)
    _set_legacy(
        row,
        disposition=formal.get("current_action"),
        source_kind="FORMAL_PLAN",
        evidence_id=evidence_id,
        reason_codes=[
            "FORMAL_PLAN",
            str(valuation.get("current_interpretation", "UNKNOWN")),
            "BOARD_LOT_MISMATCH_" + str(bool(sizing.get("board_lot_sizing_mismatch"))).upper(),
        ],
    )


def _extract_d2_research(
    data: Mapping[str, Any],
    *,
    evidence_id: str,
    opportunity_ids: set[str],
    rows: dict[str, dict[str, Any]],
) -> None:
    sid = data.get("security_id")
    if sid not in opportunity_ids:
        return
    row = _ensure_row(rows, sid)
    row["security_name"] = data.get("security_name", row["security_name"])
    _set_feature(row, "d2_facts", data.get("facts"), evidence_id)
    _set_feature(row, "d2_first_rejection_test", data.get("first_rejection_test"), evidence_id)
    _set_feature(row, "d2_source_count", len(data.get("sources", [])), evidence_id)
    _set_legacy(
        row,
        disposition=data.get("research_disposition"),
        source_kind="RESEARCH_DISPOSITION",
        evidence_id=evidence_id,
        reason_codes=["D2_RESEARCH_DISPOSITION"],
    )


def extract_model_neutral_features(
    snapshot: Mapping[str, Any],
    *,
    source_loader: Callable[[Mapping[str, Any]], Any],
) -> dict[str, Any]:
    """Extract contemporaneous features from only selected Phase 3A evidence."""
    selected_ids = set(snapshot["selected_evidence_ids"])
    opportunity_ids = set(snapshot["opportunity_security_ids"])
    rows: dict[str, dict[str, Any]] = {}

    for record in snapshot["selected_evidence"]:
        evidence_id = record["evidence_id"]
        if evidence_id not in selected_ids:
            raise AssertionError("UNSELECTED_EVIDENCE_RECORD")
        data = source_loader(record)
        key = record["evidence_key"]

        if key == "CANDIDATE_STATE" and isinstance(data, Mapping):
            _extract_candidate_state(data, evidence_id=evidence_id, opportunity_ids=opportunity_ids, rows=rows)
        elif key == "REAL_ACCOUNT_STATE" and isinstance(data, Mapping):
            _extract_real_account(data, evidence_id=evidence_id, opportunity_ids=opportunity_ids, rows=rows)
        elif key == "RESEARCH_CORE2" and isinstance(data, Mapping):
            _extract_core2_research(data, evidence_id=evidence_id, opportunity_ids=opportunity_ids, rows=rows)
        elif key == "RESEARCH_601138_P0" and isinstance(data, Mapping):
            _extract_wp5_p0(data, evidence_id=evidence_id, opportunity_ids=opportunity_ids, rows=rows)
        elif key == "DECISION_00669_BUY_REVIEW" and isinstance(data, Mapping):
            _extract_00669_decision(data, evidence_id=evidence_id, opportunity_ids=opportunity_ids, rows=rows)
        elif key.startswith("RESEARCH_D2_") and isinstance(data, Mapping):
            _extract_d2_research(data, evidence_id=evidence_id, opportunity_ids=opportunity_ids, rows=rows)
        else:
            # The source remains part of the shared evidence packet, but unsupported
            # source shapes are not interpreted merely to create model inputs.
            continue

    clean_rows = {}
    for sid in sorted(opportunity_ids):
        row = rows.get(sid)
        if row is None:
            continue
        row["provenance_evidence_ids"].sort()
        row["legacy_reason_codes"] = list(dict.fromkeys(row["legacy_reason_codes"]))
        row.pop("legacy_disposition_priority", None)
        for feature, provenance in row["feature_provenance"].items():
            outside = set(provenance) - selected_ids
            if outside:
                raise AssertionError(f"FEATURE_PROVENANCE_OUTSIDE_SNAPSHOT:{sid}:{feature}")
        clean_rows[sid] = row

    return {
        "schema_version": "1.0.0",
        "phase": "3C-1",
        "mode": "POINT_IN_TIME_MODEL_NEUTRAL_FEATURES",
        "decision_point_id": snapshot["decision_point_id"],
        "at": snapshot["at"],
        "opportunity_security_ids": sorted(opportunity_ids),
        "selected_evidence_ids": sorted(selected_ids),
        "feature_rows": clean_rows,
        "unsupported_selected_evidence_ids": sorted(
            set(selected_ids)
            - {
                evidence_id
                for row in clean_rows.values()
                for evidence_id in row["provenance_evidence_ids"]
            }
        ),
        "subjective_feature_fill_count": 0,
        "retrospective_probability_backfill_count": 0,
        "retrospective_scenario_backfill_count": 0,
        "controls": deepcopy(FALSE_CONTROLS),
    }


def adapt_features_to_shared_observations(
    feature_layer: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    """Create the Phase 3B observation surface without reading any new evidence."""
    observations: dict[str, dict[str, Any]] = {}
    for sid, row in feature_layer.get("feature_rows", {}).items():
        provenance = list(row["provenance_evidence_ids"])
        if not provenance:
            continue
        observation = {
            "security_name": row.get("security_name", sid),
            "provenance_evidence_ids": provenance,
            "historical_features": deepcopy(row.get("features", {})),
            "feature_provenance": deepcopy(row.get("feature_provenance", {})),
        }
        if row.get("legacy_disposition"):
            observation["legacy_disposition"] = row["legacy_disposition"]
            observation["legacy_reason_codes"] = list(row.get("legacy_reason_codes", []))

        # Phase-2 probabilistic inputs are surfaced ONLY when the historical feature
        # layer already contains explicit probabilities plus every vector input.
        features = row.get("features", {})
        probability_scenarios = features.get("explicit_probability_scenarios")
        phase2_required = {
            "explicit_confidence",
            "explicit_portfolio_concentration_cost",
            "explicit_execution_friction",
        }
        if (
            isinstance(probability_scenarios, list)
            and probability_scenarios
            and phase2_required <= set(features)
        ):
            observation["phase2_inputs"] = {
                "valuation_scenarios": deepcopy(probability_scenarios),
                "confidence": features["explicit_confidence"],
                "portfolio_concentration_cost": features["explicit_portfolio_concentration_cost"],
                "execution_friction": features["explicit_execution_friction"],
            }

        simple_map = {
            "return_proxy": "explicit_simple_return_proxy",
            "downside_resilience": "explicit_simple_downside_resilience",
            "evidence_quality": "explicit_simple_evidence_quality",
            "concentration_cost": "explicit_simple_concentration_cost",
            "execution_friction": "explicit_simple_execution_friction",
        }
        if all(source_key in features for source_key in simple_map.values()):
            observation["simple_pareto_inputs"] = {
                target_key: features[source_key]
                for target_key, source_key in simple_map.items()
            }

        observations[sid] = observation
    return observations
