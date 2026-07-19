from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable

import pandas as pd

FACTOR_VERSION = "1.0.0"
VALID_STATES = {"VALID", "VALID_WITH_WARNING"}
INELIGIBLE_PRECEDENCE = [
    "CONFLICTED_INPUT",
    "QUARANTINED_INPUT",
    "RESTATEMENT_REPLAY_BLOCKED",
    "NON_COMPARABLE_INPUT",
    "STALE_INPUT",
    "INVALID_SIGN_TRANSITION",
    "INVALID_DENOMINATOR",
    "MISSING_REQUIRED_INPUT",
]


def stable_hash(payload: dict[str, Any]) -> str:
    text = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def max_timestamp(values: Iterable[Any]) -> str | None:
    parsed = pd.to_datetime(pd.Series(list(values)), errors="coerce", utc=True).dropna()
    if parsed.empty:
        return None
    return parsed.max().isoformat()


def combine_states(states: Iterable[str]) -> str:
    values = list(states)
    for state in INELIGIBLE_PRECEDENCE:
        if state in values:
            return state
    if "VALID_WITH_WARNING" in values:
        return "VALID_WITH_WARNING"
    return "VALID"
