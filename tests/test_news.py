import numpy as np
import pandas as pd

from holly.news import classify, market_moving_news
from holly.signals import regime_probabilities


def test_english_keywords_use_word_boundaries():
    assert "能源" in classify("Oil prices jump as OPEC cuts output")[0]
    assert classify("Water boils at home")[0] == []          # boil 不是 oil
    assert classify("Officials said rates stay")[0] == []    # said 不是 AI
    assert "日本/日圓" in classify("Yen slides as BOJ holds rates")[0]


def test_regions_get_their_quota():
    items = [{"title": f"台股大漲 台積電創新高 第{i}則", "region": "台灣", "published": None} for i in range(10)]
    items += [{"title": "Nikkei hits record as yen weakens", "region": "日本", "published": None},
              {"title": "Wall Street stocks rally on Fed rate cut hopes", "region": "美國", "published": None}]
    picked = market_moving_news(items, limit=6)  # 無時間 = 保留
    regions = [p["region"] for p in picked]
    assert "日本" in regions and "美國" in regions


def test_regime_probabilities_are_empirical_and_sum_to_100():
    rng = np.random.default_rng(1)
    idx = pd.bdate_range("2014-01-01", periods=2600)
    df = pd.DataFrame({"TAIEX": 10000 * np.exp(np.cumsum(rng.normal(0, 0.01, len(idx))))}, index=idx)
    p = regime_probabilities(df)
    assert abs(sum(p.values()) - 100) < 0.2
    assert p["Forecast_Prob_Black_Swan"] < 10
