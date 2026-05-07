"use client";

import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { EquityPoint } from "@/lib/api";
import { numberValue } from "@/lib/format";

const COLORS = ["#176b69", "#a66416", "#a23b4b", "#5d6b3c", "#6b5b95", "#357266", "#8c5f38"];

export function DistributionChart({ data, nameKey = "name", valueKey = "count" }: { data: Array<Record<string, string | number>>; nameKey?: string; valueKey?: string }) {
  if (!data.length) return <div className="grid h-56 place-items-center text-sm text-graphite">尚無資料</div>;
  return (
    <div className="h-56">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie data={data} dataKey={valueKey} nameKey={nameKey} outerRadius={78} innerRadius={42}>
            {data.map((_, index) => (
              <Cell key={index} fill={COLORS[index % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}

export function TimeBarChart({ data, xKey = "date", valueKey = "count" }: { data: Array<Record<string, string | number>>; xKey?: string; valueKey?: string }) {
  if (!data.length) return <div className="grid h-56 place-items-center text-sm text-graphite">尚無資料</div>;
  return (
    <div className="h-56">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data}>
          <CartesianGrid stroke="#dedbd2" vertical={false} />
          <XAxis dataKey={xKey} tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip />
          <Bar dataKey={valueKey} fill="#176b69" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function EquityChart({ data }: { data: EquityPoint[] }) {
  const normalized = data.map((point) => ({
    timestamp: new Date(point.timestamp).toLocaleString("zh-TW", { timeZone: "Asia/Taipei", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }),
    equity: numberValue(point.equity),
    drawdown: numberValue(point.drawdown),
    exposure: numberValue(point.exposure),
    leverage: numberValue(point.leverage),
  }));
  if (!normalized.length) return <div className="grid h-72 place-items-center text-sm text-graphite">尚無資金曲線資料</div>;
  return (
    <div className="h-72">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={normalized}>
          <CartesianGrid stroke="#dedbd2" vertical={false} />
          <XAxis dataKey="timestamp" tick={{ fontSize: 10 }} minTickGap={40} />
          <YAxis yAxisId="left" tick={{ fontSize: 11 }} />
          <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11 }} />
          <Tooltip />
          <Area yAxisId="left" type="monotone" dataKey="equity" stroke="#176b69" fill="#176b69" fillOpacity={0.14} name="資金" />
          <Line yAxisId="right" type="monotone" dataKey="drawdown" stroke="#a23b4b" dot={false} name="回撤" />
          <Line yAxisId="right" type="monotone" dataKey="exposure" stroke="#a66416" dot={false} name="曝險" />
          <Line yAxisId="right" type="monotone" dataKey="leverage" stroke="#6b5b95" dot={false} name="槓桿" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export function OverlayEquityChart({ series }: { series: Record<string, EquityPoint[]> }) {
  const keys = Object.keys(series);
  const byIndex: Array<Record<string, string | number | null>> = [];
  keys.forEach((runId) => {
    series[runId].forEach((point, index) => {
      byIndex[index] = byIndex[index] || { index };
      byIndex[index][runId] = numberValue(point.equity);
      byIndex[index][`${runId}_drawdown`] = numberValue(point.drawdown);
    });
  });
  if (!byIndex.length) return <div className="grid h-72 place-items-center text-sm text-graphite">尚無比較資料</div>;
  return (
    <div className="h-72">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={byIndex}>
          <CartesianGrid stroke="#dedbd2" vertical={false} />
          <XAxis dataKey="index" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip />
          {keys.map((runId, index) => (
            <Line key={runId} type="monotone" dataKey={runId} stroke={COLORS[index % COLORS.length]} dot={false} name={runId} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function CostBarChart({ data }: { data: Array<{ category: string; amount?: number | string | null }> }) {
  const normalized = data.map((item) => ({ category: item.category, amount: Math.abs(numberValue(item.amount) || 0) }));
  if (!normalized.length) return <div className="grid h-56 place-items-center text-sm text-graphite">尚無成本資料</div>;
  return (
    <div className="h-56">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={normalized}>
          <CartesianGrid stroke="#dedbd2" vertical={false} />
          <XAxis dataKey="category" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip />
          <Bar dataKey="amount" fill="#a66416" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
