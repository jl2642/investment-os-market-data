"""Fail-closed Phase 3 preflight: require coherent completed trading sessions.

A stale upstream lifecycle is an explicit deferred handoff, NOT a failed virtual
rebalance. The existing Phase 2 lifecycle publisher dispatches Phase 3 again
when it publishes a subsequent coherent state.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


def session_readiness(
    marks: dict[str, Any], lifecycle: dict[str, Any],
) -> tuple[bool, list[str]]:
    """Return whether Phase 3 may use its listed closing prices without lookahead."""
    for label, doc, accepted in (("PORTFOLIO_MARKS", marks, "PASS"), ("DECISION_LIFECYCLE", lifecycle, "PASS_DECISION_LIFECYCLE")):
        if doc.get("status") != accepted:
            raise ValueError(f"PHASE3_INVALID_UPSTREAM_STATUS:{label}:{doc.get('status')}")
        if doc.get("orders") != 0 or doc.get("trade_authority") != "NONE":
            raise ValueError(f"PHASE3_UPSTREAM_AUTHORITY_VIOLATION:{label}")
    date = str(marks.get("data_watermark") or "")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        raise ValueError(f"PHASE3_INVALID_MARK_DATE:{date!r}")
    issues: list[str] = []
    identity = lifecycle.get("input_identity") or {}
    for label, observed in (
        ("LIFECYCLE_AS_OF", lifecycle.get("as_of_date")),
        ("LIFECYCLE_MARKET_DATE", identity.get("market_date")),
        ("LIFECYCLE_SURFACE_DATE", identity.get("surface_as_of_date")),
    ):
        if observed != date:
            issues.append(f"{label}:{observed or 'MISSING'}:EXPECTED:{date}")
    for row in lifecycle.get("subjects", []):
        sid = str(row.get("security_id") or "")
        if (
            row.get("price_source") == "A_SHARE_FULL_MARKET"
            and sid.endswith((".SH", ".SZ", ".BJ"))
            and row.get("price_as_of") != date
        ):
            issues.append(
                f"LISTED_PRICE:{sid}:{row.get('price_as_of') or 'MISSING'}:"
                f"EXPECTED:{date}"
            )
    return not issues, issues


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--marks", type=Path, required=True)
    parser.add_argument("--lifecycle", type=Path, required=True)
    parser.add_argument("--github-output", type=Path, required=True)
    parser.add_argument("--github-summary", type=Path, required=True)
    args = parser.parse_args()
    marks = json.loads(args.marks.read_text(encoding="utf-8"))
    lifecycle = json.loads(args.lifecycle.read_text(encoding="utf-8"))
    ready, issues = session_readiness(marks, lifecycle)
    with args.github_output.open("a", encoding="utf-8") as out:
        out.write(f"ready={'true' if ready else 'false'}\n")
    date = marks["data_watermark"]
    status = "READY" if ready else "DEFERRED_UPSTREAM_SESSION_MISMATCH"
    with args.github_summary.open("a", encoding="utf-8") as summary:
        summary.write(f"## Phase 3 session preflight: {status}\n")
        summary.write(f"- target market and portfolio mark session: {date}\n")
        if issues:
            summary.write("- no Phase 3 build, publication or economic mutation attempted\n")
            summary.write("- later Phase 2 publication dispatches a new Phase 3 attempt\n")
            for issue in issues[:30]:
                summary.write(f"- mismatch: `{issue}`\n")
            if len(issues) > 30:
                summary.write(f"- additional mismatches: {len(issues) - 30}\n")
    print(json.dumps({"phase3_session_preflight": status, "date": date, "mismatches": issues}, ensure_ascii=False))


if __name__ == "__main__":
    main()
