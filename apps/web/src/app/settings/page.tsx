"use client";

import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  apiFetch,
  BitgetStatus,
  clearStoredApiBase,
  getStoredApiBase,
  normalizeApiBase,
  ProxyConnectionStatus,
  setStoredApiBase,
} from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { Button, ErrorState, Input, PageHeader, Panel } from "@/components/ui";

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const [apiBaseInput, setApiBaseInput] = useState("");
  const [savedApiBase, setSavedApiBase] = useState("");
  const [testMessage, setTestMessage] = useState<string | null>(null);
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    const saved = getStoredApiBase();
    setSavedApiBase(saved);
    setApiBaseInput(saved);
  }, []);

  const proxyQuery = useQuery({
    queryKey: ["proxy-connection"],
    queryFn: () => apiFetch<ProxyConnectionStatus>("/__connection"),
    retry: false,
  });

  const bitgetQuery = useQuery({
    queryKey: ["bitget-status"],
    queryFn: () => apiFetch<BitgetStatus>("/bitget/status"),
    retry: false,
  });

  async function saveAndTest() {
    const normalized = normalizeApiBase(apiBaseInput);
    if (!normalized) {
      setTestMessage("請先填入後端 API 網址，例如 https://your-api.zeabur.app/api");
      return;
    }

    setTesting(true);
    setTestMessage(null);
    setStoredApiBase(normalized);
    setSavedApiBase(normalized);
    setApiBaseInput(normalized);

    try {
      const status = await apiFetch<BitgetStatus>("/bitget/status");
      queryClient.setQueryData(["bitget-status"], status);
      await queryClient.invalidateQueries({ queryKey: ["proxy-connection"] });
      setTestMessage(
        status.configured
          ? "已接通後端，且後端已讀到 Bitget API 金鑰。"
          : `已接通後端，但後端仍缺少：${status.missing?.join(", ") || "API_KEY, API_SECRET, API_PASSPHRASE"}。請確認金鑰填在 API 服務，不是 Web 服務。`,
      );
    } catch (error) {
      setTestMessage(`後端網址仍無法連線：${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setTesting(false);
    }
  }

  async function clearSavedApi() {
    clearStoredApiBase();
    setSavedApiBase("");
    setApiBaseInput("");
    setTestMessage("已清除前台保存的後端 API 網址，系統會改用環境變數或前台代理。");
    await queryClient.invalidateQueries({ queryKey: ["proxy-connection"] });
    await queryClient.invalidateQueries({ queryKey: ["bitget-status"] });
  }

  const bitgetStatusText = bitgetQuery.data?.configured
    ? "後端已讀到 Bitget API 金鑰"
    : `後端缺少：${bitgetQuery.data?.missing?.join(", ") || "API_KEY, API_SECRET, API_PASSPHRASE"}`;

  return (
    <div>
      <PageHeader title="設定" description="目前前台、後台與資料記錄規則。" />
      <div className="grid gap-4 lg:grid-cols-2">
        <Panel className="lg:col-span-2">
          <div className="mb-3 text-sm font-semibold">後端 API 連線修復</div>
          <div className="grid gap-3 lg:grid-cols-[1fr_auto_auto]">
            <label className="text-sm">
              <span className="mb-1 block text-xs text-graphite">後端 API 網址</span>
              <Input
                className="w-full"
                value={apiBaseInput}
                onChange={(event) => setApiBaseInput(event.target.value)}
                placeholder="https://your-api.zeabur.app/api"
              />
            </label>
            <Button className="self-end bg-teal text-white hover:border-teal" onClick={saveAndTest} disabled={testing}>
              {testing ? "測試中" : "儲存並測試"}
            </Button>
            <Button className="self-end" onClick={clearSavedApi} disabled={testing}>
              清除
            </Button>
          </div>
          <p className="mt-3 text-sm text-graphite">
            前台會優先使用這裡保存的網址；若沒有保存，才會使用 Web 服務的 API_BASE_URL / NEXT_PUBLIC_API_BASE_URL 或前台代理。
          </p>
          {savedApiBase ? <div className="mt-3 text-sm">目前保存：<span className="font-medium">{savedApiBase}</span></div> : null}
          {testMessage ? <div className="mt-3 rounded-md border border-line bg-paper p-3 text-sm">{testMessage}</div> : null}
        </Panel>

        <Panel>
          <div className="mb-3 text-sm font-semibold">前後台連線</div>
          {proxyQuery.error ? <ErrorState message={(proxyQuery.error as Error).message} /> : null}
          <dl className="space-y-2 text-sm">
            <InfoRow label="前台代理" value={proxyQuery.data?.configured ? "已設定" : "未設定或未讀到"} />
            <InfoRow label="代理後端網址" value={proxyQuery.data?.base_url || "尚未讀到 API_BASE_URL"} />
            <InfoRow label="實際優先網址" value={savedApiBase || "使用環境變數或前台代理"} />
            <InfoRow label="狀態說明" value={proxyQuery.data?.message || "檢查中"} />
          </dl>
        </Panel>

        <Panel>
          <div className="mb-3 text-sm font-semibold">Bitget 唯讀 API</div>
          {bitgetQuery.error ? <ErrorState message={(bitgetQuery.error as Error).message} /> : null}
          <dl className="space-y-2 text-sm">
            <InfoRow label="金鑰狀態" value={bitgetStatusText} />
            <InfoRow label="Bitget API 位址" value={bitgetQuery.data?.base_url || "-"} />
            <InfoRow label="匯入模式" value={bitgetQuery.data?.mode || "-"} />
          </dl>
        </Panel>

        <Panel>
          <div className="mb-3 text-sm font-semibold">時間規則</div>
          <dl className="space-y-2 text-sm">
            <InfoRow label="資料庫時間" value="統一存成 UTC" />
            <InfoRow label="網頁顯示" value="Asia/Taipei 台北時間" />
            <InfoRow label="最早計入時間" value={formatDateTime(bitgetQuery.data?.record_start_at || "2026-05-08T00:00:00+08:00")} />
          </dl>
        </Panel>

        <Panel>
          <div className="mb-3 text-sm font-semibold">儲存規則</div>
          <p className="text-sm text-graphite">
            匯入的原始檔、雜湊、資料列數、驗證報告與 API 回傳內容，會存放在後端設定的儲存空間。計入資料頁只顯示符合時間規則的真實 Bitget 下單與成交資料。
          </p>
        </Panel>

        <Panel>
          <div className="mb-3 text-sm font-semibold">欄位保存</div>
          <p className="text-sm text-graphite">
            訂單、成交與持倉會保存已知欄位；Bitget 額外回傳的欄位會放在 metadata_json，方便之後追查原始內容。
          </p>
        </Panel>

        <Panel>
          <div className="mb-3 text-sm font-semibold">封存</div>
          <p className="text-sm text-graphite">
            封存只會把紀錄標記為不顯示，不會刪除原始檔；若要清掉儲存空間，需要另外執行清理任務。
          </p>
        </Panel>
      </div>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-graphite">{label}</dt>
      <dd className="max-w-[70%] break-words text-right font-medium">{value}</dd>
    </div>
  );
}
