"""訊號層：把指標轉成分數、條件與機率。純計算，不碰畫面。"""
from dataclasses import dataclass, field

from .indicators import cycle_pr, growth_pr


# ---------- 台股量化健康度 ----------

@dataclass
class HealthScore:
    score: int
    level: str          # "good" / "warn" / "bad"，畫面層據此上色
    status: str
    features: list = field(default_factory=list)   # 盤勢特徵
    details: list = field(default_factory=list)    # 各項評分明細


def _dev_from_month(df, col, window=20):
    if col not in df.columns:
        return 0.0
    s = df[col].dropna()
    if len(s) < window:
        return 0.0
    ma = s.tail(window).mean()
    return (s.iloc[-1] - ma) / ma * 100


def _clamp(x, limit):
    return max(-limit, min(limit, x))


def _icon(points):
    return "🟢" if points >= 0 else "🔴"


def taiwan_health_score(df):
    score, features, details = 50.0, [], []

    sox_dev = _dev_from_month(df, "SOX")
    pts = _clamp(sox_dev * 5, 25)
    score += pts
    if sox_dev > 3: features.append("費半強勢撐盤")
    elif sox_dev < -3: features.append("費半弱勢拖累")
    details.append(f"{_icon(pts)} 費半距月線 {sox_dev:+.1f}% ({pts:+.0f}分)")

    twd_dev = _dev_from_month(df, "USDTWD")
    pts = _clamp(twd_dev * -20, 25)
    score += pts
    if twd_dev > 0.5: features.append("台幣貶值壓力")
    elif twd_dev < -0.5: features.append("台幣升值熱錢")
    details.append(f"{_icon(pts)} 台幣距月線 {twd_dev:+.2f}% ({pts:+.0f}分)")

    qqq_dev = _dev_from_month(df, "QQQ")
    pts = _clamp(qqq_dev * 4, 15)
    score += pts
    details.append(f"{_icon(pts)} 科技股距月線 {qqq_dev:+.1f}% ({pts:+.0f}分)")

    copper_dev = _dev_from_month(df, "Copper")
    pts = _clamp(copper_dev * 3, 10)
    score += pts
    if copper_dev > 3: features.append("實體需求增溫")
    details.append(f"{_icon(pts)} 銅價距月線 {copper_dev:+.1f}% ({pts:+.0f}分)")

    if "VIX" in df.columns and not df["VIX"].dropna().empty:
        vix = df["VIX"].dropna().iloc[-1]
        if vix < 15:
            score += 10; details.append("🟢 VIX 安定 <15 (+10分)")
        elif vix > 25:
            score -= 25; features.append("華爾街極度恐慌"); details.append("🚨 VIX 恐慌 >25 (-25分)")
        elif vix > 20:
            score -= 10; features.append("避險情緒升溫"); details.append("🔴 VIX 警戒 >20 (-10分)")
        else:
            details.append("⚪ VIX 震盪正常 (0分)")

    score = int(max(0, min(100, score)))
    if score >= 80: level, status = "good", "極度狂熱 (留意拉回)"
    elif score >= 60: level, status = "good", "健康偏多 (順勢操作)"
    elif score >= 40: level, status = "warn", "震盪整理 (控制資金)"
    elif score >= 20: level, status = "bad", "資金退潮 (提高現金防禦)"
    else: level, status = "bad", "恐慌殺盤 (抱緊避險資產)"
    return HealthScore(score, level, status, features, details)


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


def regime_probabilities(df):
    usdtwd_roc = _latest(df, "USDTWD_ROC_5D")
    hy_chg = _latest(df, "HY_Spread_Chg_5D")
    vix_dev = _latest(df, "VIX_Dev_20D")

    tail_risk = 5.0
    if hy_chg > 0.1: tail_risk += 15.0     # 抽銀根
    if usdtwd_roc > 0.5: tail_risk += 10.0 # 外資逃亡
    if vix_dev > 15.0: tail_risk += 10.0   # 極度恐慌

    high_vol = 25.0
    if abs(vix_dev) > 10.0: high_vol += 15.0
    if abs(usdtwd_roc) > 0.2: high_vol += 15.0

    tail_risk = min(max(tail_risk, 2.0), 95.0)
    high_vol = min(max(high_vol, 5.0), 100.0 - tail_risk - 5.0)
    return {
        "Forecast_Prob_Low_Vol": round(100.0 - tail_risk - high_vol, 1),
        "Forecast_Prob_High_Vol": round(high_vol, 1),
        "Forecast_Prob_Black_Swan": round(tail_risk, 1),
    }


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
