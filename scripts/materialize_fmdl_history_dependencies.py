#!/usr/bin/env python3
"""Resolve and verify history-manifest backing dependencies for FMDL daily bootstrap."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Iterable

_REBASE = re.compile(r"^FMDL2B4_REBASE_(\d+)_A(\d+)$")


def rebase_branch_for_release_id(release_id: str | None) -> str | None:
    if not release_id:
        return None
    match = _REBASE.fullmatch(str(release_id))
    if not match:
        return None
    return f"automation/fmdl2b4-rebase-{match.group(1)}-a{match.group(2)}"


def iter_dependencies(manifest: dict) -> Iterable[dict]:
    for key in ("delta_files", "repair_files"):
        for row in manifest.get(key, []) or []:
            if isinstance(row, dict) and row.get("path"):
                yield row


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dependency_is_valid(root: Path, row: dict) -> bool:
    path = root / row["path"]
    if not path.is_file():
        return False
    expected = str(row.get("sha256") or "").strip().lower()
    return not expected or sha256_file(path) == expected


def missing_dependency_rows(root: Path, manifest: dict) -> list[dict]:
    missing = []
    for row in iter_dependencies(manifest):
        if dependency_is_valid(root, row):
            continue
        release_id = row.get("recovery_release_id")
        branch = rebase_branch_for_release_id(release_id)
        missing.append(
            {
                "path": row["path"],
                "sha256": row.get("sha256"),
                "recovery_release_id": release_id,
                "source_branch": branch,
            }
        )
    return missing


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--root", default=".")
    parser.add_argument("--emit-missing-tsv")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    root = Path(args.root)
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    missing = missing_dependency_rows(root, manifest)

    if args.emit_missing_tsv:
        out = Path(args.emit_missing_tsv)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8") as handle:
            for row in missing:
                handle.write(
                    f"{row.get('source_branch') or '__UNRESOLVED__'}\t{row['path']}\t"
                    f"{row.get('sha256') or ''}\t{row.get('recovery_release_id') or ''}\n"
                )

    print(
        json.dumps(
            {
                "release_id": manifest.get("release_id"),
                "as_of_date": manifest.get("as_of_date"),
                "dependency_count": sum(1 for _ in iter_dependencies(manifest)),
                "missing_or_mismatched_count": len(missing),
                "unresolvable_count": sum(1 for row in missing if not row["source_branch"]),
                "missing": missing,
            },
            ensure_ascii=False,
        )
    )

    if args.verify and missing:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
