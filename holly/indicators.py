"""指標層：把原始數據整理成「美股交易日對齊」的指標表。純 pandas，不依賴 Streamlit。"""
from dataclasses import dataclass, field

import pandas as pd

from .config import FRED_SERIES

# 衍生指標 → 原始欄位，用來顯示「真正的」資料公布日期 (多個來源時取最舊的)
DATE_SOURCES = {
    "USDTWD_ROC_5D": ["USDTWD"], "HY_Spread_Chg_5D": ["High_Yield_Spread"], "VIX_Dev_20D": ["VIX"],
    "Total_Assets_T": ["Total_Assets"], "TGA_Account_T": ["TGA_Account"],
    "Net_Liquidity_T": ["Total_Assets", "TGA_Account", "ON_RRP"],
    "SMH_Dev_200D": ["SMH"], "SMH_Relative_Strength": ["SMH", "SPY"],
    "CPI_YoY": ["CPI"], "Core_PCE_YoY": ["Core_PCE"], "Buffett": ["Corp_Equities", "US_GDP"],
    "Reserves_T": ["Reserve_Balances"], "RRP_T": ["ON_RRP"],
    "Liquidity_Spread": ["SOFR", "IORB"], "Yield_Curve": ["DGS10", "DGS2"],
    "Sahm_Indicator": ["Unemployment_Rate"],
}


@dataclass
class Dataset:
    df: pd.DataFrame
    raw: pd.DataFrame = None            # 原始表 (含 NaN)，用來判斷哪天有真的公布數據
    obs_dates: dict = field(default_factory=dict)
    missing_fred: list = field(default_factory=list)

    def last_date(self, column):
        """指標真正的最後公布日；找不到來源時退回表格最後一列的日期。"""
        dates = [self.obs_dates[c] for c in DATE_SOURCES.get(column, [column]) if self.obs_dates.get(c) is not None]
        if dates:
            return min(dates)
        s = self.df[column].dropna() if column in self.df.columns else None
        return s.index[-1] if s is not None and not s.empty else None

    def release_points(self, column):
        """只取「有新數據公布」的交易日 (週/月/季資料不會被 ffill 成每日)。"""
        s = self.df[column].dropna()
        if self.raw is None:
            return s
        idx, days = self.df.index, set()
        for src in DATE_SOURCES.get(column, [column]):
            if src in self.raw.columns:
                pos = idx.searchsorted(self.raw[src].dropna().index)  # 非交易日公布 → 歸到下一個交易日
                days.update(idx[pos[pos < len(idx)]])
        return s[s.index.isin(days)] if days else s

    def latest(self, column, default=None):
        if column not in self.df.columns:
            return default
        s = self.df[column].dropna()
        return s.iloc[-1] if not s.empty else default


def build_dataset(raw):
    """原始表 → 對齊後的指標表。

    1. 先記下每個欄位最後一筆真實觀測日
    2. 只做 ffill (不 bfill，避免用未來數據回填過去)
    3. 只保留美股交易日，讓 5/20/200 日視窗都是真的交易日數
    """
    obs_dates = {c: raw[c].last_valid_index() for c in raw.columns}
    missing_fred = [c for c in FRED_SERIES if c not in raw.columns]

    df = raw.ffill()
    if "SPY" in raw.columns:
        df = df[raw["SPY"].notna()]
    df = add_indicators(df.copy())
    return Dataset(df=df, raw=raw, obs_dates=obs_dates, missing_fred=missing_fred)


def _has(df, *cols):
    return all(c in df.columns for c in cols)


def _dev_from_ma(s, window):
    ma = s.rolling(window=window).mean()
    return (s - ma) / ma * 100


def add_indicators(df):
    # 高頻戰術變數
    if _has(df, "USDTWD"):
        df["USDTWD_ROC_5D"] = df["USDTWD"].pct_change(periods=5) * 100
    if _has(df, "High_Yield_Spread"):
        df["HY_Spread_Chg_5D"] = df["High_Yield_Spread"].diff(periods=5)  # 單位：百分點
    if _has(df, "VIX"):
        df["VIX_Dev_20D"] = _dev_from_ma(df["VIX"], 20)

    # 半導體擁擠度
    if _has(df, "SMH"):
        df["SMH_Dev_200D"] = _dev_from_ma(df["SMH"], 200)
    if _has(df, "SMH", "SPY"):
        df["SMH_Relative_Strength"] = _dev_from_ma(df["SMH"] / df["SPY"], 60)
    if _has(df, "SOX", "SPY"):
        df["Semi_Relative_Strength_RawDev"] = _dev_from_ma(df["SOX"] / df["SPY"], 120) / 100

    # FRED 已用 pc1 回傳年增率
    if _has(df, "CPI"):
        df["CPI_YoY"] = df["CPI"]
    if _has(df, "Core_PCE"):
        df["Core_PCE_YoY"] = df["Core_PCE"]

    # 利率與流動性 (百萬美元 → 兆美元)
    if _has(df, "SOFR", "IORB"):
        df["Liquidity_Spread"] = df["SOFR"] - df["IORB"]
    if _has(df, "DGS10", "DGS2"):
        df["Yield_Curve"] = df["DGS10"] - df["DGS2"]
    for src, dst in [("Reserve_Balances", "Reserves_T"), ("ON_RRP", "RRP_T"),
                     ("Total_Assets", "Total_Assets_T"), ("TGA_Account", "TGA_Account_T")]:
        if _has(df, src):
            df[dst] = df[src] / 1e6
    if _has(df, "Total_Assets", "TGA_Account", "ON_RRP"):
        df["Net_Liquidity"] = df["Total_Assets"] - df["TGA_Account"] - df["ON_RRP"]
        df["Net_Liquidity_T"] = df["Net_Liquidity"] / 1e6
        df["Liquidity_ROC_4W"] = df["Net_Liquidity"].pct_change(periods=20) * 100

    # 巴菲特指標 = 企業股權市值 (百萬美元 → 十億) / GDP (十億美元)
    if _has(df, "Corp_Equities", "US_GDP"):
        df["Buffett"] = df["Corp_Equities"] / 1000 / df["US_GDP"] * 100

    # 薩姆規則：失業率 3 個月均值 - 過去 12 個月的最低 3 個月均值
    if _has(df, "Unemployment_Rate"):
        u3_ma3 = df["Unemployment_Rate"].rolling(window=63).mean()
        df["Sahm_Indicator"] = u3_ma3 - u3_ma3.rolling(window=252).min()

    return df


# ---------- PR 值 (百分位) ----------

def cycle_pr(s, invert=False):
    """週期型 PR：目前數值在歷史上的百分位。"""
    s = s.dropna()
    if s.empty:
        return None
    pr = s.rank(pct=True).iloc[-1] * 100
    return 100 - pr if invert else pr


def growth_pr(s, window):
    """成長型 PR：目前距離 N 日均線的乖離，在歷史乖離中的百分位。"""
    s = s.dropna()
    if len(s) <= window:
        return None
    return cycle_pr(_dev_from_ma(s, window))
