"""更新專案內的外銷訂單備份檔 (經濟部網站擋海外 IP，雲端抓不到時會用這份)。

在台灣的電腦上執行：  .venv/bin/python scripts/update_export_orders.py
然後 git commit + push，Render 會自動用新的備份檔。經濟部約每月 20 日公布上個月數據。
"""
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from holly.taiwan import EXPORT_ORDERS_SNAPSHOT, HEADERS, MOEA_EXPORT_ORDERS_URL  # noqa: E402

r = requests.get(MOEA_EXPORT_ORDERS_URL, headers=HEADERS, timeout=60)
r.raise_for_status()
EXPORT_ORDERS_SNAPSHOT.write_bytes(r.content)
last = r.content.decode("utf-8-sig").strip().splitlines()[-1]
print(f"✅ 已更新 {EXPORT_ORDERS_SNAPSHOT}，最新一筆：{last}")
