"""配置健檢：使用者輸入持股與比重 → 組合風險樣貌 + 依今日大盤局勢給 AI 調整建議。

持股資料只在這次請求中使用，不儲存、不與其他人共用結果。
"""
import time as _time
from datetime import datetime, timedelta, timezone

import pandas as pd

from .stock_check import price_metrics, resolve, valuation_metrics
from .taiwan import _finmind

MAX_HOLDINGS = 10
GOALS = {"long_term": "長期持有、依局勢調整比重", "income": "穩健領息、重視現金流", "growth": "積極成長、可承受較大波動"}
_data_cache = {}           # 股票代號 → (時間, {"price": df, "per": df})；與使用者無關的公開數據可以共用
DATA_TTL = 3600


class PortfolioInputError(ValueError):
    pass


def parse_holdings(rows, cash, info):
    """驗證並解析輸入：名稱 → 股票、比重 → 百分比。金額或百分比都可以，會自動換算成合計 100%。"""
    rows = [r for r in (rows or []) if str(r.get("query", "")).strip()]
    if not rows:
        raise PortfolioInputError("請至少輸入一筆持股。")
    if len(rows) > MAX_HOLDINGS:
        raise PortfolioInputError(f"最多輸入 {MAX_HOLDINGS} 筆持股。")
    try:
        cash = max(0.0, float(cash or 0))
        weights = [float(r.get("weight") or 0) for r in rows]
    except (TypeError, ValueError):
        raise PortfolioInputError("比重請輸入數字。")
    if any(w <= 0 for w in weights):
        raise PortfolioInputError("每筆持股的比重都要大於 0。")

    holdings, seen = [], {}
    for n, (r, w) in enumerate(zip(rows, weights), 1):
        q = str(r["query"]).strip()[:30]
        stock, candidates = resolve(q, info)
        if candidates:
            names = "、".join(f"{c['name']}({c['id']})" for c in candidates[:5])
            raise PortfolioInputError(f"第 {n} 筆「{q}」符合多家公司：{names}，請改輸入股票代號。")
        if stock is None:
            raise PortfolioInputError(f"第 {n} 筆找不到「{q}」，請改輸入股票代號。")
        if stock["id"] in seen:                       # 同一檔輸入兩次 → 合併
            holdings[seen[stock["id"]]]["raw"] += w
            continue
        seen[stock["id"]] = len(holdings)
        holdings.append({**stock, "raw": w})

    total = sum(h["raw"] for h in holdings) + cash
    for h in holdings:
        h["weight"] = h.pop("raw") / total * 100
    return holdings, cash / total * 100


def fetch_light(stock_id):
    hit = _data_cache.get(stock_id)
    if hit and _time.time() - hit[0] < DATA_TTL:
        return hit[1]
    start = (datetime.now() - timedelta(days=420)).strftime("%Y-%m-%d")
    out = {}
    for key, ds in (("price", "TaiwanStockPrice"), ("per", "TaiwanStockPER"), ("div", "TaiwanStockDividend")):
        try:
            out[key] = _finmind(ds, start, data_id=stock_id)
        except Exception as e:
            print(f"⚠️ 配置健檢資料抓取失敗 [{stock_id} {key}]: {e}")
            out[key] = pd.DataFrame()
        _time.sleep(0.2)
    _data_cache[stock_id] = (_time.time(), out)
    return out


def trailing_yield(div, close, today=None):
    """近 12 個月除息的現金股利合計 ÷ 現價 (%)。個股與 ETF 用同一套算法 (本益比資料不含 ETF)。"""
    if div is None or div.empty or not close or "CashExDividendTradingDate" not in div.columns:
        return None
    today = pd.Timestamp(today or datetime.now().date())
    ex = pd.to_datetime(div["CashExDividendTradingDate"], errors="coerce")
    cash = pd.to_numeric(div.get("CashEarningsDistribution"), errors="coerce").fillna(0) + \
        pd.to_numeric(div.get("CashStatutorySurplus"), errors="coerce").fillna(0)
    recent = cash[(ex > today - pd.Timedelta(days=365)) & (ex <= today)]
    return float(recent.sum() / close * 100) if len(recent) else 0.0


def enrich(holdings, fetch, taiex=None):
    for h in holdings:
        d = fetch(h["id"])
        p = price_metrics(d.get("price"), taiex)
        v = valuation_metrics(d.get("per"))
        h.update({
            "isEtf": h["id"].startswith("00"),
            "isBond": h["id"].startswith("00") and h["id"].endswith("B"),   # 台灣債券 ETF 代號以 B 結尾
            "ret3m": p and p["ret3m"], "ret1y": p and p["ret1y"], "vol": p and p["vol"], "beta": p and p["beta"],
            "ma200dev": p and p["ma200dev"], "close": p and p["close"],
            "pe": v and v["pe"],
            "dividendYield": trailing_yield(d.get("div"), p and p["close"]),
        })
    return holdings


def portfolio_metrics(holdings, cash):
    equity = sum(h["weight"] for h in holdings)
    w = [h["weight"] / 100 for h in holdings]
    wavg = lambda key: (sum(h["weight"] * h[key] for h in holdings if h.get(key) is not None)
                        / max(1e-9, sum(h["weight"] for h in holdings if h.get(key) is not None))) if any(h.get(key) is not None for h in holdings) else None
    beta_known = [h for h in holdings if h.get("beta") is not None]
    industries = {}
    for h in holdings:
        label = "債券 ETF" if h.get("isBond") else "股票型 ETF" if h["isEtf"] else (h["industry"].split("、")[0] or "其他")
        industries[label] = industries.get(label, 0) + h["weight"]
    top = max(holdings, key=lambda h: h["weight"])
    return {
        "equity": equity, "cash": cash,
        "topHolding": {"name": top["name"], "weight": top["weight"]},
        # 有效持股數 = 1 / Σ(權重²)：10 檔平均分配 = 10；一檔占 90% ≈ 1.2
        "effectiveN": 1 / sum(x * x for x in [x / max(1e-9, sum(w)) for x in w]),
        # 組合 Beta：含現金 (Beta 0)，代表整體比大盤震盪幾倍
        "beta": sum(h["weight"] / 100 * h["beta"] for h in beta_known) if beta_known else None,
        "avgVol": wavg("vol"), "dividendYield": wavg("dividendYield"),
        "industries": dict(sorted(industries.items(), key=lambda x: -x[1])),
        "etfWeight": sum(h["weight"] for h in holdings if h["isEtf"]),
        "stockLike": sum(h["weight"] for h in holdings if not h.get("isBond")),   # 個股 + 股票型 ETF
        "bond": sum(h["weight"] for h in holdings if h.get("isBond")),
    }


PROMPT = """你是一位穩健的資產配置顧問，請用繁體中文替這位投資人的台股配置做健檢。

【規則】
1. 根據下方的持股數據、組合指標與「今日大盤局勢」給建議；本站對長期投資人的今日建議是重要依據。
2. 建議要具體到「哪一檔 / 哪一類、往上或往下調多少百分點」，並說明理由；不要建議投資人沒持有、也沒有數據的個股名稱，若要新增，請用「大盤 ETF」「高股息 ETF」「短債」等類別描述。
3. suggested_weights 必須包含所有現有持股與「現金」，數字合計 100。
3-1. 「股票類」(個股 + 股票型 ETF，不含債券 ETF 與現金) 合計比重的調整幅度，必須符合本站今日結論：加碼 → +5～10 個百分點、維持 → ±5 以內、減碼 → −5～−10 個百分點；風險溫度 ≥ 65 時取較小的幅度，並提醒分批執行。
4. 不要使用「保證」「一定」等字眼；這是一般性建議，不是個人化投資顧問服務。
5. 只輸出下面格式的 JSON，字串內不要換行。
{
  "summary": "<一句話總評，30 字內>",
  "risk_level": "<低|中|高>",
  "fit_with_market": "<這個配置和今天大盤局勢 (加碼 / 維持 / 減碼) 是否相符>",
  "strengths": ["<做得好的地方>"],
  "issues": ["<問題 1，例如過度集中、單一產業、波動過大、現金太少或太多>", "<問題 2>"],
  "suggestions": [{"action": "<加碼|減碼|維持|新增|出清>", "target": "<持股名稱或類別>", "detail": "<調多少、為什麼>"}],
  "suggested_weights": [{"name": "<持股名稱 或 現金 或 新增類別>", "current": <目前 %>, "suggested": <建議 %>}],
  "next_steps": ["<接下來 1~3 個月可以觀察或執行的事>"]
}
"""

_f = lambda v, d=1, s="": "無資料" if v is None else f"{v:,.{d}f}{s}"

STANCE_RANGE = {"加碼": (5, 10), "維持": (-5, 5), "減碼": (-10, -5)}


def classify(name, holdings):
    """AI 建議表裡的名稱 → 股票類 / 債券 / 現金 (用代號或名稱比對持股；新增的類別依關鍵字判斷)"""
    if "現金" in name:
        return "cash"
    for h in holdings:
        if h["id"] in name or h["name"] in name:
            return "bond" if h.get("isBond") else "stock"
    return "bond" if ("債" in name or "Bond" in name) else "stock"


def check_stance(suggested, holdings, current_stock, label):
    """AI 建議的股票類比重變化，是否落在本站今日結論的範圍內 (容許 ±2 個百分點誤差)"""
    if label not in STANCE_RANGE or not suggested:
        return None
    new_stock = sum(r["suggested"] for r in suggested if classify(r["name"], holdings) == "stock")
    change = new_stock - current_stock
    lo, hi = STANCE_RANGE[label]
    return {"change": change, "allowed": [lo, hi], "ok": lo - 2 <= change <= hi + 2}


def build_prompt(holdings, cash, pm, goal, market):
    lines = [PROMPT, f"【投資目標】{GOALS.get(goal, GOALS['long_term'])}", "【持股】"]
    for h in sorted(holdings, key=lambda x: -x["weight"]):
        lines.append(f"- {h['name']} ({h['id']}，{'ETF' if h['isEtf'] else h['industry']})：比重 {h['weight']:.1f}%；"
                     f"近 3 月 {_f(h['ret3m'], 0, '%')}、近 1 年 {_f(h['ret1y'], 0, '%')}；年化波動 {_f(h['vol'], 0, '%')}；Beta {_f(h['beta'], 2)}；"
                     f"距 200 日線 {_f(h['ma200dev'], 0, '%')}；本益比 {_f(h['pe'], 1)}；殖利率 {_f(h['dividendYield'], 2, '%')}")
    lines.append(f"- 現金：{cash:.1f}%")
    ind = "、".join(f"{k} {v:.0f}%" for k, v in pm["industries"].items())
    lines.append(f"【組合指標】股票類 {pm['stockLike']:.0f}% / 債券 ETF {pm['bond']:.0f}% / 現金 {pm['cash']:.0f}%；最大持股 {pm['topHolding']['name']} {pm['topHolding']['weight']:.0f}%；"
                 f"有效持股數 {pm['effectiveN']:.1f}；組合 Beta {_f(pm['beta'], 2)}；平均年化波動 {_f(pm['avgVol'], 0, '%')}；加權殖利率 {_f(pm['dividendYield'], 2, '%')}；產業分布：{ind}")
    if market:
        lines.append(f"【今日大盤局勢】本站建議「{market.get('label')}」({market.get('headline')})；3 個月機會分數 {market.get('opportunity')}、風險溫度 {market.get('risk')}；"
                     f"本站對長期投資人的行動建議：{'；'.join(market.get('actions') or [])}")
    return "\n".join(lines)


def normalize_weights(rows):
    """AI 給的建議比重合計不一定剛好 100：等比例調整，並移除格式錯誤的列。"""
    clean = []
    for r in rows or []:
        try:
            clean.append({"name": str(r["name"]), "current": float(r.get("current") or 0), "suggested": max(0.0, float(r["suggested"]))})
        except (KeyError, TypeError, ValueError):
            continue
    total = sum(r["suggested"] for r in clean)
    if total > 0:
        for r in clean:
            r["suggested"] = r["suggested"] / total * 100
    return clean


def analyze(holdings, cash, goal, market, api_key, ask):
    pm = portfolio_metrics(holdings, cash)
    result = {"holdings": holdings, "cash": cash, "metrics": pm, "goal": GOALS.get(goal, GOALS["long_term"]), "market": market,
              "ai": None, "model": None, "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    if not api_key:
        result["error"] = "尚未設定 GEMINI_API_KEY，只顯示組合指標。"
        return result
    try:
        ai, model = ask(build_prompt(holdings, cash, pm, goal, market), api_key)
    except Exception as e:
        result["error"] = f"AI 暫時無法分析，以下只顯示組合指標。({str(e)[:150]})"
        return result
    ai["suggested_weights"] = normalize_weights(ai.get("suggested_weights"))
    ai["stanceCheck"] = check_stance(ai["suggested_weights"], holdings, pm["stockLike"], (market or {}).get("label"))
    result.update(ai=ai, model=model)
    return result
