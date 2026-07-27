#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


UNIFIED = "outputs/fmdl3e/operational/current/FMDL3EFINAL_UNIFIED_CURRENT.parquet"
CANDIDATE = "investment_os_runtime/30_STATE_CURRENT/40_CANDIDATE/CANDIDATE_CURRENT.json"
POSITION_REVIEW = "investment_os_runtime/30_STATE_CURRENT/60_DECISIONS/WP5_POSITION_REVIEW_CURRENT.json"
WORKPLAN = "investment_os_runtime/00_CONTROL/WP5_P0_REUNDERWRITE_WORKPLAN_CURRENT.json"
OUTPUT = "investment_os_runtime/40_EVIDENCE_AND_LINEAGE/WP5/P0_REUNDERWRITE/WP5_P0_INTERNAL_EVIDENCE_INVENTORY_CURRENT.json"
P0 = {
    "300124.SZ": "汇川技术",
    "300750.SZ": "宁德时代",
    "601138.SH": "工业富联",
}


def read_json(root: Path, relative: str) -> dict[str, Any]:
    return json.loads((root / relative).read_text(encoding="utf-8"))


def write_json(root: Path, relative: str, payload: dict[str, Any]) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def clean(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if hasattr(value, "item"):
        try:
            return clean(value.item())
        except Exception:
            pass
    text = str(value)
    return text


def normalize_id(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().upper()
    if not text or text == "NAN":
        return None
    text = text.replace("XSHG", "SH").replace("XSHE", "SZ")
    if "." in text:
        left, right = text.split(".", 1)
        if left.isdigit():
            return f"{left.zfill(6)}.{right}"
        if right.isdigit():
            return f"{right.zfill(6)}.{left}"
    digits = "".join(char for char in text if char.isdigit())
    if len(digits) >= 6:
        code = digits[-6:]
        suffix = "SH" if code.startswith(("5", "6")) else "SZ"
        return f"{code}.{suffix}"
    return None


def find_id_column(frame: pd.DataFrame) -> str:
    preferred = [
        "security_id", "symbol", "ticker", "ts_code", "stock_code", "security_code", "code",
    ]
    lower = {str(column).lower(): str(column) for column in frame.columns}
    for key in preferred:
        if key in lower:
            return lower[key]
    for column in frame.columns:
        name = str(column).lower()
        if "code" in name or "symbol" in name or "ticker" in name:
            return str(column)
    raise KeyError("WP5_P0_SECURITY_ID_COLUMN_NOT_FOUND")


def field_group(name: str) -> str:
    text = name.lower()
    if any(token in text for token in ("period", "report", "date", "as_of", "publish", "announce")):
        return "period_and_lineage"
    if any(token in text for token in ("roe", "roa", "roic", "margin", "profit", "revenue", "income", "eps", "growth")):
        return "profitability_and_growth"
    if any(token in text for token in ("cash", "fcf", "cfo", "receiv", "inventory", "working_capital", "capex")):
        return "cash_flow_and_balance_sheet"
    if any(token in text for token in ("pe", "pb", "ps", "ev", "valuation", "market_cap", "price", "yield")):
        return "valuation_and_market"
    if any(token in text for token in ("quality", "rank", "score", "factor", "eligib", "missing", "fresh")):
        return "quality_and_screening"
    if any(token in text for token in ("industry", "sector", "board", "exchange", "name", "code", "symbol", "security")):
        return "identity_and_classification"
    return "other"


def select_row(frame: pd.DataFrame, id_column: str, sid: str) -> dict[str, Any]:
    normalized = frame[id_column].map(normalize_id)
    matched = frame.loc[normalized == sid]
    if matched.empty:
        return {"found": False, "non_null_field_count": 0, "fields_by_group": {}}
    row = matched.iloc[0]
    groups: dict[str, dict[str, Any]] = {}
    for column in frame.columns:
        value = clean(row[column])
        if value is None or value == "":
            continue
        group = field_group(str(column))
        groups.setdefault(group, {})[str(column)] = value
    return {
        "found": True,
        "matched_row_count": int(len(matched)),
        "non_null_field_count": sum(len(values) for values in groups.values()),
        "fields_by_group": {key: dict(sorted(values.items())) for key, values in sorted(groups.items())},
    }


def record_sid(record: dict[str, Any]) -> str | None:
    for key in ("security_id", "symbol", "ticker", "ts_code", "stock_code", "security_code", "code"):
        if key in record:
            sid = normalize_id(record[key])
            if sid:
                return sid
    return None


def collect_candidate_records(node: Any, path: str = "$") -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if isinstance(node, dict):
        sid = record_sid(node)
        if sid in P0:
            records.append({"path": path, "security_id": sid, "record": node})
        for key, value in node.items():
            records.extend(collect_candidate_records(value, f"{path}.{key}"))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            records.extend(collect_candidate_records(value, f"{path}[{index}]"))
    return records


def missing_dimension_flags(fields: dict[str, Any]) -> list[str]:
    groups = fields.get("fields_by_group", {})
    flags = []
    for group in (
        "period_and_lineage",
        "profitability_and_growth",
        "cash_flow_and_balance_sheet",
        "valuation_and_market",
        "quality_and_screening",
    ):
        if not groups.get(group):
            flags.append(f"NO_INTERNAL_{group.upper()}_FIELDS")
    if not fields.get("found"):
        flags.append("NOT_FOUND_IN_FMDL3E_UNIFIED_CURRENT")
    return flags


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()

    frame = pd.read_parquet(root / UNIFIED)
    id_column = find_id_column(frame)
    candidate = read_json(root, CANDIDATE)
    review = read_json(root, POSITION_REVIEW)
    workplan = read_json(root, WORKPLAN)
    candidate_records = collect_candidate_records(candidate)
    candidate_by_sid: dict[str, list[dict[str, Any]]] = {sid: [] for sid in P0}
    for record in candidate_records:
        candidate_by_sid[record["security_id"]].append(record)
    position_by_sid = {row["security_id"]: row for row in review["simulation"]["positions"]}
    workplan_by_sid = {row["security_id"]: row for row in workplan["research_objects"]}

    objects: dict[str, Any] = {}
    for sid, name in P0.items():
        factor_record = select_row(frame, id_column, sid)
        objects[sid] = {
            "security_id": sid,
            "security_name": name,
            "position_review": position_by_sid[sid],
            "workplan": workplan_by_sid[sid],
            "fmdl3e_internal_record": factor_record,
            "candidate_current_records": candidate_by_sid[sid],
            "candidate_record_count": len(candidate_by_sid[sid]),
            "internal_evidence_gap_flags": missing_dimension_flags(factor_record),
            "research_status": "INTERNAL_EVIDENCE_INVENTORIED_EXTERNAL_PRIMARY_SOURCE_REUNDERWRITE_PENDING",
        }

    output = {
        "inventory_id": "WP5_P0_INTERNAL_EVIDENCE_INVENTORY_V1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "INTERNAL_EVIDENCE_INVENTORY_COMPLETE_EXTERNAL_PRIMARY_SOURCE_REUNDERWRITE_PENDING",
        "source_unified_path": UNIFIED,
        "source_unified_rows": int(len(frame)),
        "source_unified_columns": int(len(frame.columns)),
        "security_id_column": id_column,
        "objects": objects,
        "summary": {
            "p0_object_count": len(objects),
            "fmdl3e_found_count": sum(bool(item["fmdl3e_internal_record"]["found"]) for item in objects.values()),
            "candidate_record_count": sum(item["candidate_record_count"] for item in objects.values()),
            "implementation_ready_count": 0,
            "orders": 0,
        },
        "economic_mutations": {"real_account": 0, "simulation": 0, "candidate_membership": 0, "orders": 0},
        "trade_authority": "NONE",
    }
    write_json(root, OUTPUT, output)
    print(output["summary"])


if __name__ == "__main__":
    main()
