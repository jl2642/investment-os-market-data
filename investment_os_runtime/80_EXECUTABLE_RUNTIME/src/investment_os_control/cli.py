from __future__ import annotations

from pathlib import Path
import argparse
import json

from .core import read_json, route_event, validate_runtime


def main() -> int:
    parser = argparse.ArgumentParser(prog="investment-os-control")
    parser.add_argument("--root", default="investment_os_runtime")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate-all")
    validate.add_argument("--evaluation-date", required=True)

    route = sub.add_parser("route-event")
    route.add_argument("--event-file", required=True)

    args = parser.parse_args()
    root = Path(args.root)

    if args.command == "validate-all":
        result = validate_runtime(root, args.evaluation_date)
    else:
        event = read_json(Path(args.event_file))
        taxonomy = read_json(root / "60_OPERATIONS_AND_EVENT" / "EVENT_TAXONOMY_AND_ROUTING.json")
        result = route_event(event, taxonomy)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status", "PASS") != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
