"""FastAPI 後端：把 holly 計算層包成 JSON API，給 web/ (Next.js) 使用。

啟動：uvicorn api.main:app --port 8000
"""
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException

from holly import data
from holly.ai_advisor import generate_ai_summary
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
