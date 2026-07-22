from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import shutil
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

PHASE_ID = "FMDL-6X3-A"
STATUS = "FMDL6X3A_RESEARCH_UNIVERSE_AND_DATA_READINESS_CONTRACT_ACCEPTED"
NEXT_GATE = "FMDL-6X3-B_FINANCIAL_NORMALIZATION_TTM_AND_ANNUAL_METRIC_LAYER"
CONTRACT_PATH = Path("config/fmdl6x3a_research_universe_readiness_contract.json")
ZIP_TIME = (1980, 1, 1, 0, 0, 0)

PROFILE_BY_INSTRUMENT = {
    "COMMON_EQUITY": "STANDARD_OPERATING_COMPANY",
    "REIT_COMMON_OR_BENEFICIAL": "REIT",
    "ADR_OR_ADS": "ADR",
    "PTP_MLP_UNIT": "PASS_THROUGH",
    "ROYALTY_TRUST_UNIT": "PASS_THROUGH",
    "SPAC_COMMON": "SPAC",
    "ETF_OR_EXCHANGE_TRADED_PRODUCT": "ETF_ETP_REFERENCE",
    "CLOSED_END_FUND": "LISTED_FUND_REFERENCE",
    "CLOSED_END_OR_LISTED_FUND": "LISTED_FUND_REFERENCE",
    "PREFERRED_EQUITY": "PREFERRED_REFERENCE",
    "DEBT_SECURITY": "DEBT_REFERENCE",
}
SPECIAL_PROFILES = {"REIT", "ADR", "PASS_THROUGH", "SPAC"}
REFERENCE_PROFILES = {"ETF_ETP_REFERENCE", "LISTED_FUND_REFERENCE", "PREFERRED_REFERENCE", "DEBT_REFERENCE"}


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_path(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def record_hash(namespace: str, *parts: Any) -> str:
    return sha256_bytes((namespace + "|" + "|".join(map(str, parts))).encode("utf-8"))


def bucket_hex(value: str, count: int = 64) -> str:
    return f"{int(sha256_bytes(value.encode('utf-8')), 16) % count:02X}"


def jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    return "".join(stable_json(row) + "\n" for row in rows).encode("utf-8")


def deterministic_gzip(rows: list[dict[str, Any]]) -> bytes:
    output = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=output, mtime=0) as handle:
        handle.write(jsonl_bytes(rows))
    return output.getvalue()


def deterministic_zip(entries: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(entries):
            info = zipfile.ZipInfo(name, ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, entries[name])
    return output.getvalue()


def read_zip_jsonl(path: Path, prefix: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with zipfile.ZipFile(path) as archive:
        for name in sorted(archive.namelist()):
            if name.startswith(prefix) and name.endswith(".jsonl"):
                rows.extend(json.loads(line) for line in archive.read(name).decode("utf-8").splitlines() if line.strip())
    return rows


def validate_contract(repo_root: Path) -> dict[str, Any]:
    contract = read_json(repo_root / CONTRACT_PATH)
    errors: list[str] = []
    if contract.get("phase_id") != PHASE_ID:
        errors.append("PHASE")
    if contract.get("trade_authority") != "NONE":
        errors.append("TRADE")
    if contract.get("required_exit_status") != STATUS:
        errors.append("EXIT")
    if contract.get("next_gate") != NEXT_GATE:
        errors.append("NEXT")
    if any(value != 0 for value in contract.get("zero_mutation_gate", {}).values()):
        errors.append("ZERO_MUTATION")
    if contract["storage_contract"].get("expected_shard_count") != 128:
        errors.append("SHARD_CONTRACT")
    if contract["readiness_contract"].get("full_data_readiness_claimed") is not False:
        errors.append("READINESS_OVERCLAIM")
    if contract["scope"].get("investment_os_candidate_mutation_authorized") is not False:
        errors.append("CANDIDATE_AUTHORITY")
    pointer_path = repo_root / contract["entry_gate"]["pointer_path"]
    if not pointer_path.is_file():
        errors.append("ENTRY_POINTER_MISSING")
    else:
        pointer = read_json(pointer_path)
        mapping = {
            "phase_id": "required_phase_id",
            "release_id": "required_release_id",
            "release_sequence": "required_release_sequence",
            "status": "required_status",
            "next_gate": "required_next_gate",
            "trade_authority": "required_trade_authority",
        }
        for field, required in mapping.items():
            if pointer.get(field) != contract["entry_gate"][required]:
                errors.append("ENTRY_" + field.upper())
    if errors:
        raise RuntimeError("CONTRACT:" + ",".join(sorted(set(errors))))
    return contract


def profile_for(instrument_type: str) -> str:
    return PROFILE_BY_INSTRUMENT.get(instrument_type, "NON_STANDARD_REVIEW")


def research_scope(profile: str, identity_research_status: str) -> str:
    if identity_research_status == "EXCLUDED":
        return "EXCLUDED"
    if profile in REFERENCE_PROFILES or identity_research_status == "REFERENCE_ONLY":
        return "REFERENCE_ONLY"
    if profile == "STANDARD_OPERATING_COMPANY":
        return "STANDARD_RESEARCH_PROFILE"
    if profile in SPECIAL_PROFILES:
        return "SPECIAL_RESEARCH_PROFILE"
    return "REVIEW_REQUIRED"


def readiness_tier(scope: str, market_ready: bool, filing_ready: bool, facts_ready: bool) -> str:
    if scope == "EXCLUDED":
        return "EXCLUDED"
    if scope == "REVIEW_REQUIRED":
        return "INSTRUMENT_PROFILE_REVIEW_REQUIRED"
    if scope == "REFERENCE_ONLY":
        return "REFERENCE_MARKET_READY_NON_DECISION_GRADE" if market_ready else "REFERENCE_DATA_PENDING"
    if facts_ready and market_ready:
        return "READY_FOR_6X3B_FINANCIAL_NORMALIZATION_AND_MARKET_SANDBOX"
    if facts_ready:
        return "READY_FOR_6X3B_FINANCIAL_NORMALIZATION_MARKET_BACKFILL_PENDING"
    if filing_ready and market_ready:
        return "OFFICIAL_FILINGS_READY_FACTS_PENDING_MARKET_SANDBOX"
    if filing_ready:
        return "OFFICIAL_FILINGS_READY_FACTS_AND_MARKET_PENDING"
    if market_ready:
        return "MARKET_SANDBOX_ONLY_SEC_BACKFILL_PENDING"
    return "DATA_BACKFILL_PENDING"


def load_inputs(repo_root: Path, contract: dict[str, Any]) -> dict[str, Any]:
    identity_root = repo_root / contract["input_contract"]["identity_root"]
    market_root = repo_root / contract["input_contract"]["market_root"]
    sec_root = repo_root / contract["input_contract"]["sec_root"]
    full_root = repo_root / contract["input_contract"]["full_store_root"]
    identity_zip = identity_root / "FMDL6X2B_IDENTITY_SHARDS.zip"
    sec_map_zip = sec_root / "FMDL6X2E_ISSUER_CIK_SHARDS.zip"
    sec_filings_zip = sec_root / "FMDL6X2E_FILINGS_SHARDS.zip"
    sec_facts_zip = sec_root / "FMDL6X2E_FACTS_SHARDS.zip"
    return {
        "identity_root": identity_root,
        "market_root": market_root,
        "sec_root": sec_root,
        "full_root": full_root,
        "securities": read_zip_jsonl(identity_zip, "SECURITY/"),
        "listings": read_zip_jsonl(identity_zip, "LISTING/"),
        "issuers": read_zip_jsonl(identity_zip, "ISSUER/"),
        "market_coverage": read_json(market_root / "FMDL6X2D_COVERAGE_REPORT.json"),
        "sec_coverage": read_json(sec_root / "FMDL6X2E_COVERAGE_REPORT.json"),
        "sec_maps": read_zip_jsonl(sec_map_zip, "ISSUER_CIK/"),
        "sec_filings": read_zip_jsonl(sec_filings_zip, "FILINGS/"),
        "sec_facts": read_zip_jsonl(sec_facts_zip, "FACTS/"),
        "full_decision": read_json(full_root / "FMDL6X2_FINAL_DECISION.json"),
        "full_manifest_path": full_root / "FMDL6X2_FINAL_MANIFEST.json",
        "identity_manifest_path": identity_root / "FMDL6X2B_MANIFEST.json",
        "market_manifest_path": market_root / "FMDL6X2D_MANIFEST.json",
        "sec_manifest_path": sec_root / "FMDL6X2E_MANIFEST.json",
    }


def build_records(inputs: dict[str, Any], research_date: str) -> dict[str, Any]:
    securities = sorted(inputs["securities"], key=lambda row: row["canonical_security_id"])
    issuers = sorted(inputs["issuers"], key=lambda row: row["canonical_issuer_id"])
    listings_by_security: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for listing in inputs["listings"]:
        listings_by_security[listing["canonical_security_id"]].append(listing)
    venue_rank = {"XNAS": 0, "XNYS": 1, "XASE": 2}
    primary_listing: dict[str, dict[str, Any]] = {}
    for security_id, rows in listings_by_security.items():
        primary_listing[security_id] = sorted(rows, key=lambda row: (venue_rank.get(row["venue"], 99), row["symbol"], row["canonical_listing_id"]))[0]

    market_by_security = {
        row["canonical_security_id"]: row
        for row in inputs["market_coverage"].get("accepted_security_coverage", [])
    }
    sec_map_by_issuer = {row["canonical_issuer_id"]: row for row in inputs["sec_maps"]}
    filing_count_by_issuer = Counter(row["canonical_issuer_id"] for row in inputs["sec_filings"])
    fact_count_by_issuer = Counter(row["canonical_issuer_id"] for row in inputs["sec_facts"])

    security_rows: list[dict[str, Any]] = []
    queues: dict[str, list[dict[str, Any]]] = {
        "MARKET_HISTORY_BACKFILL_QUEUE": [],
        "SEC_EVIDENCE_BACKFILL_QUEUE": [],
        "INSTRUMENT_PROFILE_REVIEW_QUEUE": [],
        "ADR_PROFILE_RESOLUTION_QUEUE": [],
        "SPECIAL_PROFILE_REVIEW_QUEUE": [],
    }
    securities_by_issuer: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for security in securities:
        sid = security["canonical_security_id"]
        iid = security["canonical_issuer_id"]
        listing = primary_listing.get(sid, {})
        profile = profile_for(security["instrument_type"])
        scope = research_scope(profile, security.get("research_status", "RESEARCH_REVIEW_REQUIRED"))
        market = market_by_security.get(sid)
        sec_map = sec_map_by_issuer.get(iid)
        filing_count = filing_count_by_issuer.get(iid, 0)
        fact_count = fact_count_by_issuer.get(iid, 0)
        market_ready = market is not None
        filing_ready = filing_count > 0
        facts_ready = fact_count > 0
        financial_scope = scope in {"STANDARD_RESEARCH_PROFILE", "SPECIAL_RESEARCH_PROFILE"}
        x3b_gate = (
            "OPEN_OFFICIAL_SEC_FACTS_AVAILABLE"
            if financial_scope and facts_ready
            else "BLOCKED_OFFICIAL_SEC_FACTS_PENDING"
            if financial_scope and filing_ready
            else "BLOCKED_SEC_EVIDENCE_BACKFILL_PENDING"
            if financial_scope
            else "NOT_APPLICABLE"
        )
        x3c_gate = (
            "NOT_APPLICABLE"
            if scope == "EXCLUDED"
            else "SANDBOX_ONLY_NON_DECISION_GRADE"
            if market_ready
            else "BLOCKED_MARKET_BACKFILL_PENDING"
        )
        row = {
            "canonical_security_id": sid,
            "canonical_issuer_id": iid,
            "canonical_share_class_id": security.get("canonical_share_class_id"),
            "canonical_listing_id": listing.get("canonical_listing_id"),
            "symbol": listing.get("symbol") or (security.get("symbols") or [None])[0],
            "venue": listing.get("venue") or (security.get("venues") or [None])[0],
            "official_security_name": security.get("official_security_name"),
            "instrument_type": security["instrument_type"],
            "identity_research_status": security.get("research_status"),
            "research_profile": profile,
            "research_scope": scope,
            "identity_readiness": "SEC_OFFICIAL_CIK_LINKED" if sec_map else "PROVISIONAL_DIRECTORY_ONLY",
            "sec_cik10": sec_map.get("cik10") if sec_map else None,
            "official_filing_count": filing_count,
            "official_fact_count": fact_count,
            "financial_data_readiness": (
                "DECISION_GRADE_OFFICIAL_SEC_FACTS_AVAILABLE"
                if facts_ready
                else "OFFICIAL_SEC_FILINGS_FACTS_PENDING"
                if filing_ready
                else "SEC_OFFICIAL_BACKFILL_PENDING"
            ),
            "market_data_readiness": (
                "NON_DECISION_GRADE_FALLBACK_AVAILABLE"
                if market_ready
                else "MARKET_HISTORY_BACKFILL_PENDING"
            ),
            "market_bar_count": market.get("bar_count", 0) if market else 0,
            "market_first_date": market.get("first_date") if market else None,
            "market_last_date": market.get("last_date") if market else None,
            "x3b_financial_normalization_gate": x3b_gate,
            "x3c_market_factor_gate": x3c_gate,
            "readiness_tier": readiness_tier(scope, market_ready, filing_ready, facts_ready),
            "ready_for_fmdl6x3b": x3b_gate == "OPEN_OFFICIAL_SEC_FACTS_AVAILABLE",
            "research_as_of_date": research_date,
            "candidate_pool_status": "NOT_AUTHORIZED",
            "trade_authority": "NONE",
        }
        security_rows.append(row)
        securities_by_issuer[iid].append(row)

        queue_base = {
            "canonical_security_id": sid,
            "canonical_issuer_id": iid,
            "symbol": row["symbol"],
            "venue": row["venue"],
            "research_profile": profile,
            "research_scope": scope,
        }
        if scope != "EXCLUDED" and not market_ready:
            queues["MARKET_HISTORY_BACKFILL_QUEUE"].append({
                **queue_base,
                "required_action": "COMPLETE_ACCEPTED_MARKET_HISTORY_ROUTE_BEFORE_MARKET_FACTOR_PRODUCTION",
            })
        if financial_scope and not facts_ready:
            queues["SEC_EVIDENCE_BACKFILL_QUEUE"].append({
                **queue_base,
                "required_action": "CAPTURE_OFFICIAL_SEC_CIK_FILINGS_AND_COMPANY_FACTS",
                "filing_available": filing_ready,
            })
        if scope == "REVIEW_REQUIRED":
            queues["INSTRUMENT_PROFILE_REVIEW_QUEUE"].append({
                **queue_base,
                "required_action": "RESOLVE_OFFICIAL_INSTRUMENT_DESCRIPTION_AND_RESEARCH_PROFILE",
            })
        if profile == "ADR":
            queues["ADR_PROFILE_RESOLUTION_QUEUE"].append({
                **queue_base,
                "required_action": "RESOLVE_UNDERLYING_DEPOSITARY_RATIO_AND_REPORTING_CURRENCY",
            })
        if scope == "SPECIAL_RESEARCH_PROFILE":
            queues["SPECIAL_PROFILE_REVIEW_QUEUE"].append({
                **queue_base,
                "required_action": "APPLY_PROFILE_SPECIFIC_NORMALIZATION_AND_COMPARABILITY_RULES",
            })

    issuer_rows: list[dict[str, Any]] = []
    for issuer in issuers:
        iid = issuer["canonical_issuer_id"]
        rows = securities_by_issuer.get(iid, [])
        sec_map = sec_map_by_issuer.get(iid)
        issuer_rows.append({
            "canonical_issuer_id": iid,
            "issuer_display_name": issuer.get("issuer_display_name"),
            "security_count": len(rows),
            "research_profile_counts": dict(sorted(Counter(row["research_profile"] for row in rows).items())),
            "research_scope_counts": dict(sorted(Counter(row["research_scope"] for row in rows).items())),
            "readiness_tier_counts": dict(sorted(Counter(row["readiness_tier"] for row in rows).items())),
            "sec_cik10": sec_map.get("cik10") if sec_map else None,
            "sec_identity_readiness": "SEC_OFFICIAL_CIK_LINKED" if sec_map else "PROVISIONAL_DIRECTORY_ONLY",
            "official_filing_count": filing_count_by_issuer.get(iid, 0),
            "official_fact_count": fact_count_by_issuer.get(iid, 0),
            "ready_security_count_for_fmdl6x3b": sum(row["ready_for_fmdl6x3b"] for row in rows),
            "research_as_of_date": research_date,
            "candidate_pool_status": "NOT_AUTHORIZED",
            "trade_authority": "NONE",
        })

    for rows in queues.values():
        rows.sort(key=stable_json)
    return {
        "security_rows": security_rows,
        "issuer_rows": issuer_rows,
        "queues": queues,
        "market_ids": set(market_by_security),
        "sec_map_ids": set(sec_map_by_issuer),
        "fact_issuer_ids": set(fact_count_by_issuer),
        "filing_issuer_ids": set(filing_count_by_issuer),
    }


def build_shards(
    security_rows: list[dict[str, Any]],
    issuer_rows: list[dict[str, Any]],
    bucket_count: int,
    generated_at: str,
) -> tuple[bytes, list[dict[str, Any]]]:
    entries: dict[str, bytes] = {}
    manifest: list[dict[str, Any]] = []
    for domain, rows, key in (
        ("SECURITY_READINESS", security_rows, "canonical_security_id"),
        ("ISSUER_READINESS", issuer_rows, "canonical_issuer_id"),
    ):
        for index in range(bucket_count):
            bucket = f"{index:02X}"
            shard_rows = [row for row in rows if bucket_hex(str(row[key]), bucket_count) == bucket]
            shard_rows.sort(key=lambda row: str(row[key]))
            name = f"{domain}/{bucket}.jsonl"
            payload = jsonl_bytes(shard_rows)
            entries[name] = payload
            manifest.append({
                "shard_id": f"{domain}-{bucket}",
                "domain": domain,
                "bucket": bucket,
                "row_count": len(shard_rows),
                "payload_sha256": sha256_bytes(payload),
                "generated_at": generated_at,
                "quality_status": "PASS",
            })
    return deterministic_zip(entries), manifest


def build(repo_root: Path, candidate: Path, accepted_at: str, source_commit: str) -> dict[str, Any]:
    contract = validate_contract(repo_root)
    inputs = load_inputs(repo_root, contract)
    records = build_records(inputs, contract["as_of_date"])
    security_rows = records["security_rows"]
    issuer_rows = records["issuer_rows"]

    input_contract = contract["input_contract"]
    errors: list[str] = []
    if len(security_rows) != input_contract["universe_security_count_expected"]:
        errors.append("SECURITY_UNIVERSE")
    if len(issuer_rows) != input_contract["universe_issuer_count_expected"]:
        errors.append("ISSUER_UNIVERSE")
    if len(records["market_ids"]) != input_contract["market_accepted_security_count_expected"]:
        errors.append("MARKET_COVERAGE")
    if len(records["filing_issuer_ids"]) != input_contract["sec_filing_issuer_count_expected"]:
        errors.append("SEC_FILING_COVERAGE")
    if len(records["fact_issuer_ids"]) != input_contract["sec_fact_issuer_count_expected"]:
        errors.append("SEC_FACT_COVERAGE")

    security_ids = {row["canonical_security_id"] for row in security_rows}
    issuer_ids = {row["canonical_issuer_id"] for row in issuer_rows}
    if len(security_ids) != len(security_rows):
        errors.append("DUPLICATE_SECURITY")
    if len(issuer_ids) != len(issuer_rows):
        errors.append("DUPLICATE_ISSUER")
    if not records["market_ids"].issubset(security_ids):
        errors.append("UNKNOWN_MARKET_SECURITY")
    if not records["sec_map_ids"].issubset(issuer_ids):
        errors.append("UNKNOWN_SEC_ISSUER")
    ready_count = sum(row["ready_for_fmdl6x3b"] for row in security_rows)
    if ready_count < input_contract["sec_fact_issuer_count_expected"]:
        errors.append("X3B_READY_MINIMUM")
    if any(row["market_data_readiness"] == "DECISION_GRADE" for row in security_rows):
        errors.append("MARKET_GRADE_PROMOTION")
    if any(row["candidate_pool_status"] != "NOT_AUTHORIZED" or row["trade_authority"] != "NONE" for row in security_rows):
        errors.append("AUTHORITY")
    if any(row["research_as_of_date"] != contract["as_of_date"] for row in security_rows):
        errors.append("AS_OF")

    contract_sha = sha256_path(repo_root / CONTRACT_PATH)
    full_manifest_sha = sha256_path(inputs["full_manifest_path"])
    identity_manifest_sha = sha256_path(inputs["identity_manifest_path"])
    market_manifest_sha = sha256_path(inputs["market_manifest_path"])
    sec_manifest_sha = sha256_path(inputs["sec_manifest_path"])
    release_id = "FMDL6X3A_20260722_" + record_hash(
        "FMDL6X3A_RELEASE",
        contract_sha,
        full_manifest_sha,
        identity_manifest_sha,
        market_manifest_sha,
        sec_manifest_sha,
    )[:12]

    shard_zip, shard_manifest = build_shards(
        security_rows,
        issuer_rows,
        contract["storage_contract"]["bucket_count"],
        accepted_at,
    )
    if len(shard_manifest) != contract["storage_contract"]["expected_shard_count"]:
        errors.append("SHARDS")

    candidate.mkdir(parents=True, exist_ok=True)
    (candidate / "FMDL6X3A_READINESS_SHARDS.zip").write_bytes(shard_zip)
    (candidate / "FMDL6X3A_REVIEW_QUEUES.zip").write_bytes(
        deterministic_zip({name + ".jsonl": jsonl_bytes(rows) for name, rows in records["queues"].items()})
    )
    profile_summary = {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "research_as_of_date": contract["as_of_date"],
        "security_count": len(security_rows),
        "issuer_count": len(issuer_rows),
        "research_profile_counts": dict(sorted(Counter(row["research_profile"] for row in security_rows).items())),
        "research_scope_counts": dict(sorted(Counter(row["research_scope"] for row in security_rows).items())),
        "readiness_tier_counts": dict(sorted(Counter(row["readiness_tier"] for row in security_rows).items())),
        "x3b_gate_counts": dict(sorted(Counter(row["x3b_financial_normalization_gate"] for row in security_rows).items())),
        "x3c_market_gate_counts": dict(sorted(Counter(row["x3c_market_factor_gate"] for row in security_rows).items())),
        "ready_for_fmdl6x3b_count": ready_count,
        "full_security_universe_profiled": True,
        "full_data_readiness_claimed": False,
    }
    write_json(candidate / "FMDL6X3A_PROFILE_SUMMARY.json", profile_summary)

    queue_counts = {name: len(rows) for name, rows in records["queues"].items()}
    coverage = {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "research_as_of_date": contract["as_of_date"],
        "security_universe_count": len(security_rows),
        "issuer_universe_count": len(issuer_rows),
        "market_history_accepted_security_count": len(records["market_ids"]),
        "market_history_data_grade": "NON_DECISION_GRADE_FALLBACK",
        "sec_official_filing_issuer_count": len(records["filing_issuer_ids"]),
        "sec_official_fact_issuer_count": len(records["fact_issuer_ids"]),
        "ready_for_fmdl6x3b_security_count": ready_count,
        "queue_counts": queue_counts,
        "full_security_universe_profiled": True,
        "full_data_readiness_claimed": False,
        "candidate_pool_integration_claimed": False,
    }
    write_json(candidate / "FMDL6X3A_COVERAGE_REPORT.json", coverage)

    quality = {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "quality_status": "FAIL" if errors else "PASS",
        "errors": sorted(set(errors)),
        "security_universe_expected": input_contract["universe_security_count_expected"],
        "security_universe_actual": len(security_rows),
        "issuer_universe_expected": input_contract["universe_issuer_count_expected"],
        "issuer_universe_actual": len(issuer_rows),
        "market_security_expected": input_contract["market_accepted_security_count_expected"],
        "market_security_actual": len(records["market_ids"]),
        "sec_filing_issuer_expected": input_contract["sec_filing_issuer_count_expected"],
        "sec_filing_issuer_actual": len(records["filing_issuer_ids"]),
        "sec_fact_issuer_expected": input_contract["sec_fact_issuer_count_expected"],
        "sec_fact_issuer_actual": len(records["fact_issuer_ids"]),
        "ready_for_fmdl6x3b_count": ready_count,
        "expected_shard_count": contract["storage_contract"]["expected_shard_count"],
        "manifested_shard_count": len(shard_manifest),
        "full_data_readiness_claimed": False,
        "market_data_grade": "NON_DECISION_GRADE_FALLBACK",
        "trade_authority": "NONE",
        "zero_mutation_proof": contract["zero_mutation_gate"],
    }
    write_json(candidate / "FMDL6X3A_QUALITY_REPORT.json", quality)
    if errors:
        raise RuntimeError("QUALITY:" + ",".join(sorted(set(errors))))

    source_binding = {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "full_store_release_id": inputs["full_decision"]["release_id"],
        "full_store_manifest_sha256": full_manifest_sha,
        "identity_manifest_sha256": identity_manifest_sha,
        "market_manifest_sha256": market_manifest_sha,
        "sec_manifest_sha256": sec_manifest_sha,
        "identity_authority": "NASDAQ_TRADER_DIRECTORY_PLUS_SEC_OFFICIAL_PARTIAL_LINKAGE",
        "market_data_grade": "NON_DECISION_GRADE_FALLBACK",
        "sec_data_grade": "DECISION_GRADE_OFFICIAL_SEC",
        "research_as_of_date": contract["as_of_date"],
        "silent_source_substitution": False,
        "neutral_fill_used": False,
    }
    write_json(candidate / "FMDL6X3A_SOURCE_BINDING.json", source_binding)

    decision = {
        "phase_id": PHASE_ID,
        "status": STATUS,
        "release_id": release_id,
        "release_sequence": contract["storage_contract"]["release_sequence"],
        "accepted_at": accepted_at,
        "source_commit": source_commit,
        "input_release_id": inputs["full_decision"]["release_id"],
        "next_gate": NEXT_GATE,
        "research_universe_status": "FULL_SECURITY_UNIVERSE_PROFILED_WITH_EXPLICIT_DATA_READINESS",
        "full_data_readiness_claimed": False,
        "ready_for_fmdl6x3b_security_count": ready_count,
        "research_production_gate": "OPEN_FOR_FMDL6X3B_FINANCIAL_NORMALIZATION_ON_READY_SECURITIES_ONLY",
        "investment_os_candidate_pool_gate": "CLOSED_NOT_AUTHORIZED_IN_FMDL6X3A",
        "simulation_gate": "CLOSED_NOT_AUTHORIZED_IN_FMDL6X3A",
        "brokerage_real_account_gate": "CLOSED_NO_CHANNEL",
        "trade_authority": "NONE",
        "zero_mutation_proof": contract["zero_mutation_gate"],
    }
    write_json(candidate / "FMDL6X3A_DECISION.json", decision)

    files = {
        path.name: {"bytes": path.stat().st_size, "sha256": sha256_path(path)}
        for path in sorted(candidate.iterdir())
        if path.is_file() and path.name != "FMDL6X3A_MANIFEST.json"
    }
    manifest = {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "release_sequence": contract["storage_contract"]["release_sequence"],
        "generated_at": accepted_at,
        "contract_sha256": contract_sha,
        "input_manifest_sha256": {
            "full_store": full_manifest_sha,
            "identity": identity_manifest_sha,
            "market_reference": market_manifest_sha,
            "sec_filings_facts": sec_manifest_sha,
        },
        "files": files,
        "shards": shard_manifest,
    }
    write_json(candidate / "FMDL6X3A_MANIFEST.json", manifest)
    return {"decision": decision, "quality": quality, "coverage": coverage, "profile_summary": profile_summary}


def validate_candidate(
    repo_root: Path,
    candidate: Path,
    accepted_at: str,
    source_commit: str,
    acceptance: Path,
) -> dict[str, Any]:
    replay = candidate.parent / (candidate.name + "_replay")
    if replay.exists():
        shutil.rmtree(replay)
    build(repo_root, replay, accepted_at, source_commit)
    candidate_files = {path.name: sha256_path(path) for path in candidate.iterdir() if path.is_file()}
    replay_files = {path.name: sha256_path(path) for path in replay.iterdir() if path.is_file()}
    if candidate_files != replay_files:
        raise RuntimeError("CAPTURED_INPUT_REPLAY_FAILED")
    decision = read_json(candidate / "FMDL6X3A_DECISION.json")
    result = {
        "phase_id": PHASE_ID,
        "status": "PASS",
        "release_id": decision["release_id"],
        "same_input_byte_replay": True,
        "file_sha256": candidate_files,
        "trade_authority": "NONE",
    }
    write_json(acceptance, result)
    return result


def copy_tree(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def publish(repo_root: Path, candidate: Path, published_at: str, source_commit: str) -> dict[str, Any]:
    contract = read_json(repo_root / CONTRACT_PATH)
    decision = read_json(candidate / "FMDL6X3A_DECISION.json")
    release_id = decision["release_id"]
    current = repo_root / contract["storage_contract"]["current_root"]
    release = repo_root / f"datasets/fmdl6x3/releases/{release_id}/research_universe_readiness"
    normalized = repo_root / f"datasets/fmdl6x3/normalized/research_universe_readiness/{release_id}"
    archive_root = repo_root / contract["storage_contract"]["archive_root"]

    incoming = {path.name: sha256_path(path) for path in candidate.iterdir() if path.is_file()}
    if release.exists():
        existing = {path.name: sha256_path(path) for path in release.iterdir() if path.is_file()}
        if existing != incoming:
            raise RuntimeError("IMMUTABLE_RELEASE_COLLISION")
    if current.exists():
        old = read_json(current / "FMDL6X3A_DECISION.json")
        archive = archive_root / old["release_id"] / "research_universe_readiness"
        if not archive.exists():
            copy_tree(current, archive)
    if not release.exists():
        copy_tree(candidate, release)
    copy_tree(candidate, normalized)
    copy_tree(candidate, current)

    for name in ("FMDL6X3A_DECISION.json", "FMDL6X3A_MANIFEST.json"):
        if (current / name).read_bytes() != (release / name).read_bytes():
            raise RuntimeError("CURRENT_RELEASE_PARITY_FAILED")

    manifest_sha = sha256_path(current / "FMDL6X3A_MANIFEST.json")
    pointer = {
        "phase_id": PHASE_ID,
        "status": STATUS,
        "published_at": published_at,
        "source_commit": source_commit,
        "release_id": release_id,
        "release_sequence": contract["storage_contract"]["release_sequence"],
        "current_path": contract["storage_contract"]["current_root"],
        "release_path": f"datasets/fmdl6x3/releases/{release_id}/research_universe_readiness",
        "normalized_path": f"datasets/fmdl6x3/normalized/research_universe_readiness/{release_id}",
        "manifest_sha256": manifest_sha,
        "input_release_id": decision["input_release_id"],
        "research_universe_status": decision["research_universe_status"],
        "full_data_readiness_claimed": False,
        "ready_for_fmdl6x3b_security_count": decision["ready_for_fmdl6x3b_security_count"],
        "next_gate": NEXT_GATE,
        "research_production_gate": decision["research_production_gate"],
        "investment_os_candidate_pool_gate": decision["investment_os_candidate_pool_gate"],
        "brokerage_real_account_gate": "CLOSED_NO_CHANNEL",
        "trade_authority": "NONE",
        "zero_mutation_proof": decision["zero_mutation_proof"],
    }
    write_json(repo_root / contract["storage_contract"]["last_success"], pointer)
    lkg = dict(pointer)
    lkg["lkg_scope"] = "FMDL6X3_RESEARCH_UNIVERSE_AND_READINESS_DOMAIN"
    lkg["lkg_reason"] = "LATEST_ACCEPTED_PROFILED_UNIVERSE_WITH_EXPLICIT_READINESS"
    write_json(repo_root / contract["storage_contract"]["last_known_good"], lkg)
    return pointer


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate-contract")
    build_parser = sub.add_parser("build")
    build_parser.add_argument("--candidate", required=True)
    build_parser.add_argument("--accepted-at", required=True)
    build_parser.add_argument("--source-commit", required=True)
    validate_parser = sub.add_parser("validate-candidate")
    validate_parser.add_argument("--candidate", required=True)
    validate_parser.add_argument("--accepted-at", required=True)
    validate_parser.add_argument("--source-commit", required=True)
    validate_parser.add_argument("--acceptance", required=True)
    publish_parser = sub.add_parser("publish")
    publish_parser.add_argument("--candidate", required=True)
    publish_parser.add_argument("--published-at", required=True)
    publish_parser.add_argument("--source-commit", required=True)
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    if args.command == "validate-contract":
        validate_contract(root)
    elif args.command == "build":
        build(root, root / args.candidate, args.accepted_at, args.source_commit)
    elif args.command == "validate-candidate":
        validate_candidate(root, root / args.candidate, args.accepted_at, args.source_commit, root / args.acceptance)
    elif args.command == "publish":
        publish(root, root / args.candidate, args.published_at, args.source_commit)


if __name__ == "__main__":
    main()
