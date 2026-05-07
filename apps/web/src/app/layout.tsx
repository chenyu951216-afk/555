import type { Metadata } from "next";
import { ReactNode } from "react";
import "./globals.css";
import { Providers } from "./providers";
import { AppShell } from "@/components/app-shell";

export const metadata: Metadata = {
  title: "回測紀錄系統",
  description: "回測與真實下單紀錄資料庫",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-Hant">
      <body>
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  );
}
