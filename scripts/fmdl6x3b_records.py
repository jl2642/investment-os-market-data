from __future__ import annotations

from fmdl6x3b_common import *

def canonical_source_fact(source: dict[str, Any], readiness: dict[str, Any], mapping: dict[str, Any]) -> dict[str, Any]:
    start = date.fromisoformat(source['start_date'])
    end = date.fromisoformat(source['end_date'])
    duration_days = (end - start).days + 1
    return {'normalized_fact_id': 'USNF-' + record_hash('NORMALIZED_FACT', source['fact_id'])[:24], 'source_fact_id': source['fact_id'], 'canonical_security_id': source['canonical_security_id'], 'canonical_issuer_id': source['canonical_issuer_id'], 'canonical_listing_id': readiness.get('canonical_listing_id'), 'symbol': source['symbol'], 'research_profile': readiness['research_profile'], 'statement': mapping['statement'], 'canonical_metric': mapping['canonical_metric'], 'taxonomy': source['taxonomy'], 'source_tag': source['tag'], 'source_label': source['label'], 'reported_value': source['value'], 'normalized_value': source['value'], 'reported_unit': source['unit'], 'normalized_unit': source['unit'], 'currency': 'USD' if source['unit'] in {'USD', 'USD/shares'} else None, 'start_date': source['start_date'], 'end_date': source['end_date'], 'duration_days': duration_days, 'period_granularity': 'QUARTER' if 60 <= duration_days <= 120 else 'UNRESOLVED_DURATION', 'fiscal_year': source['fiscal_year'], 'fiscal_period': source['fiscal_period'], 'period_id': period_id(source), 'form': source['form'], 'filing_date': source['filing_date'], 'accepted_at': source['accepted_at'], 'report_period': source['report_period'], 'accession_number': source['accession_number'], 'source_id': source['accession_number'], 'source_name': 'SEC_OFFICIAL_FILING', 'source_url': source['source_url'], 'source_authority': source['source_authority'], 'data_grade': source['data_grade'], 'evidence_label': 'fact_source_reported', 'confidence': 'high', 'reported_or_derived': 'REPORTED', 'comparability_status': 'SINGLE_PERIOD_REPORTED', 'model_loadable': duration_days >= 60 and duration_days <= 120, 'neutral_fill_used': False}

def statement_row_from_source(row: dict[str, Any]) -> dict[str, Any]:
    return {'statement_row_id': 'USFS-' + record_hash('STATEMENT', row['normalized_fact_id'])[:24], 'canonical_security_id': row['canonical_security_id'], 'canonical_issuer_id': row['canonical_issuer_id'], 'symbol': row['symbol'], 'research_profile': row['research_profile'], 'statement': row['statement'], 'canonical_metric': row['canonical_metric'], 'value': row['normalized_value'], 'unit': row['normalized_unit'], 'currency': row['currency'], 'start_date': row['start_date'], 'end_date': row['end_date'], 'fiscal_year': row['fiscal_year'], 'fiscal_period': row['fiscal_period'], 'period_id': row['period_id'], 'source_fact_ids': [row['source_fact_id']], 'source_ids': [row['source_id']], 'source_urls': [row['source_url']], 'evidence_label': row['evidence_label'], 'confidence': row['confidence'], 'reported_or_derived': 'REPORTED', 'formula': None, 'comparability_status': row['comparability_status'], 'model_loadable': row['model_loadable']}

def derived_statement_row(template: dict[str, Any], metric: str, value: int | float, source_rows: list[dict[str, Any]], formula: str) -> dict[str, Any]:
    return {'statement_row_id': 'USFS-' + record_hash('DERIVED_STATEMENT', template['canonical_issuer_id'], template['period_id'], metric, value)[:24], 'canonical_security_id': template['canonical_security_id'], 'canonical_issuer_id': template['canonical_issuer_id'], 'symbol': template['symbol'], 'research_profile': template['research_profile'], 'statement': 'INCOME_STATEMENT', 'canonical_metric': metric, 'value': value, 'unit': source_rows[0]['unit'], 'currency': source_rows[0]['currency'], 'start_date': template['start_date'], 'end_date': template['end_date'], 'fiscal_year': template['fiscal_year'], 'fiscal_period': template['fiscal_period'], 'period_id': template['period_id'], 'source_fact_ids': sorted({fact for row in source_rows for fact in row['source_fact_ids']}), 'source_ids': sorted({source for row in source_rows for source in row['source_ids']}), 'source_urls': sorted({url for row in source_rows for url in row['source_urls']}), 'evidence_label': 'derived_calculation', 'confidence': 'high', 'reported_or_derived': 'DERIVED', 'formula': formula, 'comparability_status': 'SINGLE_PERIOD_DERIVED_FROM_REPORTED_COMPONENTS', 'model_loadable': all((row['model_loadable'] for row in source_rows))}

def metric_row(template: dict[str, Any], metric: str, numerator: dict[str, Any], denominator: dict[str, Any]) -> dict[str, Any]:
    value = numerator['value'] / denominator['value']
    return {'metric_row_id': 'USFM-' + record_hash('DERIVED_METRIC', template['canonical_issuer_id'], template['period_id'], metric)[:24], 'canonical_security_id': template['canonical_security_id'], 'canonical_issuer_id': template['canonical_issuer_id'], 'symbol': template['symbol'], 'research_profile': template['research_profile'], 'canonical_metric': metric, 'value': value, 'unit': 'ratio', 'start_date': template['start_date'], 'end_date': template['end_date'], 'fiscal_year': template['fiscal_year'], 'fiscal_period': template['fiscal_period'], 'period_id': template['period_id'], 'numerator_metric': numerator['canonical_metric'], 'denominator_metric': denominator['canonical_metric'], 'formula': f"{numerator['canonical_metric']} / {denominator['canonical_metric']}", 'source_fact_ids': sorted(set(numerator['source_fact_ids'] + denominator['source_fact_ids'])), 'source_ids': sorted(set(numerator['source_ids'] + denominator['source_ids'])), 'evidence_label': 'derived_calculation', 'confidence': 'high', 'downstream_use': 'QUARTERLY_QUALITY_SANDBOX_ONLY_UNTIL_TTM_AND_ANNUAL_READY', 'model_loadable': True}

def tolerance(expected: float) -> float:
    return max(1000000.0, abs(expected) * 1e-06)

def validation_row(issuer_id: str, security_id: str, period: str, check_name: str, left: float, right: float, formula: str) -> dict[str, Any]:
    difference = left - right
    threshold = tolerance(right)
    return {'validation_id': 'USVAL-' + record_hash('VALIDATION', issuer_id, period, check_name)[:24], 'canonical_issuer_id': issuer_id, 'canonical_security_id': security_id, 'period_id': period, 'check_name': check_name, 'formula': formula, 'left_value': left, 'right_value': right, 'difference': difference, 'tolerance': threshold, 'status': 'PASS' if abs(difference) <= threshold else 'FAIL'}

def issue_row(readiness: dict[str, Any], issue_type: str, severity: str, affected_layer: str, required_action: str, evidence_label: str='missing_required_source') -> dict[str, Any]:
    return {'issue_id': 'USISS-' + record_hash('ISSUE', readiness['canonical_security_id'], issue_type)[:24], 'canonical_security_id': readiness['canonical_security_id'], 'canonical_issuer_id': readiness['canonical_issuer_id'], 'symbol': readiness['symbol'], 'research_profile': readiness['research_profile'], 'issue_type': issue_type, 'severity': severity, 'affected_layer': affected_layer, 'required_action': required_action, 'evidence_label': evidence_label, 'status': 'OPEN'}

def build_records(inputs: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    ready = inputs['ready_rows']
    ready_by_security = {row['canonical_security_id']: row for row in ready}
    ready_ids = set(ready_by_security)
    supported_profiles = set(contract['profile_contract']['supported_profiles_v1'])
    accepted_grade = contract['input_contract']['accepted_sec_data_grade']
    mapping = contract['tag_mapping']
    source_facts = [fact for fact in inputs['facts'] if fact['canonical_security_id'] in ready_ids]
    source_facts.sort(key=lambda row: (row['canonical_issuer_id'], row['start_date'], row['tag']))
    errors: list[str] = []
    if len(ready) < contract['input_contract']['minimum_ready_security_count']:
        errors.append('READY_SECURITY_COVERAGE')
    if len({row['canonical_issuer_id'] for row in ready}) < contract['input_contract']['minimum_ready_issuer_count']:
        errors.append('READY_ISSUER_COVERAGE')
    if len(source_facts) < contract['input_contract']['minimum_source_fact_count']:
        errors.append('SOURCE_FACT_COVERAGE')
    if any((row['research_profile'] not in supported_profiles for row in ready)):
        errors.append('UNSUPPORTED_READY_PROFILE')
    if any((fact.get('data_grade') != accepted_grade or fact.get('source_authority') != 'SEC_OFFICIAL' for fact in source_facts)):
        errors.append('SOURCE_GRADE')
    unmapped = sorted({fact['tag'] for fact in source_facts if fact['tag'] not in mapping})
    if unmapped:
        errors.append('UNMAPPED_TAGS')
    normalized: list[dict[str, Any]] = []
    for fact in source_facts:
        readiness = ready_by_security[fact['canonical_security_id']]
        row = canonical_source_fact(fact, readiness, mapping[fact['tag']])
        if row['period_granularity'] != 'QUARTER':
            errors.append('PERIOD_GRANULARITY')
        normalized.append(row)
    duplicate_source_keys = len(normalized) - len({(row['canonical_security_id'], row['source_tag'], row['start_date'], row['end_date'], row['reported_unit'], str(row['reported_value'])) for row in normalized})
    if duplicate_source_keys:
        errors.append('DUPLICATE_SOURCE_FACT_KEYS')
    statement_rows = [statement_row_from_source(row) for row in normalized]
    statement_by_security: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in statement_rows:
        statement_by_security[row['canonical_security_id']].append(row)
    derived_statement: list[dict[str, Any]] = []
    for readiness in ready:
        rows = statement_by_security[readiness['canonical_security_id']]
        by_metric = {row['canonical_metric']: row for row in rows}
        template = rows[0]
        if 'SELLING_GENERAL_AND_ADMINISTRATIVE' not in by_metric:
            if 'SELLING_AND_MARKETING' in by_metric and 'GENERAL_AND_ADMINISTRATIVE' in by_metric:
                sgna = derived_statement_row(template, 'SELLING_GENERAL_AND_ADMINISTRATIVE', by_metric['SELLING_AND_MARKETING']['value'] + by_metric['GENERAL_AND_ADMINISTRATIVE']['value'], [by_metric['SELLING_AND_MARKETING'], by_metric['GENERAL_AND_ADMINISTRATIVE']], 'SELLING_AND_MARKETING + GENERAL_AND_ADMINISTRATIVE')
                rows.append(sgna)
                derived_statement.append(sgna)
                by_metric[sgna['canonical_metric']] = sgna
        if 'OPERATING_EXPENSES' not in by_metric:
            if 'RESEARCH_AND_DEVELOPMENT' in by_metric and 'SELLING_GENERAL_AND_ADMINISTRATIVE' in by_metric:
                opex = derived_statement_row(template, 'OPERATING_EXPENSES', by_metric['RESEARCH_AND_DEVELOPMENT']['value'] + by_metric['SELLING_GENERAL_AND_ADMINISTRATIVE']['value'], [by_metric['RESEARCH_AND_DEVELOPMENT'], by_metric['SELLING_GENERAL_AND_ADMINISTRATIVE']], 'RESEARCH_AND_DEVELOPMENT + SELLING_GENERAL_AND_ADMINISTRATIVE')
                rows.append(opex)
                derived_statement.append(opex)
                by_metric[opex['canonical_metric']] = opex
    statement_rows.extend(derived_statement)
    statement_rows.sort(key=lambda row: (row['canonical_issuer_id'], row['period_id'], row['canonical_metric'], row['reported_or_derived']))
    derived_metrics: list[dict[str, Any]] = []
    validations: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    period_readiness: list[dict[str, Any]] = []
    ratio_specs = [('COST_OF_REVENUE_RATIO', 'COST_OF_REVENUE', 'REVENUE'), ('GROSS_MARGIN', 'GROSS_PROFIT', 'REVENUE'), ('RESEARCH_AND_DEVELOPMENT_INTENSITY', 'RESEARCH_AND_DEVELOPMENT', 'REVENUE'), ('SELLING_GENERAL_AND_ADMINISTRATIVE_INTENSITY', 'SELLING_GENERAL_AND_ADMINISTRATIVE', 'REVENUE'), ('OPERATING_EXPENSE_RATIO', 'OPERATING_EXPENSES', 'REVENUE'), ('OPERATING_MARGIN', 'OPERATING_INCOME', 'REVENUE'), ('PRETAX_MARGIN', 'PRETAX_INCOME', 'REVENUE'), ('EFFECTIVE_TAX_RATE', 'INCOME_TAX_EXPENSE', 'PRETAX_INCOME'), ('NET_MARGIN', 'NET_INCOME', 'REVENUE')]
    for readiness in ready:
        sid = readiness['canonical_security_id']
        rows = [row for row in statement_rows if row['canonical_security_id'] == sid]
        by_metric = {row['canonical_metric']: row for row in rows}
        template = rows[0]
        required = {'REVENUE', 'COST_OF_REVENUE', 'GROSS_PROFIT', 'RESEARCH_AND_DEVELOPMENT', 'SELLING_GENERAL_AND_ADMINISTRATIVE', 'OPERATING_EXPENSES', 'OPERATING_INCOME', 'PRETAX_INCOME', 'INCOME_TAX_EXPENSE', 'NET_INCOME', 'DILUTED_EPS'}
        missing_required = sorted(required - set(by_metric))
        if missing_required:
            errors.append('MISSING_REQUIRED_STATEMENT_METRIC:' + sid)
            for metric in missing_required:
                issues.append(issue_row(readiness, 'REQUIRED_QUARTERLY_METRIC_MISSING_' + metric, 'BLOCKING', 'QUARTERLY_INCOME_STATEMENT', 'CAPTURE_OFFICIAL_SEC_FACT_FOR_' + metric))
        for name, numerator_metric, denominator_metric in ratio_specs:
            if numerator_metric in by_metric and denominator_metric in by_metric:
                if by_metric[denominator_metric]['value'] == 0:
                    issues.append(issue_row(readiness, 'ZERO_DENOMINATOR_' + name, 'BLOCKING', 'DERIVED_METRIC', 'REVIEW_SOURCE_AND_DO_NOT_EMIT_RATIO', 'unknown'))
                else:
                    derived_metrics.append(metric_row(template, name, by_metric[numerator_metric], by_metric[denominator_metric]))
        if required.issubset(by_metric):
            validations.extend([validation_row(readiness['canonical_issuer_id'], sid, template['period_id'], 'GROSS_PROFIT_TIE', by_metric['REVENUE']['value'] - by_metric['COST_OF_REVENUE']['value'], by_metric['GROSS_PROFIT']['value'], 'REVENUE - COST_OF_REVENUE = GROSS_PROFIT'), validation_row(readiness['canonical_issuer_id'], sid, template['period_id'], 'OPERATING_INCOME_TIE', by_metric['GROSS_PROFIT']['value'] - by_metric['OPERATING_EXPENSES']['value'], by_metric['OPERATING_INCOME']['value'], 'GROSS_PROFIT - OPERATING_EXPENSES = OPERATING_INCOME'), validation_row(readiness['canonical_issuer_id'], sid, template['period_id'], 'NET_INCOME_TIE', by_metric['PRETAX_INCOME']['value'] - by_metric['INCOME_TAX_EXPENSE']['value'], by_metric['NET_INCOME']['value'], 'PRETAX_INCOME - INCOME_TAX_EXPENSE = NET_INCOME'), validation_row(readiness['canonical_issuer_id'], sid, template['period_id'], 'OPERATING_EXPENSE_COMPONENT_TIE', by_metric['RESEARCH_AND_DEVELOPMENT']['value'] + by_metric['SELLING_GENERAL_AND_ADMINISTRATIVE']['value'], by_metric['OPERATING_EXPENSES']['value'], 'RESEARCH_AND_DEVELOPMENT + SELLING_GENERAL_AND_ADMINISTRATIVE = OPERATING_EXPENSES')])
        issues.extend([issue_row(readiness, 'TTM_INSUFFICIENT_DISTINCT_QUARTERS', 'BLOCKING', 'TTM_METRIC_LAYER', 'CAPTURE_FOUR_DISTINCT_OFFICIAL_SEC_QUARTERS_BEFORE_TTM_CALCULATION'), issue_row(readiness, 'ANNUAL_FISCAL_YEAR_SOURCE_MISSING', 'BLOCKING', 'ANNUAL_METRIC_LAYER', 'CAPTURE_OFFICIAL_FISCAL_YEAR_OR_10K_FACTS_BEFORE_ANNUAL_METRICS'), issue_row(readiness, 'BALANCE_SHEET_SOURCE_MISSING', 'BLOCKING', 'THREE_STATEMENT_MODEL', 'CAPTURE_OFFICIAL_PERIOD_END_BALANCE_SHEET_FACTS'), issue_row(readiness, 'CASH_FLOW_SOURCE_MISSING', 'BLOCKING', 'THREE_STATEMENT_MODEL', 'CAPTURE_OFFICIAL_CASH_FLOW_FACTS_AND_YTD_TO_QUARTER_BRIDGE')])
        if 'BASIC_EPS' not in by_metric:
            issues.append(issue_row(readiness, 'BASIC_EPS_OPTIONAL_SOURCE_MISSING', 'NON_BLOCKING', 'QUARTERLY_INCOME_STATEMENT', 'CAPTURE_BASIC_EPS_WHEN_DISCLOSED'))
        period_readiness.append({'canonical_security_id': sid, 'canonical_issuer_id': readiness['canonical_issuer_id'], 'symbol': readiness['symbol'], 'research_profile': readiness['research_profile'], 'available_distinct_quarter_count': 1, 'available_period_ids': [template['period_id']], 'quarterly_income_statement_status': 'MODEL_LOADABLE_PARTIAL_INCOME_STATEMENT' if not missing_required and all((row['status'] == 'PASS' for row in validations if row['canonical_security_id'] == sid)) else 'BLOCKED_QA_OR_REQUIRED_METRIC', 'ttm_status': 'BLOCKED_REQUIRES_FOUR_DISTINCT_OFFICIAL_QUARTERS', 'annual_status': 'BLOCKED_REQUIRES_FISCAL_YEAR_OR_10K_SOURCE', 'balance_sheet_status': 'BLOCKED_OFFICIAL_PERIOD_END_FACTS_PENDING', 'cash_flow_status': 'BLOCKED_OFFICIAL_CASH_FLOW_FACTS_PENDING', 'x3c_financial_factor_gate': 'OPEN_QUARTERLY_QUALITY_SANDBOX_ONLY', 'x3c_valuation_gate': 'BLOCKED_TTM_AND_ANNUAL_PENDING', 'candidate_pool_status': 'NOT_AUTHORIZED', 'trade_authority': 'NONE'})
    validations.sort(key=lambda row: row['validation_id'])
    derived_metrics.sort(key=lambda row: (row['canonical_issuer_id'], row['canonical_metric']))
    issues.sort(key=stable_json)
    period_readiness.sort(key=lambda row: row['canonical_security_id'])
    validation_failures = sum((row['status'] != 'PASS' for row in validations))
    if validation_failures > contract['quality_contract']['maximum_validation_failures']:
        errors.append('VALIDATION_FAILURES')
    if len(validations) < len(ready) * contract['quality_contract']['required_validation_equations_per_ready_issuer']:
        errors.append('VALIDATION_CHECK_COUNT')
    if any((row['neutral_fill_used'] for row in normalized)):
        errors.append('NEUTRAL_FILL_USED')
    if errors:
        raise RuntimeError('PREBUILD_OR_QUALITY_ERRORS:' + ','.join(sorted(set(errors))))
    return {'ready_rows': ready, 'normalized': normalized, 'statement_rows': statement_rows, 'derived_metrics': derived_metrics, 'validations': validations, 'issues': issues, 'period_readiness': period_readiness, 'unmapped_tags': unmapped, 'duplicate_source_keys': duplicate_source_keys}
