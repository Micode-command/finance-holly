"""更新潛力股雷達的歷史快照 (每月一次即可)：近 3 年月底本益比、近 15 個月月營收。

在台灣的電腦上執行：  .venv/bin/python scripts/update_radar_history.py [--cache 研究下載資料夾]
然後 git commit + push。證交所會擋太快的請求，所以每次請求間隔 3 秒，第一次約需 5 分鐘。
"""
import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from holly.radar import HEADERS, PE_SNAPSHOT, REV_SNAPSHOT, parse_bwibbu_rwd, parse_mops  # noqa: E402

cache = Path(sys.argv[sys.argv.index("--cache") + 1]) if "--cache" in sys.argv else None


def polite_get(url, encoding=None):
    for attempt in range(4):
        try:
            r = requests.get(url, headers=HEADERS, timeout=60)
            if encoding:
                r.encoding = encoding
            time.sleep(3)
            return r
        except Exception as e:
            print("  重試", e)
            time.sleep(10 * (attempt + 1))
    raise RuntimeError(url)


def month_end_pe(year, month):
    """該月最後一個有交易的日子的全市場本益比"""
    d = (date(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1))
    for _ in range(8):
        cached = cache / f"pe_{d:%Y%m%d}.json" if cache else None
        if cached and cached.exists():
            j = json.loads(cached.read_text())
        else:
            if d.weekday() >= 5:
                d -= timedelta(days=1)
                continue
            j = polite_get(f"https://www.twse.com.tw/rwd/zh/afterTrading/BWIBBU_d?date={d:%Y%m%d}&selectType=ALL&response=json").json()
        df = parse_bwibbu_rwd(j)
        if len(df):
            return d, df
        d -= timedelta(days=1)
    return None, None


def month_revenue(year, month):
    cached = cache / f"rev_{year}{month:02d}.html" if cache else None
    if cached and cached.exists():
        return parse_mops(cached.read_text(encoding="utf-8"))
    r = polite_get(f"https://mopsov.twse.com.tw/nas/t21/sii/t21sc03_{year - 1911}_{month}_0.html", encoding="big5")
    return parse_mops(r.text)


today = date.today()
months = [(today.year, today.month)]
for _ in range(40):
    y, m = months[-1]
    months.append((y - (m == 1), 12 if m == 1 else m - 1))
months = months[1:]                     # 不含本月 (還沒結束)

pe_rows = []
for y, m in months[:37]:
    d, df = month_end_pe(y, m)
    if df is not None:
        pe_rows.append(df.assign(date=d.isoformat()))
        print("本益比", d)
rev_rows = []
for y, m in months[1:17]:               # 上個月營收要到本月 10 日才公布，從上上個月開始
    df = month_revenue(y, m)
    if len(df):
        rev_rows.append(df.assign(month=f"{y}-{m:02d}-01"))
        print("營收", y, m, len(df))

PE_SNAPSHOT.parent.mkdir(exist_ok=True)
pd.concat(pe_rows)[["date", "code", "pe"]].dropna().to_csv(PE_SNAPSHOT, index=False, compression="gzip")
pd.concat(rev_rows)[["month", "code", "rev", "rev_ly"]].dropna().to_csv(REV_SNAPSHOT, index=False, compression="gzip")
print(f"✅ 已更新 {PE_SNAPSHOT.name} ({len(pe_rows)} 個月) 與 {REV_SNAPSHOT.name} ({len(rev_rows)} 個月)")
