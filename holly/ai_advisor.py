"""AI 層：把量化結果與新聞頭條整理成提示詞，交給 Gemini 產生解盤。"""
import json

from google import genai
from google.genai import types

from .config import GEMINI_MODELS
from .data import fetch_headlines
from .signals import pr_matrix

PROB_KEYS = ("Forecast_Prob_Low_Vol", "Forecast_Prob_High_Vol", "Forecast_Prob_Black_Swan")

PROMPT_TEMPLATE = """
你是一位擁有 30 年經驗的總經量化投資大師。請為穩健型高階半導體產業客戶規劃資產配置。
【🚨 輸出要求】
1. 只輸出下面格式的 JSON，Value 內【絕對禁止】真實換行符號。
2. 解讀必須與下方【量化系統今日結論】的方向一致；若你判斷不同，要明確說明理由，不可自相矛盾。
3. 每個數字的方向請依括號內的說明解讀，不要自行反過來 (例如台幣動能為正 = 台幣貶值 = 外資流出)。
4. allocation_recommendation 五個整數加總必須等於 100，依今日局勢自行決定，防守時現金與債券比重應提高。
{
    "macro_phase_insight": "【當前經濟階段與今日驅動】(請綜合評估通膨、聯準會淨流動性動能、台幣匯率與今日新聞給出大方向。若流動性急縮，務必提出警告)",
    "broadcast": "<h4 style='color:#0044CC; margin-bottom: 5px;'>🏦 總經定調</h4><ul style='line-height: 1.8; margin-top: 0;'><li><b>聯準會水龍頭與籌碼：</b>(解讀聯準會淨流動性4週動能，判斷是偷偷放水還是抽銀根，並結合VIX與台幣給出短線警示)</li></ul>",
    "allocation_recommendation": {"twd_cash": <整數>, "usd_assets": <整數>, "cashflow": <整數>, "core_growth": <整數>, "tactical_hedge": <整數>},
    "allocation_reasons": {"twd_cash": "<一句理由>", "usd_assets": "<一句理由，例如美債/公司債>", "cashflow": "<一句理由，例如 00937B 月配息>", "core_growth": "<一句理由，例如核心持股>", "tactical_hedge": "<一句理由，例如黃金或 AI 強勢股短打>"},
    "market_insights_html": "<div><h4 style='color: #0284C7;'>🔄 未來一週操作劇本</h4><p>(分析高頻指標與流動性抽水/放水的應對)</p><h4 style='color: #F59E0B;'>🔥 科技股熱點</h4><p>(帶入 AI、矽光子CPO、CoWoS，但若流動性吃緊則強烈建議防禦)</p></div>"
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
        lines += ["", "[今日華爾街/全球財經頭條]"] + [f"{i}. {t}" for i, t in enumerate(headlines, 1)]
    else:
        lines += ["", "[今日國際新聞] 暫時無法取得，請純依據量化數據解盤。"]
    return "\n".join(lines)


def generate_ai_summary(df, api_key, context=None):
    """回傳 AI 解盤 dict。失敗時仍保留 Python 算出的機率，並附上 error 欄位。"""
    pr = pr_matrix(df)
    result = {
        "Forecast_Prob_Low_Vol": pr.get("Forecast_Prob_Low_Vol", 60.0),
        "Forecast_Prob_High_Vol": pr.get("Forecast_Prob_High_Vol", 30.0),
        "Forecast_Prob_Black_Swan": pr.get("Forecast_Prob_Black_Swan", 10.0),
        "macro_phase_insight": "尚未取得 AI 總經觀測，請點擊重新解讀或檢查 API。",
        "broadcast": "💡 系統提示：AI 模組連線超時或 API 錯誤。但高頻戰術機率與指標已透過 Python 量化矩陣計算完成，請參考下方數值。",
    }
    if not api_key:
        result["error"] = "請在 .env 設定 GEMINI_API_KEY"
        return result

    contents = PROMPT_TEMPLATE + "\n\n" + build_data_summary(df, pr, fetch_headlines(), context)
    try:
        ai_json, model = ask_gemini_json(contents, api_key)
    except RuntimeError as e:
        result["error"] = str(e)
        return result
    # AI 的文字覆蓋預設提示，但機率永遠以 Python 量化矩陣為準
    return {**result, **ai_json, **{k: result[k] for k in PROB_KEYS}, "model": model}


def ask_gemini_json(prompt, api_key, temperature=0.1):
    """呼叫 Gemini 並要求回傳 JSON 物件；強的模型忙線 / 額度用完時自動改用下一個。
    成功回傳 (dict, 模型名稱)，全部失敗則丟出 RuntimeError。"""
    # client 必須用變數持有：若寫成 genai.Client(...).models.generate_content(...)，
    # client 會在請求送出前被回收並關閉連線 ("client has been closed")
    client = genai.Client(api_key=api_key)
    errors = []
    for model in GEMINI_MODELS:
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
