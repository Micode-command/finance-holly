import pytest
from fastapi.testclient import TestClient

from api import main
from holly import data, portfolio_check, stock_check

from .conftest import make_raw
from .test_stock_check import INFO, _price


def test_parse_holdings_normalizes_and_merges():
    holdings, cash = portfolio_check.parse_holdings(
        [{"query": "台積電", "weight": 30}, {"query": "2330", "weight": 10}, {"query": "愛普", "weight": 40}], cash=20, info=INFO)
    assert [h["id"] for h in holdings] == ["2330", "6531"]          # 重複的台積電合併
    assert holdings[0]["weight"] == pytest.approx(40) and cash == pytest.approx(20)
    amounts, cash2 = portfolio_check.parse_holdings([{"query": "2330", "weight": 300}], cash=100, info=INFO)   # 輸入金額也行
    assert amounts[0]["weight"] == pytest.approx(75) and cash2 == pytest.approx(25)


@pytest.mark.parametrize("rows, message", [
    ([], "至少輸入一筆"),
    ([{"query": "金", "weight": 10}], "符合多家公司"),
    ([{"query": "火星電力", "weight": 10}], "找不到"),
    ([{"query": "2330", "weight": 0}], "大於 0"),
    ([{"query": "2330", "weight": 1}] * 11, "最多輸入 10 筆"),
])
def test_parse_holdings_errors(rows, message):
    with pytest.raises(portfolio_check.PortfolioInputError, match=message):
        portfolio_check.parse_holdings(rows, 0, INFO)


def test_portfolio_metrics_concentration_and_beta():
    hs = [{"id": "2330", "name": "台積電", "industry": "半導體業", "weight": 60, "isEtf": False, "isBond": False, "beta": 1.2, "vol": 30, "dividendYield": 1.5},
          {"id": "0050", "name": "元大台灣50", "industry": "", "weight": 20, "isEtf": True, "isBond": False, "beta": 1.0, "vol": 20, "dividendYield": 3.0}]
    pm = portfolio_check.portfolio_metrics(hs, cash=20)
    assert pm["equity"] == 80 and pm["topHolding"]["name"] == "台積電"
    assert pm["effectiveN"] == pytest.approx(1 / (0.75 ** 2 + 0.25 ** 2))
    assert pm["beta"] == pytest.approx(0.6 * 1.2 + 0.2 * 1.0)          # 現金 Beta 0
    assert pm["industries"] == {"半導體業": 60, "股票型 ETF": 20} and pm["stockLike"] == 80 and pm["bond"] == 0


def test_normalize_suggested_weights():
    rows = portfolio_check.normalize_weights([{"name": "台積電", "current": 60, "suggested": 50}, {"name": "現金", "current": 20, "suggested": 30},
                                              {"name": "壞資料"}])
    assert [r["name"] for r in rows] == ["台積電", "現金"]
    assert sum(r["suggested"] for r in rows) == pytest.approx(100)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(data, "load_raw", make_raw)
    monkeypatch.setattr(data, "fetch_market_news", lambda: [])
    monkeypatch.setattr(stock_check, "stock_list", lambda: INFO)
    monkeypatch.setattr(portfolio_check, "fetch_light", lambda sid: {"price": _price()})
    prompts = []

    def fake_ai(prompt, key):
        prompts.append(prompt)
        return {"summary": "太集中", "risk_level": "高", "suggestions": [{"action": "減碼", "target": "台積電", "detail": "降 10 個百分點"}],
                "suggested_weights": [{"name": "台積電", "current": 80, "suggested": 70}, {"name": "現金", "current": 20, "suggested": 40}]}, "fake"

    monkeypatch.setattr(main, "ask_gemini_json", fake_ai)
    monkeypatch.setenv("APP_PASSCODE", "1102")
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    main.cache.clear()
    main.PORTFOLIO_PER_CLIENT.__init__(limit=5)
    main.PORTFOLIO_OVERALL.__init__(limit=15)
    with TestClient(main.app) as c:
        c.prompts = prompts
        yield c


def test_portfolio_check_ok(client):
    body = client.post("/api/portfolio-check", json={"passcode": "1102", "holdings": [{"query": "台積電", "weight": 80}], "cash": 20,
                                                     "goal": "income"}).json()
    assert body["status"] == "ok" and body["metrics"]["equity"] == pytest.approx(80)
    assert sum(r["suggested"] for r in body["ai"]["suggested_weights"]) == pytest.approx(100)   # 110 → 等比例調回 100
    assert "穩健領息" in client.prompts[0] and "今日大盤局勢" in client.prompts[0]


def test_portfolio_check_errors(client):
    assert client.post("/api/portfolio-check", json={"passcode": "0000", "holdings": [{"query": "2330", "weight": 1}]}).status_code == 401
    r = client.post("/api/portfolio-check", json={"passcode": "1102", "holdings": [{"query": "金", "weight": 1}]})
    assert r.status_code == 400 and "請改輸入股票代號" in r.json()["detail"]
    main.PORTFOLIO_PER_CLIENT.__init__(limit=1)
    ok = {"passcode": "1102", "holdings": [{"query": "2330", "weight": 1}]}
    assert client.post("/api/portfolio-check", json=ok).status_code == 200
    assert client.post("/api/portfolio-check", json=ok).status_code == 429


def test_trailing_yield_counts_last_12_months_only():
    import pandas as pd
    div = pd.DataFrame({"CashExDividendTradingDate": ["2025-09-16", "2026-01-16", "2026-07-16", "2026-10-19", "2026-12-01"],
                        "CashEarningsDistribution": [9.9, 0.07, 0.07, 0.07, 9.9], "CashStatutorySurplus": [0, 0, 0, 0.01, 0]})
    # 2025-09 太舊、2026-12 還沒除息 → 只算中間 3 次 = 0.22 元，股價 15 元
    assert portfolio_check.trailing_yield(div, 15.0, today="2026-10-24") == pytest.approx(0.22 / 15 * 100)
    assert portfolio_check.trailing_yield(pd.DataFrame(), 15.0) is None


def test_stance_check_flags_too_aggressive_advice():
    hs = [{"id": "2330", "name": "台積電", "isBond": False}, {"id": "0050", "name": "元大台灣50", "isBond": False},
          {"id": "00937B", "name": "群益ESG投等債20+", "isBond": True}]
    aggressive = [{"name": "台積電 (2330)", "suggested": 40}, {"name": "元大台灣50 (0050)", "suggested": 40},
                  {"name": "群益ESG投等債20+ (00937B)", "suggested": 15}, {"name": "現金", "suggested": 5}]
    c = portfolio_check.check_stance(aggressive, hs, current_stock=60, label="加碼")
    assert c["change"] == pytest.approx(20) and c["ok"] is False          # +20 超過加碼上限 +10
    modest = [dict(r) for r in aggressive]; modest[1]["suggested"] = 28; modest[3]["suggested"] = 17
    assert portfolio_check.check_stance(modest, hs, 60, "加碼")["ok"] is True   # +8
    assert portfolio_check.classify("高股息 ETF", hs) == "stock" and portfolio_check.classify("短天期美債", hs) == "bond"
