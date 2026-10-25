"""潛力股雷達：新聞找技術趨勢 → 營收證明需求 → EPS 合理價排除陷阱 → 交集出候選名單。

選股規則 (2021~2026 上市股票回測，每月底只用當時已知的資料)：
1. 上個月營收創 12 個月新高
2. 營收成長加速 (近 3 個月年增率 - 前 3 個月年增率) 排在全市場前 40%
3. 現價在「近四季 EPS × 自己過去 3 年本益比中位數」的 -10% ~ +30% 之間
   (太便宜反而是陷阱：比合理價低 30% 以上的股票，3 個月後表現比大盤差)
回測：入選股票 3 個月後上漲 57% (全市場 46%)、贏過一半股票 62%、平均 +8.5% (中位數 +2.8%)，
等權持有入選股票贏過全市場的月份 67%。門檻是在同一段資料上決定的，實際表現可能較低。
"""
import io
import re
import time as _time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

from . import technicals

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
PE_SNAPSHOT = DATA_DIR / "radar_pe.csv.gz"         # 每月底本益比 (近 3 年)
REV_SNAPSHOT = DATA_DIR / "radar_rev.csv.gz"       # 每月營收 (近 15 個月)
HEADERS = {"User-Agent": "Mozilla/5.0"}
OPENAPI = "https://openapi.twse.com.tw/v1"

BACKTEST = {"period": "2021~2026", "upProb": 57, "baseUpProb": 46, "beatMedian": 62, "avgReturn": 8.5,
            "medianReturn": 2.8, "baseAvgReturn": 3.3, "portfolioBeatMarket": 67, "picksPerMonth": 10}
MIN_PRICE, MIN_TURNOVER = 10, 3e7
ACCEL_TOP = 0.6                 # 加速排在前 40%
FAIR_GAP = (-0.10, 0.30)        # 合理價缺口範圍
RESULT_TTL = 6 * 3600


# ---------- 解析 (純函式) ----------

def _num(s):
    return pd.to_numeric(pd.Series(s).astype(str).str.replace(",", "").str.strip().replace({"-": None, "--": None, "": None}), errors="coerce")


def parse_bwibbu_rwd(j):
    """證交所 BWIBBU_d (某日全市場本益比) → code, pe"""
    f, d = j.get("fields") or [], j.get("data") or []
    if not d:
        return pd.DataFrame(columns=["code", "pe"])
    df = pd.DataFrame(d, columns=f[:len(d[0])])
    return pd.DataFrame({"code": df["證券代號"].str.strip(), "pe": _num(df["本益比"]).values})


def parse_mops(html):
    """公開資訊觀測站月營收彙總表 → code, rev, rev_ly"""
    rows = []
    for t in pd.read_html(io.StringIO(html)):
        cols = [" ".join(str(x) for x in c) if isinstance(c, tuple) else str(c) for c in t.columns]
        if t.shape[1] < 7 or not any("當月營收" in c for c in cols):
            continue
        t.columns = cols
        rows.append(pd.DataFrame({
            "code": t[[c for c in cols if "代號" in c][0]].astype(str).str.strip().values,
            "rev": _num(t[[c for c in cols if c.endswith("當月營收") and "累計" not in c][0]]).values,
            "rev_ly": _num(t[[c for c in cols if "去年當月營收" in c][0]]).values,
        }))
    df = pd.concat(rows) if rows else pd.DataFrame(columns=["code", "rev", "rev_ly"])
    return df[df["code"].str.fullmatch(r"\d{4}")].drop_duplicates("code")


def parse_current(day_rows, pe_rows, rev_rows):
    """證交所 OpenAPI 今日價格 + 本益比 + 最新月營收 → (今日表, 最新月份, 最新營收表)"""
    px = pd.DataFrame(day_rows)
    px = pd.DataFrame({"code": px["Code"], "name": px["Name"], "close": _num(px["ClosingPrice"]).values,
                       "turnover": _num(px["TradeValue"]).values, "date": px["Date"]})
    pe = pd.DataFrame(pe_rows)
    pe = pd.DataFrame({"code": pe["Code"], "pe": _num(pe["PEratio"]).values, "pb": _num(pe["PBratio"]).values,
                       "dy": _num(pe["DividendYield"]).values})
    cur = px.merge(pe, on="code", how="left").set_index("code")
    rv = pd.DataFrame(rev_rows)
    roc = rv["資料年月"].astype(str).str.zfill(5)
    month = pd.Timestamp(f"{int(roc.iloc[0][:3]) + 1911}-{roc.iloc[0][3:]}-01")
    latest = pd.DataFrame({"code": rv["公司代號"].str.strip(), "rev": _num(rv["營業收入-當月營收"]).values,
                           "rev_ly": _num(rv["營業收入-去年當月營收"]).values, "industry": rv["產業別"].values,
                           "note": rv.get("備註", pd.Series([""] * len(rv))).fillna("").astype(str).values}).set_index("code")
    return cur, month, latest


# ---------- 選股 (純函式) ----------

def screen(cur, pe_hist, rev_hist, latest_month, latest_rev):
    """cur：今日表 (index=code)；pe_hist：月底 × 股票 本益比；rev_hist：營收月份 × 股票 (rev, rev_ly 兩張表)。"""
    rev, rev_ly = rev_hist
    if latest_month not in rev.index:                           # 把 OpenAPI 的最新月營收接上去
        rev = pd.concat([rev, latest_rev["rev"].rename(latest_month).to_frame().T])
        rev_ly = pd.concat([rev_ly, latest_rev["rev_ly"].rename(latest_month).to_frame().T])
    rev, rev_ly = rev.sort_index().tail(15), rev_ly.sort_index().tail(15)
    yoy = rev / rev_ly - 1

    u = cur[cur.index.str.fullmatch(r"[1-9]\d{3}") & (cur["close"] >= MIN_PRICE) & (cur["turnover"] >= MIN_TURNOVER)].copy()
    last12 = rev.tail(12).reindex(columns=u.index)
    u["revHigh"] = (last12.iloc[-1] >= last12.max()) & last12.notna().sum().ge(12)
    u["yoy3"] = (rev.tail(3).sum() / rev_ly.tail(3).sum() - 1).reindex(u.index) * 100
    u["accel"] = (yoy.tail(3).mean() - yoy.iloc[-6:-3].mean()).reindex(u.index) * 100
    u["accelPct"] = u["accel"].rank(pct=True)
    own = pe_hist.where(pe_hist > 0).tail(36)
    u["normalPE"] = own.median().where(own.notna().sum() >= 24).reindex(u.index)
    pe_now = u["pe"].where(u["pe"] > 0)
    u["fairGap"] = (u["normalPE"] / pe_now - 1) * 100            # >0 = 現價低於合理價
    u["fairPrice"] = u["close"] * u["normalPE"] / pe_now
    u["latestYoy"] = yoy.iloc[-1].reindex(u.index) * 100

    passed = u[u["revHigh"] & (u["accelPct"] >= ACCEL_TOP) & u["fairGap"].between(FAIR_GAP[0] * 100, FAIR_GAP[1] * 100)].copy()
    passed["score"] = passed["accelPct"] + passed["yoy3"].rank(pct=True)
    passed = passed.sort_values("score", ascending=False)
    passed["industry"] = latest_rev["industry"].reindex(passed.index)
    passed["note"] = latest_rev["note"].reindex(passed.index)
    funnel = {"universe": int(len(u)), "revHigh": int(u["revHigh"].sum()),
              "accel": int((u["revHigh"] & (u["accelPct"] >= ACCEL_TOP)).sum()), "passed": int(len(passed))}
    return passed, funnel, latest_month


def valid_themes(themes, n_headlines):
    """程式驗證「每個趨勢至少 2 則不同新聞支持」：AI 有時不照規則，只憑 1 則新聞就列成趨勢。"""
    out = []
    for th in themes or []:
        try:
            sources = {int(s) for s in th.get("sources") or [] if 1 <= int(s) <= n_headlines}
        except (TypeError, ValueError):
            continue
        if len(sources) >= 2 and th.get("name"):
            out.append({**th, "sources": sorted(sources)})
    return out


INORGANIC = re.compile(r"併購|合併|收購|納入.{0,12}子公司|新增.{0,6}子公司")


def clean_note(note):
    note = str(note or "").strip()
    return None if note in ("", "-", "－", "nan", "None") else note


# ---------- AI：新聞趨勢 + 候選股對應 ----------

PROMPT = """你是台股產業研究員。請用繁體中文完成兩件事：
A. 從下方「近期新聞標題」歸納 2~5 個「需求正在升溫」的技術或產業趨勢。
   每個趨勢至少要有 2 則新聞支持，只有 1 則的不要列；趨勢要具體 (例如「AI 伺服器散熱」優於「AI 應用」)。
B. 判斷每一檔「候選股」(已通過營收與估值篩選) 和哪個趨勢相關，並區分關係強度：
   - direct：公司的核心產品直接屬於該趨勢的供應鏈 (例如 CoWoS 封裝廠之於 AI 晶片)
   - indirect：只是通路代理、泛用零組件、或少部分業務沾到邊
   - none：沒有關係
   寧可判 none 也不要硬湊。可參考公司自己寫的營收變動原因 (備註)，那是最直接的需求證據。
   business 用一句話描述公司主要業務；若不確定，請寫「不確定」，不要猜。
C. 有「技術面 / 交易計畫」數據的候選股，用 case 說明這個交易機會為何成立 (結合營收、估值與技術面，2 句內)，
   invalidation 寫判斷失效的條件 (例如跌破停損價、營收年增轉負)。價位由程式計算，不要改數字；風險報酬比低於 1 要明講不划算。
只輸出 JSON，字串內不要換行：
{
  "themes": [{"name": "<趨勢名稱>", "sources": [<支持這個趨勢的新聞編號，至少 2 個>], "demand": "<需求升溫的證據，引用新聞>", "watch": "<要留意的風險>"}],
  "stocks": {"<股票代號>": {"theme": "<趨勢名稱或 null>", "relation": "<direct|indirect|none>", "business": "<主要業務>", "why": "<判斷理由，30 字內>", "case": "<交易機會成立的原因或 null>", "invalidation": "<失效條件或 null>"}}
}
"""


def _tech_brief(t):
    if not t:
        return ""
    pl, mo = t["plan"], t["momentum"]
    above = "、".join(m["name"] for m in t["mas"] if m["above"]) or "無"
    trend = f"，趨勢{t['trend']['kind']}" if t.get("trend") else ""
    return (f"；技術面：站上{above}，RSI {mo['rsi']:.0f}{trend}；計畫：進場 {pl['entryLow']:,.1f}~{pl['entryHigh']:,.1f}、"
            f"目標 {pl['target']:,.1f}、停損 {pl['stop']:,.1f}、風險報酬比 {pl['rr']:.1f}" if pl.get("rr") else "")


def build_prompt(headlines, candidates, techs=None):
    techs = techs or {}
    lines = [PROMPT, "【近期新聞標題】"] + [f"{i}. {h}" for i, h in enumerate(headlines[:60], 1)]
    lines.append("\n【候選股】")
    for code, r in candidates.iterrows():
        note = f"；公司說明：{r['note'][:60]}" if r.get("note") else ""
        lines.append(f"- {code} {r['name']} ({r.get('industry') or '產業不明'})：近 3 月營收年增 {r['yoy3']:.0f}%、"
                     f"距合理價 {r['fairGap']:+.0f}%{note}{_tech_brief(techs.get(code))}")
    return "\n".join(lines)


TECH_TOP = 12                   # 前 12 檔另外抓日 K 算技術面 (每 6 小時最多 12 次 FinMind)


def build_radar(cur, pe_hist, rev_hist, latest_month, latest_rev, headlines, api_key, ask, price_fetch=None):
    passed, funnel, month = screen(cur, pe_hist, rev_hist, latest_month, latest_rev)
    techs = {}
    for code in passed.index[:TECH_TOP] if price_fetch else []:
        try:
            techs[code] = technicals.analyze(price_fetch(code))
        except Exception as e:
            print(f"⚠️ 雷達技術面失敗 [{code}]: {e}")
    result = {"generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "funnel": funnel,
              "revenueMonth": f"{month.year}/{month.month}", "priceDate": str(cur["date"].iloc[0]) if "date" in cur else None,
              "backtest": BACKTEST, "themes": [], "model": None}
    ai = {}
    if api_key and len(passed):
        try:
            ai, result["model"] = ask(build_prompt(headlines, passed.head(25), techs), api_key)
        except Exception as e:
            result["error"] = f"AI 趨勢分析暫時失敗，以下只顯示數據篩選結果。({str(e)[:120]})"
    result["themes"] = valid_themes(ai.get("themes"), len(headlines[:60]))
    names = {th["name"] for th in result["themes"]}
    # 被刪掉的趨勢 (新聞支持不足)，掛在上面的股票標籤也一併拿掉
    tags = {code: t if t.get("theme") in names else {**t, "theme": None, "relation": "none"} for code, t in (ai.get("stocks") or {}).items()}
    stocks = []
    for code, r in passed.iterrows():
        t = tags.get(code) or {}
        note = clean_note(r.get("note"))
        stocks.append({
            "code": code, "name": r["name"], "industry": r.get("industry"), "note": note,
            # 營收成長來自併購 / 新納入子公司，不是原本業務的需求成長
            "inorganic": bool(note and INORGANIC.search(note)),
            "close": r["close"], "pe": r["pe"], "normalPE": r["normalPE"], "fairPrice": r["fairPrice"], "fairGap": r["fairGap"],
            "yoy3": r["yoy3"], "latestYoy": r["latestYoy"], "accel": r["accel"], "dividendYield": r["dy"],
            # 只有「直接」相關才掛上趨勢標籤；間接相關另外標示，避免牽強的連結誤導使用者
            "theme": t.get("theme") if t.get("relation") == "direct" else None,
            "indirectTheme": t.get("theme") if t.get("relation") == "indirect" else None,
            "business": t.get("business"), "why": t.get("why"),
            "technicals": _slim(techs.get(code)), "case": t.get("case"), "invalidation": t.get("invalidation"),
        })
    # 直接對上新聞趨勢的排前面，其餘照分數
    stocks.sort(key=lambda s: s["theme"] is None)
    result["stocks"] = stocks
    return result


def _slim(t):
    """雷達列表只需要計畫、均線與解讀，不傳整段圖表資料"""
    return None if not t else {k: t[k] for k in ("plan", "mas", "supports", "resistances", "trend", "momentum", "readings")}


# ---------- 資料來源 (網路 + 專案內快照) ----------

def load_snapshots():
    pe = pd.read_csv(PE_SNAPSHOT, dtype={"code": str}, parse_dates=["date"]).pivot(index="date", columns="code", values="pe")
    rv = pd.read_csv(REV_SNAPSHOT, dtype={"code": str}, parse_dates=["month"])
    return pe, (rv.pivot(index="month", columns="code", values="rev"), rv.pivot(index="month", columns="code", values="rev_ly"))


def fetch_current():
    get = lambda path: requests.get(f"{OPENAPI}/{path}", headers=HEADERS, timeout=60).json()
    return parse_current(get("exchangeReport/STOCK_DAY_ALL"), get("exchangeReport/BWIBBU_ALL"), get("opendata/t187ap05_L"))


_cache = {"at": 0.0, "result": None}


def fetch_price(code, days=500):
    from .taiwan import _finmind
    start = (datetime.now() - pd.Timedelta(days=days)).strftime("%Y-%m-%d")
    out = _finmind("TaiwanStockPrice", start, data_id=code)
    _time.sleep(0.3)
    return out


def radar(headlines, api_key, ask, force=False):
    if not force and _cache["result"] and _time.time() - _cache["at"] < RESULT_TTL:
        return {**_cache["result"], "cached": True}
    cur, month, latest = fetch_current()
    pe_hist, rev_hist = load_snapshots()
    result = build_radar(cur, pe_hist, rev_hist, month, latest, headlines, api_key, ask, price_fetch=fetch_price)
    if not result.get("error"):
        _cache.update(at=_time.time(), result=result)
    return {**result, "cached": False}
