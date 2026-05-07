export const API_BASE = "/api-proxy";
export const STORED_API_BASE_KEY = "oqr_api_base_url";

export type Page<T> = {
  items: T[];
  total: number;
  limit: number;
  offset: number;
};

export type RunSummary = {
  id: number;
  run_id: string;
  title?: string | null;
  strategy_name?: string | null;
  strategy_version?: string | null;
  strategy_family?: string | null;
  exchange?: string | null;
  market_type?: string | null;
  base_currency?: string | null;
  initial_capital?: number | string | null;
  timeframe?: string | null;
  start_time?: string | null;
  end_time?: string | null;
  status: string;
  tags: string[];
  config_hash?: string | null;
  result_hash?: string | null;
  imported_at: string;
  archived_at?: string | null;
  metrics: Record<string, number | string | null>;
};

export type ImportFile = {
  id: number;
  file_name: string;
  file_type?: string | null;
  file_hash: string;
  row_count?: number | null;
  validation_status: string;
};

export type RunDetail = RunSummary & {
  created_by?: string | null;
  data_source?: string | null;
  data_version?: string | null;
  code_version?: string | null;
  schema_version: string;
  notes?: string | null;
  created_at: string;
  updated_at: string;
  files: ImportFile[];
};

export type ValidationIssue = {
  level: string;
  code: string;
  message: string;
  file_name?: string | null;
  row?: number | null;
  field?: string | null;
};

export type FileValidationSummary = {
  file_name: string;
  file_type?: string | null;
  file_hash?: string | null;
  row_count?: number | null;
  columns: string[];
  validation_status: string;
  errors: ValidationIssue[];
  warnings: ValidationIssue[];
  skipped_rows: number;
};

export type ValidationReport = {
  ok: boolean;
  run_id?: string | null;
  record_start_at?: string | null;
  errors: ValidationIssue[];
  warnings: ValidationIssue[];
  files: FileValidationSummary[];
  result_hash?: string | null;
  config_hash?: string | null;
};

export type ImportResult = {
  ok: boolean;
  run_id: string;
  validation: ValidationReport;
  imported_counts: Record<string, number>;
};

export type BitgetStatus = {
  configured: boolean;
  missing?: string[];
  base_url: string;
  mode: string;
  record_start_at: string;
};

export type ProxyConnectionStatus = {
  configured: boolean;
  base_url?: string | null;
  message: string;
};

export type EquityPoint = {
  timestamp: string;
  equity: number | string;
  cash?: number | string | null;
  position_value?: number | string | null;
  unrealized_pnl?: number | string | null;
  realized_pnl?: number | string | null;
  drawdown?: number | string | null;
  exposure?: number | string | null;
  leverage?: number | string | null;
};

export type Trade = {
  id: number;
  trade_id: string;
  symbol?: string | null;
  side?: string | null;
  entry_time?: string | null;
  exit_time?: string | null;
  entry_price?: number | string | null;
  exit_price?: number | string | null;
  qty?: number | string | null;
  notional?: number | string | null;
  gross_pnl?: number | string | null;
  fee?: number | string | null;
  slippage?: number | string | null;
  funding?: number | string | null;
  net_pnl?: number | string | null;
  return_pct?: number | string | null;
  holding_minutes?: number | string | null;
  exit_reason?: string | null;
  parse_warnings?: Array<Record<string, string>> | null;
};

export type OrderRecord = {
  id: number;
  order_id: string;
  trade_id?: string | null;
  symbol?: string | null;
  side?: string | null;
  order_type?: string | null;
  order_time?: string | null;
  status?: string | null;
  price?: number | string | null;
  qty?: number | string | null;
  filled_qty?: number | string | null;
  reduce_only?: boolean | null;
  position_effect?: string | null;
  parent_order_id?: string | null;
  parse_warnings?: Array<Record<string, string>> | null;
};

export type FillRecord = {
  id: number;
  fill_id: string;
  order_id?: string | null;
  trade_id?: string | null;
  symbol?: string | null;
  side?: string | null;
  fill_time?: string | null;
  price?: number | string | null;
  qty?: number | string | null;
  notional?: number | string | null;
  fee?: number | string | null;
  fee_currency?: string | null;
  liquidity?: string | null;
  reduce_only?: boolean | null;
  position_effect?: string | null;
  realized_pnl?: number | string | null;
  parse_warnings?: Array<Record<string, string>> | null;
};

export type PositionRecord = {
  id: number;
  position_id?: string | null;
  trade_id?: string | null;
  symbol?: string | null;
  side?: string | null;
  timestamp?: string | null;
  qty?: number | string | null;
  avg_price?: number | string | null;
  market_price?: number | string | null;
  notional?: number | string | null;
  unrealized_pnl?: number | string | null;
  realized_pnl?: number | string | null;
  position_effect?: string | null;
  parse_warnings?: Array<Record<string, string>> | null;
};

export type ImportRowIssue = {
  id: number;
  file_name: string;
  row_number?: number | null;
  issue_code: string;
  message: string;
  raw_row_json?: Record<string, unknown> | null;
  created_at: string;
};

export type SymbolSummary = {
  id: number;
  symbol: string;
  trade_count?: number | null;
  gross_pnl?: number | string | null;
  net_pnl?: number | string | null;
  fee_total?: number | string | null;
  slippage_total?: number | string | null;
  funding_total?: number | string | null;
  win_rate?: number | string | null;
  avg_return?: number | string | null;
  max_drawdown?: number | string | null;
  avg_holding_minutes?: number | string | null;
  selection_count?: number | null;
};

export type CostSummary = {
  id: number;
  category: string;
  amount?: number | string | null;
  currency?: string | null;
  bps?: number | string | null;
  description?: string | null;
};

export type CandidateSnapshot = {
  id: number;
  timestamp: string;
  symbol: string;
  is_in_universe?: boolean | null;
  is_candidate?: boolean | null;
  is_selected?: boolean | null;
  rank?: number | null;
  score?: number | string | null;
  blocked_reason?: string | null;
};

export type DashboardStats = {
  total_runs: number;
  total_trades: number;
  stored_bytes: number;
  recent_runs: RunSummary[];
  runs_imported_over_time: Array<Record<string, string | number>>;
  strategy_distribution: Array<Record<string, string | number>>;
  market_type_distribution: Array<Record<string, string | number>>;
  exchange_distribution: Array<Record<string, string | number>>;
  tag_distribution: Array<Record<string, string | number>>;
  timeframe_distribution: Array<Record<string, string | number>>;
};

export type ConfigResponse = {
  run_id: string;
  config_json: Record<string, unknown>;
  config_hash: string;
};

export type ConfigDiffItem = {
  path: string;
  left: unknown;
  right: unknown;
};

export type CompareResponse = {
  run_ids: string[];
  runs: RunSummary[];
  metrics: Record<string, Record<string, number | string | null>>;
  equity: Record<string, EquityPoint[]>;
  config_diffs: Record<string, ConfigDiffItem[]>;
};

export type RecordedOrder = {
  id: number;
  run_id: string;
  run_title?: string | null;
  imported_at: string;
  order_id: string;
  trade_id?: string | null;
  symbol?: string | null;
  side?: string | null;
  order_type?: string | null;
  order_time?: string | null;
  status?: string | null;
  price?: number | string | null;
  qty?: number | string | null;
  filled_qty?: number | string | null;
  reduce_only?: boolean | null;
  position_effect?: string | null;
  parent_order_id?: string | null;
  metadata_json?: Record<string, unknown> | null;
};

export type RecordedFill = {
  id: number;
  run_id: string;
  run_title?: string | null;
  imported_at: string;
  fill_id: string;
  order_id?: string | null;
  trade_id?: string | null;
  symbol?: string | null;
  side?: string | null;
  fill_time?: string | null;
  price?: number | string | null;
  qty?: number | string | null;
  notional?: number | string | null;
  fee?: number | string | null;
  fee_currency?: string | null;
  liquidity?: string | null;
  position_effect?: string | null;
  realized_pnl?: number | string | null;
  metadata_json?: Record<string, unknown> | null;
};

export type RecordedRowIssue = {
  id: number;
  run_id: string;
  file_name: string;
  row_number?: number | null;
  issue_code: string;
  message: string;
  created_at: string;
};

export type RecordedAuditLog = {
  id: number;
  action: string;
  target_type: string;
  target_id: string;
  details_json?: Record<string, unknown> | null;
  created_at: string;
};

export type BitgetRecordedData = {
  source: string;
  record_start_at: string;
  summary: {
    real_import_runs: number;
    orders: number;
    fills: number;
    last_order_time?: string | null;
    last_fill_time?: string | null;
  };
  orders: RecordedOrder[];
  fills: RecordedFill[];
  row_issues: RecordedRowIssue[];
  audit_logs: RecordedAuditLog[];
};

export function normalizeApiBase(value: string) {
  const trimmed = value.trim().replace(/^['"]|['"]$/g, "").replace(/\/+$/, "");
  if (!trimmed) return "";
  return trimmed.endsWith("/api") ? trimmed : `${trimmed}/api`;
}

export function getStoredApiBase() {
  if (typeof window === "undefined") return "";
  return window.localStorage.getItem(STORED_API_BASE_KEY) || "";
}

export function setStoredApiBase(value: string) {
  if (typeof window === "undefined") return "";
  const normalized = normalizeApiBase(value);
  if (normalized) window.localStorage.setItem(STORED_API_BASE_KEY, normalized);
  return normalized;
}

export function clearStoredApiBase() {
  if (typeof window !== "undefined") window.localStorage.removeItem(STORED_API_BASE_KEY);
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const method = (init?.method || "GET").toUpperCase();
  const candidates = getApiCandidates(path, method === "GET" || method === "HEAD");
  const errors: string[] = [];

  for (const candidate of candidates) {
    try {
      const response = await fetchWithTimeout(candidate.url, init);
      if (!response.ok) {
        const message = await readErrorMessage(response);
        if (shouldTryNext(response.status, candidate.kind, method)) {
          errors.push(`${candidate.label}: ${message || response.status}`);
          continue;
        }
        throw new ApiHttpError(message || `API 錯誤 ${response.status}`);
      }
      if (candidate.kind === "direct" && candidate.base) {
        setStoredApiBase(candidate.base);
      }
      return response.json() as Promise<T>;
    } catch (error) {
      if (error instanceof ApiHttpError) {
        throw error;
      }
      if (isAbortError(error)) {
        errors.push(`${candidate.label}: 連線逾時`);
      } else {
        errors.push(`${candidate.label}: ${error instanceof Error ? error.message : String(error)}`);
      }
      if (!canTryNextAfterFetchError(method, candidate.kind)) break;
    }
  }

  throw new Error(`前台無法連到後端 API。已嘗試：${errors.join("；")}`);
}

export async function uploadZip<T>(path: string, file: File): Promise<T> {
  const form = new FormData();
  form.append("file", file);
  return apiFetch<T>(path, { method: "POST", body: form });
}

export function downloadUrl(path: string) {
  const stored = getStoredApiBase();
  return stored ? directPath(stored, path) : proxyPath(path);
}

function proxyPath(path: string) {
  return `${API_BASE}?target=${encodeURIComponent(path)}`;
}

function directPath(base: string, path: string) {
  return `${normalizeApiBase(base)}${path.startsWith("/") ? path : `/${path}`}`;
}

type ApiCandidate = {
  kind: "direct" | "proxy";
  label: string;
  url: string;
  base?: string;
};

function getApiCandidates(path: string, allowDiscovery: boolean): ApiCandidate[] {
  const seen = new Set<string>();
  const candidates: ApiCandidate[] = [];

  function addDirect(label: string, value?: string) {
    const base = normalizeApiBase(value || "");
    if (!base || seen.has(base)) return;
    seen.add(base);
    candidates.push({ kind: "direct", label, base, url: directPath(base, path) });
  }

  addDirect("設定頁保存的後端網址", getStoredApiBase());
  addDirect("NEXT_PUBLIC_API_BASE_URL", process.env.NEXT_PUBLIC_API_BASE_URL);
  addDirect("NEXT_PUBLIC_API_URL", process.env.NEXT_PUBLIC_API_URL);
  addDirect("NEXT_PUBLIC_BACKEND_URL", process.env.NEXT_PUBLIC_BACKEND_URL);

  if (allowDiscovery && typeof window !== "undefined") {
    addDirect("同網域 /api", `${window.location.origin}/api`);
  }

  candidates.push({ kind: "proxy", label: "前台代理", url: proxyPath(path) });
  return candidates;
}

async function fetchWithTimeout(url: string, init?: RequestInit) {
  const controller = init?.signal ? null : new AbortController();
  const timeout = controller && typeof window !== "undefined" ? window.setTimeout(() => controller.abort(), 30_000) : null;
  try {
    return await fetch(url, {
      ...init,
      signal: init?.signal || controller?.signal,
      headers: buildHeaders(init),
    });
  } finally {
    if (timeout) window.clearTimeout(timeout);
  }
}

function buildHeaders(init?: RequestInit) {
  if (init?.body instanceof FormData) return init.headers;
  const headers = new Headers(init?.headers);
  if (!headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  return headers;
}

async function readErrorMessage(response: Response) {
  try {
    const payload = await response.json();
    if (typeof payload.detail === "string") return payload.detail;
    if (typeof payload.message === "string") return payload.message;
    return JSON.stringify(payload.detail || payload);
  } catch {
    return response.text();
  }
}

function shouldTryNext(status: number, kind: ApiCandidate["kind"], method: string) {
  if (method !== "GET" && method !== "HEAD") return false;
  return kind === "direct" && [404, 405, 502, 503, 504].includes(status);
}

function canTryNextAfterFetchError(method: string, kind: ApiCandidate["kind"]) {
  return (method === "GET" || method === "HEAD") || kind === "direct";
}

function isAbortError(error: unknown) {
  return error instanceof DOMException && error.name === "AbortError";
}

class ApiHttpError extends Error {}
