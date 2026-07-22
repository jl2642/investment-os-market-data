from __future__ import annotations

import json
import math
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from fmdl6x2d_common import (
    bucket_hex, deterministic_zip, load_json, parse_ecb_csv, read_zip_jsonl,
    sha256_bytes, stable_json,
)

IDENTITY_ROOT = Path('outputs/fmdl6x2/current/identity')


def load_security_universe(repo_root: Path) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    root = repo_root / IDENTITY_ROOT
    securities = read_zip_jsonl(root / 'FMDL6X2B_IDENTITY_SHARDS.zip', 'SECURITY/')
    listings = read_zip_jsonl(root / 'FMDL6X2B_IDENTITY_SHARDS.zip', 'LISTING/')
    by_sec: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in listings:
        by_sec[row['canonical_security_id']].append(row)
    return securities, by_sec


def select_cohort(securities: list[dict[str, Any]], listings: dict[str, list[dict[str, Any]]], contract: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    eligible = [s for s in securities if not s.get('test_issue') and s.get('research_status') in {'RESEARCH_REVIEW_REQUIRED','RESEARCH_ELIGIBLE_SPECIAL_PROFILE','REFERENCE_ONLY'}]
    eligible.sort(key=lambda s: s['canonical_security_id'])
    selected: dict[str, dict[str, Any]] = {}
    mandatory = set(contract['market_contract']['mandatory_symbols'])
    for sec in eligible:
        sec_listings = sorted(listings.get(sec['canonical_security_id'], []), key=lambda x: ({'XNAS':0,'XNYS':1,'XASE':2}.get(x.get('venue'),9), x.get('symbol','')))
        symbols = {x.get('symbol') for x in sec_listings}
        if mandatory & symbols:
            listing = sec_listings[0]
            selected[sec['canonical_security_id']] = _cohort_row(sec, listing, 'MANDATORY_SENTINEL')
    bucket_count = int(contract['storage_contract']['bucket_count'])
    for bucket in range(bucket_count):
        if len(selected) >= int(contract['acceptance_gates']['cohort_size']):
            break
        bid = f'{bucket:02X}'
        candidates = [s for s in eligible if s['canonical_security_id'] not in selected and bucket_hex(s['canonical_security_id'], bucket_count) == bid]
        if candidates:
            sec = candidates[0]
            listing = sorted(listings[sec['canonical_security_id']], key=lambda x: ({'XNAS':0,'XNYS':1,'XASE':2}.get(x.get('venue'),9), x.get('symbol','')))[0]
            selected[sec['canonical_security_id']] = _cohort_row(sec, listing, 'SHA256_BUCKET_REPRESENTATIVE')
    if len(selected) < int(contract['acceptance_gates']['cohort_size']):
        for sec in eligible:
            if sec['canonical_security_id'] in selected:
                continue
            listing = sorted(listings[sec['canonical_security_id']], key=lambda x: ({'XNAS':0,'XNYS':1,'XASE':2}.get(x.get('venue'),9), x.get('symbol','')))[0]
            selected[sec['canonical_security_id']] = _cohort_row(sec, listing, 'DETERMINISTIC_FILL')
            if len(selected) >= int(contract['acceptance_gates']['cohort_size']):
                break
    cohort = sorted(selected.values(), key=lambda x: x['canonical_security_id'])
    queued = []
    selected_ids = set(selected)
    for sec in securities:
        if sec['canonical_security_id'] in selected_ids:
            continue
        queued.append({'canonical_security_id': sec['canonical_security_id'], 'instrument_type': sec.get('instrument_type'), 'research_status': sec.get('research_status'), 'symbols': sec.get('symbols',[]), 'venues': sec.get('venues',[]), 'backfill_status': 'QUEUED_NOT_FETCHED_CURRENT_RUNTIME_BUDGET', 'market_data_grade': 'NOT_AVAILABLE'})
    queued.sort(key=lambda x: x['canonical_security_id'])
    return cohort, queued


def _cohort_row(sec: dict[str, Any], listing: dict[str, Any], reason: str) -> dict[str, Any]:
    return {'canonical_security_id': sec['canonical_security_id'], 'canonical_issuer_id': sec.get('canonical_issuer_id'), 'selected_listing_id': listing['canonical_listing_id'], 'selected_symbol': listing['symbol'], 'venue': listing['venue'], 'instrument_type': sec.get('instrument_type'), 'research_status': sec.get('research_status'), 'selection_reason': reason}


def _read_raw(raw_root: Path) -> tuple[dict[str, bytes], dict[str, Any]]:
    entries: dict[str, bytes] = {}
    with zipfile.ZipFile(raw_root / 'FMDL6X2D_RAW_PAYLOADS.zip') as archive:
        for name in archive.namelist():
            entries[name] = archive.read(name)
    return entries, load_json(raw_root / 'FMDL6X2D_ROUTE_OBSERVATIONS.json')


def parse_yahoo(payload: bytes, security_id: str, route_id: str) -> dict[str, Any]:
    data = json.loads(payload.decode('utf-8'))
    chart = data.get('chart', {})
    if chart.get('error') or not chart.get('result'):
        raise ValueError('YAHOO_CHART_ERROR')
    result = chart['result'][0]
    meta = result.get('meta', {})
    tz_name = meta.get('exchangeTimezoneName') or 'UTC'
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = timezone.utc
        tz_name = 'UTC_FALLBACK'
    timestamps = result.get('timestamp') or []
    quote = ((result.get('indicators') or {}).get('quote') or [{}])[0]
    bars: list[dict[str, Any]] = []
    for i, ts in enumerate(timestamps):
        vals = {k: (quote.get(k) or [None] * len(timestamps))[i] if i < len(quote.get(k) or []) else None for k in ('open','high','low','close','volume')}
        if all(vals[k] is None for k in ('open','high','low','close')):
            continue
        date = datetime.fromtimestamp(int(ts), tz=timezone.utc).astimezone(tz).date().isoformat()
        bars.append({'canonical_security_id': security_id, 'date': date, 'open': vals['open'], 'high': vals['high'], 'low': vals['low'], 'close': vals['close'], 'volume': vals['volume'], 'currency': meta.get('currency'), 'exchange_timezone': tz_name, 'market_data_grade': 'NON_DECISION_GRADE_FALLBACK', 'source_authority': 'YAHOO_FREE_UNOFFICIAL'})
    events: list[dict[str, Any]] = []
    raw_events = result.get('events') or {}
    for key, item in sorted((raw_events.get('dividends') or {}).items()):
        date = datetime.fromtimestamp(int(item.get('date', key)), tz=timezone.utc).astimezone(tz).date().isoformat()
        events.append({'canonical_security_id': security_id, 'event_type':'DIVIDEND', 'event_date':date, 'amount':item.get('amount'), 'currency':meta.get('currency'), 'market_data_grade':'NON_DECISION_GRADE_FALLBACK','source_authority':'YAHOO_FREE_UNOFFICIAL'})
    for key, item in sorted((raw_events.get('splits') or {}).items()):
        date = datetime.fromtimestamp(int(item.get('date', key)), tz=timezone.utc).astimezone(tz).date().isoformat()
        events.append({'canonical_security_id': security_id, 'event_type':'SPLIT', 'event_date':date, 'numerator':item.get('numerator'), 'denominator':item.get('denominator'), 'split_ratio':item.get('splitRatio'), 'market_data_grade':'NON_DECISION_GRADE_FALLBACK','source_authority':'YAHOO_FREE_UNOFFICIAL'})
    bars.sort(key=lambda x: x['date'])
    events.sort(key=lambda x: (x['event_date'], x['event_type'], stable_json(x)))
    return {'route_id': route_id, 'bars': bars, 'events': events, 'meta': {'currency': meta.get('currency'), 'symbol': meta.get('symbol'), 'exchange_timezone': tz_name}}


def _norm(value: Any) -> Any:
    if isinstance(value, float):
        if math.isnan(value):
            return None
        return round(value, 10)
    if isinstance(value, dict):
        return {k: _norm(v) for k,v in value.items() if k != 'route_id'}
    if isinstance(value, list):
        return [_norm(v) for v in value]
    return value


def reconcile_market(cohort: list[dict[str, Any]], entries: dict[str, bytes], route_obs: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    obs_map = {(o.get('canonical_security_id'), o['route_id']): o for o in route_obs['route_observations']}
    bars: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    accepted: list[dict[str, Any]] = []
    quarantine: list[dict[str, Any]] = []
    for row in cohort:
        sec = row['canonical_security_id']
        routes = {}
        failure = None
        for route in ('YAHOO_QUERY1_CHART','YAHOO_QUERY2_CHART'):
            obs = obs_map.get((sec, route), {})
            key = f'market/{sec}/{route}.json'
            if not obs.get('success') or not entries.get(key):
                failure = 'DUAL_ROUTE_MISSING_OR_FAILED'
                break
            try:
                routes[route] = parse_yahoo(entries[key], sec, route)
            except Exception as exc:
                failure = 'PARSE_FAILURE:' + type(exc).__name__
                break
        if failure is None and _norm(routes['YAHOO_QUERY1_CHART']) != _norm(routes['YAHOO_QUERY2_CHART']):
            failure = 'DUAL_ROUTE_NORMALIZED_DIVERGENCE'
        if failure:
            quarantine.append({**row, 'market_status':'QUARANTINED', 'reason':failure})
            continue
        result = routes['YAHOO_QUERY1_CHART']
        if not result['bars']:
            quarantine.append({**row, 'market_status':'QUARANTINED', 'reason':'NO_DAILY_BARS'})
            continue
        bars.extend(result['bars'])
        events.extend(result['events'])
        accepted.append({**row, 'market_status':'ACCEPTED_NON_DECISION_GRADE', 'bar_count':len(result['bars']), 'event_count':len(result['events']), 'first_date':result['bars'][0]['date'], 'last_date':result['bars'][-1]['date'], 'currency':result['meta']['currency']})
    bars.sort(key=lambda x: (x['canonical_security_id'], x['date']))
    events.sort(key=lambda x: (x['canonical_security_id'], x['event_date'], x['event_type']))
    accepted.sort(key=lambda x: x['canonical_security_id'])
    quarantine.sort(key=lambda x: x['canonical_security_id'])
    return bars, events, accepted, quarantine


def build_fx(entries: dict[str, bytes]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    def series_rows(series: str) -> dict[str, float]:
        combined: dict[str, float] = {}
        prefix = f'fx/ECB_{series}/'
        for name in sorted(entries):
            if name.startswith(prefix) and name.endswith('.csv'):
                combined.update(parse_ecb_csv(entries[name]))
        return combined
    usd = series_rows('USD_EUR')
    cny = series_rows('CNY_EUR')
    hkd = series_rows('HKD_EUR')
    dates = sorted(set(usd) & set(cny) & set(hkd))
    rows: list[dict[str, Any]] = []
    for date in dates:
        if usd[date] == 0:
            continue
        rows.append({'pair':'USD_CNY','date':date,'rate':round(cny[date]/usd[date],10),'source_authority':'ECB_OFFICIAL','derivation':'CNY_PER_EUR_DIVIDED_BY_USD_PER_EUR','input_series':['D.CNY.EUR.SP00.A','D.USD.EUR.SP00.A'],'data_grade':'DECISION_GRADE_REFERENCE_OFFICIAL'})
        rows.append({'pair':'USD_HKD','date':date,'rate':round(hkd[date]/usd[date],10),'source_authority':'ECB_OFFICIAL','derivation':'HKD_PER_EUR_DIVIDED_BY_USD_PER_EUR','input_series':['D.HKD.EUR.SP00.A','D.USD.EUR.SP00.A'],'data_grade':'DECISION_GRADE_REFERENCE_OFFICIAL'})
    support = {'route_present': bool(entries.get('fx/FRANKFURTER_USD_CNY_HKD.json')), 'status':'SUPPORT_ONLY_NOT_USED_FOR_HISTORY'}
    try:
        support['payload'] = json.loads(entries['fx/FRANKFURTER_USD_CNY_HKD.json'].decode('utf-8'))
    except Exception:
        support['payload'] = None
    return rows, support


def _jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    return ''.join(stable_json(row) + '\n' for row in rows).encode('utf-8')


def build_shards(bars: list[dict[str, Any]], events: list[dict[str, Any]], fx: list[dict[str, Any]], bucket_count: int, accepted_at: str) -> tuple[bytes, bytes, list[dict[str, Any]]]:
    market_entries: dict[str, bytes] = {}
    fx_entries: dict[str, bytes] = {}
    manifest: list[dict[str, Any]] = []
    years = list(range(2010, 2027))
    for domain, rows, date_field in [('DAILY_OHLCV', bars, 'date'), ('CORPORATE_ACTION', events, 'event_date')]:
        for year in years:
            yr = str(year)
            year_rows = [r for r in rows if r[date_field].startswith(yr)]
            for bucket in range(bucket_count):
                bid = f'{bucket:02X}'
                shard = [r for r in year_rows if bucket_hex(r['canonical_security_id'], bucket_count) == bid]
                shard.sort(key=lambda r: (r['canonical_security_id'], r[date_field], stable_json(r)))
                name = f'{domain}/{yr}/{bid}.jsonl'
                payload = _jsonl_bytes(shard)
                market_entries[name] = payload
                manifest.append({'domain':domain,'shard_id':f'{domain}-{yr}-{bid}','year':year,'bucket':bid,'row_count':len(shard),'payload_sha256':sha256_bytes(payload),'generated_at':accepted_at,'quality_status':'PASS','schema_version':'fmdl6x2d.market.v1'})
    calendar_dates = sorted({r['date'] for r in bars})
    for year in years:
        rows = [{'calendar':'US_DERIVED_FROM_ACCEPTED_COHORT','date':d,'source_grade':'DERIVED_NON_DECISION_GRADE'} for d in calendar_dates if d.startswith(str(year))]
        payload = _jsonl_bytes(rows)
        name = f'TRADING_CALENDAR/{year}.jsonl'
        market_entries[name] = payload
        manifest.append({'domain':'TRADING_CALENDAR','shard_id':f'TRADING_CALENDAR-{year}','year':year,'bucket':None,'row_count':len(rows),'payload_sha256':sha256_bytes(payload),'generated_at':accepted_at,'quality_status':'PASS','schema_version':'fmdl6x2d.calendar.v1'})
    for pair in ('USD_CNY','USD_HKD'):
        for year in years:
            rows = [r for r in fx if r['pair'] == pair and r['date'].startswith(str(year))]
            payload = _jsonl_bytes(rows)
            name = f'{pair}/{year}.jsonl'
            fx_entries[name] = payload
            manifest.append({'domain':'FX','shard_id':f'{pair}-{year}','year':year,'bucket':None,'pair':pair,'row_count':len(rows),'payload_sha256':sha256_bytes(payload),'generated_at':accepted_at,'quality_status':'PASS','schema_version':'fmdl6x2d.fx.v1'})
    return deterministic_zip(market_entries), deterministic_zip(fx_entries), manifest
