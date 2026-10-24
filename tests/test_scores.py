import numpy as np
import pandas as pd

from holly.indicators import build_dataset
from holly.scores import OPPORTUNITY, composite, market_scores


def test_scores_in_range_and_smooth(raw):
    s = market_scores(build_dataset(raw).df)
    assert 0 <= s.opportunity <= 100 and 0 <= s.risk <= 100
    assert len(s.opportunity_details) == len(OPPORTUNITY)
    assert s.odds is None or 0 <= s.odds["upProb"] <= 100
    opp, _ = composite(build_dataset(raw).df, OPPORTUNITY, 10)
    assert opp.dropna().diff().abs().mean() < 5  # 平滑後不應天天大跳


def test_no_lookahead():
    """未來的數據改變，不能影響過去某天的分數"""
    idx = pd.bdate_range("2018-01-01", periods=1200)
    rng = np.random.default_rng(0)
    base = {c: 100 * np.exp(np.cumsum(rng.normal(0, 0.01, len(idx)))) for c in
            ["VIX", "High_Yield_Spread", "Net_Liquidity", "DXY", "DGS10", "Copper", "TAIEX"]}
    df = pd.DataFrame(base, index=idx)
    full, _ = composite(df, OPPORTUNITY, 10)
    cut = df.iloc[:900]
    partial, _ = composite(cut, OPPORTUNITY, 10)
    assert np.allclose(full.iloc[:900].dropna(), partial.dropna())


def test_contrarian_direction():
    """VIX 與垃圾債利差飆高時，機會分數應該上升 (歷史上恐慌常是 3 個月後的買點)"""
    idx = pd.bdate_range("2018-01-01", periods=600)
    calm = pd.DataFrame({"VIX": 15.0, "High_Yield_Spread": 3.0, "Copper": 4.0}, index=idx)
    calm.iloc[:, :] += np.random.default_rng(1).normal(0, 0.01, calm.shape)
    panic = calm.copy()
    panic.iloc[-30:, :2] *= 2.5
    o_calm, _ = composite(calm, OPPORTUNITY, 10)
    o_panic, _ = composite(panic, OPPORTUNITY, 10)
    assert o_panic.iloc[-1] > o_calm.iloc[-1] + 20
