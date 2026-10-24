"""FastAPI 後端：把 holly 計算層包成 JSON API，給 web/ (Next.js) 使用。

啟動：uvicorn api.main:app --port 8000
"""
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime

import math

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from holly import data
from holly import portfolio_check, stock_check
from holly.access import AccessError, RateLimiter, check_limits, check_passcode
from holly.ai_advisor import ask_gemini_json, generate_ai_summary
from holly.config import get_secret
from holly.indicators import build_dataset
from holly.market_clock import TPE, fetch_holidays, market_status
from holly.overnight import detect_suspension, live_inputs, opening_forecast, reconcile_last_session

from .payload import dashboard_payload

CACHE_TTL = 3600  # 秒；抓一次全部數據約 20-30 秒，一小時內共用
REFRESH_COOLDOWN = 600  # 公開網站上「強制重新抓取」的冷卻時間，避免被狂按
AI_RETRY_COOLDOWN = 30  # AI 失敗後，所有訪客至少等這麼久才能再試


class _Cache:
    def __init__(self):
        self._lock = threading.Lock()
        self._loaded_at = 0.0
        self.dataset = None
        self.payload = None

    def get(self):
        # 用鎖確保多個請求同時進來時只抓一次數據
        with self._lock:
            if self.payload is None or time.time() - self._loaded_at > CACHE_TTL:
                raw = data.load_raw()
                if raw.empty:
                    raise HTTPException(503, "無法取得數據。請檢查網路或 FRED_API_KEY。")
                self.dataset = build_dataset(raw)
                self.payload = dashboard_payload(self.dataset, data.fetch_market_news())
                self._loaded_at = time.time()
            return self.dataset, self.payload

    @property
    def age(self):
        return time.time() - self._loaded_at

    @property
    def version(self):
        return self._loaded_at

    def clear(self):
        with self._lock:
            self.payload = None


class _AiCache:
    """AI 解盤在「同一份數據」下只產生一次，所有訪客共用，保護 Gemini 免費額度。"""

    def __init__(self):
        self._lock = threading.Lock()
        self.version = None
        self.result = None
        self.failed_at = 0.0

    def get(self, version, generate):
        with self._lock:  # 多人同時按，只有第一個會真的呼叫 Gemini，其他人等結果
            if self.result is not None and self.version == version:
                return {**self.result, "cached": True}
            if time.time() - self.failed_at < AI_RETRY_COOLDOWN:
                raise HTTPException(429, f"AI 剛剛連線失敗，請 {AI_RETRY_COOLDOWN} 秒後再試。")
            result = generate()
            if result.get("error"):
                self.failed_at = time.time()
                return result
            self.version = version
            self.result = {**result, "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
            return self.result


cache = _Cache()
ai_cache = _AiCache()


@asynccontextmanager
async def lifespan(app):
    # 啟動時就在背景先抓數據，第一個打開網頁的人不用等
    threading.Thread(target=_safe_warm, daemon=True).start()
    yield


def _safe_warm():
    try:
        cache.get()
    except Exception as e:
        print(f"⚠️ 預先載入數據失敗：{e}")


app = FastAPI(title="Holly Dashboard API", lifespan=lifespan)


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/dashboard")
def dashboard():
    _, payload = cache.get()
    return {**payload, "aiEnabled": bool(get_secret("GEMINI_API_KEY"))}


@app.get("/api/market")
def market():
    """台股現在開盤了沒？沒開盤時預估下次開盤。每次請求都依「現在時間」重算 (即時報價有短快取)。"""
    now = datetime.now(TPE)
    status = market_status(now, fetch_holidays())
    taifex, us = live_inputs()
    status = reconcile_last_session(detect_suspension(status, taifex, now), taifex)
    forecast = None
    if status["state"] != "open":
        dataset, _ = cache.get()
        closes = dataset.release_points("TAIEX") if "TAIEX" in dataset.df.columns else None
        taiex = {d.date(): float(v) for d, v in closes.tail(10).items()} if closes is not None else {}
        forecast = opening_forecast(status, taiex, taifex, us)
    return {"status": status, "forecast": forecast}


# ---------- 互動工具 (需要密碼) ----------

STOCK_PER_CLIENT = RateLimiter(limit=10)   # 每人每小時
STOCK_OVERALL = RateLimiter(limit=40)      # 全站每小時 (保護 Gemini / FinMind 額度)
_stock_results = {}                         # 股票代號 → (時間, 結果)，1 小時內所有人共用


def _client(request):
    # Next.js 轉發時會帶上訪客真正的 IP；直接呼叫時用連線來源
    return request.headers.get("x-client-ip") or (request.client.host if request.client else "unknown")


def _clean(x):
    """JSON 不接受 NaN / Infinity：換成 null"""
    if isinstance(x, float):
        return None if math.isnan(x) or math.isinf(x) else x
    if isinstance(x, dict):
        return {k: _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    return x


def _market_context(payload):
    v, s = payload.get("verdict") or {}, payload.get("scores") or {}
    return {"label": v.get("label"), "headline": v.get("headline"), "actions": v.get("actions"),
            "opportunity": s.get("opportunity"), "risk": s.get("risk")}


@app.post("/api/stock-check")
def stock_check_api(request: Request, body: dict = Body(...)):
    client = _client(request)
    try:
        check_passcode(body.get("passcode"), client)
        query = str(body.get("query") or "").strip()[:30]
        if not query:
            raise AccessError(400, "請輸入公司名稱或股票代號。")
        try:
            stock, candidates = stock_check.resolve(query, stock_check.stock_list())
        except Exception as e:
            raise AccessError(502, f"股票清單暫時抓不到，請稍後再試。({str(e)[:80]})")
        if candidates:
            return {"status": "ambiguous", "candidates": candidates}
        if stock is None:
            raise AccessError(404, f"找不到「{query}」，可以改用股票代號試試 (例如 6531)。")

        hit = _stock_results.get(stock["id"])
        if hit and time.time() - hit[0] < stock_check.RESULT_TTL and not hit[1].get("error"):
            return _clean({"status": "ok", **hit[1], "cached": True})

        check_limits(client, STOCK_PER_CLIENT, STOCK_OVERALL, "個股健檢")
        dataset, dash = cache.get()
        taiex = dataset.release_points("TAIEX") if "TAIEX" in dataset.df.columns else None
        metrics = stock_check.compute_metrics(stock_check.fetch_stock_data(stock["id"]), taiex)
        result = stock_check.analyze(stock, metrics, _market_context(dash), get_secret("GEMINI_API_KEY"), ask_gemini_json)
        _stock_results[stock["id"]] = (time.time(), result)
        return _clean({"status": "ok", **result, "cached": False})
    except AccessError as e:
        return JSONResponse({"detail": e.message}, status_code=e.status)


PORTFOLIO_PER_CLIENT = RateLimiter(limit=5)
PORTFOLIO_OVERALL = RateLimiter(limit=15)


@app.post("/api/portfolio-check")
def portfolio_check_api(request: Request, body: dict = Body(...)):
    """持股資料只在這次請求中使用，不寫入任何地方、不快取結果。"""
    client = _client(request)
    try:
        check_passcode(body.get("passcode"), client)
        try:
            holdings, cash = portfolio_check.parse_holdings(body.get("holdings"), body.get("cash"), stock_check.stock_list())
        except portfolio_check.PortfolioInputError as e:
            raise AccessError(400, str(e))
        check_limits(client, PORTFOLIO_PER_CLIENT, PORTFOLIO_OVERALL, "配置健檢")
        dataset, dash = cache.get()
        taiex = dataset.release_points("TAIEX") if "TAIEX" in dataset.df.columns else None
        portfolio_check.enrich(holdings, portfolio_check.fetch_light, taiex)
        result = portfolio_check.analyze(holdings, cash, body.get("goal"), _market_context(dash), get_secret("GEMINI_API_KEY"), ask_gemini_json)
        return _clean({"status": "ok", **result})
    except AccessError as e:
        return JSONResponse({"detail": e.message}, status_code=e.status)


@app.post("/api/ai")
def ai_summary():
    dataset, payload = cache.get()
    # 把頁面上的結論與總經評語一起給 AI，避免 AI 的解讀和頁面自相矛盾
    context = {"verdict": payload["verdict"], "macro": payload["macro"], "scores": payload["scores"]}
    return ai_cache.get(cache.version, lambda: generate_ai_summary(dataset.df, get_secret("GEMINI_API_KEY"), context))


@app.post("/api/refresh")
def refresh():
    if cache.payload is not None and cache.age < REFRESH_COOLDOWN:
        wait = int(REFRESH_COOLDOWN - cache.age) // 60 + 1
        raise HTTPException(429, f"數據才剛更新過，約 {wait} 分鐘後才能再強制重新抓取。")
    cache.clear()
    cache.get()
    return {"ok": True}
