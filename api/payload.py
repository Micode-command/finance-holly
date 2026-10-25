"""把 holly 的計算結果轉成前端用的 JSON (camelCase)。"""
import math
from dataclasses import asdict

import pandas as pd

from holly.catalog import CARD_TERMS, SECTIONS
from holly.commentary import macro_commentary
from holly.indicators import cycle_pr, growth_pr
from holly.news import market_moving_news
from holly.scores import market_scores
from holly.data import MARKET_ERRORS
from holly.taiwan import LAST_ERRORS
from holly.signals import bottom_fishing_signals, regime_probabilities
from holly.verdict import market_verdict, vitals

CHART_YEARS = 3
DAILY_CHANGES = [("1 週", 7), ("1 個月", 30), ("3 個月", 91)]
MACRO_CHANGES = [("3 個月", 91), ("1 年", 365)]


def _num(x, digits=4):
    if x is None:
        return None
    x = float(x)
    return None if math.isnan(x) or math.isinf(x) else round(x, digits)


def _date(ts):
    return ts.strftime("%Y-%m-%d") if ts is not None else None


# 依指標公布頻率選「約半年」的均線：日資料 120 日、週資料 26 週、月資料 6 個月、季資料 4 季
MA_BY_FREQUENCY = [(4, 120, "120 日均線 (半年線)"), (12, 26, "26 週均線 (半年)"), (45, 6, "6 個月均線"), (10_000, 4, "4 季均線 (一年)")]
PR_YEARS = 3       # 歷史位階只看近 3 年：資金規模與估值水準一直在變，10 年前的數字參考性低


def _ma_spec(points):
    gap = float(pd.Series(points.index).diff().dt.days.median()) if len(points) > 2 else 1
    return next((w, label) for limit, w, label in MA_BY_FREQUENCY if gap <= limit)


def _chart_points(dataset, column):
    """只畫真正公布數據的那些天 (週/月資料不畫成階梯)，並附上適合頻率的均線。"""
    s = dataset.release_points(column)
    window, label = _ma_spec(s)
    ma = s.rolling(window, min_periods=window).mean()
    keep = s.index >= s.index[-1] - pd.DateOffset(years=CHART_YEARS)
    return [[_date(d), _num(v), _num(m)] for d, v, m in zip(s.index[keep], s[keep], ma[keep])], label


def _change(latest, previous, mode):
    if previous is None or math.isnan(previous):
        return None
    if mode == "pct":
        return None if previous == 0 else (latest / previous - 1) * 100
    return latest - previous


def _changes(dataset, series, spec):
    latest, end = series.iloc[-1], series.index[-1]
    out = []
    if spec.is_macro:
        # 週/月資料先比「上一次公布」，再比較長的期間
        releases = dataset.release_points(spec.column)
        if len(releases) >= 2:
            out.append({"label": "上次公布", "value": _num(_change(latest, releases.iloc[-2], spec.change_mode))})
    for label, days in (MACRO_CHANGES if spec.is_macro else DAILY_CHANGES):
        target = end - pd.Timedelta(days=days)
        if target >= series.index[0]:
            out.append({"label": label, "value": _num(_change(latest, series.asof(target), spec.change_mode))})
    return out


def _percentiles(series, spec):
    if len(series) < 252:
        return []
    series = series[series.index >= series.index[-1] - pd.DateOffset(years=PR_YEARS)]
    if spec.pr_type == "C":
        pr = cycle_pr(series, invert=spec.invert_pr)
        return [{"label": "C-PR", "value": _num(pr, 1)}] if pr is not None else []
    return [{"label": f"G-{w}PR", "value": _num(pr, 1)} for w in (120, 200) if (pr := growth_pr(series, w)) is not None]


def card_payload(dataset, spec):
    card = {
        "id": spec.column, "title": spec.title, "desc": spec.desc,
        "prType": spec.pr_type, "isMacro": spec.is_macro, "invertColor": spec.invert_color,
        "decimals": spec.decimals, "signed": spec.signed, "prefix": spec.prefix, "suffix": spec.suffix,
        "changeMode": spec.change_mode, "defaultRange": spec.range, "prNeutral": spec.pr_neutral,
        "refLines": [{"value": v, "label": label} for v, label in spec.ref_lines],
        "terms": CARD_TERMS.get(spec.column, []),
        "available": False,
    }
    if spec.column not in dataset.df.columns or dataset.df[spec.column].dropna().empty:
        return card
    series = dataset.df[spec.column].dropna()
    card.update({
        "available": True,
        "latest": _num(series.iloc[-1]),
        "lastDate": _date(dataset.last_date(spec.column)),
        "changes": _changes(dataset, series, spec),
        "percentiles": _percentiles(series, spec),
        "note": spec.note(dataset) if spec.note else None,
    })
    card["series"], card["maLabel"] = _chart_points(dataset, spec.column)
    return card


def dashboard_payload(dataset, news_items=()):
    df = dataset.df
    scores = market_scores(df)
    bf = bottom_fishing_signals(df)
    verdict = market_verdict(df, scores, bf)
    return {
        "asOf": _date(df.index[-1]),
        "missingFred": dataset.missing_fred,
        "missingTw": dataset.missing_tw,
        "dataErrors": {**dict(LAST_ERRORS), **{f"yahoo:{k}": v for k, v in MARKET_ERRORS.items()}},
        "verdict": asdict(verdict),
        "vitals": [{**v, "value": _num(v["value"]), "change": _num(v["change"])} for v in vitals(dataset)],
        "regime": regime_probabilities(df),
        "news": market_moving_news(list(news_items)),
        "macro": macro_commentary(dataset),
        "scores": asdict(scores) if scores else None,
        "bottomFishing": None if bf is None else {
            "values": {k: _num(v) for k, v in bf.values.items()},
            "oilOk": bool(bf.oil_ok), "cpiOk": bool(bf.cpi_ok), "longRatesOk": bool(bf.long_rates_ok),
            "cutPricedIn": bool(bf.cut_priced_in), "met": int(bf.met),
        },
        "sections": [
            {"title": s.title, "nav": s.nav, "intro": s.intro, "cards": [card_payload(dataset, c) for c in s.cards]}
            for s in SECTIONS
        ],
    }
