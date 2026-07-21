#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

HKEX_URL = "https://www.hkex.com.hk/Services/Trading/Securities/Trading-News/Newly-Listed-Securities?sc_lang=en"
ACTION_FIELDS = [
    "security_id",
    "stock_code_5d",
    "action_date",
    "action_type",
    "cash_amount",
    "currency",
    "split_numerator",
    "split_denominator",
    "related_stock_code",
    "provider",
    "source_tier",
    "retrieved_at_utc",
    "source_response_sha256",
    "evidence_detail",
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def code5(value: str) -> str:
    return value.strip().zfill(5)


def fetch() -> requests.Response:
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; InvestmentOS/5C; +https://github.com/jl2642/investment-os-market-data)",
        "Accept-Language": "en-US,en;q=0.9",
    }
    last: Exception | None = None
    for attempt in range(5):
        try:
            response = requests.get(HKEX_URL, headers=headers, timeout=(15, 120))
            response.raise_for_status()
            return response
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(min(16, 2**attempt))
    assert last is not None
    raise last


def parse_hkex_action_html(
    html: bytes,
    universe_codes: set[str],
    retrieved_at_utc: str,
    response_sha256: str,
) -> list[dict[str, object]]:
    soup = BeautifulSoup(html, "html.parser")
    target = None
    for table in soup.find_all("table"):
        header = " ".join(table.get_text(" ", strip=True).split())
        if "Corresponding Corporate Action" in header and "Related Stock Code" in header:
            target = table
            break
    if target is None:
        raise ValueError("HKEX_ACTION_TABLE_NOT_FOUND")
    rows: list[dict[str, object]] = []
    for tr in target.find_all("tr"):
        cells = [" ".join(td.get_text(" ", strip=True).split()) for td in tr.find_all("td")]
        if len(cells) < 6:
            continue
        raw_code = cells[2].replace(".0", "").strip()
        if not raw_code.isdigit():
            continue
        listed_code = code5(raw_code)
        action = cells[-2].strip()
        raw_related = cells[-1].replace(".0", "").strip()
        related_code = code5(raw_related) if raw_related.isdigit() else ""
        if not action or action.lower() == "nan" or action == "New Listing":
            continue
        anchor_code = related_code if related_code in universe_codes else listed_code
        if anchor_code not in universe_codes:
            continue
        raw_date = cells[0].replace("*", "").strip()
        action_date = ""
        for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
            try:
                action_date = datetime.strptime(raw_date, fmt).date().isoformat()
                break
            except ValueError:
                continue
        rows.append(
            {
                "security_id": f"HKEX:{anchor_code}",
                "stock_code_5d": anchor_code,
                "action_date": action_date,
                "action_type": "HKEX_CURRENT_LISTING_OR_CORPORATE_ACTION",
                "cash_amount": "",
                "currency": "",
                "split_numerator": "",
                "split_denominator": "",
                "related_stock_code": listed_code if anchor_code == related_code else related_code,
                "provider": "HKEX_NEWLY_LISTED_SECURITIES",
                "source_tier": "OFFICIAL_CURRENT_EVENT",
                "retrieved_at_utc": retrieved_at_utc,
                "source_response_sha256": response_sha256,
                "evidence_detail": action,
            }
        )
    return rows


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ACTION_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def recompute_release(candidate: Path) -> None:
    decision_path = candidate / "FMDL5C_DECISION.json"
    manifest_path = candidate / "FMDL5C_MANIFEST.json"
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    base_files: dict[str, dict[str, object]] = {}
    for path in sorted(candidate.iterdir()):
        if path.is_file() and path.name not in {"FMDL5C_MANIFEST.json", "FMDL5C_DECISION.json"}:
            base_files[path.name] = {"size_bytes": path.stat().st_size, "sha256": sha256_file(path)}
    canonical_material = json.dumps(base_files, sort_keys=True, separators=(",", ":")).encode("utf-8")
    canonical_sha = sha256_bytes(canonical_material)
    release_id = f"FMDL5C_{datetime.now(timezone.utc).strftime('%Y%m%d')}_{canonical_sha[:12]}"
    decision["canonical_sha256"] = canonical_sha
    decision["release_id"] = release_id
    decision_path.write_text(json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    base_files["FMDL5C_DECISION.json"] = {
        "size_bytes": decision_path.stat().st_size,
        "sha256": sha256_file(decision_path),
    }
    manifest = {
        "program_id": "FMDL-5C",
        "release_id": release_id,
        "release_sequence": decision["release_sequence"],
        "canonical_sha256": canonical_sha,
        "source_release_id": decision["source_release_id"],
        "generated_at_utc": decision.get("generated_at_utc") or datetime.now(timezone.utc).isoformat(),
        "files": base_files,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True)
    args = parser.parse_args()
    candidate = Path(args.candidate)
    latest = read_csv(candidate / "FMDL5C_LATEST_PRICE_SNAPSHOT.csv")
    universe_codes = {code5(row["stock_code_5d"]) for row in latest}
    retrieved_at_utc = datetime.now(timezone.utc).isoformat()
    response = fetch()
    response_sha = sha256_bytes(response.content)
    official_rows = parse_hkex_action_html(response.content, universe_codes, retrieved_at_utc, response_sha)
    if not official_rows:
        raise ValueError("HKEX_CURRENT_ACTIONS_EMPTY_AFTER_SUCCESSFUL_PARSE")
    existing = read_csv(candidate / "FMDL5C_CORPORATE_ACTIONS.csv")
    combined: dict[tuple[str, ...], dict[str, object]] = {}
    for row in [*existing, *official_rows]:
        key = (
            str(row.get("security_id", "")),
            str(row.get("action_date", "")),
            str(row.get("action_type", "")),
            str(row.get("provider", "")),
            str(row.get("evidence_detail", "")),
            str(row.get("related_stock_code", "")),
        )
        combined[key] = row
    rows = sorted(combined.values(), key=lambda row: (str(row.get("security_id")), str(row.get("action_date")), str(row.get("provider"))))
    write_csv(candidate / "FMDL5C_CORPORATE_ACTIONS.csv", rows)

    registry_path = candidate / "FMDL5C_SOURCE_REGISTRY.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry["hkex_current_action_summary"] = {
        "provider": "HKEX_NEWLY_LISTED_SECURITIES",
        "row_count": len(official_rows),
        "response_sha256": response_sha,
        "warning": "",
    }
    registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    quality_path = candidate / "FMDL5C_QUALITY_REPORT.json"
    quality = json.loads(quality_path.read_text(encoding="utf-8"))
    quality["corporate_action_count"] = len(rows)
    quality["hkex_official_current_action_count"] = len(official_rows)
    quality["hkex_current_action_parse_warning"] = ""
    quality_path.write_text(json.dumps(quality, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    decision_path = candidate / "FMDL5C_DECISION.json"
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    decision["metrics"] = quality
    decision_path.write_text(json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    recompute_release(candidate)
    print(json.dumps({"official_action_count": len(official_rows), "total_action_count": len(rows)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
