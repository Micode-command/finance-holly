"""個股技術面與交易計畫：均線、動能 (RSI / KD / MACD)、趨勢線、支撐壓力、進場 / 目標 / 停損。

全部用固定規則計算 (不由 AI 產生數字)，AI 只負責解釋。參數用台股慣用設定：
均線 20 / 60 / 120 / 240 日 (月 / 季 / 半年 / 年線)、RSI 14、KD 9-3-3、MACD 12-26-9。
"""
import math

import numpy as np
import pandas as pd

MAS = [(20, "月線"), (60, "季線"), (120, "半年線"), (240, "年線")]


def _series(price):
    df = price.assign(date=pd.to_datetime(price["date"])).set_index("date").sort_index()
    df = df[df["close"] > 0]
    close = df["close"].astype(float)
    return close, df.get("max", close).astype(float), df.get("min", close).astype(float)


def rsi(close, n=14):
    delta = close.diff()
    up = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    down = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / down.replace(0, np.nan))


def kd(close, high, low, n=9):
    """台股常用 KD：RSV 的 1/3 平滑"""
    rsv = (close - low.rolling(n).min()) / (high.rolling(n).max() - low.rolling(n).min()).replace(0, np.nan) * 100
    k = rsv.ewm(alpha=1 / 3, adjust=False).mean()
    return k, k.ewm(alpha=1 / 3, adjust=False).mean()


def macd(close):
    dif = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
    signal = dif.ewm(span=9, adjust=False).mean()
    return dif, signal, dif - signal


def atr(close, high, low, n=14):
    tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def trendline(close, days=120):
    """對數價格線性回歸：斜率換算每月漲跌 %、R²、通道上下緣 (±1 標準差)"""
    s = close.tail(days)
    if len(s) < 40:
        return None
    x = np.arange(len(s))
    y = np.log(s.values)
    b, a = np.polyfit(x, y, 1)
    fit = a + b * x
    resid = y - fit
    r2 = 1 - (resid ** 2).sum() / ((y - y.mean()) ** 2).sum()
    monthly = (math.exp(b * 21) - 1) * 100
    kind = "上升" if monthly > 2 and r2 > 0.3 else "下降" if monthly < -2 and r2 > 0.3 else "盤整"
    sd = resid.std()
    return {"kind": kind, "monthlyPct": monthly, "r2": float(r2), "days": len(s),
            "start": [s.index[0].strftime("%Y-%m-%d"), float(math.exp(fit[0]))],
            "end": [s.index[-1].strftime("%Y-%m-%d"), float(math.exp(fit[-1]))],
            "channel": [float(math.exp(fit[-1] - sd)), float(math.exp(fit[-1] + sd))]}


def pivots(high, low, window=5, days=250):
    """近一年的轉折高點 / 低點 (前後各 window 天都沒有更高 / 更低)"""
    h, l = high.tail(days), low.tail(days)
    peaks = h[(h == h.rolling(2 * window + 1, center=True).max())]
    troughs = l[(l == l.rolling(2 * window + 1, center=True).min())]
    return list(peaks.values) + list(troughs.values)


def zones(levels, close, width=0.03):
    """價位相近 (3% 內) 的轉折點合併成區間；轉折次數越多越重要"""
    out = []
    for lv in sorted(levels):
        if out and lv <= out[-1]["high"] * (1 + width):
            z = out[-1]; z["high"] = max(z["high"], lv); z["touches"] += 1
        else:
            out.append({"low": lv, "high": lv, "touches": 1})
    supports = sorted([z for z in out if z["high"] < close], key=lambda z: -z["high"])[:2]
    resistances = sorted([z for z in out if z["low"] > close], key=lambda z: z["low"])[:2]
    return supports, resistances


def vol_bands(close, horizon=63):
    """近 60 日波動推算 3 個月 68% / 90% 統計區間"""
    sig = float(np.log(close).diff().tail(60).std() * math.sqrt(horizon))
    last = float(close.iloc[-1])
    return [last * math.exp(-sig), last * math.exp(sig)], [last * math.exp(-1.645 * sig), last * math.exp(1.645 * sig)]


def analyze(price, band68=None):
    """price：FinMind 日 K (date, open, max, min, close)。目標價不超過 3 個月 90% 統計區間上緣 (避免不切實際的目標)。"""
    if price is None or price.empty:
        return None
    close, high, low = _series(price)
    if len(close) < 130:
        return None
    last = float(close.iloc[-1])
    out = {"close": last, "date": close.index[-1].strftime("%Y-%m-%d")}

    mas = []
    for n, name in MAS:
        if len(close) >= n:
            m = close.rolling(n).mean()
            mas.append({"days": n, "name": name, "value": float(m.iloc[-1]), "above": last > float(m.iloc[-1]),
                        "rising": float(m.iloc[-1]) > float(m.iloc[-11])})
    out["mas"] = mas

    r = rsi(close); k, d = kd(close, high, low); dif, sig, hist = macd(close)
    out["momentum"] = {
        "rsi": float(r.iloc[-1]), "rsiPrev": float(r.iloc[-21]),
        "k": float(k.iloc[-1]), "d": float(d.iloc[-1]), "kPrev": float(k.iloc[-6]), "dPrev": float(d.iloc[-6]),
        "macdHist": float(hist.iloc[-1]), "macdHistPrev": float(hist.iloc[-6]), "dif": float(dif.iloc[-1]),
    }
    out["trend"] = trendline(close)
    a = float(atr(close, high, low).iloc[-1])
    out["atr"] = a
    supports, resistances = zones(pivots(high, low), last)
    out["supports"], out["resistances"] = supports, resistances
    b68, b90 = vol_bands(close)
    out["plan"] = trade_plan(last, a, supports, resistances, band68 or b68, b90[1])
    out["readings"] = readings(out)
    # 給前端畫圖：近 250 天收盤與四條均線
    tail = close.tail(250)
    mas_full = {n: close.rolling(n).mean() for n, _ in MAS if len(close) >= n}
    out["chart"] = [[d.strftime("%Y-%m-%d"), round(float(v), 2)] + [None if pd.isna(mas_full[n].get(d)) else round(float(mas_full[n][d]), 2) for n in mas_full]
                    for d, v in tail.items()]
    out["chartMas"] = [n for n in mas_full]
    return out


def trade_plan(close, atr_v, supports, resistances, band68=None, cap=None):
    """參考進場 / 停損 / 目標 / 風險報酬比 (固定規則)：
    - 進場：最近支撐區上緣與現價之間 (不追高；離支撐太遠時，用現價往下 1 個 ATR)
    - 停損：最近支撐區下緣再往下 0.5 個 ATR；與進場距離至少 1 個 ATR、最多 12%
    - 目標：最近壓力區下緣；沒有壓力 (創新高) 時用統計 3 個月 68% 區間上緣；最多到 90% 區間上緣"""
    sup = supports[0] if supports else None
    entry_low = max(sup["high"], close - 1.5 * atr_v) if sup else close - atr_v
    entry = (entry_low + close) / 2
    stop = (sup["low"] - 0.5 * atr_v) if sup else entry - 2 * atr_v
    stop = min(stop, entry - atr_v)
    stop = max(stop, entry * 0.88)
    res = next((z for z in resistances if z["low"] > entry + atr_v), None)
    if res:
        target, basis = res["low"], "壓力區"
    elif band68:
        target, basis = band68[1], "統計 3 個月區間上緣"
    else:
        target, basis = entry + 3 * atr_v, "3 倍 ATR"
    if cap and target > cap:
        target, basis = cap, "3 個月 90% 統計區間上緣 (壓力區太遠)"
    rr = (target - entry) / (entry - stop) if entry > stop else None
    grade = None if rr is None else "佳" if rr >= 2 else "普通" if rr >= 1 else "不划算"
    return {"entryLow": entry_low, "entryHigh": close, "entry": entry, "stop": stop, "target": target, "targetBasis": basis,
            "rr": rr, "grade": grade, "upside": (target / entry - 1) * 100, "downside": (stop / entry - 1) * 100}


def readings(t):
    """把技術指標翻成白話 (固定規則)"""
    out = []
    mas = {m["days"]: m for m in t["mas"]}
    above = [m["name"] for m in t["mas"] if m["above"]]
    if len(above) == len(t["mas"]):
        out.append("股價站上所有均線：短、中、長期都是多方掌控")
    elif not above:
        out.append("股價跌破所有均線：短、中、長期都偏弱，先別急著接")
    else:
        out.append(f"股價在{'、'.join(above)}之上，在其他均線之下：多空交戰中")
    if 20 in mas and 60 in mas:
        out.append("月線在季線之上 (短期強於中期)" if mas[20]["value"] > mas[60]["value"] else "月線在季線之下 (短期弱於中期)")
    m = t["momentum"]
    if m["rsi"] >= 70: out.append(f"RSI {m['rsi']:.0f} 進入過熱區，短線容易拉回")
    elif m["rsi"] <= 30: out.append(f"RSI {m['rsi']:.0f} 進入超賣區，短線有反彈機會")
    else: out.append(f"RSI 從 {m['rsiPrev']:.0f} {'升' if m['rsi'] > m['rsiPrev'] else '降'}到 {m['rsi']:.0f}：動能{'轉強' if m['rsi'] > m['rsiPrev'] else '轉弱'}")
    if m["kPrev"] < m["dPrev"] and m["k"] > m["d"]: out.append("KD 近期黃金交叉：短線轉強訊號")
    elif m["kPrev"] > m["dPrev"] and m["k"] < m["d"]: out.append("KD 近期死亡交叉：短線轉弱訊號")
    out.append("MACD 柱狀體擴大：上漲動能增加" if m["macdHist"] > m["macdHistPrev"] else "MACD 柱狀體縮小：動能減弱")
    tr = t.get("trend")
    if tr:
        out.append(f"近 {tr['days']} 天趨勢{tr['kind']} (每月約 {tr['monthlyPct']:+.1f}%)，趨勢明確度 {tr['r2']:.0%}")
    return out
