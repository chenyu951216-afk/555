"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { GitCompareArrows } from "lucide-react";
import { apiFetch, CompareResponse } from "@/lib/api";
import { formatNumber, metricDisplay, metricLabel } from "@/lib/format";
import { OverlayEquityChart } from "@/components/charts";
import { Button, ErrorState, Input, LoadingState, PageHeader, Panel } from "@/components/ui";

const keys = ["total_return", "annualized_return", "max_drawdown", "sharpe", "sortino", "calmar", "win_rate", "profit_factor", "trade_count", "gross_pnl", "net_pnl"];

export default function ComparePage() {
  return (
    <Suspense fallback={<LoadingState />}>
      <CompareContent />
    </Suspense>
  );
}

function CompareContent() {
  const search = useSearchParams();
  const [runIds, setRunIds] = useState(search.get("run_ids") || "");
  const [active, setActive] = useState(search.get("run_ids") || "");
  const { data, error, isLoading } = useQuery({
    queryKey: ["compare", active],
    enabled: active.split(",").filter(Boolean).length >= 2,
    queryFn: () => apiFetch<CompareResponse>(`/compare?run_ids=${encodeURIComponent(active)}`),
  });

  return (
    <div>
      <PageHeader title="紀錄比較" description="比較多筆紀錄的指標、資金曲線與設定差異。" />
      <Panel>
        <div className="flex flex-col gap-2 md:flex-row">
          <Input className="w-full" value={runIds} onChange={(event) => setRunIds(event.target.value)} placeholder="紀錄代號_1,紀錄代號_2,紀錄代號_3" />
          <Button onClick={() => setActive(runIds)}><GitCompareArrows size={16} />比較</Button>
        </div>
      </Panel>
      {isLoading ? <div className="mt-4"><LoadingState /></div> : null}
      {error ? <div className="mt-4"><ErrorState message={(error as Error).message} /></div> : null}
      {data ? (
        <>
          <Panel className="mt-5">
            <div className="mb-3 text-sm font-semibold">資金曲線疊圖</div>
            <OverlayEquityChart series={data.equity} />
          </Panel>
          <Panel className="mt-5">
            <div className="mb-3 text-sm font-semibold">指標比較</div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] text-left text-sm">
                <thead className="border-b border-line text-xs text-graphite">
                  <tr>
                    <th className="py-2">metric</th>
                    {data.run_ids.map((runId) => <th key={runId}>{runId}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {keys.map((key) => (
                    <tr key={key} className="border-b border-line/70">
                      <td className="py-2 font-medium">{metricLabel(key)}</td>
                      {data.run_ids.map((runId) => <td key={runId}>{metricDisplay(key, data.metrics[runId]?.[key])}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
          <Panel className="mt-5">
            <div className="mb-3 text-sm font-semibold">設定差異</div>
            <div className="space-y-4">
              {Object.entries(data.config_diffs).map(([pair, diffs]) => (
                <div key={pair} className="rounded-md border border-line bg-paper p-3">
                  <div className="mb-2 text-xs font-semibold text-graphite">{pair}</div>
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[720px] text-left text-xs">
                      <thead><tr className="border-b border-line"><th className="py-2">路徑</th><th>左側</th><th>右側</th></tr></thead>
                      <tbody>
                        {diffs.map((item, index) => (
                          <tr key={`${item.path}-${index}`} className="border-b border-line/70">
                            <td className="py-2 font-medium">{item.path}</td>
                            <td><code>{JSON.stringify(item.left)}</code></td>
                            <td><code>{JSON.stringify(item.right)}</code></td>
                          </tr>
                        ))}
                        {!diffs.length ? <tr><td className="py-3 text-graphite" colSpan={3}>無差異</td></tr> : null}
                      </tbody>
                    </table>
                  </div>
                </div>
              ))}
            </div>
          </Panel>
          <Panel className="mt-5">
            <div className="mb-3 text-sm font-semibold">交易筆數</div>
            <div className="grid gap-3 md:grid-cols-3">
              {data.run_ids.map((runId) => <div key={runId} className="rounded-md border border-line bg-paper p-3 text-sm"><div className="text-xs text-graphite">{runId}</div><div className="mt-2 text-xl font-semibold">{formatNumber(data.metrics[runId]?.trade_count, 0)}</div></div>)}
            </div>
          </Panel>
        </>
      ) : null}
    </div>
  );
}
