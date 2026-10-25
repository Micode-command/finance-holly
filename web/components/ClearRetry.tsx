"use client";

import { useEffect } from "react";

/** 頁面成功載入後，清掉「主機喚醒中」的自動重試次數 */
export default function ClearRetry() {
  useEffect(() => {
    try {
      sessionStorage.removeItem("holly-auto-retry");
    } catch {}
  }, []);
  return null;
}
