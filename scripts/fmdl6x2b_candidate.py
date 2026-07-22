from __future__ import annotations

import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from fmdl6x2b_classification import enrich_identity
from fmdl6x2b_common import (
    CONTRACT_PATH, EXIT_STATUS, NEXT_GATE, PHASE_ID, bucket_hex, copytree_replace,
    deterministic_gzip, deterministic_zip, load_json, read_gzip_jsonl,
    read_zip_jsonl, record_hash, sha256_bytes, sha256_file, stable_json, validate_contract, write_json,
)


def _jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    return ''.join(stable_json(row) + '\n' for row in rows).encode('utf-8')


def load_input(repo_root: Path) -> dict[str, Any]:
    contract = load_json(repo_root / CONTRACT_PATH)
    root = repo_root / contract['input_contract']['current_security_master_root']
    return {
        'contract': contract,
        'input_root': root,
        'decision': load_json(root / 'FMDL6X2A_DECISION.json'),
        'quality': load_json(root / 'FMDL6X2A_QUALITY_REPORT.json'),
        'manifest': load_json(root / 'FMDL6X2A_MANIFEST.json'),
        'securities': read_zip_jsonl(root / 'FMDL6X2A_SECURITY_MASTER_SHARDS.zip'),
        'inherited_quarantine': read_gzip_jsonl(root / 'FMDL6X2A_QUARANTINE.jsonl.gz'),
    }


def build_records(input_data: dict[str, Any]) -> dict[str, Any]:
    enriched = [enrich_identity(row) for row in input_data['securities']]
    enriched.sort(key=lambda row: (row['venue'], row['symbol'], row['canonical_listing_id']))

    issuer_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    share_class_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in enriched:
        issuer_groups[row['canonical_issuer_id']].append(row)
        if row.get('canonical_share_class_id'):
            share_class_groups[row['canonical_share_class_id']].append(row)

    issuers: list[dict[str, Any]] = []
    for issuer_id, rows in sorted(issuer_groups.items()):
        names = sorted({row['issuer_display_name_directory_derived'] for row in rows})
        normalized_keys = sorted({row['issuer_normalized_key'] for row in rows})
        venues = sorted({row['venue'] for row in rows})
        types = sorted({row['instrument_type'] for row in rows})
        issuers.append({
            'canonical_issuer_id': issuer_id,
            'canonical_id_status': 'PROVISIONAL_DIRECTORY_DERIVED_MERGEABLE',
            'issuer_display_name': names[0],
            'issuer_display_name_variants': names,
            'issuer_normalized_keys': normalized_keys,
            'issuer_identity_confidence': 'MEDIUM' if all(row['issuer_identity_confidence'] == 'MEDIUM' for row in rows) else 'LOW',
            'sec_cik10': None,
            'sec_identity_status': 'PENDING_OFFICIAL_SEC_EVIDENCE',
            'security_record_count': len(rows),
            'venues': venues,
            'instrument_types': types,
            'cross_market_review_required': len(venues) > 1,
            'identity_merge_policy': 'ALIAS_AND_SUPERSESSION_NO_DESTRUCTIVE_REKEY',
            'source_authorities': sorted({row['source_authority'] for row in rows}),
            'source_snapshot_ids': sorted({row['source_snapshot_id'] for row in rows}),
        })

    share_classes: list[dict[str, Any]] = []
    for class_id, rows in sorted(share_class_groups.items()):
        share_classes.append({
            'canonical_share_class_id': class_id,
            'canonical_issuer_id': rows[0]['canonical_issuer_id'],
            'share_class_token': rows[0]['share_class_token'],
            'canonical_id_status': 'PROVISIONAL_DIRECTORY_DERIVED_MERGEABLE',
            'security_record_count': len(rows),
            'instrument_types': sorted({row['instrument_type'] for row in rows}),
            'venues': sorted({row['venue'] for row in rows}),
        })

    security_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in enriched:
        security_groups[row['canonical_security_id']].append(row)
    securities: list[dict[str, Any]] = []
    for security_id, rows in sorted(security_groups.items()):
        first = rows[0]
        securities.append({
            'canonical_security_id': security_id,
            'canonical_issuer_id': first['canonical_issuer_id'],
            'canonical_share_class_id': first['canonical_share_class_id'],
            'canonical_id_status': first['canonical_id_status'],
            'instrument_type': first['instrument_type'],
            'classification_confidence': first['classification_confidence'],
            'classification_basis': first['classification_basis'],
            'classification_rule_version': first['classification_rule_version'],
            'research_status': first['research_status'],
            'research_profile': first['research_profile'],
            'sec_identity_status': first['sec_identity_status'],
            'identity_resolution_status': first['identity_resolution_status'],
            'identity_merge_policy': first['identity_merge_policy'],
            'official_security_name': first['official_security_name'],
            'official_security_name_variants': sorted({row['official_security_name'] for row in rows}),
            'issuer_display_name_directory_derived': first['issuer_display_name_directory_derived'],
            'issuer_normalized_key': first['issuer_normalized_key'],
            'share_class_token': first['share_class_token'],
            'listing_count': len(rows),
            'venues': sorted({row['venue'] for row in rows}),
            'symbols': sorted({row['symbol'] for row in rows}),
            'source_row_ids': sorted({row['source_row_id'] for row in rows}),
            'source_snapshot_ids': sorted({row['source_snapshot_id'] for row in rows}),
            'source_authorities': sorted({row['source_authority'] for row in rows}),
            'etf_flag': any(row['etf_flag'] for row in rows),
            'test_issue': any(row['test_issue'] for row in rows),
            'channel_status': first['channel_status'],
            'portfolio_status': first['portfolio_status'],
            'trade_authority': first['trade_authority'],
        })

    listings: list[dict[str, Any]] = []
    for row in enriched:
        listings.append({
            'canonical_listing_id': row['canonical_listing_id'],
            'canonical_security_id': row['canonical_security_id'],
            'canonical_issuer_id': row['canonical_issuer_id'],
            'venue': row['venue'], 'symbol': row['symbol'],
            'listing_lifecycle_status': row['listing_lifecycle_status'],
            'effective_date_confidence': row['effective_date_confidence'],
            'observation_date': row['observation_date'],
            'source_exchange_code': row['source_exchange_code'],
            'market_category': row['market_category'], 'financial_status': row['financial_status'],
            'round_lot_size': row['round_lot_size'], 'cqs_symbol': row['cqs_symbol'],
            'nasdaq_symbol': row['nasdaq_symbol'], 'active_listing_observation_key': row['active_listing_observation_key'],
            'source_row_id': row['source_row_id'], 'source_snapshot_id': row['source_snapshot_id'],
            'source_authority': row['source_authority'], 'canonical_id_status': row['canonical_id_status'],
        })

    cross_market: list[dict[str, Any]] = []
    for issuer in issuers:
        if issuer['cross_market_review_required']:
            rows = issuer_groups[issuer['canonical_issuer_id']]
            cross_market.append({
                'cross_market_group_id': 'USXMK-' + record_hash('CROSS_MARKET', issuer['canonical_issuer_id'])[:24],
                'canonical_issuer_id': issuer['canonical_issuer_id'],
                'issuer_display_name': issuer['issuer_display_name'],
                'venues': issuer['venues'],
                'symbols': sorted({row['symbol'] for row in rows}),
                'security_ids': sorted({row['canonical_security_id'] for row in rows}),
                'status': 'REVIEW_REQUIRED_OFFICIAL_IDENTITY_NOT_CONFIRMED',
            })

    queues: dict[str, list[dict[str, Any]]] = {
        'ADR_UNDERLYING_DEPOSITARY_AND_RATIO_QUEUE': [],
        'SPECIAL_INSTRUMENT_CLASSIFICATION_QUEUE': [],
        'CLASSIFICATION_AMBIGUITY_QUEUE': [],
        'SEC_OFFICIAL_IDENTITY_PENDING_QUEUE': [],
        'CROSS_MARKET_ISSUER_REVIEW_QUEUE': [],
        'INHERITED_SOURCE_SCOPE_QUARANTINE': list(input_data['inherited_quarantine']),
    }
    for row in enriched:
        base = {
            'canonical_issuer_id': row['canonical_issuer_id'], 'canonical_security_id': row['canonical_security_id'],
            'canonical_listing_id': row['canonical_listing_id'], 'venue': row['venue'], 'symbol': row['symbol'],
            'official_security_name': row['official_security_name'], 'instrument_type': row['instrument_type'],
            'research_status': row['research_status'], 'research_profile': row['research_profile'],
            'source_row_id': row['source_row_id'], 'source_snapshot_id': row['source_snapshot_id'],
        }
        if row['instrument_type'] == 'ADR_OR_ADS':
            queues['ADR_UNDERLYING_DEPOSITARY_AND_RATIO_QUEUE'].append({**base, 'required_evidence': ['SEC_FILING', 'ISSUER_OFFICIAL', 'DEPOSITARY_OFFICIAL']})
        if row['research_status'] == 'RESEARCH_ELIGIBLE_SPECIAL_PROFILE':
            queues['SPECIAL_INSTRUMENT_CLASSIFICATION_QUEUE'].append({**base, 'required_action': 'CONFIRM_SPECIAL_PROFILE_AND_EXCLUDE_FROM_STANDARD_INDUSTRIAL_RANKING'})
        if row['instrument_type'] in {'UNRESOLVED_LISTED_SECURITY', 'UNIT_UNRESOLVED', 'COMMON_UNIT_UNRESOLVED'}:
            queues['CLASSIFICATION_AMBIGUITY_QUEUE'].append({**base, 'required_action': 'OBTAIN_OFFICIAL_SECURITY_DESCRIPTION'})
        if row['research_status'] in {'RESEARCH_REVIEW_REQUIRED', 'RESEARCH_ELIGIBLE_SPECIAL_PROFILE'}:
            queues['SEC_OFFICIAL_IDENTITY_PENDING_QUEUE'].append({**base, 'required_action': 'RESOLVE_CIK_AND_REPORTING_PROFILE_FROM_SEC_OFFICIAL_EVIDENCE'})
    for group in cross_market:
        queues['CROSS_MARKET_ISSUER_REVIEW_QUEUE'].append(group)
    for rows in queues.values():
        rows.sort(key=lambda row: stable_json(row))

    return {
        'enriched': enriched, 'issuers': issuers, 'share_classes': share_classes,
        'securities': securities, 'listings': listings, 'cross_market': cross_market, 'queues': queues,
    }


def build_identity_zip(records: dict[str, Any], bucket_count: int, accepted_at: str, observation_date: str) -> tuple[bytes, list[dict[str, Any]]]:
    entries: dict[str, bytes] = {}
    manifest: list[dict[str, Any]] = []

    def add_domain(domain: str, rows: list[dict[str, Any]], key_field: str, venue_partition: bool = False) -> None:
        if venue_partition:
            for venue in ['XNAS', 'XNYS', 'XASE']:
                venue_rows = [row for row in rows if row.get('venue') == venue]
                for bucket in range(bucket_count):
                    bid = f'{bucket:02X}'
                    shard_rows = [row for row in venue_rows if bucket_hex(str(row[key_field]), bucket_count) == bid]
                    shard_rows.sort(key=lambda row: str(row[key_field]))
                    name = f'{domain}/{venue}/{bid}.jsonl'
                    payload = _jsonl_bytes(shard_rows)
                    entries[name] = payload
                    manifest.append(_shard_manifest(domain, f'{domain}-{venue}-{bid}', name, payload, len(shard_rows), accepted_at, observation_date, venue, bid))
        else:
            for bucket in range(bucket_count):
                bid = f'{bucket:02X}'
                shard_rows = [row for row in rows if bucket_hex(str(row[key_field]), bucket_count) == bid]
                shard_rows.sort(key=lambda row: str(row[key_field]))
                name = f'{domain}/{bid}.jsonl'
                payload = _jsonl_bytes(shard_rows)
                entries[name] = payload
                manifest.append(_shard_manifest(domain, f'{domain}-{bid}', name, payload, len(shard_rows), accepted_at, observation_date, None, bid))

    add_domain('ISSUER', records['issuers'], 'canonical_issuer_id')
    add_domain('SHARE_CLASS', records['share_classes'], 'canonical_share_class_id')
    add_domain('SECURITY', records['securities'], 'canonical_security_id')
    add_domain('LISTING', records['listings'], 'canonical_listing_id', venue_partition=True)
    add_domain('CROSS_MARKET', records['cross_market'], 'cross_market_group_id')
    return deterministic_zip(entries), manifest


def _shard_manifest(domain: str, shard_id: str, name: str, payload: bytes, count: int, accepted_at: str, observation_date: str, venue: str | None, bucket: str) -> dict[str, Any]:
    return {
        'domain': domain, 'shard_id': shard_id, 'zip_member': name, 'venue': venue, 'bucket': bucket,
        'row_count': count, 'schema_version': 'fmdl6x2b.identity.v1', 'payload_sha256': sha256_bytes(payload),
        'generated_at': accepted_at, 'observation_date': observation_date, 'quality_status': 'PASS',
    }


def build_candidate(repo_root: Path, candidate_root: Path, accepted_at: str, source_commit: str) -> dict[str, Any]:
    checks, contract_errors = validate_contract(repo_root)
    if contract_errors:
        raise RuntimeError('CONTRACT_ERRORS:' + ','.join(contract_errors))
    input_data = load_input(repo_root)
    records = build_records(input_data)
    contract = input_data['contract']
    observation_date = input_data['decision']['observation_date']
    contract_sha = sha256_file(repo_root / CONTRACT_PATH)
    input_manifest_sha = sha256_file(input_data['input_root'] / 'FMDL6X2A_MANIFEST.json')
    release_fingerprint = record_hash('FMDL6X2B_RELEASE', contract_sha, input_manifest_sha)
    release_id = f"FMDL6X2B_{observation_date.replace('-', '')}_{release_fingerprint[:12]}"
    bucket_count = int(contract['storage_contract']['bucket_count'])
    identity_zip, shard_manifest = build_identity_zip(records, bucket_count, accepted_at, observation_date)
    review_zip = deterministic_zip({name + '.jsonl': _jsonl_bytes(rows) for name, rows in records['queues'].items()})

    candidate_root.mkdir(parents=True, exist_ok=True)
    (candidate_root / 'FMDL6X2B_IDENTITY_SHARDS.zip').write_bytes(identity_zip)
    (candidate_root / 'FMDL6X2B_REVIEW_QUEUES.zip').write_bytes(review_zip)
    (candidate_root / 'FMDL6X2B_IDENTITY_LINEAGE.jsonl.gz').write_bytes(deterministic_gzip(records['enriched']))

    status_counts = Counter(row['research_status'] for row in records['enriched'])
    type_counts = Counter(row['instrument_type'] for row in records['enriched'])
    queue_counts = {name: len(rows) for name, rows in records['queues'].items()}
    summary = {
        'phase_id': PHASE_ID, 'release_id': release_id, 'observation_date': observation_date,
        'input_security_records': len(records['enriched']), 'issuer_records': len(records['issuers']),
        'share_class_records': len(records['share_classes']), 'security_records': len(records['securities']),
        'listing_records': len(records['listings']), 'cross_market_groups': len(records['cross_market']),
        'research_status_counts': dict(sorted(status_counts.items())),
        'instrument_type_counts': dict(sorted(type_counts.items())), 'review_queue_counts': dict(sorted(queue_counts.items())),
        'canonical_id_status': 'PROVISIONAL_DIRECTORY_DERIVED_MERGEABLE',
        'sec_identity_completion_claimed': False,
    }
    write_json(candidate_root / 'FMDL6X2B_CLASSIFICATION_SUMMARY.json', summary)

    listing_ids = [row['canonical_listing_id'] for row in records['listings']]
    security_ids = [row['canonical_security_id'] for row in records['securities']]
    issuer_ids = [row['canonical_issuer_id'] for row in records['issuers']]
    quality = {
        'phase_id': PHASE_ID, 'release_id': release_id, 'quality_status': 'PASS',
        'input_security_records_expected': input_data['decision']['included_security_records'],
        'input_security_records_accounted': len(records['enriched']),
        'input_inherited_quarantine_expected': input_data['decision']['quarantined_rows'],
        'input_inherited_quarantine_preserved': len(records['queues']['INHERITED_SOURCE_SCOPE_QUARANTINE']),
        'canonical_issuer_ids_issued': len(issuer_ids), 'canonical_share_class_ids_issued': len(records['share_classes']),
        'canonical_security_ids_issued': len(security_ids), 'canonical_listing_ids_issued': len(listing_ids),
        'duplicate_canonical_security_ids': len(security_ids) - len(set(security_ids)),
        'duplicate_canonical_listing_ids': len(listing_ids) - len(set(listing_ids)),
        'duplicate_issuer_master_ids': len(issuer_ids) - len(set(issuer_ids)),
        'identity_shard_count': len(shard_manifest),
        'review_queue_count': len(records['queues']), 'review_queue_rows': sum(queue_counts.values()),
        'fuzzy_issuer_merges': 0, 'sec_cik_values_inferred_without_official_evidence': 0,
        'trade_authority': 'NONE',
        'zero_mutation_proof': {'candidate_pool_mutations': 0, 'simulation_mutations': 0, 'real_account_mutations': 0, 'orders': 0},
    }
    expected_shards = bucket_count * (1 + 1 + 1 + 3 + 1)
    errors = []
    if quality['input_security_records_accounted'] != quality['input_security_records_expected']:
        errors.append('INPUT_SECURITY_COUNT')
    if quality['input_inherited_quarantine_preserved'] != quality['input_inherited_quarantine_expected']:
        errors.append('INHERITED_QUARANTINE')
    if quality['duplicate_canonical_security_ids'] != 0:
        errors.append('DUPLICATE_SECURITY_IDS')
    if quality['duplicate_canonical_listing_ids'] != 0:
        errors.append('DUPLICATE_LISTING_IDS')
    if quality['duplicate_issuer_master_ids'] != 0:
        errors.append('DUPLICATE_ISSUER_IDS')
    if quality['identity_shard_count'] != expected_shards:
        errors.append('SHARD_COUNT')
    if errors:
        quality['quality_status'] = 'FAIL'
        quality['errors'] = errors
        write_json(candidate_root / 'FMDL6X2B_QUALITY_REPORT.json', quality)
        raise RuntimeError('QUALITY_ERRORS:' + ','.join(errors))
    write_json(candidate_root / 'FMDL6X2B_QUALITY_REPORT.json', quality)

    decision = {
        'phase_id': PHASE_ID, 'status': EXIT_STATUS, 'release_id': release_id,
        'release_sequence': contract['storage_contract']['release_sequence'], 'accepted_at': accepted_at,
        'observation_date': observation_date, 'source_commit': source_commit,
        'input_release_id': input_data['decision']['release_id'], 'next_gate': NEXT_GATE,
        'canonical_id_status': 'PROVISIONAL_DIRECTORY_DERIVED_MERGEABLE',
        'issuer_records': len(records['issuers']), 'security_records': len(records['securities']),
        'listing_records': len(records['listings']), 'cross_market_groups': len(records['cross_market']),
        'sec_identity_status': 'PENDING_OFFICIAL_SEC_EVIDENCE',
        'research_production_gate': 'OPEN_FOR_FMDL6X2_DATA_PRODUCTION',
        'brokerage_real_account_gate': 'CLOSED_NO_CHANNEL',
        'channel_eligibility_default': 'CHANNEL_ELIGIBILITY_PENDING',
        'portfolio_admission_default': 'PORTFOLIO_ADMISSION_NOT_AUTHORIZED', 'trade_authority': 'NONE',
        'zero_mutation_proof': quality['zero_mutation_proof'],
    }
    write_json(candidate_root / 'FMDL6X2B_DECISION.json', decision)

    source_binding = {
        'phase_id': PHASE_ID, 'release_id': release_id,
        'input_release_id': input_data['decision']['release_id'],
        'input_manifest_sha256': input_manifest_sha,
        'input_identity_shards_sha256': sha256_file(input_data['input_root'] / 'FMDL6X2A_SECURITY_MASTER_SHARDS.zip'),
        'input_quarantine_sha256': sha256_file(input_data['input_root'] / 'FMDL6X2A_QUARANTINE.jsonl.gz'),
        'source_authority': 'NASDAQ_OFFICIAL_VIA_ACCEPTED_FMDL6X2A',
        'sec_official_evidence_bundle_present': False,
        'sec_identity_completion_claimed': False,
        'silent_source_substitution': False,
    }
    write_json(candidate_root / 'FMDL6X2B_SOURCE_BINDING.json', source_binding)

    manifest_files = {}
    for path in sorted(candidate_root.iterdir()):
        if path.name == 'FMDL6X2B_MANIFEST.json' or not path.is_file():
            continue
        manifest_files[path.name] = {'bytes': path.stat().st_size, 'sha256': sha256_file(path)}
    manifest = {
        'phase_id': PHASE_ID, 'release_id': release_id, 'release_sequence': contract['storage_contract']['release_sequence'],
        'generated_at': accepted_at, 'contract_sha256': contract_sha, 'input_manifest_sha256': input_manifest_sha,
        'files': manifest_files, 'shards': shard_manifest,
    }
    write_json(candidate_root / 'FMDL6X2B_MANIFEST.json', manifest)
    return {'release_id': release_id, 'summary': summary, 'quality': quality, 'decision': decision, 'contract_checks': checks}


def validate_candidate(repo_root: Path, candidate_root: Path, accepted_at: str, source_commit: str, acceptance_path: Path) -> dict[str, Any]:
    replay_root = candidate_root.parent / (candidate_root.name + '_replay')
    if replay_root.exists():
        shutil.rmtree(replay_root)
    build_candidate(repo_root, replay_root, accepted_at, source_commit)
    left = {p.name: sha256_file(p) for p in candidate_root.iterdir() if p.is_file()}
    right = {p.name: sha256_file(p) for p in replay_root.iterdir() if p.is_file()}
    errors = []
    if left != right:
        errors.append('SAME_INPUT_REPLAY_MISMATCH')
    manifest = load_json(candidate_root / 'FMDL6X2B_MANIFEST.json')
    for name, meta in manifest['files'].items():
        path = candidate_root / name
        if not path.is_file() or sha256_file(path) != meta['sha256'] or path.stat().st_size != meta['bytes']:
            errors.append('MANIFEST_FILE:' + name)
    quality = load_json(candidate_root / 'FMDL6X2B_QUALITY_REPORT.json')
    if quality.get('quality_status') != 'PASS':
        errors.append('QUALITY_STATUS')
    decision = load_json(candidate_root / 'FMDL6X2B_DECISION.json')
    if decision.get('trade_authority') != 'NONE':
        errors.append('TRADE_AUTHORITY')
    result = {
        'phase_id': PHASE_ID, 'status': 'PASS' if not errors else 'FAIL', 'errors': errors,
        'validation_check_count': len(manifest['files']) + 4, 'same_input_replay': 'PASS' if left == right else 'FAIL',
        'candidate_file_count': len(left), 'release_id': decision['release_id'],
    }
    write_json(acceptance_path, result)
    if errors:
        raise RuntimeError('VALIDATION_ERRORS:' + ','.join(errors))
    return result


def publish(repo_root: Path, candidate_root: Path, published_at: str, source_commit: str) -> dict[str, Any]:
    decision = load_json(candidate_root / 'FMDL6X2B_DECISION.json')
    release_id = decision['release_id']
    current = repo_root / 'outputs/fmdl6x2/current/identity'
    release = repo_root / f'datasets/fmdl6x2/releases/{release_id}/identity'
    normalized = repo_root / f'datasets/fmdl6x2/normalized/identity/{release_id}'
    archive = repo_root / f'outputs/fmdl6x2/archive/{published_at.replace(":", "").replace("-", "")}/identity'
    if release.exists():
        raise RuntimeError('IMMUTABLE_RELEASE_COLLISION')
    if current.exists():
        copytree_replace(current, archive)
    copytree_replace(candidate_root, current)
    copytree_replace(candidate_root, release)
    copytree_replace(candidate_root, normalized)
    current_manifest_sha = sha256_file(current / 'FMDL6X2B_MANIFEST.json')
    if current_manifest_sha != sha256_file(release / 'FMDL6X2B_MANIFEST.json'):
        raise RuntimeError('CURRENT_RELEASE_MANIFEST_MISMATCH')
    pointer = {
        'phase_id': PHASE_ID, 'status': EXIT_STATUS, 'release_id': release_id,
        'release_sequence': decision['release_sequence'], 'published_at': published_at, 'source_commit': source_commit,
        'current_path': str(current.relative_to(repo_root)), 'release_path': str(release.relative_to(repo_root)),
        'normalized_path': str(normalized.relative_to(repo_root)), 'manifest_sha256': current_manifest_sha,
        'issuer_records': decision['issuer_records'], 'security_records': decision['security_records'],
        'listing_records': decision['listing_records'], 'cross_market_groups': decision['cross_market_groups'],
        'canonical_id_status': decision['canonical_id_status'], 'sec_identity_status': decision['sec_identity_status'],
        'next_gate': NEXT_GATE, 'research_production_gate': decision['research_production_gate'],
        'brokerage_real_account_gate': decision['brokerage_real_account_gate'], 'trade_authority': 'NONE',
    }
    write_json(repo_root / 'outputs/status/FMDL6X2B_LAST_SUCCESS.json', pointer)
    lkg = dict(pointer)
    lkg.update({'lkg_scope': 'IDENTITY_CLASSIFICATION_DOMAIN', 'lkg_reason': 'LATEST_ACCEPTED_COMPLETE_IDENTITY_CLASSIFICATION_AND_REVIEW_QUEUES'})
    write_json(repo_root / 'outputs/status/FMDL6X2_IDENTITY_LKG.json', lkg)
    return pointer
