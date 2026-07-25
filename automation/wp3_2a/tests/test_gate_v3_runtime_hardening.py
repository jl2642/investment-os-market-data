from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
GATE = ROOT / "automation/wp3_2a/validate_a_share_universe_gate_v3.py"


def write_current(path: Path) -> None:
    rows = [
        {
            "security_code": "600000",
            "security_name": "浦发银行",
            "exchange": "SSE",
        },
        {
            "security_code": "000001",
            "security_name": "平安银行",
            "exchange": "SZSE",
        },
        {
            "security_code": "920001",
            "security_name": "北交样本",
            "exchange": "BSE",
        },
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "security_code",
                "security_name",
                "exchange",
                "last_price",
                "volume",
                "source_provider",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    **row,
                    "last_price": "10.0",
                    "volume": "100",
                    "source_provider": "fixture",
                }
            )


def gate_command(previous: Path, current: Path, output: Path) -> list[str]:
    return [
        sys.executable,
        str(GATE),
        "--previous-jsonl",
        str(previous),
        "--current-csv",
        str(current),
        "--as-of",
        "2026-07-24",
        "--latest-completed-session",
        "2026-07-24",
        "--expected-provider",
        "fixture",
        "--expected-min",
        "3",
        "--expected-max",
        "3",
        "--output",
        str(output),
    ]


def test_gate_accepts_suffixless_historical_symbol(tmp_path: Path) -> None:
    previous = tmp_path / "old.jsonl"
    historical = [
        {
            "symbol": "600000",
            "name": "浦发银行",
            "market_evidence": {"exchange": "SH"},
        },
        {
            "symbol": "000001",
            "name": "平安银行",
            "market_evidence": {"exchange": "SZ"},
        },
        {
            "symbol": "920001",
            "name": "北交样本",
            "market_evidence": {"exchange": "BJ"},
        },
    ]
    previous.write_text(
        "".join(
            json.dumps(item, ensure_ascii=False) + "\n" for item in historical
        ),
        encoding="utf-8",
    )
    current = tmp_path / "current.csv"
    write_current(current)
    output = tmp_path / "gate.json"

    run = subprocess.run(
        gate_command(previous, current, output),
        text=True,
        capture_output=True,
    )

    assert run.returncode == 0, run.stdout + run.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["status"] == "PASS"
    assert report["previous"]["records"] == 3
    assert report["current"]["exchanges"] == ["BSE", "SSE", "SZSE"]
    assert report["trade_authority"] == "NONE"


def test_gate_writes_structured_report_on_runtime_exception(tmp_path: Path) -> None:
    previous = tmp_path / "old.jsonl"
    previous.write_text("not-json\n", encoding="utf-8")
    current = tmp_path / "current.csv"
    write_current(current)
    output = tmp_path / "gate.json"

    run = subprocess.run(
        gate_command(previous, current, output),
        text=True,
        capture_output=True,
    )

    assert run.returncode == 2
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["status"] == "FAIL"
    assert report["errors"] == ["GATE_RUNTIME_EXCEPTION"]
    assert report["runtime_exception"]["type"] == "JSONDecodeError"
    assert report["permissions"]["governed_screening"] is False
    assert report["trade_authority"] == "NONE"
