from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROUTES = [
    {
        "route_id": "SEC_COMPANY_TICKERS_EXCHANGE",
        "url": "https://www.sec.gov/files/company_tickers_exchange.json",
        "expected_magic": b"{",
        "kind": "FULL_SMALL_JSON",
    },
    {
        "route_id": "SEC_SUBMISSIONS_BULK_ZIP",
        "url": "https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip",
        "expected_magic": b"PK",
        "kind": "RANGE_PROBE_ZIP",
    },
    {
        "route_id": "SEC_COMPANYFACTS_BULK_ZIP",
        "url": "https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip",
        "expected_magic": b"PK",
        "kind": "RANGE_PROBE_ZIP",
    },
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def session() -> requests.Session:
    retry = Retry(
        total=2,
        connect=2,
        read=2,
        status=2,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "HEAD"}),
        raise_on_status=False,
    )
    s = requests.Session()
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.headers.update(
        {
            "User-Agent": os.getenv(
                "SEC_USER_AGENT",
                "InvestmentOS-FMDL6X2E/1.0 jl2642@users.noreply.github.com",
            ),
            "From": "jl2642@users.noreply.github.com",
            "Accept-Encoding": "gzip, deflate",
            "Accept": "application/json,application/zip,*/*",
        }
    )
    return s


def probe() -> dict:
    s = session()
    observations = []
    for route in ROUTES:
        started = time.monotonic()
        headers = {}
        status = None
        error = None
        payload = b""
        try:
            request_headers = {"Range": "bytes=0-65535"} if route["kind"] == "RANGE_PROBE_ZIP" else {}
            response = s.get(route["url"], headers=request_headers, timeout=45, stream=True)
            status = response.status_code
            headers = {
                k.lower(): v
                for k, v in response.headers.items()
                if k.lower()
                in {
                    "content-type",
                    "content-length",
                    "content-range",
                    "accept-ranges",
                    "etag",
                    "last-modified",
                    "retry-after",
                }
            }
            if route["kind"] == "FULL_SMALL_JSON":
                payload = response.content
            else:
                payload = response.raw.read(65536, decode_content=True)
            response.close()
        except Exception as exc:  # noqa: BLE001
            error = f"{type(exc).__name__}:{exc}"
        magic_ok = payload.startswith(route["expected_magic"])
        success = error is None and status in {200, 206} and magic_ok
        controlled_block = error is None and status == 403
        parsed = None
        if route["kind"] == "FULL_SMALL_JSON" and success:
            try:
                value = json.loads(payload.decode("utf-8-sig"))
                parsed = {
                    "fields": value.get("fields"),
                    "row_count": len(value.get("data", [])),
                }
            except Exception as exc:  # noqa: BLE001
                success = False
                error = f"JSON_PARSE:{type(exc).__name__}:{exc}"
        observations.append(
            {
                "route_id": route["route_id"],
                "official_source_url": route["url"],
                "retrieved_at": utc_now(),
                "http_status": status,
                "headers": headers,
                "probe_bytes": len(payload),
                "probe_sha256": hashlib.sha256(payload).hexdigest() if payload else None,
                "magic_ok": magic_ok,
                "parsed": parsed,
                "success": success,
                "controlled_block": controlled_block,
                "error": error,
                "latency_ms": round((time.monotonic() - started) * 1000, 1),
                "source_authority": "SEC_OFFICIAL",
                "no_silent_replacement_assertion": True,
            }
        )
    all_success = all(o["success"] for o in observations)
    repeatable_controlled_403 = len(observations) == len(ROUTES) and all(o["controlled_block"] for o in observations)
    return {
        "phase_id": "FMDL-6X2-E",
        "captured_at": utc_now(),
        "execution_environment": "GITHUB_HOSTED_RUNNER_PROBE",
        "observations": observations,
        "all_routes_success": all_success,
        "repeatable_controlled_403": repeatable_controlled_403,
        "probe_gate_status": "PASS_DIRECT" if all_success else "PASS_CONTROLLED_403" if repeatable_controlled_403 else "FAIL",
    }


def main() -> None:
    output = Path("outputs/fmdl6x2e/probe/FMDL6X2E_SEC_ROUTE_PROBE.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    result = probe()
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["probe_gate_status"] == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
