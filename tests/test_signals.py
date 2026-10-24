import pandas as pd

from holly.indicators import build_dataset
from holly.signals import bottom_fishing_signals, pr_matrix, regime_probabilities, taiwan_health_score


def test_bottom_fishing_none_when_data_missing(raw):
    df = build_dataset(raw.drop(columns=["IORB"])).df
    assert bottom_fishing_signals(df) is None


def test_bottom_fishing_conditions():
    idx = pd.bdate_range("2026-01-01", periods=3)
    df = pd.DataFrame({"Brent": 80.0, "CPI_YoY": 2.4, "DGS10": 4.2, "DGS30": 4.6, "DGS2": 3.5, "IORB": 4.0}, index=idx)
    bf = bottom_fishing_signals(df)
    assert (bf.oil_ok, bf.cpi_ok, bf.long_rates_ok, bf.cut_priced_in) == (True, True, False, True)
    assert bf.met == 3


def test_health_score_bounded(raw):
    hs = taiwan_health_score(build_dataset(raw).df)
    assert 0 <= hs.score <= 100
    assert hs.level in {"good", "warn", "bad"}
    assert len(hs.details) == 5


def test_regime_probabilities_sum_to_100(raw):
    probs = regime_probabilities(build_dataset(raw).df)
    assert abs(sum(probs.values()) - 100) < 0.2


def test_pr_matrix_includes_taiex_forecast(raw):
    pr = pr_matrix(build_dataset(raw).df)
    assert pr["Forecast_5D_TAIEX_Low"] < pr["Forecast_5D_TAIEX_High"]
    assert "Buffett_PR" in pr
