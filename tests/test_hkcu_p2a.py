from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "hkcu_p2a", ROOT / "pipeline/hkcu_p2a_build_longlist.py"
)
assert SPEC and SPEC.loader
p2a = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(p2a)


def test_distribution_clustering_is_deterministic_and_not_fixed_n() -> None:
    scores = pd.Series(
        list(np.linspace(0.20, 0.55, 40))
        + list(np.linspace(0.60, 0.90, 35))
        + list(np.linspace(1.05, 1.30, 25))
    )
    labels_a, centroids_a = p2a.deterministic_kmeans_1d(scores, 3)
    labels_b, centroids_b = p2a.deterministic_kmeans_1d(scores, 3)
    assert np.array_equal(labels_a, labels_b)
    assert np.allclose(centroids_a, centroids_b)
    high = int(np.argmax(centroids_a))
    selected = int((labels_a == high).sum())
    assert selected == 25
    assert selected != 100


def test_research_readiness_does_not_impute_missing_p2b_dimensions() -> None:
    row = pd.Series({"confidence_grade": "A", "factor_record_quality": "VALID"})
    assert p2a.research_readiness(row, 0.90) == "READY_HIGH"
    assert p2a.research_readiness(row, 0.50) == "READY_PARTIAL"


def test_canonical_gate_fails_on_trade_authority_or_sell_only() -> None:
    contract = {
        "required_input_columns": [
            "security_id", "publication_eligible", "r2e_gate_pass", "buy_eligible",
            "sell_only", "freshness_status", "trade_authority", "investability_status"
        ],
        "allowed_investability_status": ["ELIGIBLE_CORE", "ELIGIBLE_WATCH"],
    }
    frame = pd.DataFrame([
        {
            "security_id": "HKEX:00001",
            "publication_eligible": True,
            "r2e_gate_pass": True,
            "buy_eligible": True,
            "sell_only": True,
            "freshness_status": "CURRENT",
            "trade_authority": "ORDER",
            "investability_status": "ELIGIBLE_CORE",
        }
    ])
    decision = {"status": "PASS_CURRENT", "provisional_investable_count": 1}
    quality = {"status": "PASS", "hard_failures": []}
    errors = p2a.validate_canonical(frame, decision, quality, contract)
    assert any(item.startswith("SELL_ONLY_PRESENT") for item in errors)
    assert any(item.startswith("TRADE_AUTHORITY_NOT_NONE") for item in errors)
