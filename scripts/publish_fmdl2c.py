#!/usr/bin/env python3
"""Publish an independently validated FMDL-2C candidate as research-priority Current."""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import shutil
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
BUSINESS_TZ = ZoneInfo("Asia/Shanghai")
CANDIDATE = ROOT / "outputs/screens/candidate"
CURRENT = ROOT / "outputs/screens/current"
STATUS = ROOT / "outputs/status/FMDL2C_LAST_SUCCESS.json"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def publish(root: Path = ROOT):
    candidate = root / CANDIDATE.relative_to(ROOT)
    current = root / CURRENT.relative_to(ROOT)
    validation = read_json(candidate / "SCREENING_VALIDATION.json")
    quality = read_json(candidate / "SCREENING_QUALITY.json")
    manifest = read_json(candidate / "SCREENING_MANIFEST.json")
    if validation.get("status") != "PASS" or quality.get("hard_failures"):
        raise RuntimeError("SCREENING_CANDIDATE_NOT_VALIDATED")
    if current.exists():
        shutil.rmtree(current)
    shutil.copytree(candidate, current)
    release = {
        "release_version": "1.0.0",
        "release_id": manifest["run_id"],
        "as_of_date": manifest["as_of_date"],
        "published_at": datetime.now(tz=BUSINESS_TZ).isoformat(timespec="seconds"),
        "status": "PUBLISHED_WITH_WARNINGS" if quality.get("controlled_warnings") else "PUBLISHED",
        "manifest_path": "outputs/screens/current/SCREENING_MANIFEST.json",
        "factor_release_id": manifest["factor_release_id"],
        "stability_status": "PENDING_FMDL2D_REPLAY_AND_ECONOMIC_STABILITY",
        "authority": "RESEARCH_PRIORITY_ONLY_NO_TRADE_AUTHORITY",
        "trade_authority": "NONE",
    }
    (current / "SCREENING_CURRENT_RELEASE.json").write_text(
        json.dumps(release, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    status_path = root / STATUS.relative_to(ROOT)
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(json.dumps(release, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(release, ensure_ascii=False))
    return release


if __name__ == "__main__":
    publish()
