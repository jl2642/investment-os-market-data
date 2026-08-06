#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def replace_between(text: str, start_marker: str, end_marker: str, replacement: str) -> str:
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[:start] + replacement.rstrip() + "\n\n" + text[end + 2:]


def patch_engine() -> None:
    path = ROOT / "automation/cross_market/build_round3_limited_production.py"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        'US_MARKET_QUEUE = Path("outputs/fmdl6x2/current/market_reference/FMDL6X2D_BACKFILL_QUEUE.jsonl.gz")\nUS_SEC_QUEUE = Path("outputs/fmdl6x2/current/sec_filings_facts/FMDL6X2E_BACKFILL_QUEUE.jsonl.gz")',
        'US_MARKET_INITIAL = Path("outputs/fmdl6x2/current/market_reference/FMDL6X2D_INITIAL_COHORT.json")\nUS_MARKET_QUEUE = Path("outputs/fmdl6x2/current/market_reference/FMDL6X2D_BACKFILL_QUEUE.jsonl.gz")\nUS_SEC_INITIAL = Path("evidence/fmdl6x2e/2026-07-22/FMDL6X2E_FILINGS.csv")\nUS_SEC_QUEUE = Path("outputs/fmdl6x2/current/sec_filings_facts/FMDL6X2E_BACKFILL_QUEUE.jsonl.gz")',
    )
    text = text.replace(
        '("cik", "cik_str", "issuer_cik", "sec_cik", "CIK")',
        '("cik", "cik10", "cik_str", "issuer_cik", "sec_cik", "CIK")',
    )
    text = text.replace(
        '("symbol", "ticker", "primary_symbol", "listing_symbol", "security_symbol")',
        '("symbol", "ticker", "selected_symbol", "primary_symbol", "primary_ticker", "listing_symbol", "security_symbol")',
    )
    plan = '''def plan_batches(root: Path, policy: dict[str, Any], as_of: date) -> dict[str, Any]:
    bucket = as_of.weekday()
    if bucket not in range(5):
        raise ValueError("Round 3 runs only for Monday-Friday market dates")
    hk_rows = read_csv(root / HK_UNIVERSE)
    hk_selected = [row for row in hk_rows if stable_bucket(first_value(row, ("canonical_security_id", "stock_code")), 5) == bucket]

    initial_payload = read_json(root / US_MARKET_INITIAL)
    initial_market_rows = initial_payload.get("securities", []) if isinstance(initial_payload, dict) else initial_payload
    market_sources = list(initial_market_rows) + read_jsonl_gz(root / US_MARKET_QUEUE)
    market_pool: dict[str, dict[str, Any]] = {}
    for row in market_sources:
        symbol = sec_symbol(row)
        security_id = first_value(row, ("canonical_security_id", "security_id", "security_key")) or symbol
        if symbol and security_id:
            market_pool[security_id] = {**row, "symbol": symbol, "_security_key": security_id}
    normalized_us = list(market_pool.values())
    bucket_rows = sorted((row for row in normalized_us if stable_bucket(row["_security_key"], 5) == bucket), key=lambda row: row["_security_key"])
    iso_year, iso_week, _ = as_of.isocalendar()
    week_index = iso_year * 53 + iso_week
    us_size = int(policy["united_states"]["daily_rotation_batch_size"])
    us_selected = circular_slice(bucket_rows, us_size, week_index * us_size)

    sec_sources = read_csv(root / US_SEC_INITIAL) + read_jsonl_gz(root / US_SEC_QUEUE)
    sec_pool: dict[str, dict[str, Any]] = {}
    for row in sec_sources:
        symbol = sec_symbol(row)
        cik = sec_cik(row)
        key = first_value(row, ("canonical_issuer_id", "issuer_id")) or cik or symbol
        if key and (symbol or cik):
            sec_pool[key] = {**row, "symbol": symbol, "cik": cik, "_issuer_key": key}
    normalized_sec = list(sec_pool.values())
    sec_bucket = sorted((row for row in normalized_sec if stable_bucket(row["_issuer_key"], 5) == bucket), key=lambda row: row["_issuer_key"])
    sec_size = int(policy["united_states"]["daily_sec_batch_size"])
    sec_selected = circular_slice(sec_bucket, sec_size, week_index * sec_size)

    benchmark_payload = read_json(root / US_BENCHMARK)
    benchmark = benchmark_payload.get("members", [])
    return {
        "bucket": bucket,
        "hk_universe_count": len(hk_rows),
        "hk_selected": hk_selected,
        "us_rotation_pool_count": len(normalized_us),
        "us_selected": us_selected,
        "us_sec_pool_count": len(normalized_sec),
        "us_sec_selected": sec_selected,
        "us_benchmark": benchmark,
    }


def build_sec_retrieval_queue(rows: list[dict[str, Any]], as_of: date) -> list[dict[str, Any]]:
    queue: list[dict[str, Any]] = []
    for row in rows:
        symbol = sec_symbol(row)
        cik = sec_cik(row)
        issuer_id = first_value(row, ("canonical_issuer_id", "issuer_id"))
        queue.append({
            "symbol": symbol,
            "cik": cik,
            "canonical_issuer_id": issuer_id,
            "as_of_date": as_of.isoformat(),
            "status": "PENDING_CHATGPT_WEB_OFFICIAL_RETRIEVAL",
            "required_sources": ["SEC_SUBMISSIONS", "SEC_COMPANYFACTS"],
            "data_grade_required": "OFFICIAL_SEC_RESEARCH_EVIDENCE",
            "candidate_pool_mutation_authorized": False,
            "trade_authority": "NONE",
        })
    queue.sort(key=lambda row: (row["symbol"], row["cik"], row["canonical_issuer_id"]))
    return queue'''
    text = replace_between(text, "def plan_batches(", "def execute_market_rows(", plan)

    cycle = '''def update_cycle(ledger: dict[str, Any], as_of: date, bucket: int, hk_ok: list[dict[str, Any]], hk_fail: list[dict[str, Any]], us_ok: list[dict[str, Any]], us_fail: list[dict[str, Any]], sec_rows: list[dict[str, Any]], benchmark_symbols: list[str], policy: dict[str, Any]) -> dict[str, Any]:
    iso_year, iso_week, _ = as_of.isocalendar()
    cycle_id = f"{iso_year}-W{iso_week:02d}"
    cycle = ledger.setdefault("weekly_cycles", {}).setdefault(cycle_id, {
        "cycle_id": cycle_id,
        "hk_buckets": [],
        "us_buckets": [],
        "hk_attempted": 0,
        "hk_success": 0,
        "us_rotation_attempted": 0,
        "us_rotation_success": 0,
        "us_benchmark_success_symbols": [],
        "sec_queued": 0,
        "sec_official_completed_issuer_count": 0,
        "sec_official_retrieval_status": "PENDING_CHATGPT_WEB_OFFICIAL_RETRIEVAL",
        "observations": {"HK": {}, "US": {}, "SEC": {}},
        "market_rotation_completed": False,
        "completed": False,
    })
    if bucket not in cycle["hk_buckets"]:
        cycle["hk_buckets"].append(bucket)
        cycle["hk_attempted"] += len(hk_ok) + len(hk_fail)
        cycle["hk_success"] += len(hk_ok)
    new_us_bucket = bucket not in cycle["us_buckets"]
    if new_us_bucket:
        cycle["us_buckets"].append(bucket)
        rotation = [row for row in us_ok if row["symbol"] not in benchmark_symbols]
        rotation_fail = [row for row in us_fail if row["symbol"] not in benchmark_symbols]
        cycle["us_rotation_attempted"] += len(rotation) + len(rotation_fail)
        cycle["us_rotation_success"] += len(rotation)
        cycle["sec_queued"] += len(sec_rows)
    for row in hk_ok:
        cycle["observations"]["HK"][row["symbol"]] = row
    for row in us_ok:
        cycle["observations"]["US"][row["symbol"]] = row
        if row["symbol"] in benchmark_symbols and row["symbol"] not in cycle["us_benchmark_success_symbols"]:
            cycle["us_benchmark_success_symbols"].append(row["symbol"])
    for row in sec_rows:
        cycle["observations"]["SEC"][row.get("symbol") or row.get("cik") or row.get("canonical_issuer_id") or "UNKNOWN"] = row
    hk_ratio = cycle["hk_success"] / cycle["hk_attempted"] if cycle["hk_attempted"] else 0.0
    cycle["hk_success_ratio"] = round(hk_ratio, 6)
    cycle["market_rotation_completed"] = (
        sorted(cycle["hk_buckets"]) == [0, 1, 2, 3, 4]
        and sorted(cycle["us_buckets"]) == [0, 1, 2, 3, 4]
        and cycle["hk_attempted"] >= int(policy["hong_kong"]["minimum_weekly_attempted_count"])
        and hk_ratio >= float(policy["hong_kong"]["minimum_weekly_success_ratio"])
        and cycle["us_rotation_attempted"] >= int(policy["united_states"]["minimum_weekly_rotation_attempted_count"])
        and len(cycle["us_benchmark_success_symbols"]) >= int(policy["united_states"]["minimum_weekly_benchmark_success_count"])
        and cycle["sec_queued"] >= int(policy["united_states"]["minimum_weekly_sec_queued_count"])
    )
    cycle["completed"] = (
        cycle["market_rotation_completed"]
        and cycle.get("sec_official_completed_issuer_count", 0) >= int(policy["united_states"]["minimum_weekly_official_sec_completed_count"])
    )
    ledger["completed_weekly_cycle_count"] = sum(bool(item.get("completed")) for item in ledger["weekly_cycles"].values())
    ledger["market_rotation_completed_weekly_cycle_count"] = sum(bool(item.get("market_rotation_completed")) for item in ledger["weekly_cycles"].values())
    return cycle'''
    text = replace_between(text, "def update_cycle(", "def parse_rank(", cycle)

    text = text.replace(
        '        "cycle_completed": bool(cycle["completed"]),\n        "status": "WEEKLY_RESEARCH_REVIEW_READY" if cycle["completed"] else "DAILY_BATCH_CAPTURED_NO_WEEKLY_PROPOSAL_YET",\n        "hong_kong": hk_rows if cycle["completed"] else [],\n        "united_states": us_rows if cycle["completed"] else [],',
        '        "cycle_completed": bool(cycle["completed"]),\n        "market_rotation_completed": bool(cycle["market_rotation_completed"]),\n        "sec_official_retrieval_status": cycle.get("sec_official_retrieval_status", "PENDING_CHATGPT_WEB_OFFICIAL_RETRIEVAL"),\n        "status": (\n            "WEEKLY_RESEARCH_REVIEW_READY" if cycle["completed"]\n            else "WEEKLY_RESEARCH_REVIEW_READY_SEC_ENRICHMENT_PENDING" if cycle["market_rotation_completed"]\n            else "DAILY_BATCH_CAPTURED_NO_WEEKLY_PROPOSAL_YET"\n        ),\n        "hong_kong": hk_rows if cycle["market_rotation_completed"] else [],\n        "united_states": us_rows if cycle["market_rotation_completed"] else [],',
    )

    run = '''def run(root: Path, policy_path: Path, as_of: date, fetcher: Fetcher = default_fetcher, sleep_seconds: float = 0.05) -> dict[str, Any]:
    policy = read_json(root / policy_path)
    ledger = load_ledger(root / LEDGER_PATH)
    prior = next((item for item in ledger.get("daily_runs", []) if item.get("as_of_date") == as_of.isoformat()), None)
    if prior:
        cycle = ledger.get("weekly_cycles", {}).get(prior["cycle_id"], {})
        return {
            "due": False,
            "run_id": prior["run_id"],
            "status": "NOOP_ALREADY_CAPTURED",
            "operating_state": prior["operating_state"],
            "cycle_id": prior["cycle_id"],
            "cycle_completed": bool(cycle.get("completed")),
            "market_rotation_completed": bool(cycle.get("market_rotation_completed")),
            "orders": 0,
            "trade_authority": "NONE",
        }
    plan = plan_batches(root, policy, as_of)
    hk_symbols = [first_value(row, ("stock_code", "canonical_security_id")) for row in plan["hk_selected"]]
    benchmark_symbols = [str(row.get("symbol")) for row in plan["us_benchmark"]]
    rotation_symbols = [row["symbol"] for row in plan["us_selected"] if row["symbol"] not in benchmark_symbols]
    us_symbols = list(dict.fromkeys(benchmark_symbols + rotation_symbols))

    hk_ok, hk_fail = execute_market_rows("HK", hk_symbols, as_of, fetcher, max_workers=12)
    if sleep_seconds:
        time.sleep(sleep_seconds)
    us_ok, us_fail = execute_market_rows("US", us_symbols, as_of, fetcher, max_workers=10)
    sec_rows = build_sec_retrieval_queue(plan["us_sec_selected"], as_of)

    cycle = update_cycle(ledger, as_of, plan["bucket"], hk_ok, hk_fail, us_ok, us_fail, sec_rows, benchmark_symbols, policy)
    run_id = f"ROUND3_{as_of.isoformat()}_B{plan['bucket']}_{hashlib.sha256((as_of.isoformat()+str(plan['bucket'])).encode()).hexdigest()[:10]}"
    proposal = build_proposal(root, cycle, plan["us_benchmark"], policy)
    acceptance_required = int(policy["acceptance"]["completed_weekly_cycles_for_limited_production_acceptance"])
    operating_state = "ROUND3_LIMITED_PRODUCTION_ACCEPTED" if ledger["completed_weekly_cycle_count"] >= acceptance_required else "ROUND3_OPERATING_OBSERVATION"
    run_record = {
        "run_id": run_id,
        "as_of_date": as_of.isoformat(),
        "bucket": plan["bucket"],
        "operating_state": operating_state,
        "completed_weekly_cycle_count": ledger["completed_weekly_cycle_count"],
        "market_rotation_completed_weekly_cycle_count": ledger.get("market_rotation_completed_weekly_cycle_count", 0),
        "hong_kong": {"scope": "SOUTHBOUND_STOCK_CONNECT_ONLY", "universe_count": plan["hk_universe_count"], "attempted": len(hk_ok) + len(hk_fail), "success": len(hk_ok), "failures": len(hk_fail), "full_hkex_market_claimed": False},
        "united_states": {
            "scope": "BOUNDED_ROTATION",
            "security_master_reference_count": policy["united_states"]["expected_security_master_count"],
            "rotation_pool_count": plan["us_rotation_pool_count"],
            "rotation_attempted": len(rotation_symbols),
            "market_success": len(us_ok),
            "market_failures": len(us_fail),
            "benchmark_attempted": len(benchmark_symbols),
            "issuer_reference_count": policy["united_states"]["expected_issuer_count"],
            "sec_pool_count": plan["us_sec_pool_count"],
            "sec_queued": len(sec_rows),
            "sec_execution_mode": policy["united_states"]["sec_execution_mode"],
            "sec_official_success_claimed": False,
            "full_universe_market_history_claimed": False,
        },
        "controls": policy["authority"],
        "canonical_authority": "MERGE_OF_GOVERNED_PR_ONLY",
    }
    ledger["daily_runs"].append({"run_id": run_id, "as_of_date": as_of.isoformat(), "bucket": plan["bucket"], "cycle_id": cycle["cycle_id"], "operating_state": operating_state})
    ledger["daily_runs"] = ledger["daily_runs"][-60:]
    ledger["orders"] = 0
    ledger["trade_authority"] = "NONE"

    write_json(root / LEDGER_PATH, ledger)
    write_json(root / RUN_PATH, run_record)
    write_json(root / PROPOSAL_PATH, proposal)
    evidence_dir = root / EVIDENCE_ROOT / run_id
    write_json(evidence_dir / "ROUND3_SEC_OFFICIAL_RETRIEVAL_QUEUE.json", {"run_id": run_id, "as_of_date": as_of.isoformat(), "execution_environment_required": "CHATGPT_WEB_CONTROLLED_OFFICIAL_RETRIEVAL", "queue": sec_rows, "orders": 0, "trade_authority": "NONE"})
    write_json(evidence_dir / "ROUND3_RUN_EVIDENCE.json", {"run": run_record, "hk_market_successes": hk_ok, "hk_market_failures": hk_fail, "us_market_successes": us_ok, "us_market_failures": us_fail, "us_sec_retrieval_queue": sec_rows})
    manifest = {
        "run_id": run_id,
        "policy_sha256": sha256_file(root / policy_path),
        "input_sha256": {
            str(HK_UNIVERSE): sha256_file(root / HK_UNIVERSE),
            str(US_BENCHMARK): sha256_file(root / US_BENCHMARK),
            str(US_MARKET_INITIAL): sha256_file(root / US_MARKET_INITIAL),
            str(US_MARKET_QUEUE): sha256_file(root / US_MARKET_QUEUE),
            str(US_SEC_INITIAL): sha256_file(root / US_SEC_INITIAL),
            str(US_SEC_QUEUE): sha256_file(root / US_SEC_QUEUE),
        },
        "output_sha256": {
            str(LEDGER_PATH): sha256_file(root / LEDGER_PATH),
            str(RUN_PATH): sha256_file(root / RUN_PATH),
            str(PROPOSAL_PATH): sha256_file(root / PROPOSAL_PATH),
            str(evidence_dir / "ROUND3_SEC_OFFICIAL_RETRIEVAL_QUEUE.json"): sha256_file(evidence_dir / "ROUND3_SEC_OFFICIAL_RETRIEVAL_QUEUE.json"),
        },
        "orders": 0,
        "trade_authority": "NONE",
    }
    write_json(evidence_dir / "ROUND3_MANIFEST.json", manifest)
    return {"due": True, "run_id": run_id, "status": proposal["status"], "operating_state": operating_state, "cycle_id": cycle["cycle_id"], "cycle_completed": cycle["completed"], "market_rotation_completed": cycle["market_rotation_completed"], "hk_success": len(hk_ok), "us_success": len(us_ok), "sec_queued": len(sec_rows), "orders": 0, "trade_authority": "NONE"}'''
    text = replace_between(text, "def run(", "def main()", run)
    path.write_text(text, encoding="utf-8")


def patch_validator() -> None:
    path = ROOT / "automation/cross_market/validate_round3_outputs.py"
    text = path.read_text(encoding="utf-8")
    marker = '''    if run.get("united_states", {}).get("full_universe_market_history_claimed") is not False:
        raise SystemExit("ROUND3_RUN_US_OVERCLAIM")
'''
    addition = marker + '''    us_run = run.get("united_states", {})
    if us_run.get("sec_execution_mode") != "QUEUE_FOR_CHATGPT_WEB_OFFICIAL_RETRIEVAL":
        raise SystemExit("ROUND3_SEC_EXECUTION_ENVIRONMENT_MISMATCH")
    if us_run.get("sec_official_success_claimed") is not False:
        raise SystemExit("ROUND3_FALSE_SEC_SUCCESS_CLAIM")
    if int(us_run.get("rotation_pool_count", 0)) != int(policy["united_states"]["expected_security_master_count"]):
        raise SystemExit("ROUND3_US_ROTATION_POOL_COUNT_MISMATCH")
    if int(us_run.get("sec_pool_count", 0)) != int(policy["united_states"]["expected_issuer_count"]):
        raise SystemExit("ROUND3_US_SEC_POOL_COUNT_MISMATCH")
    if proposal.get("sec_official_retrieval_status") not in {
        "PENDING_CHATGPT_WEB_OFFICIAL_RETRIEVAL",
        "PARTIAL_CHATGPT_WEB_OFFICIAL_RETRIEVAL",
        "PASS_CHATGPT_WEB_OFFICIAL_RETRIEVAL",
    }:
        raise SystemExit("ROUND3_SEC_RETRIEVAL_STATUS_INVALID")
    for cycle in ledger.get("weekly_cycles", {}).values():
        if cycle.get("completed") and int(cycle.get("sec_official_completed_issuer_count", 0)) < int(policy["united_states"]["minimum_weekly_official_sec_completed_count"]):
            raise SystemExit("ROUND3_WEEKLY_ACCEPTANCE_WITHOUT_SEC_EVIDENCE")
'''
    if "ROUND3_SEC_EXECUTION_ENVIRONMENT_MISMATCH" not in text:
        text = text.replace(marker, addition)
    path.write_text(text, encoding="utf-8")


def patch_tests() -> None:
    path = ROOT / "automation/cross_market/tests/test_round3_limited_production.py"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        '"expected_security_master_count": 100, "daily_rotation_batch_size": 4, "daily_sec_batch_size": 2, "minimum_weekly_rotation_attempted_count": 15, "minimum_weekly_benchmark_success_count": 2',
        '"expected_security_master_count": 100, "expected_issuer_count": 30, "daily_rotation_batch_size": 4, "daily_sec_batch_size": 2, "minimum_weekly_rotation_attempted_count": 15, "minimum_weekly_benchmark_success_count": 2, "minimum_weekly_sec_queued_count": 8, "minimum_weekly_official_sec_completed_count": 8, "sec_execution_mode": "QUEUE_FOR_CHATGPT_WEB_OFFICIAL_RETRIEVAL"',
    )
    old = '''    market_rows = [{"symbol": f"T{idx:03d}", "canonical_security_id": f"USSEC-{idx:03d}"} for idx in range(100)]
    sec_rows = [{"symbol": f"T{idx:03d}", "canonical_issuer_id": f"USISS-{idx:03d}", "cik": str(1000000 + idx)} for idx in range(30)]
    write_jsonl_gz(root / "outputs/fmdl6x2/current/market_reference/FMDL6X2D_BACKFILL_QUEUE.jsonl.gz", market_rows)
    write_jsonl_gz(root / "outputs/fmdl6x2/current/sec_filings_facts/FMDL6X2E_BACKFILL_QUEUE.jsonl.gz", sec_rows)
'''
    new = '''    initial_market = {"cohort_size": 4, "securities": [{"selected_symbol": f"T{idx:03d}", "canonical_security_id": f"USSEC-{idx:03d}"} for idx in range(4)]}
    write_json(root / "outputs/fmdl6x2/current/market_reference/FMDL6X2D_INITIAL_COHORT.json", initial_market)
    market_rows = [{"symbol": f"T{idx:03d}", "canonical_security_id": f"USSEC-{idx:03d}"} for idx in range(4, 100)]
    sec_initial = root / "evidence/fmdl6x2e/2026-07-22/FMDL6X2E_FILINGS.csv"
    sec_initial.parent.mkdir(parents=True, exist_ok=True)
    with sec_initial.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["symbol", "cik10"])
        writer.writeheader()
        for idx in range(2):
            writer.writerow({"symbol": f"T{idx:03d}", "cik10": str(1000000 + idx)})
    sec_rows = [{"symbol": f"T{idx:03d}", "canonical_issuer_id": f"USISS-{idx:03d}", "cik": str(1000000 + idx)} for idx in range(2, 30)]
    write_jsonl_gz(root / "outputs/fmdl6x2/current/market_reference/FMDL6X2D_BACKFILL_QUEUE.jsonl.gz", market_rows)
    write_jsonl_gz(root / "outputs/fmdl6x2/current/sec_filings_facts/FMDL6X2E_BACKFILL_QUEUE.jsonl.gz", sec_rows)
'''
    text = text.replace(old, new)
    text = text.replace(
        '    assert proposal["cycle_completed"] is True\n',
        '    assert proposal["market_rotation_completed"] is True\n    assert proposal["cycle_completed"] is False\n    assert proposal["sec_official_retrieval_status"] == "PENDING_CHATGPT_WEB_OFFICIAL_RETRIEVAL"\n',
    )
    text = text.replace(
        '    assert run_current["operating_state"] == "ROUND3_OPERATING_OBSERVATION"\n',
        '    assert run_current["operating_state"] == "ROUND3_OPERATING_OBSERVATION"\n    assert run_current["united_states"]["sec_queued"] == 2\n    assert run_current["united_states"]["sec_official_success_claimed"] is False\n',
    )
    path.write_text(text, encoding="utf-8")


def patch_workflow() -> None:
    path = ROOT / ".github/workflows/round3-cross-market-limited-production.yml"
    text = path.read_text(encoding="utf-8")
    marker = '''          pytest -q automation/cross_market/tests/test_round3_limited_production.py
'''
    preflight = marker + '''      - name: Validate real Canonical input compatibility
        run: |
          PYTHONPATH=. python - <<'PY'
          from datetime import date, timedelta
          from pathlib import Path
          from automation.cross_market.build_round3_limited_production import plan_batches, read_json

          root = Path('.')
          policy = read_json(root / 'automation/cross_market/round3_policy.json')
          start = date(2026, 8, 3)
          plans = [plan_batches(root, policy, start + timedelta(days=offset)) for offset in range(5)]
          assert {plan['hk_universe_count'] for plan in plans} == {644}
          hk_ids = {
              row['canonical_security_id']
              for plan in plans
              for row in plan['hk_selected']
          }
          assert len(hk_ids) == 644
          assert {plan['us_rotation_pool_count'] for plan in plans} == {8785}
          assert all(len(plan['us_selected']) == 64 for plan in plans)
          assert {plan['us_sec_pool_count'] for plan in plans} == {7419}
          assert all(len(plan['us_sec_selected']) == 8 for plan in plans)
          assert all(len(plan['us_benchmark']) == 7 for plan in plans)
          print({
              'hk_universe': len(hk_ids),
              'us_rotation_pool': plans[0]['us_rotation_pool_count'],
              'us_daily_batch': len(plans[0]['us_selected']),
              'us_issuer_pool': plans[0]['us_sec_pool_count'],
              'sec_daily_queue': len(plans[0]['us_sec_selected']),
              'benchmark_daily': len(plans[0]['us_benchmark']),
          })
          PY
'''
    if "Validate real Canonical input compatibility" not in text:
        text = text.replace(marker, preflight)
    text = text.replace('''        env:
          SEC_USER_AGENT: "investment-os-market-data/1.0 contact:ljjx2020@gmail.com"
        run: |
''', '''        run: |
''')
    text = text.replace("seven-name daily benchmark plus bounded 64-name rotation and eight-issuer SEC batch", "seven-name daily benchmark plus bounded 64-name rotation and eight-issuer official SEC retrieval queue")
    path.write_text(text, encoding="utf-8")


def patch_docs() -> None:
    path = ROOT / "docs/ROUND3_HK_US_LIMITED_PRODUCTION.md"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "A deterministic 64-security market-data batch and an eight-issuer official SEC batch rotate each weekday.",
        "A deterministic 64-security market-data batch and an eight-issuer official SEC retrieval queue rotate each weekday.",
    )
    text = text.replace(
        "Yahoo dual-route market evidence remains `NON_DECISION_GRADE_FALLBACK`. SEC submissions and company facts are official research evidence, but neither source alone authorizes an investment conclusion.",
        "Yahoo dual-route market evidence remains `NON_DECISION_GRADE_FALLBACK`. GitHub Hosted Runner is not authorized to claim SEC retrieval success because the accepted FMDL-6 contract records repeatable 403 responses. The workflow therefore emits an eight-issuer queue for ChatGPT web-controlled retrieval from official SEC submissions and company facts; official evidence remains research-only and does not authorize an investment conclusion.",
    )
    text = text.replace(
        "- `ROUND3_LIMITED_PRODUCTION_ACCEPTED`: at least three completed weekly rotations pass all source, scope and authority gates.",
        "- `ROUND3_LIMITED_PRODUCTION_ACCEPTED`: at least three completed weekly rotations pass all source, scope and authority gates, including at least 30 official SEC issuer refreshes per accepted week through the ChatGPT web-controlled observer.",
    )
    path.write_text(text, encoding="utf-8")


def main() -> None:
    patch_engine()
    patch_validator()
    patch_tests()
    patch_workflow()
    patch_docs()
    policy = json.loads((ROOT / "automation/cross_market/round3_policy.json").read_text(encoding="utf-8"))
    assert policy["united_states"]["sec_execution_mode"] == "QUEUE_FOR_CHATGPT_WEB_OFFICIAL_RETRIEVAL"


if __name__ == "__main__":
    main()
