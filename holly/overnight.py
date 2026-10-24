"""台股休市 / 收盤後：用台指期夜盤與美股，預估下一次開盤的跳空幅度。

研究 (2017~2026，係數只用 2021 年以前估計，2022 年以後檢驗)：
- 夜盤 (+美股)：開盤方向猜對 92%，80% 的日子誤差在 ±0.42% 內
- 只有美股 (夜盤還沒開始、或連假期間)：方向猜對 86%，80% 誤差 ±0.46%
時間軸 (台灣時間)：台股 13:30 收盤 → 夜盤 15:00~05:00 → 美股約 21:30~04:00 → 台股 09:00 開盤
只能用「台股收盤之後」才發生的資訊，否則會重複計算台股當天已經反映的漲跌。
"""
import json
import time as _time
from datetime import date

import pandas as pd
import requests

# 開盤跳空 (%) = 截距 + Σ 係數 × 輸入 (%)
MODELS = {
    "full": {"label": "台指期夜盤 + 美股", "intercept": 0.039, "night": 0.386, "ewt": 0.052, "sox": 0.040, "band": 0.42, "hit": 92},
    "night_only": {"label": "台指期夜盤", "intercept": 0.040, "night": 0.555, "band": 0.42, "hit": 92},
    "us_only": {"label": "美股 (台灣 ETF + 費半)", "intercept": 0.042, "ewt": 0.117, "sox": 0.097, "band": 0.46, "hit": 86},
}

TAIFEX_URL = "https://mis.taifex.com.tw/futures/api/getQuoteList"
US_TICKERS = {"ewt": "EWT", "tsm": "TSM", "sox": "^SOX"}
_cache = {}


def _cached(key, fn, ttl):
    hit = _cache.get(key)
    if hit and _time.time() - hit[0] < ttl:
        return hit[1]
    try:
        value = fn()
    except Exception as e:
        print(f"⚠️ 即時數據抓取失敗 [{key}]: {e}")
        value = hit[1] if hit else None    # 失敗時沿用上一次的結果
    _cache[key] = (_time.time(), value)
    return value


# ---------- 下載 (網路) ----------

def _taifex_quotes(market_type):
    headers = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json",
               "Origin": "https://mis.taifex.com.tw", "Referer": "https://mis.taifex.com.tw/futures/"}
    body = {"MarketType": market_type, "SymbolType": "F", "KindID": "1", "CID": "TXF", "ExpireMonth": "",
            "RowSize": "全部", "PageNo": "", "SortColumn": "", "AscDesc": "A"}
    r = requests.post(TAIFEX_URL, headers=headers, data=json.dumps(body), timeout=20)
    r.raise_for_status()
    return r.json().get("RtData", {}).get("QuoteList", [])


def parse_taifex(night_rows, day_rows):
    """期交所即時報價 → 近月台指期 (夜盤 / 日盤) 與現貨。"""
    def pick(rows, suffix):
        for q in rows or []:
            if str(q.get("SymbolID", "")).endswith(suffix) and q.get("CLastPrice"):
                return {"last": float(q["CLastPrice"]), "ref": float(q["CRefPrice"]), "pct": float(q["CDiffRate"]),
                        "date": q.get("CDate"), "time": q.get("CTime")}
        return None
    return {"night": pick(night_rows, "-M"), "day": pick(day_rows, "-F"), "spot": pick(day_rows, "-S")}


def fetch_taifex():
    return parse_taifex(_taifex_quotes("1"), _taifex_quotes("0"))


def fetch_us_daily():
    import yfinance as yf
    out = {}
    for key, ticker in US_TICKERS.items():
        h = yf.Ticker(ticker).history(period="15d", interval="1d")
        if not h.empty:
            s = h["Close"].dropna()
            s.index = [d.date() for d in s.index]   # 美國當地日期
            out[key] = s
    return out


def live_inputs():
    """即時數據：期交所 2 分鐘、美股 5 分鐘快取。"""
    return _cached("taifex", fetch_taifex, 120), _cached("us", fetch_us_daily, 300)


# ---------- 計算 (純函式，可離線測試) ----------

def _since(series, t):
    """台股 t 日收盤之後，美股的累計報酬：基準 = t 日之前最後一個美股收盤；
    t 日 (含) 之後還沒有美股交易時，代表美股還沒開盤 → 沒有新資訊。"""
    if series is None or series.empty:
        return None
    before = series[[d < t for d in series.index]]
    after = series[[d >= t for d in series.index]]
    if before.empty or after.empty:
        return None
    return {"pct": (float(after.iloc[-1]) / float(before.iloc[-1]) - 1) * 100, "asOf": str(after.index[-1])}


def detect_suspension(status, taifex, now):
    """交易時間內 (9:10 後) 期交所沒有今天的現貨成交 → 可能是颱風假等臨時休市。"""
    spot = (taifex or {}).get("spot")
    if status["state"] != "open" or spot is None or now.hour * 60 + now.minute < 9 * 60 + 10:
        return status
    if spot.get("date") == now.strftime("%Y%m%d"):
        return status
    return {**status, "state": "suspended", "label": "可能臨時休市",
            "detail": "交易時間內期交所沒有今天的成交，可能是颱風假等臨時休市"}


def reconcile_last_session(status, taifex):
    """日曆說某天有交易，但期交所最後一筆現貨成交更早 → 那天其實臨時休市 (例如颱風假)，以實際成交日為準。"""
    spot = (taifex or {}).get("spot")
    if status["state"] == "open" or not spot or not spot.get("date"):
        return status
    actual = date(int(spot["date"][:4]), int(spot["date"][4:6]), int(spot["date"][6:]))
    expected = date.fromisoformat(status["lastClosedDay"])
    if actual >= expected:
        return status
    return {**status, "lastClosedDay": actual.isoformat(),
            "note": f"{expected.month}/{expected.day} 臨時休市 (例如颱風假)，以 {actual.month}/{actual.day} 收盤為基準"}


def opening_forecast(status, taiex_closes, taifex, us):
    """status：market_clock.market_status 的結果；taiex_closes：{date: 收盤}。"""
    if status["state"] == "open":
        return None
    t = date.fromisoformat(status["lastClosedDay"])
    t_key = t.strftime("%Y%m%d")
    taifex = taifex or {}

    # 台股 t 日收盤與當天漲跌：優先用期交所的現貨報價 (最即時)，其次用歷史數據
    spot = taifex.get("spot")
    if spot and spot.get("date") == t_key:
        close_t, tw_ret = spot["last"], spot["pct"]
    else:
        s = pd.Series(taiex_closes).sort_index()
        s = s[[d <= t for d in s.index]]
        close_t = float(s.iloc[-1]) if len(s) else None
        tw_ret = (float(s.iloc[-1]) / float(s.iloc[-2]) - 1) * 100 if len(s) >= 2 and s.index[-1] == t else None

    night = taifex.get("night")
    night_pct = night["pct"] if night and night.get("date") == t_key else None   # 必須是 t 日之後的那場夜盤

    us_moves = {k: _since((us or {}).get(k), t) for k in US_TICKERS}
    ewt, sox, tsm = us_moves["ewt"], us_moves["sox"], us_moves["tsm"]
    # EWT / 台積電 ADR 在美國開盤時，會先反映台股 t 日已經發生的漲跌，要扣掉才是「新」資訊
    adj = lambda m: None if m is None else ((1 + m["pct"] / 100) / (1 + (tw_ret or 0) / 100) - 1) * 100
    ewt_new, tsm_new = adj(ewt), adj(tsm)

    inputs = [
        {"key": "night", "label": "台指期夜盤", "pct": night_pct,
         "detail": f"{night['last']:,.0f} 點 · {night['time'][:2]}:{night['time'][2:4]} 更新" if night_pct is not None and night.get("time") else None},
        {"key": "ewt", "label": "台灣 ETF (EWT，美股掛牌)", "pct": ewt_new, "detail": f"扣除台股當天漲跌後 · 美股 {ewt['asOf']}" if ewt else None},
        {"key": "tsm", "label": "台積電 ADR (TSM)", "pct": tsm_new, "detail": "參考用，未放進模型" if tsm else None},
        {"key": "sox", "label": "費城半導體", "pct": sox["pct"] if sox else None, "detail": f"美股 {sox['asOf']}" if sox else None},
    ]

    has_night, has_us = night_pct is not None, ewt_new is not None and sox is not None
    model_key = "full" if has_night and has_us else "night_only" if has_night else "us_only" if has_us else None
    base = {"lastClose": close_t, "lastClosedDay": status["lastClosedDay"], "inputs": inputs}
    if model_key is None:
        return {**base, "model": None,
                "message": "台股剛收盤，台指期夜盤 15:00 開始、美股晚上開盤後，這裡就會出現下次開盤的預估。"}

    m = MODELS[model_key]
    gap = m["intercept"] + m.get("night", 0) * (night_pct or 0) + m.get("ewt", 0) * (ewt_new or 0) + m.get("sox", 0) * (sox["pct"] if sox else 0)
    direction = "開高" if gap >= 0.3 else "開低" if gap <= -0.3 else "平盤附近"
    return {
        **base, "model": model_key, "modelLabel": m["label"],
        "gapPct": round(gap, 2), "gapPoints": round(close_t * gap / 100) if close_t else None,
        "low": round(gap - m["band"], 2), "high": round(gap + m["band"], 2),
        "direction": direction, "hitRate": m["hit"], "band": m["band"],
    }
