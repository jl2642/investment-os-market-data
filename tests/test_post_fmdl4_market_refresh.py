from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "post_fmdl4_fetch_market.py"
spec = importlib.util.spec_from_file_location("post_fmdl4_fetch_market", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def test_market_mapping() -> None:
    assert module.market_id("600900") == 1
    assert module.market_id("510500") == 1
    assert module.market_id("000333") == 0
    assert module.market_id("300308") == 0
    assert module.market_id("159352") == 0


def test_config_has_complete_unique_universe() -> None:
    config_path = Path(__file__).resolve().parents[1] / "config" / "post_fmdl4_symbol_universe.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    symbols = [row["symbol"] for row in config["symbols"]]
    assert len(symbols) == 30
    assert len(symbols) == len(set(symbols))
    assert {"000333", "600900", "000938", "600018", "300308", "002396"}.issubset(symbols)
    assert config["trade_authority"] == "NONE"
    assert config["target_market_date"] == "2026-07-20"


def test_release4_binding_and_cash_policy() -> None:
    path = Path(__file__).resolve().parents[1] / "config" / "post_fmdl4_release4_state_binding.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["source_package_sha256"] == "cfc25d81c900e11cab594067a8a6220fc7654b9bf2540783d02121da3abda511"
    assert len(data["real_holdings"]) == 7
    assert len(data["simulation_holdings"]) == 16
    assert len(data["candidate_core_20"]) == 20
    assert data["cash_policy"] == "BROKER_CASH_IS_EXECUTION_BALANCE_NOT_STRATEGIC_ASSET_BUCKET"
    assert data["trade_authority"] == "NONE"
