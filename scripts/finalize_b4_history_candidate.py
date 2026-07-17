#!/usr/bin/env python3
"""Finalize current-run FMDL-2B-4 component row hashes and manifest hashes."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pandas as pd

from scripts.fmdl2b4_history import ROOT, canonical_hash, read_json, resolve_path, sha256_file

MANIFEST_PATH = ROOT / "outputs/history/refresh_candidate/HISTORY_CURRENT_MANIFEST.json"


def rehash_frame(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    payload_columns = [column for column in output.columns if column != "row_hash"]
    output["row_hash"] = [canonical_hash(row) for row in output[payload_columns].to_dict(orient="records")]
    return output


def finalize(root: Path = ROOT) -> dict:
    manifest_path = root / MANIFEST_PATH.relative_to(ROOT)
    manifest = read_json(manifest_path)
    release_id = str(manifest["release_id"])
    changed = 0
    entries = [*manifest.get("delta_files", []), *manifest.get("repair_files", [])]
    for entry in entries:
        path = resolve_path(str(entry["path"]), root)
        if release_id not in str(path):
            continue
        frame = pd.read_parquet(path)
        frame = rehash_frame(frame)
        frame.to_parquet(path, index=False, compression="zstd")
        symbols = sorted(frame["symbol"].astype(str).unique().tolist())
        entry.update({
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
            "row_count": int(len(frame)),
            "symbol_count": len(symbols),
            "symbol_set_sha256": canonical_hash(symbols),
        })
        changed += 1
    manifest["component_aggregate_sha256"] = canonical_hash(entries)
    manifest["component_hash_finalization"] = {
        "status": "PASS",
        "current_run_components_rehashed": changed,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result = {"status": "PASS", "release_id": release_id, "components_rehashed": changed}
    print(json.dumps(result, ensure_ascii=False))
    return result


if __name__ == "__main__":
    try:
        finalize(ROOT)
    except Exception as exc:
        print(f"FMDL-2B-4 history finalization failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(2)
