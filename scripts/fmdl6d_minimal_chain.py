#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import shutil
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

PROGRAM_ID = "FMDL-6D"
DEFAULT_CONTRACT = "config/fmdl6d_minimal_end_to_end_data_chain_contract.json"
DEFAULT_CAPTURE = "outputs/fmdl6d/work/FMDL6D_RAW_CAPTURE.json"
DEFAULT_CANDIDATE = "outputs/fmdl6d/candidate"
DEFAULT_ACCEPTANCE = "outputs/fmdl6d/acceptance/FMDL6D_INDEPENDENT_ACCEPTANCE.json"
USER_AGENT = "investment-os-market-data FMDL-6D/1.0 technical-pilot"


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def http_get(url: str, *, timeout: int = 30, attempts: int = 4) -> tuple[bytes, dict[str, str], int, float]:
    last_error: Exception | None = None
    for attempt in range(attempts):
        started = time.monotonic()
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json,text/csv,text/plain,*/*",
                "Accept-Encoding": "identity",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = response.read()
                latency_ms = round((time.monotonic() - started) * 1000, 3)
                headers = {str(k).lower(): str(v) for k, v in response.headers.items()}
                return payload, headers, int(response.status), latency_ms
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt + 1 >= attempts:
                break
            time.sleep(min(8.0, 1.5 * (2**attempt)))
    raise RuntimeError(f"GET failed after {attempts} attempts: {url}: {last_error}")


def yahoo_url(host: str, symbol: str, start: str, end_exclusive: str) -> str:
    period1 = int(datetime.combine(parse_date(start), datetime.min.time(), tzinfo=timezone.utc).timestamp())
    period2 = int(datetime.combine(parse_date(end_exclusive), datetime.min.time(), tzinfo=timezone.utc).timestamp())
    encoded = urllib.parse.quote(symbol, safe=".-")
    params = urllib.parse.urlencode(
        {
            "period1": period1,
            "period2": period2,
            "interval": "1d",
            "events": "div,splits",
            "includeAdjustedClose": "true",
        }
    )
    return f"https://{host}.finance.yahoo.com/v8/finance/chart/{encoded}?{params}"


def parse_yahoo_payload(payload: bytes, expected_symbol: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    decoded = json.loads(payload)
    chart = decoded.get("chart") or {}
    if chart.get("error"):
        raise ValueError(f"Yahoo chart error: {chart['error']}")
    result = (chart.get("result") or [None])[0]
    if not result:
        raise ValueError("Yahoo chart result missing")
    timestamps = result.get("timestamp") or []
    indicators = result.get("indicators") or {}
    quote = (indicators.get("quote") or [{}])[0]
    adjusted = (indicators.get("adjclose") or [{}])[0].get("adjclose") or [None] * len(timestamps)
    fields = {key: quote.get(key) or [None] * len(timestamps) for key in ("open", "high", "low", "close", "volume")}
    observations: list[dict[str, Any]] = []
    for index, timestamp in enumerate(timestamps):
        values = {key: fields[key][index] if index < len(fields[key]) else None for key in fields}
        if any(values[key] is None for key in ("open", "high", "low", "close")):
            continue
        observations.append(
            {
                "trade_date": datetime.fromtimestamp(int(timestamp), timezone.utc).date().isoformat(),
                "open": float(values["open"]),
                "high": float(values["high"]),
                "low": float(values["low"]),
                "close": float(values["close"]),
                "adjusted_close": float(adjusted[index]) if index < len(adjusted) and adjusted[index] is not None else float(values["close"]),
                "volume": int(values["volume"] or 0),
            }
        )
    events: list[dict[str, Any]] = []
    event_root = result.get("events") or {}
    for event_type, event_map in (("DIVIDEND", event_root.get("dividends") or {}), ("SPLIT", event_root.get("splits") or {})):
        for _, row in sorted(event_map.items(), key=lambda item: int(item[0])):
            timestamp = int(row.get("date") or 0)
            event = {
                "event_type": event_type,
                "event_date": datetime.fromtimestamp(timestamp, timezone.utc).date().isoformat(),
            }
            if event_type == "DIVIDEND":
                event["amount"] = float(row.get("amount") or 0.0)
                event["currency"] = (result.get("meta") or {}).get("currency")
            else:
                event["numerator"] = float(row.get("numerator") or 0.0)
                event["denominator"] = float(row.get("denominator") or 0.0)
                event["split_ratio"] = row.get("splitRatio")
            events.append(event)
    meta = result.get("meta") or {}
    returned_symbol = str(meta.get("symbol") or expected_symbol)
    return observations, events, {
        "returned_symbol": returned_symbol,
        "currency": meta.get("currency"),
        "exchange_name": meta.get("exchangeName"),
        "instrument_type": meta.get("instrumentType"),
        "timezone": meta.get("exchangeTimezoneName"),
        "first_trade_date": meta.get("firstTradeDate"),
        "regular_market_time": meta.get("regularMarketTime"),
    }


def fetch_yahoo_series(symbol: str, start: str, end_exclusive: str) -> dict[str, Any]:
    errors: list[str] = []
    for host in ("query1", "query2"):
        url = yahoo_url(host, symbol, start, end_exclusive)
        try:
            payload, headers, status, latency = http_get(url)
            observations, events, meta = parse_yahoo_payload(payload, symbol)
            if not observations:
                raise ValueError("Yahoo returned no usable daily observations")
            return {
                "route_id": f"YAHOO_{host.upper()}_CHART_EVENTS",
                "source_authority": "YAHOO_FREE_UNOFFICIAL",
                "official_or_fallback": "FREE_FALLBACK",
                "url": url,
                "http_status": status,
                "latency_ms": latency,
                "response_bytes": len(payload),
                "payload_sha256": sha256_bytes(payload),
                "retrieved_headers": {k: headers[k] for k in sorted(headers) if k in {"content-type", "etag", "last-modified", "cache-control"}},
                "meta": meta,
                "observations": observations,
                "events": events,
            }
        except Exception as exc:  # noqa: BLE001 - route fallback records full failure context
            errors.append(f"{host}:{type(exc).__name__}:{exc}")
    raise RuntimeError(f"all Yahoo routes failed for {symbol}: {' | '.join(errors)}")


def ecb_url(currency: str, start: str) -> str:
    return (
        "https://data-api.ecb.europa.eu/service/data/EXR/"
        f"D.{currency}.EUR.SP00.A?startPeriod={urllib.parse.quote(start)}&format=csvdata"
    )


def parse_ecb_csv(payload: bytes, expected_currency: str) -> list[dict[str, Any]]:
    text = payload.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    rows: dict[str, float] = {}
    for row in reader:
        currency = str(row.get("CURRENCY") or row.get("KEY") or "")
        if expected_currency not in currency:
            continue
        period = str(row.get("TIME_PERIOD") or "").strip()
        raw = str(row.get("OBS_VALUE") or "").strip()
        if not period or not raw:
            continue
        try:
            rows[period] = float(raw)
        except ValueError:
            continue
    return [{"reference_date": key, "eur_per_unit_inverse": value} for key, value in sorted(rows.items())]


def fetch_ecb_series(currency: str, start: str) -> dict[str, Any]:
    url = ecb_url(currency, start)
    payload, headers, status, latency = http_get(url, timeout=45)
    observations = parse_ecb_csv(payload, currency)
    if not observations:
        raise ValueError(f"ECB returned no observations for {currency}")
    return {
        "route_id": f"ECB_EXR_D_{currency}_EUR_SP00_A",
        "source_authority": "ECB_OFFICIAL",
        "official_or_fallback": "OFFICIAL_PRIMARY",
        "url": url,
        "http_status": status,
        "latency_ms": latency,
        "response_bytes": len(payload),
        "payload_sha256": sha256_bytes(payload),
        "retrieved_headers": {k: headers[k] for k in sorted(headers) if k in {"content-type", "etag", "last-modified", "cache-control"}},
        "currency": currency,
        "observations": observations,
    }


def derive_fx_pairs(series: dict[str, dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    maps: dict[str, dict[str, float]] = {}
    for currency, payload in series.items():
        maps[currency] = {row["reference_date"]: float(row["eur_per_unit_inverse"]) for row in payload["observations"]}
    common_dates = sorted(set(maps["USD"]) & set(maps["CNY"]) & set(maps["HKD"]))
    cny: list[dict[str, Any]] = []
    hkd: list[dict[str, Any]] = []
    for current_date in common_dates:
        usd_per_eur = maps["USD"][current_date]
        if not usd_per_eur:
            continue
        cny.append({"reference_date": current_date, "rate": round(maps["CNY"][current_date] / usd_per_eur, 10)})
        hkd.append({"reference_date": current_date, "rate": round(maps["HKD"][current_date] / usd_per_eur, 10)})
    return {"USD/CNY": cny, "USD/HKD": hkd}


def _load_pointer(repo_root: Path, relative: str) -> dict[str, Any]:
    path = repo_root / relative
    if not path.exists():
        raise ValueError(f"missing entry-gate pointer: {relative}")
    return load_json(path)


def validate_contract(repo_root: Path, contract_path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    contract = load_json(contract_path)
    checks: list[dict[str, Any]] = []
    errors: list[str] = []

    def check(name: str, condition: bool, detail: Any = None) -> None:
        checks.append({"check": name, "status": "PASS" if condition else "FAIL", "detail": detail})
        if not condition:
            errors.append(name)

    check("PROGRAM_ID", contract.get("program_id") == PROGRAM_ID)
    check("AUTHORITY", contract.get("authority") == "BOUNDED_TECHNICAL_DATA_CHAIN_ONLY")
    check("TRADE_AUTHORITY", contract.get("trade_authority") == "NONE")
    entry = contract.get("entry_gates") or {}
    for prefix in ("fmdl6b", "fmdl6c"):
        pointer = _load_pointer(repo_root, entry[f"{prefix}_pointer"])
        check(f"{prefix.upper()}_RELEASE", pointer.get("release_id") == entry[f"{prefix}_release_id"], pointer.get("release_id"))
        check(f"{prefix.upper()}_STATUS", pointer.get("status") == entry[f"{prefix}_status"], pointer.get("status"))
        check(f"{prefix.upper()}_TRADE_AUTHORITY", pointer.get("trade_authority") == "NONE")
    scope = contract.get("scope") or {}
    forbidden = [key for key, value in scope.items() if key.endswith("_authorized") and value is not False]
    check("NO_SCOPE_AUTHORITY_LEAK", not forbidden, forbidden)
    sample = contract.get("sample_securities") or []
    check("MARKET_SAMPLE_COUNT", len(sample) == 8, len(sample))
    check("UNIQUE_SECURITY_KEYS", len({row.get("security_key") for row in sample}) == len(sample))
    check("UNIQUE_MARKET_SYMBOLS", len({row.get("market_symbol") for row in sample}) == len(sample))
    pool_path = repo_root / "outputs/fmdl6c/current/FMDL6C_BENCHMARK_POOL.json"
    pool = load_json(pool_path)
    by_security = {row["security_key"]: row for row in pool.get("securities", [])}
    for row in sample:
        upstream = by_security.get(row["security_key"])
        check(f"SECURITY_BINDING:{row['ticker']}", upstream is not None and upstream.get("cik10") == row.get("cik10"), upstream)
        check(f"BENCHMARK_ONLY:{row['ticker']}", upstream is not None and upstream.get("benchmark_only") is True)
        check(f"NO_INVESTMENT_AUTHORITY:{row['ticker']}", upstream is not None and upstream.get("investment_eligible") is False and upstream.get("research_candidate") is False and upstream.get("trade_authority") == "NONE")
    sec_path = repo_root / contract["source_routes"]["sec_financial_sample"]["path"]
    sec_snapshot = load_json(sec_path)
    issuers = sec_snapshot.get("issuers") or []
    check("SEC_FINANCIAL_ISSUER_COUNT", len(issuers) == 4, len(issuers))
    fact_count = sum(len(row.get("facts") or []) for row in issuers)
    check("SEC_FINANCIAL_FACT_COUNT", fact_count >= contract["acceptance_gates"]["minimum_financial_fact_count"], fact_count)
    check("SEC_OFFICIAL_URLS", all(str(row.get("official_filing_url", "")).startswith("https://www.sec.gov/Archives/edgar/data/") for row in issuers))
    check("SEC_NO_SILENT_REPLACEMENT", sec_snapshot.get("no_silent_replacement") is True)
    check("EXIT_STATUS", contract.get("exit_status") == "FMDL6D_MINIMAL_END_TO_END_DATA_CHAIN_ACCEPTED")
    check("NEXT_GATE", contract.get("next_gate") == "FMDL-6E_QUALITY_FAILURE_AND_COST_BENCHMARK")
    return checks, errors


def capture_inputs(repo_root: Path, contract_path: Path, capture_path: Path) -> dict[str, Any]:
    checks, errors = validate_contract(repo_root, contract_path)
    if errors:
        raise ValueError(f"contract validation failed: {errors}")
    contract = load_json(contract_path)
    captured_at = utc_now()
    end_exclusive = (captured_at.date() + timedelta(days=1)).isoformat()
    market: list[dict[str, Any]] = []
    for sample in contract["sample_securities"]:
        series = fetch_yahoo_series(sample["market_symbol"], contract["source_routes"]["market"]["history_start"], end_exclusive)
        market.append({"sample": sample, "capture": series})
    ecb: dict[str, dict[str, Any]] = {}
    for currency in contract["source_routes"]["fx"]["currencies"]:
        ecb[currency] = fetch_ecb_series(currency, contract["source_routes"]["fx"]["history_start"])
    fx_pairs = derive_fx_pairs(ecb)
    sec_path = repo_root / contract["source_routes"]["sec_financial_sample"]["path"]
    capture = {
        "program_id": PROGRAM_ID,
        "captured_at_utc": iso_z(captured_at),
        "as_of_date": captured_at.date().isoformat(),
        "contract_sha256": sha256_file(contract_path),
        "contract_checks": checks,
        "upstream": {
            "fmdl6b": load_json(repo_root / contract["entry_gates"]["fmdl6b_pointer"]),
            "fmdl6c": load_json(repo_root / contract["entry_gates"]["fmdl6c_pointer"]),
        },
        "market": market,
        "ecb_series": ecb,
        "fx_pairs": fx_pairs,
        "sec_financial_snapshot": {
            "path": contract["source_routes"]["sec_financial_sample"]["path"],
            "sha256": sha256_file(sec_path),
            "snapshot": load_json(sec_path),
        },
        "trade_authority": "NONE",
    }
    write_json(capture_path, capture)
    return capture


def validate_capture(
    contract: dict[str, Any],
    capture: dict[str, Any],
    *,
    expected_contract_sha256: str | None = None,
    expected_sec_snapshot_sha256: str | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    checks: list[dict[str, Any]] = []
    errors: list[str] = []

    def check(name: str, condition: bool, detail: Any = None) -> None:
        checks.append({"check": name, "status": "PASS" if condition else "FAIL", "detail": detail})
        if not condition:
            errors.append(name)

    gates = contract["acceptance_gates"]
    market = capture.get("market") or []
    check("CAPTURE_PROGRAM_ID", capture.get("program_id") == PROGRAM_ID)
    check("CAPTURE_TRADE_AUTHORITY", capture.get("trade_authority") == "NONE")
    check(
        "CAPTURE_CONTRACT_SHA",
        len(str(capture.get("contract_sha256", ""))) == 64
        and (expected_contract_sha256 is None or capture.get("contract_sha256") == expected_contract_sha256),
        capture.get("contract_sha256"),
    )
    upstream = capture.get("upstream") or {}
    check("CAPTURE_FMDL6B_RELEASE", (upstream.get("fmdl6b") or {}).get("release_id") == contract["entry_gates"]["fmdl6b_release_id"])
    check("CAPTURE_FMDL6C_RELEASE", (upstream.get("fmdl6c") or {}).get("release_id") == contract["entry_gates"]["fmdl6c_release_id"])
    check("CAPTURE_MARKET_SECURITY_COUNT", len(market) == gates["market_security_count"], len(market))
    total = 0
    seen: set[str] = set()
    for item in market:
        symbol = item["sample"]["market_symbol"]
        seen.add(symbol)
        rows = item["capture"].get("observations") or []
        total += len(rows)
        check(f"MARKET_MIN_OBSERVATIONS:{symbol}", len(rows) >= gates["minimum_daily_observations_per_security"], len(rows))
        dates = [row["trade_date"] for row in rows]
        check(f"MARKET_UNIQUE_DATES:{symbol}", len(dates) == len(set(dates)))
        check(f"MARKET_SORTED_DATES:{symbol}", dates == sorted(dates))
        check(f"MARKET_LINEAGE:{symbol}", bool(item["capture"].get("url")) and len(str(item["capture"].get("payload_sha256", ""))) == 64)
        check(f"MARKET_ROUTE:{symbol}", item["capture"].get("source_authority") == "YAHOO_FREE_UNOFFICIAL" and item["capture"].get("official_or_fallback") == "FREE_FALLBACK")
        check(f"MARKET_SAMPLE_BINDING:{symbol}", item.get("sample") in contract["sample_securities"])
    check("MARKET_SYMBOL_SET", seen == {row["market_symbol"] for row in contract["sample_securities"]}, sorted(seen))
    check("MARKET_TOTAL_OBSERVATIONS", total >= gates["minimum_total_daily_observations"], total)
    fx_pairs = capture.get("fx_pairs") or {}
    for pair in contract["source_routes"]["fx"]["derived_pairs"]:
        rows = fx_pairs.get(pair) or []
        check(f"FX_MIN_OBSERVATIONS:{pair}", len(rows) >= gates["minimum_fx_observations_per_pair"], len(rows))
        check(f"FX_POSITIVE:{pair}", all(float(row["rate"]) > 0 for row in rows))
    ecb = capture.get("ecb_series") or {}
    check("ECB_SOURCE_COUNT", set(ecb) == set(contract["source_routes"]["fx"]["currencies"]), sorted(ecb))
    check("ECB_OFFICIAL_LINEAGE", all(row.get("source_authority") == "ECB_OFFICIAL" and len(str(row.get("payload_sha256", ""))) == 64 for row in ecb.values()))
    sec_wrapper = capture.get("sec_financial_snapshot") or {}
    sec = sec_wrapper.get("snapshot") or {}
    check(
        "SEC_SNAPSHOT_HASH",
        len(str(sec_wrapper.get("sha256", ""))) == 64
        and (expected_sec_snapshot_sha256 is None or sec_wrapper.get("sha256") == expected_sec_snapshot_sha256),
    )
    check("SEC_SNAPSHOT_ROUTE", sec.get("retrieval_route") == contract["source_routes"]["sec_financial_sample"]["route"])
    check("SEC_SNAPSHOT_AUTHORITY", sec.get("source_authority") == contract["source_routes"]["sec_financial_sample"]["authority"])
    issuers = sec.get("issuers") or []
    check("FINANCIAL_SAMPLE_ISSUER_COUNT", len(issuers) == gates["financial_sample_issuer_count"], len(issuers))
    total_facts = sum(len(row.get("facts") or []) for row in issuers)
    check("FINANCIAL_SAMPLE_FACT_COUNT", total_facts >= gates["minimum_financial_fact_count"], total_facts)
    for issuer in issuers:
        check(f"FINANCIAL_MIN_FACTS:{issuer['cik10']}", len(issuer.get("facts") or []) >= gates["minimum_financial_facts_per_issuer"], len(issuer.get("facts") or []))
        check(f"FINANCIAL_AVAILABILITY:{issuer['cik10']}", bool(issuer.get("available_from_utc")) and bool(issuer.get("availability_basis")))
        check(f"FINANCIAL_OFFICIAL_URL:{issuer['cik10']}", str(issuer.get("official_filing_url", "")).startswith("https://www.sec.gov/Archives/edgar/data/"))
    return checks, errors


def _canonical_file_hashes(output_dir: Path, names: list[str]) -> dict[str, str]:
    return {name: sha256_file(output_dir / name) for name in names}


def build_candidate(repo_root: Path, contract_path: Path, capture_path: Path, candidate_dir: Path) -> dict[str, Any]:
    contract = load_json(contract_path)
    capture = load_json(capture_path)
    contract_checks, contract_errors = validate_contract(repo_root, contract_path)
    sec_snapshot_path = repo_root / contract["source_routes"]["sec_financial_sample"]["path"]
    capture_checks, capture_errors = validate_capture(
        contract,
        capture,
        expected_contract_sha256=sha256_file(contract_path),
        expected_sec_snapshot_sha256=sha256_file(sec_snapshot_path),
    )
    hard_failures = contract_errors + capture_errors
    if hard_failures:
        raise ValueError(f"FMDL-6D build rejected: {hard_failures}")
    if candidate_dir.exists():
        shutil.rmtree(candidate_dir)
    candidate_dir.mkdir(parents=True, exist_ok=True)
    captured_at = capture["captured_at_utc"]
    market_securities: list[dict[str, Any]] = []
    total_daily = 0
    total_events = 0
    source_registry: list[dict[str, Any]] = []
    for item in capture["market"]:
        sample = item["sample"]
        source = item["capture"]
        rows = []
        for row in source["observations"]:
            enriched = dict(row)
            enriched["available_from_utc"] = captured_at
            enriched["availability_basis"] = "CONSERVATIVE_RETRIEVAL_TIMESTAMP"
            enriched["point_in_time_status"] = "RETRIEVAL_BOUND_ONLY_NOT_HISTORICAL_AS_OF"
            rows.append(enriched)
        events = []
        for event in source["events"]:
            enriched_event = dict(event)
            enriched_event["available_from_utc"] = captured_at
            enriched_event["availability_basis"] = "CONSERVATIVE_RETRIEVAL_TIMESTAMP"
            enriched_event["point_in_time_status"] = "RETRIEVAL_BOUND_ONLY_NOT_HISTORICAL_AS_OF"
            events.append(enriched_event)
        total_daily += len(rows)
        total_events += len(events)
        series_key = f"USMKT:{sample['security_key']}:{rows[0]['trade_date']}:{rows[-1]['trade_date']}"
        market_securities.append(
            {
                "series_key": series_key,
                "security_key": sample["security_key"],
                "ticker": sample["ticker"],
                "market_symbol": sample["market_symbol"],
                "cik10": sample["cik10"],
                "case_role": sample["case_role"],
                "currency": source["meta"].get("currency"),
                "source_route_id": source["route_id"],
                "source_payload_sha256": source["payload_sha256"],
                "source_url": source["url"],
                "observation_count": len(rows),
                "event_count": len(events),
                "history_start": rows[0]["trade_date"],
                "history_end": rows[-1]["trade_date"],
                "observations": rows,
                "corporate_actions": events,
                "benchmark_only": True,
                "investment_eligible": False,
                "trade_authority": "NONE",
            }
        )
        source_registry.append(
            {
                "source_id": f"MARKET:{sample['market_symbol']}",
                "interface_family": "FREE_DAILY_MARKET_CORPORATE_ACTION_AND_FX",
                "route_id": source["route_id"],
                "source_authority": source["source_authority"],
                "official_or_fallback": source["official_or_fallback"],
                "url": source["url"],
                "retrieved_at_utc": captured_at,
                "payload_sha256": source["payload_sha256"],
                "response_bytes": source["response_bytes"],
                "parser_version": "FMDL6D_YAHOO_CHART_V1",
                "no_silent_replacement": True,
                "decision_grade": False,
            }
        )
    market_store = {
        "program_id": PROGRAM_ID,
        "captured_at_utc": captured_at,
        "source_posture": "FREE_MARKET_DATA_PILOT_ONLY_NOT_DECISION_GRADE",
        "security_count": len(market_securities),
        "total_daily_observations": total_daily,
        "total_corporate_actions": total_events,
        "securities": market_securities,
        "trade_authority": "NONE",
    }
    fx_series: list[dict[str, Any]] = []
    for pair in contract["source_routes"]["fx"]["derived_pairs"]:
        observations = []
        for row in capture["fx_pairs"][pair]:
            observations.append(
                {
                    **row,
                    "available_from_utc": captured_at,
                    "availability_basis": "CONSERVATIVE_RETRIEVAL_TIMESTAMP",
                    "point_in_time_status": "REFERENCE_DATE_WITH_RETRIEVAL_BOUND",
                }
            )
        fx_series.append(
            {
                "pair": pair,
                "observation_count": len(observations),
                "history_start": observations[0]["reference_date"],
                "history_end": observations[-1]["reference_date"],
                "derivation": "ECB_CURRENCY_PER_EUR_CROSS_RATE",
                "observations": observations,
            }
        )
    ecb_hashes = {currency: payload["payload_sha256"] for currency, payload in capture["ecb_series"].items()}
    fx_store = {
        "program_id": PROGRAM_ID,
        "captured_at_utc": captured_at,
        "source_authority": "ECB_OFFICIAL",
        "source_payload_sha256_by_currency": ecb_hashes,
        "series": fx_series,
        "trade_authority": "NONE",
    }
    for currency, source in capture["ecb_series"].items():
        source_registry.append(
            {
                "source_id": f"FX:ECB:{currency}/EUR",
                "interface_family": "FREE_DAILY_MARKET_CORPORATE_ACTION_AND_FX",
                "route_id": source["route_id"],
                "source_authority": "ECB_OFFICIAL",
                "official_or_fallback": "OFFICIAL_PRIMARY",
                "url": source["url"],
                "retrieved_at_utc": captured_at,
                "payload_sha256": source["payload_sha256"],
                "response_bytes": source["response_bytes"],
                "parser_version": "FMDL6D_ECB_CSV_V1",
                "no_silent_replacement": True,
                "decision_grade": False,
            }
        )
    sec_snapshot = capture["sec_financial_snapshot"]["snapshot"]
    facts: list[dict[str, Any]] = []
    issuer_records: list[dict[str, Any]] = []
    facts_by_issuer: dict[str, list[str]] = defaultdict(list)
    for issuer in sec_snapshot["issuers"]:
        issuer_fact_rows = []
        for fact in issuer["facts"]:
            row = {
                **fact,
                "issuer_key": issuer["issuer_key"],
                "cik10": issuer["cik10"],
                "entity_name": issuer["entity_name"],
                "filing_form": issuer["filing_form"],
                "report_period_end": issuer["report_period_end"],
                "filing_accession": issuer["filing_accession"],
                "official_filing_url": issuer["official_filing_url"],
                "filing_date": issuer.get("filing_date"),
                "available_from_utc": issuer["available_from_utc"],
                "availability_basis": issuer["availability_basis"],
                "point_in_time_status": "CONSERVATIVE_RETRIEVAL_BOUND",
                "normalization_status": "MINIMAL_SELECTED_FACT_SAMPLE",
                "decision_grade": False,
            }
            facts.append(row)
            issuer_fact_rows.append(row["fact_key"])
            facts_by_issuer[issuer["issuer_key"]].append(row["fact_key"])
        issuer_records.append(
            {
                "issuer_key": issuer["issuer_key"],
                "cik10": issuer["cik10"],
                "entity_name": issuer["entity_name"],
                "filing_form": issuer["filing_form"],
                "report_period_end": issuer["report_period_end"],
                "filing_accession": issuer["filing_accession"],
                "official_filing_url": issuer["official_filing_url"],
                "available_from_utc": issuer["available_from_utc"],
                "availability_basis": issuer["availability_basis"],
                "fact_keys": issuer_fact_rows,
            }
        )
    financial_store = {
        "program_id": PROGRAM_ID,
        "snapshot_id": sec_snapshot["snapshot_id"],
        "snapshot_sha256": capture["sec_financial_snapshot"]["sha256"],
        "retrieval_route": sec_snapshot["retrieval_route"],
        "source_authority": sec_snapshot["source_authority"],
        "full_raw_payload_retained": False,
        "issuer_count": len(issuer_records),
        "fact_count": len(facts),
        "issuers": issuer_records,
        "facts": facts,
        "controlled_limitations": sec_snapshot["controlled_limitations"],
        "trade_authority": "NONE",
    }
    source_registry.append(
        {
            "source_id": "SEC:SELECTED_FINANCIAL_FACT_SAMPLE",
            "interface_family": "SEC_EDGAR_COMPANY_FACTS_AND_XBRL",
            "route_id": sec_snapshot["retrieval_route"],
            "source_authority": sec_snapshot["source_authority"],
            "official_or_fallback": "OFFICIAL_PRIMARY_SELECTED_FACTS",
            "url_count": len(sec_snapshot["issuers"]),
            "retrieved_at_utc": sec_snapshot["retrieved_at_utc"],
            "payload_sha256": capture["sec_financial_snapshot"]["sha256"],
            "parser_version": "FMDL6D_SEC_SELECTED_FACT_V1",
            "no_silent_replacement": True,
            "decision_grade": False,
            "full_raw_payload_retained": False,
        }
    )
    pool = load_json(repo_root / "outputs/fmdl6c/current/FMDL6C_BENCHMARK_POOL.json")
    pool_by_key = {row["security_key"]: row for row in pool["securities"]}
    market_by_key = {row["security_key"]: row for row in market_securities}
    chain_records: list[dict[str, Any]] = []
    for sample in contract["sample_securities"]:
        identity = pool_by_key[sample["security_key"]]
        market_row = market_by_key[sample["security_key"]]
        financial_keys = facts_by_issuer.get(identity["issuer_key"], [])
        chain_records.append(
            {
                "chain_key": f"FMDL6D:{sample['security_key']}",
                "security_key": sample["security_key"],
                "issuer_key": identity["issuer_key"],
                "share_class_key": identity["share_class_key"],
                "listing_observation_key": identity["listing_observation_key"],
                "ticker": identity["ticker"],
                "mic": identity["mic"],
                "instrument_type": identity["instrument_type"],
                "reporting_profile": identity["reporting_profile"],
                "market_series_key": market_row["series_key"],
                "financial_fact_keys": financial_keys,
                "financial_sample_status": "IN_MINIMAL_SAMPLE" if financial_keys else "NOT_IN_MINIMAL_FINANCIAL_SAMPLE",
                "fx_pairs": contract["source_routes"]["fx"]["derived_pairs"],
                "availability_policy": "CONSERVATIVE_RETRIEVAL_BOUND_NO_LOOKAHEAD_CLAIM",
                "benchmark_only": True,
                "investment_eligible": False,
                "research_candidate": False,
                "trade_authority": "NONE",
            }
        )
    chain_store = {
        "program_id": PROGRAM_ID,
        "record_count": len(chain_records),
        "records": chain_records,
        "trade_authority": "NONE",
    }
    availability = {
        "program_id": PROGRAM_ID,
        "captured_at_utc": captured_at,
        "policy": "CONSERVATIVE_RETRIEVAL_BOUND_NO_HISTORICAL_AS_OF_CLAIM",
        "market": {
            "field_set": ["trade_date", "available_from_utc", "availability_basis", "point_in_time_status"],
            "availability_from": captured_at,
            "historical_revision_guarantee": False,
        },
        "corporate_actions": {
            "field_set": ["event_date", "available_from_utc", "availability_basis", "point_in_time_status"],
            "availability_from": captured_at,
            "historical_revision_guarantee": False,
        },
        "fx": {
            "field_set": ["reference_date", "available_from_utc", "availability_basis", "point_in_time_status"],
            "availability_from": captured_at,
            "official_series": True,
        },
        "financial_facts": {
            "field_set": ["report_period_end", "filing_accession", "filing_form", "available_from_utc", "availability_basis", "point_in_time_status"],
            "availability_from": sec_snapshot["retrieved_at_utc"],
            "filing_acceptance_timestamp_complete": False,
        },
        "lookahead_claim_authorized": False,
        "trade_authority": "NONE",
    }
    source_registry_doc = {
        "program_id": PROGRAM_ID,
        "source_count": len(source_registry),
        "sources": source_registry,
        "trade_authority": "NONE",
    }
    canonical_payload = {
        "program_id": PROGRAM_ID,
        "contract_sha256": sha256_file(contract_path),
        "capture_sha256": sha256_file(capture_path),
        "market_store": market_store,
        "fx_store": fx_store,
        "financial_store": financial_store,
        "chain_store": chain_store,
        "availability": availability,
        "source_registry": source_registry_doc,
        "controlled_limitations": contract["controlled_limitations"],
    }
    canonical_sha = sha256_bytes(stable_json(canonical_payload).encode("utf-8"))
    release_id = f"FMDL6D_{capture['as_of_date'].replace('-', '')}_{canonical_sha[:12]}"
    decision = {
        "program_id": PROGRAM_ID,
        "release_id": release_id,
        "status": contract["exit_status"],
        "hard_failures": [],
        "market_security_count": len(market_securities),
        "market_daily_observation_count": total_daily,
        "corporate_action_count": total_events,
        "fx_pair_count": len(fx_series),
        "fx_observation_count": sum(row["observation_count"] for row in fx_series),
        "financial_sample_issuer_count": len(issuer_records),
        "financial_fact_count": len(facts),
        "chain_record_count": len(chain_records),
        "point_in_time_posture": availability["policy"],
        "decision_grade_market_data_authorized": False,
        "production_financial_normalization_authorized": False,
        "candidate_pool_mutation_count": 0,
        "simulation_mutation_count": 0,
        "real_account_mutation_count": 0,
        "order_generation_count": 0,
        "trade_authority": "NONE",
        "next_gate": contract["next_gate"],
    }
    validation_checks = contract_checks + capture_checks
    validation = {
        "program_id": PROGRAM_ID,
        "release_id": release_id,
        "validation": "PASS",
        "check_count": len(validation_checks),
        "pass_count": sum(row["status"] == "PASS" for row in validation_checks),
        "error_count": 0,
        "errors": [],
        "checks": validation_checks,
        "trade_authority": "NONE",
    }
    release = {
        "program_id": PROGRAM_ID,
        "program_name": contract["program_name"],
        "release_id": release_id,
        "release_sequence": contract["publication"]["release_sequence"],
        "as_of_date": capture["as_of_date"],
        "captured_at_utc": captured_at,
        "status": contract["exit_status"],
        "authority": contract["authority"],
        "scope_mode": contract["scope"]["mode"],
        "canonical_sha256": canonical_sha,
        "contract_sha256": sha256_file(contract_path),
        "capture_sha256": sha256_file(capture_path),
        "upstream_fmdl6b_release_id": capture["upstream"]["fmdl6b"]["release_id"],
        "upstream_fmdl6c_release_id": capture["upstream"]["fmdl6c"]["release_id"],
        "market_security_count": len(market_securities),
        "financial_sample_issuer_count": len(issuer_records),
        "chain_record_count": len(chain_records),
        "small_sample_not_full_universe": True,
        "decision_grade_market_data_authorized": False,
        "candidate_pool_integration_authorized": False,
        "simulation_integration_authorized": False,
        "real_account_integration_authorized": False,
        "order_generation_authorized": False,
        "trade_authority": "NONE",
        "controlled_limitations": contract["controlled_limitations"],
        "next_gate": contract["next_gate"],
    }
    documents = {
        "FMDL6D_MARKET_STORE.json": market_store,
        "FMDL6D_FX_STORE.json": fx_store,
        "FMDL6D_FINANCIAL_FACT_SAMPLE.json": financial_store,
        "FMDL6D_CHAIN_RECORDS.json": chain_store,
        "FMDL6D_AVAILABILITY.json": availability,
        "FMDL6D_SOURCE_REGISTRY.json": source_registry_doc,
        "FMDL6D_DECISION.json": decision,
        "FMDL6D_VALIDATION.json": validation,
        "FMDL6D_RELEASE.json": release,
    }
    for name, document in documents.items():
        write_json(candidate_dir / name, document)
    manifest_files = {
        name: {"sha256": sha256_file(candidate_dir / name), "size_bytes": (candidate_dir / name).stat().st_size}
        for name in sorted(documents)
    }
    manifest = {
        "program_id": PROGRAM_ID,
        "release_id": release_id,
        "release_sequence": contract["publication"]["release_sequence"],
        "canonical_sha256": canonical_sha,
        "contract_sha256": sha256_file(contract_path),
        "capture_sha256": sha256_file(capture_path),
        "sec_snapshot_sha256": capture["sec_financial_snapshot"]["sha256"],
        "files": manifest_files,
        "trade_authority": "NONE",
    }
    write_json(candidate_dir / "FMDL6D_MANIFEST.json", manifest)
    return release



def validate_candidate_content(contract: dict[str, Any], capture_path: Path, candidate_dir: Path) -> list[str]:
    errors: list[str] = []
    gates = contract["acceptance_gates"]
    required_names = {
        "FMDL6D_MARKET_STORE.json",
        "FMDL6D_FX_STORE.json",
        "FMDL6D_FINANCIAL_FACT_SAMPLE.json",
        "FMDL6D_CHAIN_RECORDS.json",
        "FMDL6D_AVAILABILITY.json",
        "FMDL6D_SOURCE_REGISTRY.json",
        "FMDL6D_DECISION.json",
        "FMDL6D_VALIDATION.json",
        "FMDL6D_RELEASE.json",
    }
    manifest = load_json(candidate_dir / "FMDL6D_MANIFEST.json")
    if set(manifest.get("files") or {}) != required_names:
        errors.append("MANIFEST_FILE_SET")
    if manifest.get("capture_sha256") != sha256_file(capture_path):
        errors.append("CAPTURE_HASH")
    market = load_json(candidate_dir / "FMDL6D_MARKET_STORE.json")
    if market.get("security_count") != gates["market_security_count"]:
        errors.append("MARKET_SECURITY_COUNT")
    securities = market.get("securities") or []
    if len({row.get("security_key") for row in securities}) != len(securities):
        errors.append("MARKET_SECURITY_DUPLICATE")
    total_daily = 0
    total_events = 0
    for security in securities:
        observations = security.get("observations") or []
        events = security.get("corporate_actions") or []
        total_daily += len(observations)
        total_events += len(events)
        if len(observations) < gates["minimum_daily_observations_per_security"]:
            errors.append(f"MARKET_OBSERVATION_COUNT:{security.get('ticker')}")
        dates = [row.get("trade_date") for row in observations]
        if dates != sorted(dates) or len(dates) != len(set(dates)):
            errors.append(f"MARKET_DATES:{security.get('ticker')}")
        if not all(row.get("available_from_utc") and row.get("availability_basis") and row.get("point_in_time_status") for row in observations):
            errors.append(f"MARKET_AVAILABILITY:{security.get('ticker')}")
        if not all(row.get("available_from_utc") and row.get("availability_basis") and row.get("point_in_time_status") for row in events):
            errors.append(f"EVENT_AVAILABILITY:{security.get('ticker')}")
        if security.get("benchmark_only") is not True or security.get("investment_eligible") is not False or security.get("trade_authority") != "NONE":
            errors.append(f"MARKET_AUTHORITY:{security.get('ticker')}")
        if not str(security.get("source_url", "")).startswith("https://query") or len(str(security.get("source_payload_sha256", ""))) != 64:
            errors.append(f"MARKET_LINEAGE:{security.get('ticker')}")
    if total_daily != market.get("total_daily_observations") or total_daily < gates["minimum_total_daily_observations"]:
        errors.append("MARKET_TOTAL")
    if total_events != market.get("total_corporate_actions"):
        errors.append("EVENT_TOTAL")

    fx = load_json(candidate_dir / "FMDL6D_FX_STORE.json")
    fx_series = fx.get("series") or []
    if {row.get("pair") for row in fx_series} != set(contract["source_routes"]["fx"]["derived_pairs"]):
        errors.append("FX_PAIR_SET")
    for series in fx_series:
        observations = series.get("observations") or []
        if len(observations) < gates["minimum_fx_observations_per_pair"]:
            errors.append(f"FX_OBSERVATION_COUNT:{series.get('pair')}")
        if not all(float(row.get("rate", 0)) > 0 and row.get("available_from_utc") and row.get("availability_basis") and row.get("point_in_time_status") for row in observations):
            errors.append(f"FX_AVAILABILITY_OR_RATE:{series.get('pair')}")
    if fx.get("source_authority") != "ECB_OFFICIAL" or fx.get("trade_authority") != "NONE":
        errors.append("FX_AUTHORITY")

    financial = load_json(candidate_dir / "FMDL6D_FINANCIAL_FACT_SAMPLE.json")
    if financial.get("issuer_count") != gates["financial_sample_issuer_count"]:
        errors.append("FINANCIAL_ISSUER_COUNT")
    facts = financial.get("facts") or []
    if len(facts) != financial.get("fact_count") or len(facts) < gates["minimum_financial_fact_count"]:
        errors.append("FINANCIAL_FACT_COUNT")
    issuer_fact_counts: dict[str, int] = defaultdict(int)
    for fact in facts:
        issuer_fact_counts[str(fact.get("issuer_key"))] += 1
        if not str(fact.get("official_filing_url", "")).startswith("https://www.sec.gov/Archives/edgar/data/"):
            errors.append(f"FINANCIAL_URL:{fact.get('fact_key')}")
        if not fact.get("available_from_utc") or not fact.get("availability_basis") or not fact.get("point_in_time_status"):
            errors.append(f"FINANCIAL_AVAILABILITY:{fact.get('fact_key')}")
        if fact.get("decision_grade") is not False:
            errors.append(f"FINANCIAL_DECISION_GRADE:{fact.get('fact_key')}")
    if any(count < gates["minimum_financial_facts_per_issuer"] for count in issuer_fact_counts.values()) or len(issuer_fact_counts) != gates["financial_sample_issuer_count"]:
        errors.append("FINANCIAL_MIN_PER_ISSUER")
    if financial.get("full_raw_payload_retained") is not False or financial.get("trade_authority") != "NONE":
        errors.append("FINANCIAL_AUTHORITY")

    chains = load_json(candidate_dir / "FMDL6D_CHAIN_RECORDS.json")
    records = chains.get("records") or []
    if chains.get("record_count") != gates["market_security_count"] or len(records) != gates["market_security_count"]:
        errors.append("CHAIN_RECORD_COUNT")
    expected_security_keys = {row["security_key"] for row in contract["sample_securities"]}
    if {row.get("security_key") for row in records} != expected_security_keys:
        errors.append("CHAIN_SECURITY_SET")
    market_series_keys = {row.get("series_key") for row in securities}
    financial_fact_keys = {row.get("fact_key") for row in facts}
    for record in records:
        if record.get("market_series_key") not in market_series_keys:
            errors.append(f"CHAIN_MARKET_LINK:{record.get('ticker')}")
        if not set(record.get("financial_fact_keys") or []).issubset(financial_fact_keys):
            errors.append(f"CHAIN_FINANCIAL_LINK:{record.get('ticker')}")
        if record.get("benchmark_only") is not True or record.get("investment_eligible") is not False or record.get("research_candidate") is not False or record.get("trade_authority") != "NONE":
            errors.append(f"CHAIN_AUTHORITY:{record.get('ticker')}")

    availability = load_json(candidate_dir / "FMDL6D_AVAILABILITY.json")
    if availability.get("lookahead_claim_authorized") is not False or availability.get("trade_authority") != "NONE":
        errors.append("AVAILABILITY_AUTHORITY")
    sources = load_json(candidate_dir / "FMDL6D_SOURCE_REGISTRY.json")
    source_rows = sources.get("sources") or []
    if sources.get("source_count") != 12 or len(source_rows) != 12:
        errors.append("SOURCE_COUNT")
    for source in source_rows:
        if len(str(source.get("payload_sha256", ""))) != 64 or source.get("no_silent_replacement") is not True or source.get("decision_grade") is not False:
            errors.append(f"SOURCE_LINEAGE:{source.get('source_id')}")

    decision = load_json(candidate_dir / "FMDL6D_DECISION.json")
    if decision.get("market_daily_observation_count") != total_daily or decision.get("corporate_action_count") != total_events or decision.get("financial_fact_count") != len(facts):
        errors.append("DECISION_COUNTS")
    if any(decision.get(key) != 0 for key in ("candidate_pool_mutation_count", "simulation_mutation_count", "real_account_mutation_count", "order_generation_count")):
        errors.append("DECISION_MUTATION")
    release = load_json(candidate_dir / "FMDL6D_RELEASE.json")
    if any(release.get(key) is not False for key in ("decision_grade_market_data_authorized", "candidate_pool_integration_authorized", "simulation_integration_authorized", "real_account_integration_authorized", "order_generation_authorized")):
        errors.append("RELEASE_AUTHORITY")
    canonical_payload = {
        "program_id": PROGRAM_ID,
        "contract_sha256": release.get("contract_sha256"),
        "capture_sha256": release.get("capture_sha256"),
        "market_store": market,
        "fx_store": fx,
        "financial_store": financial,
        "chain_store": chains,
        "availability": availability,
        "source_registry": sources,
        "controlled_limitations": contract["controlled_limitations"],
    }
    canonical_sha = sha256_bytes(stable_json(canonical_payload).encode("utf-8"))
    if canonical_sha != release.get("canonical_sha256") or canonical_sha != manifest.get("canonical_sha256"):
        errors.append("CANONICAL_RECOMPUTE")
    expected_release_id = f"FMDL6D_{release.get('as_of_date', '').replace('-', '')}_{canonical_sha[:12]}"
    if release.get("release_id") != expected_release_id or manifest.get("release_id") != expected_release_id:
        errors.append("RELEASE_ID")
    return errors


def validate_candidate(repo_root: Path, contract_path: Path, capture_path: Path, candidate_dir: Path, acceptance_path: Path) -> dict[str, Any]:
    contract = load_json(contract_path)
    manifest = load_json(candidate_dir / "FMDL6D_MANIFEST.json")
    errors: list[str] = []
    errors.extend(validate_candidate_content(contract, capture_path, candidate_dir))
    for name, metadata in manifest["files"].items():
        path = candidate_dir / name
        if not path.exists():
            errors.append(f"MISSING_FILE:{name}")
        elif sha256_file(path) != metadata["sha256"]:
            errors.append(f"HASH_MISMATCH:{name}")
    release = load_json(candidate_dir / "FMDL6D_RELEASE.json")
    decision = load_json(candidate_dir / "FMDL6D_DECISION.json")
    validation = load_json(candidate_dir / "FMDL6D_VALIDATION.json")
    if release.get("status") != contract["exit_status"]:
        errors.append("RELEASE_STATUS")
    if decision.get("hard_failures"):
        errors.append("DECISION_HARD_FAILURES")
    if validation.get("validation") != "PASS" or validation.get("error_count") != 0:
        errors.append("VALIDATION_NOT_PASS")
    if release.get("canonical_sha256") != manifest.get("canonical_sha256"):
        errors.append("CANONICAL_HASH_MISMATCH")
    if release.get("trade_authority") != "NONE" or decision.get("trade_authority") != "NONE":
        errors.append("TRADE_AUTHORITY")
    if decision.get("candidate_pool_mutation_count") != 0 or decision.get("simulation_mutation_count") != 0 or decision.get("real_account_mutation_count") != 0 or decision.get("order_generation_count") != 0:
        errors.append("STATE_MUTATION")
    with tempfile.TemporaryDirectory(prefix="fmdl6d-replay-") as tmp:
        replay_dir = Path(tmp) / "candidate"
        replay_release = build_candidate(repo_root, contract_path, capture_path, replay_dir)
        replay_manifest = load_json(replay_dir / "FMDL6D_MANIFEST.json")
        same_input_replay = replay_release["canonical_sha256"] == release["canonical_sha256"] and replay_manifest["files"] == manifest["files"]
    if not same_input_replay:
        errors.append("SAME_INPUT_REPLAY")
    acceptance = {
        "program_id": PROGRAM_ID,
        "release_id": release["release_id"],
        "validation": "PASS" if not errors else "FAIL",
        "same_input_replay": "PASS" if same_input_replay else "FAIL",
        "manifest_file_count": len(manifest["files"]),
        "errors": errors,
        "trade_authority": "NONE",
    }
    write_json(acceptance_path, acceptance)
    if errors:
        raise ValueError(f"independent validation failed: {errors}")
    return acceptance


def _copy_tree_verified(source: Path, target: Path) -> None:
    if target.exists():
        source_manifest = load_json(source / "FMDL6D_MANIFEST.json")
        target_manifest_path = target / "FMDL6D_MANIFEST.json"
        if target_manifest_path.exists() and load_json(target_manifest_path) == source_manifest:
            return
        raise FileExistsError(f"target exists with different content: {target}")
    shutil.copytree(source, target)


def publish_candidate(repo_root: Path, contract_path: Path, candidate_dir: Path) -> dict[str, Any]:
    contract = load_json(contract_path)
    release = load_json(candidate_dir / "FMDL6D_RELEASE.json")
    manifest = load_json(candidate_dir / "FMDL6D_MANIFEST.json")
    if release.get("status") != contract["exit_status"] or release.get("trade_authority") != "NONE":
        raise ValueError("candidate is not publishable")
    current_path = repo_root / contract["publication"]["current_path"]
    archive_path = repo_root / contract["publication"]["archive_root"] / release["release_id"]
    immutable_path = repo_root / contract["publication"]["immutable_root"] / release["release_id"]
    if current_path.exists():
        shutil.rmtree(current_path)
    shutil.copytree(candidate_dir, current_path)
    _copy_tree_verified(candidate_dir, archive_path)
    _copy_tree_verified(candidate_dir, immutable_path)
    last_success = {
        "program_id": PROGRAM_ID,
        "release_id": release["release_id"],
        "release_sequence": release["release_sequence"],
        "status": release["status"],
        "canonical_sha256": release["canonical_sha256"],
        "contract_sha256": release["contract_sha256"],
        "capture_sha256": release["capture_sha256"],
        "sec_snapshot_sha256": manifest["sec_snapshot_sha256"],
        "current_path": contract["publication"]["current_path"],
        "archive_path": str(archive_path.relative_to(repo_root)),
        "immutable_path": str(immutable_path.relative_to(repo_root)),
        "market_security_count": release["market_security_count"],
        "financial_sample_issuer_count": release["financial_sample_issuer_count"],
        "chain_record_count": release["chain_record_count"],
        "small_sample_not_full_universe": True,
        "decision_grade_market_data_authorized": False,
        "next_gate": release["next_gate"],
        "trade_authority": "NONE",
    }
    write_json(repo_root / contract["publication"]["last_success_path"], last_success)
    return last_success


def command_fetch(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    contract_path = (repo_root / args.contract).resolve()
    capture_path = (repo_root / args.capture).resolve()
    capture = capture_inputs(repo_root, contract_path, capture_path)
    print(json.dumps({"captured_at_utc": capture["captured_at_utc"], "market_count": len(capture["market"]), "fx_pairs": {k: len(v) for k, v in capture["fx_pairs"].items()}}, sort_keys=True))
    return 0


def command_build(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    release = build_candidate(repo_root, (repo_root / args.contract).resolve(), (repo_root / args.capture).resolve(), (repo_root / args.candidate).resolve())
    print(json.dumps(release, sort_keys=True))
    return 0


def command_validate(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    acceptance = validate_candidate(repo_root, (repo_root / args.contract).resolve(), (repo_root / args.capture).resolve(), (repo_root / args.candidate).resolve(), (repo_root / args.acceptance).resolve())
    print(json.dumps(acceptance, sort_keys=True))
    return 0


def command_publish(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    last_success = publish_candidate(repo_root, (repo_root / args.contract).resolve(), (repo_root / args.candidate).resolve())
    print(json.dumps(last_success, sort_keys=True))
    return 0


def command_contract(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    checks, errors = validate_contract(repo_root, (repo_root / args.contract).resolve())
    print(json.dumps({"check_count": len(checks), "errors": errors}, sort_keys=True))
    return 1 if errors else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="FMDL-6D minimal end-to-end data chain")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, handler in (("contract", command_contract), ("fetch", command_fetch), ("build", command_build), ("validate", command_validate), ("publish", command_publish)):
        current = sub.add_parser(name)
        current.add_argument("--repo-root", default=".")
        current.add_argument("--contract", default=DEFAULT_CONTRACT)
        if name in {"fetch", "build", "validate"}:
            current.add_argument("--capture", default=DEFAULT_CAPTURE)
        if name in {"build", "validate", "publish"}:
            current.add_argument("--candidate", default=DEFAULT_CANDIDATE)
        if name == "validate":
            current.add_argument("--acceptance", default=DEFAULT_ACCEPTANCE)
        current.set_defaults(handler=handler)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
