# Schema Docs

本系統只保存、統整、顯示回測紀錄，不產生交易訊號、不連接交易所、不做策略建議。

## 紀錄起點

預設紀錄起點為：

```text
2026-05-08T00:00:00+08:00
```

核心表只寫入可確認在紀錄起點之後的時間序列資料：

- `trades.entry_time >= record_start_at`
- `orders.order_time >= record_start_at`
- `fills.order_time >= record_start_at`，若未提供 `order_time` 才以 `fill_time` 作為匯入窗口 fallback，並在 parse warning 保留說明
- `positions.timestamp >= record_start_at`
- `equity_points.timestamp >= record_start_at`
- `candidate_snapshots.timestamp >= record_start_at`

未寫入核心表的資料列仍保留在原始檔案中，並在 `import_row_issues` 中保存原因與原始 row。

## manifest.json

必要欄位：

- `schema_version`
- `run_id`
- `base_currency`
- `initial_capital`
- `start_time`
- `end_time`
- `market_type`

`market_type` 支援：`spot`、`perp`、`futures`、`options`、`other`。

## config.json

完整保存原始 JSON，系統不解析策略邏輯。匯入時計算 `config_hash`，UI 可複製、下載與做 config diff。

## metrics.json

彈性 key-value。常見欄位會顯示於主要卡片，未知欄位仍保留在 metrics API。

## trades.csv

```csv
trade_id,symbol,side,entry_time,exit_time,entry_price,exit_price,qty,notional,gross_pnl,fee,slippage,funding,net_pnl,return_pct,holding_minutes,exit_reason
```

`trades.csv` 是回測器提供的交易摘要，不用來推測實際開倉、分批止盈或平倉流程。分批止盈請提供 `orders.csv`、`fills.csv`、`positions.csv`。

## orders.csv

```csv
order_id,trade_id,symbol,side,order_type,order_time,status,price,qty,filled_qty,reduce_only,position_effect,parent_order_id
```

`position_effect` 建議值：

- `open`
- `increase`
- `reduce`
- `partial_close`
- `partial_take_profit`
- `close`
- `stop_loss`
- `unknown`

Bitget 唯讀 API 匯入會把官方 `tradeSide` / `orderSource` 中立映射為 `position_effect`：

- `open` 或 one-way buy/sell：`open`
- `close`：`close`
- `reduce_*` / `offset_close_*`：`reduce`
- `profit_*` order source：`partial_take_profit`
- `loss_*` order source：`stop_loss`

## fills.csv

```csv
fill_id,order_id,trade_id,symbol,side,fill_time,price,qty,notional,fee,fee_currency,liquidity,reduce_only,position_effect,realized_pnl,order_time
```

成交紀錄是分批止盈與實際減倉的主要追溯來源。若能提供 `order_time`，系統會用它判斷是否為 2026-05-08 00:00 +08:00 後下的單；沒有 `order_time` 時才使用 `fill_time` 作為 fallback。

Bitget 唯讀 API 匯入時，`fills` 必須能用 `orderId` 對回 `orders-history` 內 2026-05-08 00:00 +08:00 後建立的委託，才會寫入核心 `fills` 表。若委託時間早於 5/8 或無法確認，該成交列會保留在原始 API JSON 與 `import_row_issues`，不會混入核心成交表。

## positions.csv

```csv
position_id,trade_id,symbol,side,timestamp,qty,avg_price,market_price,notional,unrealized_pnl,realized_pnl,position_effect
```

部位事件可保存開倉後數量變化，避免把減倉和平倉混成單一交易摘要。

## equity_curve.csv

```csv
timestamp,equity,cash,position_value,unrealized_pnl,realized_pnl,drawdown,exposure,leverage
```

`timestamp` 與 `equity` 必要，其餘欄位可缺。

## symbol_summary.csv

```csv
symbol,trade_count,gross_pnl,net_pnl,fee_total,slippage_total,funding_total,win_rate,avg_return,max_drawdown,avg_holding_minutes,selection_count
```

沒有提供時，系統可從 trades 做中立 group by 統整。

## cost_summary.csv

```csv
category,amount,currency,bps,description
```

沒有提供時，系統會從 `metrics.json` 的 `fee_total`、`slippage_total`、`funding_total` 產生顯示資料。

## candidate_snapshot.csv

```csv
timestamp,symbol,is_in_universe,is_candidate,is_selected,rank,score,blocked_reason,volume_24h,spread_bps,volatility
```

此檔用於保存 universe / candidate / selected 狀態，只顯示紀錄，不做選幣建議。
