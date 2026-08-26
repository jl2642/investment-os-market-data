"""Audit Canonical checkpoint trees for contemporaneous candidate-model inputs.

The audit distinguishes exact model fields from legacy/proxy-like fields and never
maps a proxy into a Phase 3B model dimension. It scans each Canonical checkpoint tree
with git-grep first, then parses only matching historical files.
"""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Iterable, Mapping

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from strategy_kernel_v2.point_in_time_ledger import build_point_in_time_ledger  # noqa: E402

PHASE2_REQUIRED = {"confidence", "portfolio_concentration_cost", "execution_friction"}
SIMPLE_REQUIRED = {
    "return_proxy",
    "downside_resilience",
    "evidence_quality",
    "concentration_cost",
    "execution_friction",
}
EXACT_SEARCH_TERMS = sorted(
    PHASE2_REQUIRED
    | SIMPLE_REQUIRED
    | {"valuation_scenarios", "probability", "annualized_total_return"}
)
PROXY_KEYS = {
    "evidence_score",
    "quality_score",
    "portfolio_fit_score",
    "risk_penalty",
    "race_confidence",
    "current_weight",
    "base_case_expected_return",
    "current_sim_pnl_pct",
    "board_lot_sizing_mismatch",
    "research_gap_count",
    "valuation_score_coarse",
    "return_vs_completed_close",
    "driver_based_scenarios",
}
SCAN_ROOTS = ("investment_os_runtime", "evidence", "outputs")
TEXT_SUFFIXES = {".json", ".csv", ".md", ".txt"}
SEARCH_PATTERN = "|".join(re.escape(term) for term in sorted(set(EXACT_SEARCH_TERMS) | PROXY_KEYS))


def _run(repo_root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=str(repo_root), text=True, capture_output=True, check=False)


def _tree_paths(repo_root: Path, commit_sha: str) -> list[str]:
    completed = _run(repo_root, ["git", "ls-tree", "-r", "--name-only", commit_sha, "--", *SCAN_ROOTS])
    if completed.returncode != 0:
        raise RuntimeError("CHECKPOINT_TREE_UNREADABLE:" + commit_sha + ":" + completed.stderr.strip())
    return sorted(
        line.strip()
        for line in completed.stdout.splitlines()
        if line.strip() and Path(line.strip()).suffix.lower() in TEXT_SUFFIXES
    )


def _matching_paths(repo_root: Path, commit_sha: str, allowed_paths: set[str]) -> list[str]:
    completed = _run(
        repo_root,
        ["git", "grep", "-l", "-I", "-E", SEARCH_PATTERN, commit_sha, "--", *SCAN_ROOTS],
    )
    if completed.returncode not in (0, 1):
        raise RuntimeError("CHECKPOINT_GREP_FAILED:" + commit_sha + ":" + completed.stderr.strip())
    matches = []
    prefix = commit_sha + ":"
    for line in completed.stdout.splitlines():
        value = line.strip()
        if value.startswith(prefix):
            value = value[len(prefix):]
        if value in allowed_paths:
            matches.append(value)
    return sorted(set(matches))


def _show(repo_root: Path, commit_sha: str, path: str) -> str:
    completed = _run(repo_root, ["git", "show", f"{commit_sha}:{path}"])
    if completed.returncode != 0:
        raise RuntimeError("CHECKPOINT_FILE_UNREADABLE:" + commit_sha + ":" + path)
    return completed.stdout


def _walk_mappings(value: Any) -> Iterable[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        yield value
        for child in value.values():
            yield from _walk_mappings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_mappings(child)


def _all_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    for mapping in _walk_mappings(value):
        keys.update(str(key) for key in mapping)
    return keys


def _parse(path: str, raw: str) -> Any:
    suffix = Path(path).suffix.lower()
    if suffix == ".json":
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw
    if suffix == ".csv":
        try:
            return list(csv.DictReader(io.StringIO(raw)))
        except csv.Error:
            return raw
    return raw


def _scenario_list_is_probability_weighted(value: Any) -> bool:
    if not isinstance(value, list) or len(value) < 2:
        return False
    for row in value:
        if not isinstance(row, Mapping) or "probability" not in row:
            return False
        if not ({"annualized_total_return", "return_vs_completed_close"} & set(row)):
            return False
    return True


def _complete_phase2_mappings(value: Any) -> int:
    count = 0
    for mapping in _walk_mappings(value):
        if not PHASE2_REQUIRED <= set(mapping):
            continue
        if _scenario_list_is_probability_weighted(mapping.get("valuation_scenarios")):
            count += 1
        elif _scenario_list_is_probability_weighted(mapping.get("scenarios")):
            count += 1
    return count


def _complete_simple_mappings(value: Any) -> int:
    return sum(1 for mapping in _walk_mappings(value) if SIMPLE_REQUIRED <= set(mapping))


def _registered_paths_for_snapshot(snapshot: Mapping[str, Any]) -> set[str]:
    return {str(record["source"]["path"]) for record in snapshot["selected_evidence"]}


def audit_checkpoint(*, repo_root: Path, point: Mapping[str, Any], snapshot: Mapping[str, Any]) -> dict[str, Any]:
    commit_sha = point["canonical_commit_sha"]
    tree_paths = _tree_paths(repo_root, commit_sha)
    tree_path_set = set(tree_paths)
    paths = _matching_paths(repo_root, commit_sha, tree_path_set)
    registered_paths = _registered_paths_for_snapshot(snapshot)

    exact_field_files: list[dict[str, Any]] = []
    proxy_field_files: list[dict[str, Any]] = []
    complete_phase2: list[dict[str, Any]] = []
    complete_simple: list[dict[str, Any]] = []

    for path in paths:
        raw = _show(repo_root, commit_sha, path)
        parsed = _parse(path, raw)
        keys = _all_keys(parsed) if not isinstance(parsed, str) else set()
        exact_keys = sorted(set(EXACT_SEARCH_TERMS) & keys)
        proxy_keys = sorted(PROXY_KEYS & keys)
        registered = path in registered_paths

        if exact_keys:
            exact_field_files.append({"path": path, "registered_selected_path": registered, "exact_keys": exact_keys})
        if proxy_keys:
            proxy_field_files.append({"path": path, "registered_selected_path": registered, "proxy_keys": proxy_keys})

        p2_count = _complete_phase2_mappings(parsed) if not isinstance(parsed, str) else 0
        simple_count = _complete_simple_mappings(parsed) if not isinstance(parsed, str) else 0
        if p2_count:
            complete_phase2.append({"path": path, "registered_selected_path": registered, "complete_mapping_count": p2_count})
        if simple_count:
            complete_simple.append({"path": path, "registered_selected_path": registered, "complete_mapping_count": simple_count})

    return {
        "decision_point_id": point["decision_point_id"],
        "at": point["at"],
        "canonical_commit_sha": commit_sha,
        "tree_text_file_count": len(tree_paths),
        "keyword_candidate_file_count": len(paths),
        "registered_selected_path_count": len(registered_paths),
        "exact_model_field_files": exact_field_files,
        "proxy_like_field_files": proxy_field_files,
        "complete_phase2_packet_files": complete_phase2,
        "complete_simple_packet_files": complete_simple,
        "unregistered_complete_phase2_packet_files": [row for row in complete_phase2 if not row["registered_selected_path"]],
        "unregistered_complete_simple_packet_files": [row for row in complete_simple if not row["registered_selected_path"]],
    }


def build_audit(repo_root: str | Path = ".") -> dict[str, Any]:
    root = Path(repo_root)
    registry = json.loads((root / "strategy_kernel_v2/PHASE3A_EVIDENCE_REGISTRY.json").read_text(encoding="utf-8"))
    points_doc = json.loads((root / "strategy_kernel_v2/PHASE3A_DECISION_POINTS.json").read_text(encoding="utf-8"))
    ledger = build_point_in_time_ledger(registry["records"], points_doc["decision_points"])
    snapshots = {row["decision_point_id"]: row for row in ledger["snapshots"]}

    checkpoint_results = [
        audit_checkpoint(repo_root=root, point=point, snapshot=snapshots[point["decision_point_id"]])
        for point in points_doc["decision_points"]
    ]

    phase2_complete = sum(len(row["complete_phase2_packet_files"]) for row in checkpoint_results)
    simple_complete = sum(len(row["complete_simple_packet_files"]) for row in checkpoint_results)
    phase2_unregistered = sum(len(row["unregistered_complete_phase2_packet_files"]) for row in checkpoint_results)
    simple_unregistered = sum(len(row["unregistered_complete_simple_packet_files"]) for row in checkpoint_results)
    exact_files = sum(len(row["exact_model_field_files"]) for row in checkpoint_results)
    proxy_files = sum(len(row["proxy_like_field_files"]) for row in checkpoint_results)
    keyword_files = sum(row["keyword_candidate_file_count"] for row in checkpoint_results)

    if phase2_unregistered or simple_unregistered:
        conclusion = "POTENTIAL_UNREGISTERED_COMPLETE_INPUTS_REQUIRE_GOVERNED_REVIEW"
    elif phase2_complete or simple_complete:
        conclusion = "COMPLETE_INPUTS_EXIST_ONLY_IN_ALREADY_SELECTED_HISTORICAL_PATHS_REVIEW_EXTRACTOR"
    else:
        conclusion = "NO_COMPLETE_CANDIDATE_MODEL_INPUT_PACKET_FOUND_IN_CANONICAL_CHECKPOINT_TREES"

    return {
        "schema_version": "1.0.0",
        "phase": "3C",
        "mode": "HISTORICAL_INPUT_RECOVERY_AND_REPLAYABILITY_AUDIT",
        "checkpoint_count": len(checkpoint_results),
        "scan_roots": list(SCAN_ROOTS),
        "keyword_candidate_file_occurrences": keyword_files,
        "exact_model_field_file_occurrences": exact_files,
        "proxy_like_field_file_occurrences": proxy_files,
        "complete_phase2_packet_file_occurrences": phase2_complete,
        "complete_simple_packet_file_occurrences": simple_complete,
        "unregistered_complete_phase2_packet_file_occurrences": phase2_unregistered,
        "unregistered_complete_simple_packet_file_occurrences": simple_unregistered,
        "conclusion": conclusion,
        "proxy_policy": "PROXY_LIKE_LEGACY_FIELDS_ARE_NOT_MAPPED_TO_PHASE3B_MODEL_INPUTS",
        "checkpoint_results": checkpoint_results,
        "orders": 0,
        "trade_authority": "NONE",
    }


if __name__ == "__main__":
    result = build_audit(REPO_ROOT)
    print(
        "PHASE3C_REPLAYABILITY_AUDIT "
        f"checkpoints={result['checkpoint_count']} "
        f"keyword_files={result['keyword_candidate_file_occurrences']} "
        f"exact_field_files={result['exact_model_field_file_occurrences']} "
        f"proxy_files={result['proxy_like_field_file_occurrences']} "
        f"phase2_complete={result['complete_phase2_packet_file_occurrences']} "
        f"simple_complete={result['complete_simple_packet_file_occurrences']} "
        f"phase2_unregistered={result['unregistered_complete_phase2_packet_file_occurrences']} "
        f"simple_unregistered={result['unregistered_complete_simple_packet_file_occurrences']} "
        f"conclusion={result['conclusion']} "
        "orders=0 trade_authority=NONE"
    )
