"""台股雙分數：3 個月機會分數 + 風險溫度。純 pandas，不依賴畫面。

方法 (2026-10 用 2016~2026 數據研究決定)：
- 每個因子換算成「今天的值在過去 3 年排第幾」(百分位，只用過去資料，不偷看未來)
- 依方向翻轉後等權平均，再做指數平滑，避免分數天天大跳
- 樣本外檢驗 (2022~2026)：機會分數 vs 台股未來 60 日報酬排序相關 +0.46；
  風險溫度 vs 未來 20 日實際波動 +0.47。舊版健康度只有 +0.03。
- 等權重比「依歷史相關係數調權重」在樣本外更好 (避免過度擬合)，所以全部等權。
"""
from dataclasses import dataclass, field

import pandas as pd

WINDOW = 756        # 百分位的回看期：約 3 年交易日
MIN_PERIODS = 252   # 至少 1 年歷史才計算
OPP_SMOOTH = 10     # 機會分數平滑天數
RISK_SMOOTH = 5     # 風險溫度平滑天數
HORIZON = 60        # 機會分數對應的未來期間：60 個交易日 ≈ 3 個月
BUCKETS = [0, 30, 45, 55, 70, 100]


@dataclass(frozen=True)
class Factor:
    key: str
    label: str
    sign: int            # +1：數值越高分數越高；-1：越低分數越高
    build: object        # (df) -> Series
    why: str             # 白話說明為什麼這個因子有用
    fmt: object          # (value) -> 顯示文字


def _col(name):
    return lambda df: df[name] if name in df.columns else None


def _pct_change(name, n):
    return lambda df: df[name].pct_change(n) * 100 if name in df.columns else None


def _diff(name, n):
    return lambda df: df[name].diff(n) if name in df.columns else None


def _drawdown(df):
    if "TAIEX" not in df.columns:
        return None
    tw = df["TAIEX"]
    return -(tw / tw.rolling(252).max() - 1) * 100


OPPORTUNITY = [
    Factor("hy_level", "垃圾債利差", +1, _col("High_Yield_Spread"),
           "利差高代表信用市場害怕，歷史上往往是 3 個月後的好買點", lambda v: f"{v:.2f}%"),
    Factor("vix_level", "VIX 恐慌指數", +1, _col("VIX"),
           "恐慌越深，之後反彈的機率越高 (別人恐懼時貪婪)", lambda v: f"{v:.1f}"),
    Factor("net_liq", "淨流動性 13 週變化", +1, _pct_change("Net_Liquidity", 63),
           "Fed 與財政部放水越多，股市越有資金推升", lambda v: f"{v:+.1f}%"),
    Factor("dxy", "美元指數 60 日變化", -1, _pct_change("DXY", 60),
           "美元轉強時資金回流美國，台股等新興市場容易失血", lambda v: f"{v:+.1f}%"),
    Factor("dgs10", "10 年美債 60 日變化", -1, _diff("DGS10", 60),
           "長天期利率快速上升會壓縮股票估值", lambda v: f"{v:+.2f} 百分點"),
    Factor("copper", "銅價 60 日變化", +1, _pct_change("Copper", 60),
           "銅價上漲代表實體需求轉好 (銅博士)", lambda v: f"{v:+.1f}%"),
]

RISK = [
    Factor("vix_level", "VIX 恐慌指數", +1, _col("VIX"),
           "選擇權市場的避險需求，越高代表越恐慌", lambda v: f"{v:.1f}"),
    Factor("hy_level", "垃圾債利差", +1, _col("High_Yield_Spread"),
           "信用市場要求的風險補償，越高越緊張", lambda v: f"{v:.2f}%"),
    Factor("hy_change", "垃圾債利差 20 日變化", +1, _diff("High_Yield_Spread", 20),
           "利差快速擴大 = 銀行開始收緊銀根", lambda v: f"{v:+.2f} 百分點"),
    Factor("twd", "台幣 20 日變化", +1, _pct_change("USDTWD", 20),
           "美元兌台幣上升 = 台幣貶值 = 外資在賣台股匯出", lambda v: f"{v:+.2f}%"),
    Factor("drawdown", "台股距一年高點", +1, _drawdown,
           "從高點跌得越深，市場越動盪", lambda v: f"-{v:.1f}%"),
    Factor("dgs10", "10 年美債 60 日變化", +1, _diff("DGS10", 60),
           "利率急升常伴隨股市大幅波動", lambda v: f"{v:+.2f} 百分點"),
]


def _pct_rank(s):
    return s.rolling(WINDOW, min_periods=MIN_PERIODS).rank(pct=True)


def composite(df, factors, smooth):
    """回傳 (分數歷史 Series 0~100, 各因子最新明細 list)。可用因子少於 3 個時回傳 (None, [])。"""
    parts, details = [], []
    for f in factors:
        s = f.build(df)
        if s is None or s.dropna().empty:
            continue
        p = _pct_rank(s)
        oriented = p if f.sign > 0 else 1 - p
        parts.append(oriented)
        latest_raw, latest_pct = s.dropna(), oriented.dropna()
        if not latest_raw.empty and not latest_pct.empty:
            details.append({
                "key": f.key, "label": f.label, "value": f.fmt(float(latest_raw.iloc[-1])),
                "score": round(float(latest_pct.iloc[-1]) * 100), "why": f.why,
            })
    if len(parts) < 3:
        return None, []
    # 每天用「當天有值的因子」平均 (等權)，早期資料不足的因子自動略過
    score = pd.concat(parts, axis=1).mean(axis=1, skipna=True) * 100
    return score.ewm(span=smooth).mean(), details


def bucket_label(x):
    for lo, hi in zip(BUCKETS, BUCKETS[1:]):
        if x < hi or hi == BUCKETS[-1]:
            return lo, hi


def historical_odds(score, price):
    """目前分數所在區間，歷史上 60 個交易日後的表現 (上漲機率、平均報酬、樣本數)"""
    fwd = price.shift(-HORIZON) / price - 1
    lo, hi = bucket_label(score.iloc[-1])
    mask = (score >= lo) & (score < hi if hi < 100 else score <= hi) & fwd.notna()
    n = int(mask.sum())
    if n < 20:
        return None
    return {"range": f"{lo}-{hi}", "upProb": round(float((fwd[mask] > 0).mean()) * 100),
            "avgReturn": round(float(fwd[mask].mean()) * 100, 1), "days": n,
            "baseUpProb": round(float((fwd.dropna() > 0).mean()) * 100)}


@dataclass
class MarketScores:
    opportunity: int
    risk: int
    opportunity_change_5d: int        # 一週前到現在的變化
    risk_change_5d: int
    opportunity_details: list = field(default_factory=list)
    risk_details: list = field(default_factory=list)
    odds: dict = None                 # historical_odds 的結果
    history: list = field(default_factory=list)   # [[日期, 機會, 風險], ...] 近 1 年，給走勢圖


def market_scores(df):
    opp, opp_details = composite(df, OPPORTUNITY, OPP_SMOOTH)
    risk, risk_details = composite(df, RISK, RISK_SMOOTH)
    if opp is None or risk is None:
        return None
    opp, risk = opp.dropna(), risk.dropna()
    both = pd.concat([opp.rename("o"), risk.rename("r")], axis=1).dropna()
    recent = both[both.index >= both.index[-1] - pd.DateOffset(years=1)]
    return MarketScores(
        opportunity=round(float(opp.iloc[-1])),
        risk=round(float(risk.iloc[-1])),
        opportunity_change_5d=round(float(opp.iloc[-1] - opp.iloc[-6])) if len(opp) > 5 else 0,
        risk_change_5d=round(float(risk.iloc[-1] - risk.iloc[-6])) if len(risk) > 5 else 0,
        opportunity_details=opp_details,
        risk_details=risk_details,
        odds=historical_odds(opp, df["TAIEX"]) if "TAIEX" in df.columns else None,
        history=[[d.strftime("%Y-%m-%d"), round(float(o), 1), round(float(r), 1)] for d, (o, r) in recent.iterrows()],
    )
