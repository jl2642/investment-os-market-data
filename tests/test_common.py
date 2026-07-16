from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from pipeline.common import canonical_symbol, latest_completed_trade_date


def test_canonical_symbols() -> None:
    assert canonical_symbol("688001") == "688001.SH"
    assert canonical_symbol("300001") == "300001.SZ"
    assert canonical_symbol("832000") == "832000.BJ"


def test_completed_trade_date_excludes_open_session() -> None:
    calendar = pd.DataFrame({"trade_date": ["2026-07-15", "2026-07-16"]})
    current = datetime(2026, 7, 16, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    assert latest_completed_trade_date(calendar, current).isoformat() == "2026-07-15"
