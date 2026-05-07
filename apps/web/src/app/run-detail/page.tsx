"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import type { ReactNode } from "react";
import { Suspense, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Copy, Download, FileText, MessageSquarePlus } from "lucide-react";
import {
  apiFetch,
  CandidateSnapshot,
  ConfigResponse,
  CostSummary,
  downloadUrl,
  EquityPoint,
  FillRecord,
  ImportRowIssue,
  OrderRecord,
  Page,
  PositionRecord,
  RunDetail,
  SymbolSummary,
  Trade,
} from "@/lib/api";
import { formatCurrency, formatDateTime, formatNumber, metricDisplay, metricLabel } from "@/lib/format";
import { CostBarChart, EquityChart } from "@/components/charts";
import { Badge, Button, ErrorState, Input, LoadingState, PageHeader, Panel, StatCard } from "@/components/ui";

const metricCards = [
  "total_return",
  "annualized_return",
  "max_drawdown",
  "sharpe",
  "sortino",
  "calmar",
  "win_rate",
  "profit_factor",
  "trade_count",
  "gross_pnl",
  "net_pnl",
  "fee_total",
  "slippage_total",
  "funding_total",
];

export default function RunDetailPage() {
  return (
    <Suspense fallback={<LoadingState />}>
      <RunDetailContent />
    </Suspense>
  );
}

function RunDetailContent() {
  const searchParams = useSearchParams();
  const runId = searchParams.get("run_id") || "";
  const queryEnabled = Boolean(runId);
  const [symbol, setSymbol] = useState("");
  const [side, setSide] = useState("");
  const [note, setNote] = useState("");

  const runQuery = useQuery({ queryKey: ["run", runId], queryFn: () => apiFetch<RunDetail>(`/runs/${runId}`), enabled: queryEnabled });
  const equityQuery = useQuery({ queryKey: ["equity", runId], queryFn: () => apiFetch<EquityPoint[]>(`/runs/${runId}/equity`), enabled: queryEnabled });
  const configQuery = useQuery({ queryKey: ["config", runId], queryFn: () => apiFetch<ConfigResponse>(`/runs/${runId}/config`), retry: false, enabled: queryEnabled });
  const tradesPath = useMemo(() => {
    const params = new URLSearchParams({ limit: "100" });
    if (symbol) params.set("symbol", symbol);
    if (side) params.set("side", side);
    return `/runs/${runId}/trades?${params.toString()}`;
  }, [runId, side, symbol]);
  const tradesQuery = useQuery({ queryKey: ["trades", tradesPath], queryFn: () => apiFetch<Page<Trade>>(tradesPath), enabled: queryEnabled });
  const ordersQuery = useQuery({ queryKey: ["orders", runId], queryFn: () => apiFetch<Page<OrderRecord>>(`/runs/${runId}/orders?limit=100`), enabled: queryEnabled });
  const fillsQuery = useQuery({ queryKey: ["fills", runId], queryFn: () => apiFetch<Page<FillRecord>>(`/runs/${runId}/fills?limit=100`), enabled: queryEnabled });
  const positionsQuery = useQuery({ queryKey: ["positions", runId], queryFn: () => apiFetch<Page<PositionRecord>>(`/runs/${runId}/positions?limit=100`), enabled: queryEnabled });
  const rowIssuesQuery = useQuery({ queryKey: ["row-issues", runId], queryFn: () => apiFetch<Page<ImportRowIssue>>(`/runs/${runId}/import-row-issues?limit=100`), enabled: queryEnabled });
  const symbolsQuery = useQuery({ queryKey: ["symbols", runId], queryFn: () => apiFetch<Page<SymbolSummary>>(`/runs/${runId}/symbols?limit=200`), enabled: queryEnabled });
  const costsQuery = useQuery({ queryKey: ["costs", runId], queryFn: () => apiFetch<CostSummary[]>(`/runs/${runId}/costs`), enabled: queryEnabled });
  const candidatesQuery = useQuery({ queryKey: ["candidates", runId], queryFn: () => apiFetch<Page<CandidateSnapshot>>(`/runs/${runId}/candidates?limit=100`), enabled: queryEnabled });
  const notesQuery = useQuery({ queryKey: ["notes", runId], queryFn: () => apiFetch<Array<{ id: number; content: string; created_at: string }>>(`/runs/${runId}/notes`), enabled: queryEnabled });

  if (!runId) return <ErrorState message="缺少紀錄代號。" />;
  if (runQuery.isLoading) return <LoadingState />;
  if (runQuery.error) return <ErrorState message={(runQuery.error as Error).message} />;
  const run = runQuery.data;
  if (!run) return null;

  async function addNote() {
    if (!note.trim()) return;
    await apiFetch(`/runs/${runId}/notes`, { method: "POST", body: JSON.stringify({ content: note }) });
    setNote("");
    notesQuery.refetch();
  }

  function downloadConfig() {
    const blob = new Blob([JSON.stringify(configQuery.data?.config_json || {}, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${runId}_config.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div>
      <PageHeader
        title={run.title || run.run_id}
        description={`${run.strategy_name || "未知策略"} / ${run.strategy_version || "未知版本"} / ${run.exchange || "未知交易所"} / ${run.market_type || "未知市場"}`}
        action={<Link className="inline-flex h-10 items-center rounded-md border border-line bg-white px-3 text-sm" href={`/compare?run_ids=${runId}`}>比較</Link>}
      />

      <Panel>
        <div className="grid gap-3 text-sm md:grid-cols-4">
          <div>紀錄代號：<span className="font-medium text-teal">{run.run_id}</span></div>
          <div>時間週期：{run.timeframe || "-"}</div>
          <div>回測區間：{formatDateTime(run.start_time)} 至 {formatDateTime(run.end_time)}</div>
          <div>匯入時間：{formatDateTime(run.imported_at)}</div>
          <div>基準幣：{run.base_currency || "-"}</div>
          <div>初始資金：{formatCurrency(run.initial_capital, run.base_currency || "USDT")}</div>
          <div>設定雜湊：<span className="break-all text-xs">{run.config_hash || "-"}</span></div>
          <div>結果雜湊：<span className="break-all text-xs">{run.result_hash || "-"}</span></div>
        </div>
        <div className="mt-3 flex flex-wrap gap-1">{run.tags.map((tag) => <Badge key={tag}>{tag}</Badge>)}</div>
      </Panel>

      <div className="mt-5 grid gap-3 md:grid-cols-3 xl:grid-cols-7">
        {metricCards.map((key) => (
          <StatCard key={key} label={metricLabel(key)} value={metricDisplay(key, run.metrics[key], run.base_currency || "USDT")} />
        ))}
      </div>

      <Panel className="mt-5">
        <div className="mb-3 text-sm font-semibold">資金曲線</div>
        <EquityChart data={equityQuery.data || []} />
      </Panel>

      <div className="mt-5 grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
        <Panel>
          <div className="mb-3 flex items-center justify-between">
            <div className="text-sm font-semibold">設定檔</div>
            <div className="flex gap-2">
              <Button onClick={() => navigator.clipboard.writeText(JSON.stringify(configQuery.data?.config_json || {}, null, 2))}><Copy size={15} />複製</Button>
              <Button onClick={downloadConfig}><Download size={15} />下載</Button>
            </div>
          </div>
          <pre className="max-h-96 overflow-auto rounded-md bg-paper p-3 text-xs leading-5">{JSON.stringify(configQuery.data?.config_json || {}, null, 2)}</pre>
        </Panel>
        <Panel>
          <div className="mb-3 text-sm font-semibold">成本</div>
          <CostBarChart data={costsQuery.data || []} />
          <SimpleTable
            columns={["類別", "金額", "幣別", "bps"]}
            rows={(costsQuery.data || []).map((item) => ({
              類別: item.category,
              金額: formatCurrency(item.amount, item.currency || run.base_currency || "USDT"),
              幣別: item.currency || "-",
              bps: formatNumber(item.bps),
            }))}
          />
        </Panel>
      </div>

      <Panel className="mt-5">
        <div className="mb-3 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div className="text-sm font-semibold">交易</div>
          <div className="flex flex-wrap gap-2">
            <Input value={symbol} onChange={(event) => setSymbol(event.target.value)} placeholder="交易對" />
            <Input value={side} onChange={(event) => setSide(event.target.value)} placeholder="方向" />
            <a className="inline-flex h-10 items-center gap-2 rounded-md border border-line bg-white px-3 text-sm" href={downloadUrl(`/runs/${runId}/trades/export`)}><Download size={15} />CSV</a>
          </div>
        </div>
        <SimpleTable
          columns={["交易ID", "交易對", "方向", "進場", "出場", "數量", "名目金額", "淨損益", "報酬", "出場原因"]}
          rows={(tradesQuery.data?.items || []).map((trade) => ({
            交易ID: <span className="font-mono text-xs">{trade.trade_id}</span>,
            交易對: trade.symbol || "-",
            方向: trade.side || "-",
            進場: formatDateTime(trade.entry_time),
            出場: formatDateTime(trade.exit_time),
            數量: formatNumber(trade.qty),
            名目金額: formatCurrency(trade.notional, run.base_currency || "USDT"),
            淨損益: formatCurrency(trade.net_pnl, run.base_currency || "USDT"),
            報酬: metricDisplay("return_pct", trade.return_pct, run.base_currency || "USDT"),
            出場原因: trade.exit_reason || "-",
          }))}
        />
      </Panel>

      <div className="mt-5 grid gap-4 xl:grid-cols-2">
        <Panel>
          <div className="mb-3 text-sm font-semibold">訂單</div>
          <SimpleTable
            columns={["時間", "訂單ID", "交易對", "方向", "倉位效果", "只減倉", "價格", "數量", "狀態"]}
            rows={(ordersQuery.data?.items || []).map((item) => ({
              時間: formatDateTime(item.order_time),
              訂單ID: <span className="font-mono text-xs">{item.order_id}</span>,
              交易對: item.symbol || "-",
              方向: item.side || "-",
              倉位效果: item.position_effect || "-",
              只減倉: item.reduce_only === null || item.reduce_only === undefined ? "-" : String(item.reduce_only),
              價格: formatNumber(item.price, 8),
              數量: formatNumber(item.qty, 8),
              狀態: item.status || "-",
            }))}
          />
        </Panel>
        <Panel>
          <div className="mb-3 text-sm font-semibold">成交</div>
          <SimpleTable
            columns={["時間", "成交ID", "訂單ID", "交易對", "方向", "倉位效果", "價格", "數量", "手續費", "已實現損益"]}
            rows={(fillsQuery.data?.items || []).map((item) => ({
              時間: formatDateTime(item.fill_time),
              成交ID: <span className="font-mono text-xs">{item.fill_id}</span>,
              訂單ID: item.order_id || "-",
              交易對: item.symbol || "-",
              方向: item.side || "-",
              倉位效果: item.position_effect || "-",
              價格: formatNumber(item.price, 8),
              數量: formatNumber(item.qty, 8),
              手續費: formatCurrency(item.fee, item.fee_currency || run.base_currency || "USDT"),
              已實現損益: formatCurrency(item.realized_pnl, run.base_currency || "USDT"),
            }))}
          />
        </Panel>
      </div>

      <div className="mt-5 grid gap-4 xl:grid-cols-2">
        <Panel>
          <div className="mb-3 text-sm font-semibold">持倉</div>
          <SimpleTable
            columns={["時間", "持倉ID", "交易對", "方向", "倉位效果", "數量", "均價", "已實現損益"]}
            rows={(positionsQuery.data?.items || []).map((item) => ({
              時間: formatDateTime(item.timestamp),
              持倉ID: item.position_id || "-",
              交易對: item.symbol || "-",
              方向: item.side || "-",
              倉位效果: item.position_effect || "-",
              數量: formatNumber(item.qty, 8),
              均價: formatNumber(item.avg_price, 8),
              已實現損益: formatCurrency(item.realized_pnl, run.base_currency || "USDT"),
            }))}
          />
        </Panel>
        <Panel>
          <div className="mb-3 text-sm font-semibold">匯入問題</div>
          <SimpleTable
            columns={["檔案", "列", "代碼", "訊息"]}
            rows={(rowIssuesQuery.data?.items || []).map((item) => ({
              檔案: item.file_name,
              列: item.row_number ?? "-",
              代碼: item.issue_code,
              訊息: item.message,
            }))}
          />
        </Panel>
      </div>

      <div className="mt-5 grid gap-4 xl:grid-cols-2">
        <Panel>
          <div className="mb-3 text-sm font-semibold">交易對摘要</div>
          <SimpleTable
            columns={["交易對", "交易筆數", "淨損益", "手續費", "勝率", "入選次數"]}
            rows={(symbolsQuery.data?.items || []).map((item) => ({
              交易對: item.symbol,
              交易筆數: item.trade_count ?? "-",
              淨損益: formatCurrency(item.net_pnl, run.base_currency || "USDT"),
              手續費: formatCurrency(item.fee_total, run.base_currency || "USDT"),
              勝率: metricDisplay("win_rate", item.win_rate),
              入選次數: item.selection_count ?? "-",
            }))}
          />
        </Panel>
        <Panel>
          <div className="mb-3 text-sm font-semibold">候選標的快照</div>
          <SimpleTable
            columns={["時間", "交易對", "在範圍內", "候選", "已選取", "排名", "分數"]}
            rows={(candidatesQuery.data?.items || []).map((item) => ({
              時間: formatDateTime(item.timestamp),
              交易對: item.symbol,
              在範圍內: item.is_in_universe === null || item.is_in_universe === undefined ? "-" : String(item.is_in_universe),
              候選: item.is_candidate === null || item.is_candidate === undefined ? "-" : String(item.is_candidate),
              已選取: item.is_selected === null || item.is_selected === undefined ? "-" : String(item.is_selected),
              排名: item.rank ?? "-",
              分數: formatNumber(item.score, 4),
            }))}
          />
        </Panel>
      </div>

      <div className="mt-5 grid gap-4 xl:grid-cols-2">
        <Panel>
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold"><MessageSquarePlus size={16} />備註</div>
          <div className="flex gap-2">
            <Input value={note} onChange={(event) => setNote(event.target.value)} placeholder="新增備註" className="w-full" />
            <Button onClick={addNote}>新增</Button>
          </div>
          <div className="mt-3 space-y-2">
            {(notesQuery.data || []).map((item) => (
              <div key={item.id} className="rounded-md border border-line bg-paper p-3 text-sm">
                <div className="mb-1 text-xs text-graphite">{formatDateTime(item.created_at)}</div>
                <div className="whitespace-pre-wrap">{item.content}</div>
              </div>
            ))}
          </div>
        </Panel>
        <Panel>
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold"><FileText size={16} />檔案</div>
          <SimpleTable
            columns={["檔名", "類型", "列數", "狀態", "hash", "下載"]}
            rows={run.files.map((file) => ({
              檔名: file.file_name,
              類型: file.file_type || "-",
              列數: file.row_count ?? "-",
              狀態: file.validation_status,
              hash: <span className="inline-block max-w-40 truncate font-mono text-xs">{file.file_hash}</span>,
              下載: <a className="text-teal" href={downloadUrl(`/runs/${runId}/files/${file.id}/download`)}>下載</a>,
            }))}
          />
        </Panel>
      </div>
    </div>
  );
}

function SimpleTable({ columns, rows }: { columns: string[]; rows: Array<Record<string, ReactNode>> }) {
  if (!rows.length) return <div className="rounded-md border border-dashed border-line bg-paper p-5 text-center text-sm text-graphite">尚無資料</div>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[560px] text-left text-sm">
        <thead className="border-b border-line text-xs text-graphite">
          <tr>{columns.map((column) => <th key={column} className="py-2 pr-3">{column}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index} className="border-b border-line/70 align-top">
              {columns.map((column) => <td key={column} className="max-w-[280px] break-words py-2 pr-3">{row[column] ?? "-"}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
