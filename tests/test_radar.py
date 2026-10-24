import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api import main
from holly import data, radar

from .conftest import make_raw

MONTHS = pd.date_range("2025-06-01", periods=15, freq="MS")
PE_DATES = pd.date_range("2023-10-31", periods=36, freq="ME")


def _world():
    """4 檔假想股票：
    1111 營收創新高 + 加速 + 價格合理 → 入選
    2222 營收創新高 + 加速，但比自己常態本益比便宜 50% (價值陷阱) → 排除
    3333 營收沒創新高 → 排除
    4444 營收創新高，但成長減速 → 排除"""
    codes = ["1111", "2222", "3333", "4444"]
    growth = {"1111": np.r_[np.full(12, 1.0), [1.3, 1.6, 2.0]], "2222": np.r_[np.full(12, 1.0), [1.3, 1.6, 2.0]],
              "3333": np.r_[np.full(12, 3.0), [1.0, 1.0, 1.0]], "4444": np.r_[np.full(9, 1.0), [1.5, 1.5, 1.5], [1.55, 1.6, 1.65]]}
    rev = pd.DataFrame({c: 100 * growth[c] for c in codes}, index=MONTHS)
    rev_ly = pd.DataFrame({c: np.full(15, 100.0) for c in codes}, index=MONTHS)
    # 4444：營收仍創新高，但年增率從 +50% 降到 +11~18% → 減速
    rev_ly["4444"] = np.r_[np.full(12, 100.0), [140.0, 140.0, 140.0]]
    pe_hist = pd.DataFrame({c: np.full(36, 20.0) for c in codes}, index=PE_DATES)
    cur = pd.DataFrame({"name": ["甲", "乙", "丙", "丁"], "close": 100.0, "turnover": 1e9, "pe": [19.0, 10.0, 19.0, 19.0],
                        "pb": 2.0, "dy": 3.0, "date": "1151022"}, index=pd.Index(codes, name="code"))
    latest = pd.DataFrame({"rev": rev.iloc[-1], "rev_ly": rev_ly.iloc[-1], "industry": "半導體業", "note": "因 AI 需求增加"})
    # 讓 1111 的加速排名在前 40%：再放幾檔一般股票當背景
    for i in range(6):
        code = f"5{i:03d}"
        rev[code] = 100.0; rev_ly[code] = 100.0; pe_hist[code] = 15.0
        cur.loc[code] = ["背景", 50.0, 1e9, 15.0, 1.0, 2.0, "1151022"]
        latest.loc[code] = [100.0, 100.0, "其他", ""]
    return cur, pe_hist, (rev.iloc[:-1], rev_ly.iloc[:-1]), MONTHS[-1], latest


def test_screen_keeps_only_growing_and_reasonably_priced():
    passed, funnel, month = radar.screen(*_world())
    assert list(passed.index) == ["1111"]
    assert funnel["passed"] == 1 and funnel["revHigh"] >= 3
    row = passed.loc["1111"]
    assert row["fairGap"] == pytest.approx((20 / 19 - 1) * 100)       # 現價比合理價低約 5%
    assert row["fairPrice"] == pytest.approx(100 * 20 / 19)


def test_parse_current():
    day = [{"Code": "2330", "Name": "台積電", "ClosingPrice": "2,385.00", "TradeValue": "71536783195", "Date": "1151022"}]
    pe = [{"Code": "2330", "PEratio": "27.65", "PBratio": "9.61", "DividendYield": "0.92"}]
    rev = [{"資料年月": "11509", "公司代號": "2330", "營業收入-當月營收": "511857399", "營業收入-去年當月營收": "330980920", "產業別": "半導體業", "備註": "先進製程需求"}]
    cur, month, latest = radar.parse_current(day, pe, rev)
    assert cur.loc["2330", "close"] == 2385.0 and month == pd.Timestamp("2026-09-01")
    assert latest.loc["2330", "note"] == "先進製程需求"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(data, "load_raw", make_raw)
    monkeypatch.setattr(data, "fetch_market_news", lambda: [{"title": "AI 伺服器需求強勁", "link": "x", "published": None, "source": "t"}])
    world = _world()
    monkeypatch.setattr(radar, "fetch_current", lambda: (world[0], world[3], world[4]))
    monkeypatch.setattr(radar, "load_snapshots", lambda: (world[1], world[2]))
    prompts = []

    def fake_ai(prompt, key):
        prompts.append(prompt)
        return {"themes": [{"name": "AI 伺服器", "demand": "新聞", "watch": "估值"}],
                "stocks": {"1111": {"theme": "AI 伺服器", "relation": "direct", "business": "測試", "why": "營收成長"}}}, "fake"

    monkeypatch.setattr(main, "ask_gemini_json", fake_ai)
    monkeypatch.setenv("APP_PASSCODE", "1102")
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    radar._cache.update(at=0.0, result=None)
    main.RADAR_PER_CLIENT.__init__(limit=10)
    main.cache.clear()
    with TestClient(main.app) as c:
        c.prompts = prompts
        yield c


def test_radar_api_shared_result(client):
    assert client.post("/api/radar", json={"passcode": "0000"}).status_code == 401
    body = client.post("/api/radar", json={"passcode": "1102"}).json()
    assert body["status"] == "ok" and [s["code"] for s in body["stocks"]] == ["1111"]
    assert body["stocks"][0]["theme"] == "AI 伺服器" and body["themes"][0]["name"] == "AI 伺服器"
    assert "AI 伺服器需求強勁" in client.prompts[0] and "因 AI 需求增加" in client.prompts[0]
    again = client.post("/api/radar", json={"passcode": "1102"}).json()
    assert again["cached"] is True and len(client.prompts) == 1          # 6 小時內共用，不再呼叫 AI


def test_indirect_theme_not_shown_as_main_tag():
    world = _world()
    ask = lambda prompt, key: ({"themes": [], "stocks": {"1111": {"theme": "AI", "relation": "indirect"}}}, "fake")
    r = radar.build_radar(world[0], world[1], world[2], world[3], world[4], ["新聞"], "key", ask)
    assert r["stocks"][0]["theme"] is None and r["stocks"][0]["indirectTheme"] == "AI"


def test_inorganic_growth_flagged_and_empty_notes_hidden():
    assert radar.clean_note("-") is None and radar.clean_note(" ") is None
    assert radar.INORGANIC.search("主係自115年8月底納入重要子公司FDK株式會社之營收")
    assert not radar.INORGANIC.search("因客戶需求增加，致使營收增加")
