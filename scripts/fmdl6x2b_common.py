from __future__ import annotations

import gzip
import hashlib
import io
import json
import shutil
import unicodedata
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

CONTRACT_PATH = Path('config/fmdl6x2b_identity_classification_contract.json')
PHASE_ID = 'FMDL-6X2-B'
EXIT_STATUS = 'FMDL6X2B_IDENTITY_CLASSIFICATION_AND_REVIEW_QUEUES_ACCEPTED'
NEXT_GATE = 'FMDL-6X2-C_HISTORICAL_LISTING_AND_LIFECYCLE_BACKFILL'
FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8-sig'))


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n'


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(pretty_json(value), encoding='utf-8')


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def record_hash(namespace: str, *parts: Any) -> str:
    payload = namespace + '|' + '|'.join('' if p is None else str(p).strip() for p in parts)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def normalize_text(value: str) -> str:
    text = unicodedata.normalize('NFKC', value or '')
    text = text.replace('–', '-').replace('—', '-').replace('’', "'")
    return ' '.join(text.split()).strip()


def ascii_key(value: str) -> str:
    text = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode().upper()
    text = text.replace('&', ' AND ')
    import re
    text = re.sub(r'\bTHE\b', ' ', text)
    text = re.sub(r'[^A-Z0-9]+', ' ', text)
    return ' '.join(text.split()).strip()


def bucket_hex(value: str, bucket_count: int = 64) -> str:
    return f'{int(hashlib.sha256(value.encode("utf-8")).hexdigest(), 16) % bucket_count:02X}'


def deterministic_gzip(records: Iterable[dict[str, Any]]) -> bytes:
    raw = ''.join(stable_json(row) + '\n' for row in records).encode('utf-8')
    out = io.BytesIO()
    with gzip.GzipFile(filename='', mode='wb', fileobj=out, mtime=0) as handle:
        handle.write(raw)
    return out.getvalue()


def deterministic_zip(entries: dict[str, bytes]) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(entries):
            info = zipfile.ZipInfo(name, FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, entries[name])
    return out.getvalue()


def read_gzip_jsonl(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, 'rt', encoding='utf-8') as handle:
        return [json.loads(line) for line in handle if line.strip()]


def read_zip_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with zipfile.ZipFile(path) as archive:
        for name in sorted(archive.namelist()):
            if not name.endswith('.jsonl'):
                continue
            for line in archive.read(name).decode('utf-8').splitlines():
                if line.strip():
                    rows.append(json.loads(line))
    return rows


def copytree_replace(source: Path, target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)


def validate_contract(repo_root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    checks: list[dict[str, Any]] = []
    errors: list[str] = []
    path = repo_root / CONTRACT_PATH
    if not path.is_file():
        return [{'check_id': 'CONTRACT_EXISTS', 'status': 'FAIL'}], ['CONTRACT_EXISTS']
    contract = load_json(path)

    def check(cid: str, condition: bool, actual: Any = None, expected: Any = None) -> None:
        checks.append({'check_id': cid, 'status': 'PASS' if condition else 'FAIL', 'actual': actual, 'expected': expected})
        if not condition:
            errors.append(cid)

    check('PHASE_ID', contract.get('phase_id') == PHASE_ID, contract.get('phase_id'), PHASE_ID)
    check('STATUS', contract.get('status') == 'PRODUCTION_CONTRACT_CANDIDATE')
    check('TRADE_AUTHORITY', contract.get('trade_authority') == 'NONE')
    entry = contract.get('entry_gate', {})
    pointer_path = repo_root / str(entry.get('pointer_path', ''))
    check('ENTRY_POINTER_EXISTS', pointer_path.is_file(), str(pointer_path), 'existing file')
    if pointer_path.is_file():
        pointer = load_json(pointer_path)
        for field, required_key in [
            ('phase_id', 'required_phase_id'), ('release_id', 'required_release_id'),
            ('status', 'required_status'), ('release_sequence', 'required_release_sequence'),
            ('next_gate', 'required_next_gate'), ('trade_authority', 'required_trade_authority'),
        ]:
            check('ENTRY_' + field.upper(), pointer.get(field) == entry.get(required_key), pointer.get(field), entry.get(required_key))
    input_root = repo_root / contract.get('input_contract', {}).get('current_security_master_root', '')
    for name in contract.get('input_contract', {}).get('required_files', []):
        check('INPUT_' + Path(name).stem, (input_root / name).is_file(), str(input_root / name), 'existing file')
    scope = contract.get('scope', {})
    check('IDENTITY_AUTHORIZED', scope.get('issuer_identity_classification_and_review_queues_authorized') is True)
    for key, value in scope.items():
        if key != 'issuer_identity_classification_and_review_queues_authorized' and key.endswith('authorized'):
            check('SCOPE_FALSE_' + key.upper(), value is False, value, False)
    identity = contract.get('identity_contract', {})
    check('NO_FUZZY_MERGE', identity.get('fuzzy_issuer_merge_authorized') is False)
    check('TICKER_NOT_IDENTITY', identity.get('ticker_or_exchange_may_be_used_as_immutable_identity') is False)
    check('IDS_MERGEABLE', identity.get('directory_derived_ids_are_mergeable') is True)
    check('SEC_NOT_FABRICATED', identity.get('sec_cik_may_be_inferred_without_official_evidence') is False)
    check('CLASSIFICATION_RULE_VERSION', bool(contract.get('classification_contract', {}).get('rule_version')))
    storage = contract.get('storage_contract', {})
    check('BUCKET_COUNT', storage.get('bucket_count') == 64)
    check('RELEASE_SEQUENCE', storage.get('release_sequence') == 31)
    check('EXIT_STATUS', contract.get('required_exit_status') == EXIT_STATUS)
    check('NEXT_GATE', contract.get('next_gate') == NEXT_GATE)
    check('ZERO_MUTATIONS', all(v == 0 for v in contract.get('zero_mutation_gate', {}).values()))
    return checks, sorted(set(errors))
