"use client";

import { useEffect } from "react";

/** 把捲動距離寫進 CSS 變數 --sy，所有 .parallax 層用 CSS 自己算位移 (不觸發 React 重繪) */
export function ScrollVar() {
  useEffect(() => {
    let frame = 0;
    const update = () => {
      frame = 0;
      document.documentElement.style.setProperty("--sy", String(window.scrollY));
    };
    const onScroll = () => {
      if (!frame) frame = requestAnimationFrame(update);
    };
    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      cancelAnimationFrame(frame);
    };
  }, []);
  return null;
}
