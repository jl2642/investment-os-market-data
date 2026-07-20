from __future__ import annotations

import json
import math

import pandas as pd

from scripts import fmdl3efinal_core as core


def _chain():
    status = {
        "fmdl3d": "FMDL3D_VALUATION_CAPITALIZATION_AND_SHAREHOLDER_RETURN_LAYER_ACCEPTED",
        "fmdl3ea": "FMDL3EA_INCREMENTAL_REFRESH_CONTRACT_ACCEPTED",
        "fmdl3ebc": "FMDL3EBC_MARKET_AND_FINANCIAL_INCREMENTAL_REFRESH_ACCEPTED",
        "fmdl3ede": "FMDL3E_INCREMENTAL_PROPAGATION_RESILIENCE_AND_REPLAY_ACCEPTED",
    }
    d3 = {"release_id": "D3", "status": status["fmdl3d"], "trade_authority": "NONE"}
    ea = {"release_id": "EA", "status": status["fmdl3ea"], "trade_authority": "NONE", "baseline_id": "B0", "source_fmdl3d_release_id": "D3"}
    bc = {"release_id": "BC", "status": status["fmdl3ebc"], "trade_authority": "NONE", "baseline_id": "B0", "source_fmdl3d_release_id": "D3"}
    de = {"release_id": "DE", "status": status["fmdl3ede"], "trade_authority": "NONE", "baseline_id": "B0", "source_fmdl3d_release_id": "D3", "entry_release_id": "BC", "incremental_release_id": "BC"}
    return {
        "fmdl3d_pointer": dict(d3),
        "fmdl3d_release": dict(d3),
        "fmdl3ea_pointer": {**ea, "next_gate": "FMDL-3E-BC_MARKET_AND_FINANCIAL_INCREMENTAL_REFRESH"},
        "fmdl3ea_release": dict(ea),
        "fmdl3ebc_pointer": {**bc, "next_gate": "FMDL-3E-DE_PROPAGATION_RESILIENCE_AND_REPLAY"},
        "fmdl3ebc_release": dict(bc),
        "fmdl3ede_pointer": {**de, "next_gate": "FMDL-4_PUBLIC_EQUITY_INVESTING_AND_INVESTMENT_OS_INTEGRATION"},
        "fmdl3ede_release": dict(de),
    }


def _cfg():
    return {
        "required_statuses": {
            "fmdl3d": "FMDL3D_VALUATION_CAPITALIZATION_AND_SHAREHOLDER_RETURN_LAYER_ACCEPTED",
            "fmdl3ea": "FMDL3EA_INCREMENTAL_REFRESH_CONTRACT_ACCEPTED",
            "fmdl3ebc": "FMDL3EBC_MARKET_AND_FINANCIAL_INCREMENTAL_REFRESH_ACCEPTED",
            "fmdl3ede": "FMDL3E_INCREMENTAL_PROPAGATION_RESILIENCE_AND_REPLAY_ACCEPTED",
        },
        "acceptance": {
            "accepted_legacy_entry_next_gates": [
                "FMDL-4_PUBLIC_EQUITY_INVESTING_AND_INVESTMENT_OS_INTEGRATION",
                "FMDL-3E-FINAL_UNIFIED_OPERATIONAL_ACCEPTANCE_AND_CANONICAL_CLOSURE",
            ]
        },
    }


def test_valid_release_chain():
    assert core.chain_errors(_chain(), _cfg()) == []


def test_baseline_mismatch_rejected():
    chain = _chain()
    chain["fmdl3ebc_release"]["baseline_id"] = "OTHER"
    assert "BASELINE_ID_MISMATCH" in core.chain_errors(chain, _cfg())


def test_non_finite_values_canonicalize_to_null():
    assert core.stable_hash({"x": math.nan}) == core.stable_hash({"x": None})
    assert core.stable_hash({"x": math.inf}) == core.stable_hash({"x": None})


def test_trade_authority_and_lineage():
    frame = pd.DataFrame([
        {"symbol": "000001.SZ", "trade_authority": "NONE", "component_release_ids_json": json.dumps({"FMDL-3E-BC": "BC", "FMDL-3E-DE": "DE"})}
    ])
    assert core.trade_authority_errors(frame) == 0
    assert core.component_lineage_errors(frame, bc_release_id="BC", de_release_id="DE") == 0
