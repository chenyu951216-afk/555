export function numberValue(value: unknown): number | null {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function formatNumber(value: unknown, digits = 2): string {
  const parsed = numberValue(value);
  if (parsed === null) return "-";
  return new Intl.NumberFormat("zh-TW", { maximumFractionDigits: digits }).format(parsed);
}

export function formatPercent(value: unknown, digits = 2): string {
  const parsed = numberValue(value);
  if (parsed === null) return "-";
  return `${new Intl.NumberFormat("zh-TW", { maximumFractionDigits: digits }).format(parsed * 100)}%`;
}

export function formatCurrency(value: unknown, currency = "USDT"): string {
  const parsed = numberValue(value);
  if (parsed === null) return "-";
  return `${new Intl.NumberFormat("zh-TW", { maximumFractionDigits: 4 }).format(parsed)} ${currency}`;
}

export function formatDateTime(value?: string | null): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return new Intl.DateTimeFormat("zh-TW", {
    timeZone: "Asia/Taipei",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function formatBytes(value: number): string {
  if (!Number.isFinite(value)) return "-";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let current = value;
  let unit = 0;
  while (current >= 1024 && unit < units.length - 1) {
    current /= 1024;
    unit += 1;
  }
  return `${current.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`;
}

export function metricDisplay(key: string, value: unknown, currency = "USDT") {
  if (key.includes("return") || key.includes("drawdown") || key.includes("rate")) return formatPercent(value);
  if (key.includes("pnl") || key.includes("fee") || key.includes("slippage") || key.includes("funding")) return formatCurrency(value, currency);
  return formatNumber(value);
}

const metricLabels: Record<string, string> = {
  total_return: "總報酬",
  annualized_return: "年化報酬",
  max_drawdown: "最大回撤",
  sharpe: "夏普值",
  sortino: "索提諾值",
  calmar: "卡瑪值",
  win_rate: "勝率",
  profit_factor: "獲利因子",
  trade_count: "交易筆數",
  gross_pnl: "毛損益",
  net_pnl: "淨損益",
  fee_total: "手續費",
  slippage_total: "滑價成本",
  funding_total: "資金費",
  return_pct: "報酬率",
};

export function metricLabel(key: string) {
  return metricLabels[key] || key;
}
