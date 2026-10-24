import math

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api import main
from holly import data, stock_check
from holly.access import RateLimiter

from .conftest import make_raw

INFO = pd.DataFrame([
    {"stock_id": "6531", "stock_name": "愛普*", "industry_category": "半導體業", "type": "twse"},
    {"stock_id": "6531", "stock_name": "愛普*", "industry_category": "電子工業", "type": "twse"},
    {"stock_id": "2330", "stock_name": "台積電", "industry_category": "半導體業", "type": "twse"},
    {"stock_id": "2337", "stock_name": "旺宏", "industry_category": "半導體業", "type": "twse"},
    {"stock_id": "2882", "stock_name": "國泰金", "industry_category": "金融保險業", "type": "twse"},
    {"stock_id": "2881", "stock_name": "富邦金", "industry_category": "金融保險業", "type": "twse"},
]).assign(name=lambda d: d["stock_name"].str.replace("*", "", regex=False))


def test_resolve_by_id_and_names():
    assert stock_check.resolve("6531", INFO)[0]["name"] == "愛普"
    assert stock_check.resolve("愛普科技", INFO)[0]["id"] == "6531"        # 輸入比登記名稱長
    assert stock_check.resolve("台積", INFO)[0]["id"] == "2330"             # 輸入比登記名稱短
    assert stock_check.resolve("愛普", INFO)[0]["industry"] == "半導體業、電子工業"
    stock, candidates = stock_check.resolve("金", INFO)                     # 模糊 → 讓使用者選
    assert stock is None and {c["id"] for c in candidates} == {"2882", "2881"}
    assert stock_check.resolve("不存在的公司", INFO) == (None, [])


def _price(n=300, start=100.0, daily=0.001):
    days = pd.bdate_range("2025-06-01", periods=n)
    rng = np.random.default_rng(3)
    close = start * np.exp(np.cumsum(rng.normal(daily, 0.02, n)))
    return pd.DataFrame({"date": days.strftime("%Y-%m-%d"), "close": close})


def test_price_metrics_band_from_own_volatility():
    m = stock_check.price_metrics(_price())
    sig = m["vol"] / 100 * math.sqrt(63 / 252)
    assert m["band68"][0] == pytest.approx(m["close"] * math.exp(-sig))
    assert m["band90"][1] == pytest.approx(m["close"] * math.exp(1.645 * sig))
    assert m["band90"][0] < m["band68"][0] < m["close"] < m["band68"][1] < m["band90"][1]


def test_revenue_and_income_metrics():
    rev = pd.DataFrame({"revenue_year": [2025] * 9 + [2026] * 9, "revenue_month": list(range(1, 10)) * 2,
                        "revenue": [100.0] * 9 + [150.0] * 9})
    r = stock_check.revenue_metrics(rev)
    assert r["month"] == "2026/9" and r["yoy"] == pytest.approx(50) and r["ytdYoy"] == pytest.approx(50)

    quarters = pd.date_range("2024-09-30", periods=8, freq="QE").strftime("%Y-%m-%d")
    rows = []
    for i, q in enumerate(quarters):
        rows += [{"date": q, "type": "Revenue", "value": 1000.0}, {"date": q, "type": "GrossProfit", "value": 400.0 + 10 * i},
                 {"date": q, "type": "OperatingIncome", "value": 200.0}, {"date": q, "type": "EPS", "value": 1.0 + i * 0.1}]
    i = stock_check.income_metrics(pd.DataFrame(rows))
    assert i["grossMargin"] == pytest.approx(47) and i["grossMarginYearAgo"] == pytest.approx(43)
    assert i["epsTTM"] == pytest.approx(1.4 + 1.5 + 1.6 + 1.7)


def test_rate_limiter_window():
    rl = RateLimiter(limit=2, window=3600)
    assert rl.hit("a", now=0) is None and rl.hit("a", now=1) is None
    assert rl.hit("a", now=2) == 60            # 第 3 次被擋，約 60 分鐘後才能再用
    assert rl.hit("b", now=2) is None          # 別人不受影響
    assert rl.hit("a", now=3601) is None       # 一小時後恢復


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(data, "load_raw", make_raw)
    monkeypatch.setattr(data, "fetch_market_news", lambda: [])
    monkeypatch.setattr(stock_check, "stock_list", lambda: INFO)
    monkeypatch.setattr(stock_check, "fetch_stock_data", lambda sid: {"price": _price()})
    calls = []

    def fake_ai(prompt, key):
        calls.append(prompt)
        return {"summary": "測試", "stance": "中性", "price_3m": {"bear": 90, "base": 105, "bull": 120}, "risks": ["r"]}, "fake-model"

    monkeypatch.setattr(main, "ask_gemini_json", fake_ai)
    monkeypatch.setenv("APP_PASSCODE", "1102")
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    main.cache.clear()
    main._stock_results.clear()
    main.STOCK_PER_CLIENT.__init__(limit=10)
    main.STOCK_OVERALL.__init__(limit=40)
    import holly.access as access
    access._wrong_code.__init__(limit=8)
    with TestClient(main.app) as c:
        c.calls = calls
        yield c


def test_stock_check_requires_passcode(client):
    assert client.post("/api/stock-check", json={"query": "6531", "passcode": "0000"}).status_code == 401
    assert client.post("/api/stock-check", json={"query": "6531"}).status_code == 401


def test_stock_check_ok_and_shared_cache(client):
    body = client.post("/api/stock-check", json={"query": "愛普科技", "passcode": "1102"}).json()
    assert body["status"] == "ok" and body["stock"]["id"] == "6531" and body["ai"]["stance"] == "中性"
    assert "大盤局勢" in client.calls[0] and "統計區間" in client.calls[0]
    again = client.post("/api/stock-check", json={"query": "6531", "passcode": "1102"}).json()
    assert again["cached"] is True and len(client.calls) == 1        # 第二個人查同一檔，不再呼叫 AI


def test_stock_check_ambiguous_and_not_found(client):
    amb = client.post("/api/stock-check", json={"query": "金", "passcode": "1102"}).json()
    assert amb["status"] == "ambiguous" and len(amb["candidates"]) == 2
    assert client.post("/api/stock-check", json={"query": "火星電力", "passcode": "1102"}).status_code == 404


def test_stock_check_rate_limited_per_person(client):
    main.STOCK_PER_CLIENT.__init__(limit=1)
    ok = client.post("/api/stock-check", json={"query": "6531", "passcode": "1102"}, headers={"x-client-ip": "1.1.1.1"})
    assert ok.status_code == 200
    blocked = client.post("/api/stock-check", json={"query": "2330", "passcode": "1102"}, headers={"x-client-ip": "1.1.1.1"})
    assert blocked.status_code == 429 and "每小時最多 1 次" in blocked.json()["detail"]


def test_disabled_without_passcode_env(client, monkeypatch):
    monkeypatch.delenv("APP_PASSCODE")
    assert client.post("/api/stock-check", json={"query": "6531", "passcode": "1102"}).status_code == 503


def test_brute_force_blocked(client):
    for _ in range(8):
        client.post("/api/stock-check", json={"query": "6531", "passcode": "9999"}, headers={"x-client-ip": "2.2.2.2"})
    r = client.post("/api/stock-check", json={"query": "6531", "passcode": "9999"}, headers={"x-client-ip": "2.2.2.2"})
    assert r.status_code == 429
