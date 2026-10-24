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
  const digits = card.changeMode === "pct" ? (Math.abs(value) < 10 ? 2 : 1) : Math.max(card.decimals, 2);
  return `${value > 0 ? "+" : ""}${value.toFixed(digits)}${unit}`;
}

/** 這個方向的變化是好事還是壞事 */
export function changeTone(card: Card, value: number): "good" | "bad" | "flat" {
  if (Math.abs(value) < 1e-9) return "flat";
  const up = value > 0;
  return up !== card.invertColor ? "good" : "bad";
}

export const RANGE_DAYS = { "3M": 92, "1Y": 366, "3Y": 1100 } as const;

export function prBand(pr: number) {
  if (pr >= 90) return { label: "極端", tone: "bad" as const };
  if (pr >= 80) return { label: "警戒", tone: "serious" as const };
  if (pr >= 20) return { label: "常態", tone: "neutral" as const };
  if (pr >= 10) return { label: "超跌", tone: "goodSoft" as const };
  return { label: "黃金坑", tone: "good" as const };
}
