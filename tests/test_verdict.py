import pandas as pd

from holly.signals import BottomFishing, HealthScore
from holly.verdict import collect_drivers, market_verdict


def _df(**cols):
    return pd.DataFrame(cols, index=pd.bdate_range("2026-01-01", periods=30))


def test_defensive_when_risks_pile_up():
    df = _df(VIX=30.0, DGS10=4.9, Brent=110.0, USDTWD_ROC_5D=1.0)
    v = market_verdict(df, HealthScore(10, "bad", "恐慌殺盤"), None)
    assert v.stance == "defensive" and v.label == "防守"
    assert v.drivers[0]["tone"] == "bad"
    assert "VIX 恐慌" in v.one_liner and "提高台幣現金" in v.one_liner


def test_offensive_when_bottom_fishing_confirmed():
    df = _df(VIX=14.0, DGS10=3.9)
    bf = BottomFishing({}, True, True, True, False)
    v = market_verdict(df, HealthScore(55, "warn", "震盪整理"), bf)
    assert v.stance == "offensive"
    assert v.drivers[0]["tone"] == "good"


def test_neutral_without_strong_signals():
    v = market_verdict(_df(VIX=18.0), HealthScore(50, "warn", "震盪整理"), None)
    assert v.stance == "neutral"
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
