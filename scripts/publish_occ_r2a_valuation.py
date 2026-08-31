from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("Asia/Shanghai")
CANDIDATE = ROOT / "outputs/occ_r2/valuation/candidate"
CURRENT = ROOT / "outputs/occ_r2/valuation/current"
ARCHIVE = ROOT / "outputs/occ_r2/valuation/archive"
RELEASES = ROOT / "datasets/occ_r2/valuation/releases"
LAST_SUCCESS = ROOT / "outputs/status/OCC_R2A_VALUATION_LAST_SUCCESS.json"


def copy_tree(source: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(source, dest)


def main() -> int:
    decision = json.loads((CANDIDATE / "VALUATION_CONTEXT_DECISION.json").read_text(encoding="utf-8"))
    validation = json.loads((CANDIDATE / "VALUATION_CONTEXT_VALIDATION.json").read_text(encoding="utf-8"))
    if decision.get("status") != "PASS" or validation.get("status") != "PASS":
        raise SystemExit("OCC_R2A_CANDIDATE_NOT_ACCEPTED")
    release_id = str(decision["release_id"])
    release_root = RELEASES / release_id
    copy_tree(CANDIDATE, CURRENT)
    copy_tree(CANDIDATE, release_root)
    published_at = datetime.now(TZ).isoformat(timespec="seconds")
    pointer = {
        "schema_version": "1.0.0",
        "release_id": release_id,
        "published_at": published_at,
        "status": "PASS",
        "qc_status": decision["qc_status"],
        "market_as_of_date": decision["market_as_of_date"],
        "financial_denominator_status": decision["financial_denominator"]["status"],
        "financial_statement_release_id": decision["financial_denominator"]["statement_release_id"],
        "financial_factor_release_id": decision["financial_denominator"]["financial_factor_release_id"],
        "financial_score_release_id": decision["financial_denominator"]["financial_score_release_id"],
        "financial_event_propagation": decision["financial_denominator"]["financial_event_propagation"],
        "row_count": decision["universe"]["valuation_context_row_count"],
        "coverage_scope": decision["universe"]["coverage_scope"],
        "authority": decision["authority"],
        "trade_authority": "NONE",
    }
    (CURRENT / "VALUATION_CONTEXT_RELEASE.json").write_text(
        json.dumps(pointer, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (release_root / "VALUATION_CONTEXT_RELEASE.json").write_text(
        json.dumps(pointer, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    LAST_SUCCESS.parent.mkdir(parents=True, exist_ok=True)
    LAST_SUCCESS.write_text(json.dumps(pointer, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(pointer, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
