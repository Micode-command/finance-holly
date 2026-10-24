"""台股開休市時鐘：盤前 / 盤中 / 收盤 / 休市，以及下一次開盤時間。

休市日來自證交所 OpenAPI (每年公布)；颱風假這類臨時休市不在清單裡，
由 overnight.py 用「開盤後期交所是否有今天的成交」補判斷。
"""
import time as _time
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import requests

TPE = ZoneInfo("Asia/Taipei")
OPEN, CLOSE = time(9, 0), time(13, 30)
HOLIDAY_URL = "https://openapi.twse.com.tw/v1/holidaySchedule/holidaySchedule"
WEEKDAYS = "一二三四五六日"

_cache = {"at": 0.0, "holidays": {}}


def parse_holidays(rows):
    """證交所清單 → {日期: 名稱}。清單也列了「開始交易日 / 最後交易日」，那些是交易日，要排除。"""
    out = {}
    for r in rows:
        name = r.get("Name", "")
        if "開始交易" in name or "最後交易" in name:
            continue
        roc = str(r.get("Date", ""))
        if len(roc) != 7:
            continue
        d = date(int(roc[:3]) + 1911, int(roc[3:5]), int(roc[5:]))
        out[d] = "農曆春節休市" if "市場無交易" in name else name
    return out


def fetch_holidays(ttl=12 * 3600):
    if _time.time() - _cache["at"] < ttl and _cache["holidays"]:
        return _cache["holidays"]
    try:
        rows = requests.get(HOLIDAY_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=30).json()
        _cache.update(at=_time.time(), holidays=parse_holidays(rows))
    except Exception as e:
        print(f"⚠️ 證交所休市日抓取失敗：{e}")   # 抓不到時沿用舊的；完全沒有就只排除週末
    return _cache["holidays"]


def is_trading_day(d, holidays):
    return d.weekday() < 5 and d not in holidays


def _step(d, holidays, direction):
    d = d + timedelta(days=direction)
    while not is_trading_day(d, holidays):
        d += timedelta(days=direction)
    return d


def fmt_day(d):
    return f"{d.month}/{d.day} ({WEEKDAYS[d.weekday()]})"


def market_status(now, holidays):
    """now：帶時區的 datetime。回傳狀態、說明、最後一個已收盤交易日、下一次開盤。"""
    now = now.astimezone(TPE)
    today, clock = now.date(), now.time()

    if is_trading_day(today, holidays):
        if clock < OPEN:
            state, label = "pre_open", "盤前"
            last_closed, next_open = _step(today, holidays, -1), today
        elif clock < CLOSE:
            state, label = "open", "盤中"
            last_closed, next_open = _step(today, holidays, -1), _step(today, holidays, +1)
        else:
            state, label = "closed", "已收盤"
            last_closed, next_open = today, _step(today, holidays, +1)
        reason = None
    else:
        state = "holiday" if today in holidays else "weekend"
        reason = holidays.get(today) or "週末"
        label = f"休市：{reason}"
        last_closed, next_open = _step(today, holidays, -1), _step(today, holidays, +1)

    next_open_at = datetime.combine(next_open, OPEN, tzinfo=TPE)
    # 下次開盤前還有沒有其他假日 (例如週末接補假)，讓畫面說明「連假」
    skipped = [holidays[d] for d in (today + timedelta(days=i) for i in range(1, (next_open - today).days)) if d in holidays]
    detail = {
        "open": f"今天 {CLOSE:%H:%M} 收盤",
        "pre_open": f"今天 {OPEN:%H:%M} 開盤",
    }.get(state, f"下次開盤 {fmt_day(next_open)} {OPEN:%H:%M}" + (f" (中間遇到{ '、'.join(dict.fromkeys(skipped)) })" if skipped else ""))
    return {
        "state": state, "label": label, "detail": detail, "reason": reason,
        "now": now.isoformat(timespec="minutes"),
        "lastClosedDay": last_closed.isoformat(),
        "nextOpenDay": next_open.isoformat(),
        "nextOpenAt": next_open_at.isoformat(),
        "hoursToOpen": round(max(0.0, (next_open_at - now).total_seconds() / 3600), 1) if state != "open" else 0,
    }
