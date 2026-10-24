"""數據層：只負責從外部 (FRED / yfinance / RSS) 抓原始數據，不做任何計算或填補。

回傳的表會保留 NaN，讓指標層可以知道每個欄位真正的最後公布日。
"""
import time
from datetime import datetime, timedelta

import feedparser
import pandas as pd
import requests
import yfinance as yf

from .config import FRED_SERIES, FRED_YOY_SERIES, NEWS_RSS_URL, TW_NEWS_RSS_URLS, YEARS_BACK, YF_TICKERS, get_secret

FRED_OBS_URL = "https://api.stlouisfed.org/fred/series/observations"


def fetch_fred_series(col, series_id, in_billions, start, key):
    params = {
        "series_id": series_id, "api_key": key, "file_type": "json",
        "sort_order": "asc", "observation_start": start,
    }
    if col in FRED_YOY_SERIES:
        params["units"] = "pc1"
    try:
        r = requests.get(FRED_OBS_URL, params=params, timeout=15)
        r.raise_for_status()
    except Exception as e:
        print(f"⚠️ FRED API 抓取失敗 [{col}]: {e}")
        return None

    values = {}
    for o in r.json().get("observations", []):
        try:
            val = float(o.get("value"))
        except (TypeError, ValueError):
            continue  # FRED 用 "." 表示缺值
        values[pd.Timestamp(o["date"])] = val * 1000 if in_billions else val
    return pd.Series(values, name=col, dtype=float) if values else None


def fetch_fred(key, years_back=YEARS_BACK):
    if not key:
        return pd.DataFrame()
    start = (datetime.now() - timedelta(days=years_back * 365)).strftime("%Y-%m-%d")
    series = []
    for col, (sid, in_billions) in FRED_SERIES.items():
        s = fetch_fred_series(col, sid, in_billions, start, key)
        if s is not None:
            series.append(s)
        time.sleep(0.6)  # FRED 速率限制
    return pd.concat(series, axis=1, sort=True) if series else pd.DataFrame()


def fetch_market(years_back=YEARS_BACK):
    series = []
    for name, ticker in YF_TICKERS.items():
        try:
            hist = yf.download(ticker, period=f"{years_back}y", progress=False)
            if hist.empty or "Close" not in hist.columns:
                continue
            s = hist["Close"]
            if isinstance(s, pd.DataFrame):
                s = s.iloc[:, 0]
            s.index = s.index.tz_localize(None)
            series.append(s.rename(name))
        except Exception as e:
            print(f"⚠️ yfinance 抓取失敗 [{name}]: {e}")
    return pd.concat(series, axis=1, sort=True) if series else pd.DataFrame()


def fetch_headlines(limit=5):
    try:
        feed = feedparser.parse(NEWS_RSS_URL)
        return [entry.get("title", "無標題") for entry in feed.entries[:limit]]
    except Exception:
        return []


def fetch_market_news():
    """中文財經新聞 (Yahoo 奇摩股市)：回傳 [{title, link, published, source}]，依時間新到舊。"""
    items, seen = [], set()
    for url in TW_NEWS_RSS_URLS:
        try:
            feed = feedparser.parse(url)
        except Exception:
            continue
        for e in feed.entries:
            title = e.get("title", "").strip()
            if not title or title in seen:
                continue
            seen.add(title)
            published = e.get("published_parsed")
            items.append({
                "title": title,
                "link": e.get("link", ""),
                "published": time.strftime("%Y-%m-%dT%H:%M:%SZ", published) if published else None,
                "source": "Yahoo奇摩股市",
            })
    return sorted(items, key=lambda x: x["published"] or "", reverse=True)


def load_raw(years_back=YEARS_BACK):
    """抓取全部數據，回傳 FRED + 市場數據的原始合併表 (含 NaN)。"""
    fred = fetch_fred(get_secret("FRED_API_KEY"), years_back)
    market = fetch_market(years_back)
    if fred.empty:
        return market
    if market.empty:
        return fred
    return fred.join(market, how="outer").sort_index()
