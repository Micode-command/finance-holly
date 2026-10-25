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


def test_projection_reverts_toward_mean_with_widening_band():
    from holly.scores import project
    rng = np.random.default_rng(0)
    x = np.zeros(1500)
    for i in range(1, 1500):                      # 會回歸平均 50 的序列
        x[i] = 0.97 * x[i - 1] + rng.normal(0, 2)
    s = pd.Series(50 + x, index=pd.bdate_range("2020-01-01", periods=1500))
    s.iloc[-1] = 90                               # 今天特別高
    p = project(s)
    assert p[0] == [0, 90.0, 90.0, 90.0]
    mids = [m for _, m, _, _ in p]
    assert mids == sorted(mids, reverse=True) and mids[-1] < 75        # 往 50 回落
    widths = [hi - lo for _, _, lo, hi in p[1:]]
    assert widths[-1] > widths[0]                                       # 越遠越不確定
