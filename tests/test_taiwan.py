import pandas as pd

from holly.taiwan import taiwan_frame


def _inst(days, foreign_net):
    rows = []
    for d, n in zip(days, foreign_net):
        rows += [{"date": d, "name": "Foreign_Investor", "buy": 1e10 + n, "sell": 1e10},
                 {"date": d, "name": "Foreign_Dealer_Self", "buy": 0, "sell": 0},
                 {"date": d, "name": "Investment_Trust", "buy": 2e8, "sell": 1e8}]
    return pd.DataFrame(rows)


def test_flows_in_yi_and_rolling_on_trading_days():
    days = [d.strftime("%Y-%m-%d") for d in pd.bdate_range("2026-01-05", periods=25)]
    df = taiwan_frame(inst=_inst(days, [-1e9] * 25))           # 每天賣超 10 億
    assert df["TW_Foreign_Net"].iloc[-1] == -10                # 單位：億
    assert df["TW_Foreign_Net_20D"].iloc[-1] == -200           # 20 個交易日累計
    assert df["TW_Trust_Net_20D"].iloc[-1] == 20


def test_futures_net_open_interest():
    fut = pd.DataFrame([{"date": "2026-10-22", "institutional_investors": "外資",
                         "long_open_interest_balance_volume": 9000, "short_open_interest_balance_volume": 96000},
                        {"date": "2026-10-22", "institutional_investors": "投信",
                         "long_open_interest_balance_volume": 1, "short_open_interest_balance_volume": 0}])
    assert taiwan_frame(fut=fut)["TW_Fut_Foreign_OI"].iloc[-1] == -87000


def test_monthly_data_only_used_after_release():
    ndc = pd.DataFrame({"Date": ["202606", "202607", "202608"], "景氣對策信號綜合分數": ["41", "41", "-"],
                        "領先指標不含趨勢指數": ["103.3", "103.9", "104.4"]})
    exports = pd.DataFrame({"統計項目": ["外銷訂單金額"] * 13, "資料期(民國年)": [f"1140{m}" if m < 10 else f"114{m}" for m in range(8, 13)]
                            + [f"1150{m}" for m in range(1, 9)], "統計值(美元)": [100] * 12 + [150]})
    df = taiwan_frame(ndc=ndc, exports=exports, now="2026-10-24")
    # 7 月的燈號要到 9/1 才採用；8 月 "-" (尚未公布) 不採用
    assert df["TW_NDC_Score"].dropna().index.max() == pd.Timestamp("2026-09-01")
    # 2026/08 外銷訂單 150 vs 2025/08 100 → 年增 50%，10/1 才採用
    yoy = df["TW_Export_YoY"].dropna()
    assert yoy.index.max() == pd.Timestamp("2026-10-01") and yoy.iloc[-1] == 50
    # 沒有被往後填滿：只出現在採用日
    assert df["TW_Export_YoY"].notna().sum() == 1


def test_missing_sources_are_skipped():
    assert taiwan_frame().empty
    assert list(taiwan_frame(per=pd.DataFrame({"date": ["2026-10-22"], "PER": [27.6]})).columns) == ["TW_PE_TSMC"]


def test_monthly_data_not_dated_in_the_future():
    exports = pd.DataFrame({"統計項目": ["外銷訂單金額"] * 14,
                            "資料期(民國年)": [f"1140{m}" if m < 10 else f"114{m}" for m in range(8, 13)] + [f"1150{m}" for m in range(1, 10)],
                            "統計值(美元)": [100] * 12 + [150, 170]})
    # 9 月數據已公布，但依規則 11/1 才採用；10/24 時最新應該還是 8 月數據 (10/1 採用)
    yoy = taiwan_frame(exports=exports, now="2026-10-24")["TW_Export_YoY"].dropna()
    assert yoy.index.max() == pd.Timestamp("2026-10-01") and yoy.iloc[-1] == 50
