#!/usr/bin/env python3
"""Build the FMDL-2C research-priority screening sleeves and funnel."""
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

ROOT = Path(__file__).resolve().parents[1]
BUSINESS_TZ = ZoneInfo("Asia/Shanghai")
CONFIG_PATH = ROOT / "config/fmdl2_screening_funnel.json"
DEFAULT_OUTPUT = ROOT / "outputs/screens/candidate"
PUBLISHED = {"PUBLISHED", "PUBLISHED_WITH_WARNINGS"}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_hash(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(encoded.encode()).hexdigest()


def as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def finite(value: Any) -> float | None:
    converted = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(converted):
        return None
    number = float(converted)
    return number if math.isfinite(number) else None


def load_inputs(root: Path = ROOT) -> tuple[dict[str, Any], dict[str, Any], pd.DataFrame]:
    config = read_json(root / CONFIG_PATH.relative_to(ROOT))
    paths = config["inputs"]
    release = read_json(root / paths["factor_release"])
    manifest = read_json(root / paths["factor_manifest"])
    quality = read_json(root / paths["factor_quality"])
    errors: list[str] = []
    if release.get("status") not in PUBLISHED:
        errors.append("FACTOR_CURRENT_NOT_PUBLISHED")
    if quality.get("hard_failures"):
        errors.append("FACTOR_CURRENT_HAS_HARD_FAILURES")
    if release.get("as_of_date") != manifest.get("as_of_date"):
        errors.append("FACTOR_RELEASE_MANIFEST_AS_OF_MISMATCH")
    if release.get("history_release_id") != manifest.get("history_release_id"):
        errors.append("FACTOR_HISTORY_RELEASE_MISMATCH")
    artifact_map = {item["dataset_id"]: item for item in manifest.get("artifacts", [])}
    factor_artifact = artifact_map.get("basic_factor_table")
    if not factor_artifact:
        errors.append("FACTOR_TABLE_ARTIFACT_MISSING")
    else:
        path = root / factor_artifact["path"]
        if not path.exists():
            errors.append("FACTOR_TABLE_FILE_MISSING")
        elif sha256_file(path) != factor_artifact.get("sha256"):
            errors.append("FACTOR_TABLE_HASH_MISMATCH")
    if config.get("authority_boundary") != "RESEARCH_PRIORITY_ONLY_NO_TRADE_AUTHORITY":
        errors.append("SCREENING_AUTHORITY_BOUNDARY_MISMATCH")
    if errors:
        raise RuntimeError(";".join(errors))
    table = pd.read_parquet(root / paths["factor_table"])
    if len(table) != int(manifest["universe_symbols"]):
        raise RuntimeError("FACTOR_TABLE_ROW_COUNT_MISMATCH")
    if table["symbol"].astype(str).duplicated().any():
        raise RuntimeError("DUPLICATE_FACTOR_TABLE_SYMBOL")
    if set(table["as_of_date"].astype(str)) != {str(release["as_of_date"])}:
        raise RuntimeError("FACTOR_TABLE_AS_OF_MISMATCH")
    return config, {"release": release, "manifest": manifest, "quality": quality}, table


def liquidity_threshold(board: str, config: dict[str, Any]) -> float:
    thresholds = config["investability"]["minimum_avg_turnover_cny_20d"]
    return float(thresholds.get(board, thresholds["DEFAULT"]))


def classify_investability(row: pd.Series, config: dict[str, Any]) -> tuple[str, list[str]]:
    rule = config["investability"]
    reasons: list[str] = []
    quality = str(row.get("factor_record_quality", "UNKNOWN"))
    confidence = str(row.get("confidence_grade", "D"))
    if quality in set(rule["excluded_factor_record_quality"]):
        reasons.append(f"FACTOR_RECORD_{quality}")
        return "EXCLUDED", reasons
    if rule["exclude_suspended"] and as_bool(row.get("is_suspended")):
        reasons.append("CURRENTLY_SUSPENDED")
        return "EXCLUDED", reasons
    avg_turnover = finite(row.get("avg_turnover_cny_20d"))
    threshold = liquidity_threshold(str(row.get("board", "DEFAULT")), config)
    if avg_turnover is None:
        reasons.append("MISSING_AVG_TURNOVER_20D")
        return "EXCLUDED", reasons
    if avg_turnover < threshold:
        reasons.append("BELOW_ABSOLUTE_LIQUIDITY_FLOOR")
        return "EXCLUDED", reasons
    active = finite(row.get("active_trade_ratio_60d"))
    susp20 = finite(row.get("suspension_days_20"))
    zero20 = finite(row.get("zero_turnover_days_20"))
    if active is None or active < float(rule["minimum_active_trade_ratio_60d_hard"]):
        reasons.append("ACTIVE_TRADE_RATIO_HARD_FAIL")
        return "EXCLUDED", reasons
    if susp20 is None or susp20 > float(rule["maximum_suspension_days_20_hard"]):
        reasons.append("SUSPENSION_DAYS_HARD_FAIL")
        return "EXCLUDED", reasons
    if zero20 is None or zero20 > float(rule["maximum_zero_turnover_days_20_hard"]):
        reasons.append("ZERO_TURNOVER_DAYS_HARD_FAIL")
        return "EXCLUDED", reasons
    if as_bool(row.get("is_st")):
        reasons.append("ST_REVIEW_ONLY")
        return "REVIEW_ONLY", reasons
    if int(finite(row.get("event_flag_count")) or 0) > int(rule["maximum_event_flags_core"]):
        reasons.append("ELEVATED_EVENT_FLAGS")
        return "REVIEW_ONLY", reasons
    coverage = finite(row.get("history_coverage_ratio_250")) or 0.0
    if coverage < float(rule["minimum_history_coverage_ratio_250_watch"]):
        reasons.append("INSUFFICIENT_HISTORY_COVERAGE")
        return "REVIEW_ONLY", reasons
    core_fail = False
    if confidence not in set(rule["core_confidence_grades"]):
        reasons.append("NON_CORE_CONFIDENCE")
        core_fail = True
    if coverage < float(rule["minimum_history_coverage_ratio_250_core"]):
        reasons.append("WATCH_HISTORY_COVERAGE")
        core_fail = True
    if active < float(rule["minimum_active_trade_ratio_60d_core"]):
        reasons.append("WATCH_ACTIVE_TRADE_RATIO")
        core_fail = True
    if susp20 > float(rule["maximum_suspension_days_20_core"]):
        reasons.append("WATCH_SUSPENSION_DAYS")
        core_fail = True
    if zero20 > float(rule["maximum_zero_turnover_days_20_core"]):
        reasons.append("WATCH_ZERO_TURNOVER_DAYS")
        core_fail = True
    return ("ELIGIBLE_WATCH" if core_fail else "ELIGIBLE_CORE"), reasons


def percentile_column(factor_id: str, config: dict[str, Any]) -> str:
    suffix = (
        "__board_pct"
        if config["percentile_basis"] == "board_neutral_percentile"
        else "__broad_pct"
    )
    return factor_id + suffix


def evaluate_sleeve(
    frame: pd.DataFrame,
    sleeve_id: str,
    sleeve: dict[str, Any],
    config: dict[str, Any],
) -> pd.DataFrame:
    allowed = (
        {"ELIGIBLE_CORE"}
        if sleeve["route"] == "CORE"
        else {"ELIGIBLE_CORE", "ELIGIBLE_WATCH"}
    )
    eligible = frame.loc[frame["investability_status"].isin(allowed)].copy()
    if eligible.empty:
        return pd.DataFrame()
    weights: dict[str, float] = sleeve["weights"]
    if abs(sum(weights.values()) - 1.0) > 1e-9:
        raise RuntimeError(f"SLEEVE_WEIGHT_SUM_{sleeve_id}")
    component_columns: list[str] = []
    for factor_id, weight in weights.items():
        column = percentile_column(factor_id, config)
        if column not in eligible.columns:
            raise RuntimeError(f"MISSING_SCREEN_FACTOR_COLUMN_{sleeve_id}_{column}")
        component = f"component__{factor_id}"
        eligible[component] = pd.to_numeric(eligible[column], errors="coerce") * float(weight)
        component_columns.append(component)
    complete = eligible[component_columns].notna().all(axis=1)
    eligible = eligible.loc[complete].copy()
    if eligible.empty:
        return pd.DataFrame()
    eligible["sleeve_score"] = eligible[component_columns].sum(axis=1)
    for factor_id, minimum in sleeve.get("minimum_percentiles", {}).items():
        column = percentile_column(factor_id, config)
        eligible = eligible.loc[
            pd.to_numeric(eligible[column], errors="coerce") >= float(minimum)
        ].copy()
    maximum_any = sleeve.get("maximum_any_percentiles", {})
    if maximum_any:
        masks = []
        for factor_id, maximum in maximum_any.items():
            column = percentile_column(factor_id, config)
            masks.append(pd.to_numeric(eligible[column], errors="coerce") <= float(maximum))
        eligible = eligible.loc[pd.concat(masks, axis=1).any(axis=1)].copy()
    for factor_id, condition in sleeve.get("raw_conditions", {}).items():
        values = pd.to_numeric(eligible[factor_id], errors="coerce")
        if "minimum" in condition:
            eligible = eligible.loc[values >= float(condition["minimum"])].copy()
            values = pd.to_numeric(eligible[factor_id], errors="coerce")
        if "maximum" in condition:
            eligible = eligible.loc[values <= float(condition["maximum"])].copy()
    eligible = eligible.loc[
        eligible["sleeve_score"] >= float(sleeve["minimum_score"])
    ].copy()
    if eligible.empty:
        return pd.DataFrame()
    eligible = eligible.sort_values(
        ["sleeve_score", "avg_turnover_cny_20d", "symbol"],
        ascending=[False, False, True],
    )
    eligible = eligible.head(int(sleeve["maximum_candidates"])).copy()
    eligible["sleeve_rank"] = range(1, len(eligible) + 1)
    eligible["sleeve_id"] = sleeve_id
    eligible["sleeve_route"] = sleeve["route"]
    eligible["sleeve_description"] = sleeve["description"]
    eligible["component_score_json"] = eligible[component_columns].apply(
        lambda row: json.dumps(
            {
                name.removeprefix("component__"): round(float(value), 8)
                for name, value in row.items()
            },
            sort_keys=True,
        ),
        axis=1,
    )
    keep = [
        "as_of_date",
        "symbol",
        "board",
        "is_st",
        "is_suspended",
        "factor_record_quality",
        "confidence_grade",
        "event_flag_count",
        "history_coverage_ratio_250",
        "investability_status",
        "investability_reason_codes",
        "sleeve_id",
        "sleeve_route",
        "sleeve_rank",
        "sleeve_score",
        "component_score_json",
        "avg_turnover_cny_20d",
        "return_20d",
        "return_60d",
        "return_120d",
        "return_250d",
        "momentum_250_20d",
        "distance_52w_high",
        "volatility_60d",
        "max_drawdown_120d",
        "volume_ratio_20_60d",
    ]
    return eligible[[column for column in keep if column in eligible.columns]]


def build_longlist(
    sleeve_detail: pd.DataFrame,
    screening_universe: pd.DataFrame,
    config: dict[str, Any],
) -> pd.DataFrame:
    if sleeve_detail.empty:
        return pd.DataFrame(columns=["as_of_date", "symbol"])
    metadata = screening_universe.set_index("symbol")
    rows: list[dict[str, Any]] = []
    bonus_per = float(config["funnel"]["cross_sleeve_bonus_per_extra_sleeve"])
    bonus_max = float(config["funnel"]["cross_sleeve_bonus_maximum"])
    for symbol, group in sleeve_detail.groupby("symbol", sort=True):
        ordered = group.sort_values(
            ["sleeve_score", "sleeve_id"], ascending=[False, True]
        )
        best = ordered.iloc[0]
        sleeves = ordered["sleeve_id"].astype(str).tolist()
        sleeve_count = len(sleeves)
        bonus = min(bonus_max, max(0, sleeve_count - 1) * bonus_per)
        meta = metadata.loc[str(symbol)]
        rows.append(
            {
                "as_of_date": str(best["as_of_date"]),
                "symbol": str(symbol),
                "board": str(best["board"]),
                "primary_sleeve": str(best["sleeve_id"]),
                "sleeves": "|".join(sleeves),
                "sleeve_count": sleeve_count,
                "best_sleeve_score": round(float(best["sleeve_score"]), 8),
                "cross_sleeve_bonus": round(bonus, 8),
                "aggregate_score": round(float(best["sleeve_score"]) + bonus, 8),
                "investability_status": str(best["investability_status"]),
                "factor_record_quality": str(best["factor_record_quality"]),
                "confidence_grade": str(best["confidence_grade"]),
                "event_flag_count": int(finite(best["event_flag_count"]) or 0),
                "avg_turnover_cny_20d": finite(best["avg_turnover_cny_20d"]),
                "return_20d": finite(best.get("return_20d")),
                "return_60d": finite(best.get("return_60d")),
                "return_120d": finite(best.get("return_120d")),
                "return_250d": finite(best.get("return_250d")),
                "distance_52w_high": finite(best.get("distance_52w_high")),
                "volatility_60d": finite(best.get("volatility_60d")),
                "max_drawdown_120d": finite(best.get("max_drawdown_120d")),
                "screen_row_hash": str(meta.get("screen_row_hash", "")),
                "next_workflow": config["funnel"]["next_workflow"],
                "authority": config["authority_boundary"],
            }
        )
    longlist = (
        pd.DataFrame(rows)
        .sort_values(
            ["aggregate_score", "best_sleeve_score", "avg_turnover_cny_20d", "symbol"],
            ascending=[False, False, False, True],
        )
        .head(int(config["funnel"]["longlist_maximum"]))
        .reset_index(drop=True)
    )
    longlist["overall_rank"] = range(1, len(longlist) + 1)
    counts = config["funnel"]["priority_bucket_counts"]
    a_end = int(counts["A_IMMEDIATE_RESEARCH"])
    b_end = a_end + int(counts["B_WATCH_OR_TRIGGER"])
    longlist["research_priority"] = longlist["overall_rank"].map(
        lambda rank: (
            "A_IMMEDIATE_RESEARCH"
            if rank <= a_end
            else "B_WATCH_OR_TRIGGER"
            if rank <= b_end
            else "C_SCREEN_FLAG_ONLY"
        )
    )
    ordered = ["as_of_date", "overall_rank", "research_priority"] + [
        column
        for column in longlist.columns
        if column not in {"as_of_date", "overall_rank", "research_priority"}
    ]
    return longlist[ordered]


def add_hash(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    output = frame.copy()
    output[column] = [canonical_hash(row) for row in output.to_dict(orient="records")]
    return output


def build_funnel(
    screen: pd.DataFrame, detail: pd.DataFrame, longlist: pd.DataFrame
) -> pd.DataFrame:
    stages = [
        ("01_UNIVERSE", len(screen)),
        (
            "02_DATA_READY",
            int((~screen["factor_record_quality"].isin(["SUSPECT", "BLOCKED"])).sum()),
        ),
        (
            "03_CORE_INVESTABLE",
            int((screen["investability_status"] == "ELIGIBLE_CORE").sum()),
        ),
        (
            "04_WATCH_ELIGIBLE",
            int((screen["investability_status"] == "ELIGIBLE_WATCH").sum()),
        ),
        ("05_RAW_SLEEVE_HITS", len(detail)),
        (
            "06_DISTINCT_SLEEVE_CANDIDATES",
            int(detail["symbol"].nunique()) if not detail.empty else 0,
        ),
        ("07_RESEARCH_LONGLIST", len(longlist)),
    ]
    initial = max(1, len(screen))
    return pd.DataFrame(
        [
            {
                "stage": stage,
                "count": count,
                "universe_ratio": round(count / initial, 8),
            }
            for stage, count in stages
        ]
    )


def quality_payload(
    screen: pd.DataFrame,
    detail: pd.DataFrame,
    longlist: pd.DataFrame,
    funnel: pd.DataFrame,
    config: dict[str, Any],
    as_of_date: str,
) -> dict[str, Any]:
    failures: list[str] = []
    warnings: list[str] = []
    if screen["symbol"].duplicated().any():
        failures.append("DUPLICATE_SCREEN_SYMBOL")
    if not detail.empty and detail.duplicated(["symbol", "sleeve_id"]).any():
        failures.append("DUPLICATE_SYMBOL_SLEEVE")
    if not longlist.empty and longlist["symbol"].duplicated().any():
        failures.append("DUPLICATE_LONGLIST_SYMBOL")
    unknown = set(longlist.get("symbol", pd.Series(dtype=str)).astype(str)).difference(
        set(screen["symbol"].astype(str))
    )
    if unknown:
        failures.append(f"UNKNOWN_LONGLIST_SYMBOLS_{len(unknown)}")
    if not longlist.empty:
        blocked = longlist["factor_record_quality"].isin(["SUSPECT", "BLOCKED"])
        if blocked.any():
            failures.append(f"BLOCKED_OR_SUSPECT_LONGLIST_{int(blocked.sum())}")
        if (longlist["investability_status"] == "EXCLUDED").any():
            failures.append("EXCLUDED_SYMBOL_IN_LONGLIST")
        if longlist["aggregate_score"].isna().any():
            failures.append("MISSING_LONGLIST_SCORE")
    if len(longlist) > int(config["funnel"]["longlist_maximum"]):
        failures.append("LONGLIST_LIMIT_EXCEEDED")
    sleeve_counts = detail.groupby("sleeve_id").size().to_dict() if not detail.empty else {}
    for sleeve_id, sleeve in config["sleeves"].items():
        count = int(sleeve_counts.get(sleeve_id, 0))
        if count == 0:
            warnings.append(f"EMPTY_SLEEVE_{sleeve_id}")
        if count > int(sleeve["maximum_candidates"]):
            failures.append(f"SLEEVE_LIMIT_EXCEEDED_{sleeve_id}")
    if len(longlist) < min(50, int(config["funnel"]["longlist_maximum"])):
        warnings.append(f"THIN_LONGLIST_{len(longlist)}")
    status = "FAIL" if failures else "PASS_WITH_WARNINGS" if warnings else "PASS"
    return {
        "quality_version": "1.0.0",
        "status": status,
        "as_of_date": as_of_date,
        "hard_failures": failures,
        "controlled_warnings": warnings,
        "metrics": {
            "universe_symbols": int(len(screen)),
            "core_investable": int(
                (screen["investability_status"] == "ELIGIBLE_CORE").sum()
            ),
            "watch_eligible": int(
                (screen["investability_status"] == "ELIGIBLE_WATCH").sum()
            ),
            "review_only": int(
                (screen["investability_status"] == "REVIEW_ONLY").sum()
            ),
            "excluded": int((screen["investability_status"] == "EXCLUDED").sum()),
            "raw_sleeve_hits": int(len(detail)),
            "distinct_sleeve_candidates": (
                int(detail["symbol"].nunique()) if not detail.empty else 0
            ),
            "longlist_symbols": int(len(longlist)),
            "priority_a": (
                int((longlist.get("research_priority") == "A_IMMEDIATE_RESEARCH").sum())
                if not longlist.empty
                else 0
            ),
            "priority_b": (
                int((longlist.get("research_priority") == "B_WATCH_OR_TRIGGER").sum())
                if not longlist.empty
                else 0
            ),
            "priority_c": (
                int((longlist.get("research_priority") == "C_SCREEN_FLAG_ONLY").sum())
                if not longlist.empty
                else 0
            ),
            "sleeve_counts": {str(key): int(value) for key, value in sleeve_counts.items()},
            "funnel_stages": int(len(funnel)),
        },
        "authority": config["authority_boundary"],
        "stability_status": "PENDING_FMDL2D_REPLAY_AND_ECONOMIC_STABILITY",
    }


def write_outputs(
    output_dir: Path,
    screen: pd.DataFrame,
    detail: pd.DataFrame,
    longlist: pd.DataFrame,
    funnel: pd.DataFrame,
    quality: dict[str, Any],
    config: dict[str, Any],
    contracts: dict[str, Any],
    generated_at: str,
) -> dict[str, Any]:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "screening_universe": output_dir / "SCREENING_UNIVERSE.parquet",
        "screening_sleeve_detail": output_dir / "SCREENING_SLEEVE_DETAIL.parquet",
        "screening_longlist": output_dir / "SCREENING_LONGLIST.csv",
        "screening_funnel": output_dir / "SCREENING_FUNNEL.csv",
        "screening_quality": output_dir / "SCREENING_QUALITY.json",
        "run_report": output_dir / "FMDL2C_RUN_REPORT.json",
    }
    screen.to_parquet(paths["screening_universe"], index=False, compression="zstd")
    detail.to_parquet(
        paths["screening_sleeve_detail"], index=False, compression="zstd"
    )
    longlist.to_csv(paths["screening_longlist"], index=False, encoding="utf-8-sig")
    funnel.to_csv(paths["screening_funnel"], index=False, encoding="utf-8-sig")
    paths["screening_quality"].write_text(
        json.dumps(quality, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    run_id = "FMDL2C_" + generated_at.replace("-", "").replace(":", "")
    report = {
        "report_version": "1.0.0",
        "run_id": run_id,
        "generated_at": generated_at,
        "as_of_date": contracts["release"]["as_of_date"],
        "factor_release_id": contracts["release"]["release_id"],
        "screening_contract_version": config["contract_version"],
        "status": quality["status"],
        "metrics": quality["metrics"],
        "hard_failures": quality["hard_failures"],
        "controlled_warnings": quality["controlled_warnings"],
        "non_claims": [
            "NO_FACTOR_ALPHA_CLAIM",
            "NO_LIVE_CANDIDATE_POOL_PROMOTION",
            "NO_PORTFOLIO_CHANGE",
            "NO_TRADE_AUTHORITY",
        ],
        "authority": config["authority_boundary"],
    }
    paths["run_report"].write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    row_counts = {
        "screening_universe": len(screen),
        "screening_sleeve_detail": len(detail),
        "screening_longlist": len(longlist),
        "screening_funnel": len(funnel),
        "screening_quality": 1,
        "run_report": 1,
    }
    artifacts = []
    for dataset_id, path in paths.items():
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
        "run_id": run_id,
        "generated_at": generated_at,
        "as_of_date": report["as_of_date"],
        "factor_release_id": report["factor_release_id"],
        "factor_manifest_sha256": sha256_file(
            ROOT / config["inputs"]["factor_manifest"]
        ),
        "screening_contract_version": config["contract_version"],
        "screening_config_sha256": sha256_file(CONFIG_PATH),
        "artifacts": artifacts,
        "aggregate_sha256": canonical_hash(artifacts),
        "status": (
            "CANDIDATE_GENERATED"
            if not quality["hard_failures"]
            else "CANDIDATE_REJECTED"
        ),
        "authority": config["authority_boundary"],
        "stability_status": "PENDING_FMDL2D",
    }
    manifest_path = output_dir / "SCREENING_MANIFEST.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def run(root: Path = ROOT, output_dir: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    config, contracts, factor_table = load_inputs(root)
    screen = factor_table.copy()
    classified = screen.apply(lambda row: classify_investability(row, config), axis=1)
    screen["investability_status"] = [item[0] for item in classified]
    screen["investability_reason_codes"] = [
        "|".join(item[1]) if item[1] else "NONE" for item in classified
    ]
    screen = add_hash(screen, "screen_row_hash")
    details = []
    for sleeve_id, sleeve in config["sleeves"].items():
        result = evaluate_sleeve(screen, sleeve_id, sleeve, config)
        if not result.empty:
            details.append(result)
    detail = (
        pd.concat(details, ignore_index=True)
        if details
        else pd.DataFrame(columns=["as_of_date", "symbol", "sleeve_id", "sleeve_score"])
    )
    if not detail.empty:
        detail = add_hash(detail, "sleeve_row_hash")
    longlist = build_longlist(detail, screen, config)
    if not longlist.empty:
        longlist = add_hash(longlist, "longlist_row_hash")
    funnel = build_funnel(screen, detail, longlist)
    as_of_date = str(contracts["release"]["as_of_date"])
    quality = quality_payload(screen, detail, longlist, funnel, config, as_of_date)
    generated_at = datetime.now(tz=BUSINESS_TZ).isoformat(timespec="seconds")
    manifest = write_outputs(
        output_dir,
        screen,
        detail,
        longlist,
        funnel,
        quality,
        config,
        contracts,
        generated_at,
    )
    if quality["hard_failures"]:
        raise RuntimeError(";".join(quality["hard_failures"]))
    print(
        json.dumps(
            {
                "status": quality["status"],
                "as_of_date": as_of_date,
                "longlist": len(longlist),
                "manifest": manifest["run_id"],
            },
            ensure_ascii=False,
        )
    )
    return manifest


if __name__ == "__main__":
    run()
