#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

TRADE_AUTHORITY = "NONE"


def build(root: Path, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    candidate_path = root / "outputs/hk_candidate/current/HK_CANDIDATE_CURRENT.csv"
    candidates = pd.read_csv(candidate_path, dtype={"stock_code_5d": str}, keep_default_na=False)
    required = {"security_id", "candidate_tier", "candidate_status", "monitor_triggers", "principal_falsifier"}
    missing = sorted(required - set(candidates.columns))
    if missing:
        raise ValueError("HK_CANDIDATE_REVIEW_MISSING_COLUMNS:" + ",".join(missing))

    review = candidates[[c for c in [
        "p2a_overall_rank", "security_id", "stock_code_5d", "security_name",
        "candidate_tier", "candidate_status", "as_of_date", "primary_sleeve",
        "principal_falsifier", "monitor_triggers"
    ] if c in candidates.columns]].copy()
    review["review_state"] = "OPERATING_OBSERVATION"
    review["candidate_change_proposed"] = False
    review["candidate_tier_change_proposed"] = False
    review["portfolio_action_proposed"] = False
    review["order_created"] = False
    review["trade_authority"] = TRADE_AUTHORITY
    review.to_csv(output / "HK_CANDIDATE_OPERATING_REVIEW.csv", index=False)

    result = {
        "status": "PASS_HK_CANDIDATE_OPERATING_REVIEW",
        "mode": "PROPOSAL_ONLY_NO_AUTOMATIC_MUTATION",
        "candidate_count": len(review),
        "core_count": int(review["candidate_tier"].astype(str).eq("CORE").sum()),
        "watch_count": int(review["candidate_tier"].astype(str).eq("WATCH").sum()),
        "active_count": int(review["candidate_status"].astype(str).eq("ACTIVE").sum()),
        "rows_with_monitor_triggers": int(review["monitor_triggers"].astype(str).str.strip().ne("").sum()),
        "candidate_mutations": 0,
        "portfolio_mutations": 0,
        "orders": 0,
        "trade_authority": TRADE_AUTHORITY,
        "next_action": "NORMAL_OPERATING_OBSERVATION; evidence-triggered changes require a separately governed Candidate proposal and PR"
    }
    (output / "HK_CANDIDATE_OPERATING_REVIEW.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = build(Path(args.repo_root), Path(args.output))
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
