from __future__ import annotations

import os
import time
from typing import Any
from urllib.parse import urlparse

import requests

import fmdl6b_fetch
from fmdl6b_core import classify_failure, sha256_bytes


def _sec_headers(endpoint: str) -> dict[str, str]:
    host = urlparse(endpoint).netloc
    if not host.endswith("sec.gov"):
        return {}
    contact = os.getenv("SEC_CONTACT_EMAIL", "jl2642@users.noreply.github.com")
    identity = os.getenv("SEC_USER_AGENT", f"InvestmentOS Research {contact}")
    return {
        "Host": host,
        "From": contact,
        "User-Agent": identity,
        "Accept": "application/json,text/plain,*/*",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.sec.gov/",
    }


def fair_access_fetch_simple(
    session: requests.Session,
    interface: dict[str, Any],
    route: dict[str, Any],
    timeout: int,
) -> dict[str, Any]:
    observation = fmdl6b_fetch.base_observation(interface, route)
    started = time.perf_counter()
    payload = b""
    response: requests.Response | None = None
    try:
        headers = _sec_headers(route["endpoint"])
        if headers:
            time.sleep(0.25)
        response = session.get(route["endpoint"], timeout=timeout, headers=headers or None)
        payload = response.content
        observation["http_status"] = response.status_code
        observation["rate_limit_headers"] = {
            key: value for key, value in response.headers.items()
            if key.lower().startswith(("x-ratelimit", "retry-after"))
        }
        if response.status_code >= 400:
            raise requests.HTTPError(f"HTTP {response.status_code}")
        observation.update(fmdl6b_fetch.PARSERS[route["parser"]](payload))
        observation["access_status"] = "SUCCESS"
        observation["github_actions_compatibility"] = True
    except Exception as error:
        observation["error"] = f"{type(error).__name__}: {error}"[:1000]
        if response is not None and response.status_code < 400 and payload:
            observation["failure_mode"] = "SCHEMA_OR_PARSE_DRIFT"
        else:
            observation["failure_mode"] = classify_failure(error, getattr(response, "status_code", None), payload)
    observation["latency_ms"] = round((time.perf_counter() - started) * 1000, 3)
    observation["response_bytes"] = len(payload)
    if payload:
        observation["payload_sha256"] = sha256_bytes(payload)
    return observation


def install_sec_request_adapter() -> None:
    fmdl6b_fetch.fetch_simple = fair_access_fetch_simple
