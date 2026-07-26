from __future__ import annotations

import json
import subprocess
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "finalize_account_summaries.py"


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def test_cash_and_historical_watermark_bridge_are_explicit(tmp_path: Path) -> None:
    config = {
        "source_paths": {
            "real_legacy": "real_source.json",
            "simulation_legacy": "sim_source.json",
        },
        "output_paths": {
            "real_positions": "out/real.json",
            "simulation_positions": "out/sim.json",
            "portfolio_marks": "out/marks.json",
            "run_current": "out/run.json",
            "acceptance": "out/acceptance.json",
        },
    }
    real_source = {"summary": {"brokerage_available_cash": 120.49}}
    sim_source = {"summary": {"available_cash": 200.0, "total_assets": 1000.0, "total_pnl": 0.0}}
    register = {
        "wp2_3": {
            "real_account": {"total_assets": 1110.0, "watermark": "MIXED"},
            "simulation": {"total_assets": 1000.0, "watermark": "CLOSE"},
        }
    }
    real = {
        "holdings": [{"security_id": "000001.SZ", "market_value": 1000.0, "cost_basis": 900.0}],
        "summary": {},
    }
    sim = {
        "holdings": [{"security_id": "000002.SZ", "market_value": 850.0, "cost_basis": 800.0}],
        "summary": {},
    }
    marks = {"status": "CURRENT_COMPLETE"}
    run = {"economic_transaction_mutations": 0, "orders": 0, "trade_authority": "NONE"}
    acceptance = {"outputs": {}, "wp5_unblocked": False}

    write(tmp_path / "config.json", config)
    write(tmp_path / "real_source.json", real_source)
    write(tmp_path / "sim_source.json", sim_source)
    write(tmp_path / "investment_os_runtime/00_CONTROL/EXECUTION_REGISTER_CURRENT.json", register)
    write(tmp_path / "out/real.json", real)
    write(tmp_path / "out/sim.json", sim)
    write(tmp_path / "out/marks.json", marks)
    write(tmp_path / "out/run.json", run)
    write(tmp_path / "out/acceptance.json", acceptance)

    subprocess.run(
        ["python", str(SCRIPT), "--repo-root", str(tmp_path), "--config", "config.json"],
        check=True,
    )
    real_out = json.loads((tmp_path / "out/real.json").read_text(encoding="utf-8"))
    sim_out = json.loads((tmp_path / "out/sim.json").read_text(encoding="utf-8"))
    run_out = json.loads((tmp_path / "out/run.json").read_text(encoding="utf-8"))
    acceptance_out = json.loads((tmp_path / "out/acceptance.json").read_text(encoding="utf-8"))

    assert real_out["summary"]["account_total_assets"] == 1120.49
    assert real_out["summary"]["difference_vs_historical_wp2_3"] == 10.49
    assert real_out["summary"]["cash_semantics"] == "BROKER_EXECUTION_BALANCE_ONLY_EXTERNAL_LIQUIDITY_EXCLUDED"
    assert sim_out["summary"]["account_total_assets"] == 1050.0
    assert sim_out["summary"]["account_total_pnl"] == 50.0
    assert sim_out["summary"]["difference_vs_historical_wp2_3"] == 50.0
    assert run_out["position_or_cost_mutations_from_reconciliation"] == 0
    assert acceptance_out["account_summary_controls"]["forced_reconciliation_mutations"] == 0
    assert acceptance_out["trade_authority"] == "NONE"
