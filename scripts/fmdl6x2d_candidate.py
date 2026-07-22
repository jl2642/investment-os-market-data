from __future__ import annotations

import shutil
from collections import Counter
from pathlib import Path
from typing import Any

from fmdl6x2d_common import (
    CONTRACT_PATH, EXIT_STATUS, NEXT_GATE, PHASE_ID, copytree_replace, deterministic_gzip,
    load_json, record_hash, sha256_file, validate_contract, write_json,
)
from fmdl6x2d_market import (
    IDENTITY_ROOT, _read_raw, build_fx, build_shards, load_security_universe, reconcile_market, select_cohort,
)


def build_candidate(repo_root: Path, raw_root: Path, candidate_root: Path, accepted_at: str, source_commit: str) -> dict[str, Any]:
    checks, contract_errors = validate_contract(repo_root)
    if contract_errors:
        raise RuntimeError('CONTRACT_ERRORS:' + ','.join(contract_errors))
    contract = load_json(repo_root / CONTRACT_PATH)
    securities, listings = load_security_universe(repo_root)
    cohort, queued = select_cohort(securities, listings, contract)
    entries, route_obs = _read_raw(raw_root)
    bars, events, accepted, quarantine = reconcile_market(cohort, entries, route_obs)
    fx, frankfurter = build_fx(entries)
    contract_sha = sha256_file(repo_root / CONTRACT_PATH)
    input_manifest_sha = sha256_file(repo_root / IDENTITY_ROOT / 'FMDL6X2B_MANIFEST.json')
    raw_manifest_sha = sha256_file(raw_root / 'FMDL6X2D_ROUTE_OBSERVATIONS.json')
    release_fingerprint = record_hash('FMDL6X2D_RELEASE', contract_sha, input_manifest_sha, raw_manifest_sha)
    release_id = f"FMDL6X2D_20260722_{release_fingerprint[:12]}"
    candidate_root.mkdir(parents=True, exist_ok=True)
    market_zip, fx_zip, shards = build_shards(bars, events, fx, int(contract['storage_contract']['bucket_count']), accepted_at)
    (candidate_root / 'FMDL6X2D_MARKET_SHARDS.zip').write_bytes(market_zip)
    (candidate_root / 'FMDL6X2D_FX_SHARDS.zip').write_bytes(fx_zip)
    (candidate_root / 'FMDL6X2D_BACKFILL_QUEUE.jsonl.gz').write_bytes(deterministic_gzip(queued))
    (candidate_root / 'FMDL6X2D_MARKET_QUARANTINE.jsonl.gz').write_bytes(deterministic_gzip(quarantine))
    write_json(candidate_root / 'FMDL6X2D_INITIAL_COHORT.json', {'selection_method':contract['market_contract']['cohort_selection'],'cohort_size':len(cohort),'securities':cohort})
    coverage = {'phase_id':PHASE_ID,'release_id':release_id,'universe_security_count':len(securities),'initial_cohort_count':len(cohort),'accepted_dual_route_security_count':len(accepted),'quarantined_cohort_count':len(quarantine),'backfill_queue_count':len(queued),'market_bar_count':len(bars),'corporate_action_count':len(events),'fx_row_count':len(fx),'full_universe_market_history_claimed':False,'market_data_grade':'NON_DECISION_GRADE_FALLBACK','backfill_start_date':contract['market_contract']['backfill_start_date'],'backfill_end_date':contract['market_contract']['backfill_end_date'],'accepted_security_coverage':[{'canonical_security_id':r['canonical_security_id'],'symbol':r['selected_symbol'],'venue':r['venue'],'bar_count':r['bar_count'],'event_count':r['event_count'],'first_date':r['first_date'],'last_date':r['last_date'],'currency':r['currency']} for r in accepted]}
    write_json(candidate_root / 'FMDL6X2D_COVERAGE_REPORT.json', coverage)
    write_json(candidate_root / 'FMDL6X2D_ROUTE_OBSERVATIONS.json', route_obs)
    write_json(candidate_root / 'FMDL6X2D_FX_SUPPORT_REPORT.json', frankfurter)
    duplicate_bar_keys = len(bars) - len({(r['canonical_security_id'],r['date']) for r in bars})
    invalid_ohlc = sum(1 for r in bars if any(r[k] is None for k in ('open','high','low','close')) or r['high'] < max(r['open'],r['close'],r['low']) or r['low'] > min(r['open'],r['close'],r['high']) or (r['volume'] is not None and r['volume'] < 0))
    min_dual = int(contract['acceptance_gates']['dual_route_minimum_accepted_securities'])
    fx_counts = Counter(r['pair'] for r in fx)
    route_observations = route_obs['route_observations']
    ecb_archives = [o for o in route_observations if o['route_id'] == 'ECB_EUROFXREF_HIST_ZIP']
    ecb_archive_failures = [o for o in ecb_archives if not o.get('success')]
    quality = {'phase_id':PHASE_ID,'release_id':release_id,'quality_status':'PASS','universe_expected':contract['market_contract']['universe_size_expected'],'universe_accounted':len(cohort)+len(queued),'cohort_expected':contract['acceptance_gates']['cohort_size'],'cohort_selected':len(cohort),'accepted_dual_route_securities':len(accepted),'minimum_required':min_dual,'quarantined_cohort_securities':len(quarantine),'duplicate_market_bar_keys':duplicate_bar_keys,'invalid_ohlcv_rows':invalid_ohlc,'market_bar_count':len(bars),'corporate_action_count':len(events),'fx_pair_counts':dict(sorted(fx_counts.items())),'ecb_official_archives_observed':len(ecb_archives),'ecb_official_archive_failures':len(ecb_archive_failures),'manifested_shard_count':len(shards),'expected_shard_count':17*64*2+17+17*2,'fabricated_market_rows':0,'full_universe_market_history_claimed':False,'trade_authority':'NONE','zero_mutation_proof':contract['zero_mutation_gate']}
    errors=[]
    if quality['universe_accounted'] != quality['universe_expected']: errors.append('UNIVERSE_ACCOUNTING')
    if quality['cohort_selected'] != quality['cohort_expected']: errors.append('COHORT_SIZE')
    if quality['accepted_dual_route_securities'] < min_dual: errors.append('DUAL_ROUTE_COVERAGE')
    if duplicate_bar_keys: errors.append('DUPLICATE_BAR_KEYS')
    if invalid_ohlc: errors.append('INVALID_OHLCV')
    if quality['ecb_official_archives_observed'] != contract['acceptance_gates']['ecb_official_archives_required']: errors.append('ECB_ARCHIVE_ACCOUNTING')
    if quality['ecb_official_archive_failures'] > contract['acceptance_gates']['ecb_official_archive_failures_allowed']: errors.append('ECB_ARCHIVE_FAILURE')
    if any(fx_counts.get(pair,0) < 3000 for pair in ('USD_CNY','USD_HKD')): errors.append('FX_COVERAGE')
    if quality['manifested_shard_count'] != quality['expected_shard_count']: errors.append('SHARD_COUNT')
    if errors:
        quality['quality_status']='FAIL'; quality['errors']=errors
    write_json(candidate_root / 'FMDL6X2D_QUALITY_REPORT.json', quality)
    if errors:
        raise RuntimeError('QUALITY_ERRORS:' + ','.join(errors))
    decision={'phase_id':PHASE_ID,'status':EXIT_STATUS,'release_id':release_id,'release_sequence':33,'accepted_at':accepted_at,'source_commit':source_commit,'input_release_id':'FMDL6X2C_20260722_e55a579723f1','next_gate':NEXT_GATE,'market_store_status':'PARTIAL_NON_DECISION_GRADE_BASELINE_WITH_SHARDED_BACKFILL_QUEUE','market_data_grade':'NON_DECISION_GRADE_FALLBACK','full_universe_market_history_claimed':False,'accepted_dual_route_securities':len(accepted),'market_bar_count':len(bars),'corporate_action_count':len(events),'fx_row_count':len(fx),'research_production_gate':'OPEN_FOR_FMDL6X2_DATA_PRODUCTION','brokerage_real_account_gate':'CLOSED_NO_CHANNEL','trade_authority':'NONE','zero_mutation_proof':contract['zero_mutation_gate']}
    write_json(candidate_root / 'FMDL6X2D_DECISION.json', decision)
    source_binding={'phase_id':PHASE_ID,'release_id':release_id,'input_identity_manifest_sha256':input_manifest_sha,'raw_route_observations_sha256':raw_manifest_sha,'raw_payload_zip_sha256':sha256_file(raw_root/'FMDL6X2D_RAW_PAYLOADS.zip'),'market_routes':['YAHOO_QUERY1_CHART','YAHOO_QUERY2_CHART'],'market_authority':'YAHOO_FREE_UNOFFICIAL','market_data_grade':'NON_DECISION_GRADE_FALLBACK','fx_primary':'ECB_OFFICIAL','fx_support':'FRANKFURTER_FREE','stooq_route':'DISABLED_HTML_CHALLENGE','silent_source_substitution':False}
    write_json(candidate_root / 'FMDL6X2D_SOURCE_BINDING.json', source_binding)
    manifest_files={}
    for path in sorted(candidate_root.iterdir()):
        if path.name == 'FMDL6X2D_MANIFEST.json' or not path.is_file(): continue
        manifest_files[path.name]={'bytes':path.stat().st_size,'sha256':sha256_file(path)}
    manifest={'phase_id':PHASE_ID,'release_id':release_id,'release_sequence':33,'generated_at':accepted_at,'contract_sha256':contract_sha,'input_identity_manifest_sha256':input_manifest_sha,'raw_route_observations_sha256':raw_manifest_sha,'files':manifest_files,'shards':shards}
    write_json(candidate_root/'FMDL6X2D_MANIFEST.json',manifest)
    return {'decision':decision,'quality':quality,'coverage':coverage,'contract_checks':checks}


def validate_candidate(repo_root: Path, raw_root: Path, candidate_root: Path, accepted_at: str, source_commit: str, acceptance_path: Path) -> dict[str, Any]:
    replay = candidate_root.parent / (candidate_root.name + '_replay')
    if replay.exists(): shutil.rmtree(replay)
    build_candidate(repo_root, raw_root, replay, accepted_at, source_commit)
    left={p.name:sha256_file(p) for p in candidate_root.iterdir() if p.is_file()}
    right={p.name:sha256_file(p) for p in replay.iterdir() if p.is_file()}
    errors=[]
    if left != right: errors.append('CAPTURED_INPUT_REPLAY_MISMATCH')
    manifest=load_json(candidate_root/'FMDL6X2D_MANIFEST.json')
    for name,meta in manifest['files'].items():
        path=candidate_root/name
        if not path.is_file() or path.stat().st_size != meta['bytes'] or sha256_file(path) != meta['sha256']:
            errors.append('MANIFEST_FILE:'+name)
    decision=load_json(candidate_root/'FMDL6X2D_DECISION.json')
    if decision.get('trade_authority') != 'NONE': errors.append('TRADE_AUTHORITY')
    result={'phase_id':PHASE_ID,'status':'PASS' if not errors else 'FAIL','captured_input_replay':'PASS' if left==right else 'FAIL','errors':errors,'release_id':decision.get('release_id')}
    write_json(acceptance_path,result)
    if errors: raise RuntimeError('ACCEPTANCE_ERRORS:'+','.join(errors))
    return result


def publish(repo_root: Path, raw_root: Path, candidate_root: Path, published_at: str, source_commit: str) -> dict[str, Any]:
    contract=load_json(repo_root/CONTRACT_PATH)
    decision=load_json(candidate_root/'FMDL6X2D_DECISION.json')
    release_id=decision['release_id']
    current=repo_root/contract['storage_contract']['current_root']
    release=repo_root/contract['storage_contract']['release_root'].replace('<release_id>',release_id)
    normalized=repo_root/contract['storage_contract']['normalized_root'].replace('<release_id>',release_id)
    raw_target=repo_root/contract['storage_contract']['raw_root'].replace('<release_id>',release_id)
    archive_root=repo_root/contract['storage_contract']['archive_root']
    if release.exists(): raise RuntimeError('IMMUTABLE_RELEASE_COLLISION')
    if current.exists():
        archive=archive_root/f"market_reference_{published_at.replace(':','').replace('-','')}"
        copytree_replace(current,archive)
    copytree_replace(candidate_root,current)
    copytree_replace(candidate_root,release)
    copytree_replace(candidate_root,normalized)
    raw_target.mkdir(parents=True,exist_ok=True)
    shutil.copy2(raw_root/'FMDL6X2D_RAW_PAYLOADS.zip',raw_target/'FMDL6X2D_RAW_PAYLOADS.zip')
    shutil.copy2(raw_root/'FMDL6X2D_ROUTE_OBSERVATIONS.json',raw_target/'FMDL6X2D_ROUTE_OBSERVATIONS.json')
    manifest_sha=sha256_file(current/'FMDL6X2D_MANIFEST.json')
    pointer={'phase_id':PHASE_ID,'status':EXIT_STATUS,'release_id':release_id,'release_sequence':33,'published_at':published_at,'source_commit':source_commit,'current_path':str(current.relative_to(repo_root)),'release_path':str(release.relative_to(repo_root)),'normalized_path':str(normalized.relative_to(repo_root)),'raw_path':str(raw_target.relative_to(repo_root)),'manifest_sha256':manifest_sha,'market_store_status':decision['market_store_status'],'market_data_grade':decision['market_data_grade'],'full_universe_market_history_claimed':False,'accepted_dual_route_securities':decision['accepted_dual_route_securities'],'market_bar_count':decision['market_bar_count'],'corporate_action_count':decision['corporate_action_count'],'fx_row_count':decision['fx_row_count'],'next_gate':NEXT_GATE,'research_production_gate':'OPEN_FOR_FMDL6X2_DATA_PRODUCTION','brokerage_real_account_gate':'CLOSED_NO_CHANNEL','trade_authority':'NONE'}
    write_json(repo_root/contract['storage_contract']['last_success'],pointer)
    lkg={**pointer,'lkg_scope':'MARKET_HISTORY_CORPORATE_ACTIONS_AND_FX_DOMAIN','lkg_reason':'LATEST_ACCEPTED_MARKET_REFERENCE_BASELINE'}
    write_json(repo_root/contract['storage_contract']['last_known_good'],lkg)
    return pointer
