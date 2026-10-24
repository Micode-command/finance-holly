"""新聞時事：用關鍵字把標題分到「會影響股市的主題」，並標出連動的指標。純規則，不呼叫 AI。"""

# 主題: (關鍵字, 連動指標 id, 指標中文名)
TOPICS = {
    "聯準會/利率": (["聯準會", "Fed", "FED", "鮑爾", "升息", "降息", "利率", "殖利率", "美債", "央行", "FOMC"],
                 ["DGS30", "Yield_Curve"], ["美債殖利率", "長短債利差"]),
    "通膨": (["通膨", "CPI", "PCE", "物價"], ["CPI_YoY", "Core_PCE_YoY"], ["CPI", "核心 PCE"]),
    "能源": (["油價", "原油", "OPEC", "能源", "天然氣"], ["Brent"], ["布倫特原油"]),
    "AI/半導體": (["台積電", "輝達", "NVIDIA", "Nvidia", "半導體", "晶片", "AI", "黃仁勳", "CoWoS", "記憶體", "伺服器"],
                ["SOX", "SMH_Dev_200D"], ["費半", "半導體乖離"]),
    "匯率/資金": (["台幣", "匯率", "外資", "美元", "熱錢", "匯出", "匯入"], ["USDTWD", "USDTWD_ROC_5D"], ["美元兌台幣", "台幣動能"]),
    "經濟/就業": (["就業", "非農", "失業", "GDP", "衰退", "景氣", "消費", "零售"], ["Unemployment_Rate", "Sahm_Indicator"], ["失業率", "薩姆指標"]),
    "地緣/貿易": (["關稅", "川普", "中國", "貿易", "戰爭", "制裁", "地緣", "中東", "烏克蘭"], ["VIX", "DXY"], ["VIX", "美元指數"]),
    "市場情緒": (["崩跌", "重挫", "暴跌", "恐慌", "大漲", "創高", "創新高", "熔斷", "賣壓", "反彈"], ["VIX", "TAIEX"], ["VIX", "台股加權"]),
}


def classify(title):
    topics, related = [], []
    for name, (keywords, ids, labels) in TOPICS.items():
        if any(k in title for k in keywords):
            topics.append(name)
            related += [{"id": i, "label": label} for i, label in zip(ids, labels) if i not in {r["id"] for r in related}]
    return topics, related


# 直接提到「大盤」的標題對股市影響最直接，排序加權
MARKET_WORDS = ["台股", "美股", "加權", "大盤", "道瓊", "那斯達克", "標普", "費半", "台積電", "外資", "櫃買"]


def _bigrams(text):
    return {text[i:i + 2] for i in range(len(text) - 1)}


def _similar(a, b, threshold=0.5):
    """字元雙連詞的重疊係數 (交集 / 較短標題)；同一事件的不同報導通常 > 0.5"""
    x, y = _bigrams(a), _bigrams(b)
    return len(x & y) / max(1, min(len(x), len(y))) > threshold


def market_moving_news(items, limit=6):
    """優先挑「有對應主題」且直接提到大盤的新聞，同分再依時間新到舊。"""
    scored = []
    for rank, item in enumerate(items):  # items 已依時間排序
        topics, related = classify(item["title"])
        if topics:
            score = len(topics) + 2 * any(w in item["title"] for w in MARKET_WORDS)
            scored.append((-score, rank, {**item, "topics": topics, "related": related}))
    scored.sort(key=lambda x: (x[0], x[1]))
    picked = []
    for _, _, item in scored:
        if not any(_similar(item["title"], p["title"]) for p in picked):  # 同一事件只留一則
            picked.append(item)
        if len(picked) == limit:
            break
    return picked
