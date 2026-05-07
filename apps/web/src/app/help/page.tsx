import { PageHeader, Panel } from "@/components/ui";

const manifest = `{
  "schema_version": "1.0",
  "run_id": "bitget_20260507_readonly_001",
  "title": "Bitget 唯讀下單紀錄匯入",
  "exchange": "bitget",
  "market_type": "perp",
  "base_currency": "USDT",
  "initial_capital": 100000,
  "start_time": "2026-05-08T00:00:00+08:00",
  "end_time": "2026-05-07T23:59:00+08:00",
  "data_source": "bitget_api_v2"
}`;

export default function HelpPage() {
  return (
    <div>
      <PageHeader title="說明與格式" description="匯入格式、真實資料來源與常見狀況。" />
      <div className="grid gap-4">
        <DocBlock title="Zip 檔案結構" code={`run_folder/\n  manifest.json\n  config.json\n  metrics.json\n  equity_curve.csv\n  trades.csv\n  orders.csv\n  fills.csv\n  positions.csv\n  symbol_summary.csv\n  cost_summary.csv\n  candidate_snapshot.csv\n  notes.md\n  attachments/`} />
        <DocBlock title="manifest.json 範例" code={manifest} />
        <DocBlock title="orders.csv 欄位" code="order_id,trade_id,symbol,side,order_type,order_time,status,price,qty,filled_qty,reduce_only,position_effect,parent_order_id" />
        <DocBlock title="fills.csv 欄位" code="fill_id,order_id,trade_id,symbol,side,fill_time,price,qty,notional,fee,fee_currency,liquidity,reduce_only,position_effect,realized_pnl,order_time" />
        <DocBlock title="Bitget 唯讀 API 匯入" code={`POST /api/bitget/sync-readonly\nPOST /api/bitget/import-readonly\nGET /api/bitget/recorded-data\n\n只會計入 2026-05-08 00:00 Asia/Taipei 之後的訂單與成交。請使用只有讀取權限的 Bitget API key。`} />
        <Panel>
          <div className="mb-2 text-sm font-semibold">常見狀況</div>
          <ul className="space-y-2 text-sm text-graphite">
            <li>缺少 manifest.json、config.json 或 metrics.json 時，Zip 匯入會停止。</li>
            <li>run_id 重複時會停止匯入，避免覆蓋舊資料。</li>
            <li>2026-05-08 00:00 +08:00 之前的資料不會計入核心統計；若是檔案匯入，會保留在原始檔或列入匯入問題。</li>
            <li>成交資料若有 order_time，系統會優先用 order_time 判斷是否落在計入時間之後。</li>
            <li>前台若一直載入，請到「設定」確認前台 API_BASE_URL 是否指到正確的後端 /api 網址。</li>
          </ul>
        </Panel>
      </div>
    </div>
  );
}

function DocBlock({ title, code }: { title: string; code: string }) {
  return (
    <Panel>
      <div className="mb-2 text-sm font-semibold">{title}</div>
      <pre className="overflow-auto rounded-md bg-paper p-3 text-xs leading-5">{code}</pre>
    </Panel>
  );
}
