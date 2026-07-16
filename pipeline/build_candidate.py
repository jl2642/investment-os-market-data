#!/usr/bin/env python3
"""Build real FMDL-1B/C A-share candidate datasets from free AKShare sources."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ingestion.akshare import fetch_a_share_bundle  # noqa: E402
from pipeline.common import file_sha256, iso_shanghai, latest_completed_trade_date, now_shanghai, write_json  # noqa: E402
from pipeline.normalize import normalize_a_share_bundle  # noqa: E402
from pipeline.quality import DatasetQuality, evaluate_snapshot, evaluate_universe  # noqa: E402


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig", lineterminator="\n")


def _source_entry(call: Any, adapter_version: str, retrieved_at: str, raw_hash: str | None = None) -> dict[str, Any]:
    provider_id = "eastmoney" if "spot_em" in call.function else "exchange_or_sina_public_source"
    return {
        "adapter_id": "akshare",
        "adapter_version": adapter_version,
        "adapter_function": call.function,
        "provider_id": provider_id,
        "retrieved_at": retrieved_at,
        "source_as_of_date": None,
        "raw_hash_sha256": raw_hash,
        "retries": call.retries,
        "warnings": call.warnings,
    }


def _quality_payload(quality: DatasetQuality) -> dict[str, Any]:
    return {
        "dataset_id": quality.dataset_id,
        "qa_status": quality.qa_status,
        "publication_status": quality.publication_status,
        "hard_failures": quality.hard_failures,
        "soft_warnings": quality.soft_warnings,
        "metrics": quality.metrics,
        "gate_results": quality.gate_results,
    }


def _manifest(
    *,
    dataset_id: str,
    schema_id: str,
    run_id: str,
    as_of_date: str,
    generated_at: str,
    path: Path,
    frame: pd.DataFrame,
    quality: DatasetQuality,
    sources: list[dict[str, Any]],
    limitations: list[str],
) -> dict[str, Any]:
    return {
        "manifest_version": "1.0.0",
        "dataset_id": dataset_id,
        "dataset_version": f"{dataset_id}-{as_of_date}-{run_id}",
        "schema_id": schema_id,
        "schema_version": "1.0.0",
        "run_id": run_id,
        "as_of_date": as_of_date,
        "generated_at": generated_at,
        "business_timezone": "Asia/Shanghai",
        "publication_status": quality.publication_status,
        "qa_status": quality.qa_status,
        "sources": sources,
        "row_count": len(frame),
        "column_count": len(frame.columns),
        "file": {
            "path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "size_bytes": path.stat().st_size,
            "sha256": file_sha256(path),
        },
        "quality": {
            "hard_failures": quality.hard_failures,
            "soft_warnings": quality.soft_warnings,
            "gate_results_path": f"outputs/candidate/{dataset_id.upper()}_QUALITY.json",
        },
        "lineage": {
            "parent_dataset_version": None,
            "last_known_good_dataset_version": None,
        },
        "known_limitations": limitations,
        "notes": "FMDL-1B/C candidate output. Not yet promoted to outputs/current.",
    }


def _write_summary(
    path: Path,
    *,
    run_id: str,
    as_of_date: str,
    generated_at: str,
    universe_quality: DatasetQuality,
    snapshot_quality: DatasetQuality,
    warnings: list[str],
) -> None:
    lines = [
        "# FMDL-1B/C Candidate Data Report",
        "",
        f"- Run ID: `{run_id}`",
        f"- As-of date: `{as_of_date}`",
        f"- Generated at: `{generated_at}`",
        f"- Universe QA: `{universe_quality.qa_status}` / `{universe_quality.publication_status}`",
        f"- Snapshot QA: `{snapshot_quality.qa_status}` / `{snapshot_quality.publication_status}`",
        "- Promotion state: `CANDIDATE_ONLY`",
        "",
        "## Universe metrics",
        "",
    ]
    for key, value in universe_quality.metrics.items():
        if key != "schema_error_examples":
            lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Snapshot metrics", ""])
    for key, value in snapshot_quality.metrics.items():
        if key != "schema_error_examples":
            lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Source warnings", ""])
    lines.extend(f"- {warning}" for warning in warnings) if warnings else lines.append("- None")
    lines.extend([
        "",
        "## Boundary",
        "",
        "These files prove real A-share universe and market-snapshot ingestion. They are not yet stable Investment OS current outputs; FMDL-1D/E/F own hardening, scheduled publication and downstream promotion.",
        "",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(ROOT))
    args = parser.parse_args()
    root = Path(args.root).resolve()
    if root != ROOT:
        raise ValueError("This MVP expects execution from the repository root")

    generated_dt = now_shanghai()
    generated_at = iso_shanghai(generated_dt)
    run_id = generated_dt.strftime("FMDL1BC_%Y%m%dT%H%M%S%z")
    bundle = fetch_a_share_bundle()
    as_of = latest_completed_trade_date(bundle.trade_calendar.data, generated_dt)
    normalized = normalize_a_share_bundle(bundle, as_of_date=as_of, source_timestamp=generated_at)

    candidate_dir = root / "outputs/candidate"
    raw_dir = root / "datasets/raw" / as_of.isoformat() / run_id
    raw_spot_path = raw_dir / "AKSHARE_STOCK_ZH_A_SPOT_EM.csv"
    universe_path = candidate_dir / "A_SHARE_UNIVERSE.csv"
    snapshot_path = candidate_dir / "DAILY_MARKET_SNAPSHOT.csv"
    _write_csv(bundle.spot.data, raw_spot_path)
    _write_csv(normalized.universe, universe_path)
    _write_csv(normalized.snapshot, snapshot_path)

    lkg_path = root / "outputs/current/A_SHARE_UNIVERSE.csv"
    lkg_frame = pd.read_csv(lkg_path, dtype={"source_symbol": str}) if lkg_path.exists() else None
    universe_quality = evaluate_universe(normalized.universe, root=root, lkg_frame=lkg_frame)
    snapshot_quality = evaluate_snapshot(normalized.snapshot, universe=normalized.universe, root=root)
    write_json(candidate_dir / "A_SHARE_UNIVERSE_QUALITY.json", _quality_payload(universe_quality))
    write_json(candidate_dir / "DAILY_MARKET_SNAPSHOT_QUALITY.json", _quality_payload(snapshot_quality))

    raw_hash = file_sha256(raw_spot_path)
    universe_sources = [
        _source_entry(bundle.spot, bundle.adapter_version, generated_at, raw_hash),
        _source_entry(bundle.sh_main, bundle.adapter_version, generated_at),
        _source_entry(bundle.sh_star, bundle.adapter_version, generated_at),
        _source_entry(bundle.sz_a, bundle.adapter_version, generated_at),
        _source_entry(bundle.bj_a, bundle.adapter_version, generated_at),
        _source_entry(bundle.trade_calendar, bundle.adapter_version, generated_at),
    ]
    universe_manifest = _manifest(
        dataset_id="a_share_universe",
        schema_id="a_share_universe.schema.json",
        run_id=run_id,
        as_of_date=as_of.isoformat(),
        generated_at=generated_at,
        path=universe_path,
        frame=normalized.universe,
        quality=universe_quality,
        sources=universe_sources,
        limitations=[
            "Industry and listing-date enrichment depends on optional free exchange endpoints.",
            "Suspension status is inferred from the market-wide spot response.",
            "FMDL-2, not this data layer, owns investability exclusions.",
        ],
    )
    snapshot_manifest = _manifest(
        dataset_id="daily_market_snapshot",
        schema_id="daily_market_snapshot.schema.json",
        run_id=run_id,
        as_of_date=as_of.isoformat(),
        generated_at=generated_at,
        path=snapshot_path,
        frame=normalized.snapshot,
        quality=snapshot_quality,
        sources=[_source_entry(bundle.spot, bundle.adapter_version, generated_at, raw_hash)],
        limitations=[
            "AKShare/Eastmoney 成交量 is converted from lots to shares using 100 shares per lot.",
            "pe_ttm temporarily maps the free-source dynamic PE field; valuation semantics are hardened in FMDL-3.",
            "Candidate data is not a stable Investment OS current output until FMDL-1F promotion.",
        ],
    )
    write_json(candidate_dir / "A_SHARE_UNIVERSE_MANIFEST.json", universe_manifest)
    write_json(candidate_dir / "DAILY_MARKET_SNAPSHOT_MANIFEST.json", snapshot_manifest)

    combined = {
        "run_id": run_id,
        "as_of_date": as_of.isoformat(),
        "generated_at": generated_at,
        "adapter_version": bundle.adapter_version,
        "universe": _quality_payload(universe_quality),
        "snapshot": _quality_payload(snapshot_quality),
        "source_warnings": normalized.warnings,
        "candidate_files": [
            str(universe_path.relative_to(root)),
            str(snapshot_path.relative_to(root)),
        ],
    }
    write_json(candidate_dir / "FMDL_1BC_RUN_REPORT.json", combined)
    _write_summary(
        candidate_dir / "FMDL_1BC_RUN_REPORT.md",
        run_id=run_id,
        as_of_date=as_of.isoformat(),
        generated_at=generated_at,
        universe_quality=universe_quality,
        snapshot_quality=snapshot_quality,
        warnings=normalized.warnings,
    )

    if universe_quality.hard_failures or snapshot_quality.hard_failures:
        print(json.dumps(combined, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps({
        "run_id": run_id,
        "as_of_date": as_of.isoformat(),
        "universe_rows": len(normalized.universe),
        "snapshot_rows": len(normalized.snapshot),
        "universe_qa": universe_quality.qa_status,
        "snapshot_qa": snapshot_quality.qa_status,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
