from __future__ import annotations
import argparse
import gzip
import hashlib
import io
import json
import shutil
import zipfile
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any
PHASE_ID = 'FMDL-6X3-B'
STATUS = 'FMDL6X3B_FINANCIAL_NORMALIZATION_TTM_AND_ANNUAL_METRIC_LAYER_ACCEPTED'
NEXT_GATE = 'FMDL-6X3-C_FACTOR_VALUATION_QUALITY_AND_RISK_ENGINE'
CONTRACT_PATH = Path('config/fmdl6x3b_financial_normalization_contract.json')
ZIP_TIME = (1980, 1, 1, 0, 0, 0)

def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))

def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf-8')

def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8-sig'))

def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()

def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())

def record_hash(namespace: str, *parts: Any) -> str:
    return sha256_bytes((namespace + '|' + '|'.join((str(x) for x in parts))).encode('utf-8'))

def bucket_hex(value: str, bucket_count: int) -> str:
    return f"{int(sha256_bytes(value.encode('utf-8')), 16) % bucket_count:02X}"

def jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    return ''.join((stable_json(row) + '\n' for row in rows)).encode('utf-8')

def deterministic_zip(entries: dict[str, bytes]) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(entries):
            info = zipfile.ZipInfo(name, ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 33188 << 16
            archive.writestr(info, entries[name])
    return out.getvalue()

def deterministic_gzip(rows: list[dict[str, Any]]) -> bytes:
    out = io.BytesIO()
    with gzip.GzipFile(filename='', mode='wb', fileobj=out, mtime=0) as handle:
        handle.write(jsonl_bytes(rows))
    return out.getvalue()

def read_zip_jsonl(path: Path, prefix: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with zipfile.ZipFile(path) as archive:
        for name in sorted(archive.namelist()):
            if name.startswith(prefix) and name.endswith('.jsonl'):
                rows.extend((json.loads(line) for line in archive.read(name).decode('utf-8').splitlines() if line.strip()))
    return rows

def numeric(value: Any) -> int | float:
    text = str(value)
    return float(text) if any((ch in text.lower() for ch in ('.', 'e'))) else int(text)

def period_id(row: dict[str, Any]) -> str:
    return 'USPER-' + record_hash('PERIOD', row['canonical_issuer_id'], row['fiscal_year'], row['fiscal_period'], row['start_date'], row['end_date'])[:24]

def validate_contract(repo_root: Path) -> dict[str, Any]:
    contract = read_json(repo_root / CONTRACT_PATH)
    errors: list[str] = []
    if contract.get('phase_id') != PHASE_ID:
        errors.append('PHASE_ID')
    if contract.get('trade_authority') != 'NONE':
        errors.append('TRADE_AUTHORITY')
    if contract.get('required_exit_status') != STATUS:
        errors.append('EXIT_STATUS')
    if contract.get('next_gate') != NEXT_GATE:
        errors.append('NEXT_GATE')
    if contract.get('source_contract', {}).get('neutral_fill_authorized') is not False:
        errors.append('NEUTRAL_FILL')
    if contract.get('source_contract', {}).get('silent_source_substitution_authorized') is not False:
        errors.append('SILENT_SUBSTITUTION')
    if contract.get('quality_contract', {}).get('expected_shard_count') != 256:
        errors.append('SHARD_COUNT')
    if any((value != 0 for value in contract.get('zero_mutation_gate', {}).values())):
        errors.append('ZERO_MUTATION')
    pointer_path = repo_root / contract['entry_gate']['pointer_path']
    if not pointer_path.is_file():
        errors.append('ENTRY_POINTER_MISSING')
    else:
        pointer = read_json(pointer_path)
        checks = {'phase_id': 'required_phase_id', 'release_id': 'required_release_id', 'release_sequence': 'required_release_sequence', 'status': 'required_status', 'next_gate': 'required_next_gate', 'trade_authority': 'required_trade_authority'}
        for field, requirement in checks.items():
            if pointer.get(field) != contract['entry_gate'][requirement]:
                errors.append('ENTRY_' + field.upper())
    if errors:
        raise RuntimeError('CONTRACT_ERRORS:' + ','.join(sorted(set(errors))))
    return contract

def load_inputs(repo_root: Path, contract: dict[str, Any]) -> dict[str, Any]:
    inp = contract['input_contract']
    readiness_root = repo_root / inp['readiness_root']
    sec_root = repo_root / inp['sec_root']
    readiness_rows = read_zip_jsonl(readiness_root / inp['readiness_shards'], 'SECURITY_READINESS/')
    ready_rows = sorted([row for row in readiness_rows if row.get('ready_for_fmdl6x3b') is True], key=lambda row: row['canonical_security_id'])
    facts = read_zip_jsonl(sec_root / inp['sec_fact_shards'], 'FACTS/')
    filings = read_zip_jsonl(sec_root / inp['sec_filing_shards'], 'FILINGS/')
    return {'readiness_root': readiness_root, 'sec_root': sec_root, 'readiness_manifest_path': readiness_root / inp['readiness_manifest'], 'sec_manifest_path': sec_root / inp['sec_manifest'], 'ready_rows': ready_rows, 'facts': facts, 'filings': filings}
