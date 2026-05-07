# API Docs

OpenAPI 文件：

```text
http://localhost:8000/api/docs
```

## 主要端點

- `POST /api/import/validate`
- `POST /api/import/backtest`
- `POST /api/import/backtest-zip`
- `GET /api/runs`
- `GET /api/runs/{run_id}`
- `PATCH /api/runs/{run_id}`
- `POST /api/runs/{run_id}/archive`
- `DELETE /api/runs/{run_id}`
- `GET /api/runs/{run_id}/metrics`
- `GET /api/runs/{run_id}/config`
- `GET /api/runs/{run_id}/config-diff?compare_to=RUN_ID`
- `GET /api/runs/{run_id}/equity`
- `GET /api/runs/{run_id}/trades`
- `GET /api/runs/{run_id}/orders`
- `GET /api/runs/{run_id}/fills`
- `GET /api/runs/{run_id}/positions`
- `GET /api/runs/{run_id}/trades/export`
- `GET /api/runs/{run_id}/symbols`
- `GET /api/runs/{run_id}/costs`
- `GET /api/runs/{run_id}/candidates`
- `GET /api/runs/{run_id}/import-row-issues`
- `GET /api/compare?run_ids=RUN_ID1,RUN_ID2`
- `GET /api/aggregate/runs`
- `GET /api/aggregate/by-strategy`
- `GET /api/aggregate/by-symbol`
- `GET /api/aggregate/by-tag`
- `GET /api/dashboard`
- `GET /api/runs/{run_id}/notes`
- `POST /api/runs/{run_id}/notes`
- `PATCH /api/notes/{note_id}`
- `DELETE /api/notes/{note_id}`
- `POST /api/runs/{run_id}/attachments`
- `GET /api/runs/{run_id}/attachments`
- `GET /api/attachments/{attachment_id}/download`
- `GET /api/runs/{run_id}/export`
- `GET /api/export/all`
- `POST /api/explorer/query`
- `GET /api/bitget/status`
- `POST /api/bitget/import-readonly`
- `GET /api/health`

## Bitget Read-Only Import

`POST /api/bitget/import-readonly` 讀取 Bitget Futures history orders 與 fill history，寫入本地 `orders` / `fills`。

此端點只做唯讀紀錄，不實作下單、改單、撤單、轉帳或任何交易動作。

系統會同時保存 `bitget_import_request.json`、`bitget_orders_history.json`、`bitget_fill_history.json` 到該 run 的 raw files，並建立 SHA256 hash。
`fills` 會用 `orderId` 對回 16:00 後建立的 Bitget order；若成交發生在 16:00 後、但委託是在 16:00 前建立，該列只保留在 raw files 與 `import_row_issues`，不寫入核心 `fills` 表。

實作參考 Bitget 官方文件：

- [Signature](https://www.bitget.com/api-doc/common/signature)
- [Get History Order](https://www.bitget.com/api-doc/classic/contract/trade/Get-Orders-History)
- [Get Historical Transaction Details](https://www.bitget.com/api-doc/classic/contract/trade/Get-Fill-History)

Request:

```json
{
  "run_id": "bitget_20260507_readonly_001",
  "title": "Bitget 唯讀下單成交紀錄",
  "product_type": "usdt-futures",
  "symbols": ["BTCUSDT", "ETHUSDT"],
  "start_time": "2026-05-07T16:00:00+08:00",
  "end_time": "2026-05-07T23:59:00+08:00",
  "base_currency": "USDT",
  "max_pages": 10
}
```

Credentials 只從後端環境變數讀取：

```text
BITGET_API_KEY
BITGET_API_SECRET
BITGET_API_PASSPHRASE
```
