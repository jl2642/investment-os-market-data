from __future__ import annotations

import hashlib
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

from fmdl6x2a_common import (
    CONTRACT_PATH, EXIT_STATUS, NEXT_GATE, PHASE_ID, deterministic_gzip,
    deterministic_zip, load_json, pretty_json, read_gzip_jsonl, sha256_bytes,
    sha256_file, stable_json, validate_contract, write_json,
)
from fmdl6x2a_parser import normalize_rows, parse_pipe_source

def build_candidate(repo_root: Path, raw_root: Path, candidate_root: Path, accepted_at: str, source_commit: str) -> dict[str, Any]:
    contract = load_json(repo_root / CONTRACT_PATH)
    if candidate_root.exists():
        shutil.rmtree(candidate_root)
    candidate_root.mkdir(parents=True)
    source_summary = load_json(raw_root / "SOURCE_SNAPSHOTS.json")
    meta_by_route = {x["route_id"]: x for x in source_summary["snapshots"]}
    parsed_all, ledger, parse_reports = [], [], []
    raw_files: dict[str, bytes] = {}
    for route in contract["source_contract"]["routes"]:
        filename = route["route_id"].lower() + ".txt"
        payload = (raw_root / filename).read_bytes()
        raw_files["raw/" + filename] = payload
        raw_files["raw/" + filename + ".meta.json"] = (raw_root / (filename + ".meta.json")).read_bytes()
        rows, source_ledger, report = parse_pipe_source(route, payload, meta_by_route[route["route_id"]], contract)
        ledger.extend(source_ledger)
        source_type = "NASDAQ" if route["route_id"].endswith("NASDAQLISTED") else "OTHER"
        parsed_all.extend((row, source_type) for row in rows)
        parse_reports.append(report)
    observation_date = min(x["retrieved_at"][:10] for x in source_summary["snapshots"])
    included, exclusions, quarantine, normalized_ledger = normalize_rows(contract, parsed_all, observation_date)
    ledger.extend(normalized_ledger)
    ledger.sort(key=lambda x: (x["route_id"], int(x["line_number"])))
    included.sort(key=lambda x: (x["venue"], x["symbol"], x["provisional_security_record_id"]))
    exclusions.sort(key=lambda x: (x["route_id"], int(x["line_number"])))
    quarantine.sort(key=lambda x: (x["route_id"], int(x["line_number"])))

    bucket_count = contract["storage_contract"]["bucket_count"]
    shard_records = {(v, b): [] for v in contract["storage_contract"]["venues"] for b in range(bucket_count)}
    for record in included:
        bucket = int(hashlib.sha256(record["provisional_security_record_id"].encode()).hexdigest(), 16) % bucket_count
        shard_records[(record["venue"], bucket)].append(record)
    zip_entries: dict[str, bytes] = {}
    shard_manifest = []
    for venue in contract["storage_contract"]["venues"]:
        for bucket in range(bucket_count):
            records = shard_records[(venue, bucket)]
            payload = "".join(stable_json(r) + "\n" for r in records).encode()
            name = f"{venue}/{bucket:02X}.jsonl"
            zip_entries[name] = payload
            shard_manifest.append({
                "domain": "SECURITY_MASTER", "shard_id": f"{venue}-{bucket:02X}",
                "venue": venue, "bucket": f"{bucket:02X}",
                "source_snapshot_ids": sorted({r["source_snapshot_id"] for r in records}),
                "schema_version": "fmdl6x2a.security_master.v1", "row_count": len(records),
                "min_effective_date": None, "max_effective_date": None,
                "observation_date": observation_date, "payload_sha256": sha256_bytes(payload),
                "generated_at": accepted_at, "quality_status": "PASS", "zip_member": name,
            })

    contract_sha = sha256_file(repo_root / CONTRACT_PATH)
    release_seed = {
        "accepted_at": accepted_at, "contract_sha256": contract_sha,
        "source_payloads": sorted((x["route_id"], x["payload_sha256"]) for x in source_summary["snapshots"]),
    }
    release_hash = sha256_bytes(stable_json(release_seed).encode())
    release_id = f"FMDL6X2A_{accepted_at[:10].replace('-', '')}_{release_hash[:12]}"
    assets: dict[str, bytes] = dict(raw_files)
    assets["FMDL6X2A_SECURITY_MASTER_SHARDS.zip"] = deterministic_zip(zip_entries)
    assets["FMDL6X2A_ROW_ACCOUNTING.jsonl.gz"] = deterministic_gzip(ledger)
    assets["FMDL6X2A_EXCLUSIONS.jsonl.gz"] = deterministic_gzip(exclusions)
    assets["FMDL6X2A_QUARANTINE.jsonl.gz"] = deterministic_gzip(quarantine)
    assets["FMDL6X2A_SOURCE_SNAPSHOTS.json"] = pretty_json({
        "phase_id": PHASE_ID, "release_id": release_id, "captured_at": source_summary["captured_at"],
        "source_count": len(source_summary["snapshots"]), "sources": source_summary["snapshots"],
        "parse_reports": parse_reports, "silent_source_substitution": False,
    }).encode()

    counts_by_venue = Counter(r["venue"] for r in included)
    dispositions = Counter(x["row_disposition"] for x in ledger)
    logical_rows = sum(x["logical_data_row_count"] + x["footer_count"] for x in parse_reports)
    quality = {
        "phase_id": PHASE_ID, "release_id": release_id, "quality_status": "PASS",
        "source_count": len(source_summary["snapshots"]), "source_parse_reports": parse_reports,
        "logical_source_rows_expected": logical_rows, "logical_source_rows_accounted": len(ledger),
        "row_accounting_percent": round((len(ledger) / logical_rows) * 100, 8) if logical_rows else 0,
        "row_dispositions": dict(sorted(dispositions.items())),
        "included_security_records": len(included), "included_by_venue": dict(sorted(counts_by_venue.items())),
        "excluded_rows": len(exclusions), "quarantined_rows": len(quarantine),
        "duplicate_provisional_security_record_ids": len(included) - len({r["provisional_security_record_id"] for r in included}),
        "duplicate_active_listing_keys": len(included) - len({r["active_listing_observation_key"] for r in included}),
        "manifested_shard_count": len(shard_manifest),
        "expected_shard_count": len(contract["storage_contract"]["venues"]) * bucket_count,
        "canonical_security_ids_issued": 0, "trade_authority": "NONE",
        "zero_mutation_proof": contract["zero_mutation_gate"],
    }
    required_pass = (
        quality["source_count"] == 2
        and all(r["footer_count"] == 1 for r in parse_reports)
        and quality["logical_source_rows_accounted"] == quality["logical_source_rows_expected"]
        and quality["row_accounting_percent"] == 100
        and quality["duplicate_provisional_security_record_ids"] == 0
        and quality["duplicate_active_listing_keys"] == 0
        and quality["manifested_shard_count"] == quality["expected_shard_count"] == 192
    )
    quality["quality_status"] = "PASS" if required_pass else "FAIL"
    assets["FMDL6X2A_QUALITY_REPORT.json"] = pretty_json(quality).encode()
    decision = {
        "phase_id": PHASE_ID, "status": EXIT_STATUS if required_pass else "FMDL6X2A_CANDIDATE_REJECTED",
        "release_id": release_id, "release_sequence": contract["storage_contract"]["release_sequence"],
        "accepted_at": accepted_at, "source_commit": source_commit, "observation_date": observation_date,
        "included_security_records": len(included), "included_by_venue": dict(sorted(counts_by_venue.items())),
        "excluded_rows": len(exclusions), "quarantined_rows": len(quarantine),
        "source_row_accounting_percent": quality["row_accounting_percent"],
        "canonical_security_ids_issued": 0, "identity_resolution_status": "PENDING_FMDL6X2B",
        "research_production_gate": "OPEN_FOR_FMDL6X2_DATA_PRODUCTION",
        "brokerage_real_account_gate": "CLOSED_NO_CHANNEL",
        "channel_eligibility_default": "CHANNEL_ELIGIBILITY_PENDING",
        "portfolio_admission_default": "PORTFOLIO_ADMISSION_NOT_AUTHORIZED",
        "trade_authority": "NONE", "next_gate": NEXT_GATE,
        "zero_mutation_proof": contract["zero_mutation_gate"],
    }
    assets["FMDL6X2A_DECISION.json"] = pretty_json(decision).encode()
    manifest = {
        "phase_id": PHASE_ID, "release_id": release_id,
        "release_sequence": contract["storage_contract"]["release_sequence"],
        "generated_at": accepted_at, "contract_sha256": contract_sha,
        "shards": shard_manifest, "files": {},
    }
    for rel, payload in assets.items():
        path = candidate_root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        manifest["files"][rel] = {"bytes": len(payload), "sha256": sha256_bytes(payload)}
    (candidate_root / "FMDL6X2A_MANIFEST.json").write_bytes(pretty_json(manifest).encode())
    return {"release_id": release_id, "quality_status": quality["quality_status"], "decision": decision, "quality": quality}

def compare_directories(a: Path, b: Path) -> list[str]:
    files_a = sorted(p.relative_to(a).as_posix() for p in a.rglob("*") if p.is_file())
    files_b = sorted(p.relative_to(b).as_posix() for p in b.rglob("*") if p.is_file())
    if files_a != files_b:
        return ["FILE_SET_MISMATCH"]
    return ["BYTE_MISMATCH:" + rel for rel in files_a if (a / rel).read_bytes() != (b / rel).read_bytes()]

def validate_candidate(repo_root: Path, raw_root: Path, candidate_root: Path, accepted_at: str, source_commit: str, acceptance_path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    checks, errors = validate_contract(repo_root)
    required_files = [
        "FMDL6X2A_SECURITY_MASTER_SHARDS.zip", "FMDL6X2A_ROW_ACCOUNTING.jsonl.gz",
        "FMDL6X2A_EXCLUSIONS.jsonl.gz", "FMDL6X2A_QUARANTINE.jsonl.gz",
        "FMDL6X2A_SOURCE_SNAPSHOTS.json", "FMDL6X2A_QUALITY_REPORT.json",
        "FMDL6X2A_DECISION.json", "FMDL6X2A_MANIFEST.json",
        "raw/nasdaq_trader_nasdaqlisted.txt", "raw/nasdaq_trader_otherlisted.txt",
    ]
    def check(cid: str, condition: bool, actual: Any = None, expected: Any = None) -> None:
        checks.append({"check_id": cid, "status": "PASS" if condition else "FAIL", "actual": actual, "expected": expected})
        if not condition:
            errors.append(cid)
    for rel in required_files:
        check("FILE_" + rel.replace("/", "_").upper(), (candidate_root / rel).is_file(), rel, "existing file")
    if errors:
        write_json(acceptance_path, {"phase_id": PHASE_ID, "status": "FAIL", "checks": checks, "errors": sorted(set(errors))})
        return checks, sorted(set(errors))
    manifest = load_json(candidate_root / "FMDL6X2A_MANIFEST.json")
    quality = load_json(candidate_root / "FMDL6X2A_QUALITY_REPORT.json")
    decision = load_json(candidate_root / "FMDL6X2A_DECISION.json")
    check("QUALITY_PASS", quality.get("quality_status") == "PASS")
    check("DECISION_ACCEPTED", decision.get("status") == EXIT_STATUS)
    check("RELEASE_IDS_MATCH", manifest.get("release_id") == quality.get("release_id") == decision.get("release_id"))
    check("ROW_ACCOUNTING_100", quality.get("row_accounting_percent") == 100)
    check("SHARD_COUNT_192", quality.get("manifested_shard_count") == 192)
    check("NO_DUPLICATE_IDS", quality.get("duplicate_provisional_security_record_ids") == 0)
    check("NO_DUPLICATE_LISTING_KEYS", quality.get("duplicate_active_listing_keys") == 0)
    check("ZERO_CANONICAL_IDS", quality.get("canonical_security_ids_issued") == 0)
    check("TRADE_AUTHORITY_NONE", decision.get("trade_authority") == "NONE")
    check("NEXT_GATE", decision.get("next_gate") == NEXT_GATE)
    check("ZERO_MUTATIONS", all(v == 0 for v in decision.get("zero_mutation_proof", {}).values()))
    ledger = read_gzip_jsonl(candidate_root / "FMDL6X2A_ROW_ACCOUNTING.jsonl.gz")
    check("LEDGER_UNIQUE_SOURCE_ROWS", len(ledger) == len({x["source_row_id"] for x in ledger}))
    check("LEDGER_COUNTS_RECONCILE", len(ledger) == quality["logical_source_rows_accounted"])
    for rel, meta in manifest["files"].items():
        path = candidate_root / rel
        check("HASH_" + rel.replace("/", "_").upper(), path.is_file() and sha256_file(path) == meta["sha256"])
    replay_root = candidate_root.parent / (candidate_root.name + "_replay")
    build_candidate(repo_root, raw_root, replay_root, accepted_at, source_commit)
    replay_errors = compare_directories(candidate_root, replay_root)
    check("SAME_INPUT_REPLAY_BYTE_IDENTICAL", not replay_errors, replay_errors, [])
    shutil.rmtree(replay_root, ignore_errors=True)
    status = "PASS" if not errors else "FAIL"
    write_json(acceptance_path, {
        "phase_id": PHASE_ID, "status": status, "release_id": decision.get("release_id"),
        "check_count": len(checks), "checks": checks, "errors": sorted(set(errors)),
    })
    return checks, sorted(set(errors))
