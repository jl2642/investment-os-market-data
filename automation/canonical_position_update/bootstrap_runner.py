#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import zlib

EXPECTED_PART_COUNT = 4
EXPECTED_BASE64_LENGTH = 14416
EXPECTED_COMPRESSED_SHA256 = "8b7a9b8fec8ac9c254f0b2e3c00e175f4b24b2d7b4e522c0717a701f49a438f2"
EXPECTED_PAYLOAD_SHA256 = "0aca0666fd8353c85390d2353636affac6e0529fd8075e4c69669ac74a9ab05a"


def main() -> None:
    repo = Path(__file__).resolve().parents[2]
    root = repo / "automation/canonical_position_update"
    parts = [root / f"payload.part{i}" for i in range(1, EXPECTED_PART_COUNT + 1)]
    assert all(path.is_file() for path in parts), [str(path) for path in parts if not path.is_file()]
    encoded = "".join(path.read_text(encoding="ascii").strip() for path in parts)
    assert len(encoded) == EXPECTED_BASE64_LENGTH, len(encoded)
    compressed = base64.b64decode(encoded, validate=True)
    assert hashlib.sha256(compressed).hexdigest() == EXPECTED_COMPRESSED_SHA256
    payload = zlib.decompress(compressed)
    assert hashlib.sha256(payload).hexdigest() == EXPECTED_PAYLOAD_SHA256
    files = json.loads(payload.decode("utf-8"))
    for relative, content in files.items():
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="")
    print(json.dumps({"status":"INSTALLED_AND_HASH_VERIFIED","file_count":len(files),"trade_authority":"NONE","orders":0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
