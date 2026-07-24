from __future__ import annotations

from pathlib import Path
import base64
import hashlib
import json
import shutil
import zipfile

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))

parts: list[str] = []
for item in manifest["chunks"]:
    path = ROOT / item["file"]
    raw = path.read_bytes()
    if len(raw) != item["size"]:
        raise SystemExit(f"chunk size mismatch: {path}")
    if hashlib.sha256(raw).hexdigest() != item["sha256"]:
        raise SystemExit(f"chunk hash mismatch: {path}")
    parts.append(raw.decode("ascii"))

encoded = "".join(parts)
if len(encoded) != manifest["base64_length"]:
    raise SystemExit("base64 length mismatch")

payload = base64.b64decode(encoded, validate=True)
if len(payload) != manifest["zip_size"]:
    raise SystemExit("payload size mismatch")
if hashlib.sha256(payload).hexdigest() != manifest["zip_sha256"]:
    raise SystemExit("payload SHA-256 mismatch")

zip_path = ROOT / "runtime_payload.reconstructed.zip"
zip_path.write_bytes(payload)
stage = ROOT / "_stage"
if stage.exists():
    shutil.rmtree(stage)

with zipfile.ZipFile(zip_path) as archive:
    if archive.testzip() is not None:
        raise SystemExit("ZIP CRC failure")
    for name in archive.namelist():
        member = Path(name)
        if member.is_absolute() or ".." in member.parts or not name.startswith("investment_os_runtime/"):
            raise SystemExit(f"unsafe member: {name}")
    archive.extractall(stage)

target = REPO / "investment_os_runtime"
if target.exists():
    shutil.rmtree(target)
shutil.copytree(stage / "investment_os_runtime", target)

file_count = sum(1 for path in target.rglob("*") if path.is_file())
if file_count != manifest["expected_file_count"]:
    raise SystemExit(f"runtime file count mismatch: {file_count}")

print(json.dumps({
    "status": "PASS",
    "files": file_count,
    "payload_sha256": manifest["zip_sha256"],
    "trade_authority": "NONE"
}, indent=2))
