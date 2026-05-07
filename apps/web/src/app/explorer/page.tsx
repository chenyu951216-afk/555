"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Database } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { Button, ErrorState, Input, PageHeader, Panel, Select } from "@/components/ui";

const tables = ["runs", "metrics", "trades", "orders", "fills", "positions", "equity", "symbols", "costs", "candidates"];
const tableLabels: Record<string, string> = {
  runs: "紀錄主表",
  metrics: "績效指標",
  trades: "交易紀錄",
  orders: "訂單",
  fills: "成交",
  positions: "持倉",
  equity: "資金曲線",
  symbols: "交易對摘要",
  costs: "成本摘要",
  candidates: "候選標的",
};

export default function ExplorerPage() {
  const [table, setTable] = useState("orders");
  const [runId, setRunId] = useState("");
  const [sortBy, setSortBy] = useState("");
  const mutation = useMutation({
    mutationFn: () =>
      apiFetch<{ items: Array<Record<string, unknown>>; total: number }>("/explorer/query", {
        method: "POST",
        body: JSON.stringify({ table, run_id: runId || null, sort_by: sortBy || null, limit: 100, offset: 0 }),
      }),
  });
  const rows = mutation.data?.items || [];
  const columns = rows[0] ? Object.keys(rows[0]) : [];

  return (
    <div>
      <PageHeader title="資料表查詢" description="安全查詢允許的資料庫表格，方便確認目前實際寫入的內容。" />
      <Panel>
        <div className="grid gap-3 md:grid-cols-[180px_1fr_180px_120px]">
          <Select value={table} onChange={(event) => setTable(event.target.value)}>
            {tables.map((item) => <option key={item} value={item}>{tableLabels[item]} ({item})</option>)}
          </Select>
          <Input value={runId} onChange={(event) => setRunId(event.target.value)} placeholder="紀錄代號，可留空" />
          <Input value={sortBy} onChange={(event) => setSortBy(event.target.value)} placeholder="排序欄位，可留空" />
          <Button onClick={() => mutation.mutate()}><Database size={16} />查詢</Button>
        </div>
      </Panel>
      {mutation.error ? <div className="mt-4"><ErrorState message={(mutation.error as Error).message} /></div> : null}
      <Panel className="mt-5">
        <div className="mb-3 text-sm font-semibold">查詢結果 {mutation.data ? `(${mutation.data.total})` : ""}</div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px] text-left text-xs">
            <thead className="border-b border-line text-graphite"><tr>{columns.map((column) => <th key={column} className="py-2">{column}</th>)}</tr></thead>
            <tbody>
              {rows.map((row, index) => (
                <tr key={index} className="border-b border-line/70">{columns.map((column) => <td key={column} className="max-w-80 truncate py-2">{JSON.stringify(row[column])}</td>)}</tr>
              ))}
              {!rows.length ? <tr><td className="py-5 text-graphite">尚無查詢結果</td></tr> : null}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}
