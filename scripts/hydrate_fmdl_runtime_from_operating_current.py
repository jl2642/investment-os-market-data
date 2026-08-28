#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

DOMAIN_PATH = "operating_current/domains/A_SHARE_FULL_MARKET.json"
RUNTIME_PATHS = (
    "outputs/history/current",
    "outputs/factors/current",
    "datasets/history/incremental",
    "datasets/history/repair",
)


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        text=True,
        check=check,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    root = Path(".")
    local_manifest = root / "outputs/history/current/HISTORY_CURRENT_MANIFEST.json"
    local_as_of = str(read_json(local_manifest).get("as_of_date") or "") if local_manifest.exists() else ""

    fetch = run(
        "git","fetch","origin",
        "refs/heads/operating-current:refs/remotes/origin/operating-current",
        "--force","--no-tags",
        check=False,
    )
    if fetch.returncode != 0:
        print(json.dumps({
            "status":"NO_OP_OPERATING_CURRENT_UNAVAILABLE",
            "local_history_as_of":local_as_of,
            "trade_authority":"NONE",
        }, ensure_ascii=False))
        return 0

    show = run(
        "git","show",
        f"refs/remotes/origin/operating-current:{DOMAIN_PATH}",
        check=False,
    )
    if show.returncode != 0:
        print(json.dumps({
            "status":"NO_OP_A_SHARE_POINTER_MISSING",
            "local_history_as_of":local_as_of,
            "trade_authority":"NONE",
        }, ensure_ascii=False))
        return 0

    pointer = json.loads(show.stdout)
    if pointer.get("status") != "PASS":
        print(json.dumps({
            "status":"NO_OP_A_SHARE_POINTER_NOT_PASS",
            "pointer_status":pointer.get("status"),
            "local_history_as_of":local_as_of,
            "trade_authority":"NONE",
        }, ensure_ascii=False))
        return 0

    source_branch = str(pointer.get("source_branch") or "")
    source_commit = str(pointer.get("source_commit_sha") or "")
    source_as_of = str(pointer.get("watermark_sort_key") or pointer.get("data_watermark") or "")
    if not source_branch or not source_commit or not source_as_of:
        raise RuntimeError("A_SHARE_OPERATING_POINTER_IDENTITY_INCOMPLETE")

    if local_as_of and source_as_of <= local_as_of:
        print(json.dumps({
            "status":"NO_OP_LOCAL_RUNTIME_NOT_BEHIND",
            "local_history_as_of":local_as_of,
            "operating_history_as_of":source_as_of,
            "source_branch":source_branch,
            "source_commit":source_commit,
            "trade_authority":"NONE",
        }, ensure_ascii=False))
        return 0

    remote_ref = "refs/remotes/origin/fmdl-runtime-source"
    run(
        "git","fetch","origin",
        f"refs/heads/{source_branch}:{remote_ref}",
        "--force","--no-tags",
    )
    actual = run("git","rev-parse",remote_ref).stdout.strip()
    if actual != source_commit:
        raise RuntimeError(f"A_SHARE_OPERATING_SOURCE_HEAD_DRIFT:{actual}:{source_commit}")

    restored: list[str] = []
    for path in RUNTIME_PATHS:
        exists = run("git","cat-file","-e",f"{source_commit}:{path}",check=False)
        if exists.returncode == 0:
            run("git","checkout",source_commit,"--",path)
            restored.append(path)

    hydrated_manifest = read_json(local_manifest)
    hydrated_as_of = str(hydrated_manifest.get("as_of_date") or "")
    if hydrated_as_of != source_as_of:
        raise RuntimeError(
            f"A_SHARE_RUNTIME_HYDRATION_WATERMARK_MISMATCH:{hydrated_as_of}:{source_as_of}"
        )
    factor_release = root / "outputs/factors/current/FACTOR_CURRENT_RELEASE.json"
    if factor_release.exists():
        factor_as_of = str(read_json(factor_release).get("as_of_date") or "")
        if factor_as_of != source_as_of:
            raise RuntimeError(
                f"A_SHARE_FACTOR_HYDRATION_WATERMARK_MISMATCH:{factor_as_of}:{source_as_of}"
            )

    print(json.dumps({
        "status":"HYDRATED_FROM_OPERATING_CURRENT",
        "local_history_as_of_before":local_as_of,
        "operating_history_as_of":source_as_of,
        "source_branch":source_branch,
        "source_commit":source_commit,
        "restored_paths":restored,
        "candidate_membership_mutations":0,
        "real_account_mutations":0,
        "simulation_mutations":0,
        "orders":0,
        "trade_authority":"NONE",
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
