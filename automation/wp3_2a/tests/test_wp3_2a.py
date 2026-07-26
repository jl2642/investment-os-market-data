from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
AUTO = ROOT / "automation/wp3_2a"


def test_config_authority():
    config = json.loads((AUTO / "config.json").read_text(encoding="utf-8"))
    assert config["trade_authority"] == "NONE"
    assert not any(config["permissions"].values())


def test_workflows_parse_and_count():
    import yaml

    files = sorted(
        set((ROOT / ".github/workflows").glob("wp3_2a_*.yml"))
        | set((ROOT / ".github/workflows").glob("wp3_2b_*.yml"))
    )
    assert len(files) >= 5
    for path in files:
        data = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
        assert "jobs" in data


def test_required_lineage_check_has_no_path_filter():
    text = (
        ROOT / ".github/workflows/wp3_2a_lineage_gate.yml"
    ).read_text(encoding="utf-8")
    assert "paths:" not in text
    assert "paths-ignore:" not in text
    assert "name: WP3-2A / Lineage Gate" in text
    assert "automation/wp3-2a-*" in text
    assert "automation/wp3-2b-*" in text


def test_generated_cache_patterns_are_ignored():
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".pytest_cache/" in ignore
    assert "__pycache__/" in ignore
    assert "*.pyc" in ignore or "*.py[codz]" in ignore


def test_gate_v3_fixture(tmp_path):
    out = tmp_path / "gate.json"
    run = subprocess.run(
        [
            sys.executable,
            str(AUTO / "validate_a_share_universe_gate_v3.py"),
            "--previous-jsonl",
            str(AUTO / "fixtures/old_identity.jsonl"),
            "--current-csv",
            str(AUTO / "fixtures/current.csv"),
            "--as-of",
            "2026-07-23",
            "--latest-completed-session",
            "2026-07-23",
            "--expected-provider",
            "fixture",
            "--expected-min",
            "3",
            "--expected-max",
            "3",
            "--output",
            str(out),
        ],
        text=True,
        capture_output=True,
    )
    assert run.returncode == 0, run.stdout + run.stderr
    assert json.loads(out.read_text())["status"] == "PASS"


def test_screening_never_mutates_candidate(tmp_path):
    repo = tmp_path / "repo"
    current = (
        repo
        / "investment_os_runtime/40_EVIDENCE_AND_LINEAGE/WP3_2A/CURRENT"
    )
    current.mkdir(parents=True)

    config = json.loads((AUTO / "config.json").read_text())
    config["current_root"] = str(current.relative_to(repo))
    config["screening_root"] = (
        "investment_os_runtime/40_EVIDENCE_AND_LINEAGE/"
        "WP3_2A/SCREENING_PROPOSALS"
    )
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps(config))

    (current / "PROPOSAL_MANIFEST.json").write_text(
        json.dumps({"session": "2026-07-23"})
    )
    (current / "LINEAGE_ACCEPTANCE.json").write_text(
        json.dumps({"status": "PASS"})
    )

    binding = (
        repo
        / "investment_os_runtime/50_MARKET_CAPABILITY_BINDINGS/"
        "A_SHARE_CURRENT.json"
    )
    binding.parent.mkdir(parents=True, exist_ok=True)
    binding.write_text(
        json.dumps(
            {
                "as_of_date": "2026-07-23",
                "status": "ACCEPTED_ON_MAIN",
                "accepted_merge_sha": "fixture-main-merge",
                "datasets": {"universe": {"rows": 1}},
                "trade_authority": "NONE",
            }
        )
    )

    with (current / "A_SHARE_FULL_UNIVERSE.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "security_code",
                "security_name",
                "exchange",
                "last_price",
                "volume",
                "turnover_amount",
                "total_market_cap",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "security_code": "600000",
                "security_name": "浦发银行",
                "exchange": "SSE",
                "last_price": 10,
                "volume": 100,
                "turnover_amount": 1000,
                "total_market_cap": 100000,
            }
        )

    run = subprocess.run(
        [
            sys.executable,
            str(AUTO / "governed_screening.py"),
            "--repo-root",
            str(repo),
            "--config",
            str(cfg),
            "--max-proposals",
            "10",
            "--confirmation",
            "RUN_PROPOSAL_ONLY_SCREENING",
            "--run-id",
            "TEST",
        ],
        text=True,
        capture_output=True,
    )
    assert run.returncode == 0, run.stdout + run.stderr

    manifest = list(
        (repo / config["screening_root"]).glob(
            "*/SCREENING_PROPOSAL_MANIFEST.json"
        )
    )[0]
    result = json.loads(manifest.read_text())
    assert result["work_package"] == "WP3-2B"
    assert result["eligible_universe_rows"] == 1
    assert result["workload_queue_rows"] == 1
    assert result["candidate_membership_mutations"] == 0
    assert result["orders"] == 0
    assert result["investment_ranking"] is False
