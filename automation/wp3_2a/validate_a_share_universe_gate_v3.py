from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

CODE = re.compile(r"^\d{6}$")
EXCHANGE_ALIASES = {
    "SH": "SSE",
    "SSE": "SSE",
    "XSHG": "SSE",
    "SZ": "SZSE",
    "SZSE": "SZSE",
    "XSHE": "SZSE",
    "BJ": "BSE",
    "BSE": "BSE",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def normalize_old_symbol(item: dict, line_number: int) -> tuple[str, str]:
    symbol = str(item.get("symbol") or "").strip()
    if not symbol:
        raise ValueError(f"missing symbol at line {line_number}")

    if "." in symbol:
        code, suffix = symbol.split(".", 1)
    else:
        code, suffix = symbol, ""
    code = code.zfill(6)
    if not CODE.fullmatch(code):
        raise ValueError(f"invalid historical symbol at line {line_number}: {symbol}")

    market = item.get("market_evidence") or {}
    raw_exchange = str(market.get("exchange") or suffix).strip().upper()
    exchange = EXCHANGE_ALIASES.get(raw_exchange, raw_exchange)
    if not exchange:
        raise ValueError(
            f"missing historical exchange at line {line_number}: {symbol}"
        )
    return code, exchange


def old_identity(path: Path) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    with path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            if not line.strip():
                continue
            item = json.loads(line)
            code, exchange = normalize_old_symbol(item, line_number)
            if code in rows:
                raise ValueError(f"duplicate historical code {code} at line {line_number}")
            rows[code] = {
                "name": item.get("name"),
                "exchange": exchange,
            }
    return rows


def current_rows(path: Path) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            code = str(row.get("security_code") or "").zfill(6)
            if code in rows:
                raise ValueError(f"duplicate code {code}")
            rows[code] = row
    return rows


def ensure_previous_identity(path: Path) -> None:
    if path.exists():
        return
    from materialize_identity_baseline import materialize

    generated = materialize(Path.cwd())
    if generated.resolve() != path.resolve():
        raise RuntimeError(
            f"materialized identity baseline at unexpected path: {generated} != {path}"
        )


def write_result(path: Path, result: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


def execute_gate(a: argparse.Namespace) -> dict:
    previous_path = Path(a.previous_jsonl)
    current_path = Path(a.current_csv)
    ensure_previous_identity(previous_path)
    old = old_identity(previous_path)
    cur = current_rows(current_path)
    errors: list[str] = []
    warnings: list[str] = []

    if a.as_of != a.latest_completed_session:
        errors.append("FRESHNESS_NOT_LATEST_COMPLETED_SESSION")
    if not a.expected_min <= len(cur) <= a.expected_max:
        errors.append("ROW_COUNT_OUT_OF_RANGE")
    if any(not CODE.match(code) for code in cur):
        errors.append("INVALID_SECURITY_CODE")

    exchanges = {str(row.get("exchange") or "") for row in cur.values()}
    if not {"SSE", "SZSE", "BSE"}.issubset(exchanges):
        errors.append("EXCHANGE_COVERAGE_INCOMPLETE")

    providers = sorted(
        {
            str(row.get("source_provider") or "")
            for row in cur.values()
            if row.get("source_provider")
        }
    )
    if providers != [a.expected_provider]:
        errors.append("PROVIDER_CHANGE_OR_MIX_REQUIRES_EXPLICIT_REVIEW")

    price_fill = sum(
        row.get("last_price") not in ("", None, "-", "--")
        for row in cur.values()
    ) / max(len(cur), 1)
    volume_fill = sum(
        row.get("volume") not in ("", None, "-", "--")
        for row in cur.values()
    ) / max(len(cur), 1)
    if price_fill < 0.90:
        errors.append("PRICE_FILL_BELOW_90_PERCENT")
    if volume_fill < 0.85:
        errors.append("VOLUME_FILL_BELOW_85_PERCENT")

    old_codes, cur_codes = set(old), set(cur)
    additions = sorted(cur_codes - old_codes)
    deletions = sorted(old_codes - cur_codes)
    name_changes: list[dict] = []
    exchange_changes: list[dict] = []
    for code in sorted(old_codes & cur_codes):
        old_name = str(old[code].get("name") or "")
        new_name = str(cur[code].get("security_name") or "")
        if old_name and new_name and old_name != new_name:
            name_changes.append(
                {
                    "security_code": code,
                    "previous_name": old_name,
                    "current_name": new_name,
                }
            )
        old_exchange = str(old[code].get("exchange") or "")
        new_exchange = str(cur[code].get("exchange") or "")
        if old_exchange and new_exchange and old_exchange != new_exchange:
            exchange_changes.append(
                {
                    "security_code": code,
                    "previous_exchange": old_exchange,
                    "current_exchange": new_exchange,
                }
            )
    if exchange_changes:
        errors.append("UNRESOLVED_EXCHANGE_IDENTITY_CHANGES")
    if abs(len(cur) - len(old)) > 80:
        warnings.append("LARGE_UNIVERSE_COUNT_DELTA_REVIEW")

    return {
        "status": "PASS" if not errors else "FAIL",
        "as_of": a.as_of,
        "latest_completed_session": a.latest_completed_session,
        "previous": {
            "records": len(old),
            "sha256": sha256(previous_path),
        },
        "current": {
            "records": len(cur),
            "sha256": sha256(current_path),
            "providers": providers,
            "exchanges": sorted(exchanges),
            "price_fill_ratio": price_fill,
            "volume_fill_ratio": volume_fill,
        },
        "identity_diff": {
            "additions": additions,
            "deletions": deletions,
            "name_changes": name_changes,
            "exchange_changes": exchange_changes,
        },
        "errors": errors,
        "warnings": warnings,
        "permissions": {
            "governed_screening": not errors,
            "automatic_candidate_admission": False,
            "candidate_membership_change": False,
            "orders": False,
            "trade": False,
        },
        "trade_authority": "NONE",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--previous-jsonl", required=True)
    ap.add_argument("--current-csv", required=True)
    ap.add_argument("--as-of", required=True)
    ap.add_argument("--latest-completed-session", required=True)
    ap.add_argument("--expected-provider", required=True)
    ap.add_argument("--expected-min", type=int, default=5400)
    ap.add_argument("--expected-max", type=int, default=5700)
    ap.add_argument("--output", required=True)
    a = ap.parse_args()
    output = Path(a.output)

    try:
        result = execute_gate(a)
    except Exception as exc:
        result = {
            "status": "FAIL",
            "as_of": a.as_of,
            "latest_completed_session": a.latest_completed_session,
            "errors": ["GATE_RUNTIME_EXCEPTION"],
            "warnings": [],
            "runtime_exception": {
                "type": type(exc).__name__,
                "message": str(exc),
            },
            "permissions": {
                "governed_screening": False,
                "automatic_candidate_admission": False,
                "candidate_membership_change": False,
                "orders": False,
                "trade": False,
            },
            "trade_authority": "NONE",
        }
        write_result(output, result)
        raise SystemExit(2) from exc

    write_result(output, result)
    raise SystemExit(0 if result["status"] == "PASS" else 2)


if __name__ == "__main__":
    main()
