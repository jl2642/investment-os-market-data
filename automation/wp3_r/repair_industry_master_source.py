#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


PATH = Path(__file__).resolve().parent / "refresh_industry_master.py"
OLD = '''def read_market_ids(path: Path) -> set[str]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if "security_code" not in (reader.fieldnames or []):
            raise ValueError("A_SHARE_CURRENT_SECURITY_CODE_COLUMN_MISSING")
        return {
            normalize_security_id(row["security_code"])
            for row in reader
            if str(row.get("security_code") or "").strip()
        }
'''
NEW = '''def read_market_ids(path: Path) -> set[str]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        raw_fields = reader.fieldnames or []
        normalized_fields = {
            str(field).strip().lstrip("\\ufeff"): field
            for field in raw_fields
            if field is not None
        }
        source_field = normalized_fields.get("security_code")
        if source_field is None:
            raise ValueError(
                "A_SHARE_CURRENT_SECURITY_CODE_COLUMN_MISSING:"
                + ",".join(map(str, raw_fields))
            )
        market_ids = {
            normalize_security_id(row[source_field])
            for row in reader
            if str(row.get(source_field) or "").strip()
        }
        if len(market_ids) < 5000:
            raise ValueError(
                f"A_SHARE_CURRENT_SECURITY_ID_COUNT_TOO_LOW:{len(market_ids)}"
            )
        return market_ids
'''


def main() -> None:
    text = PATH.read_text(encoding="utf-8")
    if OLD in text:
        PATH.write_text(text.replace(OLD, NEW), encoding="utf-8")
        print("WP3R_INDUSTRY_MARKET_ID_READER_REPAIRED")
        return
    if NEW in text:
        print("WP3R_INDUSTRY_MARKET_ID_READER_ALREADY_VALID")
        return
    raise SystemExit("WP3R_INDUSTRY_MARKET_ID_READER_TARGET_NOT_FOUND")


if __name__ == "__main__":
    main()
