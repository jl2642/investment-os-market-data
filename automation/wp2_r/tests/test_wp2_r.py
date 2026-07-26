from __future__ import annotations

import importlib.util
import json
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "build_portfolio_current.py"
SPEC = importlib.util.spec_from_file_location("wp2r_builder", MODULE_PATH)
assert SPEC and SPEC.loader
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_security_id_normalization() -> None:
    assert BUILDER.canonical_security_id("000333") == "000333.SZ"
    assert BUILDER.canonical_security_id("600900") == "600900.SH"
    assert BUILDER.canonical_security_id("159352") == "159352.SZ"
    assert BUILDER.canonical_security_id("510500") == "510500.SH"
    assert BUILDER.canonical_security_id("920079") == "920079.SH"
    assert BUILDER.security_id_for("017534", "BOND_FUND") == "017534.OF"


def test_user_confirmation_is_required_for_applied_delta() -> None:
    ledger = {
        "trade_authority": "NONE",
        "entries": [
            {
                "delta_id": "D1",
                "status": "CONFIRMED_BY_USER",
                "confirmation_authority": "AUTOMATION",
            }
        ],
    }
    try:
        BUILDER.validate_delta_ledger(ledger)
    except ValueError as exc:
        assert "REQUIRES_USER_AUTHORITY" in str(exc)
    else:
        raise AssertionError("non-user confirmation must fail closed")


def test_confirmed_buy_changes_position_but_market_refresh_cannot() -> None:
    positions = [
        {
            "account": "SIMULATION",
            "security_id": "000333.SZ",
            "code": "000333",
            "security_name": "美的集团",
            "asset_class": "A_SHARE_STOCK",
            "quantity": 100.0,
            "available_quantity": 100.0,
            "unit_cost": 70.0,
            "cost_basis": 7000.0,
            "cost_basis_method": "UNIT_COST_TIMES_QUANTITY",
            "position_source_as_of": "2026-07-20_CLOSE",
            "position_source_run_id": "BASE",
            "broker_verified": False,
        }
    ]
    ledger = {
        "trade_authority": "NONE",
        "entries": [
            {
                "delta_id": "D1",
                "account": "SIMULATION",
                "security_id": "000333",
                "action": "BUY",
                "quantity_delta": 20,
                "unit_price": 80,
                "fees": 5,
                "trade_date": "2026-07-24",
                "status": "CONFIRMED_BY_USER",
                "confirmation_authority": "USER",
            }
        ],
    }
    updated, applied = BUILDER.apply_confirmed_deltas(positions, ledger, "SIMULATION")
    assert applied == ["D1"]
    assert updated[0]["quantity"] == 120
    assert updated[0]["cost_basis"] == 8605
    marks = [
        {
            "security_id": "000333.SZ",
            "mark": 90,
            "as_of_date": "2026-07-24",
            "provider": "TEST",
            "freshness_status": "FRESH",
        }
    ]
    enriched = BUILDER.enrich_positions(updated, marks)
    assert enriched[0]["quantity"] == 120
    assert enriched[0]["cost_basis"] == 8605
    assert enriched[0]["market_value"] == 10800


def test_builder_produces_separate_watermarks_and_zero_orders(tmp_path: Path) -> None:
    real = {
        "state_id": "REAL_BASE",
        "as_of": "2026-07-20_CLOSE",
        "holdings": [
            {
                "code": "159352",
                "holding_name": "南方中证A500ETF",
                "asset_class": "A_SHARE_ETF",
                "quantity_or_shares": 100,
                "latest_price_or_nav": 1.2,
                "cost_price_or_cost": 1.3,
                "as_of": "2026-07-20_CLOSE",
                "data_source": "TEST",
            },
            {
                "code": "017534",
                "holding_name": "富国天利增长债券C",
                "asset_class": "BOND_FUND",
                "quantity_or_shares": 100,
                "latest_price_or_nav": 1.4,
                "cost_price_or_cost": 130,
                "as_of": "2026-07-20_CLOSE",
                "data_source": "TEST",
            },
        ],
    }
    simulation = {
        "state_id": "SIM_BASE",
        "as_of": "2026-07-20_CLOSE",
        "holdings": [
            {
                "security_code": "000333",
                "security_name": "美的集团",
                "quantity": 10,
                "available_quantity": 10,
                "last_price_close": 80,
                "cost_price": 70,
                "as_of": "2026-07-20_CLOSE",
                "data_source": "TEST",
            }
        ],
    }
    ledger = {
        "ledger_id": "LEDGER",
        "continuity_confirmed_through": "2026-07-24",
        "entries": [],
        "trade_authority": "NONE",
    }
    marks = {
        "refresh_id": "TEST_MARKS",
        "status": "PASS_COMPLETE",
        "marks": [
            {
                "security_id": "159352.SZ",
                "code": "159352",
                "security_name": "ETF",
                "asset_class": "A_SHARE_ETF",
                "mark": 1.25,
                "as_of_date": "2026-07-24",
                "provider": "TEST",
                "freshness_status": "FRESH",
            },
            {
                "security_id": "017534.OF",
                "code": "017534",
                "security_name": "FUND",
                "asset_class": "BOND_FUND",
                "mark": 1.41,
                "as_of_date": "2026-07-23",
                "provider": "TEST",
                "freshness_status": "ACCEPTABLE_LAG",
            },
            {
                "security_id": "000333.SZ",
                "code": "000333",
                "security_name": "MIDEA",
                "asset_class": "A_SHARE_STOCK",
                "mark": 84,
                "as_of_date": "2026-07-24",
                "provider": "TEST",
                "freshness_status": "FRESH",
            },
        ],
    }
    config = {
        "source_paths": {
            "real_legacy": "real.json",
            "simulation_legacy": "sim.json",
            "delta_ledger": "ledger.json",
            "marks_candidate": "marks.json",
        },
        "output_paths": {
            "real_positions": "out/real.json",
            "simulation_positions": "out/sim.json",
            "portfolio_marks": "out/marks.json",
            "run_current": "out/run.json",
            "acceptance": "out/acceptance.json",
        },
    }
    write_json(tmp_path / "real.json", real)
    write_json(tmp_path / "sim.json", simulation)
    write_json(tmp_path / "ledger.json", ledger)
    write_json(tmp_path / "marks.json", marks)
    write_json(tmp_path / "config.json", config)

    import subprocess
    subprocess.run(
        [
            "python",
            str(MODULE_PATH),
            "--repo-root",
            str(tmp_path),
            "--config",
            "config.json",
        ],
        check=True,
    )
    real_out = json.loads((tmp_path / "out/real.json").read_text(encoding="utf-8"))
    run_out = json.loads((tmp_path / "out/run.json").read_text(encoding="utf-8"))
    assert {row["security_id"] for row in real_out["holdings"]} == {"159352.SZ", "017534.OF"}
    assert real_out["position_watermark"]["position_state_current"] is True
    assert real_out["mark_watermark"]["all_marks_fresh_or_acceptable"] is True
    assert real_out["broker_verification"]["broker_verified"] is False
    assert run_out["wp4b_position_level_fit_ready"] is True
    assert run_out["wp5_live_action_ready"] is False
    assert run_out["orders"] == 0
    assert run_out["trade_authority"] == "NONE"
