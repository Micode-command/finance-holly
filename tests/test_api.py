"""API 測試：用模擬數據呼叫 FastAPI，確認前端拿到的 JSON 結構正確。"""
import pytest
from fastapi.testclient import TestClient

from api import main
from holly import data
from holly.catalog import SECTIONS

from .conftest import make_raw


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(data, "load_raw", make_raw)
    monkeypatch.setattr(data, "fetch_market_news", lambda: [
        {"title": "聯準會暗示降息 台積電大漲", "link": "https://example.com/1", "published": None, "source": "test"},
        {"title": "某公司舉辦員工旅遊", "link": "https://example.com/2", "published": None, "source": "test"},
    ])
    main.cache.clear()
    main.ai_cache.__init__()  # 每個測試從乾淨的 AI 快取開始
    with TestClient(main.app) as c:
        yield c


def test_dashboard_shape(client):
    body = client.get("/api/dashboard").json()
    cards = [c for s in body["sections"] for c in s["cards"]]
    assert len(cards) == sum(len(s.cards) for s in SECTIONS)
    assert all(c["available"] for c in cards)
    assert body["missingFred"] == []
    assert 0 <= body["scores"]["opportunity"] <= 100 and 0 <= body["scores"]["risk"] <= 100


def test_weekly_series_not_drawn_as_steps(client):
    body = client.get("/api/dashboard").json()
    card = next(c for s in body["sections"] for c in s["cards"] if c["id"] == "Total_Assets_T")
    # 週資料只畫公布日 (每週三或其後第一個交易日)，3 年約 156 點，而不是 750 個交易日
    assert 150 <= len(card["series"]) <= 160
    cpi = next(c for s in body["sections"] for c in s["cards"] if c["id"] == "CPI_YoY")
    assert 35 <= len(cpi["series"]) <= 37  # 月資料，即使數值沒變也保留


def test_macro_changes_compare_previous_release(client):
    body = client.get("/api/dashboard").json()
    card = next(c for s in body["sections"] for c in s["cards"] if c["id"] == "CPI_YoY")
    assert [c["label"] for c in card["changes"]] == ["上次公布", "3 個月", "1 年"]
    assert card["changeMode"] == "abs"


def test_ai_without_key_returns_fallback(client, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    body = client.post("/api/ai").json()
    assert "error" in body and "Forecast_Prob_Black_Swan" in body


def test_header_and_footer_payload(client):
    body = client.get("/api/dashboard").json()
    assert body["verdict"]["stance"] in {"offensive", "neutral", "defensive"}
    assert body["verdict"]["one_liner"].startswith("今日台股建議")
    assert {v["id"] for v in body["vitals"]} >= {"TAIEX", "VIX", "DGS10"}
    assert abs(sum(body["regime"].values()) - 100) < 0.2
    # 與股市無關的新聞會被濾掉
    assert [n["title"] for n in body["news"]] == ["聯準會暗示降息 台積電大漲"]
    assert body["news"][0]["topics"] == ["聯準會/利率", "AI/半導體", "市場情緒"]


def test_ai_result_shared_between_visitors(client, monkeypatch):
    calls = []

    def fake_ai(df, key, context, news=()):
        calls.append(1)
        return {"broadcast": "ok", "model": "fake"}

    monkeypatch.setattr(main, "generate_ai_summary", fake_ai)
    first = client.post("/api/ai").json()
    second = client.post("/api/ai").json()
    assert len(calls) == 1  # 第二位訪客拿到快取，不再呼叫 Gemini
    assert second["cached"] is True and second["generatedAt"] == first["generatedAt"]


def test_refresh_has_cooldown(client):
    client.get("/api/dashboard")
    r = client.post("/api/refresh")
    assert r.status_code == 429 and "分鐘後" in r.json()["detail"]


def test_secret_tolerates_pasted_whitespace_and_quotes(monkeypatch):
    from holly.config import get_secret
    monkeypatch.setenv("FAKE_KEY", '  "abc123"\n')
    assert get_secret("FAKE_KEY") == "abc123"
    monkeypatch.setenv("FAKE_KEY", "   ")
    assert get_secret("FAKE_KEY") is None


def test_every_card_has_glossary_terms_that_exist(client):
    import re
    from pathlib import Path
    glossary = Path(__file__).resolve().parents[1] / "web/lib/glossary.ts"
    ids = set(re.findall(r'id: "([a-z_]+)"', glossary.read_text()))
    body = client.get("/api/dashboard").json()
    for card in (c for s in body["sections"] for c in s["cards"]):
        assert card["terms"], f"{card['id']} 沒有對應名詞"
        assert set(card["terms"]) <= ids, f"{card['id']} 對應到不存在的名詞 {set(card['terms']) - ids}"


def test_market_download_retries_then_reports(monkeypatch):
    import pandas as pd
    from holly import data as d
    calls = {"n": 0}

    def flaky(ticker, period=None, progress=None):
        calls["n"] += 1
        if calls["n"] < 3:
            return pd.DataFrame()                                   # 前兩次 Yahoo 回空資料
        return pd.DataFrame({"Close": [1.0, 2.0]}, index=pd.DatetimeIndex(["2026-10-21", "2026-10-22"]))

    monkeypatch.setattr(d.yf, "download", flaky)
    monkeypatch.setattr(d.time, "sleep", lambda s: None)
    assert list(d._download_close("^TWII", 1)) == [1.0, 2.0] and calls["n"] == 3

    monkeypatch.setattr(d.yf, "download", lambda *a, **k: pd.DataFrame())
    monkeypatch.setattr(d, "YF_TICKERS", {"TAIEX": "^TWII"})
    assert d.fetch_market(1).empty and "TAIEX" in d.MARKET_ERRORS
