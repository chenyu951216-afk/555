from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RunSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: str
    title: str | None = None
    strategy_name: str | None = None
    strategy_version: str | None = None
    strategy_family: str | None = None
    exchange: str | None = None
    market_type: str | None = None
    base_currency: str | None = None
    initial_capital: Decimal | None = None
    timeframe: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    status: str
    tags: list[str] = Field(default_factory=list)
    config_hash: str | None = None
    result_hash: str | None = None
    imported_at: datetime
    archived_at: datetime | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)


class RunDetail(RunSummary):
    created_by: str | None = None
    data_source: str | None = None
    data_version: str | None = None
    code_version: str | None = None
    schema_version: str
    notes: str | None = None
    created_at: datetime
    updated_at: datetime
    files: list[dict[str, Any]] = Field(default_factory=list)


class MetricItem(BaseModel):
    metric_key: str
    metric_value_numeric: Decimal | None = None
    metric_value_text: str | None = None
    metric_unit: str | None = None
    metric_category: str | None = None


class ConfigResponse(BaseModel):
    run_id: str
    config_json: dict[str, Any]
    config_hash: str


class ConfigDiffItem(BaseModel):
    path: str
    left: Any = None
    right: Any = None


class ConfigDiffResponse(BaseModel):
    run_id: str
    compare_to: str
    differences: list[ConfigDiffItem]


class EquityPointOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    timestamp: datetime
    equity: Decimal
    cash: Decimal | None = None
    position_value: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    realized_pnl: Decimal | None = None
    drawdown: Decimal | None = None
    exposure: Decimal | None = None
    leverage: Decimal | None = None


class TradeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: str
    trade_id: str
    symbol: str | None = None
    side: str | None = None
    entry_time: datetime | None = None
    exit_time: datetime | None = None
    entry_price: Decimal | None = None
    exit_price: Decimal | None = None
    qty: Decimal | None = None
    notional: Decimal | None = None
    gross_pnl: Decimal | None = None
    fee: Decimal | None = None
    slippage: Decimal | None = None
    funding: Decimal | None = None
    net_pnl: Decimal | None = None
    return_pct: Decimal | None = None
    holding_minutes: Decimal | None = None
    exit_reason: str | None = None
    raw_row_json: dict[str, Any] | None = None
    parse_warnings: list[Any] | None = None
    metadata_json: dict[str, Any] | None = None


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: str
    order_id: str
    trade_id: str | None = None
    symbol: str | None = None
    side: str | None = None
    order_type: str | None = None
    order_time: datetime | None = None
    status: str | None = None
    price: Decimal | None = None
    qty: Decimal | None = None
    filled_qty: Decimal | None = None
    reduce_only: bool | None = None
    position_effect: str | None = None
    parent_order_id: str | None = None
    raw_row_json: dict[str, Any] | None = None
    parse_warnings: list[Any] | None = None
    metadata_json: dict[str, Any] | None = None


class FillOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: str
    fill_id: str
    order_id: str | None = None
    trade_id: str | None = None
    symbol: str | None = None
    side: str | None = None
    fill_time: datetime | None = None
    price: Decimal | None = None
    qty: Decimal | None = None
    notional: Decimal | None = None
    fee: Decimal | None = None
    fee_currency: str | None = None
    liquidity: str | None = None
    reduce_only: bool | None = None
    position_effect: str | None = None
    realized_pnl: Decimal | None = None
    raw_row_json: dict[str, Any] | None = None
    parse_warnings: list[Any] | None = None
    metadata_json: dict[str, Any] | None = None


class PositionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: str
    position_id: str | None = None
    trade_id: str | None = None
    symbol: str | None = None
    side: str | None = None
    timestamp: datetime | None = None
    qty: Decimal | None = None
    avg_price: Decimal | None = None
    market_price: Decimal | None = None
    notional: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    realized_pnl: Decimal | None = None
    position_effect: str | None = None
    raw_row_json: dict[str, Any] | None = None
    parse_warnings: list[Any] | None = None
    metadata_json: dict[str, Any] | None = None


class SymbolSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: str
    symbol: str
    trade_count: int | None = None
    gross_pnl: Decimal | None = None
    net_pnl: Decimal | None = None
    fee_total: Decimal | None = None
    slippage_total: Decimal | None = None
    funding_total: Decimal | None = None
    win_rate: Decimal | None = None
    avg_return: Decimal | None = None
    max_drawdown: Decimal | None = None
    avg_holding_minutes: Decimal | None = None
    selection_count: int | None = None
    metadata_json: dict[str, Any] | None = None


class CostSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: str
    category: str
    amount: Decimal | None = None
    currency: str | None = None
    bps: Decimal | None = None
    description: str | None = None
    metadata_json: dict[str, Any] | None = None


class CandidateSnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: str
    timestamp: datetime
    symbol: str
    is_in_universe: bool | None = None
    is_candidate: bool | None = None
    is_selected: bool | None = None
    rank: int | None = None
    score: Decimal | None = None
    blocked_reason: str | None = None
    volume_24h: Decimal | None = None
    spread_bps: Decimal | None = None
    volatility: Decimal | None = None
    metadata_json: dict[str, Any] | None = None


class NoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: str
    content: str
    created_at: datetime
    updated_at: datetime


class AttachmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: str
    file_name: str
    file_hash: str
    file_size: int | None = None
    mime_type: str | None = None
    created_at: datetime


class CompareResponse(BaseModel):
    run_ids: list[str]
    runs: list[RunSummary]
    metrics: dict[str, dict[str, Any]]
    equity: dict[str, list[EquityPointOut]]
    config_diffs: dict[str, list[ConfigDiffItem]] = Field(default_factory=dict)


class DashboardStats(BaseModel):
    total_runs: int
    total_trades: int
    stored_bytes: int
    recent_runs: list[RunSummary]
    runs_imported_over_time: list[dict[str, Any]]
    strategy_distribution: list[dict[str, Any]]
    market_type_distribution: list[dict[str, Any]]
    exchange_distribution: list[dict[str, Any]]
    tag_distribution: list[dict[str, Any]]
    timeframe_distribution: list[dict[str, Any]]
