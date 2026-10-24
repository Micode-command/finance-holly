"""所有指標卡片的「內容設定」。要新增 / 調整卡片只需改這個檔案。

這裡只描述內容 (標題、說明、門檻線、格式)，不含任何畫面程式碼，
由 api/ 轉成 JSON 給前端使用。
"""
from dataclasses import dataclass, field
from typing import Callable, Optional

import pandas as pd


@dataclass
class CardSpec:
    column: str
    title: str
    desc: dict                          # explain(...) 或 tip(...) 的結果
    pr_type: str = "C"                  # "C" 週期型 / "G" 成長型
    range: str = "1Y"                   # 預設圖表區間：3M / 1Y / 3Y
    invert_color: bool = False          # 數值上升是壞事時設 True
    invert_pr: bool = False             # PR 反轉 (例如殖利率曲線：越低越危險)
    is_macro: bool = False              # 週 / 月 / 季資料
    decimals: int = 2
    signed: bool = False                # 數值前顯示 +/-
    prefix: str = ""
    suffix: str = ""
    ref_lines: list = field(default_factory=list)   # [(數值, 說明)] 圖上的門檻線
    note: Optional[Callable] = None     # (dataset) -> str，動態補充說明
    change: Optional[str] = None        # 強制指定變化的算法："abs" 增減量 / "pct" 漲跌 %
    pr_neutral: bool = False            # 歷史位階只標「極高～極低」，不暗示好壞 (買賣超、成長率這類)

    @property
    def change_mode(self):
        """利率、百分比、買賣超類看「增減多少」，價格類看「漲跌幾 %」。"""
        # 買賣超金額、口數會在正負之間跳動，算「漲跌 %」沒有意義，也看增減量
        if self.change:
            return self.change
        return "abs" if any(u in self.suffix for u in ("%", "百分點", "億", "口", "分")) else "pct"


@dataclass
class Section:
    title: str
    cards: list
    intro: str = ""
    nav: str = ""                       # 頁面導覽列的短名稱


def explain(formula, threshold, impact, threshold_label="閾值"):
    return {"kind": "explain", "formula": formula, "threshold": threshold, "impact": impact,
            "thresholdLabel": threshold_label}


def tip(summary, hint):
    return {"kind": "tip", "summary": summary, "hint": hint}


def _latest_flow_note(dataset):
    v = dataset.latest("TW_Foreign_Net")
    return None if v is None else f"最新一日外資 {'買超' if v >= 0 else '賣超'} {abs(v):,.0f} 億"


def _margin_note(dataset):
    v = dataset.latest("TW_Margin")
    return None if v is None else f"融資餘額 {v:,.0f} 億"


def _monthly_note(column):
    def note(dataset):
        d = dataset.last_date(column)
        return None if d is None else f"{(d - pd.DateOffset(months=2)):%Y 年 %-m 月}的數據 (公布後才採用)"
    return note


NDC_LIGHTS = [(38, "紅燈 (景氣過熱)"), (32, "黃紅燈 (轉熱)"), (23, "綠燈 (穩定)"), (17, "黃藍燈 (轉弱)"), (0, "藍燈 (低迷)")]


def _ndc_note(dataset):
    v = dataset.latest("TW_NDC_Score")
    if v is None:
        return None
    light = next(name for floor, name in NDC_LIGHTS if v >= floor)
    return f"{light} · " + (_monthly_note("TW_NDC_Score")(dataset) or "")


def _sahm_note(dataset):
    value = dataset.latest("Sahm_Indicator")
    if value is None:
        return None
    distance = 0.5 - value
    return f"距離觸發還差 {distance:.2f} 個百分點" if distance > 0 else "🚨 已觸發衰退訊號"


SECTIONS = [
    Section("⚡ 戰術雷達：高頻微觀與籌碼動能", nav="戰術雷達", intro="一週變盤雷達：最快反應資金與情緒的短線指標。", cards=[
        CardSpec("USDTWD_ROC_5D", "台幣 5 日動能 (外資生死線)",
                 tip("外資匯出匯入的超短期溫度計。", "大於 +0.5% (台幣急貶) 代表外資正在瘋狂撤資逃命；小於 -0.5% 代表熱錢湧入台灣準備炒股。"),
                 range="3M", invert_color=True, signed=True, suffix="%", ref_lines=[(0.5, "+0.5% 外資撤離"), (-0.5, "-0.5% 熱錢湧入")]),
        CardSpec("HY_Spread_Chg_5D", "垃圾債利差 5 日變化",
                 tip("華爾街銀行借錢意願的短期指標。", "數字大於0 (正數) 代表銀行在雨天收傘，體質差的公司借不到錢，股市隨時有連環爆雷風險。"),
                 range="3M", invert_color=True, signed=True, suffix=" 個百分點", ref_lines=[(0, "0")]),
        CardSpec("VIX_Dev_20D", "VIX 距月線乖離 (情緒偏斜)",
                 tip("短期恐慌與貪婪的極端值。", "大於 +15% 代表市場嚇壞了(通常是短線買點)；小於 -15% 代表大家過度樂觀，準備要被割韭菜了。"),
                 range="3M", invert_color=True, signed=True, decimals=1, suffix="%", ref_lines=[(15, "+15% 恐慌"), (-15, "-15% 過度樂觀")]),
    ]),
    Section("🚰 聯準會真實資金水位 (Net Liquidity)", nav="資金水位", intro="華爾街不看本益比，只看『印鈔機』。美股的漲跌趨勢，高度貼合聯準會與財政部釋放的【淨流動性】。", cards=[
        CardSpec("Total_Assets_T", "聯準會總資產 (QT/QE)",
                 explain("Fed 釋放的基礎貨幣總量。", "上升=印鈔(QE)；下降=縮表抽資金(QT)。", "若持續下降，代表長線資金正在被抽乾，風險資產的估值天花板會被無情壓抑。", "趨勢"),
                 suffix=" 兆", is_macro=True),
        CardSpec("TGA_Account_T", "財政部 TGA 帳戶",
                 explain("美國政府的國庫支票簿。", "下降=政府花錢(注資)；上升=抽稅發債(吸血)。", "當 TGA 快速飆高時，市場上的游資會被瞬間吸乾，通常伴隨美股短線急跌。", "趨勢"),
                 invert_color=True, suffix=" 兆", is_macro=True),
        CardSpec("Net_Liquidity_T", "市場淨流動性 (美股動能)",
                 explain("總資產 - TGA - ON RRP。", "美股大盤(SPY)的真正地心引力。", "當淨流動性強勢擴張，閉著眼睛買都會漲；當淨流動性萎縮，基本面再好都會面臨估值下修。", "趨勢"),
                 suffix=" 兆"),
    ]),
    Section("🔥 賽道擁擠度與泡沫雷達", nav="半導體擁擠", intro="半導體過熱警報：資金是否過度集中在單一賽道。", cards=[
        CardSpec("SMH_Dev_200D", "半導體 200 日乖離 (散戶 FOMO 指標)",
                 tip("衡量晶片股是否漲到脫離基本面。", "當乖離率大於 +30%，代表散戶已經陷入 FOMO 瘋狂追高，隨時可能觸發『達康泡沫』等級的殺盤；小於 -15% 才是長線無腦買點。"),
                 pr_type="G", invert_color=True, signed=True, decimals=1, suffix="%", ref_lines=[(30, "+30% 過熱"), (-15, "-15% 長線買點")]),
        CardSpec("SMH_Relative_Strength", "半導體資金虹吸度 (SMH/SPY 相對強度)",
                 tip("衡量半導體是否吸乾了全市場的錢。", "當這個數值急速飆破 +10%，代表全市場的錢像被『黑洞』吸走一樣只炒半導體。這是不健康的單腳跳，通常是大戶準備『獲利了結、資金撤退』的最後警告。"),
                 pr_type="G", invert_color=True, signed=True, decimals=1, suffix="%", ref_lines=[(10, "+10% 單腳跳")]),
    ]),
    Section("🛡️ 第一道防線：美股大盤與板塊", nav="美股大盤", cards=[
        CardSpec("SPY", "標普500 (SPY)", explain("美國 500 大企業加權。", "長線必向上。G-120PR > 90 中期過熱，G-200PR > 90 歷史泡沫。", "全球資產定價基準，跌破月線代表大資金撤退。"), pr_type="G", prefix="$"),
        CardSpec("QQQ", "那斯達克100 (QQQ)", explain("科技巨頭(含蘋果、輝達)。", "波動較 SPY 大，PR > 90 極度擁擠。", "台股電子股的親大哥，它破底台灣必遭外資無情提款。"), pr_type="G", prefix="$"),
        CardSpec("IWM", "羅素2000 (IWM)", explain("美國中小型企業。", "受內需與利率影響最深。", "大盤創高但它破底，代表高利率正壓垮底層經濟，屬於嚴重背離警報。"), pr_type="G", prefix="$"),
        CardSpec("XLP", "必需消費板塊 (XLP)", explain("民生必需品(牙膏/衛生紙)。", "平時漲幅小。", "科技股大跌但它逆勢漲，代表大戶沒把錢抽離股市，而是躲來這裡保命。"), pr_type="G", prefix="$"),
    ]),
    Section("🇹🇼 補充防線：台股風向球", nav="台股風向", cards=[
        CardSpec("TAIEX", "台灣加權指數 (TAIEX)", explain("台股上市公司市值加權。", "G-200PR > 90 代表歷史級過熱。", "台積電權重極高，與費半、台幣匯率高度同步。"), pr_type="G", decimals=0),
        CardSpec("SOX", "費城半導體 (SOX)", explain("全球半導體霸主集合。", "景氣循環極強，G-200PR < 10 必是歷史大底。", "與台積電連動度 >90%，直接決定台股明天的漲跌生死。"), pr_type="G", decimals=0),
        CardSpec("Copper", "銅博士期貨", explain("全球工業金屬之母。", "長線受基建與 AI 需求推動。", "銅價大漲代表實體經濟(拉貨)熱絡；暴跌暗示全球需求萎縮。"), pr_type="G", prefix="$"),
        CardSpec("USDTWD", "美元兌台幣", explain("台幣匯率。", "C-PR > 80 台幣嚴重貶值。", "向上(貶值)代表外資賣台股匯出；向下(升值)代表熱錢湧入買台股。"), invert_color=True),
    ]),
    Section("🇹🇼 台股籌碼與景氣", nav="台股籌碼", intro="外資、投信、散戶 (融資) 怎麼在買賣，以及台灣的景氣與出口接單。★ = 回測證實有用，已放進雙分數；其餘只用來解釋現況。", cards=[
        CardSpec("TW_Foreign_Net_20D", "外資 20 日累計買賣超",
                 tip("外資近 20 個交易日合計買 (+) 或賣 (−) 了多少台股。", "★ 已放進風險溫度：外資連續大賣時，台股接下來通常比較震盪。但回測 10 年發現，它「無法預測」3 個月後是漲是跌 (有時繼續跌、有時馬上反彈)，所以不放進機會分數。"),
                 signed=True, decimals=0, suffix=" 億", ref_lines=[(0, "0")], note=_latest_flow_note, pr_neutral=True),
        CardSpec("TW_Fut_Foreign_OI", "外資台指期淨未平倉",
                 tip("外資在台指期貨「多單 − 空單」的口數，負數 = 淨空單。", "★ 已放進風險溫度：外資用期貨放空越多，台股接下來越容易大幅震盪。常被視為外資看法的領先指標，但同樣無法單獨預測 3 個月方向。"),
                 signed=True, decimals=0, suffix=" 口", ref_lines=[(0, "0")], pr_neutral=True),
        CardSpec("TW_Margin_Chg20", "融資餘額 20 日變化",
                 tip("散戶借錢買股 (融資) 的總額，近 20 個交易日增減幾 %。", "★ 已放進機會分數：回測顯示融資增加時，3 個月後台股反而偏多 (代表市場動能與信心在升溫)；融資快速大減常是斷頭賣壓。"),
                 signed=True, decimals=1, suffix="%", ref_lines=[(0, "0")], note=_margin_note, pr_neutral=True),
        CardSpec("TW_Trust_Net_20D", "投信 20 日累計買賣超",
                 tip("國內基金公司 (投信) 近 20 個交易日合計買賣超。", "只解釋現況：季底常有「作帳行情」。回測時方向不穩定，不放進分數。"),
                 signed=True, decimals=0, suffix=" 億", ref_lines=[(0, "0")], pr_neutral=True),
        CardSpec("TW_NDC_Score", "國發會景氣對策信號",
                 explain("9 項景氣指標加總的分數 (9～45 分)，對應五種燈號。", "≥38 紅燈過熱、32～37 黃紅燈、23～31 綠燈、17～22 黃藍燈、≤16 藍燈。", "反映「現在」景氣冷熱。回測發現燈號本身對 3 個月後台股幫助不大，紅燈時股市常已經漲了一大段。"),
                 range="3Y", decimals=0, suffix=" 分", is_macro=True, ref_lines=[(38, "38 紅燈"), (23, "23 綠燈")], note=_ndc_note),
        CardSpec("TW_NDC_Leading_Chg3", "景氣領先指標 3 個月變化",
                 explain("國發會領先指標 (不含趨勢) 最近 3 個月的變化。", "正數 = 未來景氣轉好，負數 = 轉弱。", "★ 已放進機會分數：回測與台股 3 個月後報酬相關約 +0.27，是台灣景氣數據中最有預測力的。"),
                 range="3Y", signed=True, decimals=2, is_macro=True, ref_lines=[(0, "0")], note=_monthly_note("TW_NDC_Leading_Chg3"), change="abs", pr_neutral=True),
        CardSpec("TW_Export_YoY", "外銷訂單年增率",
                 explain("台灣廠商接到的海外訂單金額，比去年同月成長幾 %。", "正數 = 接單成長，> 20% 屬於強勁。", "★ 已放進機會分數：接單領先實際出貨 1～3 個月，電子股獲利跟著走。"),
                 range="3Y", signed=True, decimals=1, suffix="%", is_macro=True, ref_lines=[(0, "0")], note=_monthly_note("TW_Export_YoY"), pr_neutral=True),
        CardSpec("TW_PE_TSMC", "台積電本益比",
                 explain("台積電股價 ÷ 近四季每股盈餘，代表買一塊錢的獲利要付幾塊錢。", "看歷史位階：越高 = 越貴。", "台積電占台股市值四成以上，它貴不貴幾乎等於大盤貴不貴。回測無法預測 3 個月方向，只當估值參考。"),
                 decimals=1, suffix=" 倍"),
    ]),
    Section("💣 第二/三道防線：黑天鵝與匯率戰", nav="黑天鵝", cards=[
        CardSpec("VIX", "恐慌指數 (VIX)", explain("選擇權市場避險保費。", ">20 警戒，>30 股災，<13 提防樂極生悲。", "與 SPY 完全反向，C-PR > 95 是極端恐慌的逆勢買點。"), invert_color=True, ref_lines=[(20, "20 警戒"), (30, "30 股災")]),
        CardSpec("High_Yield_Spread", "垃圾債利差", explain("垃圾債減去無風險美債利息。", ">5% 亮黃燈，>8% 企業連環倒閉。", "飆高代表銀行抽銀根，股市必暴跌，應立刻轉入現金與長債。"), invert_color=True, suffix="%", ref_lines=[(5, "5% 黃燈")]),
        CardSpec("DXY", "美元指數 (DXY)", explain("美元對全球貨幣強弱。", ">105 強勢美元警報。", "強美元會吸乾新興市場(台灣)資金引發雙殺；弱美元則有利資金外溢推升亞股。"), invert_color=True, ref_lines=[(105, "105 強勢美元")]),
        CardSpec("DGS30", "30年期美債殖利率", explain("長線通膨與成長預期。", "飆破 4.5% 會引發拋售潮。", "無風險利率太香，大資金會賣股買債，對科技股估值產生毀滅性打擊。"), invert_color=True, suffix="%", ref_lines=[(4.5, "4.5%")]),
    ]),
    Section("🛢️ 第四道防線：通膨與泡沫", nav="通膨泡沫", cards=[
        CardSpec("Brent", "布倫特原油", explain("全球油價基準。", "突破 $90 即點燃通膨死灰。", "油價居高不下，聯準會就不敢降息，股市資金動能將嚴重受限。"), invert_color=True, prefix="$", ref_lines=[(90, "$90")]),
        CardSpec("Gold", "黃金期貨", explain("終極保命資產。", "創歷史新高代表信用體系動搖。", "股跌金漲=躲避災難；股金齊漲=市場預期鈔票將大幅貶值(通膨)。"), pr_type="G", prefix="$", decimals=0),
        CardSpec("CPI_YoY", "廣義 CPI 年增率", explain("官方整體物價漲幅。", "聯準會 KPI 是 2%，大於 3% 即拉警報。", "只要卡在 3% 以上，降息預期就會落空，長天期美債將面臨拋售壓力。"), range="3Y", invert_color=True, suffix="%", is_macro=True, ref_lines=[(2, "2% 目標"), (3, "3% 警報")]),
        CardSpec("Buffett", "巴菲特指標", explain("非金融企業股權市值 / GDP (Fed Z.1 季資料)。", "看 C-PR 位階比絕對數值準，PR > 90 代表歷史級高估。", "雖不代表馬上崩盤，但處於深紅極端位階時，應嚴格控制股票倉位水位。"), range="3Y", invert_color=True, decimals=0, suffix="%", is_macro=True),
    ]),
    Section("🏦 第五道防線：聯準會底層水箱", nav="Fed 水箱", cards=[
        CardSpec("Reserves_T", "銀行準備金", explain("聯準會放在銀行的閒錢。", "低於 3 兆美元代表活水枯竭。", "錢越多股市越漲；下滑趨勢確立時，美股將面臨估值下修壓力。"), suffix=" 兆", is_macro=True, ref_lines=[(3, "3 兆")]),
        CardSpec("RRP_T", "ON RRP 備用金", explain("停泊在聯準會的超額現金。", "歸零即失去流動性保護傘。", "減少代表錢被拿去買美債了；若數字見底，股市震盪將變得極度劇烈。"), suffix=" 兆", decimals=3, change="abs"),
        CardSpec("Liquidity_Spread", "短期資金吃緊度", explain("SOFR 減去 基準利率。", "翻正(>0)即爆發資金荒。", "代表華爾街連借錢過夜都有困難，隨時可能爆發如 2019 年 9 月附買回市場的資金荒。"), invert_color=True, signed=True, suffix="%", ref_lines=[(0, "0 資金荒")]),
        CardSpec("Yield_Curve", "長短債利差", explain("10年期 減 2年期國債利率。", "常態為正，倒掛(負數)是警報。", "真正恐怖的是「解除倒掛、由負翻正」的那一刻，通常宣告實質大股災到來。"), range="3Y", signed=True, suffix="%", invert_pr=True, ref_lines=[(0, "0 倒掛線")]),
    ]),
    Section("🏭 終極防線：實體經濟衰退雷達", nav="衰退雷達", cards=[
        CardSpec("Unemployment_Rate", "美國失業率", explain("勞動市場健康度。", "形成明顯上升趨勢即不妙。", "一旦狂飆，代表民眾無力消費，此時就算降息也救不回獲利衰退的殺盤。"), range="3Y", invert_color=True, suffix="%", is_macro=True),
        CardSpec("Sahm_Indicator", "薩姆衰退指標", explain("失業率3個月均值與前低比較。", "> 0.5 個百分點即宣告衰退。", "歷史上觸發後幾乎都伴隨正式衰退，是最可靠的就業警報。"), range="3Y", invert_color=True, suffix=" 個百分點", is_macro=True, ref_lines=[(0.5, "0.5 觸發")], note=_sahm_note),
        CardSpec("Core_PCE_YoY", "核心 PCE 年增率", explain("扣除能源食物的真實通膨。", "黏性極強，降至 2% 才安全。", "聯準會決策的唯一核心，此數值不降，大資金就不敢定價寬鬆週期。"), range="3Y", invert_color=True, suffix="%", is_macro=True, ref_lines=[(2, "2% 目標")]),
    ]),
]


# 每張卡片對應的名詞 (id 對應 web/lib/glossary.ts)，卡片上的「白話解釋」會列出這些名詞
CARD_TERMS = {
    "USDTWD_ROC_5D": ["usdtwd", "foreign_investors"],
    "HY_Spread_Chg_5D": ["hy_spread"],
    "VIX_Dev_20D": ["vix", "ma_deviation"],
    "Total_Assets_T": ["fed_balance_sheet", "qe_qt"],
    "TGA_Account_T": ["tga"],
    "Net_Liquidity_T": ["net_liquidity", "tga", "on_rrp"],
    "SMH_Dev_200D": ["ma_deviation", "sox_smh"],
    "SMH_Relative_Strength": ["relative_strength", "sox_smh"],
    "SPY": ["us_etfs"], "QQQ": ["us_etfs"], "IWM": ["us_etfs"], "XLP": ["us_etfs"],
    "TAIEX": ["taiex"],
    "SOX": ["sox_smh"],
    "Copper": ["copper"],
    "USDTWD": ["usdtwd", "foreign_investors"],
    "VIX": ["vix"],
    "High_Yield_Spread": ["hy_spread"],
    "DXY": ["dxy"],
    "DGS30": ["treasury_yields"],
    "Brent": ["brent"],
    "Gold": ["gold"],
    "CPI_YoY": ["cpi"],
    "Buffett": ["buffett"],
    "Reserves_T": ["reserves"],
    "RRP_T": ["on_rrp"],
    "Liquidity_Spread": ["sofr", "iorb"],
    "Yield_Curve": ["yield_curve", "treasury_yields"],
    "Unemployment_Rate": ["unemployment"],
    "Sahm_Indicator": ["sahm", "unemployment"],
    "Core_PCE_YoY": ["pce", "cpi"],
    "TW_Foreign_Net_20D": ["institutional_flows", "foreign_investors"],
    "TW_Fut_Foreign_OI": ["futures_oi"],
    "TW_Margin_Chg20": ["margin"],
    "TW_Trust_Net_20D": ["institutional_flows"],
    "TW_NDC_Score": ["ndc_signal"],
    "TW_NDC_Leading_Chg3": ["leading_index"],
    "TW_Export_YoY": ["export_orders"],
    "TW_PE_TSMC": ["pe_ratio"],
}
