"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch, BitgetStatus, ProxyConnectionStatus } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { ErrorState, PageHeader, Panel } from "@/components/ui";

export default function SettingsPage() {
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

  return (
    <div>
      <PageHeader title="設定" description="目前前台、後台與資料紀錄規則。" />
      <div className="grid gap-4 lg:grid-cols-2">
        <Panel>
          <div className="mb-3 text-sm font-semibold">前後台連線</div>
          {proxyQuery.error ? <ErrorState message={(proxyQuery.error as Error).message} /> : null}
          <dl className="space-y-2 text-sm">
            <InfoRow label="前台代理" value={proxyQuery.data?.configured ? "已設定" : "未設定"} />
            <InfoRow label="後端 API 位址" value={proxyQuery.data?.base_url || "尚未讀到 API_BASE_URL"} />
            <InfoRow label="狀態說明" value={proxyQuery.data?.message || "檢查中"} />
          </dl>
        </Panel>
        <Panel>
          <div className="mb-3 text-sm font-semibold">Bitget 唯讀 API</div>
          {bitgetQuery.error ? <ErrorState message={(bitgetQuery.error as Error).message} /> : null}
          <dl className="space-y-2 text-sm">
            <InfoRow
              label="金鑰狀態"
              value={bitgetQuery.data?.configured
                ? "後端已讀到 API 金鑰"
                : `後端缺少：${bitgetQuery.data?.missing?.join(", ") || "API_KEY, API_SECRET, API_PASSPHRASE"}，請確認金鑰設在 API 服務`}
            />
            <InfoRow label="Bitget API 位址" value={bitgetQuery.data?.base_url || "-"} />
            <InfoRow label="匯入模式" value={bitgetQuery.data?.mode || "-"} />
          </dl>
        </Panel>
        <Panel>
          <div className="mb-3 text-sm font-semibold">時間規則</div>
          <dl className="space-y-2 text-sm">
            <InfoRow label="資料庫時間" value="統一存成 UTC" />
            <InfoRow label="網頁顯示" value="Asia/Taipei 台北時間" />
            <InfoRow label="最早計入時間" value={formatDateTime(bitgetQuery.data?.record_start_at || "2026-05-07T18:30:00+08:00")} />
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
            封存只會把紀錄標記為不顯示，不會刪除原始檔案；若要清掉儲存空間，需要另外執行清理任務。
          </p>
        </Panel>
      </div>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-graphite">{label}</dt>
      <dd className="max-w-[70%] break-words text-right font-medium">{value}</dd>
    </div>
  );
}
