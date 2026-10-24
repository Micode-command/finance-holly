"""台股籌碼、景氣與估值數據 (FinMind 開放資料、國發會、經濟部)。

研究結論 (2026-10，2016~2026 回測，見 README)：
- 能預測台股未來 3 個月 → 放進機會分數：融資餘額 20 日變化、領先指標 3 個月變化、外銷訂單年增率
- 能預測未來 1 個月波動 → 放進風險溫度：外資台指期淨空單、外資 20 日賣超
- 只解釋「今天」、無法預測 3 個月 → 只當現況卡片：外資 / 投信買賣超本身、景氣燈號分數、本益比
"""
import io
import time
import zipfile
from datetime import datetime, timedelta

import pandas as pd
import requests

FINMIND_URL = "https://api.finmindtrade.com/api/v4/data"
NDC_ZIP_URL = ("https://ws.ndc.gov.tw/Download.ashx?u=LzAwMS9hZG1pbmlzdHJhdG9yLzEwL3JlbGZpbGUvNTc4MS82MzkyL2Vh"
               "MjM1YmQ5LWQwNTItNGE2OS1hYmZjLWQ1Yzc4NWQzZDBlMi56aXA%3d&n=5pmv5rCj5oyH5qiZ5Y%2bK54eI6JmfLnppcA%3d%3d&icon=.zip")
MOEA_EXPORT_ORDERS_URL = "https://service.moea.gov.tw/EE520/opendata/b.csv"
HEADERS = {"User-Agent": "Mozilla/5.0"}
YI = 1e8  # 1 億

# 月資料「M 月」約在 M+1 月下旬公布；保守起見 M+2 月 1 日才採用 (回測也用同樣規則，避免偷看未來)
MONTHLY_RELEASE_LAG = pd.DateOffset(months=2)

# 最近一次下載各來源的錯誤訊息 (給 API 回報，方便在雲端除錯)
LAST_ERRORS = {}

TW_COLUMNS = ["TW_Foreign_Net", "TW_Foreign_Net_20D", "TW_Trust_Net_20D", "TW_Margin", "TW_Margin_Chg20",
              "TW_Fut_Foreign_OI", "TW_PE_TSMC", "TW_NDC_Score", "TW_NDC_Leading_Chg3", "TW_Export_YoY"]


# ---------- 下載 (網路) ----------

def _finmind(dataset, start, **params):
    r = requests.get(FINMIND_URL, params={"dataset": dataset, "start_date": start, **params}, headers=HEADERS, timeout=60)
    j = r.json()
    if j.get("msg") != "success":
        raise RuntimeError(f"{dataset}: {j.get('msg')}")
    return pd.DataFrame(j.get("data", []))


def _ndc_table():
    r = requests.get(NDC_ZIP_URL, headers=HEADERS, timeout=60)
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        name = next(n for n in z.namelist() if n.endswith("景氣指標與燈號.csv") and not n.startswith("schema"))
        return pd.read_csv(z.open(name), dtype=str, encoding="utf-8-sig")


def _export_orders_table():
    r = requests.get(MOEA_EXPORT_ORDERS_URL, headers=HEADERS, timeout=60)
    r.raise_for_status()
    return pd.read_csv(io.BytesIO(r.content), encoding="utf-8-sig")


def fetch_taiwan(years_back):
    """下載全部台股數據並整理成日表；任何一個來源失敗都只略過那一塊，不影響其他。"""
    start = (datetime.now() - timedelta(days=years_back * 365)).strftime("%Y-%m-%d")
    sources = {
        "inst": lambda: _finmind("TaiwanStockTotalInstitutionalInvestors", start),
        "margin": lambda: _finmind("TaiwanStockTotalMarginPurchaseShortSale", start),
        "fut": lambda: _finmind("TaiwanFuturesInstitutionalInvestors", max(start, "2018-06-01"), data_id="TX"),
        "per": lambda: _finmind("TaiwanStockPER", start, data_id="2330"),
        "ndc": _ndc_table,
        "exports": _export_orders_table,
    }
    got = {}
    LAST_ERRORS.clear()
    for name, fetch in sources.items():
        try:
            got[name] = fetch()
        except Exception as e:
            LAST_ERRORS[name] = f"{type(e).__name__}: {str(e)[:200]}"
            print(f"⚠️ 台股數據抓取失敗 [{name}]: {e}")
        if name in ("inst", "margin", "fut", "per"):
            time.sleep(1.0)  # 免費 API，請求間隔一下
    return taiwan_frame(**got)


# ---------- 整理 (純計算，可離線測試) ----------

def _daily(s):
    s = s.copy()
    s.index = pd.to_datetime(s.index)
    return s.sort_index()


def taiwan_frame(inst=None, margin=None, fut=None, per=None, ndc=None, exports=None, now=None):
    cols = {}
    if inst is not None and not inst.empty:
        inst = inst.assign(net=inst["buy"] - inst["sell"])
        piv = inst.pivot_table(index="date", columns="name", values="net", aggfunc="sum")
        foreign = _daily(piv[[c for c in piv.columns if c.startswith("Foreign")]].sum(axis=1)) / YI
        cols["TW_Foreign_Net"] = foreign
        cols["TW_Foreign_Net_20D"] = foreign.rolling(20).sum()           # 在台股交易日上累計
        if "Investment_Trust" in piv.columns:
            cols["TW_Trust_Net_20D"] = _daily(piv["Investment_Trust"]).div(YI).rolling(20).sum()
    if margin is not None and not margin.empty:
        m = _daily(margin[margin["name"] == "MarginPurchaseMoney"].set_index("date")["TodayBalance"]) / YI
        cols["TW_Margin"] = m
        cols["TW_Margin_Chg20"] = m.pct_change(20) * 100
    if fut is not None and not fut.empty:
        f = fut[fut["institutional_investors"] == "外資"].set_index("date")
        cols["TW_Fut_Foreign_OI"] = _daily(f["long_open_interest_balance_volume"] - f["short_open_interest_balance_volume"])
    if per is not None and not per.empty:
        cols["TW_PE_TSMC"] = _daily(per.set_index("date")["PER"].where(lambda s: s > 0))

    monthly = {}
    if ndc is not None and not ndc.empty:
        n = ndc[ndc["景氣對策信號綜合分數"].str.strip() != "-"].copy()
        n.index = pd.to_datetime(n["Date"], format="%Y%m")
        monthly["TW_NDC_Score"] = pd.to_numeric(n["景氣對策信號綜合分數"], errors="coerce")
        monthly["TW_NDC_Leading_Chg3"] = pd.to_numeric(n["領先指標不含趨勢指數"], errors="coerce").diff(3)
    if exports is not None and not exports.empty:
        e = exports[exports["統計項目"] == "外銷訂單金額"].copy()
        roc = e["資料期(民國年)"].astype(str).str.zfill(5)   # 民國年月，例如 11509
        e.index = pd.to_datetime((roc.str[:3].astype(int) + 1911).astype(str) + roc.str[3:], format="%Y%m")
        monthly["TW_Export_YoY"] = pd.to_numeric(e["統計值(美元)"], errors="coerce").sort_index().pct_change(12) * 100
    today = pd.Timestamp.now().normalize() if now is None else pd.Timestamp(now)
    for name, s in monthly.items():
        s = s.dropna()
        s.index = s.index + MONTHLY_RELEASE_LAG   # 只放在「採用日」，不往後填，讓資料日期維持正確
        cols[name] = s[s.index <= today]          # 採用日還沒到的 (例如已公布但要下個月才採用) 先不放

    return pd.DataFrame(cols).sort_index() if cols else pd.DataFrame()
