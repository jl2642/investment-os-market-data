from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _json(path: str) -> dict:
    return json.loads(_text(path))


def test_system_current_is_the_only_system_level_authority() -> None:
    current = _json("investment_os_runtime/00_CONTROL/SYSTEM_CURRENT.json")
    assert current["sole_system_current_authority"] is True
    assert current["canonical_control_branch"] == "main"
    assert current["canonical_runtime_branch"] == "operating-current"
    assert current["runtime_index_path"] == "operating_current/OPERATING_CURRENT_INDEX.json"
    assert current["trade_authority"] == "NONE"


def test_active_registry_separates_runtime_core_transitional_and_retired() -> None:
    registry = _json("investment_os_runtime/00_CONTROL/ACTIVE_WORKFLOW_REGISTRY.json")
    active = {row["path"] for row in registry["active_runtime_core"]}
    transitional = set(registry["transitional_investment_runtime_until_s2_s3"])
    retired = {row["path"] for row in registry["retired_automatic_workflows_s1"]}
    assert ".github/workflows/fmdl-daily-production.yml" in active
    assert ".github/workflows/fmdl-2b4-full-rebase.yml" in active
    p43 = ".github/workflows/p4-3-unified-recommendation.yml"
    assert (p43 in transitional) ^ (p43 in retired)
    assert ".github/workflows/r0_product_authority_freeze.yml" in retired
    assert ".github/workflows/r2_portfolio_construction.yml" in retired
    assert ".github/workflows/fmdl-3-architecture.yml" in retired
    assert ".github/workflows/stock-investment-assistant-final-integration.yml" in retired
    assert not (retired & active)
    assert not (retired & transitional)


def test_retired_development_workflows_have_no_automatic_triggers() -> None:
    for path in (
        ".github/workflows/r0_product_authority_freeze.yml",
        ".github/workflows/r2_portfolio_construction.yml",
    ):
        text = _text(path)
        assert "workflow_dispatch:" in text
        assert "\n  push:" not in text
        assert "\n  pull_request:" not in text
        assert "\n  schedule:" not in text
        assert "\n  workflow_run:" not in text


def test_daily_retries_after_successful_full_rebase_and_verifies_dependencies() -> None:
    text = _text(".github/workflows/fmdl-daily-production.yml")
    assert 'workflows: ["FMDL 2B-4 Multi-Session Full Rebase Recovery"]' in text
    assert "github.event.workflow_run.conclusion == 'success'" in text
    assert "github.event.workflow_run.head_branch == 'main'" in text
    assert "materialize_fmdl_history_dependencies.py" in text
    assert "--verify" in text


def test_branch_policy_has_two_long_lived_authorities_only() -> None:
    text = _text("investment_os_runtime/00_CONTROL/BRANCH_POLICY.md")
    assert "`main`" in text
    assert "`operating-current`" in text
    assert "`agent/*` and `automation/*` branches are temporary" in text
    assert "trade_authority=NONE" in text


def test_retired_architecture_gates_only_validate_their_own_tombstone() -> None:
    for path in (
        ".github/workflows/fmdl-3-architecture.yml",
        ".github/workflows/stock-investment-assistant-final-integration.yml",
    ):
        text = _text(path)
        assert "workflow_dispatch:" in text
        assert "pull_request:" in text
        assert f'- "{path}"' in text
        assert "Development Complete · Operating Observation" not in text
        assert "trade_authority=NONE" in text
