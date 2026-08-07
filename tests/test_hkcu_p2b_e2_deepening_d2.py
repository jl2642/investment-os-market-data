from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "config/hkcu_p2b_e2_deepening_d2_contract.json"
MODULE = ROOT / "pipeline/hkcu_p2b_e2_synthesize_top20_partial.py"
spec = importlib.util.spec_from_file_location("p2b_e2_d2", MODULE)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


def test_d2_contract_exact_top20_surface():
    c = json.loads(CONTRACT.read_text(encoding="utf-8"))
    s = c["selection_policy"]
    assert s["rank_start"] == 1
    assert s["rank_end"] == 20
    assert s["expected_partial_rows"] == 51
    assert s["expected_governance_rows"] == 20
    assert s["expected_earnings_rows"] == 17
    assert s["expected_catalyst_rows"] == 14
    assert c["synthesis_policy"]["no_alpha_score"] is True
    assert c["synthesis_policy"]["ordinary_results_do_not_equal_consensus_revision"] is True
    assert c["acceptance"]["formal_candidate_graduation_allowed"] is False
    assert c["trade_authority"] == "NONE"


def test_governance_auditor_and_connected_transactions_are_targeted_blockers():
    auditor = mod.governance_synthesis(
        "Change of auditor",
        "Auditor change and AGM outcomes require follow-up.",
    )
    connected = mod.governance_synthesis(
        "Connected transaction",
        "Pricing and related-party economics remain open.",
    )
    for result in [auditor, connected]:
        assert result["evidence_sufficiency"] == "TARGETED_DEEPENING_REQUIRED"
        assert result["materiality"] == "HIGH"
        assert result["graduation_blocker"] is True


def test_ordinary_results_never_generate_earnings_direction():
    current = mod.earnings_synthesis(
        "First Quarter 2026 Results",
        "Official results provide current evidence but no consensus revision series.",
        "2026-04-29",
    )
    annual = mod.earnings_synthesis(
        "2025 Final Results",
        "No direct 2026 expectation-revision evidence located.",
        "2026-03-03",
    )
    assert current["finding_direction"] == "UNKNOWN"
    assert annual["finding_direction"] == "UNKNOWN"
    assert "OPERATING_EVIDENCE" in current["finding"]
    assert "ANNUAL_ONLY" in annual["finding"]


def test_material_corporate_action_is_targeted_not_scored():
    spin = mod.catalyst_synthesis(
        "Proposed spin-off of subsidiary",
        "Timing and completion conditions require tracking.",
    )
    assert spin["materiality"] == "HIGH"
    assert spin["finding_direction"] == "MIXED"
    assert spin["graduation_blocker"] is True
    assert spin["evidence_sufficiency"] == "TARGETED_DEEPENING_REQUIRED"


def test_positive_profit_catalyst_is_positive_but_not_alpha_score():
    result = mod.catalyst_synthesis(
        "Estimated Profit Increase for Interim Results 2026",
        "Near-term results catalyst.",
    )
    assert result["finding_direction"] == "POSITIVE"
    assert result["materiality"] == "HIGH"
    assert result["graduation_blocker"] is False
