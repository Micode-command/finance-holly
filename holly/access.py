"""互動工具的存取控制：密碼 + 使用次數限制 (保護 Gemini 與 FinMind 的免費額度)。

密碼放在環境變數 APP_PASSCODE (不寫進程式，因為 GitHub 倉庫是公開的)；沒設定時工具停用。
"""
import hmac
import threading
import time
from collections import defaultdict, deque

from .config import get_secret


class AccessError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status, self.message = status, message


class RateLimiter:
    """滑動視窗計數：每個 key 在 window 秒內最多 limit 次。"""

    def __init__(self, limit, window=3600):
        self.limit, self.window = limit, window
        self._hits = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key, now=None):
        """記一次；超過上限時回傳需要再等幾分鐘 (int)，沒超過回傳 None。"""
        now = time.time() if now is None else now
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > self.window:
                q.popleft()
            if len(q) >= self.limit:
                return int((self.window - (now - q[0])) // 60) + 1
            q.append(now)
            return None


_wrong_code = RateLimiter(limit=8)      # 密碼只有 4 碼，限制猜錯次數避免被暴力破解


def check_passcode(code, client):
    expected = get_secret("APP_PASSCODE")
    if not expected:
        raise AccessError(503, "這個功能尚未開放 (管理員還沒設定密碼)。")
    if hmac.compare_digest(str(code or "").strip(), expected):
        return
    wait = _wrong_code.hit(client)
    if wait:
        raise AccessError(429, f"密碼錯誤次數太多，請 {wait} 分鐘後再試。")
    raise AccessError(401, "密碼錯誤。")


def check_limits(client, per_client, overall, label):
    wait = per_client.hit(client)
    if wait:
        raise AccessError(429, f"{label}每小時最多 {per_client.limit} 次，請 {wait} 分鐘後再試。")
    wait = overall.hit("__all__")
    if wait:
        raise AccessError(429, f"目前使用人數較多，{label}暫時額滿，請 {wait} 分鐘後再試。")
