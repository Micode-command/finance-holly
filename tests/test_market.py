from datetime import date, datetime

import pandas as pd

from holly.market_clock import TPE, market_status, parse_holidays
from holly.overnight import detect_suspension, opening_forecast, parse_taifex, reconcile_last_session

HOLIDAYS = parse_holidays([
    {"Date": "1151025", "Name": "臺灣光復暨金門古寧頭大捷紀念日"},
    {"Date": "1151026", "Name": "臺灣光復暨金門古寧頭大捷紀念日"},
    {"Date": "1150211", "Name": "農曆春節前最後交易日"},          # 這是交易日，不能被當成假日
    {"Date": "1150212", "Name": "市場無交易，僅辦理結算交割作業"},
])
at = lambda *a: datetime(*a, tzinfo=TPE)


def test_holiday_list_excludes_trading_day_entries():
    assert date(2026, 2, 11) not in HOLIDAYS
    assert HOLIDAYS[date(2026, 2, 12)] == "農曆春節休市"


def test_states_through_a_trading_day():
    assert market_status(at(2026, 10, 22, 8, 30), HOLIDAYS)["state"] == "pre_open"
    assert market_status(at(2026, 10, 22, 10, 0), HOLIDAYS)["state"] == "open"
    s = market_status(at(2026, 10, 22, 14, 0), HOLIDAYS)
    assert s["state"] == "closed" and s["lastClosedDay"] == "2026-10-22" and s["nextOpenDay"] == "2026-10-23"


def test_weekend_then_makeup_holiday_skips_to_tuesday():
    s = market_status(at(2026, 10, 24, 15, 0), HOLIDAYS)           # 週六
    assert s["state"] == "weekend" and s["label"] == "休市：週末"
    assert s["nextOpenDay"] == "2026-10-27"                          # 週一補假，週二才開盤
    assert "臺灣光復暨金門古寧頭大捷紀念日" in s["detail"]
    h = market_status(at(2026, 10, 26, 10, 0), HOLIDAYS)
    assert h["state"] == "holiday" and h["reason"] == "臺灣光復暨金門古寧頭大捷紀念日"


def test_unscheduled_closure_detected_when_no_trades_today():
    s = market_status(at(2026, 10, 23, 9, 30), HOLIDAYS)
    taifex = {"spot": {"date": "20261022", "last": 46041.43, "ref": 46887.77, "pct": -1.81}}
    assert detect_suspension(s, taifex, at(2026, 10, 23, 9, 30))["state"] == "suspended"
    taifex["spot"]["date"] = "20261023"
    assert detect_suspension(s, taifex, at(2026, 10, 23, 9, 30))["state"] == "open"


def test_parse_taifex_picks_near_month_and_spot():
    night = [{"SymbolID": "TXF-P", "CLastPrice": "", "CRefPrice": "46041", "CDiffRate": "0", "CDate": "20261022"},
             {"SymbolID": "TXFK6-M", "CLastPrice": "45654", "CRefPrice": "46234", "CDiffRate": "-1.25", "CDate": "20261022", "CTime": "045959"}]
    day = [{"SymbolID": "TXF-S", "CLastPrice": "46041.43", "CRefPrice": "46887.77", "CDiffRate": "-1.81", "CDate": "20261022"}]
    q = parse_taifex(night, day)
    assert q["night"]["pct"] == -1.25 and q["spot"]["last"] == 46041.43 and q["day"] is None


def _us(dates, closes):
    return pd.Series(closes, index=dates)


def test_forecast_uses_only_information_after_tw_close():
    status = market_status(at(2026, 10, 22, 16, 0), HOLIDAYS)       # 收盤後、美股還沒開
    taifex = {"spot": {"date": "20261022", "last": 46000.0, "pct": -1.8},
              "night": {"date": "20261022", "last": 45700.0, "pct": -1.0, "time": "160500"}}
    us = {"ewt": _us([date(2026, 10, 20), date(2026, 10, 21)], [100.0, 101.0]),
          "sox": _us([date(2026, 10, 20), date(2026, 10, 21)], [100.0, 101.0])}
    f = opening_forecast(status, {}, taifex, us)
    assert f["model"] == "night_only"                                 # 10/22 之後還沒有美股交易 → 不用美股
    assert f["gapPct"] == round(0.040 + 0.555 * -1.0, 2) and f["direction"] == "開低"
    assert f["gapPoints"] == round(46000 * (0.040 + 0.555 * -1.0) / 100)   # 點數用未四捨五入的 % 計算


def test_forecast_combines_night_and_us_after_us_session():
    status = market_status(at(2026, 10, 23, 6, 0), HOLIDAYS)        # 隔天清晨 (假設 10/23 正常開盤)
    taifex = {"spot": {"date": "20261022", "last": 46000.0, "pct": -1.8},
              "night": {"date": "20261022", "last": 46200.0, "pct": 0.5, "time": "045959"}}
    us = {"ewt": _us([date(2026, 10, 21), date(2026, 10, 22)], [100.0, 99.0]),
          "sox": _us([date(2026, 10, 21), date(2026, 10, 22)], [100.0, 102.0])}
    f = opening_forecast(status, {}, taifex, us)
    ewt_new = (0.99 / 0.982 - 1) * 100                                # EWT 跌 1%，但台股當天已跌 1.8% → 新資訊其實是 +0.8%
    assert f["model"] == "full"
    assert abs(f["gapPct"] - round(0.039 + 0.386 * 0.5 + 0.052 * ewt_new + 0.040 * 2.0, 2)) < 0.011


def test_no_forecast_right_after_close_and_none_during_session():
    status = market_status(at(2026, 10, 22, 14, 0), HOLIDAYS)
    f = opening_forecast(status, {date(2026, 10, 21): 46887.0, date(2026, 10, 22): 46041.0}, {}, {})
    assert f["model"] is None and "15:00" in f["message"] and f["lastClose"] == 46041.0
    assert opening_forecast(market_status(at(2026, 10, 22, 10, 0), HOLIDAYS), {}, {}, {}) is None


def test_unscheduled_closure_uses_actual_last_session():
    """10/23 不在放假清單但臨時休市：基準要回到 10/22，才能用到 10/22 的夜盤、並從 10/21 美股收盤起算"""
    status = market_status(at(2026, 10, 24, 18, 0), HOLIDAYS)
    assert status["lastClosedDay"] == "2026-10-23"
    taifex = {"spot": {"date": "20261022", "last": 46041.43, "pct": -1.81},
              "night": {"date": "20261022", "last": 45654.0, "pct": -1.25, "time": "045959"}}
    fixed = reconcile_last_session(status, taifex)
    assert fixed["lastClosedDay"] == "2026-10-22" and "10/23 臨時休市" in fixed["note"]
    us = {"ewt": _us([date(2026, 10, 21), date(2026, 10, 22), date(2026, 10, 23)], [100.0, 99.0, 100.0]),
          "sox": _us([date(2026, 10, 21), date(2026, 10, 22), date(2026, 10, 23)], [100.0, 99.0, 100.0])}
    f = opening_forecast(fixed, {}, taifex, us)
    assert f["model"] == "full" and f["lastClose"] == 46041.43
    sox_in = next(i for i in f["inputs"] if i["key"] == "sox")
    assert abs(sox_in["pct"]) < 1e-9          # 10/21 → 10/23 累計 0%
