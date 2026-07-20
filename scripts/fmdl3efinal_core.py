from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

VOLATILE_COLUMNS = {"generated_at", "published_at", "elapsed_seconds"}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(canonical(payload), ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def clean(value: Any) -> Any:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            value = value.item()
        except (AttributeError, ValueError):
            pass
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return round(value, 12)
    return value


def canonical(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): canonical(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [canonical(item) for item in value]
    if isinstance(value, set):
        return sorted(canonical(item) for item in value)
    return clean(value)


def stable_hash(payload: Any) -> str:
    text = json.dumps(canonical(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def semantic_frame_hash(frame: pd.DataFrame, *, sort_by: Iterable[str] = ("symbol",)) -> str:
    clean_frame = frame.copy()
    clean_frame = clean_frame.drop(columns=[c for c in VOLATILE_COLUMNS if c in clean_frame.columns], errors="ignore")
    available = [column for column in sort_by if column in clean_frame.columns]
    if available:
        clean_frame = clean_frame.sort_values(available, kind="stable")
    return stable_hash(clean_frame.to_dict(orient="records"))


def manifest_for_directory(root: Path, *, excluded: set[str] | None = None) -> dict[str, Any]:
    excluded = excluded or set()
    files: list[dict[str, Any]] = []
    for path in sorted(root.iterdir()):
        if path.name in excluded or not path.is_file():
            continue
        files.append({"path": path.name, "sha256": sha256_file(path), "bytes": path.stat().st_size})
    return {"manifest_version": "1.0.0", "files": files}


def release_id(payload: dict[str, Any]) -> str:
    return str(payload.get("release_id") or "")


def chain_errors(chain: dict[str, dict[str, Any]], cfg: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    statuses = cfg["required_statuses"]
    pairs = [
        ("fmdl3d_pointer", "fmdl3d_release", "fmdl3d"),
        ("fmdl3ea_pointer", "fmdl3ea_release", "fmdl3ea"),
        ("fmdl3ebc_pointer", "fmdl3ebc_release", "fmdl3ebc"),
        ("fmdl3ede_pointer", "fmdl3ede_release", "fmdl3ede"),
    ]
    for pointer_key, release_key, status_key in pairs:
        pointer, release = chain[pointer_key], chain[release_key]
        if pointer.get("status") != statuses[status_key]:
            errors.append(f"{pointer_key.upper()}_STATUS")
        if release.get("status") != statuses[status_key]:
            errors.append(f"{release_key.upper()}_STATUS")
        if release_id(pointer) != release_id(release):
            errors.append(f"{status_key.upper()}_POINTER_RELEASE_MISMATCH")
        if pointer.get("trade_authority") != "NONE" or release.get("trade_authority") != "NONE":
            errors.append(f"{status_key.upper()}_TRADE_AUTHORITY")
    d3_id = release_id(chain["fmdl3d_release"])
    ea_id = release_id(chain["fmdl3ea_release"])
    bc_id = release_id(chain["fmdl3ebc_release"])
    de_id = release_id(chain["fmdl3ede_release"])
    baseline_ids = {
        str(chain["fmdl3ea_release"].get("baseline_id") or ""),
        str(chain["fmdl3ebc_release"].get("baseline_id") or ""),
        str(chain["fmdl3ede_release"].get("baseline_id") or ""),
    }
    if len(baseline_ids) != 1 or "" in baseline_ids:
        errors.append("BASELINE_ID_MISMATCH")
    if chain["fmdl3ea_release"].get("source_fmdl3d_release_id") != d3_id:
        errors.append("FMDL3EA_SOURCE_FMDL3D_MISMATCH")
    if chain["fmdl3ebc_release"].get("source_fmdl3d_release_id") != d3_id:
        errors.append("FMDL3EBC_SOURCE_FMDL3D_MISMATCH")
    if chain["fmdl3ede_release"].get("source_fmdl3d_release_id") != d3_id:
        errors.append("FMDL3EDE_SOURCE_FMDL3D_MISMATCH")
    if chain["fmdl3ede_release"].get("entry_release_id") != bc_id:
        errors.append("FMDL3EDE_ENTRY_RELEASE_MISMATCH")
    if chain["fmdl3ede_release"].get("incremental_release_id") != bc_id:
        errors.append("FMDL3EDE_INCREMENTAL_RELEASE_MISMATCH")
    if chain["fmdl3ea_pointer"].get("next_gate") != "FMDL-3E-BC_MARKET_AND_FINANCIAL_INCREMENTAL_REFRESH":
        errors.append("FMDL3EA_NEXT_GATE")
    if chain["fmdl3ebc_pointer"].get("next_gate") != "FMDL-3E-DE_PROPAGATION_RESILIENCE_AND_REPLAY":
        errors.append("FMDL3EBC_NEXT_GATE")
    if chain["fmdl3ede_pointer"].get("next_gate") not in cfg["acceptance"]["accepted_legacy_entry_next_gates"]:
        errors.append("FMDL3EDE_NEXT_GATE")
    if not all([d3_id, ea_id, bc_id, de_id]):
        errors.append("EMPTY_RELEASE_ID")
    return errors


def trade_authority_errors(frame: pd.DataFrame) -> int:
    if "trade_authority" not in frame.columns:
        return len(frame)
    values = set(frame["trade_authority"].dropna().astype(str))
    return 0 if values.issubset({"NONE"}) else int((frame["trade_authority"].astype(str) != "NONE").sum())


def component_lineage_errors(frame: pd.DataFrame, *, bc_release_id: str, de_release_id: str) -> int:
    if "component_release_ids_json" not in frame.columns:
        return len(frame)
    errors = 0
    for value in frame["component_release_ids_json"].tolist():
        try:
            payload = json.loads(value) if isinstance(value, str) else dict(value)
        except (json.JSONDecodeError, TypeError, ValueError):
            errors += 1
            continue
        if payload.get("FMDL-3E-BC") != bc_release_id or payload.get("FMDL-3E-DE") != de_release_id:
            errors += 1
    return errors
