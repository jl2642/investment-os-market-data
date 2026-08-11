from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

FIELDS = [
    "security_code", "security_name", "exchange", "market_segment",
    "last_price", "change_pct", "change_amount", "volume", "turnover_amount",
    "amplitude_pct", "turnover_rate_pct", "pe_ttm", "pb", "high", "low",
    "open", "prev_close", "total_market_cap", "float_market_cap",
    "source_provider", "source_market_id", "source_timestamp",
    "provider_session_date",
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def clean(value):
    return None if value in (None, "", "-", "--") else value


def market_info(code: str, market_id: str | None = None) -> tuple[str, str]:
    if code.startswith(("60", "68")):
        return "SSE", "STAR" if code.startswith("68") else "MAIN"
    if code.startswith(("00", "30")):
        return "SZSE", "CHINEXT" if code.startswith("30") else "MAIN"
    if code.startswith(("43", "83", "87", "88", "92")):
        return "BSE", "BSE"
    return ("SSE", "UNKNOWN") if market_id == "1" else ("SZSE", "UNKNOWN")


def request_bytes(url: str, params: dict[str, str], timeout: int) -> tuple[bytes, str]:
    full_url = url + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(
        full_url,
        headers={
            "User-Agent": "Mozilla/5.0 Investment-OS-WP3-2A/1.0",
            "Referer": "https://quote.eastmoney.com/",
            "Accept": "application/json,text/plain,*/*",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read(), full_url


def eastmoney_session_probe(output: Path, timeout: int) -> tuple[str | None, dict]:
    """Resolve the completed provider session from a benchmark quote timestamp.

    Eastmoney's full-universe clist occasionally omits f124 on every row even
    though the quote payload is otherwise complete. In that case, use the same
    provider's Shanghai Composite benchmark timestamp (f86) as a bounded
    session-date authority instead of discarding a complete universe solely
    because row-level timestamps are absent.
    """
    url = "https://push2.eastmoney.com/api/qt/stock/get"
    params = {
        "secid": "1.000001",
        "fields": "f57,f58,f86",
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
    }
    raw, full_url = request_bytes(url, params, timeout)
    raw_path = output / "eastmoney_session_probe.json"
    raw_path.write_bytes(raw)
    payload = json.loads(raw.decode("utf-8"))
    data = payload.get("data") or {}
    ts = data.get("f86")
    session = None
    if isinstance(ts, (int, float)) and ts > 0:
        session = datetime.fromtimestamp(int(ts), ZoneInfo("Asia/Shanghai")).date().isoformat()
    return session, {
        "file": raw_path.name,
        "size_bytes": len(raw),
        "sha256": sha256_bytes(raw),
        "request_url": full_url,
        "benchmark_security": "000001.SH",
        "benchmark_timestamp": int(ts) if isinstance(ts, (int, float)) and ts > 0 else None,
        "derived_session": session,
        "status": "PASS" if session else "UNRESOLVED",
    }


def eastmoney(output: Path, page_size: int, timeout: int) -> tuple[list[dict], dict]:
    url = "https://82.push2.eastmoney.com/api/qt/clist/get"
    base = {
        "po": "1", "np": "2", "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": "2", "invt": "2", "fid": "f3",
        "fs": "m:0 t:6,m:0 t:80,m:1 t:2,m:1 t:23,m:0 t:81 s:2048",
        "fields": (
            "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f13,f14,f15,f16,f17,"
            "f18,f20,f21,f23,f24,f25,f22,f11,f62,f124,f128,f136,f115,f152"
        ),
    }
    rows: list[dict] = []
    raw_pages = []
    page = 1
    declared_total = None
    timestamps: list[int] = []
    while True:
        params = dict(base, pn=str(page), pz=str(page_size))
        raw, full_url = request_bytes(url, params, timeout)
        raw_path = output / f"eastmoney_page_{page:03d}.json"
        raw_path.write_bytes(raw)
        raw_pages.append({
            "page": page, "file": raw_path.name, "size_bytes": len(raw),
            "sha256": sha256_bytes(raw), "request_url": full_url,
        })
        payload = json.loads(raw.decode("utf-8"))
        data = payload.get("data") or {}
        diff = data.get("diff") or []
        if declared_total is None:
            declared_total = int(data.get("total") or 0)
        iterable = diff.values() if isinstance(diff, dict) else diff
        batch = list(iterable)
        if not batch:
            break
        for item in batch:
            code = str(item.get("f12") or "").zfill(6)
            market_id = None if item.get("f13") is None else str(item.get("f13"))
            exchange, segment = market_info(code, market_id)
            ts = item.get("f124")
            session = None
            if isinstance(ts, (int, float)) and ts > 0:
                timestamps.append(int(ts))
                session = datetime.fromtimestamp(int(ts), ZoneInfo("Asia/Shanghai")).date().isoformat()
            rows.append({
                "security_code": code, "security_name": item.get("f14"),
                "exchange": exchange, "market_segment": segment,
                "last_price": clean(item.get("f2")), "change_pct": clean(item.get("f3")),
                "change_amount": clean(item.get("f4")), "volume": clean(item.get("f5")),
                "turnover_amount": clean(item.get("f6")), "amplitude_pct": clean(item.get("f7")),
                "turnover_rate_pct": clean(item.get("f8")), "pe_ttm": clean(item.get("f9")),
                "pb": clean(item.get("f23")), "high": clean(item.get("f15")),
                "low": clean(item.get("f16")), "open": clean(item.get("f17")),
                "prev_close": clean(item.get("f18")), "total_market_cap": clean(item.get("f20")),
                "float_market_cap": clean(item.get("f21")), "source_provider": "eastmoney_public",
                "source_market_id": market_id,
                "source_timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                "provider_session_date": session,
            })
        if len(rows) >= declared_total or len(batch) < page_size:
            break
        page += 1
        if page > 100:
            raise RuntimeError("Eastmoney pagination safety limit exceeded")
        time.sleep(0.2)
    session_counts = Counter(
        datetime.fromtimestamp(ts, ZoneInfo("Asia/Shanghai")).date().isoformat()
        for ts in timestamps
    )
    modal_session = session_counts.most_common(1)[0][0] if session_counts else None
    modal_ratio = (
        session_counts[modal_session] / len(timestamps) if modal_session and timestamps else 0.0
    )
    session_probe = None
    freshness_authority = "PROVIDER_ROW_TIMESTAMP_F124"
    if rows and not modal_session:
        try:
            modal_session, session_probe = eastmoney_session_probe(output, timeout)
        except Exception as exc:
            session_probe = {
                "status": "FAIL",
                "error": f"{type(exc).__name__}: {exc}",
                "derived_session": None,
            }
        if modal_session:
            modal_ratio = 1.0
            freshness_authority = "PROVIDER_BENCHMARK_TIMESTAMP_F86"
            for row in rows:
                row["provider_session_date"] = modal_session
        else:
            freshness_authority = "UNRESOLVED"
    return rows, {
        "provider": "eastmoney_public", "declared_total": declared_total,
        "raw_pages": raw_pages, "session_counts": dict(session_counts),
        "derived_session": modal_session, "derived_session_ratio": modal_ratio,
        "session_probe": session_probe,
        "freshness_authority": freshness_authority,
    }


def sina(output: Path, page_size: int, timeout: int, manual_session: str | None) -> tuple[list[dict], dict]:
    url = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
    rows: list[dict] = []
    raw_pages = []
    page = 1
    while True:
        params = {
            "page": str(page), "num": str(page_size), "sort": "symbol", "asc": "1",
            "node": "hs_a", "symbol": "", "_s_r_a": "page",
        }
        raw, full_url = request_bytes(url, params, timeout)
        raw_path = output / f"sina_page_{page:03d}.json"
        raw_path.write_bytes(raw)
        raw_pages.append({
            "page": page, "file": raw_path.name, "size_bytes": len(raw),
            "sha256": sha256_bytes(raw), "request_url": full_url,
        })
        batch = json.loads(raw.decode("utf-8"))
        if not batch:
            break
        for item in batch:
            code = str(item.get("code") or str(item.get("symbol") or "")[-6:]).zfill(6)
            exchange, segment = market_info(code)
            rows.append({
                "security_code": code, "security_name": item.get("name"),
                "exchange": exchange, "market_segment": segment,
                "last_price": clean(item.get("trade")), "change_pct": clean(item.get("changepercent")),
                "change_amount": clean(item.get("pricechange")), "volume": clean(item.get("volume")),
                "turnover_amount": clean(item.get("amount")), "amplitude_pct": None,
                "turnover_rate_pct": clean(item.get("turnoverratio")), "pe_ttm": clean(item.get("per")),
                "pb": clean(item.get("pb")), "high": clean(item.get("high")),
                "low": clean(item.get("low")), "open": clean(item.get("open")),
                "prev_close": clean(item.get("settlement")), "total_market_cap": clean(item.get("mktcap")),
                "float_market_cap": clean(item.get("nmc")), "source_provider": "sina_public",
                "source_market_id": None,
                "source_timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                "provider_session_date": manual_session,
            })
        if len(batch) < page_size:
            break
        page += 1
        if page > 200:
            raise RuntimeError("Sina pagination safety limit exceeded")
        time.sleep(0.2)
    return rows, {
        "provider": "sina_public", "declared_total": len(rows), "raw_pages": raw_pages,
        "derived_session": manual_session,
        "derived_session_ratio": 1.0 if manual_session else 0.0,
        "freshness_authority": "WORKFLOW_DISPATCH_OVERRIDE" if manual_session else "UNRESOLVED",
    }


def write_csv(rows: list[dict], path: Path) -> None:
    rows = sorted(rows, key=lambda r: (r["exchange"], r["security_code"]))
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader(); writer.writerows(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--manual-session", default="")
    ap.add_argument("--provider-policy", default="configured")
    args = ap.parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)
    raw_dir = out / "raw"; raw_dir.mkdir(exist_ok=True)
    manual_session = args.manual_session.strip() or None
    providers = config["provider_order"] if args.provider_policy == "configured" else [args.provider_policy]
    attempts = []
    selected_rows = None; selected_meta = None
    delays = [int(x) for x in config["retry_delays_seconds"]]
    for provider in providers:
        for attempt_number, delay in enumerate(delays, start=1):
            if delay:
                time.sleep(delay + random.uniform(0, min(3, delay / 10)))
            attempt_dir = raw_dir / f"{provider}_attempt_{attempt_number}"
            attempt_dir.mkdir(parents=True, exist_ok=True)
            started = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
            try:
                if provider == "eastmoney_public":
                    rows, meta = eastmoney(attempt_dir, 500, int(config["http_timeout_seconds"]))
                elif provider == "sina_public":
                    rows, meta = sina(attempt_dir, 100, int(config["http_timeout_seconds"]), manual_session)
                else:
                    raise ValueError(f"Unsupported provider: {provider}")
                unique_codes = len({r["security_code"] for r in rows})
                attempts.append({
                    "provider": provider, "attempt": attempt_number, "status": "PASS",
                    "started_at": started, "rows": len(rows), "unique_codes": unique_codes,
                    "metadata": meta,
                })
                if rows:
                    selected_rows, selected_meta = rows, meta
                    break
            except Exception as exc:
                attempts.append({
                    "provider": provider, "attempt": attempt_number, "status": "FAIL",
                    "started_at": started, "error": f"{type(exc).__name__}: {exc}",
                })
        if selected_rows:
            break

    manifest = {
        "manifest_id": "WP3_2A_ACQUISITION_MANIFEST",
        "run_status": "PASS" if selected_rows else "FAIL",
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "manual_session_override": manual_session,
        "attempts": attempts,
        "selected_provider": selected_meta.get("provider") if selected_meta else None,
        "derived_session": selected_meta.get("derived_session") if selected_meta else None,
        "derived_session_ratio": selected_meta.get("derived_session_ratio") if selected_meta else 0.0,
        "freshness_authority": selected_meta.get("freshness_authority") if selected_meta else None,
        "trade_authority": "NONE",
    }
    if selected_rows:
        derived_session = selected_meta.get("derived_session")
        session = manual_session or derived_session
        failures = []
        if not session:
            failures.append("SESSION_DATE_UNRESOLVED")
        if manual_session and derived_session and manual_session != derived_session and config.get("manual_session_must_match_provider_timestamp", True):
            failures.append("MANUAL_SESSION_PROVIDER_TIMESTAMP_MISMATCH")
        if selected_meta.get("provider") == "eastmoney_public" and float(selected_meta.get("derived_session_ratio") or 0.0) < float(config.get("minimum_session_timestamp_ratio", 0.80)):
            failures.append("PROVIDER_SESSION_TIMESTAMP_RATIO_BELOW_THRESHOLD")
        if session and date.fromisoformat(session) < date.fromisoformat(config["minimum_accepted_session"]):
            failures.append("SESSION_BELOW_MINIMUM_ACCEPTED_WATERMARK")
        if failures:
            manifest["run_status"] = "FAIL"
            manifest["failure_reasons"] = failures
            manifest["session"] = session
        else:
            current = out / "A_SHARE_FULL_UNIVERSE_CURRENT.csv"
            write_csv(selected_rows, current)
            manifest.update({
                "session": session, "rows": len(selected_rows),
                "unique_codes": len({r["security_code"] for r in selected_rows}),
                "current_file": current.name, "current_sha256": sha256_file(current),
                "provider_changed_from_previous": selected_meta.get("provider") != config["previous_canonical_provider"],
                "provider_change_requires_human_review": bool(config["provider_change_requires_human_review"]),
            })
    (out / "ACQUISITION_MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (out / "SESSION.txt").write_text(str(manifest.get("session") or "") + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    raise SystemExit(0 if manifest["run_status"] == "PASS" else 2)

if __name__ == "__main__":
    main()
