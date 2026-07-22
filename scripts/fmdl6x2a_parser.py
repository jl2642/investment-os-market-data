from __future__ import annotations

from collections import Counter
from typing import Any

from fmdl6x2a_common import normalize_flag, record_hash, sha256_bytes

def parse_pipe_source(route: dict[str, Any], payload: bytes, meta: dict[str, Any], contract: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    text = payload.decode("utf-8-sig", errors="strict")
    physical_lines = text.splitlines()
    nonblank = [(i + 1, line) for i, line in enumerate(physical_lines) if line.strip()]
    if not nonblank:
        raise ValueError(route["route_id"] + ": EMPTY_SOURCE")
    header_line_no, header_line = nonblank[0]
    header = header_line.split("|")
    if header != route["expected_header"]:
        raise ValueError(route["route_id"] + f": HEADER_MISMATCH {header}")
    rows, ledger = [], []
    footer_count = 0
    for line_no, line in nonblank[1:]:
        source_row_id = f"{meta['snapshot_id']}:{line_no}"
        if line.startswith(contract["source_contract"]["footer_prefix"]):
            footer_count += 1
            ledger.append({
                "source_row_id": source_row_id, "route_id": route["route_id"], "snapshot_id": meta["snapshot_id"],
                "line_number": line_no, "row_kind": "FOOTER", "row_disposition": "ACCOUNTED_METADATA",
                "raw_line_sha256": sha256_bytes(line.encode()), "reason": "OFFICIAL_FILE_CREATION_TIME_FOOTER",
            })
            continue
        fields = line.split("|")
        if len(fields) == len(header) + 1 and fields[-1] == "":
            fields = fields[:-1]
        if len(fields) != len(header):
            rows.append({
                "_source_row_id": source_row_id, "_route_id": route["route_id"], "_snapshot_id": meta["snapshot_id"],
                "_line_number": line_no, "_parse_error": "COLUMN_COUNT_MISMATCH",
                "_raw_line_sha256": sha256_bytes(line.encode()),
            })
            continue
        row = dict(zip(header, fields))
        row.update({
            "_source_row_id": source_row_id, "_route_id": route["route_id"], "_snapshot_id": meta["snapshot_id"],
            "_line_number": line_no, "_raw_line_sha256": sha256_bytes(line.encode()),
        })
        rows.append(row)
    return rows, ledger, {
        "route_id": route["route_id"], "header_line_number": header_line_no, "header": header,
        "physical_line_count": len(physical_lines), "nonblank_line_count": len(nonblank),
        "logical_data_row_count": len(rows), "footer_count": footer_count,
    }

def classify_preliminary(row: dict[str, Any], source_type: str, contract: dict[str, Any]) -> tuple[str, str]:
    rules = contract["record_contract"]["preliminary_classification_rules"]
    if normalize_flag(row.get("Test Issue")):
        rule = rules["TEST_ISSUE_Y"]
    elif normalize_flag(row.get("ETF")):
        rule = rules["ETF_Y"]
    elif source_type == "NASDAQ" and normalize_flag(row.get("NextShares")):
        rule = rules["NEXTSHARES_Y"]
    else:
        rule = rules["DEFAULT"]
    return rule["instrument_type"], rule["research_status"]

def normalize_rows(contract: dict[str, Any], parsed: list[tuple[dict[str, Any], str]], observation_date: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    provisional, exclusions, quarantine, ledger = [], [], [], []
    exchange_map = contract["source_contract"]["otherlisted_exchange_map"]
    for row, source_type in parsed:
        base = {
            "source_row_id": row["_source_row_id"], "route_id": row["_route_id"],
            "snapshot_id": row["_snapshot_id"], "line_number": row["_line_number"],
            "raw_line_sha256": row["_raw_line_sha256"],
        }
        if row.get("_parse_error"):
            item = {**base, "reason": row["_parse_error"]}
            quarantine.append(item)
            ledger.append({**item, "row_kind": "DATA", "row_disposition": "QUARANTINED"})
            continue
        source_exchange_code = None
        if source_type == "NASDAQ":
            symbol, venue = row.get("Symbol", "").strip(), "XNAS"
        else:
            symbol = row.get("ACT Symbol", "").strip()
            source_exchange_code = row.get("Exchange", "").strip().upper()
            mapping = exchange_map.get(source_exchange_code)
            if not mapping:
                item = {**base, "symbol": symbol, "security_name": row.get("Security Name", ""),
                        "source_exchange_code": source_exchange_code, "reason": "UNKNOWN_EXCHANGE_CODE"}
                quarantine.append(item)
                ledger.append({**item, "row_kind": "DATA", "row_disposition": "QUARANTINED"})
                continue
            venue = mapping["venue"]
            if not mapping["target"]:
                item = {**base, "symbol": symbol, "security_name": row.get("Security Name", ""),
                        "source_exchange_code": source_exchange_code, "venue": venue, "reason": "NON_TARGET_VENUE"}
                exclusions.append(item)
                ledger.append({**item, "row_kind": "DATA", "row_disposition": "EXCLUDED"})
                continue
        security_name = row.get("Security Name", "").strip()
        if not symbol or not security_name:
            item = {**base, "symbol": symbol, "security_name": security_name, "venue": venue,
                    "reason": "MISSING_REQUIRED_SYMBOL_OR_SECURITY_NAME"}
            quarantine.append(item)
            ledger.append({**item, "row_kind": "DATA", "row_disposition": "QUARANTINED"})
            continue
        instrument_type, research_status = classify_preliminary(row, source_type, contract)
        provisional_id = "USOBS-" + record_hash("SECURITY_OBSERVATION", venue, symbol, security_name)[:24]
        provisional.append({
            "provisional_security_record_id": provisional_id,
            "canonical_security_id": None, "canonical_issuer_id": None, "canonical_share_class_id": None,
            "canonical_listing_id": None, "identity_resolution_status": "PENDING_FMDL6X2B",
            "venue": venue, "symbol": symbol, "official_security_name": security_name,
            "active_listing_observation_key": f"{venue}|{symbol}",
            "listing_lifecycle_status": "ACTIVE_LISTED_OBSERVED",
            "observation_date": observation_date, "effective_date_confidence": "OBSERVATION_ONLY",
            "instrument_type_preliminary": instrument_type, "research_status": research_status,
            "channel_status": "CHANNEL_ELIGIBILITY_PENDING",
            "portfolio_status": "PORTFOLIO_ADMISSION_NOT_AUTHORIZED",
            "test_issue": normalize_flag(row.get("Test Issue")), "etf_flag": normalize_flag(row.get("ETF")),
            "nextshares_flag": normalize_flag(row.get("NextShares")),
            "market_category": row.get("Market Category") or None,
            "financial_status": row.get("Financial Status") or None,
            "round_lot_size": row.get("Round Lot Size") or None,
            "cqs_symbol": row.get("CQS Symbol") or None, "nasdaq_symbol": row.get("NASDAQ Symbol") or None,
            "source_exchange_code": source_exchange_code, "source_route_id": row["_route_id"],
            "source_snapshot_id": row["_snapshot_id"], "source_line_number": row["_line_number"],
            "source_row_id": row["_source_row_id"], "source_row_sha256": row["_raw_line_sha256"],
            "source_authority": "NASDAQ_OFFICIAL", "row_disposition": "INCLUDED", "trade_authority": "NONE",
        })
    id_counts = Counter(r["provisional_security_record_id"] for r in provisional)
    key_counts = Counter(r["active_listing_observation_key"] for r in provisional)
    included = []
    for record in provisional:
        reason = None
        if id_counts[record["provisional_security_record_id"]] > 1:
            reason = "DUPLICATE_PROVISIONAL_SECURITY_RECORD_ID"
        if key_counts[record["active_listing_observation_key"]] > 1:
            reason = "DUPLICATE_ACTIVE_LISTING_KEY"
        if reason:
            item = {
                "source_row_id": record["source_row_id"], "route_id": record["source_route_id"],
                "snapshot_id": record["source_snapshot_id"], "line_number": record["source_line_number"],
                "symbol": record["symbol"], "security_name": record["official_security_name"],
                "venue": record["venue"], "reason": reason,
                "provisional_security_record_id": record["provisional_security_record_id"],
                "active_listing_observation_key": record["active_listing_observation_key"],
                "raw_line_sha256": record["source_row_sha256"],
            }
            quarantine.append(item)
            ledger.append({**item, "row_kind": "DATA", "row_disposition": "QUARANTINED"})
        else:
            included.append(record)
            ledger.append({
                "source_row_id": record["source_row_id"], "route_id": record["source_route_id"],
                "snapshot_id": record["source_snapshot_id"], "line_number": record["source_line_number"],
                "row_kind": "DATA", "row_disposition": "INCLUDED", "venue": record["venue"],
                "symbol": record["symbol"], "provisional_security_record_id": record["provisional_security_record_id"],
                "raw_line_sha256": record["source_row_sha256"],
            })
    return included, exclusions, quarantine, ledger
