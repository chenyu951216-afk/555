"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, ClipboardList, FileArchive, Upload, XCircle } from "lucide-react";
import { apiFetch, BitgetStatus, ImportResult, uploadZip, ValidationReport } from "@/lib/api";
import { formatDateTime, formatNumber } from "@/lib/format";
import { Button, ErrorState, PageHeader, Panel, Select } from "@/components/ui";

const DEFAULT_START = "2026-05-08T00:00";
const DEFAULT_END = "2026-05-08T23:59";

const PRODUCT_TYPES = [
  { value: "USDT-FUTURES", label: "USDT 本位合約" },
  { value: "USDC-FUTURES", label: "USDC 本位合約" },
  { value: "COIN-FUTURES", label: "幣本位合約" },
];

export default function ImportPage() {
  const [file, setFile] = useState<File | null>(null);
  const [report, setReport] = useState<ValidationReport | null>(null);
  const [importedCounts, setImportedCounts] = useState<Record<string, number> | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [bitgetRunId, setBitgetRunId] = useState(`bitget_${new Date().toISOString().slice(0, 10).replace(/-/g, "")}_readonly_001`);
  const [bitgetTitle, setBitgetTitle] = useState("Bitget 唯讀下單成交紀錄匯入");
  const [bitgetProductType, setBitgetProductType] = useState("USDT-FUTURES");
  const [bitgetSymbols, setBitgetSymbols] = useState("");
  const [bitgetStart, setBitgetStart] = useState(DEFAULT_START);
  const [bitgetEnd, setBitgetEnd] = useState(DEFAULT_END);
  const bitgetStatus = useQuery({ queryKey: ["bitget-status"], queryFn: () => apiFetch<BitgetStatus>("/bitget/status") });

  async function validate() {
    if (!file) return;
    setBusy(true);
    setMessage(null);
    setImportedCounts(null);
    try {
      const next = await uploadZip<ValidationReport>("/import/validate", file);
      setReport(next);
    } catch (error) {
      setMessage((error as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function importZip() {
    if (!file) return;
    setBusy(true);
    setMessage(null);
    setImportedCounts(null);
    try {
      const result = await uploadZip<ImportResult>("/import/backtest-zip", file);
      setReport(result.validation);
      setImportedCounts(result.imported_counts);
      setRunId(result.run_id);
    } catch (error) {
      setMessage((error as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function importBitget() {
    setBusy(true);
    setMessage(null);
    setImportedCounts(null);
    try {
      const result = await apiFetch<ImportResult>("/bitget/import-readonly", {
        method: "POST",
        body: JSON.stringify({
          run_id: bitgetRunId,
          title: bitgetTitle,
          product_type: bitgetProductType,
          symbols: bitgetSymbols.split(",").map((item) => item.trim()).filter(Boolean),
          start_time: `${bitgetStart}:00+08:00`,
          end_time: `${bitgetEnd}:00+08:00`,
          base_currency: bitgetProductType === "USDC-FUTURES" ? "USDC" : "USDT",
          max_pages: 10,
        }),
      });
      setRunId(result.run_id);
      setReport(result.validation);
      setImportedCounts(result.imported_counts);
    } catch (error) {
      setMessage((error as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="匯入中心"
        description="只計入台灣時間 2026/05/08 00:00 之後建立的真實下單與成交資料。"
        action={
          <Link className="inline-flex h-10 items-center gap-2 rounded-md bg-teal px-3 text-sm text-white" href="/recorded">
            <ClipboardList size={16} />
            計入資料
          </Link>
        }
      />
      <Panel>
        <label className="flex min-h-44 cursor-pointer flex-col items-center justify-center rounded-md border border-dashed border-line bg-paper px-4 text-center hover:border-teal">
          <FileArchive className="mb-3 text-teal" />
          <div className="text-sm font-medium">{file ? file.name : "選擇或拖曳回測 zip"}</div>
          <div className="mt-1 text-xs text-graphite">必要檔案：manifest.json、config.json、metrics.json</div>
          <input className="sr-only" type="file" accept=".zip,application/zip" onChange={(event) => setFile(event.target.files?.[0] || null)} />
        </label>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button onClick={validate} disabled={!file || busy}><CheckCircle2 size={16} />驗證</Button>
          <Button onClick={importZip} disabled={!file || busy} className="bg-teal text-white hover:border-teal"><Upload size={16} />匯入 Zip</Button>
          {runId ? <Link className="inline-flex h-10 items-center rounded-md border border-line bg-white px-3 text-sm text-teal" href={`/run-detail?run_id=${encodeURIComponent(runId)}`}>查看紀錄</Link> : null}
        </div>
      </Panel>

      <Panel className="mt-5">
        <div className="mb-2 text-sm font-semibold">Bitget API 唯讀匯入</div>
        <div className="mb-3 rounded-md border border-line bg-paper p-3 text-sm">
          後端 API 狀態：
          {bitgetStatus.isLoading
            ? "檢查中"
            : bitgetStatus.error
              ? `連線失敗：${(bitgetStatus.error as Error).message}`
              : bitgetStatus.data?.configured
                ? "已設定 Bitget API 金鑰"
                : `後端可連線，但少了：${bitgetStatus.data?.missing?.join(", ") || "Bitget API 金鑰 / 密鑰 / 通行短語"}。請確認金鑰是設在 API 服務，不是只設在 Web 服務。`}
        </div>
        <div className="grid gap-3 md:grid-cols-2">
          <label className="text-sm">
            <span className="mb-1 block text-xs text-graphite">紀錄代號</span>
            <input className="h-10 w-full rounded-md border border-line px-3 text-sm" value={bitgetRunId} onChange={(event) => setBitgetRunId(event.target.value)} />
          </label>
          <label className="text-sm">
            <span className="mb-1 block text-xs text-graphite">標題</span>
            <input className="h-10 w-full rounded-md border border-line px-3 text-sm" value={bitgetTitle} onChange={(event) => setBitgetTitle(event.target.value)} />
          </label>
          <label className="text-sm">
            <span className="mb-1 block text-xs text-graphite">合約類型</span>
            <Select className="w-full" value={bitgetProductType} onChange={(event) => setBitgetProductType(event.target.value)}>
              {PRODUCT_TYPES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
            </Select>
          </label>
          <label className="text-sm">
            <span className="mb-1 block text-xs text-graphite">交易對，留空代表全部</span>
            <input className="h-10 w-full rounded-md border border-line px-3 text-sm" value={bitgetSymbols} onChange={(event) => setBitgetSymbols(event.target.value)} placeholder="BTCUSDT,ETHUSDT" />
          </label>
          <label className="text-sm">
            <span className="mb-1 block text-xs text-graphite">開始時間（台北時間）</span>
            <input className="h-10 w-full rounded-md border border-line px-3 text-sm" type="datetime-local" value={bitgetStart} min={DEFAULT_START} onChange={(event) => setBitgetStart(event.target.value)} />
          </label>
          <label className="text-sm">
            <span className="mb-1 block text-xs text-graphite">結束時間（台北時間）</span>
            <input className="h-10 w-full rounded-md border border-line px-3 text-sm" type="datetime-local" value={bitgetEnd} onChange={(event) => setBitgetEnd(event.target.value)} />
          </label>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button onClick={importBitget} disabled={busy || !bitgetRunId || !bitgetStart || !bitgetEnd}>
            <Upload size={16} />
            匯入 Bitget 紀錄
          </Button>
          {runId ? <Link className="inline-flex h-10 items-center rounded-md border border-line bg-white px-3 text-sm text-teal" href="/recorded">查看計入資料</Link> : null}
        </div>
      </Panel>

      {message ? <div className="mt-4"><ErrorState message={message} /></div> : null}

      {report ? (
        <Panel className="mt-5">
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold">
            {report.ok ? <CheckCircle2 className="text-teal" size={18} /> : <XCircle className="text-rose" size={18} />}
            匯入報告
          </div>
          <div className="grid gap-3 text-sm md:grid-cols-3">
            <div>紀錄代號：<span className="font-medium">{report.run_id || "-"}</span></div>
            <div>紀錄起點：{formatDateTime(report.record_start_at)}</div>
            <div>結果雜湊：<span className="break-all text-xs">{report.result_hash || "-"}</span></div>
          </div>
          {importedCounts ? <ImportCounts counts={importedCounts} /> : null}
          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            <IssueList title="錯誤" issues={report.errors} />
            <IssueList title="警告" issues={report.warnings} />
          </div>
          {report.files.length ? (
            <div className="mt-4 overflow-x-auto">
              <table className="w-full min-w-[760px] text-left text-sm">
                <thead className="border-b border-line text-xs text-graphite">
                  <tr><th className="py-2">檔案</th><th>狀態</th><th>列數</th><th>略過</th><th>hash</th><th>欄位</th></tr>
                </thead>
                <tbody>
                  {report.files.map((item) => (
                    <tr key={item.file_name} className="border-b border-line/70">
                      <td className="py-2 font-medium">{item.file_name}</td>
                      <td>{item.validation_status}</td>
                      <td>{item.row_count ?? "-"}</td>
                      <td>{item.skipped_rows}</td>
                      <td className="max-w-[220px] truncate text-xs">{item.file_hash}</td>
                      <td className="max-w-[280px] truncate text-xs">{item.columns.join(", ") || "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </Panel>
      ) : null}
    </div>
  );
}

function ImportCounts({ counts }: { counts: Record<string, number> }) {
  const entries = Object.entries(counts);
  if (!entries.length) return null;
  return (
    <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
      {entries.map(([key, value]) => (
        <div key={key} className="rounded-md border border-line bg-paper p-3">
          <div className="text-xs text-graphite">{key}</div>
          <div className="mt-1 text-lg font-semibold">{formatNumber(value, 0)}</div>
        </div>
      ))}
    </div>
  );
}

function IssueList({ title, issues }: { title: string; issues: ValidationReport["errors"] }) {
  return (
    <div className="rounded-md border border-line bg-paper p-3">
      <div className="mb-2 text-xs font-semibold uppercase text-graphite">{title}</div>
      {issues.length ? (
        <div className="space-y-2">
          {issues.map((item, index) => (
            <div key={index} className="text-sm">
              <span className="font-medium">{item.code}</span>: {item.message}
              <span className="ml-2 text-xs text-graphite">{item.file_name || ""}{item.row ? ` 第 ${item.row} 列` : ""}</span>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-sm text-graphite">無</div>
      )}
    </div>
  );
}
