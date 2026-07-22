from __future__ import annotations

from fmdl6x3b_common import *
from fmdl6x3b_records import build_records

def shard_bundle(domains: list[tuple[str, list[dict[str, Any]], str]], bucket_count: int, generated_at: str) -> tuple[bytes, list[dict[str, Any]]]:
    entries: dict[str, bytes] = {}
    manifest: list[dict[str, Any]] = []
    for domain, rows, key in domains:
        for index in range(bucket_count):
            bucket = f'{index:02X}'
            shard_rows = [row for row in rows if bucket_hex(str(row[key]), bucket_count) == bucket]
            shard_rows.sort(key=stable_json)
            name = f'{domain}/{bucket}.jsonl'
            payload = jsonl_bytes(shard_rows)
            entries[name] = payload
            manifest.append({'shard_id': f'{domain}-{bucket}', 'domain': domain, 'bucket': bucket, 'row_count': len(shard_rows), 'payload_sha256': sha256_bytes(payload), 'generated_at': generated_at, 'quality_status': 'PASS'})
    return (deterministic_zip(entries), manifest)

def build(repo_root: Path, candidate: Path, accepted_at: str, source_commit: str) -> dict[str, Any]:
    contract = validate_contract(repo_root)
    inputs = load_inputs(repo_root, contract)
    records = build_records(inputs, contract)
    contract_sha = sha256_file(repo_root / CONTRACT_PATH)
    readiness_manifest_sha = sha256_file(inputs['readiness_manifest_path'])
    sec_manifest_sha = sha256_file(inputs['sec_manifest_path'])
    release_fingerprint = record_hash('FMDL6X3B_RELEASE', contract_sha, readiness_manifest_sha, sec_manifest_sha)
    release_id = f"FMDL6X3B_{contract['as_of_date'].replace('-', '')}_{release_fingerprint[:12]}"
    candidate.mkdir(parents=True, exist_ok=True)
    bundle, shard_manifest = shard_bundle([('NORMALIZED_SOURCE_FACT', records['normalized'], 'canonical_security_id'), ('CANONICAL_STATEMENT', records['statement_rows'], 'canonical_security_id'), ('DERIVED_METRIC', records['derived_metrics'], 'canonical_security_id'), ('NORMALIZATION_ISSUE', records['issues'], 'canonical_security_id')], contract['quality_contract']['bucket_count'], accepted_at)
    (candidate / 'FMDL6X3B_FINANCIAL_SHARDS.zip').write_bytes(bundle)
    write_json(candidate / 'FMDL6X3B_PERIOD_READINESS.json', records['period_readiness'])
    write_json(candidate / 'FMDL6X3B_VALIDATION_CHECKS.json', records['validations'])
    write_json(candidate / 'FMDL6X3B_MAPPING_REGISTRY.json', contract['tag_mapping'])
    source_ids = sorted({(row['source_id'], row['source_url'], row['accepted_at'], row['fiscal_year'], row['fiscal_period']) for row in records['normalized']})
    source_index = [{'source_id': source_id, 'source_type': 'SEC_OFFICIAL_FILING', 'source_url': url, 'accepted_at': source_accepted_at, 'fiscal_year': fiscal_year, 'fiscal_period': fiscal_period, 'source_rank': 'PRIMARY_OFFICIAL', 'freshness_status': 'CURRENT_FOR_CAPTURED_PERIOD', 'evidence_label': 'fact_source_reported'} for source_id, url, source_accepted_at, fiscal_year, fiscal_period in source_ids]
    write_json(candidate / 'FMDL6X3B_SOURCE_INDEX.json', source_index)
    ready_issuers = len({row['canonical_issuer_id'] for row in records['ready_rows']})
    coverage = {'phase_id': PHASE_ID, 'release_id': release_id, 'input_release_id': contract['entry_gate']['required_release_id'], 'ready_security_count': len(records['ready_rows']), 'ready_issuer_count': ready_issuers, 'source_fact_count': len(records['normalized']), 'canonical_statement_row_count': len(records['statement_rows']), 'derived_metric_row_count': len(records['derived_metrics']), 'validation_check_count': len(records['validations']), 'normalization_issue_count': len(records['issues']), 'quarterly_income_statement_model_loadable_security_count': sum((row['quarterly_income_statement_status'] == 'MODEL_LOADABLE_PARTIAL_INCOME_STATEMENT' for row in records['period_readiness'])), 'ttm_ready_security_count': 0, 'annual_ready_security_count': 0, 'balance_sheet_ready_security_count': 0, 'cash_flow_ready_security_count': 0, 'full_financial_statement_completion_claimed': False, 'ttm_completion_claimed': False, 'annual_completion_claimed': False, 'coverage_status': 'QUARTERLY_INCOME_STATEMENT_BASELINE_WITH_EXPLICIT_TTM_ANNUAL_AND_THREE_STATEMENT_GAPS'}
    write_json(candidate / 'FMDL6X3B_COVERAGE_REPORT.json', coverage)
    validation_failures = sum((row['status'] != 'PASS' for row in records['validations']))
    quality = {'phase_id': PHASE_ID, 'release_id': release_id, 'quality_status': 'PASS', 'ready_security_count': len(records['ready_rows']), 'ready_issuer_count': ready_issuers, 'normalized_source_fact_count': len(records['normalized']), 'unmapped_source_tag_count': len(records['unmapped_tags']), 'duplicate_source_fact_key_count': records['duplicate_source_keys'], 'canonical_statement_row_count': len(records['statement_rows']), 'derived_metric_row_count': len(records['derived_metrics']), 'validation_check_count': len(records['validations']), 'validation_failure_count': validation_failures, 'neutral_fill_row_count': sum((row['neutral_fill_used'] for row in records['normalized'])), 'expected_shard_count': contract['quality_contract']['expected_shard_count'], 'manifested_shard_count': len(shard_manifest), 'ttm_rows_emitted': 0, 'annual_rows_emitted': 0, 'trade_authority': 'NONE', 'zero_mutation_proof': contract['zero_mutation_gate']}
    quality_errors: list[str] = []
    if len(shard_manifest) != contract['quality_contract']['expected_shard_count']:
        quality_errors.append('SHARDS')
    if len(records['normalized']) < contract['quality_contract']['minimum_normalized_source_fact_count']:
        quality_errors.append('SOURCE_FACTS')
    if ready_issuers < contract['quality_contract']['minimum_normalized_ready_issuer_count']:
        quality_errors.append('ISSUERS')
    if quality['unmapped_source_tag_count'] or quality['duplicate_source_fact_key_count']:
        quality_errors.append('SOURCE_INTEGRITY')
    if quality['validation_failure_count'] or quality['neutral_fill_row_count']:
        quality_errors.append('QA')
    if quality_errors:
        quality['quality_status'] = 'FAIL'
        quality['errors'] = quality_errors
    write_json(candidate / 'FMDL6X3B_QUALITY_REPORT.json', quality)
    if quality_errors:
        raise RuntimeError('QUALITY_ERRORS:' + ','.join(quality_errors))
    source_binding = {'phase_id': PHASE_ID, 'release_id': release_id, 'input_release_id': contract['entry_gate']['required_release_id'], 'readiness_manifest_sha256': readiness_manifest_sha, 'sec_manifest_sha256': sec_manifest_sha, 'accepted_authority': 'SEC_OFFICIAL', 'accepted_data_grade': contract['input_contract']['accepted_sec_data_grade'], 'reported_evidence_label': 'fact_source_reported', 'derived_evidence_label': 'derived_calculation', 'missing_evidence_label': 'missing_required_source', 'neutral_fill_used': False, 'silent_source_substitution': False, 'ttm_or_annual_inference_used': False}
    write_json(candidate / 'FMDL6X3B_SOURCE_BINDING.json', source_binding)
    decision = {'phase_id': PHASE_ID, 'status': STATUS, 'release_id': release_id, 'release_sequence': 37, 'accepted_at': accepted_at, 'source_commit': source_commit, 'input_release_id': contract['entry_gate']['required_release_id'], 'next_gate': NEXT_GATE, 'financial_normalization_status': coverage['coverage_status'], 'ready_security_count': len(records['ready_rows']), 'quarterly_model_loadable_security_count': coverage['quarterly_income_statement_model_loadable_security_count'], 'ttm_ready_security_count': 0, 'annual_ready_security_count': 0, 'full_financial_statement_completion_claimed': False, 'research_production_gate': 'OPEN_FOR_FMDL6X3C_QUARTERLY_QUALITY_SANDBOX_ONLY', 'valuation_gate': 'CLOSED_TTM_AND_ANNUAL_PENDING', 'investment_os_candidate_pool_gate': 'CLOSED_NOT_AUTHORIZED_IN_FMDL6X3B', 'simulation_gate': 'CLOSED_NOT_AUTHORIZED_IN_FMDL6X3B', 'brokerage_real_account_gate': 'CLOSED_NO_CHANNEL', 'trade_authority': 'NONE', 'zero_mutation_proof': contract['zero_mutation_gate']}
    write_json(candidate / 'FMDL6X3B_DECISION.json', decision)
    files = {path.name: {'bytes': path.stat().st_size, 'sha256': sha256_file(path)} for path in sorted(candidate.iterdir()) if path.is_file() and path.name != 'FMDL6X3B_MANIFEST.json'}
    manifest = {'phase_id': PHASE_ID, 'release_id': release_id, 'release_sequence': 37, 'generated_at': accepted_at, 'contract_sha256': contract_sha, 'input_manifest_sha256': {'research_universe_readiness': readiness_manifest_sha, 'sec_filings_facts': sec_manifest_sha}, 'files': files, 'shards': shard_manifest}
    write_json(candidate / 'FMDL6X3B_MANIFEST.json', manifest)
    return {'decision': decision, 'coverage': coverage, 'quality': quality, 'manifest': manifest}

def validate_candidate(repo_root: Path, candidate: Path, accepted_at: str, source_commit: str, acceptance_path: Path) -> dict[str, Any]:
    replay = candidate.parent / (candidate.name + '_replay')
    if replay.exists():
        shutil.rmtree(replay)
    build(repo_root, replay, accepted_at, source_commit)
    candidate_files = {path.name: sha256_file(path) for path in candidate.iterdir() if path.is_file()}
    replay_files = {path.name: sha256_file(path) for path in replay.iterdir() if path.is_file()}
    status = 'PASS' if candidate_files == replay_files else 'FAIL'
    result = {'phase_id': PHASE_ID, 'status': status, 'candidate_file_hashes': candidate_files, 'replay_file_hashes': replay_files, 'same_input_byte_replay': candidate_files == replay_files}
    write_json(acceptance_path, result)
    if status != 'PASS':
        raise RuntimeError('CAPTURED_INPUT_REPLAY_FAILED')
    return result

def copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)

def publish(repo_root: Path, candidate: Path, published_at: str, source_commit: str) -> dict[str, Any]:
    contract = validate_contract(repo_root)
    decision = read_json(candidate / 'FMDL6X3B_DECISION.json')
    release_id = decision['release_id']
    current = repo_root / contract['storage_contract']['current_root']
    release = repo_root / contract['storage_contract']['release_root'] / release_id / 'financial_normalization'
    normalized = repo_root / contract['storage_contract']['normalized_root'] / release_id
    archive_root = repo_root / contract['storage_contract']['archive_root']
    incoming = {path.name: sha256_file(path) for path in candidate.iterdir() if path.is_file()}
    if release.exists():
        existing = {path.name: sha256_file(path) for path in release.iterdir() if path.is_file()}
        if existing != incoming:
            raise RuntimeError('IMMUTABLE_RELEASE_COLLISION')
    if current.exists():
        old_decision = read_json(current / 'FMDL6X3B_DECISION.json')
        archive = archive_root / old_decision['release_id'] / 'financial_normalization'
        if not archive.exists():
            copy_tree(current, archive)
    if not release.exists():
        copy_tree(candidate, release)
    copy_tree(candidate, normalized)
    copy_tree(candidate, current)
    for name in ('FMDL6X3B_DECISION.json', 'FMDL6X3B_MANIFEST.json'):
        if (current / name).read_bytes() != (release / name).read_bytes():
            raise RuntimeError('CURRENT_RELEASE_PARITY_FAILED')
    manifest_hash = sha256_file(current / 'FMDL6X3B_MANIFEST.json')
    pointer = {'phase_id': PHASE_ID, 'status': STATUS, 'published_at': published_at, 'source_commit': source_commit, 'release_id': release_id, 'release_sequence': 37, 'current_path': contract['storage_contract']['current_root'], 'release_path': str(release.relative_to(repo_root)), 'normalized_path': str(normalized.relative_to(repo_root)), 'manifest_sha256': manifest_hash, 'input_release_id': decision['input_release_id'], 'financial_normalization_status': decision['financial_normalization_status'], 'quarterly_model_loadable_security_count': decision['quarterly_model_loadable_security_count'], 'ttm_ready_security_count': 0, 'annual_ready_security_count': 0, 'next_gate': NEXT_GATE, 'research_production_gate': decision['research_production_gate'], 'valuation_gate': decision['valuation_gate'], 'investment_os_candidate_pool_gate': decision['investment_os_candidate_pool_gate'], 'brokerage_real_account_gate': 'CLOSED_NO_CHANNEL', 'trade_authority': 'NONE', 'zero_mutation_proof': decision['zero_mutation_proof']}
    write_json(repo_root / contract['storage_contract']['last_success_pointer'], pointer)
    lkg = dict(pointer)
    lkg['lkg_scope'] = 'FMDL6X3_FINANCIAL_NORMALIZATION_DOMAIN'
    lkg['lkg_reason'] = 'LATEST_ACCEPTED_AUDITABLE_FINANCIAL_NORMALIZATION_BASELINE'
    write_json(repo_root / contract['storage_contract']['lkg_pointer'], lkg)
    return pointer

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo-root', default='.')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('validate-contract')
    build_parser = sub.add_parser('build')
    build_parser.add_argument('--candidate', required=True)
    build_parser.add_argument('--accepted-at', required=True)
    build_parser.add_argument('--source-commit', required=True)
    validate_parser = sub.add_parser('validate-candidate')
    validate_parser.add_argument('--candidate', required=True)
    validate_parser.add_argument('--accepted-at', required=True)
    validate_parser.add_argument('--source-commit', required=True)
    validate_parser.add_argument('--acceptance', required=True)
    publish_parser = sub.add_parser('publish')
    publish_parser.add_argument('--candidate', required=True)
    publish_parser.add_argument('--published-at', required=True)
    publish_parser.add_argument('--source-commit', required=True)
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    if args.command == 'validate-contract':
        validate_contract(root)
    elif args.command == 'build':
        build(root, root / args.candidate, args.accepted_at, args.source_commit)
    elif args.command == 'validate-candidate':
        validate_candidate(root, root / args.candidate, args.accepted_at, args.source_commit, root / args.acceptance)
    elif args.command == 'publish':
        publish(root, root / args.candidate, args.published_at, args.source_commit)
if __name__ == '__main__':
    main()
