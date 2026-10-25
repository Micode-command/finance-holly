"""對外 API 的用量預算：保證不超過免費額度 (超過時拒絕新請求，而不是被對方懲罰或封鎖)。

| 服務 | 官方免費限制 | 本站上限 (保守) |
|---|---|---|
| FinMind (有 token) | 600 次 / 小時 | 450 次 / 小時 |
| Gemini 免費層 | 依模型約 10 次 / 分鐘、數百次 / 天 | 6 次 / 分鐘、150 次 / 天 (含備援模型的重試) |
"""
import threading
import time
from collections import deque


class Budget:
    """多個滑動視窗同時限制，例如「每分鐘 6 次 且 每天 150 次」。"""

    def __init__(self, name, limits):
        self.name, self.limits = name, limits          # [(次數, 秒數), ...]
        self._hits = deque()
        self._lock = threading.Lock()

    def _trim(self, now):
        longest = max(w for _, w in self.limits)
        while self._hits and now - self._hits[0] > longest:
            self._hits.popleft()

    def remaining(self, now=None):
        now = time.time() if now is None else now
        with self._lock:
            self._trim(now)
            return min(n - sum(1 for t in self._hits if now - t <= w) for n, w in self.limits)

    def take(self, n=1, now=None):
        """扣 n 次；額度不足時回傳 False 且不扣。"""
        now = time.time() if now is None else now
        with self._lock:
            self._trim(now)
            for limit, window in self.limits:
                if sum(1 for t in self._hits if now - t <= window) + n > limit:
                    return False
            self._hits.extend([now] * n)
            return True

    def usage(self, now=None):
        now = time.time() if now is None else now
        with self._lock:
            self._trim(now)
            return {f"per_{w}s": {"used": sum(1 for t in self._hits if now - t <= w), "limit": n} for n, w in self.limits}


MINUTE, HOUR, DAY = 60, 3600, 86400
finmind = Budget("FinMind", [(450, HOUR)])
gemini = Budget("Gemini", [(6, MINUTE), (150, DAY)])
