from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd


def stable_symbol_order(symbols: list[str]) -> list[str]:
    return sorted(symbols, key=lambda symbol: (hashlib.sha256(symbol.encode("utf-8")).hexdigest(), symbol))


def assign_shards(symbols: list[str], shard_count: int) -> dict[int, list[str]]:
    result = {shard_id: [] for shard_id in range(shard_count)}
    for index, symbol in enumerate(stable_symbol_order(sorted(set(symbols)))):
        result[index % shard_count].append(symbol)
    return result


def load_universe(path: Path) -> list[str]:
    frame = pd.read_csv(path, encoding="utf-8-sig", usecols=["symbol"])
    return sorted(set(frame["symbol"].dropna().astype(str)))


def shard_membership_hash(symbols: list[str]) -> str:
    payload = json.dumps(sorted(symbols), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def empty_frame(columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=columns)
