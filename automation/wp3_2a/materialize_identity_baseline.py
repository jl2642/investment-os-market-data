from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
from pathlib import Path

PART_GLOB = "WP3_2_OLD_ACCEPTED_IDENTITY_BASELINE_20260717.slim.jsonl.gz.b64.part*"
TARGET_NAME = "WP3_2_OLD_ACCEPTED_IDENTITY_EVIDENCE_20260717.jsonl"
EXPECTED_PARTS = 6
EXPECTED_SIZE = 444_911
EXPECTED_SHA256 = "c99f9bcca0c32a3992ef8f1b46679e854a958027fc48d89f3244c510985d304a"
EXPECTED_RECORDS = 5_528
EXPECTED_FIELDS = {"symbol", "name", "market_evidence"}


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def materialize(repo_root: Path) -> Path:
    baseline_dir = (
        repo_root
        / "investment_os_runtime"
        / "40_EVIDENCE_AND_LINEAGE"
        / "WP3_2_R4"
    )
    parts = sorted(baseline_dir.glob(PART_GLOB))
    if len(parts) != EXPECTED_PARTS:
        raise RuntimeError(
            f"identity baseline transport is incomplete: expected {EXPECTED_PARTS} parts, found {len(parts)}"
        )

    encoded = "".join(part.read_text(encoding="ascii").strip() for part in parts)
    compressed = base64.b64decode(encoded, validate=True)
    payload = gzip.decompress(compressed)

    if len(payload) != EXPECTED_SIZE:
        raise RuntimeError(
            f"identity baseline size mismatch: expected {EXPECTED_SIZE}, got {len(payload)}"
        )
    digest = sha256_bytes(payload)
    if digest != EXPECTED_SHA256:
        raise RuntimeError(
            f"identity baseline SHA-256 mismatch: expected {EXPECTED_SHA256}, got {digest}"
        )

    text = payload.decode("utf-8")
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) != EXPECTED_RECORDS:
        raise RuntimeError(
            f"identity baseline record-count mismatch: expected {EXPECTED_RECORDS}, got {len(lines)}"
        )

    symbols: set[str] = set()
    for number, line in enumerate(lines, start=1):
        item = json.loads(line)
        if set(item) != EXPECTED_FIELDS:
            raise RuntimeError(
                f"identity baseline schema mismatch at line {number}: {sorted(item)}"
            )
        symbol = str(item["symbol"])
        if symbol in symbols:
            raise RuntimeError(f"duplicate identity symbol at line {number}: {symbol}")
        symbols.add(symbol)
        market = item.get("market_evidence")
        if not isinstance(market, dict) or not market.get("exchange"):
            raise RuntimeError(f"missing exchange evidence at line {number}: {symbol}")

    target = baseline_dir / TARGET_NAME
    target.write_bytes(payload)
    return target


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args()
    target = materialize(Path(args.repo_root).resolve())
    print(
        json.dumps(
            {
                "status": "PASS",
                "target": str(target),
                "records": EXPECTED_RECORDS,
                "size": EXPECTED_SIZE,
                "sha256": EXPECTED_SHA256,
                "trade_authority": "NONE",
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
