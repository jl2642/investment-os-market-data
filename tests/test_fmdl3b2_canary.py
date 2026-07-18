import json
from pathlib import Path

from scripts import run_fmdl3b2_canary as canary

ROOT = Path(__file__).resolve().parents[1]


def test_board_derivation():
    assert canary.derive_board("688256.SH") == "STAR"
    assert canary.derive_board("300750.SZ") == "CHINEXT"
    assert canary.derive_board("600519.SH") == "SH_MAIN"
    assert canary.derive_board("000333.SZ") == "SZ_MAIN"
    assert canary.derive_board("835185.BJ") == "BSE"


def test_canary_selection_is_deterministic_and_contains_stress_sample():
    universe = ["000001.SZ", "000333.SZ", "000776.SZ", "300750.SZ", "600030.SH", "600036.SH", "600519.SH", "601318.SH", "605090.SH", "688256.SH", "688981.SH", "430047.BJ", "835185.BJ"] + [f"{i:06d}.SZ" for i in range(1000, 1100)]
    first = canary.choose_canary(universe, 32)
    second = canary.choose_canary(universe, 32)
    assert [item["symbol"] for item in first] == [item["symbol"] for item in second]
    stress = {item["symbol"] for item in json.loads((ROOT / "config/fmdl3a_benchmark.json").read_text(encoding="utf-8"))["sample_design"]["symbols"]}
    assert stress.issubset({item["symbol"] for item in first})
    assert len(first) == 32


def test_storage_policy_does_not_commit_unbounded_raw_store():
    cfg = json.loads((ROOT / "config/fmdl3b2_full_build.json").read_text(encoding="utf-8"))
    assert cfg["storage"]["raw_storage_mode"].startswith("IMMUTABLE_WORKFLOW_ARTIFACT")
    assert cfg["storage"]["maximum_git_file_mib"] < 100
    assert cfg["full_build"]["fallback_policy"] == "CALL_ONLY_WHEN_PRIMARY_STATEMENT_COMPONENT_IS_MISSING_OR_FAILED"
    assert cfg["trade_authority"] == "NONE"
