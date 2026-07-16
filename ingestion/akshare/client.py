"""Resilient AKShare adapter for the FMDL-1 A-share MVP."""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError, version
import time
from typing import Callable

import akshare as ak
import pandas as pd


@dataclass
class SourceCall:
    function: str
    data: pd.DataFrame
    warnings: list[str] = field(default_factory=list)
    retries: int = 0


@dataclass
class AkshareBundle:
    spot: SourceCall
    sh_main: SourceCall
    sh_star: SourceCall
    sz_a: SourceCall
    bj_a: SourceCall
    trade_calendar: SourceCall
    adapter_version: str


def _call_with_retry(
    function_name: str,
    call: Callable[[], pd.DataFrame],
    *,
    attempts: int = 3,
    base_sleep_seconds: float = 2.0,
    optional: bool = False,
) -> SourceCall:
    warnings: list[str] = []
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            data = call()
            if data is None or not isinstance(data, pd.DataFrame):
                raise TypeError(f"{function_name} did not return a DataFrame")
            if data.empty:
                raise ValueError(f"{function_name} returned an empty DataFrame")
            return SourceCall(
                function=function_name,
                data=data,
                warnings=warnings,
                retries=attempt,
            )
        except Exception as exc:
            last_error = exc
            warnings.append(f"attempt_{attempt + 1}: {type(exc).__name__}: {exc}")
            if attempt + 1 < attempts:
                time.sleep(base_sleep_seconds * (2**attempt))
    if optional:
        warnings.append("optional_source_unavailable")
        return SourceCall(
            function=function_name,
            data=pd.DataFrame(),
            warnings=warnings,
            retries=max(0, attempts - 1),
        )
    raise RuntimeError(
        f"Required source {function_name} failed after {attempts} attempts: {last_error}"
    ) from last_error


def _adapter_version() -> str:
    try:
        return version("akshare")
    except PackageNotFoundError:
        return "unknown"


def fetch_a_share_bundle() -> AkshareBundle:
    """Fetch the required market-wide table and optional exchange masters."""

    spot = _call_with_retry(
        "stock_zh_a_spot_em",
        ak.stock_zh_a_spot_em,
        attempts=4,
        base_sleep_seconds=3.0,
        optional=False,
    )
    sh_main = _call_with_retry(
        "stock_info_sh_name_code:主板A股",
        lambda: ak.stock_info_sh_name_code(symbol="主板A股"),
        optional=True,
    )
    sh_star = _call_with_retry(
        "stock_info_sh_name_code:科创板",
        lambda: ak.stock_info_sh_name_code(symbol="科创板"),
        optional=True,
    )
    sz_a = _call_with_retry(
        "stock_info_sz_name_code:A股列表",
        lambda: ak.stock_info_sz_name_code(symbol="A股列表"),
        optional=True,
    )
    bj_a = _call_with_retry(
        "stock_info_bj_name_code",
        ak.stock_info_bj_name_code,
        optional=True,
    )
    trade_calendar = _call_with_retry(
        "tool_trade_date_hist_sina",
        ak.tool_trade_date_hist_sina,
        optional=True,
    )
    return AkshareBundle(
        spot=spot,
        sh_main=sh_main,
        sh_star=sh_star,
        sz_a=sz_a,
        bj_a=bj_a,
        trade_calendar=trade_calendar,
        adapter_version=_adapter_version(),
    )
