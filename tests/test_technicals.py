import numpy as np
import pandas as pd

from holly import technicals


def _price(closes):
    d = pd.bdate_range("2025-01-01", periods=len(closes))
    c = pd.Series(closes, dtype=float)
    return pd.DataFrame({"date": d.strftime("%Y-%m-%d"), "close": c, "max": c * 1.01, "min": c * 0.99})


def test_uptrend_reads_bullish_and_plan_is_consistent():
    rng = np.random.default_rng(0)
    closes = 100 * np.exp(np.cumsum(0.003 + rng.normal(0, 0.005, 300)))
    t = technicals.analyze(_price(closes))
    assert t["trend"]["kind"] == "上升"
    assert all(m["above"] for m in t["mas"][-2:])
    p = t["plan"]
    assert p["stop"] < p["entryLow"] <= p["entry"] <= p["entryHigh"]
    assert p["entry"] * 0.88 <= p["stop"]
    assert p["target"] > p["entry"] and p["rr"] > 0


def test_zones_merge_nearby_pivots():
    sup, res = technicals.zones([90, 91, 92.5, 110, 111, 130], close=100)
    assert sup[0] == {"low": 90, "high": 92.5, "touches": 3}
    assert res[0]["low"] == 110 and res[0]["touches"] == 2


def test_target_capped_by_volatility_band():
    plan = technicals.trade_plan(100, 2, [{"low": 95, "high": 97, "touches": 2}], [{"low": 200, "high": 205, "touches": 1}], cap=120)
    assert plan["target"] == 120 and "90%" in plan["targetBasis"]


def test_short_history_returns_none():
    assert technicals.analyze(_price(np.linspace(10, 20, 60))) is None


def test_ai_news_impacts_need_real_sources():
    from holly.ai_advisor import valid_impacts
    items = [{"event": "A", "sources": [1, 2]}, {"event": "B", "sources": [9]}, {"event": "C", "sources": "x"}, {"sources": [1]}]
    assert [i["event"] for i in valid_impacts(items, n_headlines=3)] == ["A"]
