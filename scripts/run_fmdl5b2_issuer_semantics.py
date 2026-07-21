#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

PROGRAM_ID = "FMDL-5B-2"
SOURCE_RELEASE_ID = "FMDL5B1_20260720_d31e787a3ccd"
SOURCE_PATH = Path("outputs/fmdl5b1/current/FMDL5B1_HK_SECURITY_MASTER.csv")
EXPECTED_COUNT = 644
FULL_LIST_URL = "https://www.hkex.com.hk/eng/services/trading/securities/securitieslists/ListOfSecurities.xlsx"
DUAL_COUNTER_URL = "https://www.hkex.com.hk/-/media/HKEX-Market/Services/Trading/Securities/Securities-Lists/Dual_Counter_Security_List.xlsx"
DI_URL = "https://di.hkex.com.hk/di/NSSrchCorpList.aspx"
_thread = threading.local()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_id(prefix: str, value: str) -> str:
    return f"{prefix}:{hashlib.sha256(value.encode('utf-8')).hexdigest()[:16]}"


def code5(value: object) -> str:
    text = str(value or "").strip()
    text = re.sub(r"\.0$", "", text)
    return text.zfill(5)


def optional_code5(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return ""
    return code5(text)


def parse_int(value: object) -> int | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).replace(",", "").strip()
    if not text or text.lower() == "nan":
        return None
    return int(float(text))


def normalized_issuer_name(name: str) -> str:
    text = re.sub(r"\s+", " ", name.strip())
    rules = [
        r"\s*-\s*(?:W|B|S|SW)\s*$",
        r"\s*-\s*H\s+(?:SHARES?|SH)\s*$",
        r"\s+'[AB]'\s*$",
        r"\s+CLASS\s+[AB]\s+SHARES?\s*$",
    ]
    previous = None
    while previous != text:
        previous = text
        for pattern in rules:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"\s+", " ", text)
    return text


def official_suffix_flags(name: str) -> dict[str, bool]:
    upper = name.upper().strip()
    return {
        "wvr_flag": bool(re.search(r"-(?:W|SW)$", upper)),
        "secondary_listing_flag": bool(re.search(r"-(?:S|SW)$", upper)),
        "biotech_chapter18a_flag": bool(re.search(r"-B$", upper)),
    }


def h_share_flag(issuer_name: str) -> bool:
    upper = issuer_name.upper()
    return bool(re.search(r"(?:-|\s)H\s+(?:SHARES?|SH)\b", upper))


def security_type(category: str, sub_category: str) -> str:
    c = category.strip().upper()
    s = sub_category.strip().upper()
    if "EXCHANGE TRADED" in c or "EXCHANGE TRADED FUND" in s:
        return "ETF"
    if "REAL ESTATE INVESTMENT TRUST" in c:
        return "REIT"
    if c == "EQUITY":
        return "COMMON_EQUITY"
    return "OTHER_LISTED_SECURITY"


def get_session() -> requests.Session:
    session = getattr(_thread, "session", None)
    if session is None:
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (compatible; InvestmentOS/5B2; +https://github.com/jl2642/investment-os-market-data)",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://di.hkex.com.hk/di/NSSrchCorp.aspx?g_lang=en&lang=EN&src=MAIN&",
            }
        )
        _thread.session = session
    return session


def request_bytes(url: str, timeout: int = 120) -> bytes:
    last: Exception | None = None
    for attempt in range(5):
        try:
            response = get_session().get(url, timeout=(15, timeout), allow_redirects=True)
            response.raise_for_status()
            return response.content
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(min(16, 2**attempt))
    assert last is not None
    raise last


def find_header(frame: pd.DataFrame, marker: str) -> int:
    for idx, row in frame.head(30).iterrows():
        if any(marker in str(value) for value in row.tolist()):
            return int(idx)
    raise ValueError(f"HEADER_NOT_FOUND:{marker}")


def read_full_list(data: bytes) -> pd.DataFrame:
    raw = pd.read_excel(io.BytesIO(data), header=None)
    header = find_header(raw, "Stock Code")
    frame = pd.read_excel(io.BytesIO(data), header=header)
    frame["stock_code_5d"] = frame["Stock Code"].map(code5)
    return frame


def read_dual_counter(data: bytes) -> tuple[pd.DataFrame, str]:
    raw = pd.read_excel(io.BytesIO(data), header=None)
    header = find_header(raw, "HKD Counter Stock Code")
    update_date = ""
    for value in raw.iloc[:header].fillna("").astype(str).values.flatten().tolist():
        if re.fullmatch(r"\d{2}-\d{2}-\d{4}", value.strip()):
            update_date = value.strip()
            break
    frame = pd.read_excel(io.BytesIO(data), header=header)
    frame["hkd_code_5d"] = frame["HKD Counter Stock Code"].map(code5)
    frame["rmb_code_5d"] = frame["RMB Counter Stock Code"].map(code5)
    return frame, update_date


def parse_di_html(code: str, html: bytes, url: str) -> dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    pairs: set[tuple[str, str]] = set()
    for link in soup.find_all("a"):
        href = str(link.get("href") or "")
        if "sid=" not in href or "corpn=" not in href:
            continue
        query = parse_qs(urlparse(href).query)
        sid = str((query.get("sid") or [""])[0]).strip()
        corpn = str((query.get("corpn") or [""])[0]).strip()
        if sid and corpn:
            pairs.add((sid, corpn))
    if len(pairs) != 1:
        excerpt = soup.get_text(" ", strip=True)[:1000]
        raise ValueError(f"DI_MAPPING_AMBIGUOUS:{code}:{len(pairs)}:{excerpt}")
    sid, corpn = next(iter(pairs))
    return {
        "stock_code_5d": code,
        "di_sid": sid,
        "official_issuer_name_en": corpn,
        "source_url": url,
        "response_sha256": sha256_bytes(html),
    }


def fetch_di_mapping(code: str) -> dict[str, str]:
    end = date.today().strftime("%d/%m/%Y")
    url = (
        f"{DI_URL}?sa1=cl&scsd=03/07/2017&sced={quote(end)}&sc={code}"
        "&src=MAIN&lang=EN&g_lang=en"
    )
    html = request_bytes(url, timeout=90)
    return parse_di_html(code, html, url)


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str] | None = None) -> None:
    if fields is None:
        fields = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_ndjson(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def build(output: Path) -> dict[str, object]:
    output.mkdir(parents=True, exist_ok=True)
    source_bytes = SOURCE_PATH.read_bytes()
    with SOURCE_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        source_rows = list(csv.DictReader(handle))

    full_bytes = request_bytes(FULL_LIST_URL)
    dual_bytes = request_bytes(DUAL_COUNTER_URL)
    full = read_full_list(full_bytes)
    dual, dual_update_date = read_dual_counter(dual_bytes)
    full_map = {str(row["stock_code_5d"]): row for _, row in full.iterrows()}
    dual_map = {str(row["hkd_code_5d"]): row for _, row in dual.iterrows()}

    equity_codes: list[str] = []
    for source in source_rows:
        code = code5(source["stock_code_5d"])
        official = full_map.get(code)
        if official is not None and security_type(str(official.get("Category", "")), str(official.get("Sub-Category", ""))) == "COMMON_EQUITY":
            equity_codes.append(code)

    di_results: dict[str, dict[str, str]] = {}
    di_errors: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(fetch_di_mapping, code): code for code in equity_codes}
        for future in as_completed(futures):
            code = futures[future]
            try:
                di_results[code] = future.result()
            except Exception as exc:  # noqa: BLE001
                di_errors[code] = f"{type(exc).__name__}: {exc}"

    overlays: list[dict[str, object]] = []
    bridge: list[dict[str, object]] = []
    review_queue: list[dict[str, object]] = []
    relationships: list[dict[str, object]] = []
    issuer_members: dict[str, list[dict[str, object]]] = {}

    for source in source_rows:
        code = code5(source["stock_code_5d"])
        official = full_map.get(code)
        if official is None:
            continue
        category = str(official.get("Category", "") or "").strip()
        sub_category = str(official.get("Sub-Category", "") or "").strip()
        sec_type = security_type(category, sub_category)
        official_name = str(official.get("Name of Securities", "") or "").strip()
        isin = str(official.get("ISIN", "") or "").strip()
        if isin.lower() == "nan":
            isin = ""
        dual_row = dual_map.get(code)
        rmb_counter = optional_code5(official.get("RMB Counter"))
        if dual_row is not None:
            rmb_counter = code5(dual_row.get("RMB Counter Stock Code"))

        di = di_results.get(code)
        if sec_type == "COMMON_EQUITY" and di:
            issuer_name = di["official_issuer_name_en"]
            issuer_base = normalized_issuer_name(issuer_name)
            issuer_id = stable_id("HKEX-ISSUER", issuer_base.upper())
            issuer_basis = "HKEX_DI_STOCK_CODE_CONFIRMED"
            issuer_status = "CONFIRMED"
            di_sid = di["di_sid"]
            di_response_sha = di["response_sha256"]
        elif sec_type in {"ETF", "REIT"}:
            issuer_name = official_name
            issuer_base = official_name
            issuer_id = stable_id("HKEX-FUND", isin or code)
            issuer_basis = "HKEX_SECURITY_MASTER_ISIN_CONFIRMED"
            issuer_status = "CONFIRMED"
            di_sid = ""
            di_response_sha = ""
        else:
            issuer_name = official_name or str(source.get("name_en", ""))
            issuer_base = issuer_name
            issuer_id = stable_id("HKEX-ISSUER-UNRESOLVED", code)
            issuer_basis = "SECURITY_ANCHORED_UNRESOLVED"
            issuer_status = "UNRESOLVED"
            di_sid = ""
            di_response_sha = ""
            review_queue.append(
                {
                    "security_id": source["security_id"],
                    "stock_code_5d": code,
                    "review_type": "ISSUER_IDENTITY_UNRESOLVED",
                    "evidence_status": "UNRESOLVED",
                    "detail": di_errors.get(code, "NO_OFFICIAL_ISSUER_MAPPING"),
                }
            )

        flags = official_suffix_flags(official_name)
        h_flag = h_share_flag(issuer_name)
        overlay = {
            "security_id": source["security_id"],
            "issuer_id": issuer_id,
            "stock_code_5d": code,
            "official_security_name_en": official_name,
            "official_issuer_name_en": issuer_name,
            "issuer_identity_status": issuer_status,
            "issuer_identity_basis": issuer_basis,
            "hkex_di_sid": di_sid,
            "category": category,
            "sub_category": sub_category,
            "security_type": sec_type,
            "board_lot": parse_int(official.get("Board Lot")),
            "isin": isin,
            "trading_currency": str(official.get("Trading Currency", "") or "").strip(),
            "rmb_counter_code": rmb_counter,
            "dual_counter_flag": bool(rmb_counter),
            "wvr_flag": flags["wvr_flag"],
            "secondary_listing_flag": flags["secondary_listing_flag"],
            "biotech_chapter18a_flag": flags["biotech_chapter18a_flag"],
            "h_share_flag": h_flag,
            "depositary_receipt_flag": 6200 <= int(code) <= 6399,
            "gem_flag": 8000 <= int(code) <= 8999,
            "source_release_id": SOURCE_RELEASE_ID,
            "hkex_full_list_sha256": sha256_bytes(full_bytes),
            "di_response_sha256": di_response_sha,
        }
        overlays.append(overlay)
        bridge.append(
            {
                "security_id": source["security_id"],
                "issuer_id": issuer_id,
                "stock_code_5d": code,
                "mapping_status": issuer_status,
                "mapping_basis": issuer_basis,
            }
        )
        issuer_members.setdefault(issuer_id, []).append(overlay)

        if h_flag:
            review_queue.append(
                {
                    "security_id": source["security_id"],
                    "stock_code_5d": code,
                    "review_type": "MAINLAND_A_SHARE_RELATIONSHIP",
                    "evidence_status": "REVIEW_REQUIRED",
                    "detail": "H_SHARE_STATUS_CONFIRMED_BUT_A_SHARE_CODE_NOT_CONFIRMED_IN_FMDL5B2",
                }
            )
        if flags["secondary_listing_flag"]:
            review_queue.append(
                {
                    "security_id": source["security_id"],
                    "stock_code_5d": code,
                    "review_type": "OVERSEAS_PRIMARY_LISTING_RELATIONSHIP",
                    "evidence_status": "REVIEW_REQUIRED",
                    "detail": "SECONDARY_LISTING_SUFFIX_CONFIRMED_BUT_OVERSEAS_TICKER_NOT_CONFIRMED",
                }
            )
        if rmb_counter:
            relationship_id = stable_id("HKEX-REL", f"DUAL_COUNTER:{code}:{rmb_counter}")
            relationships.append(
                {
                    "relationship_id": relationship_id,
                    "relationship_type": "HKD_RMB_DUAL_COUNTER",
                    "issuer_id": issuer_id,
                    "primary_security_id": source["security_id"],
                    "primary_market_code": code,
                    "related_market": "HKEX_RMB_COUNTER",
                    "related_security_code": rmb_counter,
                    "evidence_status": "CONFIRMED",
                    "evidence_source": "HKEX_DUAL_COUNTER_SECURITY_LIST",
                }
            )

    issuers: list[dict[str, object]] = []
    for issuer_id, members in sorted(issuer_members.items()):
        variants = sorted({str(x["official_issuer_name_en"]) for x in members if x["official_issuer_name_en"]})
        base_names = sorted({normalized_issuer_name(x) for x in variants})
        primary = sorted(members, key=lambda x: str(x["stock_code_5d"]))[0]
        status = "CONFIRMED" if all(x["issuer_identity_status"] == "CONFIRMED" for x in members) else "UNRESOLVED"
        issuers.append(
            {
                "issuer_id": issuer_id,
                "issuer_name_en": base_names[0] if len(base_names) == 1 else str(primary["official_issuer_name_en"]),
                "issuer_type": "FUND" if str(primary["security_type"]) in {"ETF", "REIT"} else "CORPORATE",
                "issuer_status": status,
                "primary_security_id": primary["security_id"],
                "member_security_count": len(members),
                "member_security_ids": "|".join(sorted(str(x["security_id"]) for x in members)),
                "official_name_variants": "|".join(variants),
                "identity_basis": str(primary["issuer_identity_basis"]),
            }
        )
        if len(members) > 1:
            relationships.append(
                {
                    "relationship_id": stable_id("HKEX-REL", f"HK_SHARE_CLASSES:{issuer_id}"),
                    "relationship_type": "HK_MULTIPLE_SHARE_CLASSES",
                    "issuer_id": issuer_id,
                    "primary_security_id": primary["security_id"],
                    "primary_market_code": primary["stock_code_5d"],
                    "related_market": "HKEX",
                    "related_security_code": "|".join(sorted(str(x["stock_code_5d"]) for x in members if x["security_id"] != primary["security_id"])),
                    "evidence_status": "CONFIRMED",
                    "evidence_source": "HKEX_DI_OFFICIAL_ISSUER_NAME_EXACT_NORMALIZATION",
                }
            )

    overlays.sort(key=lambda row: str(row["stock_code_5d"]))
    bridge.sort(key=lambda row: str(row["stock_code_5d"]))
    issuers.sort(key=lambda row: str(row["issuer_id"]))
    relationships.sort(key=lambda row: str(row["relationship_id"]))
    review_queue.sort(key=lambda row: (str(row["stock_code_5d"]), str(row["review_type"])))
    di_mapping_rows = [di_results[key] for key in sorted(di_results)]

    hard_failures: list[str] = []
    if len(source_rows) != EXPECTED_COUNT:
        hard_failures.append(f"SOURCE_COUNT_MISMATCH:{len(source_rows)}")
    if len(overlays) != EXPECTED_COUNT:
        hard_failures.append(f"OVERLAY_COUNT_MISMATCH:{len(overlays)}")
    if len({row["security_id"] for row in overlays}) != len(overlays):
        hard_failures.append("DUPLICATE_SECURITY_ID")
    if len(bridge) != EXPECTED_COUNT:
        hard_failures.append("BRIDGE_COUNT_MISMATCH")
    equity_count = sum(row["security_type"] == "COMMON_EQUITY" for row in overlays)
    mapping_count = sum(row["issuer_identity_basis"] == "HKEX_DI_STOCK_CODE_CONFIRMED" for row in overlays)
    coverage = mapping_count / equity_count if equity_count else 1.0
    if coverage < 0.95:
        hard_failures.append(f"DI_ISSUER_COVERAGE_BELOW_95PCT:{coverage:.6f}")
    if any(row["source_release_id"] != SOURCE_RELEASE_ID for row in overlays):
        hard_failures.append("SOURCE_RELEASE_MISMATCH")

    write_csv(output / "FMDL5B2_ISSUER_MASTER.csv", issuers)
    write_csv(output / "FMDL5B2_SECURITY_ISSUER_BRIDGE.csv", bridge)
    write_csv(output / "FMDL5B2_SECURITY_SEMANTIC_OVERLAY.csv", overlays)
    write_ndjson(output / "FMDL5B2_SECURITY_SEMANTIC_OVERLAY.ndjson", overlays)
    write_csv(output / "FMDL5B2_CROSS_MARKET_RELATIONSHIPS.csv", relationships)
    write_csv(output / "FMDL5B2_REVIEW_QUEUE.csv", review_queue, ["security_id", "stock_code_5d", "review_type", "evidence_status", "detail"])
    write_csv(output / "FMDL5B2_DI_ISSUER_MAPPING.csv", di_mapping_rows, ["stock_code_5d", "di_sid", "official_issuer_name_en", "source_url", "response_sha256"])

    canonical_payload = {
        "issuers": issuers,
        "bridge": bridge,
        "overlay": overlays,
        "relationships": relationships,
        "review_queue": review_queue,
    }
    canonical_bytes = json.dumps(canonical_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    canonical_sha = sha256_bytes(canonical_bytes)
    release_id = f"FMDL5B2_{date.today().strftime('%Y%m%d')}_{canonical_sha[:12]}"

    source_registry = {
        "program_id": PROGRAM_ID,
        "source_release_id": SOURCE_RELEASE_ID,
        "sources": [
            {"source": "FMDL5B1_SECURITY_MASTER", "path": str(SOURCE_PATH), "sha256": sha256_bytes(source_bytes), "record_count": len(source_rows)},
            {"source": "HKEX_FULL_LIST_OF_SECURITIES", "url": FULL_LIST_URL, "sha256": sha256_bytes(full_bytes), "record_count": int(len(full))},
            {"source": "HKEX_DUAL_COUNTER_SECURITY_LIST", "url": DUAL_COUNTER_URL, "sha256": sha256_bytes(dual_bytes), "record_count": int(len(dual)), "update_date": dual_update_date},
            {"source": "HKEX_DI_STOCK_CODE_SEARCH", "url": DI_URL, "mapping_count": mapping_count, "mapping_hash": sha256_bytes(json.dumps(di_mapping_rows, ensure_ascii=False, sort_keys=True).encode("utf-8"))},
        ],
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    (output / "FMDL5B2_SOURCE_REGISTRY.json").write_text(json.dumps(source_registry, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    metrics = {
        "source_security_count": len(source_rows),
        "semantic_overlay_count": len(overlays),
        "issuer_count": len(issuers),
        "issuer_consolidation_count": len(overlays) - len(issuers),
        "equity_count": equity_count,
        "etf_count": sum(row["security_type"] == "ETF" for row in overlays),
        "reit_count": sum(row["security_type"] == "REIT" for row in overlays),
        "official_di_issuer_mapping_count": mapping_count,
        "official_di_issuer_mapping_coverage": round(coverage, 6),
        "unresolved_issuer_count": sum(row["issuer_identity_status"] != "CONFIRMED" for row in overlays),
        "dual_counter_count": sum(bool(row["dual_counter_flag"]) for row in overlays),
        "wvr_count": sum(bool(row["wvr_flag"]) for row in overlays),
        "secondary_listing_count": sum(bool(row["secondary_listing_flag"]) for row in overlays),
        "biotech_chapter18a_count": sum(bool(row["biotech_chapter18a_flag"]) for row in overlays),
        "h_share_count": sum(bool(row["h_share_flag"]) for row in overlays),
        "multiple_hk_share_class_group_count": sum(row["relationship_type"] == "HK_MULTIPLE_SHARE_CLASSES" for row in relationships),
        "confirmed_relationship_count": sum(row["evidence_status"] == "CONFIRMED" for row in relationships),
        "review_queue_count": len(review_queue),
    }
    decision = {
        "program_id": PROGRAM_ID,
        "status": "FMDL5B2_ISSUER_AND_CROSS_MARKET_SEMANTICS_ACCEPTED" if not hard_failures else "FMDL5B2_REJECTED",
        "release_id": release_id,
        "release_sequence": 12,
        "authority": "HK_ISSUER_AND_CROSS_MARKET_SEMANTICS_ONLY",
        "source_release_id": SOURCE_RELEASE_ID,
        "canonical_sha256": canonical_sha,
        "metrics": metrics,
        "hard_failures": hard_failures,
        "candidate_pool_mutation_count": 0,
        "simulation_mutation_count": 0,
        "real_account_mutation_count": 0,
        "order_generation_count": 0,
        "trade_authority": "NONE",
        "limitations": [
            "A-share ticker relationships require direct mainland-exchange evidence and remain review items unless confirmed.",
            "US ADR or primary-listing ticker relationships are deferred until FMDL-6 official identifier integration.",
            "WVR, biotech, secondary-listing and H-share statuses are semantic flags, not investment recommendations.",
        ],
        "next_gate": "FMDL-5C_PRICE_VOLUME_CORPORATE_ACTION_AND_FX_STORE",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    (output / "FMDL5B2_DECISION.json").write_text(json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    manifest_files: dict[str, dict[str, object]] = {}
    for path in sorted(output.iterdir()):
        if path.is_file() and path.name != "FMDL5B2_MANIFEST.json":
            manifest_files[path.name] = {"sha256": sha256_bytes(path.read_bytes()), "size_bytes": path.stat().st_size}
    manifest = {"program_id": PROGRAM_ID, "release_id": release_id, "canonical_sha256": canonical_sha, "files": manifest_files}
    (output / "FMDL5B2_MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return decision


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    decision = build(Path(args.output))
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0 if not decision["hard_failures"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
