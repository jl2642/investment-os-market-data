from __future__ import annotations

import gzip
import hashlib
import io
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CONTRACT_PATH = Path("config/fmdl6x2c_historical_listing_contract.json")
PHASE_ID = "FMDL-6X2-C"
EXIT_STATUS = "FMDL6X2C_HISTORICAL_LISTING_AND_LIFECYCLE_BACKFILL_ACCEPTED"
NEXT_GATE = "FMDL-6X2-D_MARKET_HISTORY_CORPORATE_ACTIONS_AND_FX_STORE"
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

def deterministic_gzip(rows: list[dict[str, Any]]) -> bytes:
    raw = "".join(stable_json(row) + "\n" for row in rows).encode("utf-8")
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

def read_zip_jsonl(path: Path, prefix: str | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with zipfile.ZipFile(path, "r") as archive:
        for name in sorted(archive.namelist()):
            if not name.endswith(".jsonl") or (prefix and not name.startswith(prefix)):
                continue
            payload = archive.read(name).decode("utf-8")
            rows.extend(json.loads(line) for line in payload.splitlines() if line.strip())
    return rows

def bucket_hex(value: str, bucket_count: int) -> str:
    return f"{int(hashlib.sha256(value.encode('utf-8')).hexdigest(), 16) % bucket_count:02X}"

def copytree_replace(source: Path, target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)

def validate_contract(repo_root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    checks: list[dict[str, Any]] = []
    errors: list[str] = []
    path = repo_root / CONTRACT_PATH
    if not path.is_file():
        return [{"check_id":"CONTRACT_EXISTS","status":"FAIL"}], ["CONTRACT_EXISTS"]
    contract = load_json(path)
    def check(cid: str, condition: bool, actual: Any = None, expected: Any = None) -> None:
        checks.append({"check_id":cid,"status":"PASS" if condition else "FAIL","actual":actual,"expected":expected})
        if not condition:
            errors.append(cid)
    check("PHASE_ID", contract.get("phase_id") == PHASE_ID, contract.get("phase_id"), PHASE_ID)
    check("TRADE_AUTHORITY", contract.get("trade_authority") == "NONE")
    entry = contract.get("entry_gate", {})
    pointer_path = repo_root / entry.get("pointer_path", "")
    check("ENTRY_POINTER_EXISTS", pointer_path.is_file())
    if pointer_path.is_file():
        pointer = load_json(pointer_path)
        for field, key in [
            ("phase_id","required_phase_id"),("release_id","required_release_id"),
            ("release_sequence","required_release_sequence"),("status","required_status"),
            ("next_gate","required_next_gate"),("trade_authority","required_trade_authority")
        ]:
            check("ENTRY_" + field.upper(), pointer.get(field) == entry.get(key), pointer.get(field), entry.get(key))
    scope = contract.get("scope", {})
    check("HISTORY_AUTHORIZED", scope.get("historical_listing_and_lifecycle_authorized") is True)
    for key, value in scope.items():
        if key != "historical_listing_and_lifecycle_authorized" and key.endswith("authorized"):
            check("SCOPE_FALSE_" + key.upper(), value is False, value, False)
    history = contract.get("history_contract", {})
    check("TARGET_START", history.get("target_start_date") == "2005-01-01")
    check("NO_CURRENT_SURVIVORSHIP", history.get("current_only_survivorship_backfill_forbidden") is True)
    check("NO_FAKE_EFFECTIVE_DATE", history.get("observation_date_may_be_represented_as_exact_effective_date") is False)
    check("NO_UNIVERSAL_FREE_ROUTE", history.get("universal_zero_cost_official_route_confirmed") is False)
    check("CONFIDENCE_GRADES", history.get("effective_date_confidence_grades") == ["OFFICIAL_EFFECTIVE_DATE","BOUNDED_EVENT_WINDOW","OBSERVATION_ONLY"])
    check("RELEASE_SEQUENCE", contract.get("storage_contract", {}).get("release_sequence") == 32)
    check("EXIT_STATUS", contract.get("required_exit_status") == EXIT_STATUS)
    check("NEXT_GATE", contract.get("next_gate") == NEXT_GATE)
    check("ZERO_MUTATIONS", all(v == 0 for v in contract.get("zero_mutation_gate", {}).values()))
    return checks, sorted(set(errors))

def discover_identity_releases(repo_root: Path, contract: dict[str, Any]) -> list[dict[str, Any]]:
    releases: list[dict[str, Any]] = []
    required = contract["input_contract"]["required_identity_files"]
    pattern = contract["input_contract"]["identity_release_glob"]
    for root in sorted(repo_root.glob(pattern)):
        if not root.is_dir() or any(not (root / name).is_file() for name in required):
            continue
        decision = load_json(root / "FMDL6X2B_DECISION.json")
        quality = load_json(root / "FMDL6X2B_QUALITY_REPORT.json")
        if decision.get("status") != "FMDL6X2B_IDENTITY_CLASSIFICATION_AND_REVIEW_QUEUES_ACCEPTED":
            continue
        if quality.get("quality_status") != "PASS":
            continue
        releases.append({
            "root":root,
            "decision":decision,
            "manifest":load_json(root / "FMDL6X2B_MANIFEST.json"),
            "manifest_sha256":sha256_file(root / "FMDL6X2B_MANIFEST.json"),
        })
    return releases
