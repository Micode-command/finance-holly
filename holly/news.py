"""新聞時事：用關鍵字把標題分到「會影響股市的主題」，並標出連動的指標。純規則，不呼叫 AI。"""

import re
from datetime import datetime, timedelta, timezone

# 主題: (關鍵字, 連動指標 id, 指標中文名)；英文關鍵字給美國 / 日本的英文新聞用
TOPICS = {
    "聯準會/利率": (["聯準會", "Fed", "FED", "鮑爾", "升息", "降息", "利率", "殖利率", "美債", "央行", "FOMC",
                  "Powell", "rate cut", "rate hike", "interest rate", "Treasury", "Treasuries", "yields", "central bank"],
                 ["DGS30", "Yield_Curve"], ["美債殖利率", "長短債利差"]),
    "通膨": (["通膨", "CPI", "PCE", "物價", "inflation"], ["CPI_YoY", "Core_PCE_YoY"], ["CPI", "核心 PCE"]),
    "能源": (["油價", "原油", "OPEC", "能源", "天然氣", "oil", "crude", "Brent", "natural gas"], ["Brent"], ["布倫特原油"]),
    "AI/半導體": (["台積電", "輝達", "NVIDIA", "Nvidia", "半導體", "晶片", "AI", "黃仁勳", "CoWoS", "記憶體", "伺服器",
                 "TSMC", "chip", "chips", "chipmaker", "semiconductor", "Micron", "AMD", "Broadcom", "data center"],
                ["SOX", "SMH_Dev_200D"], ["費半", "半導體乖離"]),
    "匯率/資金": (["台幣", "匯率", "外資", "美元", "熱錢", "匯出", "匯入", "dollar", "currency"], ["USDTWD", "USDTWD_ROC_5D"], ["美元兌台幣", "台幣動能"]),
    "經濟/就業": (["就業", "非農", "失業", "GDP", "衰退", "景氣", "消費", "零售", "jobs", "payrolls", "unemployment",
                 "recession", "consumer", "retail sales", "economy"], ["Unemployment_Rate", "Sahm_Indicator"], ["失業率", "薩姆指標"]),
    "地緣/貿易": (["關稅", "中國", "貿易", "戰爭", "制裁", "地緣", "中東", "烏克蘭", "tariff", "tariffs",
                 "China", "trade war", "sanctions", "Middle East", "Ukraine", "Iran", "Taiwan Strait"], ["VIX", "DXY"], ["VIX", "美元指數"]),
    "日本/日圓": (["日圓", "日銀", "日經", "日股", "植田", "BOJ", "Bank of Japan", "yen", "Nikkei", "Topix", "Ueda"], [], []),
    "市場情緒": (["崩跌", "重挫", "暴跌", "恐慌", "大漲", "創高", "創新高", "熔斷", "賣壓", "反彈", "selloff", "sell-off",
                "plunge", "plunges", "tumble", "tumbles", "rally", "rallies", "record high", "slump", "surge", "rout"],
               ["VIX", "TAIEX"], ["VIX", "台股加權"]),
}


def _pattern(keywords):
    """中文直接比對；英文用單字邊界 (避免 oil 對到 boil)，全大寫縮寫 (AI、BOJ) 要大小寫相符"""
    parts = []
    for k in keywords:
        if not k.isascii():
            parts.append(re.escape(k))
        elif k.isupper():
            parts.append(rf"(?-i:\b{re.escape(k)}\b)")
        else:
            parts.append(rf"\b{re.escape(k)}\b")
    return re.compile("|".join(parts), re.IGNORECASE)


_TOPIC_RE = {name: _pattern(kw) for name, (kw, _, _) in TOPICS.items()}


def classify(title):
    topics, related = [], []
    for name, (_, ids, labels) in TOPICS.items():
        if _TOPIC_RE[name].search(title):
            topics.append(name)
            related += [{"id": i, "label": label} for i, label in zip(ids, labels) if i not in {r["id"] for r in related}]
    return topics, related


# 直接提到「大盤」的標題對股市影響最直接，排序加權
MARKET_WORDS = _pattern(["台股", "美股", "加權", "大盤", "道瓊", "那斯達克", "標普", "費半", "台積電", "外資", "櫃買", "日經", "日股",
                         "stocks", "S&P", "Nasdaq", "Dow", "Wall Street", "Nikkei", "Taiwan", "TSMC"])
REGION_QUOTA = {"台灣": 3, "國際": 2, "美國": 2, "日本": 1}   # 每區先保留名額，避免版面被同一地區洗版


def _bigrams(text):
    return {text[i:i + 2] for i in range(len(text) - 1)}


def _similar(a, b, threshold=0.5):
    """字元雙連詞的重疊係數 (交集 / 較短標題)；同一事件的不同報導通常 > 0.5"""
    x, y = _bigrams(a), _bigrams(b)
    return len(x & y) / max(1, min(len(x), len(y))) > threshold


MAX_AGE_HOURS = 72


def _fresh(items, now=None):
    """只留最近 3 天的新聞 (英文來源常混著一兩週前的舊聞)；沒有時間的保留"""
    now = now or datetime.now(timezone.utc)
    cutoff = (now - timedelta(hours=MAX_AGE_HOURS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return [x for x in items if not x.get("published") or x["published"] >= cutoff]


def market_moving_news(items, limit=8, now=None):
    """挑「有對應主題」的新聞，直接提到大盤的優先；先照地區名額挑 (台灣 / 國際 / 美國 / 日本)，再用分數補滿。"""
    scored = []
    for rank, item in enumerate(_fresh(items, now)):  # items 已依時間排序
        topics, related = classify(item["title"])
        if topics:
            score = len(topics) + 2 * bool(MARKET_WORDS.search(item["title"]))
            scored.append((-score, rank, {**item, "topics": topics, "related": related}))
    scored.sort(key=lambda x: (x[0], x[1]))
    picked = []

    def take(item):
        if len(picked) < limit and not any(_similar(item["title"], p["title"]) for p in picked):  # 同一事件只留一則
            picked.append(item)

    for region, quota in REGION_QUOTA.items():
        for item in [x for _, _, x in scored if x.get("region", "台灣") == region][:quota * 2]:
            if sum(p.get("region", "台灣") == region for p in picked) < quota:
                take(item)
    for _, _, item in scored:
        if item not in picked:
            take(item)
    order = {id(x): i for i, (_, _, x) in enumerate(scored)}
    return sorted(picked, key=lambda x: order[id(x)])
