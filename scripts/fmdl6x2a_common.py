from __future__ import annotations

import gzip
import hashlib
import io
import json
import time
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CONTRACT_PATH = Path("config/fmdl6x2a_current_security_master_contract.json")
PHASE_ID = "FMDL-6X2-A"
EXIT_STATUS = "FMDL6X2A_CURRENT_SECURITY_MASTER_PRODUCTION_ACCEPTED"
NEXT_GATE = "FMDL-6X2-B_ISSUER_IDENTITY_CLASSIFICATION_AND_REVIEW_QUEUES"
FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)

def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))

def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"

def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(pretty_json(value), encoding="utf-8")

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())

def record_hash(namespace: str, *parts: Any) -> str:
    payload = namespace + "|" + "|".join("" if p is None else str(p).strip() for p in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def deterministic_gzip(lines: list[dict[str, Any]]) -> bytes:
    raw = "".join(stable_json(line) + "\n" for line in lines).encode("utf-8")
    out = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=out, mtime=0) as handle:
        handle.write(raw)
    return out.getvalue()

def read_gzip_jsonl(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]

def deterministic_zip(entries: dict[str, bytes]) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(entries):
            info = zipfile.ZipInfo(name, FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, entries[name])
    return out.getvalue()

def normalize_flag(value: str | None) -> bool:
    return (value or "").strip().upper() == "Y"

def validate_contract(repo_root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    checks: list[dict[str, Any]] = []
    errors: list[str] = []
    path = repo_root / CONTRACT_PATH
    if not path.is_file():
        return [{"check_id": "CONTRACT_EXISTS", "status": "FAIL"}], ["CONTRACT_EXISTS"]
    contract = load_json(path)
    def check(cid: str, condition: bool, actual: Any = None, expected: Any = None) -> None:
        checks.append({"check_id": cid, "status": "PASS" if condition else "FAIL", "actual": actual, "expected": expected})
        if not condition:
            errors.append(cid)
    check("PHASE_ID", contract.get("phase_id") == PHASE_ID, contract.get("phase_id"), PHASE_ID)
    check("STATUS", contract.get("status") == "PRODUCTION_CONTRACT_CANDIDATE")
    check("TRADE_AUTHORITY", contract.get("trade_authority") == "NONE")
    entry = contract.get("entry_gate", {})
    pointer_path = repo_root / entry.get("pointer_path", "")
    check("ENTRY_POINTER_EXISTS", pointer_path.is_file(), str(pointer_path), "existing file")
    if pointer_path.is_file():
        pointer = load_json(pointer_path)
        required_fields = [
            ("phase_id", "required_phase_id"), ("release_id", "required_release_id"),
            ("status", "required_status"), ("release_sequence", "required_release_sequence"),
            ("next_gate", "required_next_gate"), ("research_production_gate", "required_research_gate"),
            ("brokerage_real_account_gate", "required_brokerage_gate"),
            ("trade_authority", "required_trade_authority"),
        ]
        for field, required_key in required_fields:
            check("ENTRY_" + field.upper(), pointer.get(field) == entry.get(required_key), pointer.get(field), entry.get(required_key))
    required_assets = [
        "FMDL6X2_BUILD_CONTRACT.json", "FMDL6X2_SOURCE_EXECUTION_REGISTRY.json",
        "FMDL6X2_DOMAIN_SCHEMA_REGISTRY.json", "FMDL6X2_SHARD_PLAN.json",
        "FMDL6X2_QUALITY_GATE_REGISTRY.json",
    ]
    for name in required_assets:
        rel = Path("outputs/fmdl6x1/current") / name
        check("PREREQUISITE_" + Path(name).stem, (repo_root / rel).is_file(), str(rel), "existing file")
    scope = contract.get("scope", {})
    check("CURRENT_PRODUCTION_AUTHORIZED", scope.get("current_security_master_production_authorized") is True)
    for key, value in scope.items():
        if key != "current_security_master_production_authorized" and key.endswith("authorized"):
            check("SCOPE_FALSE_" + key.upper(), value is False, value, False)
    source = contract.get("source_contract", {})
    check("ROUTE_COUNT", len(source.get("routes", [])) == 2)
    check("TARGET_VENUES", source.get("target_venues") == ["XNAS", "XNYS", "XASE"])
    check("OFFICIAL_PRIMARY_FIRST", source.get("official_primary_first") is True)
    check("SILENT_SUBSTITUTION_FORBIDDEN", source.get("silent_source_substitution_forbidden") is True)
    storage = contract.get("storage_contract", {})
    check("BUCKET_COUNT", storage.get("bucket_count") == 64)
    check("RELEASE_SEQUENCE", storage.get("release_sequence") == 30)
    check("ALL_SHARDS_REQUIRED", storage.get("all_venue_bucket_combinations_required") is True)
    record = contract.get("record_contract", {})
    check("NO_CANONICAL_ID_IN_PHASE", record.get("canonical_security_id_issued_in_phase") is False)
    check("TICKER_NOT_IMMUTABLE", record.get("ticker_or_exchange_may_be_used_as_immutable_identity") is False)
    check("EXIT_STATUS", contract.get("required_exit_status") == EXIT_STATUS)
    check("NEXT_GATE", contract.get("next_gate") == NEXT_GATE)
    check("ZERO_MUTATIONS", all(v == 0 for v in contract.get("zero_mutation_gate", {}).values()))
    return checks, sorted(set(errors))

def fetch_one(route: dict[str, Any], policy: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:
    request = urllib.request.Request(route["url"], headers={"User-Agent": policy["user_agent"], "Accept": "text/plain,*/*"}, method="GET")
    last_error: Exception | None = None
    for attempt in range(1, int(policy["max_attempts"]) + 1):
        started = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=int(policy["timeout_seconds"])) as response:
                payload = response.read(int(policy["max_payload_bytes_per_route"]) + 1)
                if len(payload) > int(policy["max_payload_bytes_per_route"]):
                    raise ValueError("PAYLOAD_TOO_LARGE")
                status = int(getattr(response, "status", 200))
                if not 200 <= status < 300:
                    raise RuntimeError(f"HTTP_{status}")
                headers = {k.lower(): v for k, v in response.headers.items()}
                return payload, {
                    "route_id": route["route_id"], "url": route["url"], "source_authority": route["source_authority"],
                    "retrieved_at": utc_now(), "http_status": status,
                    "latency_ms": round((time.monotonic() - started) * 1000, 1),
                    "bytes": len(payload), "payload_sha256": sha256_bytes(payload),
                    "content_type": headers.get("content-type"), "etag": headers.get("etag"),
                    "last_modified": headers.get("last-modified"), "attempt": attempt,
                }
        except Exception as exc:
            last_error = exc
            if attempt < int(policy["max_attempts"]):
                time.sleep(float(policy["backoff_seconds"]) * attempt)
    raise RuntimeError(f"{route['route_id']} fetch failed: {type(last_error).__name__}: {last_error}")

def fetch_sources(repo_root: Path, raw_root: Path) -> dict[str, Any]:
    contract = load_json(repo_root / CONTRACT_PATH)
    raw_root.mkdir(parents=True, exist_ok=True)
    snapshots = []
    for route in contract["source_contract"]["routes"]:
        payload, meta = fetch_one(route, contract["network_policy"])
        filename = route["route_id"].lower() + ".txt"
        (raw_root / filename).write_bytes(payload)
        meta["raw_filename"] = filename
        meta["snapshot_id"] = f"{route['route_id']}_{meta['retrieved_at'][:10].replace('-', '')}_{meta['payload_sha256'][:12]}"
        write_json(raw_root / (filename + ".meta.json"), meta)
        snapshots.append(meta)
    result = {"phase_id": PHASE_ID, "captured_at": utc_now(), "snapshots": snapshots}
    write_json(raw_root / "SOURCE_SNAPSHOTS.json", result)
    return result
