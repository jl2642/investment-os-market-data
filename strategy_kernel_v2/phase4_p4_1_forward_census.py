from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONTRACT = ROOT / "PHASE4_P4_1_FORWARD_CENSUS_CONTRACT.json"
OUTPUT = ROOT / "generated/PHASE4_P4_1_FORWARD_CENSUS.json"


def _load():
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def _run(*args: str) -> str:
    return subprocess.check_output(list(args), text=True).strip()


def build():
    c = _load()
    cutoff = c["future_evidence_cutoff_time_utc"]
    _run("git", "fetch", "origin", "main", "--no-tags", "--quiet")
    main_head = _run("git", "rev-parse", "origin/main")
    raw = _run(
        "git", "log", "origin/main", "--first-parent", f"--since={cutoff}",
        "--format=%H%x1f%cI%x1f%s"
    )
    rows = []
    if raw:
        for line in raw.splitlines():
            sha, committed_at, subject = line.split("\x1f", 2)
            committed = datetime.fromisoformat(committed_at.replace("Z", "+00:00"))
            cutoff_dt = datetime.fromisoformat(cutoff.replace("Z", "+00:00"))
            if committed.astimezone(timezone.utc) <= cutoff_dt:
                continue
            rows.append({
                "commit_sha": sha,
                "committed_at": committed_at,
                "subject": subject,
                "classification": "CANDIDATE_COMMIT_REQUIRES_SUBSTANTIVE_AND_SHARED_PACKET_GATES",
                "counts_as_phase4_observation": False,
            })

    if rows:
        status = "POST_CUTOFF_CANONICAL_MAIN_COMMITS_FOUND_REQUIRES_CLASSIFICATION"
    else:
        status = "NO_POST_CUTOFF_CANONICAL_MAIN_COMMITS"

    result = {
        "schema_version": "1.0.0",
        "phase": "PHASE_4",
        "subphase": "P4_1_FORWARD_CANONICAL_MAIN_CENSUS",
        "status": status,
        "cutoff_time_utc": cutoff,
        "canonical_main_head": main_head,
        "post_cutoff_main_commit_count": len(rows),
        "candidate_commits": rows,
        "counted_phase4_forward_observation_count": 0,
        "phase4_started": False,
        "phase4_realized_outcome_read_count": 0,
        "interpretation": (
            "NO_GENUINELY_FORWARD_CANONICAL_EVIDENCE_YET_NOT_MODEL_FAILURE"
            if not rows else
            "CANDIDATE_COMMITS_EXIST_BUT_NONE_COUNT_UNTIL_SUBSTANTIVE_CLASSIFICATION_AND_SHARED_PACKET_GATES_PASS"
        ),
        "orders": 0,
        "trade_authority": "NONE",
    }
    return result


def write(result):
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    result = build()
    write(result)
    print(
        "PHASE4_P4_1_FORWARD_CENSUS "
        f"status={result['status']} main_head={result['canonical_main_head']} "
        f"post_cutoff_commits={result['post_cutoff_main_commit_count']} "
        "counted_observations=0 phase4_started=false outcomes=0 orders=0 trade_authority=NONE"
    )
