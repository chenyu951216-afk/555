from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, utcnow


class Workspace(Base, TimestampMixin):
    __tablename__ = "workspaces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int | None] = mapped_column(ForeignKey("workspaces.id"), nullable=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(160), nullable=True)


class BacktestRun(Base, TimestampMixin):
    __tablename__ = "backtest_runs"
    __table_args__ = (
        Index("ix_runs_strategy", "strategy_name", "strategy_version"),
        Index("ix_runs_exchange_market", "exchange", "market_type"),
        Index("ix_runs_imported_at", "imported_at"),
        Index("ix_runs_archived_at", "archived_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int | None] = mapped_column(ForeignKey("workspaces.id"), nullable=True, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    run_id: Mapped[str] = mapped_column(String(180), unique=True, nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(320), nullable=True)
    strategy_name: Mapped[str | None] = mapped_column(String(180), nullable=True, index=True)
    strategy_version: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    strategy_family: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    exchange: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    market_type: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    base_currency: Mapped[str | None] = mapped_column(String(40), nullable=True)
    initial_capital: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    timeframe: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    created_by: Mapped[str | None] = mapped_column(String(160), nullable=True)
    data_source: Mapped[str | None] = mapped_column(String(180), nullable=True)
    data_version: Mapped[str | None] = mapped_column(String(180), nullable=True)
    code_version: Mapped[str | None] = mapped_column(String(180), nullable=True)
    schema_version: Mapped[str] = mapped_column(String(40), nullable=False, default="1.0")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active", index=True)
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    config_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    result_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    config = relationship("BacktestConfig", back_populates="run", uselist=False)


class BacktestConfig(Base):
    __tablename__ = "backtest_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("backtest_runs.run_id"), nullable=False, index=True)
    config_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    raw_file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    run = relationship("BacktestRun", back_populates="config")


class BacktestMetric(Base):
    __tablename__ = "backtest_metrics"
    __table_args__ = (
        UniqueConstraint("run_id", "metric_key", name="uq_metric_run_key"),
        Index("ix_metrics_key_numeric", "metric_key", "metric_value_numeric"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("backtest_runs.run_id"), nullable=False, index=True)
    metric_key: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    metric_value_numeric: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    metric_value_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    metric_unit: Mapped[str | None] = mapped_column(String(60), nullable=True)
    metric_category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class EquityPoint(Base):
    __tablename__ = "equity_points"
    __table_args__ = (
        UniqueConstraint("run_id", "timestamp", name="uq_equity_run_timestamp"),
        Index("ix_equity_run_timestamp", "run_id", "timestamp"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("backtest_runs.run_id"), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    equity: Mapped[Decimal] = mapped_column(Numeric(28, 10), nullable=False)
    cash: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    position_value: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    unrealized_pnl: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    realized_pnl: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    drawdown: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    exposure: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    leverage: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)


class Trade(Base):
    __tablename__ = "trades"
    __table_args__ = (
        UniqueConstraint("run_id", "trade_id", name="uq_trade_run_trade_id"),
        Index("ix_trades_run_symbol", "run_id", "symbol"),
        Index("ix_trades_run_entry_time", "run_id", "entry_time"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("backtest_runs.run_id"), nullable=False, index=True)
    trade_id: Mapped[str] = mapped_column(String(180), nullable=False)
    symbol: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    side: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    entry_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    exit_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    entry_price: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    exit_price: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    qty: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    notional: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    gross_pnl: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    fee: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    slippage: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    funding: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    net_pnl: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    return_pct: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    holding_minutes: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    exit_reason: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    raw_row_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    parse_warnings: Mapped[list | None] = mapped_column(JSON, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class OrderRecord(Base):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("run_id", "order_id", name="uq_order_run_order_id"),
        Index("ix_orders_run_symbol_time", "run_id", "symbol", "order_time"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("backtest_runs.run_id"), nullable=False, index=True)
    order_id: Mapped[str] = mapped_column(String(180), nullable=False)
    trade_id: Mapped[str | None] = mapped_column(String(180), nullable=True, index=True)
    symbol: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    side: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    order_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    order_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    status: Mapped[str | None] = mapped_column(String(80), nullable=True)
    price: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    qty: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    filled_qty: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    reduce_only: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    position_effect: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    parent_order_id: Mapped[str | None] = mapped_column(String(180), nullable=True)
    raw_row_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    parse_warnings: Mapped[list | None] = mapped_column(JSON, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class FillRecord(Base):
    __tablename__ = "fills"
    __table_args__ = (
        UniqueConstraint("run_id", "fill_id", name="uq_fill_run_fill_id"),
        Index("ix_fills_run_symbol_time", "run_id", "symbol", "fill_time"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("backtest_runs.run_id"), nullable=False, index=True)
    fill_id: Mapped[str] = mapped_column(String(180), nullable=False)
    order_id: Mapped[str | None] = mapped_column(String(180), nullable=True, index=True)
    trade_id: Mapped[str | None] = mapped_column(String(180), nullable=True, index=True)
    symbol: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    side: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    fill_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    price: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    qty: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    notional: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    fee: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    fee_currency: Mapped[str | None] = mapped_column(String(40), nullable=True)
    liquidity: Mapped[str | None] = mapped_column(String(40), nullable=True)
    reduce_only: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    position_effect: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    realized_pnl: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    raw_row_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    parse_warnings: Mapped[list | None] = mapped_column(JSON, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class PositionRecord(Base):
    __tablename__ = "positions"
    __table_args__ = (
        Index("ix_positions_run_symbol_time", "run_id", "symbol", "timestamp"),
        Index("ix_positions_effect", "position_effect"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("backtest_runs.run_id"), nullable=False, index=True)
    position_id: Mapped[str | None] = mapped_column(String(180), nullable=True, index=True)
    trade_id: Mapped[str | None] = mapped_column(String(180), nullable=True, index=True)
    symbol: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    side: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    qty: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    avg_price: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    market_price: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    notional: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    unrealized_pnl: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    realized_pnl: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    position_effect: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    raw_row_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    parse_warnings: Mapped[list | None] = mapped_column(JSON, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class SymbolSummary(Base):
    __tablename__ = "symbol_summaries"
    __table_args__ = (
        UniqueConstraint("run_id", "symbol", name="uq_symbol_summary_run_symbol"),
        Index("ix_symbol_summaries_run_symbol", "run_id", "symbol"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("backtest_runs.run_id"), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    trade_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gross_pnl: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    net_pnl: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    fee_total: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    slippage_total: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    funding_total: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    win_rate: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    avg_return: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    max_drawdown: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    avg_holding_minutes: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    selection_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class CostSummary(Base):
    __tablename__ = "cost_summaries"
    __table_args__ = (
        Index("ix_cost_summaries_run_category", "run_id", "category"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("backtest_runs.run_id"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(40), nullable=True)
    bps: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class CandidateSnapshot(Base):
    __tablename__ = "candidate_snapshots"
    __table_args__ = (
        Index("ix_candidates_run_timestamp", "run_id", "timestamp"),
        Index("ix_candidates_run_symbol", "run_id", "symbol"),
        Index("ix_candidates_selected", "run_id", "is_selected"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("backtest_runs.run_id"), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    is_in_universe: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_candidate: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_selected: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    blocked_reason: Mapped[str | None] = mapped_column(String(240), nullable=True)
    volume_24h: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    spread_bps: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    volatility: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class ImportFile(Base):
    __tablename__ = "import_files"
    __table_args__ = (
        Index("ix_import_files_run_name", "run_id", "file_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("backtest_runs.run_id"), nullable=False, index=True)
    file_name: Mapped[str] = mapped_column(String(260), nullable=False)
    file_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    schema_detected: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    validation_status: Mapped[str] = mapped_column(String(40), nullable=False, default="ok")
    validation_errors: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class ImportRowIssue(Base):
    __tablename__ = "import_row_issues"
    __table_args__ = (
        Index("ix_import_row_issues_run_file", "run_id", "file_name"),
        Index("ix_import_row_issues_code", "issue_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("backtest_runs.run_id"), nullable=False, index=True)
    file_name: Mapped[str] = mapped_column(String(260), nullable=False)
    row_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    issue_code: Mapped[str] = mapped_column(String(120), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    raw_row_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class RunTag(Base):
    __tablename__ = "run_tags"
    __table_args__ = (
        UniqueConstraint("run_id", "tag", name="uq_run_tag"),
        Index("ix_run_tags_tag", "tag"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("backtest_runs.run_id"), nullable=False, index=True)
    tag: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Note(Base, TimestampMixin):
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("backtest_runs.run_id"), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)


class Attachment(Base):
    __tablename__ = "attachments"
    __table_args__ = (
        Index("ix_attachments_run_file", "run_id", "file_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("backtest_runs.run_id"), nullable=False, index=True)
    file_name: Mapped[str] = mapped_column(String(260), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(160), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_target", "target_type", "target_id"),
        Index("ix_audit_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor: Mapped[str | None] = mapped_column(String(160), nullable=True)
    action: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(120), nullable=False)
    target_id: Mapped[str] = mapped_column(String(180), nullable=False)
    details_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
