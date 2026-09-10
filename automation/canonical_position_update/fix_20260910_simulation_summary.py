#!/usr/bin/env python3
import json
from pathlib import Path

P = Path(__file__).resolve().parents[2] / "investment_os_runtime/30_STATE_CURRENT/20_SIMULATION/SIMULATION_LEDGER_CURRENT.json"
p = json.loads(P.read_text(encoding="utf-8-sig"))
s = p["summary"]
s["total_pnl"] = round(float(s["total_assets"]) - 1_000_000.0, 6)
s["day_reference_pnl"] = None
s["valuation_status"] = "RETAINED_PRIOR_MARKS_PENDING_NEXT_COMPLETED_CLOSE_REFRESH"
P.write_text(json.dumps(p, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
assert s["total_pnl"] == 31154.74
print({"simulation_summary_reconciliation":"PASS","total_pnl":s["total_pnl"]})
