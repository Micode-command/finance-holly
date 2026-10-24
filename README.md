# 🏦 荷莉總經觀測站 (Holly Dashboard)

每日 1 分鐘看懂聯準會流動性、美股 / 台股位階與系統風險。

- **後端**：Python (FastAPI) — 抓 FRED / Yahoo 數據、計算指標與訊號、呼叫 Gemini
- **前端**：Next.js (App Router) + Tailwind CSS + Recharts

## 執行

```bash
./dev.sh          # 同時啟動後端 :8000 與前端 :3000
```

然後打開 http://localhost:3000。第一次載入要抓全部數據，約 30 秒，之後一小時內都用快取。

金鑰放在專案根目錄的 `.env` (已被 .gitignore 排除)：

```
FRED_API_KEY=...
GEMINI_API_KEY=...
```

## 架構

```
api/                   後端 API (FastAPI)
├── main.py            路由：/api/dashboard、/api/ai、/api/refresh + 一小時快取
└── payload.py         把計算結果轉成前端用的 JSON
holly/                 計算核心 (純 Python，不依賴任何畫面框架)
├── config.py          數據代號 (FRED / Yahoo)、常數、讀取金鑰
├── data.py            數據層：抓 FRED、yfinance、新聞 RSS
├── indicators.py      指標層：對齊交易日、衍生指標、PR 百分位
├── signals.py         訊號層：台股健康度、四大抄底信號、體制機率
├── verdict.py         今日結論：進攻 / 中性 / 防守、行動建議、一句話總結 (header / footer)
├── news.py            新聞時事：關鍵字分主題、標出連動指標、去除重複報導
├── ai_advisor.py      AI 層：組提示詞、呼叫 Gemini、失敗時保底
└── catalog.py         ⭐ 所有指標卡片的標題、說明、門檻線 (新增卡片只改這裡)
web/                   前端 (Next.js App Router)
├── app/page.tsx       首頁：外框立即顯示，數據區用 <Suspense> 串流
├── app/api/*          轉發 AI / 重新抓取 請求到 Python 後端
├── components/        Hero (今日狀態 + 新聞)、Footer (一句話結論)、指標卡片、走勢圖、
│                      Parallax (視差 + 捲動浮現，尊重系統「減少動態效果」設定)
└── lib/               型別、格式化、後端呼叫
tests/                 後端離線測試 (模擬數據，不需網路與金鑰)
```

資料流：`data → indicators → signals → api/payload → Next.js`

## 雙分數的研究依據 (2026-10)

用 2016～2026 的數據回測，衡量方式是「分數」與「台股未來報酬 / 波動」的排序相關 (每週取樣)。
舊版健康度與台股未來 60 日報酬的相關只有 +0.03，所以改成以下兩個分數 (因子都換算成過去 3 年百分位後等權平均)：

| 分數 | 因子 | 回測結果 |
|---|---|---|
| 3 個月機會分數 | 垃圾債利差、VIX、淨流動性 13 週變化、美元 60 日變化 (反向)、10 年債 60 日變化 (反向)、銅價 60 日變化、融資餘額 20 日變化、景氣領先指標 3 個月變化、外銷訂單年增率 | 對未來 60 日報酬：6 因子全期 +0.41、2022～26 +0.49；加入 3 個台股因子後全期 +0.48 |
| 風險溫度 | VIX、垃圾債利差與 20 日變化、台幣 20 日變化、台股距一年高點、10 年債 60 日變化、外資台指期淨空單、外資 20 日賣超 | 對未來 20 日實際波動：2019～26 +0.36、2022～26 +0.47 |

測試過但**沒有**放進分數的台股指標 (方向不穩或幾乎無關)：外資買賣超對未來 3 個月報酬、投信買賣超、景氣燈號分數、本益比。
它們仍以「台股籌碼與景氣」卡片呈現，用來解釋現況。

限制：2022～2026 只有約 20 段互不重疊的 3 個月，機會分數的相關 95% 信賴區間約 +0.05～+0.76；
台股因子是從 14 個候選中挑出，有選擇偏誤。分數代表「機率偏向」，不是保證。

## 測試

```bash
.venv/bin/python -m pytest tests     # 後端
cd web && npx tsc --noEmit && npm run lint && npm run build   # 前端
```

## 部署 (Render)

`render.yaml` 會一次建立兩個服務：`finance-holly-api` (Python) 與 `finance-holly-web` (Next.js)。

1. 把專案推到 GitHub (`.env` 已被排除，金鑰不會上傳)
2. Render 後台 → **New → Blueprint** → 選這個倉庫 → 依提示貼上 `FRED_API_KEY`、`GEMINI_API_KEY`
3. `API_URL` 填後端網址 (例如 `https://finance-holly-api.onrender.com`，以 Render 顯示的為準)
4. 部署完成後打開 `finance-holly-web` 的網址即可分享

公開網站的保護：AI 解析每次數據更新只產生一次、所有訪客共用；「強制重新抓取」有 10 分鐘冷卻。

免費方案閒置 15 分鐘會休眠，第一位訪客約需等 1 分鐘喚醒 + 30 秒抓數據。
