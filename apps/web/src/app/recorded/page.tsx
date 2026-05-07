"use client";

import Link from "next/link";
import { ReactNode, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ClipboardList, Download, FileWarning, History, ListChecks, RefreshCw, Search } from "lucide-react";
import { apiFetch, BitgetRecordedData, BitgetStatus, ImportResult, RecordedAuditLog, RecordedFill, RecordedOrder, RecordedRowIssue } from "@/lib/api";
import { formatCurrency, formatDateTime, formatNumber, numberValue } from "@/lib/format";
import { Button, ErrorState, Input, LoadingState, PageHeader, Panel, Select, StatCard } from "@/components/ui";

type Tab = "orders" | "fills" | "issues" | "logs";

export default function RecordedDataPage() {
  const [tab, setTab] = useState<Tab>("orders");
  const [search, setSearch] = useState("");
  const [symbol, setSymbol] = useState("");
  const [effect, setEffect] = useState("");

  const dataQuery = useQuery({
    queryKey: ["bitget-recorded-data"],
    queryFn: async () => {
      await apiFetch<ImportResult>("/bitget/sync-readonly", {
        method: "POST",
        body: JSON.stringify({ product_type: "USDT-FUTURES", max_pages: 20 }),
      });
      return apiFetch<BitgetRecordedData>("/bitget/recorded-data?order_limit=1000&fill_limit=1000&issue_limit=200&log_limit=200");
    },
    refetchInterval: 60_000,
  });
  const statusQuery = useQuery({ queryKey: ["bitget-status"], queryFn: () => apiFetch<BitgetStatus>("/bitget/status") });

  const data = dataQuery.data;
  const symbols = useMemo(() => uniqueValues([...(data?.orders || []), ...(data?.fills || [])].map((item) => item.symbol)), [data]);
  const effects = useMemo(() => uniqueValues([...(data?.orders || []), ...(data?.fills || [])].map((item) => item.position_effect)), [data]);
  const filteredOrders = useMemo(() => filterOrders(data?.orders || [], search, symbol, effect), [data, effect, search, symbol]);
  const filteredFills = useMemo(() => filterFills(data?.fills || [], search, symbol, effect), [data, effect, search, symbol]);
  const fillNotional = filteredFills.reduce((sum, row) => sum + (numberValue(row.notional) || 0), 0);
  const fillFees = filteredFills.reduce((sum, row) => sum + (numberValue(row.fee) || 0), 0);
  const realizedPnl = filteredFills.reduce((sum, row) => sum + (numberValue(row.realized_pnl) || 0), 0);

  if (dataQuery.isLoading) return <LoadingState />;
  if (dataQuery.error) return <ErrorState message={(dataQuery.error as Error).message} />;
  if (!data) return null;

  return (
    <div>
      <PageHeader
        title="計入資料"
        description="自動偵測並記錄台灣時間 2026/05/08 00:00 之後的真實 Bitget 下單與成交資料。"
        action={
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => dataQuery.refetch()}>
              <RefreshCw size={16} />
              重新整理
            </Button>
            <Link className="inline-flex h-10 items-center rounded-md border border-line bg-white px-3 text-sm text-teal" href="/import">
              匯入
            </Link>
          </div>
        }
      />

      <div className="grid gap-4 md:grid-cols-4">
        <StatCard label="紀錄起點" value={formatDateTime(data.record_start_at)} detail="以台北時間顯示" />
        <StatCard label="API 金鑰" value={statusQuery.data?.configured ? "已設定" : "未讀到"} detail={statusQuery.data?.base_url || "Bitget API"} />
        <StatCard label="已計入訂單" value={formatNumber(data.summary.orders, 0)} detail={`目前篩選：${formatNumber(filteredOrders.length, 0)}`} />
        <StatCard label="已計入成交" value={formatNumber(data.summary.fills, 0)} detail={`目前篩選：${formatNumber(filteredFills.length, 0)}`} />
      </div>

      <div className="mt-4 grid gap-4 md:grid-cols-4">
        <StatCard label="交易對數量" value={formatNumber(symbols.length, 0)} detail={symbols.slice(0, 4).join(", ") || "-"} />
        <StatCard label="篩選成交額" value={formatCurrency(fillNotional, "USDT")} detail="只統計成交資料" />
        <StatCard label="篩選手續費" value={formatCurrency(fillFees, "USDT")} detail="只統計成交資料" />
        <StatCard label="篩選已實現損益" value={formatCurrency(realizedPnl, "USDT")} detail="只統計成交資料" />
      </div>

      <Panel className="mt-5">
        <div className="grid gap-3 lg:grid-cols-[1fr_180px_180px_auto]">
          <div className="relative">
            <Search className="absolute left-3 top-3 text-graphite" size={16} />
            <Input className="w-full pl-9" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="搜尋交易對、訂單 ID、成交 ID、紀錄代號" />
          </div>
          <Select value={symbol} onChange={(event) => setSymbol(event.target.value)}>
            <option value="">全部交易對</option>
            {symbols.map((item) => <option key={item} value={item}>{item}</option>)}
          </Select>
          <Select value={effect} onChange={(event) => setEffect(event.target.value)}>
            <option value="">全部倉位效果</option>
            {effects.map((item) => <option key={item} value={item}>{item}</option>)}
          </Select>
          <div className="flex gap-2">
            <Button onClick={() => exportOrders(filteredOrders)}>
              <Download size={16} />
              訂單 CSV
            </Button>
            <Button onClick={() => exportFills(filteredFills)}>
              <Download size={16} />
              成交 CSV
            </Button>
          </div>
        </div>
      </Panel>

      {data.stats?.fills_by_symbol_effect?.length ? (
        <Panel className="mt-5">
          <div className="mb-3 text-sm font-semibold">策略優化用統計</div>
          <DataTable
            empty="目前沒有可彙總的成交統計。"
            columns={["交易對", "倉位效果", "成交筆數", "成交額", "手續費", "已實現損益"]}
            rows={data.stats.fills_by_symbol_effect.slice(0, 20).map((row) => ({
              交易對: row.symbol,
              倉位效果: row.position_effect,
              成交筆數: formatNumber(row.fill_count, 0),
              成交額: formatCurrency(row.notional, "USDT"),
              手續費: formatCurrency(row.fee, "USDT"),
              已實現損益: formatCurrency(row.realized_pnl, "USDT"),
            }))}
          />
        </Panel>
      ) : null}

      <Panel className="mt-5">
        <div className="mb-4 flex flex-wrap gap-2">
          <TabButton active={tab === "orders"} onClick={() => setTab("orders")} icon={<ClipboardList size={16} />} label={`訂單 (${filteredOrders.length}/${data.orders.length})`} />
          <TabButton active={tab === "fills"} onClick={() => setTab("fills")} icon={<ListChecks size={16} />} label={`成交 (${filteredFills.length}/${data.fills.length})`} />
          <TabButton active={tab === "issues"} onClick={() => setTab("issues")} icon={<FileWarning size={16} />} label={`匯入問題 (${data.row_issues.length})`} />
          <TabButton active={tab === "logs"} onClick={() => setTab("logs")} icon={<History size={16} />} label={`系統日誌 (${data.audit_logs.length})`} />
        </div>
        {tab === "orders" ? <OrdersTable rows={filteredOrders} /> : null}
        {tab === "fills" ? <FillsTable rows={filteredFills} /> : null}
        {tab === "issues" ? <IssuesTable rows={data.row_issues} /> : null}
        {tab === "logs" ? <LogsTable rows={data.audit_logs} /> : null}
      </Panel>
    </div>
  );
}

function uniqueValues(values: Array<string | null | undefined>) {
  return Array.from(new Set(values.filter((value): value is string => Boolean(value)))).sort();
}

function includesSearch(values: Array<unknown>, search: string) {
  const needle = search.trim().toLowerCase();
  if (!needle) return true;
  return values.some((value) => String(value || "").toLowerCase().includes(needle));
}

function filterOrders(rows: RecordedOrder[], search: string, symbol: string, effect: string) {
  return rows.filter((row) => {
    if (symbol && row.symbol !== symbol) return false;
    if (effect && row.position_effect !== effect) return false;
    return includesSearch([row.run_id, row.run_title, row.order_id, row.trade_id, row.symbol, row.side, row.status, row.position_effect], search);
  });
}

function filterFills(rows: RecordedFill[], search: string, symbol: string, effect: string) {
  return rows.filter((row) => {
    if (symbol && row.symbol !== symbol) return false;
    if (effect && row.position_effect !== effect) return false;
    return includesSearch([row.run_id, row.run_title, row.fill_id, row.order_id, row.trade_id, row.symbol, row.side, row.position_effect], search);
  });
}

function TabButton({ active, onClick, icon, label }: { active: boolean; onClick: () => void; icon: ReactNode; label: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex h-10 items-center gap-2 rounded-md border px-3 text-sm transition ${
        active ? "border-teal bg-teal text-white" : "border-line bg-white text-graphite hover:border-teal hover:text-ink"
      }`}
    >
      {icon}
      {label}
    </button>
  );
}

function OrdersTable({ rows }: { rows: RecordedOrder[] }) {
  return (
    <DataTable
      empty="目前篩選條件下沒有已計入的真實 Bitget 訂單。"
      columns={["時間", "交易對", "方向", "倉位效果", "訂單ID", "類型", "狀態", "價格", "數量", "成交量", "只減倉", "紀錄代號", "原始欄位"]}
      rows={rows.map((row) => ({
        時間: formatDateTime(row.order_time),
        交易對: row.symbol || "-",
        方向: row.side || "-",
        倉位效果: row.position_effect || "-",
        訂單ID: <span className="font-mono text-xs">{row.order_id}</span>,
        類型: row.order_type || "-",
        狀態: row.status || "-",
        價格: formatNumber(row.price, 8),
        數量: formatNumber(row.qty, 8),
        成交量: formatNumber(row.filled_qty, 8),
        只減倉: row.reduce_only === null || row.reduce_only === undefined ? "-" : String(row.reduce_only),
        紀錄代號: <span className="font-mono text-xs">{row.run_id}</span>,
        原始欄位: <MetadataCell value={row.metadata_json} />,
      }))}
    />
  );
}

function FillsTable({ rows }: { rows: RecordedFill[] }) {
  return (
    <DataTable
      empty="目前篩選條件下沒有已計入的真實 Bitget 成交。"
      columns={["時間", "交易對", "方向", "倉位效果", "成交ID", "訂單ID", "價格", "數量", "成交額", "手續費", "損益", "紀錄代號", "原始欄位"]}
      rows={rows.map((row) => ({
        時間: formatDateTime(row.fill_time),
        交易對: row.symbol || "-",
        方向: row.side || "-",
        倉位效果: row.position_effect || "-",
        成交ID: <span className="font-mono text-xs">{row.fill_id}</span>,
        訂單ID: <span className="font-mono text-xs">{row.order_id || "-"}</span>,
        價格: formatNumber(row.price, 8),
        數量: formatNumber(row.qty, 8),
        成交額: formatCurrency(row.notional, "USDT"),
        手續費: formatCurrency(row.fee, row.fee_currency || "USDT"),
        損益: formatCurrency(row.realized_pnl, "USDT"),
        紀錄代號: <span className="font-mono text-xs">{row.run_id}</span>,
        原始欄位: <MetadataCell value={row.metadata_json} />,
      }))}
    />
  );
}

function IssuesTable({ rows }: { rows: RecordedRowIssue[] }) {
  return (
    <DataTable
      empty="真實 Bitget 匯入目前沒有列級問題。"
      columns={["建立時間", "紀錄代號", "檔案", "列", "代碼", "訊息"]}
      rows={rows.map((row) => ({
        建立時間: formatDateTime(row.created_at),
        紀錄代號: <span className="font-mono text-xs">{row.run_id}</span>,
        檔案: row.file_name,
        列: row.row_number ?? "-",
        代碼: row.issue_code,
        訊息: row.message,
      }))}
    />
  );
}

function LogsTable({ rows }: { rows: RecordedAuditLog[] }) {
  return (
    <DataTable
      empty="真實 Bitget 匯入目前沒有系統日誌。"
      columns={["建立時間", "動作", "目標", "明細"]}
      rows={rows.map((row) => ({
        建立時間: formatDateTime(row.created_at),
        動作: row.action,
        目標: <span className="font-mono text-xs">{row.target_id}</span>,
        明細: <span className="block max-w-[520px] truncate font-mono text-xs" title={JSON.stringify(row.details_json || {})}>{JSON.stringify(row.details_json || {})}</span>,
      }))}
    />
  );
}

function MetadataCell({ value }: { value?: Record<string, unknown> | null }) {
  const text = JSON.stringify(value || {});
  if (text === "{}") return "-";
  return <span className="block max-w-[260px] truncate font-mono text-xs" title={text}>{text}</span>;
}

function DataTable({ columns, rows, empty }: { columns: string[]; rows: Array<Record<string, ReactNode>>; empty: string }) {
  if (!rows.length) return <div className="rounded-md border border-dashed border-line bg-paper p-6 text-center text-sm text-graphite">{empty}</div>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[1180px] text-left text-sm">
        <thead className="border-b border-line text-xs text-graphite">
          <tr>
            {columns.map((column) => (
              <th key={column} className="py-2 pr-3 font-medium">
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index} className="border-b border-line/70 align-top">
              {columns.map((column) => (
                <td key={column} className="max-w-[260px] break-words py-2 pr-3">
                  {row[column] ?? "-"}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function exportOrders(rows: RecordedOrder[]) {
  downloadCsv(
    "recorded_orders.csv",
    ["order_time", "symbol", "side", "position_effect", "order_id", "order_type", "status", "price", "qty", "filled_qty", "reduce_only", "run_id"],
    rows.map((row) => ({
      order_time: row.order_time,
      symbol: row.symbol,
      side: row.side,
      position_effect: row.position_effect,
      order_id: row.order_id,
      order_type: row.order_type,
      status: row.status,
      price: row.price,
      qty: row.qty,
      filled_qty: row.filled_qty,
      reduce_only: row.reduce_only,
      run_id: row.run_id,
    })),
  );
}

function exportFills(rows: RecordedFill[]) {
  downloadCsv(
    "recorded_fills.csv",
    ["fill_time", "symbol", "side", "position_effect", "fill_id", "order_id", "price", "qty", "notional", "fee", "fee_currency", "realized_pnl", "run_id"],
    rows.map((row) => ({
      fill_time: row.fill_time,
      symbol: row.symbol,
      side: row.side,
      position_effect: row.position_effect,
      fill_id: row.fill_id,
      order_id: row.order_id,
      price: row.price,
      qty: row.qty,
      notional: row.notional,
      fee: row.fee,
      fee_currency: row.fee_currency,
      realized_pnl: row.realized_pnl,
      run_id: row.run_id,
    })),
  );
}

function downloadCsv(name: string, columns: string[], rows: Array<Record<string, unknown>>) {
  const header = columns.join(",");
  const body = rows.map((row) => columns.map((column) => csvValue(row[column])).join(",")).join("\n");
  const blob = new Blob([`${header}\n${body}\n`], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name;
  anchor.click();
  URL.revokeObjectURL(url);
}

function csvValue(value: unknown) {
  const raw = value === null || value === undefined ? "" : String(value);
  return `"${raw.replace(/"/g, '""')}"`;
}
