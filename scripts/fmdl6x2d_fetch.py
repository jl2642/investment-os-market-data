from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from fmdl6x2d_common import sha256_bytes, utc_now, write_json


def make_session(contract: dict[str, Any]) -> requests.Session:
    policy = contract['network_policy']
    retries = max(int(policy['max_attempts']) - 1, 0)
    retry = Retry(total=retries, connect=retries, read=retries, status=retries, backoff_factor=float(policy['backoff_seconds']), status_forcelist=(429,500,502,503,504), allowed_methods=frozenset({'GET'}), raise_on_status=False)
    session = requests.Session()
    session.mount('https://', HTTPAdapter(max_retries=retry, pool_connections=32, pool_maxsize=32))
    session.headers.update({'User-Agent': os.getenv('FMDL_USER_AGENT', 'InvestmentOS-FMDL6X2D/1.0 jl2642@users.noreply.github.com'), 'Accept': 'application/json,text/csv,application/zip,*/*', 'Accept-Encoding': 'gzip, deflate'})
    return session


def yahoo_symbol(symbol: str) -> str:
    return symbol.replace('.', '-').replace('/', '-')


def _capture(session: requests.Session, route_id: str, url: str, timeout: int) -> tuple[dict[str, Any], bytes]:
    started = time.monotonic()
    status = None
    payload = b''
    error = None
    headers: dict[str, str] = {}
    try:
        response = session.get(url, timeout=timeout)
        status = response.status_code
        payload = response.content
        headers = {k.lower(): v for k, v in response.headers.items() if k.lower() in {'content-type','content-length','etag','last-modified','retry-after'}}
    except Exception as exc:  # noqa: BLE001
        error = type(exc).__name__
    prefix = payload[:120].decode('utf-8', errors='ignore').lower()
    success = error is None and status is not None and 200 <= status < 300 and bool(payload) and '<html' not in prefix and '<!doctype html' not in prefix
    return ({'route_id': route_id, 'url': url, 'retrieved_at': utc_now(), 'http_status': status, 'latency_ms': round((time.monotonic()-started)*1000,1), 'bytes': len(payload), 'payload_sha256': sha256_bytes(payload) if payload else None, 'headers': headers, 'success': success, 'error': error}, payload)


def capture_routes(contract: dict[str, Any], cohort: list[dict[str, Any]], raw_root: Path) -> dict[str, Any]:
    raw_root.mkdir(parents=True, exist_ok=True)
    session = make_session(contract)
    timeout = int(contract['network_policy']['timeout_seconds'])
    market = contract['market_contract']
    p1 = int(datetime.fromisoformat(market['backfill_start_date'] + 'T00:00:00+00:00').timestamp())
    p2 = int(datetime.fromisoformat(market['backfill_end_date'] + 'T23:59:59+00:00').timestamp()) + 1
    jobs: list[tuple[str,str,str]] = []
    for row in cohort:
        sec = row['canonical_security_id']
        sym = yahoo_symbol(row['selected_symbol'])
        for route_name, template in [('YAHOO_QUERY1_CHART', market['route_1_template']), ('YAHOO_QUERY2_CHART', market['route_2_template'])]:
            jobs.append((sec, route_name, template.format(symbol=quote(sym, safe='-^='), period1=p1, period2=p2)))
    observations: list[dict[str, Any]] = []
    payload_entries: dict[str, bytes] = {}
    with ThreadPoolExecutor(max_workers=int(contract['network_policy']['max_parallel_requests'])) as pool:
        futures = {pool.submit(_capture, session, route, url, timeout): (sec, route) for sec, route, url in jobs}
        for future in as_completed(futures):
            sec, route = futures[future]
            obs, payload = future.result()
            obs['canonical_security_id'] = sec
            observations.append(obs)
            payload_entries[f'market/{sec}/{route}.json'] = payload
    fx_contract = contract['fx_contract']
    obs, payload = _capture(session, 'ECB_EUROFXREF_HIST_ZIP', fx_contract['ecb_history_zip'], timeout)
    observations.append(obs)
    payload_entries['fx/ECB_EUROFXREF_HIST.zip'] = payload
    obs, payload = _capture(session, 'FRANKFURTER_USD_CNY_HKD', fx_contract['frankfurter_support'], timeout)
    observations.append(obs)
    payload_entries['fx/FRANKFURTER_USD_CNY_HKD.json'] = payload
    observations.sort(key=lambda x: (x.get('canonical_security_id',''), x['route_id']))
    from fmdl6x2d_common import deterministic_zip
    (raw_root / 'FMDL6X2D_RAW_PAYLOADS.zip').write_bytes(deterministic_zip(payload_entries))
    manifest = {'phase_id': 'FMDL-6X2-D', 'captured_at': utc_now(), 'route_observations': observations, 'payload_zip_sha256': sha256_bytes((raw_root / 'FMDL6X2D_RAW_PAYLOADS.zip').read_bytes())}
    write_json(raw_root / 'FMDL6X2D_ROUTE_OBSERVATIONS.json', manifest)
    return manifest
