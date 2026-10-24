"""總經評語：根據 FRED 數據，用總體經濟學的觀點產生中英對照評語。純規則，不呼叫 AI。

每個主題回傳 0~1 則評語 (數據不足就略過)；前端每次開啟隨機挑幾則顯示。
"""
import pandas as pd


# 單位提醒：程式內金額以「十億美元 (B)」計算；中文的「億」= 0.1B，所以中文要 ×10


def _note(topic, tone, zh, en, metric):
    return {"topic": topic, "tone": tone, "zh": zh, "en": en, "metric": metric}


def _series(dataset, col):
    """原始公布點 (週 / 月資料不含 ffill 的重複值)"""
    if col not in dataset.df.columns:
        return None
    s = dataset.release_points(col)
    return s if len(s) >= 2 else None


def _usd_b(b):
    """十億美元格式：小於 10B 時保留一位小數，避免 0.2B 顯示成 $0B"""
    return f"${b:.1f}B" if abs(b) < 10 else f"${b:,.0f}B"


def _ago(s, days):
    target = s.index[-1] - pd.Timedelta(days=days)
    return None if target < s.index[0] else float(s.asof(target))


def balance_sheet(ds):
    s = _series(ds, "Total_Assets")  # 百萬美元
    if s is None:
        return None
    now, q = float(s.iloc[-1]), _ago(s, 91)
    if q is None:
        return None
    pace = (now - q) / 3 / 1000  # 每月增減 (十億美元)
    level = f"{now / 1e6:.2f} 兆"
    metric = {"label": "Fed 總資產", "value": f"{now / 1e6:.2f}T", "change": f"{pace:+.0f}B/月"}
    if pace > 50:
        return _note("QE / 印鈔", "good",
                     f"聯準會資產負債表近 3 個月每月擴張約 {pace * 10:,.0f} 億美元，規模 {level}美元 —— 這是明確的 QE / 大量印鈔，資金潮水上漲，風險資產最受惠。",
                     f"The Fed balance sheet has grown ~${pace:.0f}B per month over 3 months to ${now / 1e6:.2f}T — clear QE. Rising liquidity tides lift risk assets.", metric)
    if pace > 10:
        return _note("溫和擴表", "good",
                     f"Fed 資產負債表近 3 個月每月增加約 {pace * 10:,.0f} 億美元，屬溫和擴表 (準備金管理購債或緊急放款)，流動性小幅改善，但還稱不上大規模印鈔。",
                     f"The balance sheet is expanding modestly (~${pace:.0f}B/month), likely reserve-management purchases rather than full-blown QE. Liquidity is improving at the margin.", metric)
    if pace < -20:
        return _note("QT 縮表", "bad",
                     f"聯準會仍在 QT 縮表，近 3 個月每月抽走約 {-pace * 10:,.0f} 億美元，資產負債表降至 {level}美元。縮表等於反向印鈔，長期壓抑估值天花板。",
                     f"Quantitative tightening continues: the Fed is draining ~${-pace:.0f}B per month, shrinking its balance sheet to ${now / 1e6:.2f}T. QT is reverse money-printing and caps valuations over time.", metric)
    return _note("資產負債表持平", "neutral",
                 f"Fed 資產負債表近 3 個月幾乎持平 (每月 {pace * 10:+,.0f} 億美元)，QT 已放緩或結束、但也沒有重啟 QE；流動性方向改由 TGA 與 ON RRP 主導。",
                 f"The Fed balance sheet is roughly flat (~${pace:+.0f}B/month): QT has slowed or ended, but QE has not restarted. Liquidity direction now hinges on the TGA and ON RRP.", metric)


def on_rrp(ds):
    s = _series(ds, "ON_RRP")  # 百萬美元
    if s is None:
        return None
    now = float(s.iloc[-1]) / 1000  # 十億美元
    q = _ago(s, 91)
    metric = {"label": "ON RRP", "value": _usd_b(now), "change": None if q is None else f"{now - q / 1000:+.1f}B/3M"}
    if now < 100:
        return _note("ON RRP 見底", "bad",
                     f"隔夜逆回購 (ON RRP) 只剩 {now * 10:,.0f} 億美元，幾乎見底。2023 年起支撐美股的「備用水池」已經用完，之後 QT 或財政部發債都會直接抽走銀行準備金，市場對流動性衝擊更敏感。",
                     f"The ON RRP facility has dwindled to {_usd_b(now)} — essentially empty. The liquidity buffer that cushioned markets since 2023 is gone, so QT and Treasury issuance now drain bank reserves directly.", metric)
    if q is not None and now < q / 1000 * 0.7:
        return _note("ON RRP 釋放資金", "good",
                     f"ON RRP 從 3 個月前的 {q / 100:,.0f} 億美元降到 {now * 10:,.0f} 億美元。貨幣基金把停在 Fed 的錢拿去買國庫券，等於把資金放回市場，抵銷了部分 QT。",
                     f"ON RRP has fallen from ${q / 1000:.0f}B to ${now:.0f}B in 3 months. Money funds are redeploying cash into T-bills, releasing liquidity that offsets part of QT.", metric)
    return _note("ON RRP 仍有緩衝", "neutral",
                 f"ON RRP 仍有 {now * 10:,.0f} 億美元，代表市場上還有閒置資金可以吸收國債發行，短期流動性緩衝尚在。",
                 f"ON RRP still holds ${now:.0f}B of idle cash, leaving a buffer to absorb Treasury issuance in the near term.", metric)


def tga(ds):
    s = _series(ds, "TGA_Account")
    if s is None:
        return None
    now, m = float(s.iloc[-1]) / 1000, _ago(s, 28)
    if m is None:
        return None
    chg = now - m / 1000
    metric = {"label": "TGA", "value": f"${now:.0f}B", "change": f"{chg:+.0f}B/4W"}
    if chg > 100:
        return _note("財政部抽水", "bad",
                     f"財政部 TGA 帳戶 4 週增加 {chg * 10:,.0f} 億美元至 {now * 10:,.0f} 億美元：發債收錢的速度快於花錢，等於從市場抽走流動性，短線對股市不利。",
                     f"The Treasury General Account rose ${chg:.0f}B in 4 weeks to ${now:.0f}B. Issuance is outpacing spending, pulling liquidity out of markets — a near-term headwind for stocks.", metric)
    if chg < -100:
        return _note("財政部放水", "good",
                     f"財政部 TGA 帳戶 4 週減少 {-chg * 10:,.0f} 億美元，政府正在把錢花回經濟體，對市場流動性是隱形的放水。",
                     f"The TGA fell ${-chg:.0f}B in 4 weeks as the Treasury spends down its cash — a stealth liquidity injection for markets.", metric)
    return None


def net_liquidity(ds):
    s = ds.df["Net_Liquidity"].dropna() if "Net_Liquidity" in ds.df.columns else None
    if s is None or len(s) < 70:
        return None
    now, q = float(s.iloc[-1]), _ago(s, 91)
    chg = (now / q - 1) * 100
    metric = {"label": "淨流動性", "value": f"{now / 1e6:.2f}T", "change": f"{chg:+.1f}%/3M"}
    if chg > 2:
        zh = f"淨流動性 (Fed 資產 - TGA - ON RRP) 近 3 個月增加 {chg:.1f}%，資金面順風。歷史上淨流動性上升時，美股多半易漲難跌。"
        en = f"Net liquidity (Fed assets − TGA − ON RRP) is up {chg:.1f}% over 3 months — a tailwind. Historically, equities tend to grind higher when net liquidity rises."
        return _note("淨流動性擴張", "good", zh, en, metric)
    if chg < -2:
        zh = f"淨流動性近 3 個月減少 {-chg:.1f}%，市場資金在退潮。基本面再好，估值也容易被壓縮，追高要特別謹慎。"
        en = f"Net liquidity has contracted {-chg:.1f}% over 3 months. With the tide going out, valuations tend to compress regardless of fundamentals."
        return _note("淨流動性收縮", "bad", zh, en, metric)
    return _note("淨流動性持平", "neutral",
                 f"淨流動性 3 個月變化 {chg:+.1f}%，資金面中性，股市方向較取決於企業獲利與利率。",
                 f"Net liquidity is roughly flat ({chg:+.1f}% over 3 months), so equity direction depends more on earnings and rates than on liquidity.", metric)


def reserves(ds):
    s = _series(ds, "Reserve_Balances")
    if s is None:
        return None
    now = float(s.iloc[-1]) / 1e6
    metric = {"label": "銀行準備金", "value": f"{now:.2f}T", "change": None}
    if now < 3.0:
        return _note("準備金偏緊", "bad",
                     f"銀行準備金 {now:.2f} 兆美元，已跌破 3 兆的「充裕」門檻。準備金不足時，銀行放款與附買回市場容易出現 2019 年式的資金緊繃。",
                     f"Bank reserves are ${now:.2f}T, below the ~$3T 'ample' threshold. Scarce reserves raise the risk of 2019-style repo-market stress.", metric)
    return _note("準備金充裕", "good",
                 f"銀行準備金 {now:.2f} 兆美元，仍在充裕區間，銀行體系的資金鋪底足夠，系統性資金荒的機率低。",
                 f"Bank reserves stand at ${now:.2f}T, still in the 'ample' regime — low risk of a systemic funding squeeze.", metric)


def real_rate(ds):
    dgs10, cpi = ds.latest("DGS10"), ds.latest("CPI_YoY")
    if dgs10 is None or cpi is None:
        return None
    real = dgs10 - cpi
    metric = {"label": "10Y 實質利率", "value": f"{real:+.2f}%", "change": None}
    if real > 1.5:
        return _note("實質利率偏高", "bad",
                     f"10 年美債 {dgs10:.2f}% 減 CPI {cpi:.2f}%，實質利率約 {real:+.2f}%，資金成本明顯高於通膨，對高本益比的成長股估值壓力最大。",
                     f"The 10-year yield ({dgs10:.2f}%) minus CPI ({cpi:.2f}%) puts real rates near {real:+.2f}% — restrictive territory that weighs most on high-multiple growth stocks.", metric)
    if real < 0:
        return _note("負實質利率", "good",
                     f"實質利率約 {real:+.2f}%，現金與債券的實質報酬為負，資金被迫流向股票、黃金等風險資產。",
                     f"Real rates are negative (~{real:+.2f}%). With cash and bonds losing to inflation, money is pushed toward equities and gold.", metric)
    return _note("實質利率中性", "neutral",
                 f"10 年實質利率約 {real:+.2f}%，接近中性水準，利率對股市估值的壓力不大也不小。",
                 f"The 10-year real rate is around {real:+.2f}%, near neutral — neither a strong headwind nor a tailwind for valuations.", metric)


def policy_stance(ds):
    iorb, pce, dgs2 = ds.latest("IORB"), ds.latest("Core_PCE_YoY"), ds.latest("DGS2")
    if iorb is None or pce is None:
        return None
    real_policy = iorb - pce
    metric = {"label": "實質政策利率", "value": f"{real_policy:+.2f}%", "change": None}
    market = ""
    market_en = ""
    if dgs2 is not None:
        if dgs2 < iorb - 0.25:
            market, market_en = f"2 年債 {dgs2:.2f}% 低於政策利率，市場在押注降息。", f" The 2-year yield ({dgs2:.2f}%) sits below the policy rate, so markets are pricing cuts."
        elif dgs2 > iorb + 0.25:
            market, market_en = f"2 年債 {dgs2:.2f}% 高於政策利率，市場甚至在擔心升息。", f" The 2-year yield ({dgs2:.2f}%) is above the policy rate — markets are pricing hike risk."
    if real_policy > 1.0:
        return _note("貨幣政策緊縮", "bad",
                     f"政策利率 {iorb:.2f}% 減核心 PCE {pce:.2f}%，實質政策利率 {real_policy:+.2f}%，Fed 仍處於緊縮立場。{market}",
                     f"Policy rate {iorb:.2f}% minus core PCE {pce:.2f}% gives a real policy rate of {real_policy:+.2f}% — the Fed remains restrictive.{market_en}", metric)
    if real_policy < 0:
        return _note("貨幣政策寬鬆", "good",
                     f"政策利率 {iorb:.2f}% 低於核心通膨 {pce:.2f}%，實質政策利率為負，Fed 實際上是在放水。{market}",
                     f"The policy rate ({iorb:.2f}%) is below core inflation ({pce:.2f}%), so real policy is negative — effectively accommodative.{market_en}", metric)
    return _note("貨幣政策中性", "neutral",
                 f"實質政策利率 {real_policy:+.2f}%，接近中性，Fed 進可攻退可守。{market}",
                 f"The real policy rate is {real_policy:+.2f}%, close to neutral, giving the Fed room to move either way.{market_en}", metric)


def yield_curve(ds):
    s = ds.df["Yield_Curve"].dropna() if "Yield_Curve" in ds.df.columns else None
    if s is None or len(s) < 252:
        return None
    now = float(s.iloc[-1])
    was_inverted = (s.tail(504) < 0).any()
    metric = {"label": "10Y-2Y", "value": f"{now:+.2f}%", "change": None}
    if now < 0:
        return _note("殖利率曲線倒掛", "bad",
                     f"10 年減 2 年殖利率為 {now:+.2f}%，曲線倒掛。倒掛代表市場預期未來經濟轉弱、利率必須下降，歷史上是衰退的領先指標。",
                     f"The 10s-2s spread is {now:+.2f}% — inverted. Inversions signal expectations of slower growth and lower future rates, a classic recession lead indicator.", metric)
    if was_inverted:
        return _note("解除倒掛", "bad",
                     f"殖利率曲線已從倒掛轉正 ({now:+.2f}%)。經驗上「解除倒掛」比倒掛本身更危險，常出現在衰退真正開始、Fed 被迫降息的階段。",
                     f"The curve has un-inverted to {now:+.2f}%. Historically the re-steepening after an inversion is more dangerous than the inversion itself, often coinciding with recession onset.", metric)
    return _note("殖利率曲線正常", "good",
                 f"10 年減 2 年殖利率 {now:+.2f}%，曲線正常向上，市場對長期成長仍有信心。",
                 f"The 10s-2s spread is a normal {now:+.2f}%, signalling confidence in longer-term growth.", metric)


def inflation(ds):
    s = _series(ds, "CPI")
    if s is None:
        return None
    now, prev = float(s.iloc[-1]), _ago(s, 92)
    if prev is None:
        return None
    pce = ds.latest("Core_PCE_YoY")
    trend = "回升" if now > prev + 0.2 else "降溫" if now < prev - 0.2 else "持平"
    trend_en = {"回升": "re-accelerating", "降溫": "cooling", "持平": "flat"}[trend]
    metric = {"label": "CPI 年增", "value": f"{now:.2f}%", "change": f"{now - prev:+.2f}pp/3M"}
    pce_txt = f"、核心 PCE {pce:.2f}%" if pce is not None else ""
    pce_en = f" and core PCE at {pce:.2f}%" if pce is not None else ""
    tone = "bad" if now > 3 or trend == "回升" else "good" if now < 2.5 else "neutral"
    return _note(f"通膨{trend}", tone,
                 f"CPI 年增 {now:.2f}%{pce_txt}，較 3 個月前{trend}。通膨離 Fed 2% 目標越遠，降息空間越小，長債殖利率越難下來。",
                 f"CPI inflation is {now:.2f}%{pce_en}, {trend_en} versus 3 months ago. The further inflation sits above 2%, the less room the Fed has to cut.", metric)


def labor(ds):
    u, sahm = ds.latest("Unemployment_Rate"), ds.latest("Sahm_Indicator")
    if u is None or sahm is None:
        return None
    metric = {"label": "失業率", "value": f"{u:.1f}%", "change": f"Sahm {sahm:.2f}"}
    if sahm >= 0.5:
        return _note("就業轉弱", "bad",
                     f"失業率 {u:.1f}%，薩姆指標 {sahm:.2f} 已觸發 0.5 的衰退門檻。勞動市場一旦轉弱，消費與企業獲利通常隨之下修。",
                     f"Unemployment is {u:.1f}% and the Sahm indicator ({sahm:.2f}) has crossed the 0.5 recession threshold. A softening labor market usually drags consumption and earnings lower.", metric)
    if sahm >= 0.3:
        return _note("就業降溫", "neutral",
                     f"失業率 {u:.1f}%，薩姆指標 {sahm:.2f} 接近 0.5 警戒線，就業市場在降溫，需密切觀察。",
                     f"Unemployment is {u:.1f}% with the Sahm indicator at {sahm:.2f}, approaching the 0.5 alarm — the labor market is cooling.", metric)
    return _note("就業穩健", "good",
                 f"失業率 {u:.1f}%，薩姆指標僅 {sahm:.2f}，勞動市場穩健，短期內沒有衰退訊號。",
                 f"Unemployment is {u:.1f}% and the Sahm indicator is just {sahm:.2f}: the labor market is solid, with no near-term recession signal.", metric)


def credit(ds):
    hy = ds.latest("High_Yield_Spread")
    if hy is None:
        return None
    metric = {"label": "垃圾債利差", "value": f"{hy:.2f}%", "change": None}
    if hy > 5:
        return _note("信用風險升溫", "bad",
                     f"高收益債利差擴大到 {hy:.2f}%，債券市場開始為違約風險要求更高補償，通常比股市更早嗅到景氣轉弱。",
                     f"High-yield spreads have widened to {hy:.2f}%. Credit markets are demanding more compensation for default risk — they often sniff out downturns before equities.", metric)
    if hy < 3.5:
        return _note("信用市場樂觀", "good" if hy > 2.8 else "neutral",
                     f"高收益債利差僅 {hy:.2f}%，企業借錢容易，信用市場樂觀；但利差太低也代表市場對風險的定價偏鬆。",
                     f"High-yield spreads are tight at {hy:.2f}%. Credit is easy to obtain and sentiment is upbeat — though spreads this tight also mean risk is cheaply priced.", metric)
    return None


def funding_stress(ds):
    spread = ds.latest("Liquidity_Spread")
    if spread is None:
        return None
    metric = {"label": "SOFR-IORB", "value": f"{spread:+.2f}%", "change": None}
    if abs(spread) <= 0.02:
        return _note("短期資金平穩", "neutral",
                     f"SOFR 與準備金利率幾乎持平 ({spread:+.2f}%)，隔夜資金沒有明顯壓力，但已沒有寬裕的緩衝，值得留意。",
                     f"SOFR is trading roughly in line with IORB ({spread:+.2f}%): no acute funding stress, but little slack left either.", metric)
    if spread > 0:
        return _note("短期資金緊繃", "bad",
                     f"SOFR 高於準備金利率 {spread:+.2f}%，隔夜資金市場出現緊繃，這是準備金不夠用的早期訊號，Fed 可能被迫停止 QT 或注資。",
                     f"SOFR is trading {spread:+.2f}% above IORB — overnight funding is tight. That's an early sign reserves are getting scarce and may force the Fed to end QT or inject liquidity.", metric)
    return _note("短期資金順暢", "good",
                 f"SOFR 低於準備金利率 ({spread:+.2f}%)，隔夜資金市場運作順暢，沒有資金荒跡象。",
                 f"SOFR is below IORB ({spread:+.2f}%), so overnight funding markets are functioning smoothly with no sign of stress.", metric)


GENERATORS = [balance_sheet, on_rrp, tga, net_liquidity, reserves, real_rate, policy_stance,
              yield_curve, inflation, labor, credit, funding_stress]


def macro_commentary(dataset):
    notes = []
    for gen in GENERATORS:
        try:
            note = gen(dataset)
        except Exception as e:  # 單一主題出錯不影響其他評語
            print(f"⚠️ 總經評語產生失敗 [{gen.__name__}]: {e}")
            continue
        if note:
            notes.append(note)
    return notes
