from __future__ import annotations

import csv
import gzip
import json
import sys
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from automation.cross_market.build_round3_limited_production import plan_batches, run, stable_bucket
from automation.cross_market.validate_round3_outputs import validate


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl_gz(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def policy() -> dict:
    return {
        "policy_id": "ROUND3_HK_US_LIMITED_PRODUCTION_V1",
        "hong_kong": {"expected_universe_count": 10, "minimum_weekly_attempted_count": 8, "minimum_weekly_success_ratio": 0.8},
        "united_states": {"expected_security_master_count": 100, "expected_issuer_count": 30, "daily_rotation_batch_size": 4, "daily_sec_batch_size": 2, "minimum_weekly_rotation_attempted_count": 15, "minimum_weekly_rotation_success_ratio": 0.8, "minimum_weekly_benchmark_success_count": 2, "minimum_weekly_sec_queued_count": 8, "minimum_weekly_official_sec_completed_count": 8, "sec_execution_mode": "QUEUE_FOR_CHATGPT_WEB_OFFICIAL_RETRIEVAL"},
        "research": {"allowed_labels": ["RESEARCH_PRIORITY", "WATCH_FOR_ENTRY", "OFFICIAL_FILING_REFRESH_PRIORITY", "MARKET_RISK_SANDBOX_OBSERVATION", "DUPLICATION_REVIEW", "DATA_GAP", "REMOVE_FROM_RESEARCH_REVIEW"], "forbidden_labels": ["BUY_CANDIDATE", "SIMULATION_ENTRY_PROPOSED"], "maximum_hk_weekly_research_proposals": 10, "maximum_us_weekly_research_proposals": 10},
        "acceptance": {"completed_weekly_cycles_for_limited_production_acceptance": 3},
        "authority": {"candidate_pool_mutations": 0, "simulation_mutations": 0, "real_account_mutations": 0, "decision_mutations": 0, "orders": 0, "trade_authority": "NONE"},
    }


def install(root: Path) -> None:
    write_json(root / "automation/cross_market/round3_policy.json", policy())
    hk_path = root / "outputs/fmdl5a/current/FMDL5A_CANONICAL_UNIVERSE.csv"
    hk_path.parent.mkdir(parents=True, exist_ok=True)
    with hk_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["canonical_security_id", "stock_code", "name_cn", "eligibility_status"])
        writer.writeheader()
        hk_codes_by_bucket = {bucket: [] for bucket in range(5)}
        candidate = 1
        while sum(len(values) for values in hk_codes_by_bucket.values()) < 10:
            security_id = f"HKEX:{candidate:05d}"
            bucket = stable_bucket(security_id, 5)
            if len(hk_codes_by_bucket[bucket]) < 2:
                hk_codes_by_bucket[bucket].append(candidate)
            candidate += 1
        hk_codes = [code for bucket in range(5) for code in hk_codes_by_bucket[bucket]]
        for idx, code in enumerate(hk_codes, start=1):
            writer.writerow({"canonical_security_id": f"HKEX:{code:05d}", "stock_code": f"{code:05d}", "name_cn": f"HK{idx}", "eligibility_status": "BUY_AND_SELL_ELIGIBLE"})
    longlist = root / "outputs/fmdl5e/current/FMDL5E_RESEARCH_LONGLIST.csv"
    longlist.parent.mkdir(parents=True, exist_ok=True)
    with longlist.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["canonical_security_id", "overall_rank", "name_cn"])
        writer.writeheader()
        for idx, code in enumerate(hk_codes, start=1):
            writer.writerow({"canonical_security_id": f"HKEX:{code:05d}", "overall_rank": idx, "name_cn": f"HK{idx}"})
    dup = root / "outputs/fmdl5g/integration/current/FMDL5G_CROSS_MARKET_DUPLICATION_REVIEW.csv"
    dup.parent.mkdir(parents=True, exist_ok=True)
    with dup.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["hk_security_id"])
        writer.writeheader()
        writer.writerow({"hk_security_id": f"HKEX:{hk_codes[0]:05d}"})
    benchmark = {"members": [
        {"symbol": "AAPL", "canonical_security_id": "USSEC-AAPL", "pool_layer": "CORE_FINANCIAL_QUALITY_SANDBOX"},
        {"symbol": "QQQ", "canonical_security_id": "USSEC-QQQ", "pool_layer": "BENCHMARK_REFERENCE_INSTRUMENT"},
    ]}
    write_json(root / "outputs/fmdl6x3/current/screening_research_cards/FMDL6X3E_US_BENCHMARK_POOL.json", benchmark)
    initial_market = {"cohort_size": 4, "securities": [{"selected_symbol": f"T{idx:03d}", "canonical_security_id": f"USSEC-{idx:03d}"} for idx in range(4)]}
    write_json(root / "outputs/fmdl6x2/current/market_reference/FMDL6X2D_INITIAL_COHORT.json", initial_market)
    market_rows = [{"symbols": [f"T{idx:03d}"], "venues": ["XNAS"], "canonical_security_id": f"USSEC-{idx:03d}"} for idx in range(4, 100)]
    sec_initial = root / "evidence/fmdl6x2e/2026-07-22/FMDL6X2E_FILINGS.csv"
    sec_initial.parent.mkdir(parents=True, exist_ok=True)
    with sec_initial.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["symbol", "cik10"])
        writer.writeheader()
        for idx in range(2):
            writer.writerow({"symbol": f"T{idx:03d}", "cik10": str(1000000 + idx)})
    identity_rows = [{"canonical_issuer_id": f"USISS-{idx:03d}", "canonical_security_id": f"USSEC-{idx:03d}", "symbol": f"T{idx:03d}", "venue": "XNAS", "row_disposition": "INCLUDED", "listing_lifecycle_status": "ACTIVE_LISTED_OBSERVED", "instrument_type": "COMMON_EQUITY", "test_issue": False, "sec_cik10": None} for idx in range(30)]
    sec_rows = [{"canonical_issuer_id": f"USISS-{idx:03d}", "status": "PENDING"} for idx in range(2, 30)]
    write_jsonl_gz(root / "outputs/fmdl6x2/current/market_reference/FMDL6X2D_BACKFILL_QUEUE.jsonl.gz", market_rows)
    write_jsonl_gz(root / "outputs/fmdl6x2/current/sec_filings_facts/FMDL6X2E_BACKFILL_QUEUE.jsonl.gz", sec_rows)
    write_jsonl_gz(root / "outputs/fmdl6x2/current/identity/FMDL6X2B_IDENTITY_LINEAGE.jsonl.gz", identity_rows)


def fake_fetcher(url: str, headers: dict[str, str] | None = None) -> bytes:
    if "finance/chart" in url:
        period2 = int(parse_qs(urlparse(url).query)["period2"][0])
        as_of = datetime.fromtimestamp(period2, tz=timezone.utc).date() - timedelta(days=2)
        ts = int(datetime.combine(as_of, datetime.min.time(), tzinfo=timezone.utc).timestamp())
        return json.dumps({"chart": {"result": [{"meta": {"currency": "USD"}, "timestamp": [ts], "indicators": {"quote": [{"close": [100.0], "volume": [1000]}]}}], "error": None}}).encode()
    if "submissions" in url:
        return json.dumps({"filings": {"recent": {"form": ["10-Q"], "filingDate": ["2026-08-01"]}}}).encode()
    if "companyfacts" in url:
        return json.dumps({"facts": {"us-gaap": {}}}).encode()
    raise AssertionError(url)


def test_deterministic_partition_and_bounded_us_rotation(tmp_path: Path) -> None:
    install(tmp_path)
    p = policy()
    covered = set()
    for offset in range(5):
        day = date(2026, 8, 3 + offset)
        plan = plan_batches(tmp_path, p, day)
        covered.update(row["canonical_security_id"] for row in plan["hk_selected"])
        assert plan["us_rotation_pool_count"] == 100
        assert len(plan["us_selected"]) <= 4
        assert all(row["symbol"] for row in plan["us_selected"])
        assert plan["us_sec_pool_count"] == 30
        assert all(row["symbol"] for row in plan["us_sec_selected"])
        assert plan["bucket"] == offset
    assert len(covered) == 10
    assert stable_bucket("abc", 5) == stable_bucket("abc", 5)


def test_five_day_cycle_creates_research_only_proposal(tmp_path: Path) -> None:
    install(tmp_path)
    result = None
    for offset in range(5):
        result = run(tmp_path, Path("automation/cross_market/round3_policy.json"), date(2026, 8, 3 + offset), fake_fetcher, sleep_seconds=0)
    assert result is not None
    proposal = json.loads((tmp_path / "investment_os_runtime/30_STATE_CURRENT/46_CROSS_MARKET_OPERATIONS/CROSS_MARKET_RESEARCH_PROPOSAL_CURRENT.json").read_text())
    ledger = json.loads((tmp_path / "investment_os_runtime/30_STATE_CURRENT/46_CROSS_MARKET_OPERATIONS/CROSS_MARKET_LIMITED_LEDGER_CURRENT.json").read_text())
    run_current = json.loads((tmp_path / "investment_os_runtime/30_STATE_CURRENT/46_CROSS_MARKET_OPERATIONS/CROSS_MARKET_LIMITED_RUN_CURRENT.json").read_text())
    assert proposal["market_rotation_completed"] is True
    assert proposal["cycle_completed"] is False
    assert proposal["sec_official_retrieval_status"] == "PENDING_CHATGPT_WEB_OFFICIAL_RETRIEVAL"
    assert proposal["controls"]["candidate_pool_mutations"] == 0
    assert all(row["label"] != "BUY_CANDIDATE" for row in proposal["hong_kong"] + proposal["united_states"])
    assert run_current["operating_state"] == "ROUND3_OPERATING_OBSERVATION"
    assert run_current["united_states"]["sec_queued"] == 2
    assert run_current["united_states"]["sec_official_success_claimed"] is False
    run_id = run_current["run_id"]
    queue_payload = json.loads((tmp_path / f"investment_os_runtime/40_EVIDENCE_AND_LINEAGE/CROSS_MARKET_LIMITED/{run_id}/ROUND3_SEC_OFFICIAL_RETRIEVAL_QUEUE.json").read_text())
    assert all(row["symbol"] for row in queue_payload["queue"])
    assert all(row["official_resolution_route"] in {"CIK_DIRECT", "SYMBOL_TO_SEC_OFFICIAL_TICKER_MAP_TO_CIK"} for row in queue_payload["queue"])
    assert validate(run_current, proposal, ledger, policy())["status"] == "ROUND3_OUTPUTS_VALID"


def test_validator_blocks_scope_and_label_overclaim(tmp_path: Path) -> None:
    install(tmp_path)
    for offset in range(5):
        run(tmp_path, Path("automation/cross_market/round3_policy.json"), date(2026, 8, 3 + offset), fake_fetcher, sleep_seconds=0)
    base = tmp_path / "investment_os_runtime/30_STATE_CURRENT/46_CROSS_MARKET_OPERATIONS"
    proposal = json.loads((base / "CROSS_MARKET_RESEARCH_PROPOSAL_CURRENT.json").read_text())
    ledger = json.loads((base / "CROSS_MARKET_LIMITED_LEDGER_CURRENT.json").read_text())
    run_current = json.loads((base / "CROSS_MARKET_LIMITED_RUN_CURRENT.json").read_text())
    bad = deepcopy(proposal)
    bad["scope_boundaries"]["full_us_market_history_claimed"] = True
    try:
        validate(run_current, bad, ledger, policy())
    except SystemExit as exc:
        assert "US_SCOPE_OVERCLAIM" in str(exc)
    else:
        raise AssertionError("US full-market overclaim must fail")
    bad = deepcopy(proposal)
    bad["united_states"][0]["label"] = "BUY_CANDIDATE"
    try:
        validate(run_current, bad, ledger, policy())
    except SystemExit as exc:
        assert "FORBIDDEN_RESEARCH_LABEL" in str(exc)
    else:
        raise AssertionError("investment label must fail")


def test_stale_observation_does_not_close_market_bucket_or_block_retry(tmp_path: Path) -> None:
    install(tmp_path)

    def stale_fetcher(url: str, headers: dict[str, str] | None = None) -> bytes:
        if "finance/chart" in url:
            ts = int(datetime(2026, 8, 2, tzinfo=timezone.utc).timestamp())
            return json.dumps({"chart": {"result": [{"meta": {"currency": "USD"}, "timestamp": [ts], "indicators": {"quote": [{"close": [100.0], "volume": [1000]}]}}], "error": None}}).encode()
        raise AssertionError(url)

    result = run(tmp_path, Path("automation/cross_market/round3_policy.json"), date(2026, 8, 3), stale_fetcher, sleep_seconds=0)
    ledger = json.loads((tmp_path / "investment_os_runtime/30_STATE_CURRENT/46_CROSS_MARKET_OPERATIONS/CROSS_MARKET_LIMITED_LEDGER_CURRENT.json").read_text())
    cycle = ledger["weekly_cycles"]["2026-W32"]
    assert result["capture_status"] == "PARTIAL_RETRYABLE_MISSING_COMPLETED_SESSION"
    assert cycle["hk_buckets"] == []
    assert cycle["us_buckets"] == []
    assert ledger["daily_runs"] == []


def test_benchmark_only_success_does_not_close_us_rotation_bucket(tmp_path: Path) -> None:
    install(tmp_path)

    def benchmark_only_fetcher(url: str, headers: dict[str, str] | None = None) -> bytes:
        if "finance/chart" not in url:
            raise AssertionError(url)
        period2 = int(parse_qs(urlparse(url).query)["period2"][0])
        as_of = datetime.fromtimestamp(period2, tz=timezone.utc).date() - timedelta(days=2)
        symbol_path = urlparse(url).path
        observed = as_of if (".HK" in symbol_path or "AAPL" in symbol_path or "QQQ" in symbol_path) else as_of - timedelta(days=1)
        ts = int(datetime.combine(observed, datetime.min.time(), tzinfo=timezone.utc).timestamp())
        return json.dumps({"chart": {"result": [{"meta": {"currency": "USD"}, "timestamp": [ts], "indicators": {"quote": [{"close": [100.0], "volume": [1000]}]}}], "error": None}}).encode()

    result = run(tmp_path, Path("automation/cross_market/round3_policy.json"), date(2026, 8, 3), benchmark_only_fetcher, sleep_seconds=0)
    ledger = json.loads((tmp_path / "investment_os_runtime/30_STATE_CURRENT/46_CROSS_MARKET_OPERATIONS/CROSS_MARKET_LIMITED_LEDGER_CURRENT.json").read_text())
    cycle = ledger["weekly_cycles"]["2026-W32"]
    assert result["capture_status"] == "PARTIAL_RETRYABLE_MISSING_COMPLETED_SESSION"
    assert cycle["hk_buckets"] == [0]
    assert cycle["us_buckets"] == []
    assert ledger["daily_runs"] == []


def test_same_date_replay_is_noop(tmp_path: Path) -> None:
    install(tmp_path)
    first = run(tmp_path, Path("automation/cross_market/round3_policy.json"), date(2026, 8, 3), fake_fetcher, sleep_seconds=0)
    ledger_path = tmp_path / "investment_os_runtime/30_STATE_CURRENT/46_CROSS_MARKET_OPERATIONS/CROSS_MARKET_LIMITED_LEDGER_CURRENT.json"
    before = ledger_path.read_bytes()
    second = run(tmp_path, Path("automation/cross_market/round3_policy.json"), date(2026, 8, 3), fake_fetcher, sleep_seconds=0)
    assert first["due"] is True
    assert second["due"] is False
    assert second["status"] == "NOOP_ALREADY_CAPTURED"
    assert ledger_path.read_bytes() == before
