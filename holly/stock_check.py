"""個股健檢：輸入公司名稱或代號 → 財務與股價指標 + 統計價格區間 + AI 評價。

三個月價格區間的做法：
- 「統計區間」由這檔股票自己最近 60 個交易日的波動度算出 (假設不漲不跌，只看波動)，是客觀的錨點
- AI 根據財報、營收、估值與大盤局勢，在統計區間的基礎上判斷悲觀 / 基本 / 樂觀情境
這是情境推估，不是預測保證。
"""
import math
import time as _time
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from .taiwan import _finmind

HORIZON_DAYS = 63          # 約 3 個月的交易日
Z90 = 1.645                # 90% 區間
_cache = {"info": (0.0, None)}
RESULT_TTL = 3600          # 同一檔股票 1 小時內共用分析結果


# ---------- 找股票 ----------

def stock_list(ttl=24 * 3600):
    at, df = _cache["info"]
    if df is None or _time.time() - at > ttl:
        df = _finmind("TaiwanStockInfo", "2000-01-01")
        df = df.assign(name=df["stock_name"].str.replace("*", "", regex=False).str.strip())
        _cache["info"] = (_time.time(), df)
    return df


def resolve(query, info):
    """回傳 (唯一結果 dict 或 None, 候選清單)。代號精確比對；名稱依「完全相同 > 輸入以名稱開頭 > 名稱以輸入開頭 > 包含」排序。"""
    q = str(query).strip().replace("*", "").replace(" ", "").upper()
    if not q:
        return None, []
    rows = info.drop_duplicates("stock_id")
    if q.isalnum() and (rows["stock_id"].str.upper() == q).any():
        r = rows[rows["stock_id"].str.upper() == q].iloc[0]
        return _brief(r, info), []

    def rank(name):
        n = name.upper()
        if n == q: return 0
        if q.startswith(n) and len(n) >= 2: return 1      # 「愛普科技」→ 愛普
        if n.startswith(q): return 2                       # 「台積」→ 台積電
        if q in n: return 3
        return None
    ranked = [(rank(r["name"]), r) for _, r in rows.iterrows()]
    ranked = sorted([x for x in ranked if x[0] is not None], key=lambda x: (x[0], len(x[1]["name"])))
    if not ranked:
        return None, []
    best = [r for k, r in ranked if k == ranked[0][0]]
    if len(best) == 1:
        return _brief(best[0], info), []
    return None, [_brief(r, info) for _, r in ranked[:8]]


def _brief(row, info):
    industries = info[info["stock_id"] == row["stock_id"]]["industry_category"].dropna().unique().tolist()
    return {"id": row["stock_id"], "name": row["name"], "industry": "、".join(industries[:2]), "market": row.get("type")}


# ---------- 抓資料 (網路) ----------

def fetch_stock_data(stock_id):
    today = datetime.now()
    since = lambda days: (today - timedelta(days=days)).strftime("%Y-%m-%d")
    data = {}
    for key, dataset, start in [("price", "TaiwanStockPrice", since(420)), ("revenue", "TaiwanStockMonthRevenue", since(800)),
                                ("income", "TaiwanStockFinancialStatements", since(800)), ("balance", "TaiwanStockBalanceSheet", since(200)),
                                ("per", "TaiwanStockPER", since(1100)), ("inst", "TaiwanStockInstitutionalInvestorsBuySell", since(45))]:
        try:
            data[key] = _finmind(dataset, start, data_id=stock_id)
        except Exception as e:
            print(f"⚠️ 個股資料抓取失敗 [{stock_id} {key}]: {e}")
            data[key] = pd.DataFrame()
        _time.sleep(0.3)
    return data


# ---------- 計算指標 (純函式) ----------

def _pct(a, b):
    return None if a is None or b in (None, 0) or pd.isna(a) or pd.isna(b) else (a / b - 1) * 100


def price_metrics(price, taiex=None):
    if price is None or price.empty:
        return None
    s = price.assign(date=pd.to_datetime(price["date"])).set_index("date")["close"].astype(float)
    s = s[s > 0].sort_index()
    if len(s) < 70:
        return None
    last = float(s.iloc[-1])
    ret = lambda n: _pct(last, float(s.iloc[-n - 1])) if len(s) > n else None
    logret = np.log(s).diff().dropna()
    vol = float(logret.tail(60).std() * math.sqrt(252))
    sig = vol * math.sqrt(HORIZON_DAYS / 252)
    out = {
        "close": last, "date": s.index[-1].strftime("%Y-%m-%d"),
        "ret1m": ret(21), "ret3m": ret(63), "ret1y": ret(250),
        "high52": float(s.tail(250).max()), "low52": float(s.tail(250).min()),
        "ma200dev": _pct(last, float(s.tail(200).mean())) if len(s) >= 200 else None,
        "vol": vol * 100,
        "band68": [last * math.exp(-sig), last * math.exp(sig)],
        "band90": [last * math.exp(-Z90 * sig), last * math.exp(Z90 * sig)],
        "beta": None,
    }
    if taiex is not None and len(taiex) > 70:
        m = pd.concat([logret, np.log(taiex.astype(float)).diff()], axis=1, join="inner").dropna().tail(250)
        if len(m) > 60 and m.iloc[:, 1].var() > 0:
            out["beta"] = float(m.cov().iloc[0, 1] / m.iloc[:, 1].var())
    return out


def revenue_metrics(rev):
    if rev is None or rev.empty:
        return None
    r = rev.assign(key=rev["revenue_year"] * 100 + rev["revenue_month"]).drop_duplicates("key").set_index("key")["revenue"].astype(float).sort_index()
    last_key = int(r.index[-1])
    yoy = lambda k: _pct(r.get(k), r.get(k - 100))
    last3 = [k for k in r.index[-3:]]
    yr, mo = divmod(last_key, 100)
    ytd = [k for k in r.index if k // 100 == yr]
    ytd_prev = [k - 100 for k in ytd if k - 100 in r.index]
    return {
        "month": f"{yr}/{mo}", "latest": float(r.iloc[-1]) / 1e8,
        "yoy": yoy(last_key), "mom": _pct(float(r.iloc[-1]), float(r.iloc[-2])) if len(r) > 1 else None,
        "yoy3m": _pct(sum(r[k] for k in last3), sum(r.get(k - 100, np.nan) for k in last3)) if all(k - 100 in r.index for k in last3) else None,
        "ytdYoy": _pct(sum(r[k] for k in ytd), sum(r[k] for k in ytd_prev)) if ytd_prev and len(ytd_prev) == len(ytd) else None,
    }


def income_metrics(inc):
    if inc is None or inc.empty:
        return None
    p = inc.pivot_table(index="date", columns="type", values="value", aggfunc="last").sort_index()
    if "Revenue" not in p.columns:
        return None
    q = p.tail(8)
    margin = lambda col, i: (q[col].iloc[i] / q["Revenue"].iloc[i] * 100) if col in q.columns and q["Revenue"].iloc[i] else None
    eps = q["EPS"].dropna() if "EPS" in q.columns else pd.Series(dtype=float)
    return {
        "quarter": q.index[-1],
        "grossMargin": margin("GrossProfit", -1), "grossMarginYearAgo": margin("GrossProfit", -5) if len(q) >= 5 else None,
        "opMargin": margin("OperatingIncome", -1), "opMarginYearAgo": margin("OperatingIncome", -5) if len(q) >= 5 else None,
        "epsLatest": float(eps.iloc[-1]) if len(eps) else None,
        "epsTTM": float(eps.tail(4).sum()) if len(eps) >= 4 else None,
        "epsTTMPrev": float(eps.iloc[-8:-4].sum()) if len(eps) >= 8 else None,
        "quarterRevenueYoy": _pct(float(q["Revenue"].iloc[-1]), float(q["Revenue"].iloc[-5])) if len(q) >= 5 else None,
    }


def balance_metrics(bal):
    if bal is None or bal.empty:
        return None
    p = bal.pivot_table(index="date", columns="type", values="value", aggfunc="last").sort_index().iloc[-1]
    get = lambda k: float(p[k]) if k in p and pd.notna(p[k]) else None
    assets, liab = get("TotalAssets"), get("Liabilities")
    ca, cl = get("CurrentAssets"), get("CurrentLiabilities")
    return {
        "debtRatio": liab / assets * 100 if assets and liab is not None else None,
        "currentRatio": ca / cl * 100 if ca and cl else None,
        "cash": get("CashAndCashEquivalents") / 1e8 if get("CashAndCashEquivalents") else None,
    }


def valuation_metrics(per):
    if per is None or per.empty:
        return None
    s = per.sort_values("date")
    pe = s["PER"].astype(float).where(lambda x: x > 0)
    last = s.iloc[-1]
    pe_hist = pe.dropna()
    return {
        "pe": float(last["PER"]) if last["PER"] > 0 else None,
        "pePercentile": float(pe_hist.rank(pct=True).iloc[-1] * 100) if len(pe_hist) > 100 and last["PER"] > 0 else None,
        "pb": float(last["PBR"]), "dividendYield": float(last["dividend_yield"]),
    }


def flow_metrics(inst):
    if inst is None or inst.empty:
        return None
    d = inst.assign(net=inst["buy"] - inst["sell"])
    days = sorted(d["date"].unique())[-20:]
    d = d[d["date"].isin(days)]
    foreign = d[d["name"].str.startswith("Foreign")]["net"].sum() / 1000     # 股 → 張
    trust = d[d["name"] == "Investment_Trust"]["net"].sum() / 1000
    return {"foreign20d": float(foreign), "trust20d": float(trust), "days": len(days)}


def compute_metrics(data, taiex=None):
    return {
        "price": price_metrics(data.get("price"), taiex),
        "revenue": revenue_metrics(data.get("revenue")),
        "income": income_metrics(data.get("income")),
        "balance": balance_metrics(data.get("balance")),
        "valuation": valuation_metrics(data.get("per")),
        "flows": flow_metrics(data.get("inst")),
    }


# ---------- AI 評價 ----------

PROMPT = """你是一位嚴謹的台股基本面分析師，請用繁體中文評價下面這家公司未來 3 個月的股價情境與風險。

【規則】
1. 只能根據下方提供的數據推論，不要編造數據裡沒有的財務數字；若提到新聞或產業事件，要說明是一般性的產業背景。
2. price_3m 的 base (基本情境) 原則上落在「68% 統計區間」內；bear / bull 大約落在「90% 統計區間」附近。若你判斷應該偏離，要在 reasoning 說明原因。
3. 要結合「大盤局勢」：大盤偏空時，即使公司體質好也要提醒系統性風險。
4. 不要使用「保證」「一定」等字眼，這是情境推估。
5. 只輸出下面格式的 JSON，字串內不要換行。
{
  "summary": "<一句話總評，30 字內>",
  "stance": "<偏多|中性|偏空>",
  "price_3m": {"bear": <數字>, "base": <數字>, "bull": <數字>},
  "reasoning": "<為什麼這樣判斷，2~3 句，要引用數據>",
  "strengths": ["<優勢 1>", "<優勢 2>"],
  "risks": ["<目前最主要的風險 1>", "<風險 2>", "<風險 3>"],
  "catalysts": ["<可能推升股價的催化劑 1>", "<催化劑 2>"],
  "valuation": "<估值評論，引用本益比與歷史位階>",
  "for_long_term_holder": "<給長期持有、調整比重的投資人的具體建議>"
}
"""


def _fmt(v, digits=1, suffix=""):
    return "無資料" if v is None else f"{v:,.{digits}f}{suffix}"


def build_prompt(stock, m, market):
    p, r, i, b, v, f = (m.get(k) or {} for k in ("price", "revenue", "income", "balance", "valuation", "flows"))
    lines = [PROMPT, f"【公司】{stock['name']} ({stock['id']})，產業：{stock['industry']}"]
    if p:
        lines += [f"【股價】{p['date']} 收盤 {p['close']:,.2f}；近 1 月 {_fmt(p['ret1m'], 1, '%')}、近 3 月 {_fmt(p['ret3m'], 1, '%')}、近 1 年 {_fmt(p['ret1y'], 1, '%')}；"
                  f"距 200 日線 {_fmt(p['ma200dev'], 1, '%')}；52 週區間 {p['low52']:,.1f}~{p['high52']:,.1f}；年化波動 {p['vol']:.0f}%；對大盤 beta {_fmt(p['beta'], 2)}",
                  f"【統計區間 (3 個月，只看波動)】68%：{p['band68'][0]:,.1f}~{p['band68'][1]:,.1f}；90%：{p['band90'][0]:,.1f}~{p['band90'][1]:,.1f}"]
    if r:
        lines.append(f"【月營收】{r['month']} {r['latest']:.2f} 億，年增 {_fmt(r['yoy'], 1, '%')}、月增 {_fmt(r['mom'], 1, '%')}；近 3 月年增 {_fmt(r['yoy3m'], 1, '%')}；今年累計年增 {_fmt(r['ytdYoy'], 1, '%')}")
    if i:
        lines.append(f"【季財報 {i['quarter']}】毛利率 {_fmt(i['grossMargin'], 1, '%')} (去年同季 {_fmt(i['grossMarginYearAgo'], 1, '%')})；營益率 {_fmt(i['opMargin'], 1, '%')} (去年同季 {_fmt(i['opMarginYearAgo'], 1, '%')})；"
                     f"單季 EPS {_fmt(i['epsLatest'], 2)}；近四季 EPS {_fmt(i['epsTTM'], 2)} (前四季 {_fmt(i['epsTTMPrev'], 2)})；單季營收年增 {_fmt(i['quarterRevenueYoy'], 1, '%')}")
    if b:
        lines.append(f"【財務結構】負債比 {_fmt(b['debtRatio'], 1, '%')}；流動比 {_fmt(b['currentRatio'], 0, '%')}；現金 {_fmt(b['cash'], 1, ' 億')}")
    if v:
        lines.append(f"【估值】本益比 {_fmt(v['pe'], 1)} 倍 (近 3 年位階 {_fmt(v['pePercentile'], 0)})；股價淨值比 {_fmt(v['pb'], 2)}；殖利率 {_fmt(v['dividendYield'], 2, '%')}")
    if f:
        lines.append(f"【籌碼 (近 {f['days']} 個交易日)】外資 {_fmt(f['foreign20d'], 0, ' 張')}；投信 {_fmt(f['trust20d'], 0, ' 張')}")
    if market:
        lines.append(f"【大盤局勢】本站今日結論：{market.get('label')} ({market.get('headline')})；3 個月機會分數 {market.get('opportunity')}、風險溫度 {market.get('risk')}")
    return "\n".join(lines)


def analyze(stock, metrics, market, api_key, ask):
    """ask：(prompt, api_key) -> (dict, model)。AI 失敗時仍回傳數據與統計區間。"""
    result = {"stock": stock, "metrics": metrics, "market": market, "ai": None, "model": None,
              "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    if not metrics.get("price"):
        result["error"] = "抓不到這檔股票的股價資料，可能剛上市或已下市。"
        return result
    if not api_key:
        result["error"] = "尚未設定 GEMINI_API_KEY，只顯示數據與統計區間。"
        return result
    try:
        ai, model = ask(build_prompt(stock, metrics, market), api_key)
    except Exception as e:
        result["error"] = f"AI 暫時無法分析，以下只顯示數據與統計區間。({str(e)[:150]})"
        return result
    p3 = ai.get("price_3m") or {}
    try:
        p3 = {k: float(p3[k]) for k in ("bear", "base", "bull")}
    except (KeyError, TypeError, ValueError):
        p3 = None
    lo, hi = metrics["price"]["band90"]
    ai["price_3m"] = p3
    ai["outsideBand"] = bool(p3 and not (lo * 0.9 <= p3["base"] <= hi * 1.1))   # AI 基本情境明顯超出統計區間時，畫面提醒
    result.update(ai=ai, model=model)
    return result
