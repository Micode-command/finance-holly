#!/usr/bin/env bash
# 一鍵啟動：Python 後端 (8000) + Next.js 前端 (3000)，Ctrl+C 同時關閉
set -e
cd "$(dirname "$0")"
[ -d .venv ] || { python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt; }
[ -d web/node_modules ] || (cd web && npm install)
trap 'kill 0' EXIT
.venv/bin/uvicorn api.main:app --port 8000 &
(cd web && npm run dev -- --port 3000) &
echo "👉 打開 http://localhost:3000 (第一次載入數據約 30 秒)"
wait
