import pandas as pd

from holly.indicators import build_dataset, cycle_pr, growth_pr


def test_index_is_trading_days_only(raw):
    ds = build_dataset(raw)
    assert ds.df.index.equals(raw.index[raw["SPY"].notna()])


def test_no_backfill_from_future(raw):
    # 第一筆 GDP 之前不該有值 (舊版 bfill 會用未來數據填)
    raw = raw.copy()
    first_gdp = pd.Timestamp("2019-01-01")
    raw.loc[raw.index < first_gdp, "US_GDP"] = float("nan")
    ds = build_dataset(raw)
    assert ds.df.loc[ds.df.index < first_gdp, "US_GDP"].isna().all()


def test_last_date_uses_real_observation(raw):
    ds = build_dataset(raw)
    assert ds.last_date("CPI_YoY") == raw["CPI"].last_valid_index()
    # 多來源時取最舊的那個
    expected = min(raw[c].last_valid_index() for c in ["Total_Assets", "TGA_Account", "ON_RRP"])
    assert ds.last_date("Net_Liquidity_T") == expected


def test_missing_fred_reported(raw):
    ds = build_dataset(raw.drop(columns=["CPI", "DGS10"]))
    assert ds.missing_fred == ["DGS10", "CPI"]
    assert "Yield_Curve" not in ds.df.columns


def test_buffett_units(raw):
    df = build_dataset(raw).df
    row = df.dropna(subset=["Buffett"]).iloc[-1]
    assert row["Buffett"] == row["Corp_Equities"] / 1000 / row["US_GDP"] * 100


def test_pr_functions():
    s = pd.Series(range(1, 101), dtype=float)
    assert cycle_pr(s) == 100
    assert cycle_pr(s, invert=True) == 0
    assert growth_pr(s, 200) is None
    assert cycle_pr(pd.Series(dtype=float)) is None
