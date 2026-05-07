"use client";

import Link from "next/link";
import { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { ClipboardList, History, ListChecks } from "lucide-react";
import { apiFetch, BitgetRecordedData } from "@/lib/api";
import { formatCurrency, formatDateTime, formatNumber } from "@/lib/format";
import { ErrorState, LoadingState, PageHeader, Panel, StatCard } from "@/components/ui";

export default function DashboardPage() {
  const { data, error, isLoading } = useQuery({
    queryKey: ["bitget-recorded-dashboard"],
    queryFn: () => apiFetch<BitgetRecordedData>("/bitget/recorded-data?order_limit=20&fill_limit=20&issue_limit=50&log_limit=20"),
  });

  if (isLoading) return <LoadingState />;
  if (error) return <ErrorState message={(error as Error).message} />;
  if (!data) return null;

  return (
    <div>
      <PageHeader
        title="總覽"
        description="只統計台灣時間 2026/05/08 00:00 之後已寫入資料庫的真實 Bitget 下單與成交資料。"
        action={
          <Link className="inline-flex h-10 items-center gap-2 rounded-md bg-teal px-3 text-sm text-white" href="/recorded">
            <ClipboardList size={16} />
            查看計入資料
          </Link>
        }
      />

      <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
        <StatCard label="紀錄起點" value={formatDateTime(data.record_start_at)} detail="台北時間" />
        <StatCard label="真實匯入批次" value={formatNumber(data.summary.real_import_runs, 0)} detail="Bitget 唯讀 API" />
        <StatCard label="已計入訂單" value={formatNumber(data.summary.orders, 0)} detail={<span className="inline-flex items-center gap-1"><ListChecks size={14} />訂單表</span>} />
        <StatCard label="已計入成交" value={formatNumber(data.summary.fills, 0)} detail="成交表" />
        <StatCard label="最新訂單時間" value={formatDateTime(data.summary.last_order_time)} detail="只看計入資料" />
        <StatCard label="最新成交時間" value={formatDateTime(data.summary.last_fill_time)} detail="只看計入資料" />
      </div>

      <div className="mt-5 grid gap-4 xl:grid-cols-2">
        <Panel>
          <div className="mb-3 text-sm font-semibold">最新計入訂單</div>
          <SimpleTable
            empty="目前沒有符合時間規則的訂單"
            columns={["時間", "交易對", "方向", "倉位效果", "訂單ID", "狀態", "價格", "數量"]}
            rows={data.orders.map((row) => ({
              時間: formatDateTime(row.order_time),
              交易對: row.symbol || "-",
              方向: row.side || "-",
              倉位效果: row.position_effect || "-",
              訂單ID: <span className="font-mono text-xs">{row.order_id}</span>,
              狀態: row.status || "-",
              價格: formatNumber(row.price, 8),
              數量: formatNumber(row.qty, 8),
            }))}
          />
        </Panel>
        <Panel>
          <div className="mb-3 text-sm font-semibold">最新計入成交</div>
          <SimpleTable
            empty="目前沒有符合時間規則的成交"
            columns={["時間", "交易對", "方向", "倉位效果", "成交ID", "價格", "數量", "手續費", "損益"]}
            rows={data.fills.map((row) => ({
              時間: formatDateTime(row.fill_time),
              交易對: row.symbol || "-",
              方向: row.side || "-",
              倉位效果: row.position_effect || "-",
              成交ID: <span className="font-mono text-xs">{row.fill_id}</span>,
              價格: formatNumber(row.price, 8),
              數量: formatNumber(row.qty, 8),
              手續費: formatCurrency(row.fee, row.fee_currency || "USDT"),
              損益: formatCurrency(row.realized_pnl, "USDT"),
            }))}
          />
        </Panel>
      </div>

      <Panel className="mt-5">
        <div className="mb-3 flex items-center gap-2 text-sm font-semibold"><History size={16} />近期匯入問題</div>
        <SimpleTable
          empty="目前沒有匯入問題"
          columns={["建立時間", "紀錄代號", "檔案", "列", "代碼", "訊息"]}
          rows={data.row_issues.map((row) => ({
            建立時間: formatDateTime(row.created_at),
            紀錄代號: row.run_id,
            檔案: row.file_name,
            列: row.row_number ?? "-",
            代碼: row.issue_code,
            訊息: row.message,
          }))}
        />
      </Panel>
    </div>
  );
}

function SimpleTable({ columns, rows, empty }: { columns: string[]; rows: Array<Record<string, ReactNode>>; empty: string }) {
  if (!rows.length) return <div className="rounded-md border border-dashed border-line bg-paper p-5 text-center text-sm text-graphite">{empty}</div>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] text-left text-sm">
        <thead className="border-b border-line text-xs text-graphite">
          <tr>{columns.map((column) => <th key={column} className="py-2 pr-3">{column}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index} className="border-b border-line/70 align-top">
              {columns.map((column) => <td key={column} className="max-w-[260px] break-words py-2 pr-3">{row[column] ?? "-"}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
