#!/usr/bin/env python3
"""FMDL-2D replay, stability and final FMDL-2 acceptance."""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import shutil
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from scripts.fmdl2b4_history import iter_composite_shards, read_json, sha256_file
from scripts.run_b4_factor_refresh import (
    _history_state_for_factor,
    _normalize_composite_lineage,
)
from scripts.run_basic_factor_engine import (
    EXPECTED_FACTOR_IDS,
    add_cross_sectional_fields,
    add_row_hashes,
    build_wide_table,
    compute_symbol_factor_values,
)
from scripts import run_screening_funnel as screen_engine
from scripts.run_screening_funnel_v2 import (
    build_longlist,
    classify_investability,
    evaluate_sleeve,
)

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("Asia/Shanghai")
CONFIG_PATH = ROOT / "config/fmdl2d_replay_stability.json"
OUTPUT_DIR = ROOT / "outputs/stability/candidate"


def canonical_hash(payload: Any) -> str:
    text = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    )
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _json_default(value: Any) -> Any:
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return str(value)


def clean_scalar(value: Any) -> Any:
    if value is None or pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def semantic_frame_hash(
    frame: pd.DataFrame,
    *,
    sort_by: list[str],
    exclude: set[str] | None = None,
) -> str:
    exclude = exclude or set()
    columns = sorted(column for column in frame.columns if column not in exclude)
    ordered = frame[columns].sort_values(sort_by).reset_index(drop=True)
    records = [
        {key: clean_scalar(value) for key, value in row.items()}
        for row in ordered.to_dict(orient="records")
    ]
    return canonical_hash(records)


def load_universe(root: Path) -> pd.DataFrame:
    universe = pd.read_csv(
        root / "outputs/current/A_SHARE_UNIVERSE.csv", dtype={"symbol": str}
    )
    if universe["symbol"].duplicated().any():
        raise RuntimeError("DUPLICATE_CURRENT_UNIVERSE_SYMBOL")
    required = {
        "symbol",
        "name",
        "exchange",
        "board",
        "listing_status",
        "list_date",
        "is_st",
        "is_suspended",
    }
    missing = required.difference(universe.columns)
    if missing:
        raise RuntimeError(f"UNIVERSE_IDENTITY_COLUMNS_MISSING_{sorted(missing)}")
    universe["name"] = universe["name"].astype(str).str.strip()
    if universe["name"].eq("").any() or universe["name"].str.lower().eq("nan").any():
        raise RuntimeError("EMPTY_CURRENT_UNIVERSE_NAME")
    return universe


def screen_factor_table(
    factor_table: pd.DataFrame,
    universe: pd.DataFrame,
    config: dict[str, Any],
) -> dict[str, pd.DataFrame]:
    identity_fields = [
        field
        for field in ["symbol", "name", "exchange", "listing_status", "industry_name"]
        if field in universe.columns
    ]
    identity = universe[identity_fields].drop_duplicates("symbol")
    table = factor_table.copy()
    for field in ["name", "exchange", "listing_status", "industry_name"]:
        if field in table.columns:
            table = table.drop(columns=[field])
    table = table.merge(identity, on="symbol", how="left", validate="one_to_one")
    if table["name"].isna().any():
        raise RuntimeError("REPLAY_UNBOUND_SECURITY_NAME")
    classified = table.apply(lambda row: classify_investability(row, config), axis=1)
    table["investability_status"] = [item[0] for item in classified]
    table["investability_reason_codes"] = [
        "|".join(item[1]) if item[1] else "NONE" for item in classified
    ]
    table = screen_engine.add_hash(table, "screen_row_hash")
    details: list[pd.DataFrame] = []
    for sleeve_id, sleeve in config["sleeves"].items():
        result = evaluate_sleeve(table, sleeve_id, sleeve, config)
        if not result.empty:
            details.append(result)
    detail = (
        pd.concat(details, ignore_index=True)
        if details
        else pd.DataFrame(
            columns=["as_of_date", "symbol", "name", "sleeve_id", "sleeve_score"]
        )
    )
    if not detail.empty:
        detail = screen_engine.add_hash(detail, "sleeve_row_hash")
    longlist = build_longlist(detail, table, config)
    if not longlist.empty:
        longlist = screen_engine.add_hash(longlist, "longlist_row_hash")
    funnel = screen_engine.build_funnel(table, detail, longlist)
    return {
        "screen": table,
        "detail": detail,
        "longlist": longlist,
        "funnel": funnel,
    }


def market_calendar(root: Path, history_manifest: dict[str, Any]) -> pd.DatetimeIndex:
    parts: list[pd.Series] = []
    for _, shard in iter_composite_shards(history_manifest, root=root):
        if shard.empty:
            continue
        dates = pd.to_datetime(shard["trade_date"], errors="coerce")
        parts.append(dates.dropna())
    if not parts:
        raise RuntimeError("EMPTY_REPLAY_MARKET_CALENDAR")
    return pd.DatetimeIndex(
        pd.concat(parts, ignore_index=True).drop_duplicates().sort_values()
    )


def replay_factor_table(
    root: Path,
    history_manifest: dict[str, Any],
    history_status: pd.DataFrame,
    universe: pd.DataFrame,
    full_calendar: pd.DatetimeIndex,
    as_of_date: str,
) -> pd.DataFrame:
    factor_registry = read_json(root / "config/fmdl2_factor_registry.json")
    engine_config = read_json(root / "config/fmdl2_factor_engine.json")
    replay_calendar = full_calendar[full_calendar <= pd.Timestamp(as_of_date)]
    if replay_calendar.empty or replay_calendar[-1] != pd.Timestamp(as_of_date):
        raise RuntimeError(f"REPLAY_DATE_NOT_MARKET_SESSION_{as_of_date}")
    universe_map = universe.set_index("symbol").to_dict(orient="index")
    status_map = history_status.set_index("symbol").to_dict(orient="index")
    status_rows: list[dict[str, Any]] = []
    detail_rows: list[dict[str, Any]] = []
    processed: set[str] = set()
    target = pd.Timestamp(as_of_date)

    for _, shard in iter_composite_shards(history_manifest, root=root):
        if shard.empty:
            continue
        shard = shard.copy()
        shard["trade_date"] = pd.to_datetime(shard["trade_date"], errors="coerce")
        for symbol, group in shard.groupby("symbol", sort=True):
            symbol = str(symbol)
            if symbol not in universe_map:
                continue
            if symbol in processed:
                raise RuntimeError(f"REPLAY_SYMBOL_MULTIPLE_SHARDS_{symbol}")
            processed.add(symbol)
            normalized, lineage_state = _normalize_composite_lineage(group)
            hstatus = status_map.get(symbol, {})
            provider_id = str(hstatus.get("provider_id", "NONE"))
            factor_state = _history_state_for_factor(
                str(hstatus.get("refresh_state", "QUARANTINED")), provider_id
            )
            list_date = pd.to_datetime(
                universe_map[symbol].get("list_date"), errors="coerce"
            )
            listed = pd.isna(list_date) or list_date <= target
            has_session = bool((group["trade_date"] == target).any()) if listed else False
            event_count = 0 if has_session else 1
            urow = {"symbol": symbol, **universe_map[symbol]}
            urow["is_suspended"] = bool(listed and not has_session)
            base, details = compute_symbol_factor_values(
                normalized,
                urow,
                {"symbol": symbol, "state": factor_state, "provider_id": provider_id},
                factor_registry,
                engine_config,
                replay_calendar,
                as_of_date,
                event_count,
            )
            base["history_refresh_state"] = hstatus.get("refresh_state")
            base["history_lineage_state"] = lineage_state
            if lineage_state == "UNVALIDATED_COMPOSITE_LINEAGE":
                base["factor_record_quality"] = "SUSPECT"
                base["confidence_grade"] = "D"
            for row in details:
                row["history_refresh_state"] = hstatus.get("refresh_state")
                row["history_lineage_state"] = lineage_state
                if lineage_state == "UNVALIDATED_COMPOSITE_LINEAGE":
                    row["factor_record_quality"] = "SUSPECT"
                    row["confidence_grade"] = "D"
            status_rows.append(base)
            detail_rows.extend(details)

    for symbol in sorted(set(universe_map).difference(processed)):
        hstatus = status_map.get(symbol, {})
        provider_id = str(hstatus.get("provider_id", "NONE"))
        urow = {"symbol": symbol, **universe_map[symbol]}
        urow["is_suspended"] = False
        base, details = compute_symbol_factor_values(
            None,
            urow,
            {"symbol": symbol, "state": "QUARANTINED", "provider_id": provider_id},
            factor_registry,
            engine_config,
            replay_calendar,
            as_of_date,
            1,
        )
        base["history_refresh_state"] = hstatus.get("refresh_state")
        base["history_lineage_state"] = "NO_COMPOSITE_HISTORY"
        for row in details:
            row["history_refresh_state"] = hstatus.get("refresh_state")
            row["history_lineage_state"] = "NO_COMPOSITE_HISTORY"
        status_rows.append(base)
        detail_rows.extend(details)

    status_frame = pd.DataFrame(status_rows).sort_values(
        ["board", "symbol"]
    ).reset_index(drop=True)
    detail_frame = pd.DataFrame(detail_rows).sort_values(
        ["factor_id", "board", "symbol"]
    ).reset_index(drop=True)
    detail_frame = add_cross_sectional_fields(detail_frame, engine_config)
    detail_frame["history_release_id"] = history_manifest["release_id"]
    detail_frame["factor_contract_version"] = factor_registry["contract_version"]
    detail_frame = add_row_hashes(detail_frame)
    wide = build_wide_table(status_frame, detail_frame)
    if len(wide) != len(universe):
        raise RuntimeError(f"REPLAY_WIDE_ROWS_{len(wide)}_EXPECTED_{len(universe)}")
    return wide


def rank_transition(
    previous: pd.DataFrame,
    current: pd.DataFrame,
    previous_date: str,
    current_date: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    prev = previous.set_index("symbol")
    curr = current.set_index("symbol")
    common = sorted(set(prev.index).intersection(curr.index))
    overlap_denominator = max(1, min(len(prev), len(curr)))
    top_prev = set(previous.nsmallest(20, "overall_rank")["symbol"])
    top_curr = set(current.nsmallest(20, "overall_rank")["symbol"])
    if len(common) >= 2:
        ranks = pd.DataFrame(
            {
                "previous": pd.to_numeric(prev.loc[common, "overall_rank"]),
                "current": pd.to_numeric(curr.loc[common, "overall_rank"]),
            }
        )
        spearman = float(ranks["previous"].corr(ranks["current"], method="spearman"))
        median_abs = float((ranks["previous"] - ranks["current"]).abs().median())
    else:
        spearman = math.nan
        median_abs = math.nan
    primary_retention = (
        float(
            (
                prev.loc[common, "primary_sleeve"].astype(str).values
                == curr.loc[common, "primary_sleeve"].astype(str).values
            ).mean()
        )
        if common
        else 0.0
    )
    priority_retention = (
        float(
            (
                prev.loc[common, "research_priority"].astype(str).values
                == curr.loc[common, "research_priority"].astype(str).values
            ).mean()
        )
        if common
        else 0.0
    )
    summary = {
        "previous_date": previous_date,
        "current_date": current_date,
        "previous_rows": len(previous),
        "current_rows": len(current),
        "common_symbols": len(common),
        "overlap_ratio": len(common) / overlap_denominator,
        "entrants": len(set(curr.index).difference(prev.index)),
        "exits": len(set(prev.index).difference(curr.index)),
        "top20_overlap_ratio": len(top_prev.intersection(top_curr)) / 20.0,
        "common_rank_spearman": spearman,
        "median_absolute_rank_change": median_abs,
        "primary_sleeve_retention": primary_retention,
        "priority_bucket_retention": priority_retention,
    }
    migrations: list[dict[str, Any]] = []
    for symbol in common:
        migrations.append(
            {
                "previous_date": previous_date,
                "current_date": current_date,
                "symbol": symbol,
                "name": str(curr.loc[symbol, "name"]),
                "previous_rank": int(prev.loc[symbol, "overall_rank"]),
                "current_rank": int(curr.loc[symbol, "overall_rank"]),
                "rank_change": int(
                    prev.loc[symbol, "overall_rank"] - curr.loc[symbol, "overall_rank"]
                ),
                "previous_priority": str(prev.loc[symbol, "research_priority"]),
                "current_priority": str(curr.loc[symbol, "research_priority"]),
                "previous_primary_sleeve": str(prev.loc[symbol, "primary_sleeve"]),
                "current_primary_sleeve": str(curr.loc[symbol, "primary_sleeve"]),
            }
        )
    return summary, migrations


def sleeve_transition(
    previous: pd.DataFrame,
    current: pd.DataFrame,
    previous_date: str,
    current_date: str,
    sleeve_ids: list[str],
) -> list[dict[str, Any]]:
    rows = []
    for sleeve_id in sleeve_ids:
        left = set(
            previous.loc[previous["sleeve_id"] == sleeve_id, "symbol"].astype(str)
        )
        right = set(
            current.loc[current["sleeve_id"] == sleeve_id, "symbol"].astype(str)
        )
        union = left.union(right)
        rows.append(
            {
                "previous_date": previous_date,
                "current_date": current_date,
                "sleeve_id": sleeve_id,
                "previous_members": len(left),
                "current_members": len(right),
                "common_members": len(left.intersection(right)),
                "jaccard": len(left.intersection(right)) / len(union) if union else 1.0,
            }
        )
    return rows


def concentration(longlist: pd.DataFrame) -> dict[str, Any]:
    board_share = longlist["board"].value_counts(normalize=True)
    industry = longlist.get(
        "industry_name", pd.Series(index=longlist.index, dtype=object)
    )
    known = (
        industry.notna()
        & industry.astype(str).str.strip().ne("")
        & industry.astype(str).str.lower().ne("nan")
    )
    industry_share = industry.loc[known].astype(str).value_counts(normalize=True)
    return {
        "maximum_board_share": float(board_share.max()) if not board_share.empty else 0.0,
        "board_hhi": float((board_share**2).sum()) if not board_share.empty else 0.0,
        "largest_board": str(board_share.index[0]) if not board_share.empty else None,
        "industry_identity_coverage": float(known.mean()) if len(industry) else 0.0,
        "maximum_known_industry_share": (
            float(industry_share.max()) if not industry_share.empty else None
        ),
        "largest_known_industry": (
            str(industry_share.index[0]) if not industry_share.empty else None
        ),
    }


def fragility_review(
    longlist: pd.DataFrame,
    screening_config: dict[str, Any],
    stability_config: dict[str, Any],
) -> pd.DataFrame:
    rows = []
    rule = stability_config["fragility"]
    for row in longlist.to_dict(orient="records"):
        board = str(row.get("board", "DEFAULT"))
        floor = screen_engine.liquidity_threshold(board, screening_config)
        flags = []
        if int(row.get("sleeve_count", 0)) <= 1:
            flags.append("SINGLE_SLEEVE")
        if int(row.get("overall_rank", 0)) >= int(rule["bottom_rank_start"]):
            flags.append("BOTTOM_QUARTILE_RANK")
        if str(row.get("factor_record_quality")) != "VALID":
            flags.append("NON_VALID_FACTOR_RECORD")
        if int(row.get("event_flag_count", 0)) > 0:
            flags.append("CURRENT_EVENT_FLAG")
        turnover = pd.to_numeric(
            pd.Series([row.get("avg_turnover_cny_20d")]), errors="coerce"
        ).iloc[0]
        if pd.notna(turnover) and float(turnover) < floor * float(
            rule["liquidity_floor_multiple"]
        ):
            flags.append("LIQUIDITY_NEAR_FLOOR")
        drawdown = pd.to_numeric(
            pd.Series([row.get("max_drawdown_120d")]), errors="coerce"
        ).iloc[0]
        if pd.notna(drawdown) and float(drawdown) < float(
            rule["large_drawdown_threshold"]
        ):
            flags.append("LARGE_120D_DRAWDOWN")
        ret20 = pd.to_numeric(
            pd.Series([row.get("return_20d")]), errors="coerce"
        ).iloc[0]
        if pd.notna(ret20) and float(ret20) < 0:
            flags.append("NEGATIVE_20D_RETURN")
        rows.append(
            {
                "as_of_date": row.get("as_of_date"),
                "overall_rank": row.get("overall_rank"),
                "research_priority": row.get("research_priority"),
                "symbol": row.get("symbol"),
                "name": row.get("name"),
                "primary_sleeve": row.get("primary_sleeve"),
                "flag_count": len(flags),
                "structural_fragility_flag": len(flags)
                >= int(rule["fragile_minimum_flags"]),
                "risk_flags": "|".join(flags) if flags else "NONE",
            }
        )
    return pd.DataFrame(rows)


def historical_anchor_match(
    root: Path,
    replay_wide: pd.DataFrame,
    anchor_date: str,
) -> dict[str, Any]:
    manifest_path = root / "outputs/factors/candidate/BASIC_FACTOR_MANIFEST.json"
    if not manifest_path.exists():
        return {"status": "NOT_AVAILABLE"}
    manifest = read_json(manifest_path)
    if str(manifest.get("as_of_date")) != anchor_date:
        return {
            "status": "DATE_MISMATCH",
            "expected": anchor_date,
            "actual": manifest.get("as_of_date"),
        }
    anchor = pd.read_parquet(
        root / "outputs/factors/candidate/BASIC_FACTOR_TABLE.parquet"
    )
    left = replay_wide.set_index("symbol")
    right = anchor.set_index("symbol")
    common = sorted(set(left.index).intersection(right.index))
    matches = 0
    compared = 0
    mismatches = 0
    for factor_id in sorted(EXPECTED_FACTOR_IDS):
        a = pd.to_numeric(left.loc[common, factor_id], errors="coerce")
        b = pd.to_numeric(right.loc[common, factor_id], errors="coerce")
        both_null = a.isna() & b.isna()
        both_value = a.notna() & b.notna()
        tolerance_match = (
            (a[both_value] - b[both_value]).abs()
            <= 1e-10 * (1.0 + b[both_value].abs())
        )
        matches += int(both_null.sum()) + int(tolerance_match.sum())
        compared += len(common)
        mismatches += int((~both_null & ~both_value).sum()) + int(
            (~tolerance_match).sum()
        )
    return {
        "status": "COMPARED",
        "anchor_run_id": manifest.get("run_id"),
        "common_symbols": len(common),
        "factor_cells_compared": compared,
        "matching_cells": matches,
        "mismatching_cells": mismatches,
        "match_ratio": matches / compared if compared else 0.0,
    }


def write_outputs(
    output_dir: Path,
    payload: dict[str, Any],
    daily: pd.DataFrame,
    transitions: pd.DataFrame,
    sleeve_transitions: pd.DataFrame,
    migrations: pd.DataFrame,
    fragility: pd.DataFrame,
    replay_longlists: pd.DataFrame,
) -> dict[str, Any]:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "acceptance": output_dir / "FMDL2D_ACCEPTANCE.json",
        "daily_replay_summary": output_dir / "DAILY_REPLAY_SUMMARY.csv",
        "rank_transitions": output_dir / "RANK_TRANSITIONS.csv",
        "sleeve_transitions": output_dir / "SLEEVE_TRANSITIONS.csv",
        "rank_migrations": output_dir / "RANK_MIGRATIONS.csv",
        "false_positive_risk_review": output_dir
        / "FALSE_POSITIVE_RISK_REVIEW.csv",
        "replay_longlists": output_dir / "REPLAY_LONGLISTS.csv",
    }
    files["acceptance"].write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    daily.to_csv(files["daily_replay_summary"], index=False, encoding="utf-8-sig")
    transitions.to_csv(files["rank_transitions"], index=False, encoding="utf-8-sig")
    sleeve_transitions.to_csv(
        files["sleeve_transitions"], index=False, encoding="utf-8-sig"
    )
    migrations.to_csv(files["rank_migrations"], index=False, encoding="utf-8-sig")
    fragility.to_csv(
        files["false_positive_risk_review"], index=False, encoding="utf-8-sig"
    )
    replay_longlists.to_csv(
        files["replay_longlists"], index=False, encoding="utf-8-sig"
    )
    artifacts = []
    row_counts = {
        "acceptance": 1,
        "daily_replay_summary": len(daily),
        "rank_transitions": len(transitions),
        "sleeve_transitions": len(sleeve_transitions),
        "rank_migrations": len(migrations),
        "false_positive_risk_review": len(fragility),
        "replay_longlists": len(replay_longlists),
    }
    for dataset_id, path in files.items():
        artifacts.append(
            {
                "dataset_id": dataset_id,
                "path": str(path.relative_to(ROOT)),
                "sha256": sha256_file(path),
                "row_count": int(row_counts[dataset_id]),
                "bytes": path.stat().st_size,
            }
        )
    manifest = {
        "manifest_version": "1.0.0",
        "run_id": payload["run_id"],
        "generated_at": payload["generated_at"],
        "as_of_date": payload["as_of_date"],
        "replay_dates": payload["replay_dates"],
        "screening_release_id": payload["screening_release_id"],
        "factor_release_id": payload["factor_release_id"],
        "artifacts": artifacts,
        "aggregate_sha256": canonical_hash(artifacts),
        "status": "CANDIDATE_ACCEPTED"
        if not payload["hard_failures"]
        else "CANDIDATE_REJECTED",
        "authority": "RESEARCH_PRIORITY_ONLY_NO_TRADE_AUTHORITY",
        "trade_authority": "NONE",
    }
    (output_dir / "FMDL2D_MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def run(root: Path = ROOT, output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    stability_config = read_json(root / CONFIG_PATH.relative_to(ROOT))
    screening_config = read_json(root / "config/fmdl2_screening_funnel.json")
    universe = load_universe(root)
    history_manifest = read_json(
        root / "outputs/history/current/HISTORY_CURRENT_MANIFEST.json"
    )
    history_status = pd.read_csv(
        root / "outputs/history/current/HISTORY_CURRENT_STATUS.csv",
        dtype={"symbol": str},
    )
    screen_release = read_json(
        root / "outputs/screens/current/SCREENING_CURRENT_RELEASE.json"
    )
    factor_release = read_json(
        root / "outputs/factors/current/FACTOR_CURRENT_RELEASE.json"
    )
    full_calendar = market_calendar(root, history_manifest)
    sessions = int(stability_config["replay"]["sessions"])
    replay_dates = [
        timestamp.date().isoformat() for timestamp in full_calendar[-sessions:]
    ]
    if replay_dates[-1] != str(screen_release["as_of_date"]):
        raise RuntimeError("REPLAY_LATEST_DATE_NOT_SCREENING_CURRENT")

    current_factor = pd.read_parquet(
        root / "outputs/factors/current/BASIC_FACTOR_TABLE.parquet"
    )
    deterministic = screen_factor_table(current_factor, universe, screening_config)
    official = {
        "screen": pd.read_parquet(
            root / "outputs/screens/current/SCREENING_UNIVERSE.parquet"
        ),
        "detail": pd.read_parquet(
            root / "outputs/screens/current/SCREENING_SLEEVE_DETAIL.parquet"
        ),
        "longlist": pd.read_csv(
            root / "outputs/screens/current/SCREENING_LONGLIST.csv",
            dtype={"symbol": str},
        ),
        "funnel": pd.read_csv(root / "outputs/screens/current/SCREENING_FUNNEL.csv"),
    }
    replay_hashes = {
        "screen": semantic_frame_hash(
            deterministic["screen"],
            sort_by=["symbol"],
            exclude={"screen_row_hash", "row_hash"},
        ),
        "detail": semantic_frame_hash(
            deterministic["detail"],
            sort_by=["sleeve_id", "symbol"],
            exclude={"sleeve_row_hash"},
        ),
        "longlist": semantic_frame_hash(
            deterministic["longlist"],
            sort_by=["overall_rank", "symbol"],
            exclude={"longlist_row_hash"},
        ),
        "funnel": semantic_frame_hash(
            deterministic["funnel"], sort_by=["stage"]
        ),
    }
    official_hashes = {
        "screen": semantic_frame_hash(
            official["screen"],
            sort_by=["symbol"],
            exclude={"screen_row_hash", "row_hash"},
        ),
        "detail": semantic_frame_hash(
            official["detail"],
            sort_by=["sleeve_id", "symbol"],
            exclude={"sleeve_row_hash"},
        ),
        "longlist": semantic_frame_hash(
            official["longlist"],
            sort_by=["overall_rank", "symbol"],
            exclude={"longlist_row_hash"},
        ),
        "funnel": semantic_frame_hash(official["funnel"], sort_by=["stage"]),
    }
    same_date_match = {
        key: replay_hashes[key] == official_hashes[key] for key in replay_hashes
    }

    replay_results: dict[str, dict[str, pd.DataFrame]] = {}
    replay_wide: dict[str, pd.DataFrame] = {}
    daily_rows = []
    all_longlists = []
    for date in replay_dates:
        wide = replay_factor_table(
            root, history_manifest, history_status, universe, full_calendar, date
        )
        replay_wide[date] = wide
        result = screen_factor_table(wide, universe, screening_config)
        replay_results[date] = result
        longlist = result["longlist"].copy()
        longlist["replay_date"] = date
        all_longlists.append(longlist)
        fragility = fragility_review(longlist, screening_config, stability_config)
        conc = concentration(longlist)
        primary = longlist["primary_sleeve"].value_counts().to_dict()
        daily_rows.append(
            {
                "as_of_date": date,
                "screen_rows": len(result["screen"]),
                "longlist_rows": len(longlist),
                "priority_a": int(
                    (longlist["research_priority"] == "A_IMMEDIATE_RESEARCH").sum()
                ),
                "priority_b": int(
                    (longlist["research_priority"] == "B_WATCH_OR_TRIGGER").sum()
                ),
                "priority_c": int(
                    (longlist["research_priority"] == "C_SCREEN_FLAG_ONLY").sum()
                ),
                "defensive_primary": int(primary.get("DEFENSIVE_STABILITY", 0)),
                "trend_primary": int(primary.get("TREND_PERSISTENCE", 0)),
                "breakout_primary": int(primary.get("LIQUID_BREAKOUT", 0)),
                "recovery_primary": int(primary.get("RECOVERY_WATCH", 0)),
                "maximum_board_share": conc["maximum_board_share"],
                "board_hhi": conc["board_hhi"],
                "largest_board": conc["largest_board"],
                "industry_identity_coverage": conc["industry_identity_coverage"],
                "maximum_known_industry_share": conc[
                    "maximum_known_industry_share"
                ],
                "fragile_share": float(
                    fragility["structural_fragility_flag"].mean()
                ),
                "priority_a_fragile_share": float(
                    fragility.loc[
                        fragility["research_priority"] == "A_IMMEDIATE_RESEARCH",
                        "structural_fragility_flag",
                    ].mean()
                ),
            }
        )

    transition_rows = []
    migration_rows: list[dict[str, Any]] = []
    sleeve_rows: list[dict[str, Any]] = []
    for previous_date, current_date in zip(replay_dates[:-1], replay_dates[1:]):
        summary, migrations = rank_transition(
            replay_results[previous_date]["longlist"],
            replay_results[current_date]["longlist"],
            previous_date,
            current_date,
        )
        transition_rows.append(summary)
        migration_rows.extend(migrations)
        sleeve_rows.extend(
            sleeve_transition(
                replay_results[previous_date]["detail"],
                replay_results[current_date]["detail"],
                previous_date,
                current_date,
                list(screening_config["sleeves"]),
            )
        )

    daily = pd.DataFrame(daily_rows)
    transitions = pd.DataFrame(transition_rows)
    sleeve_transitions = pd.DataFrame(sleeve_rows)
    migrations = pd.DataFrame(migration_rows)
    current_fragility = fragility_review(
        replay_results[replay_dates[-1]]["longlist"],
        screening_config,
        stability_config,
    )
    replay_longlists = pd.concat(all_longlists, ignore_index=True)
    anchor_date = str(
        read_json(
            root / stability_config["replay"]["historical_anchor_factor_manifest"]
        )["as_of_date"]
    )
    anchor = historical_anchor_match(root, replay_wide[anchor_date], anchor_date)

    hard = stability_config["hard_gates"]
    failures: list[str] = []
    warnings: list[str] = []
    if not all(same_date_match.values()):
        failures.append("SAME_DATE_SEMANTIC_REPLAY_MISMATCH")
    if len(replay_dates) < int(hard["minimum_replay_sessions"]):
        failures.append("INSUFFICIENT_REPLAY_SESSIONS")
    if int(daily["longlist_rows"].min()) < int(
        hard["minimum_longlist_rows_per_session"]
    ):
        failures.append("THIN_REPLAY_LONGLIST")
    if float(transitions["overlap_ratio"].mean()) < float(
        hard["minimum_average_consecutive_longlist_overlap"]
    ):
        failures.append("AVERAGE_LONGLIST_OVERLAP_BELOW_HARD_GATE")
    if float(transitions["overlap_ratio"].min()) < float(
        hard["minimum_single_transition_longlist_overlap"]
    ):
        failures.append("SINGLE_TRANSITION_OVERLAP_BELOW_HARD_GATE")
    if float(transitions["top20_overlap_ratio"].mean()) < float(
        hard["minimum_average_top20_overlap"]
    ):
        failures.append("TOP20_OVERLAP_BELOW_HARD_GATE")
    if float(transitions["common_rank_spearman"].median()) < float(
        hard["minimum_median_common_rank_spearman"]
    ):
        failures.append("RANK_SPEARMAN_BELOW_HARD_GATE")
    if float(transitions["primary_sleeve_retention"].mean()) < float(
        hard["minimum_average_primary_sleeve_retention"]
    ):
        failures.append("PRIMARY_SLEEVE_RETENTION_BELOW_HARD_GATE")
    if float(daily["maximum_board_share"].max()) > float(
        hard["maximum_board_share"]
    ):
        failures.append("BOARD_CONCENTRATION_SHARE_HARD_FAIL")
    if float(daily["board_hhi"].max()) > float(hard["maximum_board_hhi"]):
        failures.append("BOARD_CONCENTRATION_HHI_HARD_FAIL")
    current_a_fragile = float(
        current_fragility.loc[
            current_fragility["research_priority"] == "A_IMMEDIATE_RESEARCH",
            "structural_fragility_flag",
        ].mean()
    )
    if current_a_fragile > float(hard["maximum_priority_a_fragile_share"]):
        failures.append("PRIORITY_A_STRUCTURAL_FRAGILITY_HARD_FAIL")
    if anchor.get("status") == "COMPARED" and float(anchor["match_ratio"]) < 0.99:
        failures.append("HISTORICAL_FACTOR_ANCHOR_MATCH_BELOW_99_PERCENT")

    targets = stability_config["target_ranges"]
    target_checks = {
        "average_consecutive_longlist_overlap": float(
            transitions["overlap_ratio"].mean()
        ),
        "average_top20_overlap": float(transitions["top20_overlap_ratio"].mean()),
        "median_common_rank_spearman": float(
            transitions["common_rank_spearman"].median()
        ),
        "average_primary_sleeve_retention": float(
            transitions["primary_sleeve_retention"].mean()
        ),
        "maximum_longlist_fragile_share": float(daily["fragile_share"].max()),
        "minimum_industry_identity_coverage": float(
            daily["industry_identity_coverage"].min()
        ),
    }
    if target_checks["average_consecutive_longlist_overlap"] < float(
        targets["average_consecutive_longlist_overlap"]
    ):
        warnings.append("LONGLIST_OVERLAP_BELOW_TARGET")
    if target_checks["average_top20_overlap"] < float(
        targets["average_top20_overlap"]
    ):
        warnings.append("TOP20_OVERLAP_BELOW_TARGET")
    if target_checks["median_common_rank_spearman"] < float(
        targets["median_common_rank_spearman"]
    ):
        warnings.append("RANK_SPEARMAN_BELOW_TARGET")
    if target_checks["average_primary_sleeve_retention"] < float(
        targets["average_primary_sleeve_retention"]
    ):
        warnings.append("PRIMARY_SLEEVE_RETENTION_BELOW_TARGET")
    if target_checks["maximum_longlist_fragile_share"] > float(
        targets["maximum_longlist_fragile_share"]
    ):
        warnings.append("LONGLIST_STRUCTURAL_FRAGILITY_ABOVE_TARGET")
    if target_checks["minimum_industry_identity_coverage"] < float(
        targets["minimum_industry_identity_coverage"]
    ):
        warnings.append("INDUSTRY_IDENTITY_COVERAGE_BELOW_TARGET")

    generated_at = datetime.now(tz=TZ).isoformat(timespec="seconds")
    payload = {
        "acceptance_version": "1.0.0",
        "run_id": "FMDL2D_" + generated_at.replace("-", "").replace(":", ""),
        "generated_at": generated_at,
        "as_of_date": replay_dates[-1],
        "replay_dates": replay_dates,
        "replay_mode": stability_config["replay"]["mode"],
        "screening_release_id": screen_release["release_id"],
        "factor_release_id": factor_release["release_id"],
        "history_release_id": history_manifest["release_id"],
        "status": "FAIL" if failures else "PASS_WITH_CONTROLLED_LIMITATIONS",
        "acceptance_state": (
            "REJECTED"
            if failures
            else "ACCEPTED_OPERATIONAL_STABILITY_WITH_LIMITED_COHORT_REPLAY_NO_ALPHA_CLAIM"
        ),
        "hard_failures": failures,
        "controlled_warnings": warnings,
        "same_date_semantic_replay": {
            "status": "PASS" if all(same_date_match.values()) else "FAIL",
            "artifact_matches": same_date_match,
            "replay_hashes": replay_hashes,
            "official_hashes": official_hashes,
        },
        "metrics": {
            "replay_sessions": len(replay_dates),
            "minimum_longlist_rows": int(daily["longlist_rows"].min()),
            "average_consecutive_longlist_overlap": float(
                transitions["overlap_ratio"].mean()
            ),
            "minimum_consecutive_longlist_overlap": float(
                transitions["overlap_ratio"].min()
            ),
            "average_top20_overlap": float(
                transitions["top20_overlap_ratio"].mean()
            ),
            "median_common_rank_spearman": float(
                transitions["common_rank_spearman"].median()
            ),
            "average_median_absolute_rank_change": float(
                transitions["median_absolute_rank_change"].mean()
            ),
            "average_primary_sleeve_retention": float(
                transitions["primary_sleeve_retention"].mean()
            ),
            "average_priority_bucket_retention": float(
                transitions["priority_bucket_retention"].mean()
            ),
            "maximum_board_share": float(daily["maximum_board_share"].max()),
            "maximum_board_hhi": float(daily["board_hhi"].max()),
            "minimum_industry_identity_coverage": float(
                daily["industry_identity_coverage"].min()
            ),
            "maximum_longlist_fragile_share": float(
                daily["fragile_share"].max()
            ),
            "current_priority_a_fragile_share": current_a_fragile,
        },
        "historical_factor_anchor": anchor,
        "false_positive_review_posture": "EX_ANTE_STRUCTURAL_RISK_ONLY_NO_FUTURE_RETURN_OR_REALIZED_FALSE_POSITIVE_CLAIM",
        "controlled_limitations": [
            "FIXED_CURRENT_UNIVERSE_COHORT_NOT_POINT_IN_TIME_SURVIVORSHIP_FREE",
            "SIX_SESSION_OPERATIONAL_WINDOW_NOT_LONG_HORIZON_BACKTEST",
            "CURRENT_SECURITY_MASTER_ST_IDENTITY_MAY_NOT_BE_POINT_IN_TIME",
            "INDUSTRY_IDENTITY_INCOMPLETE_AND_NOT_USED_AS_A_HARD_QUOTA",
            "NO_FUTURE_RETURN_ALPHA_OR_REALIZED_FALSE_POSITIVE_TEST",
            "FINANCIAL_QUALITY_VALUATION_AND_ESTIMATES_DEFERRED_TO_FMDL3",
        ],
        "authority": "RESEARCH_PRIORITY_ONLY_NO_TRADE_AUTHORITY",
        "trade_authority": "NONE",
        "next_phase": "FMDL-3_FINANCIAL_AND_VALUATION_DATA_HARDENING",
    }
    manifest = write_outputs(
        output_dir,
        payload,
        daily,
        transitions,
        sleeve_transitions,
        migrations,
        current_fragility,
        replay_longlists,
    )
    if failures:
        raise RuntimeError(";".join(failures))
    print(json.dumps({"acceptance": payload, "manifest": manifest}, ensure_ascii=False))
    return {"acceptance": payload, "manifest": manifest}


if __name__ == "__main__":
    run()
