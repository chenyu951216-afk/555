"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BarChart3, ClipboardList, Database, FileQuestion, GitCompareArrows, Home, Import, ListFilter, Settings } from "lucide-react";
import { ReactNode } from "react";
import { clsx } from "clsx";

const nav = [
  { href: "/", label: "總覽", icon: Home },
  { href: "/recorded", label: "計入資料", icon: ClipboardList },
  { href: "/import", label: "匯入中心", icon: Import },
  { href: "/runs", label: "回測紀錄", icon: ListFilter },
  { href: "/compare", label: "紀錄比較", icon: GitCompareArrows },
  { href: "/explorer", label: "資料表查詢", icon: Database },
  { href: "/settings", label: "設定", icon: Settings },
  { href: "/help", label: "說明", icon: FileQuestion },
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  return (
    <div className="min-h-screen bg-paper text-ink">
      <aside className="fixed left-0 top-0 hidden h-screen w-64 border-r border-line bg-white/90 px-4 py-5 lg:block">
        <div className="mb-7 flex items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-md bg-teal text-white">
            <BarChart3 size={20} />
          </div>
          <div>
            <div className="text-sm font-semibold">回測紀錄系統</div>
            <div className="text-xs text-graphite">紀錄、資料表、日誌</div>
          </div>
        </div>
        <nav className="space-y-1">
          {nav.map((item) => {
            const Icon = item.icon;
            const active = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
            return (
              <Link
                key={item.href}
                href={item.href}
                className={clsx(
                  "flex h-10 items-center gap-3 rounded-md px-3 text-sm transition",
                  active ? "bg-teal text-white" : "text-graphite hover:bg-paper hover:text-ink",
                )}
              >
                <Icon size={17} />
                {item.label}
              </Link>
            );
          })}
        </nav>
      </aside>
      <div className="lg:pl-64">
        <header className="sticky top-0 z-10 border-b border-line bg-paper/95 px-4 py-3 backdrop-blur lg:hidden">
          <div className="mb-3 text-sm font-semibold">回測紀錄系統</div>
          <div className="flex gap-2 overflow-x-auto pb-1">
            {nav.map((item) => (
              <Link key={item.href} href={item.href} className="whitespace-nowrap rounded-md border border-line bg-white px-3 py-2 text-xs">
                {item.label}
              </Link>
            ))}
          </div>
        </header>
        <main className="mx-auto max-w-7xl px-4 py-6 lg:px-8">{children}</main>
      </div>
    </div>
  );
}
