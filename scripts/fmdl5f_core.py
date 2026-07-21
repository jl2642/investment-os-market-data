#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pandas as pd

PROGRAM_ID = "FMDL-5F"
ACCEPTED_STATUS = "FMDL5F_PUBLIC_EQUITY_RESEARCH_ADAPTER_ACCEPTED"
CONTRACT_PATH = Path("config/fmdl5f_public_equity_research_contract.json")

def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_profile_pack(path: Path) -> dict[str, Any]:
    spec = importlib.util.spec_from_file_location("fmdl5f_research_profiles", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("FMDL5F_PROFILE_MODULE_LOAD_FAILURE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.load_profiles()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def stable_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def as_bool(value: Any) -> bool:
    return value is True or str(value).strip().lower() in {"1", "true", "yes", "y"}


def clean_text(value: Any) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    return str(value).strip()


def iso_or_empty(value: Any) -> str:
    ts = pd.to_datetime(value, errors="coerce", utc=True)
    return "" if pd.isna(ts) else ts.isoformat()


def record_hash(row: pd.Series | dict[str, Any], fields: list[str] | None = None) -> str:
    payload = dict(row) if isinstance(row, dict) else row.to_dict()
    if fields is not None:
        payload = {key: payload.get(key) for key in fields}
    return stable_hash(payload)


def load_inputs(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    contract = read_json(root / CONTRACT_PATH)
    entry = contract["entry_gate"]
    pointer = read_json(root / entry["pointer_path"])
    decision = read_json(root / entry["decision_path"])
    errors: list[str] = []
    if pointer.get("status") != entry["required_status"]:
        errors.append("FMDL5E_POINTER_STATUS")
    if decision.get("status") != entry["required_status"]:
        errors.append("FMDL5E_DECISION_STATUS")
    if pointer.get("repair_round") != entry["required_repair_round"]:
        errors.append("FMDL5E_REPAIR_ROUND")
    if pointer.get("next_gate") != entry["required_next_gate"]:
        errors.append("FMDL5E_NEXT_GATE")
    if pointer.get("release_id") != contract["source_release_ids"]["fmdl5e"]:
        errors.append("FMDL5E_RELEASE_MISMATCH")
    if decision.get("source_release_ids", {}).get("fmdl5d") != contract["source_release_ids"]["fmdl5d"]:
        errors.append("FMDL5D_RELEASE_MISMATCH")
    if decision.get("source_release_ids", {}).get("fmdl5c") != contract["source_release_ids"]["fmdl5c"]:
        errors.append("FMDL5C_RELEASE_MISMATCH")
    if decision.get("hard_failures"):
        errors.append("FMDL5E_HARD_FAILURE")
    if decision.get("trade_authority") != "NONE" or pointer.get("trade_authority") != "NONE":
        errors.append("UPSTREAM_TRADE_AUTHORITY")

    paths = contract["inputs"]
    fmdl5e_manifest = read_json(root / paths["fmdl5e_manifest"])
    fmdl5d_decision = read_json(root / paths["fmdl5d_decision"])
    if fmdl5e_manifest.get("release_id") != contract["source_release_ids"]["fmdl5e"]:
        errors.append("FMDL5E_MANIFEST_RELEASE_MISMATCH")
    if fmdl5e_manifest.get("canonical_sha256") != pointer.get("canonical_sha256"):
        errors.append("FMDL5E_MANIFEST_CANONICAL_MISMATCH")
    if fmdl5d_decision.get("status") != "FMDL5D_HKEX_DISCLOSURE_AND_FINANCIAL_NORMALIZATION_ACCEPTED_WITH_CONTROLLED_QUARANTINE":
        errors.append("FMDL5D_DECISION_STATUS")
    if fmdl5d_decision.get("release_id") != contract["source_release_ids"]["fmdl5d"]:
        errors.append("FMDL5D_DECISION_RELEASE_MISMATCH")
    if fmdl5d_decision.get("hard_failures"):
        errors.append("FMDL5D_HARD_FAILURE")
    if fmdl5d_decision.get("trade_authority") != "NONE":
        errors.append("FMDL5D_TRADE_AUTHORITY")
    if errors:
        raise RuntimeError(";".join(errors))

    data = {
        "pointer": pointer,
        "fmdl5e_decision": decision,
        "longlist": pd.read_csv(root / paths["longlist"], dtype={"stock_code_5d": str}, encoding="utf-8-sig"),
        "factor_table": pd.read_parquet(root / paths["factor_table"]),
        "fmdl5e_manifest": fmdl5e_manifest,
        "fmdl5d_decision": fmdl5d_decision,
        "financial_current": pd.read_csv(root / paths["financial_current"], dtype={"stock_code_5d": str}, encoding="utf-8-sig"),
        "disclosures": pd.read_csv(root / paths["official_disclosures"], dtype={"stock_code_5d": str}, encoding="utf-8-sig"),
        "profiles": load_profile_pack(root / paths["research_profiles"]),
        "source_hashes": {key: sha256_file(root / path) for key, path in paths.items()},
    }
    return contract, data


def case_types(row: pd.Series, profile: dict[str, Any]) -> list[str]:
    result = set(profile.get("case_types", []))
    if as_bool(row.get("a_share_class_exists")) or as_bool(row.get("h_share_flag")):
        result.add("A_H")
    if (finite(row.get("dividend_yield_365d")) or 0.0) >= 0.04:
        result.add("HIGH_DIVIDEND")
    name = f"{clean_text(row.get('official_security_name_en'))} {clean_text(row.get('official_issuer_name_en'))}".upper()
    if as_bool(row.get("wvr_flag")) or any(token in name for token in ["NETEASE", "INTERNET", "ONLINE", "GAME"]):
        result.add("WVR_OR_INTERNET")
    if (finite(row.get("corporate_action_count_365d")) or 0.0) > 0:
        result.add("CORPORATE_ACTION")
    return sorted(result)


def disclosure_score(row: pd.Series, policy: dict[str, Any]) -> tuple[int, pd.Timestamp, str]:
    title = clean_text(row.get("title")).upper()
    filing_type = clean_text(row.get("filing_type"))
    excluded = any(token in title for token in policy["excluded_title_tokens"])
    preferred = any(token in title for token in policy["preferred_title_tokens"])
    type_allowed = filing_type in policy["allowed_official_filing_types"]
    explicit_period = clean_text(row.get("report_period_end")) != ""
    score = (100 if type_allowed else 0) + (40 if preferred else 0) + (20 if explicit_period else 0) - (100 if excluded else 0)
    available = pd.to_datetime(row.get("available_from"), errors="coerce", utc=True)
    return score, available, clean_text(row.get("filing_id"))


def select_public_sources(
    code: str,
    disclosures: pd.DataFrame,
    financial_row: pd.Series | None,
    as_of: pd.Timestamp,
    contract: dict[str, Any],
) -> list[dict[str, Any]]:
    policy = contract["source_policy"]
    frame = disclosures[disclosures["stock_code_5d"].astype(str).str.zfill(5) == code].copy()
    frame["available_ts"] = pd.to_datetime(frame["available_from"], errors="coerce", utc=True)
    cutoff = (pd.Timestamp(as_of.date()).tz_localize("Asia/Hong_Kong") + pd.Timedelta(hours=23, minutes=59)).tz_convert("UTC")
    frame = frame[frame["available_ts"].notna() & (frame["available_ts"] <= cutoff)]
    if not frame.empty:
        frame["selection_score"] = frame.apply(lambda r: disclosure_score(r, policy)[0], axis=1)
        frame = frame.sort_values(["selection_score", "available_ts", "filing_id"], ascending=[False, False, True])
    selected: list[dict[str, Any]] = []
    used_urls: set[str] = set()
    used_periods: set[str] = set()
    for _, row in frame.iterrows():
        if int(row["selection_score"]) < 100:
            continue
        url = clean_text(row.get("filing_url"))
        if not url or url in used_urls:
            continue
        period = clean_text(row.get("report_period_end"))
        if period and period in used_periods:
            continue
        selected.append({
            "source_type": "HKEX_OFFICIAL_DISCLOSURE",
            "source_tier": clean_text(row.get("source_tier")) or "OFFICIAL_PRIMARY",
            "source_id": clean_text(row.get("filing_id")) or clean_text(row.get("news_id")),
            "title": clean_text(row.get("title")),
            "url": url,
            "filing_type": clean_text(row.get("filing_type")),
            "report_period_end": period,
            "available_from": iso_or_empty(row.get("available_from")),
            "source_record_sha256": clean_text(row.get("source_record_sha256")),
        })
        used_urls.add(url)
        if period:
            used_periods.add(period)
        if len(selected) >= 2:
            break

    if financial_row is not None:
        url = clean_text(financial_row.get("official_filing_url"))
        if url and url not in used_urls:
            available = pd.to_datetime(financial_row.get("available_from"), errors="coerce", utc=True)
            if pd.notna(available) and available <= cutoff:
                selected.append({
                    "source_type": "FMDL5D_OFFICIAL_CURRENT_FINANCIAL_FILING",
                    "source_tier": "OFFICIAL_PRIMARY",
                    "source_id": clean_text(financial_row.get("official_filing_id")),
                    "title": f"FMDL-5D Current financial source for {code}",
                    "url": url,
                    "filing_type": "FINANCIAL_CURRENT_SOURCE",
                    "report_period_end": clean_text(financial_row.get("period_end")),
                    "available_from": iso_or_empty(financial_row.get("available_from")),
                    "source_record_sha256": record_hash(financial_row),
                })
                used_urls.add(url)
    return selected[:3]


def context_summary(row: pd.Series) -> dict[str, Any]:
    pe = finite(row.get("pe_ratio"))
    dy = finite(row.get("dividend_yield_365d"))
    roe = finite(row.get("roe"))
    return {
        "screen_rank": int(row["overall_rank"]),
        "research_priority": clean_text(row.get("research_priority")),
        "primary_sleeve": clean_text(row.get("primary_sleeve")),
        "sleeves": clean_text(row.get("sleeves")).split("|") if clean_text(row.get("sleeves")) else [],
        "aggregate_score": finite(row.get("aggregate_score")),
        "return_60d": finite(row.get("return_60d")),
        "return_120d": finite(row.get("return_120d")),
        "volatility_60d": finite(row.get("volatility_60d")),
        "max_drawdown_120d": finite(row.get("max_drawdown_120d")),
        "roe": roe,
        "operating_margin": finite(row.get("operating_margin")),
        "earnings_yield": finite(row.get("earnings_yield")),
        "pe_ratio": pe,
        "dividend_yield_365d": dy,
        "corporate_action_count_365d": int(finite(row.get("corporate_action_count_365d")) or 0),
        "valuation_context": (
            f"Cross-sectional screen evidence: PE {pe:.2f}x and trailing cash-dividend yield {dy:.2%}; not a target price."
            if pe is not None and dy is not None
            else f"Cross-sectional screen evidence: trailing cash-dividend yield {dy:.2%}; PE unavailable or not decision-grade."
            if dy is not None
            else "Valuation evidence is incomplete; no target price or cheap/expensive conclusion is created."
        ),
    }
