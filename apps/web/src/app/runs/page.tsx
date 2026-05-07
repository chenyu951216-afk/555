"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Archive, GitCompareArrows, Search } from "lucide-react";
import { apiFetch, Page, RunSummary } from "@/lib/api";
import { formatCurrency, formatDateTime, formatNumber, metricDisplay } from "@/lib/format";
import { Badge, Button, ErrorState, Input, LoadingState, PageHeader, Panel, Select } from "@/components/ui";

export default function RunsPage() {
  const [q, setQ] = useState("");
  const [marketType, setMarketType] = useState("");
  const [sortBy, setSortBy] = useState("imported_at");
  const [sortDir, setSortDir] = useState("desc");
  const [selected, setSelected] = useState<string[]>([]);

  const query = useMemo(() => {
    const params = new URLSearchParams({ limit: "100", sort_by: sortBy, sort_dir: sortDir });
    if (q) params.set("q", q);
    if (marketType) params.set("market_type", marketType);
    return `/runs?${params.toString()}`;
  }, [q, marketType, sortBy, sortDir]);

  const { data, error, isLoading, refetch } = useQuery({ queryKey: ["runs", query], queryFn: () => apiFetch<Page<RunSummary>>(query) });

  async function archive(runId: string) {
    await apiFetch(`/runs/${runId}/archive`, { method: "POST" });
    refetch();
  }

  function toggle(runId: string) {
    setSelected((current) => (current.includes(runId) ? current.filter((item) => item !== runId) : [...current, runId]));
  }

  if (isLoading) return <LoadingState />;
  if (error) return <ErrorState message={(error as Error).message} />;

  return (
    <div>
      <PageHeader
        title="回測紀錄"
        description="已匯入的回測與交易紀錄。"
        action={selected.length >= 2 ? <Link className="inline-flex h-10 items-center gap-2 rounded-md bg-teal px-3 text-sm text-white" href={`/compare?run_ids=${selected.join(",")}`}><GitCompareArrows size={16} />比較</Link> : null}
      />
      <Panel>
        <div className="mb-4 grid gap-3 md:grid-cols-[1fr_160px_180px_130px]">
          <div className="relative">
            <Search className="absolute left-3 top-3 text-graphite" size={16} />
            <Input value={q} onChange={(event) => setQ(event.target.value)} placeholder="搜尋紀錄代號、標題、策略" className="w-full pl-9" />
          </div>
          <Select value={marketType} onChange={(event) => setMarketType(event.target.value)}>
            <option value="">全部市場</option>
            <option value="spot">現貨</option>
            <option value="perp">永續</option>
            <option value="futures">期貨</option>
            <option value="options">選擇權</option>
            <option value="other">其他</option>
          </Select>
          <Select value={sortBy} onChange={(event) => setSortBy(event.target.value)}>
            <option value="imported_at">匯入時間</option>
            <option value="start_time">開始時間</option>
            <option value="total_return">總報酬</option>
            <option value="max_drawdown">最大回撤</option>
            <option value="sharpe">夏普值</option>
            <option value="trade_count">交易筆數</option>
          </Select>
          <Select value={sortDir} onChange={(event) => setSortDir(event.target.value)}>
            <option value="desc">由新到舊</option>
            <option value="asc">由舊到新</option>
          </Select>
        </div>
        <div className="overflow-x-auto scrollbar-thin">
          <table className="w-full min-w-[1280px] text-left text-sm">
            <thead className="border-b border-line text-xs text-graphite">
              <tr>
                <th className="py-2">比較</th>
                <th>紀錄代號</th>
                <th>標題</th>
                <th>策略</th>
                <th>版本</th>
                <th>交易所</th>
                <th>市場</th>
                <th>週期</th>
                <th>開始 / 結束</th>
                <th>初始資金</th>
                <th>總報酬</th>
                <th>最大回撤</th>
                <th>夏普值</th>
                <th>交易數</th>
                <th>標籤</th>
                <th>匯入時間</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {data?.items.map((run) => (
                <tr key={run.run_id} className="border-b border-line/70 align-top">
                  <td className="py-2"><input type="checkbox" checked={selected.includes(run.run_id)} onChange={() => toggle(run.run_id)} /></td>
                  <td className="font-medium text-teal"><Link href={`/run-detail?run_id=${encodeURIComponent(run.run_id)}`}>{run.run_id}</Link></td>
                  <td>{run.title || "-"}</td>
                  <td>{run.strategy_name || "-"}</td>
                  <td>{run.strategy_version || "-"}</td>
                  <td>{run.exchange || "-"}</td>
                  <td>{run.market_type || "-"}</td>
                  <td>{run.timeframe || "-"}</td>
                  <td className="text-xs">{formatDateTime(run.start_time)}<br />{formatDateTime(run.end_time)}</td>
                  <td>{formatCurrency(run.initial_capital, run.base_currency || "USDT")}</td>
                  <td>{metricDisplay("total_return", run.metrics.total_return, run.base_currency || "USDT")}</td>
                  <td>{metricDisplay("max_drawdown", run.metrics.max_drawdown, run.base_currency || "USDT")}</td>
                  <td>{formatNumber(run.metrics.sharpe)}</td>
                  <td>{formatNumber(run.metrics.trade_count, 0)}</td>
                  <td><div className="flex max-w-48 flex-wrap gap-1">{run.tags.map((tag) => <Badge key={tag}>{tag}</Badge>)}</div></td>
                  <td className="text-xs">{formatDateTime(run.imported_at)}</td>
                  <td><Button title="封存" onClick={() => archive(run.run_id)}><Archive size={15} /></Button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}
