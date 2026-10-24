"""今日結論：把雙分數收斂成「加碼 / 維持 / 減碼」與一句話。純規則，不呼叫 AI。

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
    label: str              # 加碼 / 維持 / 減碼
    headline: str           # header 大標
    actions: list = field(default_factory=list)
    drivers: list = field(default_factory=list)
    one_liner: str = ""


def _latest(df, col):
    if col not in df.columns:
        return None
    s = df[col].dropna()
    return float(s.iloc[-1]) if not s.empty else None


def _pct_latest(df, col, window=756):
    """最新值在過去 3 年的百分位 (0~100)"""
    if col not in df.columns:
        return None
    s = df[col].dropna()
    if len(s) < 252:
        return None
    return float(s.tail(window).rank(pct=True).iloc[-1] * 100)


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

    fn20, fn_pct = _latest(df, "TW_Foreign_Net_20D"), _pct_latest(df, "TW_Foreign_Net_20D")
    if fn20 is not None and fn_pct is not None:
        if fn_pct <= 10: d.append(Driver("bad", f"外資 20 日賣超 {-fn20:,.0f} 億：籌碼面賣壓沉重 (近 3 年最重的一成)", "外資大賣"))
        elif fn_pct >= 90: d.append(Driver("good", f"外資 20 日買超 {fn20:,.0f} 億：外資積極回補台股", "外資回補"))

    oi, oi_pct = _latest(df, "TW_Fut_Foreign_OI"), _pct_latest(df, "TW_Fut_Foreign_OI")
    if oi is not None and oi_pct is not None and oi_pct <= 10:
        d.append(Driver("bad", f"外資台指期淨空單 {-oi:,.0f} 口：外資用期貨大量避險 / 放空", "外資期貨偏空"))

    exports = _latest(df, "TW_Export_YoY")
    if exports is not None:
        if exports > 20: d.append(Driver("good", f"外銷訂單年增 {exports:.0f}%：接單強勁，電子股獲利有撐", "接單強勁"))
        elif exports < 0: d.append(Driver("bad", f"外銷訂單年減 {-exports:.0f}%：接單轉弱", "接單轉弱"))

    leading = _latest(df, "TW_NDC_Leading_Chg3")
    if leading is not None:
        if leading > 0.5: d.append(Driver("good", f"景氣領先指標 3 個月 {leading:+.2f}：台灣景氣後續偏好", "景氣領先走升"))
        elif leading < -0.5: d.append(Driver("bad", f"景氣領先指標 3 個月 {leading:+.2f}：台灣景氣後續轉弱", "景氣領先走弱"))

    sahm = _latest(df, "Sahm_Indicator")
    if sahm is not None and sahm >= 0.5:
        d.append(Driver("bad", f"薩姆指標 {sahm:.2f}：衰退訊號觸發", "衰退訊號"))
    # 外資動向是台股投資人最關心的，排在最前面 (sort 是穩定排序，其餘維持原順序)
    d.sort(key=lambda x: not x.short.startswith("外資"))
    return d


# 以「長期持有、調整股票比重」的投資人為對象
ACTIONS = {
    "offensive": ["股票比重分 2～3 次往上調 5～10%", "優先加碼核心長抱標的 (大盤 ETF、權值股)", "保留約一成現金，遇到大跌再分批"],
    "neutral": ["維持目前的股票 / 現金比例", "定期定額照常扣款，不額外加碼", "漲多的資產賣一點、調回原本比例 (再平衡)"],
    "defensive": ["股票比重往下調 5～10%，轉入現金或短債", "核心長抱部位不動，先減碼短線或高波動部位", "暫停額外加碼，等機會分數回到 45 以上"],
}
LABELS = {"offensive": "加碼", "neutral": "維持", "defensive": "減碼"}


def _headline(stance, risk):
    stormy = risk >= 65
    return {
        ("offensive", True): "市場動盪，但 3 個月勝率偏高",
        ("offensive", False): "風險平穩，3 個月勝率偏高",
        ("neutral", True): "波動劇烈、勝率普通：守住核心，不追不殺",
        ("neutral", False): "市場平穩、勝率普通：維持配置",
        ("defensive", True): "風險高、勝率低，先求自保",
        ("defensive", False): "表面平靜，但 3 個月勝率偏低",
    }[(stance, stormy)]


def market_verdict(df, scores, bottom_fishing=None):
    """依「3 個月機會分數」決定加碼 / 維持 / 減碼，「風險溫度」決定口吻與節奏。"""
    drivers = collect_drivers(df)
    opp = scores.opportunity if scores else 50
    risk = scores.risk if scores else 50

    if opp >= 55:
        stance = "offensive"
    elif opp < 35:
        stance = "defensive"
    else:
        stance = "neutral"

    actions = list(ACTIONS[stance])
    if stance == "offensive" and risk >= 65:
        actions[2] = "風險溫度高：每次加碼間隔拉長，不要一次重押"
    if bottom_fishing and bottom_fishing.met >= 3:
        actions.append(f"四大長線買點已成立 {bottom_fishing.met}/4，長債也可分批布局")

    # 利空與利多都列，但讓「與立場同方向」的排前面
    lead = "bad" if stance == "defensive" else "good" if stance == "offensive" else None
    drivers.sort(key=lambda x: x.tone != lead)

    odds = scores.odds if scores else None
    odds_txt = f"，歷史上類似分數 3 個月後上漲機率約 {odds['upProb']}%" if odds else ""
    one_liner = (f"今日台股建議{LABELS[stance]}：3 個月機會分數 {opp}、風險溫度 {risk}{odds_txt}"
                 f" —— {actions[0]}。")
    return Verdict(stance, LABELS[stance], _headline(stance, risk), actions, [asdict(x) for x in drivers], one_liner)


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
