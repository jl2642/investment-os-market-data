from __future__ import annotations

from pathlib import Path
import base64
import hashlib
import json
import shutil
import zipfile

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
DIAGNOSTIC = REPO / "outputs/status/WP1_5B_MATERIALIZATION_DIAGNOSTIC.json"
manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))

diagnostic: dict = {
    "bootstrap_id": manifest["bootstrap_id"],
    "status": "CHECKING",
    "chunks": [],
    "trade_authority": "NONE",
}
parts: list[str] = []
errors: list[str] = []
for item in manifest["chunks"]:
    path = ROOT / item["file"]
    raw = path.read_bytes()
    actual_sha = hashlib.sha256(raw).hexdigest()
    record = {
        "file": item["file"],
        "expected_size": item["size"],
        "actual_size": len(raw),
        "expected_sha256": item["sha256"],
        "actual_sha256": actual_sha,
        "size_match": len(raw) == item["size"],
        "sha_match": actual_sha == item["sha256"],
    }
    diagnostic["chunks"].append(record)
    if not record["size_match"]:
        errors.append(f"chunk size mismatch: {item['file']}")
    if not record["sha_match"]:
        errors.append(f"chunk hash mismatch: {item['file']}")
    parts.append(raw.decode("ascii"))

DIAGNOSTIC.parent.mkdir(parents=True, exist_ok=True)
if errors:
    diagnostic["status"] = "FAIL"
    diagnostic["errors"] = errors
    DIAGNOSTIC.write_text(json.dumps(diagnostic, indent=2), encoding="utf-8")
    raise SystemExit("; ".join(errors))

encoded = "".join(parts)
diagnostic["actual_base64_length"] = len(encoded)
if len(encoded) != manifest["base64_length"]:
    errors.append("base64 length mismatch")

try:
    payload = base64.b64decode(encoded, validate=True)
except Exception as exc:
    errors.append(f"base64 decode failure: {exc}")
    payload = b""

diagnostic["actual_zip_size"] = len(payload)
diagnostic["actual_zip_sha256"] = hashlib.sha256(payload).hexdigest()
if len(payload) != manifest["zip_size"]:
    errors.append("payload size mismatch")
if diagnostic["actual_zip_sha256"] != manifest["zip_sha256"]:
    errors.append("payload SHA-256 mismatch")

if errors:
    diagnostic["status"] = "FAIL"
    diagnostic["errors"] = errors
    DIAGNOSTIC.write_text(json.dumps(diagnostic, indent=2), encoding="utf-8")
    raise SystemExit("; ".join(errors))

zip_path = ROOT / "runtime_payload.reconstructed.zip"
zip_path.write_bytes(payload)
stage = ROOT / "_stage"
if stage.exists():
    shutil.rmtree(stage)

with zipfile.ZipFile(zip_path) as archive:
    bad_member = archive.testzip()
    if bad_member is not None:
        errors.append(f"ZIP CRC failure: {bad_member}")
    for name in archive.namelist():
        member = Path(name)
        if member.is_absolute() or ".." in member.parts or not name.startswith("investment_os_runtime/"):
            errors.append(f"unsafe member: {name}")
    if not errors:
        archive.extractall(stage)

if errors:
    diagnostic["status"] = "FAIL"
    diagnostic["errors"] = errors
    DIAGNOSTIC.write_text(json.dumps(diagnostic, indent=2), encoding="utf-8")
    raise SystemExit("; ".join(errors))

target = REPO / "investment_os_runtime"
if target.exists():
    shutil.rmtree(target)
shutil.copytree(stage / "investment_os_runtime", target)

file_count = sum(1 for path in target.rglob("*") if path.is_file())
diagnostic["materialized_file_count"] = file_count
if file_count != manifest["expected_file_count"]:
    errors.append(f"runtime file count mismatch: {file_count}")

if errors:
    diagnostic["status"] = "FAIL"
    diagnostic["errors"] = errors
    DIAGNOSTIC.write_text(json.dumps(diagnostic, indent=2), encoding="utf-8")
    raise SystemExit("; ".join(errors))

diagnostic["status"] = "PASS"
DIAGNOSTIC.write_text(json.dumps(diagnostic, indent=2), encoding="utf-8")
print(json.dumps(diagnostic, indent=2))
