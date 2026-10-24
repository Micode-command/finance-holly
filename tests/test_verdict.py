import pandas as pd

from holly.scores import MarketScores
from holly.signals import BottomFishing
from holly.verdict import collect_drivers, market_verdict


def _df(**cols):
    return pd.DataFrame(cols, index=pd.bdate_range("2026-01-01", periods=30))


def _scores(opp, risk, up=None):
    odds = {"upProb": up, "avgReturn": 1.0, "range": "x", "days": 100, "baseUpProb": 70} if up else None
    return MarketScores(opp, risk, 0, 0, odds=odds)


def test_trim_when_opportunity_low():
    df = _df(VIX=30.0, DGS10=4.9, Brent=110.0, USDTWD_ROC_5D=1.0)
    v = market_verdict(df, _scores(25, 80, up=31))
    assert v.stance == "defensive" and v.label == "減碼"
    assert v.headline == "風險高、勝率低，先求自保"
    assert v.drivers[0]["tone"] == "bad"
    assert "上漲機率約 31%" in v.one_liner and "股票比重往下調" in v.one_liner


def test_add_but_pace_slowly_when_stormy():
    v = market_verdict(_df(VIX=32.0), _scores(62, 85))
    assert v.stance == "offensive" and v.label == "加碼"
    assert "不要一次重押" in v.actions[2]


def test_hold_in_the_middle_and_mentions_bottom_fishing():
    bf = BottomFishing({}, True, True, True, False)
    v = market_verdict(_df(VIX=18.0), _scores(44, 30), bf)
    assert v.stance == "neutral" and v.label == "維持"
    assert any("四大長線買點已成立 3/4" in a for a in v.actions)
    assert collect_drivers(_df(VIX=18.0)) == []


def test_news_dedupes_same_story():
    from holly.news import market_moving_news
    items = [
        {"title": "油價飆至半年新高！美股道瓊大跌652點 台積電ADR漲1%", "link": "a", "published": "2", "source": "t"},
        {"title": "川普再提對伊朗動武推升油價！美股道瓊下殺652點、台積電ADR漲1.49%", "link": "b", "published": "1", "source": "t"},
        {"title": "聯準會官員暗示降息，美股開高", "link": "c", "published": "0", "source": "t"},
    ]
    titles = [n["title"] for n in market_moving_news(items)]
    assert len(titles) == 2 and titles[-1].startswith("聯準會")


def test_taiwan_drivers_foreign_first_and_positives_shown():
    import numpy as np
    idx = pd.bdate_range("2024-01-01", periods=400)
    flows = np.linspace(100, 0, 400); flows[-1] = -9000          # 最後一天外資 20 日賣超創新低
    df = pd.DataFrame({"VIX": 30.0, "TW_Foreign_Net_20D": flows, "TW_Export_YoY": 71.0, "TW_NDC_Leading_Chg3": 1.7}, index=idx)
    drivers = collect_drivers(df)
    shorts = [x.short for x in drivers]
    assert shorts[0] == "外資大賣" and "接單強勁" in shorts and "景氣領先走升" in shorts
    v = market_verdict(df, _scores(60, 86))
    assert v.drivers[0]["tone"] == "good"   # 加碼時，先列利多理由
