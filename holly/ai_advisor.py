"""AI 層：把量化結果與新聞頭條整理成提示詞，交給 Gemini 產生解盤。"""
import json

from google import genai
from google.genai import types

from . import budget
from .config import GEMINI_MODELS
from .data import fetch_headlines
from .signals import pr_matrix

PROB_KEYS = ("Forecast_Prob_Low_Vol", "Forecast_Prob_High_Vol", "Forecast_Prob_Black_Swan")

PROMPT_TEMPLATE = """
你是一位擁有 30 年經驗的總經與台股研究員，讀者是「長期持有、會調整比重」的一般投資人，請用白話繁體中文。
【輸出要求】
1. 只輸出下面格式的 JSON，字串內不要換行，不要輸出 HTML。
2. 解讀必須與下方【量化系統今日結論】的方向一致；若你判斷不同，要明確說明理由，不可自相矛盾。
3. 每個數字的方向請依括號內的說明解讀，不要自行反過來 (例如台幣動能為正 = 台幣貶值 = 外資流出)。
4. allocation 五個整數加總必須等於 100，依今日局勢自行決定，防守時現金與債券比重應提高。
5. news_impacts 挑 2~4 則「最可能影響台股」的新聞 (用新聞編號標示 sources)，不要編造新聞裡沒有的事實：
   - short_term 為 1~4 週內可能的影響；long_term 為 3~12 個月的影響
   - affected 列出受影響的資產 (個別產業、指數、匯率或債券)，direction 用 up / down / mixed，range 寫預期波動幅度 (例如「±3~5%」)
   - priced_in 用「已反映 / 部分反映 / 尚未反映」開頭，並說明判斷依據 (例如股價已先漲、或市場還沒討論)
   - allocation 是可以考慮的配置調整方向；invalidation 是讓這個判斷失效的具體條件
{
  "phase": "<當前經濟階段與今日主要驅動，2~3 句；流動性急縮時務必警告>",
  "liquidity": "<聯準會淨流動性、VIX 與台幣的短線解讀，2 句>",
  "news_impacts": [{"event": "<事件，20 字內>", "sources": [<新聞編號>], "short_term": "<短期影響>", "long_term": "<長期影響>",
                    "affected": [{"asset": "<資產>", "direction": "<up|down|mixed>", "range": "<預期波動幅度>"}],
                    "priced_in": "<已反映 / 部分反映 / 尚未反映：理由>", "allocation": "<配置方向>", "invalidation": "<失效條件>"}],
  "playbook": "<未來一到兩週的操作劇本，2~3 句>",
  "tech_hotspots": "<科技股熱點 (AI、CPO、CoWoS 等) 的機會與風險，流動性吃緊時以防禦為主，2 句>",
  "allocation": {"twd_cash": <整數>, "usd_assets": <整數>, "cashflow": <整數>, "core_growth": <整數>, "tactical_hedge": <整數>},
  "allocation_reasons": {"twd_cash": "<一句理由>", "usd_assets": "<一句理由>", "cashflow": "<一句理由>", "core_growth": "<一句理由>", "tactical_hedge": "<一句理由>"}
}
"""


def _latest(df, col):
    s = df[col].dropna() if col in df.columns else None
    return s.iloc[-1] if s is not None and not s.empty else 0.0


def build_data_summary(df, pr, headlines, context=None):
    lines = [
        f"數據日期: {df.index[-1].strftime('%Y-%m-%d')}",
        f"- VIX 恐慌指數 PR: {pr.get('VIX_PR', 0):.1f} (越高越恐慌) | 巴菲特指標 PR: {pr.get('Buffett_PR', 50):.1f} (越高估值越貴)",
        f"- 聯準會淨流動性(4週動能): {_latest(df, 'Liquidity_ROC_4W'):+.2f}% (正=放水，負=抽水)",
        f"- 外資生死線(美元兌台幣5日變化): {_latest(df, 'USDTWD_ROC_5D'):+.2f}% (正=台幣貶值、外資流出；負=台幣升值、熱錢流入)",
        f"- 信用利差動態(5日變化): {_latest(df, 'HY_Spread_Chg_5D'):+.2f} 個百分點 (正=信用收緊，利空)",
        f"- 選擇權情緒(VIX距月線乖離): {_latest(df, 'VIX_Dev_20D'):+.2f}% (正=恐慌升溫)",
    ]
    if "Forecast_5D_TAIEX_Low" in pr:
        lines.append(f"- 台股加權 5 日 VIX 隱含區間: {pr['Forecast_5D_TAIEX_Low']:,.0f} ~ {pr['Forecast_5D_TAIEX_High']:,.0f}")
    if context:
        v = context.get("verdict") or {}
        if v:
            lines += ["", f"【量化系統今日結論】{v.get('label')}：{v.get('headline')}"]
            lines += [f"- {d['text']}" for d in v.get("drivers", [])]
        s = context.get("scores")
        if s:
            lines.append(f"- 3 個月機會分數 {s['opportunity']} / 100 (≥55 加碼、<35 減碼)；風險溫度 {s['risk']} / 100 (越高越動盪)")
            if s.get("odds"):
                lines.append(f"- 歷史上類似分數，3 個月後台股上漲機率 {s['odds']['upProb']}% (平常 {s['odds']['baseUpProb']}%)")
        notes = context.get("macro") or []
        if notes:
            lines += ["", "【FRED 總經觀察】"] + [f"- {n['topic']}：{n['zh']}" for n in notes]
    if headlines:
        lines += ["", "[今日新聞 (台股與全球財經)]"] + [f"{i}. {t}" for i, t in enumerate(headlines, 1)]
    else:
        lines += ["", "[今日國際新聞] 暫時無法取得，請純依據量化數據解盤。"]
    return "\n".join(lines)


def valid_impacts(items, n_headlines):
    """只保留有對應到真實新聞編號的影響分析 (避免 AI 憑空編事件)"""
    out = []
    for it in items or []:
        if not isinstance(it, dict) or not it.get("event"):
            continue
        try:
            sources = sorted({int(x) for x in it.get("sources") or [] if 1 <= int(x) <= n_headlines})
        except (TypeError, ValueError):
            continue
        if sources:
            affected = [a for a in it.get("affected") or [] if isinstance(a, dict) and a.get("asset")]
            out.append({**it, "sources": sources, "affected": affected})
    return out[:4]


def generate_ai_summary(df, api_key, context=None, news=()):
    """news：頁面上的重點新聞 [{title, link, ...}]，和英文頭條一起編號給 AI。"""
    """回傳 AI 解盤 dict。失敗時仍保留 Python 算出的機率，並附上 error 欄位。"""
    pr = pr_matrix(df)
    result = {
        "Forecast_Prob_Low_Vol": pr.get("Forecast_Prob_Low_Vol", 60.0),
        "Forecast_Prob_High_Vol": pr.get("Forecast_Prob_High_Vol", 30.0),
        "Forecast_Prob_Black_Swan": pr.get("Forecast_Prob_Black_Swan", 10.0),
    }
    if not api_key:
        result["error"] = "請在 .env 設定 GEMINI_API_KEY"
        return result

    sources = [{"title": n["title"], "link": n.get("link")} for n in news][:10]
    sources += [{"title": t, "link": None} for t in fetch_headlines()]
    contents = PROMPT_TEMPLATE + "\n\n" + build_data_summary(df, pr, [x["title"] for x in sources], context)
    try:
        ai_json, model = ask_gemini_json(contents, api_key)
    except RuntimeError as e:
        result["error"] = str(e)
        return result
    ai_json["news_impacts"] = valid_impacts(ai_json.get("news_impacts"), len(sources))
    # AI 的文字覆蓋預設提示，但機率永遠以 Python 量化矩陣為準
    return {**result, **ai_json, **{k: result[k] for k in PROB_KEYS}, "sources": sources, "model": model}


def ask_gemini_json(prompt, api_key, temperature=0.1):
    """呼叫 Gemini 並要求回傳 JSON 物件；強的模型忙線 / 額度用完時自動改用下一個。
    成功回傳 (dict, 模型名稱)，全部失敗則丟出 RuntimeError。"""
    # client 必須用變數持有：若寫成 genai.Client(...).models.generate_content(...)，
    # client 會在請求送出前被回收並關閉連線 ("client has been closed")
    client = genai.Client(api_key=api_key)
    errors = []
    for model in GEMINI_MODELS:
        if not budget.gemini.take():
            errors.append("本站 AI 用量保護中 (每分鐘 6 次 / 每天 150 次)，請稍後再試")
            break
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=temperature),
            )
            data = json.loads((response.text or "").strip() or "{}")
            if not isinstance(data, dict):
                raise ValueError("AI 回傳格式不是 JSON 物件")
            return data, model
        except Exception as e:
            errors.append(f"{model}: {str(e)[:120]}")
    raise RuntimeError("AI 暫時無法連線，所有模型都失敗：" + "；".join(errors))
