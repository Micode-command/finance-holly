"""訊號層：把指標轉成分數、條件與機率。純計算，不碰畫面。"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .indicators import cycle_pr, growth_pr


# ---------- 四大長線買入確認信號 ----------

BOTTOM_FISHING_COLUMNS = ["Brent", "CPI_YoY", "DGS10", "DGS30", "DGS2", "IORB"]


@dataclass
class BottomFishing:
    values: dict        # 欄位 → 最新值
    oil_ok: bool        # 布蘭特 < 90
    cpi_ok: bool        # CPI 年增 < 2.5%
    long_rates_ok: bool # 10 年 < 4.3% 且 30 年 < 4.5%
    cut_priced_in: bool # 2 年債 < IORB - 1 碼

    @property
    def met(self):
        return sum([self.oil_ok, self.cpi_ok, self.long_rates_ok, self.cut_priced_in])


def bottom_fishing_signals(df):
    """缺任何必要數據時回傳 None，避免用預設值算出假訊號。"""
    if any(c not in df.columns or df[c].dropna().empty for c in BOTTOM_FISHING_COLUMNS):
        return None
    v = {c: df[c].dropna().iloc[-1] for c in BOTTOM_FISHING_COLUMNS}
    return BottomFishing(
        values=v,
        oil_ok=v["Brent"] < 90.0,
        cpi_ok=v["CPI_YoY"] < 2.5,
        long_rates_ok=v["DGS10"] < 4.3 and v["DGS30"] < 4.5,
        cut_priced_in=v["DGS2"] < v["IORB"] - 0.25,
    )


# ---------- 市場體制機率與 PR 矩陣 (給 AI 用) ----------

def _latest(df, col, default=0.0):
    if col not in df.columns:
        return default
    s = df[col].dropna()
    return s.iloc[-1] if not s.empty else default


SWAN_DROP = -0.07       # 5 個交易日內最深跌幅 ≥ 7% (近 10 年約 2% 的週)
HIGH_VOL_MULT = 1.5     # 未來 5 天平均每日漲跌幅 ≥ 過去一年「正常每日漲跌幅」的 1.5 倍
REGIME_NEIGHBORS = 200
REGIME_FALLBACK = {"Forecast_Prob_Low_Vol": 62.0, "Forecast_Prob_High_Vol": 36.0, "Forecast_Prob_Black_Swan": 2.0}


def regime_probabilities(df):
    """未來一週 (5 個交易日) 的市場體制機率：找歷史上「近期波動程度」最像今天的 200 個交易日，
    數它們之後一週分別落在哪一種體制。
    2020~2026 逐年外推回測：預測 21%→59% 的五組，實際 20%→57%，校準良好。
    黑天鵝 (一週內跌 ≥7%) 用任何指標都預測不出來 (回測與「直接用歷史平均」一樣)，所以它基本上就是歷史比例，約 2~3%。"""
    t = df["TAIEX"].dropna() if "TAIEX" in df.columns else pd.Series(dtype=float)
    if len(t) < 600:
        return dict(REGIME_FALLBACK)
    move = np.log(t).diff().abs()
    normal = move.rolling(250).median()
    heat = move.rolling(20).mean() / normal                     # 近一個月波動 ÷ 過去一年常態
    fwd_move = pd.concat([move.shift(-k) for k in range(1, 6)], axis=1).mean(axis=1) / normal
    fwd_low = pd.concat([t.shift(-k) / t - 1 for k in range(1, 6)], axis=1).min(axis=1)
    hist = pd.DataFrame({"heat": heat, "move": fwd_move, "low": fwd_low}).dropna()
    hist = hist[hist.index < t.index[-1]]
    if len(hist) < REGIME_NEIGHBORS or pd.isna(heat.iloc[-1]):
        return dict(REGIME_FALLBACK)
    near = hist.iloc[np.argsort((hist["heat"] - heat.iloc[-1]).abs().values)[:REGIME_NEIGHBORS]]
    swan = (near["low"] <= SWAN_DROP).mean() * 100
    high = ((near["move"] >= HIGH_VOL_MULT) & (near["low"] > SWAN_DROP)).mean() * 100
    swan = max(swan, 1.0)                                       # 樣本裡沒發生過，不代表機率是 0
    return {
        "Forecast_Prob_Low_Vol": round(100.0 - swan - high, 1),
        "Forecast_Prob_High_Vol": round(high, 1),
        "Forecast_Prob_Black_Swan": round(swan, 1),
    }


def volatility_heat(df):
    """近 20 日平均每日漲跌幅 ÷ 過去一年的常態 (中位數)；1 = 正常，1.5 以上 = 明顯動盪"""
    t = df["TAIEX"].dropna() if "TAIEX" in df.columns else pd.Series(dtype=float)
    if len(t) < 260:
        return None
    move = np.log(t).diff().abs()
    v = move.tail(20).mean() / move.tail(250).median()
    return round(float(v), 2) if np.isfinite(v) else None


def pr_matrix(df):
    if len(df) < 252:
        return {}
    pr = regime_probabilities(df)

    for col in ["VIX", "High_Yield_Spread", "DXY", "USDTWD", "Buffett"]:
        if col in df.columns and (v := cycle_pr(df[col])) is not None:
            pr[f"{col}_PR"] = v
    if "Yield_Curve" in df.columns and (v := cycle_pr(df["Yield_Curve"], invert=True)) is not None:
        pr["Yield_Curve_Risk_PR"] = v
    for col in ["SPY", "QQQ", "IWM", "SOX", "WTI", "Copper", "TAIEX"]:
        if col in df.columns and (v := growth_pr(df[col], 120)) is not None:
            pr[f"{col}_DevPR"] = v
    if "Semi_Relative_Strength_RawDev" in df.columns and (v := cycle_pr(df["Semi_Relative_Strength_RawDev"])) is not None:
        pr["Semi_Relative_Strength_PR"] = v

    # 台股 5 日 VIX 隱含區間：用 VIX 換算 5 日波動，再依半導體相對強度調整 beta
    if "TAIEX" in df.columns and "VIX" in df.columns:
        taiex, vix = _latest(df, "TAIEX"), _latest(df, "VIX")
        move = (vix / 100) * (5 / 252) ** 0.5
        beta = 1.3 + (pr.get("Semi_Relative_Strength_PR", 50) - 50) / 100
        pr["Forecast_5D_TAIEX_High"] = taiex * (1 + move * beta)
        pr["Forecast_5D_TAIEX_Low"] = taiex * (1 - move * beta)
    return pr
