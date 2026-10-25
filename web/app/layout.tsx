import type { Metadata } from "next";
import { Barlow_Semi_Condensed, Noto_Sans_TC } from "next/font/google";

import { ScrollVar } from "@/components/Parallax";
import "./globals.css";

const digits = Barlow_Semi_Condensed({ variable: "--font-digits", subsets: ["latin"], weight: ["500", "600", "700"] });
const cjk = Noto_Sans_TC({ variable: "--font-cjk", subsets: ["latin"], weight: ["400", "500", "700", "900"], preload: false });

export const metadata: Metadata = {
  title: "荷莉總經觀測站",
  description: "每日 1 分鐘看懂今天股市的狀態、影響股市的新聞，以及該怎麼配置資金。",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="zh-Hant" className={`${digits.variable} ${cjk.variable} h-full antialiased`}>
      <body className="min-h-full font-sans">
        <ScrollVar />
        {children}
      </body>
    </html>
  );
}
