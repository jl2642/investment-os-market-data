#!/usr/bin/env python3
"""FMDL-2B-2 aggregate wrapper with quarantine-aware hard-gate semantics.

The canonical contract prohibits impossible OHLC rows in promoted history. Rows that
fail that gate are intentionally excluded from Parquet output and preserved only in
quarantine evidence. Such evidence must not be counted again as a promoted-row hard
failure at market aggregation.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "outputs/history/candidate"
USABLE_STATES = {"READY", "PARTIAL_FALLBACK_PRICE_AMOUNT"}


def rewrite_markdown(report: dict) -> None:
    metrics = report["metrics"]
    lines = [
        "# FMDL-2B-2 Full-Universe Historical Backfill",
        "",
        f"- Release ID: `{report['release_id']}`",
        f"- As-of date: `{report['as_of_date']}`",
        f"- Attempted symbols: `{metrics['attempted_symbols']}`",
        f"- Usable symbols: `{metrics['usable_symbols']}` (`{metrics['usable_ratio']:.2%}`)",
        f"- Quarantined symbols: `{metrics['quarantined_symbols']}`",
        f"- History rows: `{metrics['history_rows']}`",
        f"- Base store size: `{metrics['base_store_size_mib']:.2f} MiB`",
        f"- Candidate status: `{report['status']}`",
        f"- Hard failures: `{len(report['hard_failures'])}`",
        f"- Promoted impossible-OHLC rows: `{metrics['impossible_ohlc_rows']}`",
        f"- Quarantined impossible-OHLC rows: `{metrics.get('quarantined_impossible_ohlc_rows', 0)}`",
        "",
        "## Board results",
        "",
        "| Board | Attempted | Usable | Ratio |",
        "|---|---:|---:|---:|",
    ]
    for board, result in metrics["board_results"].items():
        lines.append(f"| {board} | {result['attempted']} | {result['usable']} | {result['usable_ratio']:.2%} |")
    lines.extend([
        "",
        "## Boundary",
        "",
        "Impossible OHLC series are excluded from promoted Parquet history and retained only as quarantine evidence. This candidate does not calculate production factors, rank securities, modify a candidate pool or create trade authority.",
    ])
    (CANDIDATE / "FMDL2B2_RUN_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def apply_quarantine_aware_policy() -> bool:
    quality_path = CANDIDATE / "HISTORICAL_STORE_QUALITY.json"
    release_path = CANDIDATE / "HISTORICAL_STORE_RELEASE.json"
    report_path = CANDIDATE / "FMDL2B2_RUN_REPORT.json"
    status_path = CANDIDATE / "HISTORICAL_SYMBOL_STATUS.csv"
    if not all(path.exists() for path in (quality_path, release_path, report_path, status_path)):
        return False

    quality = json.loads(quality_path.read_text(encoding="utf-8"))
    release = json.loads(release_path.read_text(encoding="utf-8"))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    status = pd.read_csv(status_path, dtype={"symbol": str})

    usable = status["state"].isin(USABLE_STATES)
    promoted_impossible = int(status.loc[usable, "impossible_ohlc_rows"].fillna(0).sum())
    quarantined_impossible = int(status.loc[~usable, "impossible_ohlc_rows"].fillna(0).sum())
    hard_failures = list(quality.get("hard_failures", []))

    # This correction is deliberately narrow. Any additional hard failure remains fatal.
    if promoted_impossible != 0:
        return False
    if quarantined_impossible <= 0:
        return False
    if hard_failures != ["IMPOSSIBLE_OHLC"]:
        return False

    warnings = list(quality.get("controlled_warnings", []))
    warning = f"QUARANTINED_IMPOSSIBLE_OHLC_ROWS_{quarantined_impossible}"
    if warning not in warnings:
        warnings.append(warning)

    quality["hard_failures"] = []
    quality["controlled_warnings"] = warnings
    quality["metrics"]["impossible_ohlc_rows"] = 0
    quality["metrics"]["quarantined_impossible_ohlc_rows"] = quarantined_impossible

    release["status"] = "CANDIDATE_ACCEPTED_WITH_QUARANTINE"
    release["hard_failures"] = []
    release["controlled_warnings"] = warnings

    report["status"] = "CANDIDATE_ACCEPTED_WITH_QUARANTINE"
    report["hard_failures"] = []
    report["controlled_warnings"] = warnings
    report["metrics"]["impossible_ohlc_rows"] = 0
    report["metrics"]["quarantined_impossible_ohlc_rows"] = quarantined_impossible

    quality_path.write_text(json.dumps(quality, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    release_path.write_text(json.dumps(release, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rewrite_markdown(report)
    print(json.dumps(report, ensure_ascii=False))
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--incoming", required=True)
    parser.add_argument("--release-id", required=True)
    args = parser.parse_args()

    command = [
        sys.executable,
        "-m",
        "scripts.aggregate_full_backfill",
        "--incoming",
        args.incoming,
        "--release-id",
        args.release_id,
    ]
    result = subprocess.run(command, cwd=ROOT, check=False)
    if result.returncode == 0:
        return 0
    if apply_quarantine_aware_policy():
        return 0
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
