from __future__ import annotations
import argparse, hashlib, io, json, math, shutil, statistics, zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any

PHASE = 'FMDL-6X3-C'
STATUS = 'FMDL6X3C_FACTOR_VALUATION_QUALITY_AND_RISK_ENGINE_ACCEPTED'
NEXT = 'FMDL-6X3-D_SECTOR_INDUSTRY_PEER_AND_BENCHMARK_FRAMEWORK'
CONTRACT = Path('config/fmdl6x3c_factor_engine_contract.json')
ZTIME = (1980, 1, 1, 0, 0, 0)


def stable(x: Any) -> str:
    return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha_file(p: Path) -> str:
    return sha_bytes(p.read_bytes())


def rh(ns: str, *x: Any) -> str:
    return sha_bytes((ns + '|' + '|'.join(map(str, x))).encode())


def load(p: Path) -> Any:
    return json.loads(p.read_text(encoding='utf-8-sig'))


def write(p: Path, x: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(x, ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf-8')


def bucket(v: str, n: int = 64) -> str:
    return f'{int(hashlib.sha256(v.encode()).hexdigest(), 16) % n:02X}'


def jsonl(rows: list[dict[str, Any]]) -> bytes:
    return ''.join(stable(r) + '\n' for r in rows).encode()


def dzip(entries: dict[str, bytes]) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(entries):
            info = zipfile.ZipInfo(name, ZTIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, entries[name])
    return out.getvalue()


def zrows(p: Path, prefix: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with zipfile.ZipFile(p) as archive:
        for name in sorted(archive.namelist()):
            if name.startswith(prefix) and name.endswith('.jsonl'):
                rows += [json.loads(x) for x in archive.read(name).decode().splitlines() if x.strip()]
    return rows


def validate_contract(root: Path) -> dict[str, Any]:
    contract = load(root / CONTRACT)
    errors: list[str] = []

    def check(name: str, value: bool) -> None:
        if not value:
            errors.append(name)

    check('PHASE', contract.get('phase_id') == PHASE)
    check('STATUS', contract.get('required_exit_status') == STATUS)
    check('NEXT', contract.get('next_gate') == NEXT)
    check('TRADE', contract.get('trade_authority') == 'NONE')
    check('NO_NEUTRAL', contract['factor_contract'].get('neutral_fill_allowed') is False)
    check('NO_GLOBAL_COMPOSITE', contract['factor_contract'].get('global_composite_allowed') is False)
    check('VALUATION_BLOCK', contract['valuation_contract'].get('initial_gate') == 'CLOSED_TTM_AND_ANNUAL_PENDING')
    pointer = root / contract['entry_gate']['pointer_path']
    check('ENTRY_EXISTS', pointer.is_file())
    if pointer.is_file():
        value = load(pointer)
        for field, required in [
            ('phase_id', 'required_phase_id'),
            ('release_id', 'required_release_id'),
            ('release_sequence', 'required_release_sequence'),
            ('status', 'required_status'),
            ('next_gate', 'required_next_gate'),
        ]:
            check('ENTRY_' + field.upper(), value.get(field) == contract['entry_gate'][required])
    if errors:
        raise RuntimeError('CONTRACT:' + ','.join(errors))
    return contract


def load_inputs(root: Path, contract: dict[str, Any]) -> dict[str, Any]:
    readiness = root / contract['input_contract']['readiness_root']
    financial = root / contract['input_contract']['financial_root']
    market = root / contract['input_contract']['market_root']
    return {
        'security_readiness': zrows(readiness / 'FMDL6X3A_READINESS_SHARDS.zip', 'SECURITY_READINESS/'),
        'issuer_readiness': zrows(readiness / 'FMDL6X3A_READINESS_SHARDS.zip', 'ISSUER_READINESS/'),
        'derived_metrics': zrows(financial / 'FMDL6X3B_FINANCIAL_SHARDS.zip', 'DERIVED_METRIC/'),
        'period_readiness': load(financial / 'FMDL6X3B_PERIOD_READINESS.json'),
        'bars': zrows(market / 'FMDL6X2D_MARKET_SHARDS.zip', 'DAILY_OHLCV/'),
        'events': zrows(market / 'FMDL6X2D_MARKET_SHARDS.zip', 'CORPORATE_ACTION/'),
        'manifests': {
            'readiness': readiness / 'FMDL6X3A_MANIFEST.json',
            'financial': financial / 'FMDL6X3B_MANIFEST.json',
            'market': market / 'FMDL6X2D_MANIFEST.json',
        },
    }


def percentile_map(
    rows: list[dict[str, Any]],
    metric_key: str = 'factor_name',
    value_key: str = 'factor_value',
    higher: bool = True,
) -> dict[str, float]:
    groups: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for row in rows:
        value = row.get(value_key)
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            groups[row[metric_key]].append((row['canonical_security_id'], float(value)))
    result: dict[str, float] = {}
    for name, values in groups.items():
        unique = sorted({value for _, value in values})
        if len(unique) == 1:
            for security_id, _ in values:
                result[name + '|' + security_id] = 0.5
        else:
            for security_id, value in values:
                rank = unique.index(value) / (len(unique) - 1)
                result[name + '|' + security_id] = rank if higher else 1 - rank
    return result


def quality_records(inputs: dict[str, Any], contract: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    directions = contract['quality_contract']['metric_direction']
    raw: list[dict[str, Any]] = []
    for source in inputs['derived_metrics']:
        name = source['canonical_metric']
        raw.append({
            'factor_id': 'USFAC-' + rh('QUALITY', source['metric_row_id'])[:24],
            'canonical_security_id': source['canonical_security_id'],
            'canonical_issuer_id': source['canonical_issuer_id'],
            'symbol': source['symbol'],
            'factor_domain': 'QUALITY',
            'factor_name': name,
            'factor_value': source['value'],
            'unit': source['unit'],
            'period_id': source['period_id'],
            'period_end': source['end_date'],
            'fiscal_year': source['fiscal_year'],
            'fiscal_period': source['fiscal_period'],
            'direction': directions.get(name, 'DESCRIPTIVE_ONLY'),
            'cross_section_percentile': None,
            'source_metric_row_id': source['metric_row_id'],
            'evidence_label': source['evidence_label'],
            'data_grade': 'DECISION_GRADE_OFFICIAL_SEC_DERIVED',
            'factor_usage': 'QUARTERLY_QUALITY_SANDBOX_ONLY',
            'sector_neutral': False,
            'neutral_fill_used': False,
        })
    components = contract['quality_contract']['sandbox_score_components']
    scoring = [row for row in raw if row['factor_name'] in components]
    for name in components:
        subset = [row for row in scoring if row['factor_name'] == name]
        ranks = percentile_map(subset, higher=directions[name] == 'HIGHER_BETTER')
        for row in subset:
            row['cross_section_percentile'] = ranks[name + '|' + row['canonical_security_id']]
    by_security: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in scoring:
        if row['cross_section_percentile'] is not None:
            by_security[row['canonical_security_id']].append(row)
    composites: list[dict[str, Any]] = []
    for security_id, rows in sorted(by_security.items()):
        template = rows[0]
        score = sum(row['cross_section_percentile'] for row in rows) / len(rows)
        composites.append({
            'factor_id': 'USFAC-' + rh('QUALITY_COMPOSITE', security_id, template['period_id'])[:24],
            'canonical_security_id': security_id,
            'canonical_issuer_id': template['canonical_issuer_id'],
            'symbol': template['symbol'],
            'factor_domain': 'QUALITY',
            'factor_name': 'QUALITY_SANDBOX_COMPOSITE',
            'factor_value': score,
            'unit': 'percentile_score_0_1',
            'period_id': template['period_id'],
            'period_end': template['period_end'],
            'direction': 'HIGHER_BETTER',
            'cross_section_percentile': score,
            'component_factor_names': sorted(row['factor_name'] for row in rows),
            'component_count': len(rows),
            'data_grade': 'DECISION_GRADE_OFFICIAL_SEC_DERIVED',
            'factor_usage': 'SINGLE_QUARTER_NON_SECTOR_NEUTRAL_SANDBOX_ONLY',
            'sector_neutral': False,
            'neutral_fill_used': False,
        })
    return sorted(raw, key=lambda row: (row['canonical_security_id'], row['factor_name'])), composites


def safe_return(closes: list[float], days: int) -> float | None:
    if len(closes) <= days or closes[-days - 1] in (None, 0):
        return None
    return closes[-1] / closes[-days - 1] - 1


def realized_volatility(returns: list[float], window: int) -> float | None:
    if len(returns) < window:
        return None
    values = returns[-window:]
    return statistics.stdev(values) * math.sqrt(252) if len(values) > 1 else None


def max_drawdown(closes: list[float], window: int) -> float | None:
    if len(closes) < window:
        return None
    peak = closes[-window]
    worst = 0.0
    for value in closes[-window:]:
        peak = max(peak, value)
        worst = min(worst, value / peak - 1)
    return worst


def market_risk_records(
    inputs: dict[str, Any], contract: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    bars_by_security: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in inputs['bars']:
        bars_by_security[row['canonical_security_id']].append(row)
    security_meta = {row['canonical_security_id']: row for row in inputs['security_readiness']}
    market: list[dict[str, Any]] = []
    risk: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for security_id, rows in sorted(bars_by_security.items()):
        rows.sort(key=lambda row: row['date'])
        closes = [float(row['close']) for row in rows if row.get('close') is not None]
        returns = [
            math.log(closes[index] / closes[index - 1])
            for index in range(1, len(closes))
            if closes[index - 1] > 0 and closes[index] > 0
        ]
        meta = security_meta[security_id]
        base = {
            'canonical_security_id': security_id,
            'canonical_issuer_id': meta['canonical_issuer_id'],
            'symbol': meta['symbol'],
            'as_of_date': rows[-1]['date'],
            'source_authority': 'YAHOO_FREE_UNOFFICIAL',
            'data_grade': 'NON_DECISION_GRADE_FALLBACK',
            'factor_usage': 'MARKET_SANDBOX_ONLY',
            'neutral_fill_used': False,
        }
        market_specs: list[tuple[str, float | None, str]] = [
            ('PRICE_RETURN_21D', safe_return(closes, 21), 'ratio'),
            ('PRICE_RETURN_63D', safe_return(closes, 63), 'ratio'),
            ('PRICE_RETURN_126D', safe_return(closes, 126), 'ratio'),
            ('PRICE_RETURN_252D', safe_return(closes, 252), 'ratio'),
        ]
        if len(closes) > 252:
            market_specs.append(('PRICE_MOMENTUM_12M_EX_1M', closes[-22] / closes[-253] - 1, 'ratio'))
        if len(rows) >= 20:
            dollar_volumes = [
                float(row['close']) * float(row.get('volume') or 0)
                for row in rows[-20:]
                if row.get('close') is not None
            ]
            market_specs.append(('AVERAGE_DOLLAR_VOLUME_20D', sum(dollar_volumes) / len(dollar_volumes), 'USD'))
        for name, value, unit in market_specs:
            if value is not None and math.isfinite(value):
                market.append({
                    'factor_id': 'USFAC-' + rh('MARKET', security_id, name, rows[-1]['date'])[:24],
                    **base,
                    'factor_domain': 'MARKET',
                    'factor_name': name,
                    'factor_value': value,
                    'unit': unit,
                    'cross_section_percentile': None,
                    'direction': 'HIGHER_LIQUIDITY' if name == 'AVERAGE_DOLLAR_VOLUME_20D' else 'HIGHER_BETTER',
                    'price_basis': 'UNADJUSTED_CLOSE_EX_DIVIDENDS_SANDBOX_ONLY',
                })
        risk_specs: list[tuple[str, float | None]] = [
            ('REALIZED_VOLATILITY_20D', realized_volatility(returns, 20)),
            ('REALIZED_VOLATILITY_60D', realized_volatility(returns, 60)),
            ('REALIZED_VOLATILITY_252D', realized_volatility(returns, 252)),
            ('MAX_DRAWDOWN_252D', max_drawdown(closes, 253)),
        ]
        if len(returns) >= 60:
            downside = [min(value, 0.0) for value in returns[-60:]]
            risk_specs.append(('DOWNSIDE_VOLATILITY_60D', statistics.stdev(downside) * math.sqrt(252)))
        for name, value in risk_specs:
            if value is not None and math.isfinite(value):
                risk.append({
                    'factor_id': 'USFAC-' + rh('RISK', security_id, name, rows[-1]['date'])[:24],
                    **base,
                    'factor_domain': 'RISK',
                    'factor_name': name,
                    'factor_value': value,
                    'unit': 'ratio_annualized' if 'VOLATILITY' in name else 'ratio',
                    'cross_section_percentile': None,
                    'direction': 'LOWER_RISK_BETTER',
                    'price_basis': 'UNADJUSTED_CLOSE_SANDBOX_ONLY',
                })
        if len(closes) <= 21:
            issues.append({
                'queue': 'MARKET_WINDOW_INSUFFICIENT_QUEUE',
                'canonical_security_id': security_id,
                'symbol': meta['symbol'],
                'bar_count': len(closes),
                'required_action': 'ACCUMULATE_MORE_ACCEPTED_DAILY_BARS',
                'status': 'OPEN',
            })
    for rows, higher in ((market, True), (risk, False)):
        ranks = percentile_map(rows, higher=higher)
        for row in rows:
            row['cross_section_percentile'] = ranks[row['factor_name'] + '|' + row['canonical_security_id']]
    return (
        sorted(market, key=lambda row: (row['canonical_security_id'], row['factor_name'])),
        sorted(risk, key=lambda row: (row['canonical_security_id'], row['factor_name'])),
        issues,
    )


def build_status(
    inputs: dict[str, Any],
    quality: list[dict[str, Any]],
    market: list[dict[str, Any]],
    risk: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    quality_ids = {row['canonical_security_id'] for row in quality}
    market_ids = {row['canonical_security_id'] for row in market}
    risk_ids = {row['canonical_security_id'] for row in risk}
    output: list[dict[str, Any]] = []
    for row in sorted(inputs['security_readiness'], key=lambda item: item['canonical_security_id']):
        security_id = row['canonical_security_id']
        financial_applicable = row['x3b_financial_normalization_gate'] != 'NOT_APPLICABLE'
        output.append({
            'canonical_security_id': security_id,
            'canonical_issuer_id': row['canonical_issuer_id'],
            'symbol': row['symbol'],
            'venue': row['venue'],
            'research_profile': row['research_profile'],
            'research_scope': row['research_scope'],
            'quality_factor_gate': (
                'OPEN_QUARTERLY_SANDBOX'
                if security_id in quality_ids
                else 'BLOCKED_FINANCIAL_BACKFILL'
                if financial_applicable
                else 'NOT_APPLICABLE'
            ),
            'market_factor_gate': (
                'OPEN_NON_DECISION_GRADE_SANDBOX'
                if security_id in market_ids
                else row['x3c_market_factor_gate']
            ),
            'risk_factor_gate': (
                'OPEN_NON_DECISION_GRADE_SANDBOX'
                if security_id in risk_ids
                else 'BLOCKED_MARKET_WINDOW_OR_BACKFILL'
                if row['research_scope'] != 'EXCLUDED'
                else 'NOT_APPLICABLE'
            ),
            'valuation_factor_gate': (
                'BLOCKED_TTM_AND_ANNUAL_PENDING'
                if security_id in quality_ids
                else 'BLOCKED_FINANCIAL_BACKFILL'
                if financial_applicable
                else 'NOT_APPLICABLE'
            ),
            'cross_section_composite_gate': (
                'BLOCKED_SECTOR_PEER_AND_BENCHMARK_FRAMEWORK_PENDING'
                if row['research_scope'] in {'STANDARD_RESEARCH_PROFILE', 'SPECIAL_RESEARCH_PROFILE'}
                else 'NOT_APPLICABLE'
            ),
            'global_factor_score_emitted': False,
            'candidate_pool_status': 'NOT_AUTHORIZED',
            'trade_authority': 'NONE',
        })
    return output


def build(root: Path, candidate: Path, accepted_at: str, source_commit: str) -> dict[str, Any]:
    contract = validate_contract(root)
    inputs = load_inputs(root, contract)
    quality_raw, quality_composites = quality_records(inputs, contract)
    market, risk, window_issues = market_risk_records(inputs, contract)
    status = build_status(inputs, quality_raw, market, risk)
    queues: dict[str, list[dict[str, Any]]] = {
        'VALUATION_INPUT_BACKFILL_QUEUE': [],
        'MARKET_DATA_DECISION_GRADE_UPGRADE_QUEUE': [],
        'QUALITY_COMPARABILITY_QUEUE': [],
        'MARKET_HISTORY_BACKFILL_QUEUE': [],
        'MARKET_WINDOW_INSUFFICIENT_QUEUE': window_issues,
    }
    for period in inputs['period_readiness']:
        queues['VALUATION_INPUT_BACKFILL_QUEUE'].append({
            'canonical_security_id': period['canonical_security_id'],
            'canonical_issuer_id': period['canonical_issuer_id'],
            'symbol': period['symbol'],
            'valuation_status': period['x3c_valuation_gate'],
            'required_action': 'CAPTURE_FOUR_DISTINCT_OFFICIAL_QUARTERS_AND_ANNUAL_BALANCE_SHEET_CASH_FLOW_INPUTS',
            'status': 'OPEN',
        })
    readiness_by_security = {row['canonical_security_id']: row for row in inputs['security_readiness']}
    for security_id in sorted({row['canonical_security_id'] for row in market}):
        meta = readiness_by_security[security_id]
        queues['MARKET_DATA_DECISION_GRADE_UPGRADE_QUEUE'].append({
            'canonical_security_id': security_id,
            'symbol': meta['symbol'],
            'current_grade': 'NON_DECISION_GRADE_FALLBACK',
            'required_action': 'OBTAIN_APPROVED_DECISION_GRADE_MARKET_DATA_BEFORE_FORMAL_FACTOR_USE',
            'status': 'OPEN',
        })
    for security_id in sorted({row['canonical_security_id'] for row in quality_raw}):
        meta = readiness_by_security[security_id]
        queues['QUALITY_COMPARABILITY_QUEUE'].append({
            'canonical_security_id': security_id,
            'symbol': meta['symbol'],
            'current_basis': 'SINGLE_QUARTER_NON_SECTOR_NEUTRAL',
            'required_action': 'ADD_TTM_ANNUAL_AND_SECTOR_PEER_CONTEXT_BEFORE_FORMAL_QUALITY_RANKING',
            'status': 'OPEN',
        })
    for row in inputs['security_readiness']:
        if row['x3c_market_factor_gate'] == 'BLOCKED_MARKET_BACKFILL_PENDING':
            queues['MARKET_HISTORY_BACKFILL_QUEUE'].append({
                'canonical_security_id': row['canonical_security_id'],
                'symbol': row['symbol'],
                'required_action': 'COMPLETE_ACCEPTED_MARKET_HISTORY_BACKFILL',
                'status': 'OPEN',
            })
    for rows in queues.values():
        rows.sort(key=stable)

    valuation: list[dict[str, Any]] = []
    bucket_count = contract['storage_contract']['bucket_count']
    domains = [
        ('SECURITY_FACTOR_STATUS', status, 'canonical_security_id'),
        ('QUALITY_FACTOR', quality_raw + quality_composites, 'canonical_security_id'),
        ('MARKET_FACTOR', market, 'canonical_security_id'),
        ('RISK_FACTOR', risk, 'canonical_security_id'),
        ('VALUATION_FACTOR', valuation, 'canonical_security_id'),
    ]
    entries: dict[str, bytes] = {}
    shards: list[dict[str, Any]] = []
    for domain, rows, key in domains:
        for index in range(bucket_count):
            bucket_id = f'{index:02X}'
            shard_rows = sorted(
                [row for row in rows if bucket(str(row[key]), bucket_count) == bucket_id],
                key=lambda row: (row[key], row.get('factor_name', '')),
            )
            name = f'{domain}/{bucket_id}.jsonl'
            payload = jsonl(shard_rows)
            entries[name] = payload
            shards.append({
                'shard_id': f'{domain}-{bucket_id}',
                'domain': domain,
                'bucket': bucket_id,
                'row_count': len(shard_rows),
                'payload_sha256': sha_bytes(payload),
                'generated_at': accepted_at,
                'quality_status': 'PASS',
            })

    contract_sha = sha_file(root / CONTRACT)
    input_manifest_sha256 = {name: sha_file(path) for name, path in inputs['manifests'].items()}
    release_id = 'FMDL6X3C_20260722_' + rh(
        'RELEASE', contract_sha, *[input_manifest_sha256[name] for name in sorted(input_manifest_sha256)]
    )[:12]
    candidate.mkdir(parents=True, exist_ok=True)
    (candidate / 'FMDL6X3C_FACTOR_SHARDS.zip').write_bytes(dzip(entries))
    (candidate / 'FMDL6X3C_REVIEW_QUEUES.zip').write_bytes(
        dzip({name + '.jsonl': jsonl(rows) for name, rows in queues.items()})
    )
    market_source_security_count = len({row['canonical_security_id'] for row in inputs['bars']})
    coverage = {
        'phase_id': PHASE,
        'release_id': release_id,
        'security_universe_count': len(status),
        'market_source_security_count': market_source_security_count,
        'quarterly_quality_security_count': len({row['canonical_security_id'] for row in quality_raw}),
        'quality_raw_observation_count': len(quality_raw),
        'quality_composite_count': len(quality_composites),
        'market_security_count': len({row['canonical_security_id'] for row in market}),
        'market_factor_observation_count': len(market),
        'risk_security_count': len({row['canonical_security_id'] for row in risk}),
        'risk_factor_observation_count': len(risk),
        'valuation_factor_observation_count': 0,
        'global_factor_score_count': 0,
        'full_factor_completion_claimed': False,
        'valuation_completion_claimed': False,
        'market_data_grade': 'NON_DECISION_GRADE_FALLBACK',
        'quality_usage': 'QUARTERLY_SANDBOX_ONLY',
        'market_risk_usage': 'NON_DECISION_GRADE_SANDBOX_ONLY',
    }
    write(candidate / 'FMDL6X3C_COVERAGE_REPORT.json', coverage)
    quality = {
        'phase_id': PHASE,
        'release_id': release_id,
        'quality_status': 'PASS',
        'security_universe_actual': len(status),
        'security_universe_expected': contract['quality_gates']['security_universe_expected'],
        'quality_security_count': coverage['quarterly_quality_security_count'],
        'quality_observation_count': len(quality_raw),
        'quality_composite_count': len(quality_composites),
        'market_source_security_count': market_source_security_count,
        'market_security_count': coverage['market_security_count'],
        'market_factor_observation_count': len(market),
        'risk_factor_observation_count': len(risk),
        'valuation_factor_observation_count': 0,
        'global_factor_score_count': 0,
        'neutral_fill_count': sum(
            1 for row in quality_raw + quality_composites + market + risk if row.get('neutral_fill_used')
        ),
        'non_decision_market_rows': len(market) + len(risk),
        'manifested_shard_count': len(shards),
        'expected_shard_count': contract['quality_gates']['expected_shard_count'],
        'future_dated_financial_rows': sum(1 for row in quality_raw if row['period_end'] > contract['as_of_date']),
        'future_dated_market_rows': sum(
            1 for row in market + risk if row['as_of_date'] > contract['market_as_of_date']
        ),
        'trade_authority': 'NONE',
        'zero_mutation_proof': contract['zero_mutation_gate'],
    }
    errors: list[str] = []
    if quality['security_universe_actual'] != quality['security_universe_expected']:
        errors.append('UNIVERSE')
    if (
        quality['quality_security_count'] < 3
        or quality['quality_observation_count'] < 27
        or quality['quality_composite_count'] < 3
    ):
        errors.append('QUALITY_COVERAGE')
    if (
        quality['market_source_security_count'] < 64
        or quality['market_security_count'] < 63
        or quality['market_factor_observation_count'] < 300
        or quality['risk_factor_observation_count'] < 250
    ):
        errors.append('MARKET_RISK_COVERAGE')
    if quality['valuation_factor_observation_count'] != 0 or quality['global_factor_score_count'] != 0:
        errors.append('BLOCKED_LAYER_EMISSION')
    if quality['neutral_fill_count'] or quality['future_dated_financial_rows'] or quality['future_dated_market_rows']:
        errors.append('DATA_INTEGRITY')
    if len(shards) != quality['expected_shard_count']:
        errors.append('SHARDS')
    if errors:
        quality['quality_status'] = 'FAIL'
        quality['errors'] = errors
    write(candidate / 'FMDL6X3C_QUALITY_REPORT.json', quality)
    if errors:
        raise RuntimeError('QUALITY:' + ','.join(errors))

    write(candidate / 'FMDL6X3C_SOURCE_BINDING.json', {
        'phase_id': PHASE,
        'release_id': release_id,
        'input_manifest_sha256': input_manifest_sha256,
        'financial_source_grade': 'DECISION_GRADE_OFFICIAL_SEC_DERIVED',
        'market_source_authority': 'YAHOO_FREE_UNOFFICIAL',
        'market_data_grade': 'NON_DECISION_GRADE_FALLBACK',
        'neutral_fill_used': False,
        'silent_source_substitution': False,
        'valuation_inference_used': False,
        'global_composite_emitted': False,
    })
    write(candidate / 'FMDL6X3C_FACTOR_DEFINITIONS.json', {
        'phase_id': PHASE,
        'release_id': release_id,
        'quality_score_components': contract['quality_contract']['sandbox_score_components'],
        'market_metrics': sorted({row['factor_name'] for row in market}),
        'risk_metrics': sorted({row['factor_name'] for row in risk}),
        'valuation_metrics_emitted': [],
        'formal_cross_section_ranking_status': 'BLOCKED_PENDING_FMDL6X3D_SECTOR_PEER_FRAMEWORK',
    })
    write(candidate / 'FMDL6X3C_QUEUE_SUMMARY.json', {
        'phase_id': PHASE,
        'release_id': release_id,
        'queue_counts': {name: len(rows) for name, rows in sorted(queues.items())},
    })
    decision = {
        'phase_id': PHASE,
        'status': STATUS,
        'release_id': release_id,
        'release_sequence': 38,
        'accepted_at': accepted_at,
        'source_commit': source_commit,
        'input_release_id': 'FMDL6X3B_20260722_5d2ed5708fc1',
        'next_gate': NEXT,
        'factor_engine_status': 'QUARTERLY_QUALITY_AND_NON_DECISION_GRADE_MARKET_RISK_SANDBOX_WITH_VALUATION_BLOCKED',
        'quality_sandbox_security_count': coverage['quarterly_quality_security_count'],
        'market_risk_sandbox_security_count': coverage['market_security_count'],
        'valuation_ready_security_count': 0,
        'global_factor_score_count': 0,
        'research_production_gate': 'OPEN_FOR_FMDL6X3D_SECTOR_PEER_AND_BENCHMARK_FRAMEWORK',
        'investment_os_candidate_pool_gate': 'CLOSED_NOT_AUTHORIZED_IN_FMDL6X3C',
        'simulation_gate': 'CLOSED_NOT_AUTHORIZED_IN_FMDL6X3C',
        'brokerage_real_account_gate': 'CLOSED_NO_CHANNEL',
        'trade_authority': 'NONE',
        'zero_mutation_proof': contract['zero_mutation_gate'],
    }
    write(candidate / 'FMDL6X3C_DECISION.json', decision)
    files = {
        path.name: {'bytes': path.stat().st_size, 'sha256': sha_file(path)}
        for path in sorted(candidate.iterdir())
        if path.is_file() and path.name != 'FMDL6X3C_MANIFEST.json'
    }
    write(candidate / 'FMDL6X3C_MANIFEST.json', {
        'phase_id': PHASE,
        'release_id': release_id,
        'release_sequence': 38,
        'generated_at': accepted_at,
        'contract_sha256': contract_sha,
        'input_manifest_sha256': input_manifest_sha256,
        'files': files,
        'shards': shards,
    })
    return {'decision': decision, 'quality': quality, 'coverage': coverage}


def validate_candidate(
    root: Path,
    candidate: Path,
    accepted_at: str,
    source_commit: str,
    acceptance: Path,
) -> dict[str, Any]:
    replay = candidate.parent / (candidate.name + '_replay')
    shutil.rmtree(replay, ignore_errors=True)
    build(root, replay, accepted_at, source_commit)
    left = {path.name: sha_file(path) for path in candidate.iterdir() if path.is_file()}
    right = {path.name: sha_file(path) for path in replay.iterdir() if path.is_file()}
    errors: list[str] = [] if left == right else ['SAME_INPUT_REPLAY']
    manifest = load(candidate / 'FMDL6X3C_MANIFEST.json')
    for name, meta in manifest['files'].items():
        path = candidate / name
        if not path.is_file() or path.stat().st_size != meta['bytes'] or sha_file(path) != meta['sha256']:
            errors.append('MANIFEST:' + name)
    result = {
        'phase_id': PHASE,
        'release_id': load(candidate / 'FMDL6X3C_DECISION.json')['release_id'],
        'status': 'PASS' if not errors else 'FAIL',
        'same_input_byte_replay': 'PASS' if left == right else 'FAIL',
        'errors': errors,
    }
    write(acceptance, result)
    if errors:
        raise RuntimeError('ACCEPTANCE:' + ','.join(errors))
    return result


def copytree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def publish(root: Path, candidate: Path, published_at: str, source_commit: str) -> dict[str, Any]:
    decision = load(candidate / 'FMDL6X3C_DECISION.json')
    release_id = decision['release_id']
    current = root / 'outputs/fmdl6x3/current/factor_engine'
    release = root / f'datasets/fmdl6x3/releases/{release_id}/factor_engine'
    normalized = root / f'datasets/fmdl6x3/normalized/factor_engine/{release_id}'
    archive_root = root / 'outputs/fmdl6x3/archive'
    if release.exists():
        existing = {path.name: sha_file(path) for path in release.iterdir() if path.is_file()}
        incoming = {path.name: sha_file(path) for path in candidate.iterdir() if path.is_file()}
        if existing != incoming:
            raise RuntimeError('IMMUTABLE_RELEASE_COLLISION')
    if current.exists():
        old_decision = load(current / 'FMDL6X3C_DECISION.json')
        archive = archive_root / old_decision['release_id'] / 'factor_engine'
        if not archive.exists():
            copytree(current, archive)
    if not release.exists():
        copytree(candidate, release)
    copytree(candidate, normalized)
    copytree(candidate, current)
    for name in ('FMDL6X3C_DECISION.json', 'FMDL6X3C_MANIFEST.json'):
        if (current / name).read_bytes() != (release / name).read_bytes():
            raise RuntimeError('CURRENT_RELEASE_PARITY')
    pointer = {
        'phase_id': PHASE,
        'status': STATUS,
        'release_id': release_id,
        'release_sequence': 38,
        'published_at': published_at,
        'source_commit': source_commit,
        'current_path': 'outputs/fmdl6x3/current/factor_engine',
        'release_path': f'datasets/fmdl6x3/releases/{release_id}/factor_engine',
        'normalized_path': f'datasets/fmdl6x3/normalized/factor_engine/{release_id}',
        'manifest_sha256': sha_file(current / 'FMDL6X3C_MANIFEST.json'),
        'factor_engine_status': decision['factor_engine_status'],
        'quality_sandbox_security_count': decision['quality_sandbox_security_count'],
        'market_risk_sandbox_security_count': decision['market_risk_sandbox_security_count'],
        'valuation_ready_security_count': 0,
        'global_factor_score_count': 0,
        'next_gate': NEXT,
        'research_production_gate': decision['research_production_gate'],
        'investment_os_candidate_pool_gate': decision['investment_os_candidate_pool_gate'],
        'brokerage_real_account_gate': 'CLOSED_NO_CHANNEL',
        'trade_authority': 'NONE',
        'zero_mutation_proof': decision['zero_mutation_proof'],
    }
    write(root / 'outputs/status/FMDL6X3C_LAST_SUCCESS.json', pointer)
    write(root / 'outputs/status/FMDL6X3_FACTOR_ENGINE_LKG.json', {
        **pointer,
        'lkg_scope': 'FMDL6X3_FACTOR_VALUATION_QUALITY_AND_RISK_DOMAIN',
        'lkg_reason': 'LATEST_ACCEPTED_FACTORS_WITH_EXPLICIT_SANDBOX_AND_BLOCKED_LAYER_BOUNDARIES',
    })
    return pointer


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo-root', default='.')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('validate-contract')
    for name in ('build', 'validate-candidate', 'publish'):
        command = sub.add_parser(name)
        command.add_argument('--candidate', required=True)
        if name in ('build', 'validate-candidate'):
            command.add_argument('--accepted-at', required=True)
        if name == 'publish':
            command.add_argument('--published-at', required=True)
        command.add_argument('--source-commit', required=True)
        if name == 'validate-candidate':
            command.add_argument('--acceptance', required=True)
    args = parser.parse_args()
    root = Path(args.repo_root)
    if args.command == 'validate-contract':
        validate_contract(root)
    elif args.command == 'build':
        build(root, Path(args.candidate), args.accepted_at, args.source_commit)
    elif args.command == 'validate-candidate':
        validate_candidate(
            root,
            Path(args.candidate),
            args.accepted_at,
            args.source_commit,
            Path(args.acceptance),
        )
    else:
        publish(root, Path(args.candidate), args.published_at, args.source_commit)


if __name__ == '__main__':
    main()
