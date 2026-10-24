import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from holly.config import FRED_SERIES, YF_TICKERS  # noqa: E402

BASE = {
    "Total_Assets": 7e6, "ON_RRP": 3e5, "Reserve_Balances": 3.2e6, "TGA_Account": 8e5, "IORB": 4.4,
    "SOFR": 4.3, "DGS30": 4.6, "DGS10": 4.1, "DGS2": 3.6, "CPI": 2.9, "Core_PCE": 2.8,
    "Unemployment_Rate": 4.2, "High_Yield_Spread": 3.0, "Corp_Equities": 6e7, "US_GDP": 3e4,
}
FREQ = {"Total_Assets": "W-WED", "Reserve_Balances": "W-WED", "TGA_Account": "W-WED", "CPI": "MS",
        "Core_PCE": "MS", "Unemployment_Rate": "MS", "Corp_Equities": "QS", "US_GDP": "QS"}


def _walk(n, base, seed):
    rng = np.random.default_rng(seed)
    return base * (1 + np.cumsum(rng.normal(0, 0.003, n)))


def make_raw(start="2018-01-01", end="2026-10-23"):
    """模擬 data.load_raw() 的輸出：不同頻率的欄位 outer join，保留 NaN。"""
    cols = []
    for i, col in enumerate(FRED_SERIES):
        idx = pd.date_range(start, end, freq=FREQ.get(col, "B"))
        cols.append(pd.Series(_walk(len(idx), BASE[col], i), index=idx, name=col))
    trading = pd.bdate_range(start, end)
    for i, col in enumerate(YF_TICKERS):
        cols.append(pd.Series(_walk(len(trading), 100.0, 100 + i), index=trading, name=col))
    return pd.concat(cols, axis=1, sort=True)


@pytest.fixture
def raw():
    return make_raw()
