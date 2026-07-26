from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path


def parse_session(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise SystemExit(f"invalid session: {value}") from exc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--session", required=True)
    parser.add_argument("--open-proposal-count", type=int, required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    if args.open_proposal_count < 0:
        raise SystemExit("open-proposal-count must be non-negative")

    repo = Path(args.repo_root)
    binding_path = repo / "investment_os_runtime/50_MARKET_CAPABILITY_BINDINGS/A_SHARE_CURRENT.json"
    binding = json.loads(binding_path.read_text(encoding="utf-8"))
    current_session = str(binding.get("as_of_date") or "")
    incoming = parse_session(args.session)
    current = parse_session(current_session)

    if incoming <= current:
        proceed = False
        reason = "SESSION_NOT_NEWER_THAN_CURRENT"
    elif args.open_proposal_count > 0:
        proceed = False
        reason = "OPEN_PROPOSAL_ALREADY_EXISTS"
    else:
        proceed = True
        reason = "NEW_SESSION_NO_OPEN_PROPOSAL"

    result = {
        "status": "PROCEED" if proceed else "NO_OP",
        "proceed": proceed,
        "reason": reason,
        "incoming_session": args.session,
        "current_session": current_session,
        "open_proposal_count": args.open_proposal_count,
        "candidate_membership_mutations": 0,
        "research_object_mutations": 0,
        "simulation_trade_mutations": 0,
        "real_account_mutations": 0,
        "orders": 0,
        "trade_authority": "NONE",
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
