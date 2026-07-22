from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CONTRACT_PATH = Path('config/fmdl6x2d_market_history_contract.json')
PHASE_ID = 'FMDL-6X2-D'
EXIT_STATUS = 'FMDL6X2D_MARKET_HISTORY_CORPORATE_ACTIONS_AND_FX_ACCEPTED'
NEXT_GATE = 'FMDL-6X2-E_SEC_FILINGS_AND_FINANCIAL_FACTS_STORE'
FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8-sig'))


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n'


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


def bucket_hex(value: str, bucket_count: int) -> str:
    return f"{int(hashlib.sha256(value.encode('utf-8')).hexdigest(), 16) % bucket_count:02X}"


def deterministic_gzip(rows: list[dict[str, Any]]) -> bytes:
    raw = ''.join(stable_json(row) + '\n' for row in rows).encode('utf-8')
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


def read_zip_jsonl(path: Path, prefix: str | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with zipfile.ZipFile(path, 'r') as archive:
        for name in sorted(archive.namelist()):
            if not name.endswith('.jsonl') or (prefix and not name.startswith(prefix)):
                continue
            rows.extend(json.loads(line) for line in archive.read(name).decode('utf-8').splitlines() if line.strip())
    return rows


def copytree_replace(source: Path, target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)


def parse_ecb_csv(payload: bytes) -> dict[str, float]:
    text = payload.decode('utf-8-sig', errors='replace')
    reader = csv.DictReader(io.StringIO(text))
    out: dict[str, float] = {}
    for row in reader:
        date = (row.get('TIME_PERIOD') or '').strip()
        raw = (row.get('OBS_VALUE') or '').strip()
        if not date or not raw:
            continue
        try:
            out[date] = float(raw)
        except ValueError:
            continue
    return out


def validate_contract(repo_root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    path = repo_root / CONTRACT_PATH
    if not path.is_file():
        return [{'check_id': 'CONTRACT_EXISTS', 'status': 'FAIL'}], ['CONTRACT_EXISTS']
    contract = load_json(path)
    checks: list[dict[str, Any]] = []
    errors: list[str] = []

    def check(cid: str, condition: bool, actual: Any = None, expected: Any = None) -> None:
        checks.append({'check_id': cid, 'status': 'PASS' if condition else 'FAIL', 'actual': actual, 'expected': expected})
        if not condition:
            errors.append(cid)

    check('PHASE_ID', contract.get('phase_id') == PHASE_ID, contract.get('phase_id'), PHASE_ID)
    check('TRADE_AUTHORITY', contract.get('trade_authority') == 'NONE')
    entry = contract.get('entry_gate', {})
    pointer_path = repo_root / entry.get('pointer_path', '')
    check('ENTRY_POINTER_EXISTS', pointer_path.is_file())
    if pointer_path.is_file():
        pointer = load_json(pointer_path)
        for field, key in [('phase_id','required_phase_id'),('release_id','required_release_id'),('release_sequence','required_release_sequence'),('status','required_status'),('next_gate','required_next_gate'),('trade_authority','required_trade_authority')]:
            check('ENTRY_' + field.upper(), pointer.get(field) == entry.get(key), pointer.get(field), entry.get(key))
    scope = contract.get('scope', {})
    check('MARKET_SCOPE', scope.get('market_history_corporate_actions_and_fx_authorized') is True)
    for key, value in scope.items():
        if key != 'market_history_corporate_actions_and_fx_authorized' and key.endswith('authorized'):
            check('SCOPE_FALSE_' + key.upper(), value is False)
    market = contract.get('market_contract', {})
    check('GRADE', market.get('market_data_grade') == 'NON_DECISION_GRADE_FALLBACK')
    check('DUAL_ROUTE', 'query1.finance.yahoo.com' in market.get('route_1_template','') and 'query2.finance.yahoo.com' in market.get('route_2_template',''))
    check('STOOQ_DISABLED', market.get('stooq_route') == 'DISABLED_HTML_CHALLENGE')
    check('UNIVERSE_SIZE', market.get('universe_size_expected') == 8785)
    check('COHORT_SIZE', contract.get('acceptance_gates', {}).get('cohort_size') == 64)
    check('RELEASE_SEQUENCE', contract.get('storage_contract', {}).get('release_sequence') == 33)
    check('EXIT_STATUS', contract.get('required_exit_status') == EXIT_STATUS)
    check('NEXT_GATE', contract.get('next_gate') == NEXT_GATE)
    check('ZERO_MUTATIONS', all(v == 0 for v in contract.get('zero_mutation_gate', {}).values()))
    return checks, sorted(set(errors))
