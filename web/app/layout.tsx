import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import { ScrollVar } from "@/components/Parallax";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "荷莉總經觀測站",
  description: "每日 1 分鐘看懂今天股市的狀態、影響股市的新聞，以及該怎麼配置資金。",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="zh-Hant" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="min-h-full font-sans">
        <ScrollVar />
        {children}
      </body>
    </html>
  );
}
