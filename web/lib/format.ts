import type { Card } from "./types";

/** compact：不加單位 (給座標軸)；keepDecimals：compact 時仍保留卡片設定的小數位 */
export function formatValue(card: Card, value: number, opts: { compact?: boolean; keepDecimals?: boolean } = {}) {
  const decimals = opts.compact && !opts.keepDecimals ? Math.min(card.decimals, 2) : card.decimals;
  const abs = Math.abs(value).toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
  const sign = value < 0 ? "-" : card.signed && value > 0 ? "+" : "";
  return `${sign}${card.prefix}${abs}${opts.compact ? "" : card.suffix}`;
}

/** 變化量：價格類顯示 %；利率/百分比類只顯示數字 (單位「百分點」寫在標題) */
export function formatChange(card: Card, value: number) {
  const unit = card.changeMode === "pct" ? "%" : "";
  const rateLike = /%|百分點/.test(card.suffix);
  // 漲跌 %：小數 1~2 位；利率類增減：至少 2 位；億、口、分等：照卡片設定 (通常 0 位) 並加千分位
  const digits = card.changeMode === "pct" ? (Math.abs(value) < 10 ? 2 : 1) : rateLike ? Math.max(card.decimals, 2) : card.decimals;
  const text = value.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
  return `${value > 0 ? "+" : ""}${text}${unit}`;
}

/** 這個方向的變化是好事還是壞事 */
export function changeTone(card: Card, value: number): "good" | "bad" | "flat" {
  if (Math.abs(value) < 1e-9) return "flat";
  const up = value > 0;
  return up !== card.invertColor ? "good" : "bad";
}

export const RANGE_DAYS = { "3M": 92, "1Y": 366, "3Y": 1100 } as const;

/** 中性位階：只說在歷史上的高低，不暗示好壞 (給買賣超、成長率這類指標) */
export function prBandNeutral(pr: number) {
  if (pr >= 90) return "極高";
  if (pr >= 70) return "偏高";
  if (pr > 30) return "常態";
  if (pr > 10) return "偏低";
  return "極低";
}

export function prBand(pr: number) {
  if (pr >= 90) return { label: "極端", tone: "bad" as const };
  if (pr >= 80) return { label: "警戒", tone: "serious" as const };
  if (pr >= 20) return { label: "常態", tone: "neutral" as const };
  if (pr >= 10) return { label: "超跌", tone: "goodSoft" as const };
  return { label: "黃金坑", tone: "good" as const };
}
