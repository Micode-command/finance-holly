"""數據層：只負責從外部 (FRED / yfinance / 台股開放資料 / RSS) 抓原始數據，不做任何計算或填補。

回傳的表會保留 NaN，讓指標層可以知道每個欄位真正的最後公布日。
"""
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

import feedparser
import pandas as pd
import requests
import yfinance as yf

from .taiwan import fetch_taiwan
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
    # FRED 每分鐘允許 120 次請求，15 筆用 5 條連線同時抓 (原本逐筆抓 + 間隔要 15 秒)
    with ThreadPoolExecutor(max_workers=5) as pool:
        results = pool.map(lambda item: fetch_fred_series(item[0], item[1][0], item[1][1], start, key), FRED_SERIES.items())
    series = [s for s in results if s is not None]
    return pd.concat(series, axis=1, sort=True) if series else pd.DataFrame()


# 最近一次市場數據下載失敗的代號 (給 API 回報)
MARKET_ERRORS = {}


def _download_close(ticker, years_back, attempts=3):
    """Yahoo 偶爾會回空資料或暫時限流：失敗就間隔幾秒重試。"""
    last_error = "空資料"
    for i in range(attempts):
        try:
            hist = yf.download(ticker, period=f"{years_back}y", progress=False)
            if not hist.empty and "Close" in hist.columns:
                s = hist["Close"]
                if isinstance(s, pd.DataFrame):
                    s = s.iloc[:, 0]
                s = s.dropna()
                if not s.empty:
                    s.index = s.index.tz_localize(None)
                    return s
        except Exception as e:
            last_error = f"{type(e).__name__}: {str(e)[:120]}"
        time.sleep(2 * (i + 1))
    raise RuntimeError(last_error)


def fetch_market(years_back=YEARS_BACK):
    series = []
    MARKET_ERRORS.clear()
    for name, ticker in YF_TICKERS.items():
        try:
            series.append(_download_close(ticker, years_back).rename(name))
        except Exception as e:
            MARKET_ERRORS[name] = str(e)
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
    """抓取全部數據，回傳 FRED + 市場 + 台股數據的原始合併表 (含 NaN)。"""
    # 三大來源互不相關，同時抓：免費主機休眠喚醒後，第一位訪客要等的時間少一半以上
    with ThreadPoolExecutor(max_workers=3) as pool:
        jobs = [pool.submit(fetch_fred, get_secret("FRED_API_KEY"), years_back),
                pool.submit(fetch_market, years_back), pool.submit(fetch_taiwan, years_back)]
        parts = [j.result() for j in jobs]
    parts = [p for p in parts if not p.empty]
    if not parts:
        return pd.DataFrame()
    raw = parts[0]
    for p in parts[1:]:
        raw = raw.join(p, how="outer")
    return raw.sort_index()
