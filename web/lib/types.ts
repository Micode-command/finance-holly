// 與 api/payload.py 的輸出一一對應

export type CardDesc =
  | { kind: "explain"; formula: string; threshold: string; impact: string; thresholdLabel: string }
  | { kind: "tip"; summary: string; hint: string };

export type Range = "3M" | "1Y" | "3Y";

export interface Card {
  id: string;
  title: string;
  desc: CardDesc;
  prType: "C" | "G";
  isMacro: boolean;
  invertColor: boolean;
  decimals: number;
  signed: boolean;
  prefix: string;
  suffix: string;
  changeMode: "pct" | "abs";
  defaultRange: Range;
  prNeutral: boolean;
  refLines: { value: number; label: string }[];
  terms: string[];
  available: boolean;
  latest?: number;
  lastDate?: string;
  changes?: { label: string; value: number | null }[];
  percentiles?: { label: string; value: number | null }[];
  note?: string | null;
  series?: [string, number][];
}

export interface Section {
  title: string;
  nav: string;
  intro: string;
  cards: Card[];
}

export type Stance = "offensive" | "neutral" | "defensive";

export interface Verdict {
  stance: Stance;
  label: string;
  headline: string;
  actions: string[];
  drivers: { tone: "good" | "bad"; text: string; short: string }[];
  one_liner: string;
}

export interface Vital {
  id: string;
  label: string;
  value: number;
  change: number;
  changeMode: "pct" | "abs";
  prefix: string;
  suffix: string;
  decimals: number;
  invertColor: boolean;
  date: string;
}

export interface NewsItem {
  title: string;
  link: string;
  published: string | null;
  source: string;
  topics: string[];
  related: { id: string; label: string }[];
}

export interface MacroNote {
  topic: string;
  tone: "good" | "bad" | "neutral";
  zh: string;
  en: string;
  metric: { label: string; value: string; change: string | null };
}

export interface Regime {
  Forecast_Prob_Low_Vol: number;
  Forecast_Prob_High_Vol: number;
  Forecast_Prob_Black_Swan: number;
}

export interface ScoreFactor {
  key: string;
  label: string;
  value: string;
  score: number; // 0~100，越高 = 對該分數貢獻越大
  why: string;
}

export interface MarketScores {
  opportunity: number;
  risk: number;
  opportunity_change_5d: number;
  risk_change_5d: number;
  opportunity_details: ScoreFactor[];
  risk_details: ScoreFactor[];
  odds: { range: string; upProb: number; avgReturn: number; days: number; baseUpProb: number } | null;
  history: [string, number, number][];
}

export interface BottomFishing {
  values: Record<"Brent" | "CPI_YoY" | "DGS10" | "DGS30" | "DGS2" | "IORB", number>;
  oilOk: boolean;
  cpiOk: boolean;
  longRatesOk: boolean;
  cutPricedIn: boolean;
  met: number;
}

export interface Dashboard {
  asOf: string;
  missingFred: string[];
  missingTw: string[];
  aiEnabled: boolean;
  verdict: Verdict;
  vitals: Vital[];
  regime: Regime;
  news: NewsItem[];
  macro: MacroNote[];
  scores: MarketScores | null;
  bottomFishing: BottomFishing | null;
  sections: Section[];
}

export interface AiResult {
  error?: string;
  model?: string;
  cached?: boolean;
  generatedAt?: string;
  macro_phase_insight?: string;
  broadcast?: string;
  allocation_recommendation?: Record<string, number>;
  allocation_reasons?: Record<string, string>;
  market_insights_html?: string;
}

export interface MarketStatus {
  state: "pre_open" | "open" | "closed" | "holiday" | "weekend" | "suspended";
  label: string;
  detail: string;
  reason: string | null;
  note?: string;
  lastClosedDay: string;
  nextOpenDay: string;
  hoursToOpen: number;
}

export interface OpenForecast {
  lastClose: number | null;
  lastClosedDay: string;
  inputs: { key: string; label: string; pct: number | null; detail: string | null }[];
  model: "full" | "night_only" | "us_only" | null;
  message?: string;
  modelLabel?: string;
  gapPct?: number;
  gapPoints?: number | null;
  low?: number;
  high?: number;
  direction?: string;
  hitRate?: number;
  band?: number;
}

export interface StockBrief {
  id: string;
  name: string;
  industry: string;
}

export interface StockCheck {
  status: "ok";
  stock: StockBrief;
  cached: boolean;
  model: string | null;
  generatedAt: string;
  error?: string;
  market: { label: string; headline: string; opportunity: number; risk: number };
  metrics: {
    price: { close: number; date: string; ret1m: number | null; ret3m: number | null; ret1y: number | null; high52: number; low52: number;
      ma200dev: number | null; vol: number; band68: [number, number]; band90: [number, number]; beta: number | null } | null;
    revenue: { month: string; latest: number; yoy: number | null; mom: number | null; yoy3m: number | null; ytdYoy: number | null } | null;
    income: { quarter: string; grossMargin: number | null; grossMarginYearAgo: number | null; opMargin: number | null; opMarginYearAgo: number | null;
      epsLatest: number | null; epsTTM: number | null; epsTTMPrev: number | null; quarterRevenueYoy: number | null } | null;
    balance: { debtRatio: number | null; currentRatio: number | null; cash: number | null } | null;
    valuation: { pe: number | null; pePercentile: number | null; pb: number; dividendYield: number } | null;
    flows: { foreign20d: number; trust20d: number; days: number } | null;
  };
  ai: {
    summary: string; stance: string; price_3m: { bear: number; base: number; bull: number } | null;
    reasoning: string; strengths: string[]; risks: string[]; catalysts: string[]; valuation: string; for_long_term_holder: string; outsideBand: boolean;
  } | null;
}

export interface PortfolioHolding {
  id: string; name: string; industry: string; weight: number; isEtf: boolean; isBond: boolean;
  ret3m: number | null; ret1y: number | null; vol: number | null; beta: number | null; ma200dev: number | null;
  pe: number | null; dividendYield: number | null;
}

export interface PortfolioCheck {
  status: "ok";
  holdings: PortfolioHolding[];
  cash: number;
  goal: string;
  model: string | null;
  error?: string;
  market: { label: string; headline: string; opportunity: number; risk: number };
  metrics: {
    equity: number; cash: number; stockLike: number; bond: number; etfWeight: number;
    topHolding: { name: string; weight: number }; effectiveN: number; beta: number | null; avgVol: number | null;
    dividendYield: number | null; industries: Record<string, number>;
  };
  ai: {
    summary: string; risk_level: string; fit_with_market: string; strengths?: string[]; issues: string[];
    suggestions: { action: string; target: string; detail: string }[];
    suggested_weights: { name: string; current: number; suggested: number }[];
    next_steps: string[];
    stanceCheck: { change: number; allowed: [number, number]; ok: boolean } | null;
  } | null;
}
