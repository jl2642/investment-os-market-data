#!/usr/bin/env python3
"""Publish the independently validated FMDL-2D final FMDL-2 acceptance."""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import shutil
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("Asia/Shanghai")
CANDIDATE = ROOT / "outputs/stability/candidate"
CURRENT = ROOT / "outputs/stability/current"
STATUS = ROOT / "outputs/status/FMDL2D_LAST_SUCCESS.json"
SCREEN_RELEASE = ROOT / "outputs/screens/current/SCREENING_CURRENT_RELEASE.json"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def publish(root: Path = ROOT):
    candidate = root / CANDIDATE.relative_to(ROOT)
    current = root / CURRENT.relative_to(ROOT)
    acceptance = read_json(candidate / "FMDL2D_ACCEPTANCE.json")
    validation = read_json(candidate / "FMDL2D_VALIDATION.json")
    manifest = read_json(candidate / "FMDL2D_MANIFEST.json")
    if acceptance.get("hard_failures"):
        raise RuntimeError("FMDL2D_ACCEPTANCE_HAS_HARD_FAILURES")
    if validation.get("status") != "PASS":
        raise RuntimeError("FMDL2D_VALIDATION_NOT_PASS")
    if manifest.get("status") != "CANDIDATE_ACCEPTED":
        raise RuntimeError("FMDL2D_MANIFEST_NOT_ACCEPTED")
    if current.exists():
        shutil.rmtree(current)
    shutil.copytree(candidate, current)
    published_at = datetime.now(tz=TZ).isoformat(timespec="seconds")
    release = {
        "release_version": "1.0.0",
        "release_id": acceptance["run_id"],
        "published_at": published_at,
        "as_of_date": acceptance["as_of_date"],
        "status": "FMDL2_FINAL_ACCEPTED_WITH_CONTROLLED_LIMITATIONS",
        "acceptance_state": acceptance["acceptance_state"],
        "screening_release_id": acceptance["screening_release_id"],
        "factor_release_id": acceptance["factor_release_id"],
        "history_release_id": acceptance["history_release_id"],
        "manifest_path": "outputs/stability/current/FMDL2D_MANIFEST.json",
        "authority": "RESEARCH_PRIORITY_ONLY_NO_TRADE_AUTHORITY",
        "trade_authority": "NONE",
        "next_phase": "FMDL-3_FINANCIAL_AND_VALUATION_DATA_HARDENING",
    }
    (current / "FMDL2_FINAL_RELEASE.json").write_text(
        json.dumps(release, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    status_path = root / STATUS.relative_to(ROOT)
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(
        json.dumps(release, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    screen_path = root / SCREEN_RELEASE.relative_to(ROOT)
    screen_release = read_json(screen_path)
    if screen_release.get("release_id") != acceptance.get("screening_release_id"):
        raise RuntimeError("SCREENING_RELEASE_CHANGED_DURING_FMDL2D")
    screen_release["stability_status"] = "ACCEPTED_FMDL2D_OPERATIONAL_STABILITY"
    screen_release["fmdl2d_release_id"] = release["release_id"]
    screen_release["fmdl2_final_status"] = release["status"]
    screen_release["trade_authority"] = "NONE"
    screen_path.write_text(
        json.dumps(screen_release, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(release, ensure_ascii=False))
    return release


if __name__ == "__main__":
    publish()
