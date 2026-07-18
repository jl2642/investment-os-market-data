from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fmdl3b4_statement_current.json"
SCHEMA = ROOT / "schemas/fmdl3b4_statement_current_v1.schema.json"


def main() -> int:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    checks = {
        "PROGRAM_ID": cfg.get("program_id") == "FMDL-3B-4",
        "ENTRY_3B2": cfg.get("entry_gates", {}).get("fmdl3b2_status") == "FMDL3B2_FULL_UNIVERSE_INITIAL_BUILD_ACCEPTED_WITH_CONTROLLED_QUARANTINE",
        "ENTRY_3B3": cfg.get("entry_gates", {}).get("fmdl3b3_status") == "FMDL3B3_COMPARABILITY_AND_RESTATEMENT_HARDENING_ACCEPTED",
        "EXIT_STATUS": cfg.get("exit_status") == "FMDL3B4_POINT_IN_TIME_STATEMENT_STORE_ACCEPTED",
        "NEXT_GATE": cfg.get("next_gate") == "FMDL-3C_FINANCIAL_QUALITY_GROWTH_AND_BALANCE_SHEET_FACTORS",
        "ZERO_TRADE_AUTHORITY": cfg.get("trade_authority") == "NONE" and cfg.get("acceptance_policy", {}).get("trade_authority") == "NONE",
        "IMMUTABLE_RELEASE": cfg.get("publication", {}).get("versioned_release_is_immutable") is True,
        "LKG_PRESERVED": cfg.get("publication", {}).get("candidate_cannot_replace_current_on_failure") is True,
        "SCHEMA_STATUS": schema.get("properties", {}).get("status", {}).get("const") == cfg.get("exit_status"),
        "SCHEMA_NEXT_GATE": schema.get("properties", {}).get("next_gate", {}).get("const") == cfg.get("next_gate"),
    }
    failures = [name for name, passed in checks.items() if not passed]
    print(json.dumps({"status": "PASS" if not failures else "FAIL", "checks": checks, "hard_failures": failures}, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
