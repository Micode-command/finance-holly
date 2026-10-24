"""今日結論：把所有訊號收斂成「進攻 / 中性 / 防守」與一句話。純規則，不呼叫 AI。

給首頁 header 與 footer 用。這是量化規則的歸納，不是投資建議。
"""
from dataclasses import asdict, dataclass, field


@dataclass
class Driver:
    tone: str       # "good" / "bad"
    text: str       # 完整描述，例如「VIX 27.3：華爾街恐慌升溫」
    short: str      # 一句話結論用的短詞，例如「VIX 恐慌」


@dataclass
class Verdict:
    stance: str             # "offensive" / "neutral" / "defensive"
    label: str              # 進攻 / 中性 / 防守
    headline: str           # header 大標
    actions: list = field(default_factory=list)
    drivers: list = field(default_factory=list)
    one_liner: str = ""


def _latest(df, col):
    if col not in df.columns:
        return None
    s = df[col].dropna()
    return float(s.iloc[-1]) if not s.empty else None


def _dev_from_month(df, col, window=20):
    s = df[col].dropna() if col in df.columns else None
    if s is None or len(s) < window:
        return None
    ma = s.tail(window).mean()
    return (s.iloc[-1] - ma) / ma * 100


def collect_drivers(df):
    """把重要指標翻成白話的利多 / 利空，依影響力排序。"""
    d = []
    vix = _latest(df, "VIX")
    if vix is not None:
        if vix > 25: d.append(Driver("bad", f"VIX {vix:.1f}：華爾街進入恐慌", "VIX 恐慌"))
        elif vix > 20: d.append(Driver("bad", f"VIX {vix:.1f}：避險情緒升溫", "避險升溫"))
        elif vix < 15: d.append(Driver("good", f"VIX {vix:.1f}：市場情緒安定", "情緒安定"))

    sox = _dev_from_month(df, "SOX")
    if sox is not None:
        if sox < -5: d.append(Driver("bad", f"費半距月線 {sox:+.1f}%：半導體走弱拖累台股", "費半走弱"))
        elif sox > 5: d.append(Driver("good", f"費半距月線 {sox:+.1f}%：半導體強勢撐盤", "費半強勢"))

    twd = _latest(df, "USDTWD_ROC_5D")
    if twd is not None:
        if twd > 0.5: d.append(Driver("bad", f"台幣 5 日貶 {twd:.2f}%：外資撤離", "外資撤離"))
        elif twd < -0.5: d.append(Driver("good", f"台幣 5 日升 {-twd:.2f}%：熱錢湧入", "熱錢湧入"))

    liq = _latest(df, "Liquidity_ROC_4W")
    if liq is not None:
        if liq < -1: d.append(Driver("bad", f"聯準會淨流動性 4 週 {liq:+.1f}%：資金在抽水", "資金抽水"))
        elif liq > 1: d.append(Driver("good", f"聯準會淨流動性 4 週 {liq:+.1f}%：資金在放水", "資金放水"))

    hy = _latest(df, "HY_Spread_Chg_5D")
    if hy is not None and hy > 0.1:
        d.append(Driver("bad", f"垃圾債利差 5 日 +{hy:.2f} 個百分點：銀行收緊銀根", "信用收緊"))

    dgs10 = _latest(df, "DGS10")
    if dgs10 is not None:
        if dgs10 > 4.5: d.append(Driver("bad", f"10 年美債 {dgs10:.2f}%：高利率壓抑估值", "利率偏高"))
        elif dgs10 < 4.0: d.append(Driver("good", f"10 年美債 {dgs10:.2f}%：利率壓力解除", "利率回落"))

    brent = _latest(df, "Brent")
    if brent is not None and brent > 90:
        d.append(Driver("bad", f"布蘭特原油 ${brent:.0f}：通膨壓力未解", "油價偏高"))

    sahm = _latest(df, "Sahm_Indicator")
    if sahm is not None and sahm >= 0.5:
        d.append(Driver("bad", f"薩姆指標 {sahm:.2f}：衰退訊號觸發", "衰退訊號"))
    return d


ACTIONS = {
    "offensive": ["分批加碼核心股票與半導體", "維持月配息現金流部位", "保留 1 成戰術資金防黑天鵝"],
    "neutral": ["維持既有配置，不追高也不殺低", "新資金分批進場、拉長時間", "盯緊 VIX 與台幣動能的方向"],
    "defensive": ["提高台幣現金與短債比重", "暫停加碼成長股，等訊號轉好", "月配息部位續抱，當作防震墊"],
}
LABELS = {"offensive": "進攻", "neutral": "中性", "defensive": "防守"}
HEADLINES = {
    "offensive": "風險偏好回溫，資金面支持股市",
    "neutral": "多空拉鋸，市場方向未明",
    "defensive": "風險升溫，資金面偏空",
}


def market_verdict(df, health, bottom_fishing):
    drivers = collect_drivers(df)
    bad = sum(x.tone == "bad" for x in drivers)
    good = sum(x.tone == "good" for x in drivers)
    met = bottom_fishing.met if bottom_fishing else 0

    if met >= 3 and health.score >= 40:
        stance = "offensive"
    elif health.score >= 60 and bad <= 2:
        stance = "offensive"
    elif health.score < 35 or bad >= 4 or bad - good >= 3:
        stance = "defensive"
    else:
        stance = "neutral"

    # 利空與利多都列，但讓「與立場同方向」的排前面
    lead = "bad" if stance == "defensive" else "good" if stance == "offensive" else None
    drivers.sort(key=lambda x: x.tone != lead)

    reasons = "、".join(x.short for x in drivers[:3]) or "各項指標多在常態區間"
    one_liner = (f"今日台股{LABELS[stance]}：{reasons}，健康度 {health.score} 分、"
                 f"長線買點 {met}/4 成立 —— 建議{ACTIONS[stance][0]}。")
    return Verdict(stance, LABELS[stance], HEADLINES[stance], ACTIONS[stance], [asdict(x) for x in drivers], one_liner)


VITALS = [
    # (欄位, 名稱, 前綴, 後綴, 小數, 漲跌模式, 上漲是否為壞事)
    ("TAIEX", "台股加權", "", "", 0, "pct", False),
    ("SPY", "標普 500", "$", "", 2, "pct", False),
    ("SOX", "費城半導體", "", "", 0, "pct", False),
    ("VIX", "VIX 恐慌", "", "", 2, "pct", True),
    ("DGS10", "10 年美債", "", "%", 2, "abs", True),
    ("USDTWD", "美元/台幣", "", "", 2, "pct", True),
    ("Brent", "布蘭特原油", "$", "", 2, "pct", True),
    ("Gold", "黃金", "$", "", 0, "pct", False),
]


def vitals(dataset):
    """首頁關鍵數字：最新值 + 較前一個交易日 (或前一次公布) 的變化。"""
    out = []
    for col, label, prefix, suffix, decimals, mode, invert in VITALS:
        if col not in dataset.df.columns:
            continue
        s = dataset.release_points(col)
        if len(s) < 2:
            continue
        latest, prev = float(s.iloc[-1]), float(s.iloc[-2])
        change = (latest / prev - 1) * 100 if mode == "pct" else latest - prev
        out.append({
            "id": col, "label": label, "value": latest, "change": change, "changeMode": mode,
            "prefix": prefix, "suffix": suffix, "decimals": decimals, "invertColor": invert,
            "date": s.index[-1].strftime("%Y-%m-%d"),
        })
    return out
