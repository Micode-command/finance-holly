"""全站設定：數據來源代號、常數與 API 金鑰讀取。"""
import os
from pathlib import Path

from dotenv import load_dotenv

# 專案根目錄的 .env (已被 .gitignore 排除)。本機以 .env 為準 (override)，
# 避免 shell 裡殘留的舊金鑰蓋掉；雲端部署沒有 .env，則直接用平台設定的環境變數。
load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)

YEARS_BACK = 10

# 欄位名稱: (FRED series id, 是否為十億美元需轉成百萬美元)
FRED_SERIES = {
    "Total_Assets": ("WALCL", False),
    "ON_RRP": ("RRPONTSYD", True),
    "Reserve_Balances": ("WRESBAL", False),
    "TGA_Account": ("WDTGAL", False),
    "IORB": ("IORB", False),
    "SOFR": ("SOFR", False),
    "DGS30": ("DGS30", False),
    "DGS10": ("DGS10", False),
    "DGS2": ("DGS2", False),
    "CPI": ("CPIAUCSL", False),
    "Core_PCE": ("PCEPILFE", False),
    "Unemployment_Rate": ("UNRATE", False),
    "High_Yield_Spread": ("BAMLH0A0HYM2", False),
    # Wilshire 5000 已於 2024/6/3 自 FRED 下架，改用 Fed Z.1 非金融企業股權市值 (百萬美元，季資料)
    "Corp_Equities": ("NCBEILQ027S", False),
    "US_GDP": ("GDP", False),
}
# 這些序列直接向 FRED 要「年增率」(units=pc1)
FRED_YOY_SERIES = {"CPI", "Core_PCE"}

YF_TICKERS = {
    "SPY": "SPY", "QQQ": "QQQ", "IWM": "IWM", "XLP": "XLP",
    "SOX": "^SOX", "VIX": "^VIX", "DXY": "DX-Y.NYB",
    "USDJPY": "JPY=X", "USDTWD": "TWD=X",
    "WTI": "CL=F", "Brent": "BZ=F", "Gold": "GC=F", "Copper": "HG=F",
    "SMH": "SMH",
    "TAIEX": "^TWII",
}

NEWS_RSS_URL = "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664"  # 英文，餵給 AI
TW_NEWS_RSS_URLS = [  # 中文，首頁新聞時事
    "https://tw.stock.yahoo.com/rss?category=news",
    "https://tw.stock.yahoo.com/rss?category=intl-markets",
]
# 依序嘗試：3.5 Flash 最強但常忙線 (503)，忙線或額度用完就改用 2.5 Flash / Flash-Lite
GEMINI_MODELS = ["gemini-3.5-flash", "gemini-2.5-flash", "gemini-2.5-flash-lite"]


def get_secret(name):
    """讀取環境變數 (含 .env)；沒有則回傳 None。"""
    return os.environ.get(name) or None
