"""Vercel 部署後端用的進入點：Vercel 會在專案根目錄的 index.py 找 FastAPI 的 app。"""
from api.main import app  # noqa: F401
