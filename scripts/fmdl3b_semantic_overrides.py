from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from scripts import fmdl3b_core as core

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OVERRIDES = ROOT / "config/fmdl3b_semantic_overrides.json"


def apply_overrides(
    registry_index: dict[tuple[str, str], dict[str, Any]],
    registry_payload: dict[str, Any],
    path: Path = DEFAULT_OVERRIDES,
) -> tuple[dict[tuple[str, str], dict[str, Any]], dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    index = dict(registry_index)
    effective_payload = dict(registry_payload)
    fields = [dict(field) for field in registry_payload["fields"]]
    for override in payload["fields"]:
        field = {key: value for key, value in override.items() if key != "reason"}
        for alias in field["aliases"]:
            key = (field["statement"], core.normalize_alias(alias))
            index.pop(key, None)
            index[key] = field
        fields.append(field)
    effective_payload["fields"] = fields
    effective_payload["semantic_override_version"] = payload["override_version"]
    return index, effective_payload


def ambiguous_source_mapping_groups(raw: pd.DataFrame) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame(columns=["symbol", "statement", "report_period_end", "canonical_field_id", "source_route_id", "mapped_row_count"])
    mapped = raw[raw["canonical_field_id"].notna()].copy()
    keys = ["symbol", "statement", "report_period_end", "canonical_field_id", "source_route_id"]
    grouped = mapped.groupby(keys, dropna=False).size().reset_index(name="mapped_row_count")
    return grouped[grouped["mapped_row_count"] > 1].reset_index(drop=True)
