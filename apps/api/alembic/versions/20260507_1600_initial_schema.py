"""initial schema

Revision ID: 20260507_1600
Revises:
Create Date: 2026-05-07 16:00:00+08:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260507_1600"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_workspace_id", "users", ["workspace_id"])
    op.create_table(
        "backtest_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("run_id", sa.String(length=180), nullable=False),
        sa.Column("title", sa.String(length=320), nullable=True),
        sa.Column("strategy_name", sa.String(length=180), nullable=True),
        sa.Column("strategy_version", sa.String(length=120), nullable=True),
        sa.Column("strategy_family", sa.String(length=120), nullable=True),
        sa.Column("exchange", sa.String(length=80), nullable=True),
        sa.Column("market_type", sa.String(length=40), nullable=True),
        sa.Column("base_currency", sa.String(length=40), nullable=True),
        sa.Column("initial_capital", sa.Numeric(24, 8), nullable=True),
        sa.Column("timeframe", sa.String(length=40), nullable=True),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(length=160), nullable=True),
        sa.Column("data_source", sa.String(length=180), nullable=True),
        sa.Column("data_version", sa.String(length=180), nullable=True),
        sa.Column("code_version", sa.String(length=180), nullable=True),
        sa.Column("schema_version", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("config_hash", sa.String(length=64), nullable=True),
        sa.Column("result_hash", sa.String(length=64), nullable=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("run_id"),
    )
    for name, cols in {
        "ix_backtest_runs_workspace_id": ["workspace_id"],
        "ix_backtest_runs_user_id": ["user_id"],
        "ix_backtest_runs_run_id": ["run_id"],
        "ix_backtest_runs_strategy_name": ["strategy_name"],
        "ix_backtest_runs_strategy_version": ["strategy_version"],
        "ix_backtest_runs_strategy_family": ["strategy_family"],
        "ix_backtest_runs_exchange": ["exchange"],
        "ix_backtest_runs_market_type": ["market_type"],
        "ix_backtest_runs_timeframe": ["timeframe"],
        "ix_backtest_runs_start_time": ["start_time"],
        "ix_backtest_runs_end_time": ["end_time"],
        "ix_backtest_runs_status": ["status"],
        "ix_backtest_runs_config_hash": ["config_hash"],
        "ix_backtest_runs_result_hash": ["result_hash"],
        "ix_runs_strategy": ["strategy_name", "strategy_version"],
        "ix_runs_exchange_market": ["exchange", "market_type"],
        "ix_runs_imported_at": ["imported_at"],
        "ix_runs_archived_at": ["archived_at"],
    }.items():
        op.create_index(name, "backtest_runs", cols)

    op.create_table(
        "backtest_configs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.String(length=180), sa.ForeignKey("backtest_runs.run_id"), nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column("config_hash", sa.String(length=64), nullable=False),
        sa.Column("raw_file_path", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_backtest_configs_run_id", "backtest_configs", ["run_id"])
    op.create_index("ix_backtest_configs_config_hash", "backtest_configs", ["config_hash"])

    op.create_table(
        "backtest_metrics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.String(length=180), sa.ForeignKey("backtest_runs.run_id"), nullable=False),
        sa.Column("metric_key", sa.String(length=160), nullable=False),
        sa.Column("metric_value_numeric", sa.Numeric(28, 10), nullable=True),
        sa.Column("metric_value_text", sa.Text(), nullable=True),
        sa.Column("metric_unit", sa.String(length=60), nullable=True),
        sa.Column("metric_category", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("run_id", "metric_key", name="uq_metric_run_key"),
    )
    op.create_index("ix_backtest_metrics_run_id", "backtest_metrics", ["run_id"])
    op.create_index("ix_backtest_metrics_metric_key", "backtest_metrics", ["metric_key"])
    op.create_index("ix_metrics_key_numeric", "backtest_metrics", ["metric_key", "metric_value_numeric"])

    op.create_table(
        "equity_points",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.String(length=180), sa.ForeignKey("backtest_runs.run_id"), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("equity", sa.Numeric(28, 10), nullable=False),
        sa.Column("cash", sa.Numeric(28, 10), nullable=True),
        sa.Column("position_value", sa.Numeric(28, 10), nullable=True),
        sa.Column("unrealized_pnl", sa.Numeric(28, 10), nullable=True),
        sa.Column("realized_pnl", sa.Numeric(28, 10), nullable=True),
        sa.Column("drawdown", sa.Numeric(20, 10), nullable=True),
        sa.Column("exposure", sa.Numeric(20, 10), nullable=True),
        sa.Column("leverage", sa.Numeric(20, 10), nullable=True),
        sa.UniqueConstraint("run_id", "timestamp", name="uq_equity_run_timestamp"),
    )
    op.create_index("ix_equity_points_run_id", "equity_points", ["run_id"])
    op.create_index("ix_equity_points_timestamp", "equity_points", ["timestamp"])
    op.create_index("ix_equity_run_timestamp", "equity_points", ["run_id", "timestamp"])

    op.create_table(
        "trades",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.String(length=180), sa.ForeignKey("backtest_runs.run_id"), nullable=False),
        sa.Column("trade_id", sa.String(length=180), nullable=False),
        sa.Column("symbol", sa.String(length=80), nullable=True),
        sa.Column("side", sa.String(length=40), nullable=True),
        sa.Column("entry_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exit_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("entry_price", sa.Numeric(28, 10), nullable=True),
        sa.Column("exit_price", sa.Numeric(28, 10), nullable=True),
        sa.Column("qty", sa.Numeric(28, 10), nullable=True),
        sa.Column("notional", sa.Numeric(28, 10), nullable=True),
        sa.Column("gross_pnl", sa.Numeric(28, 10), nullable=True),
        sa.Column("fee", sa.Numeric(28, 10), nullable=True),
        sa.Column("slippage", sa.Numeric(28, 10), nullable=True),
        sa.Column("funding", sa.Numeric(28, 10), nullable=True),
        sa.Column("net_pnl", sa.Numeric(28, 10), nullable=True),
        sa.Column("return_pct", sa.Numeric(20, 10), nullable=True),
        sa.Column("holding_minutes", sa.Numeric(20, 4), nullable=True),
        sa.Column("exit_reason", sa.String(length=160), nullable=True),
        sa.Column("raw_row_json", sa.JSON(), nullable=True),
        sa.Column("parse_warnings", sa.JSON(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.UniqueConstraint("run_id", "trade_id", name="uq_trade_run_trade_id"),
    )
    for name, cols in {
        "ix_trades_run_id": ["run_id"],
        "ix_trades_symbol": ["symbol"],
        "ix_trades_side": ["side"],
        "ix_trades_entry_time": ["entry_time"],
        "ix_trades_exit_time": ["exit_time"],
        "ix_trades_exit_reason": ["exit_reason"],
        "ix_trades_run_symbol": ["run_id", "symbol"],
        "ix_trades_run_entry_time": ["run_id", "entry_time"],
    }.items():
        op.create_index(name, "trades", cols)

    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.String(length=180), sa.ForeignKey("backtest_runs.run_id"), nullable=False),
        sa.Column("order_id", sa.String(length=180), nullable=False),
        sa.Column("trade_id", sa.String(length=180), nullable=True),
        sa.Column("symbol", sa.String(length=80), nullable=True),
        sa.Column("side", sa.String(length=40), nullable=True),
        sa.Column("order_type", sa.String(length=80), nullable=True),
        sa.Column("order_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=80), nullable=True),
        sa.Column("price", sa.Numeric(28, 10), nullable=True),
        sa.Column("qty", sa.Numeric(28, 10), nullable=True),
        sa.Column("filled_qty", sa.Numeric(28, 10), nullable=True),
        sa.Column("reduce_only", sa.Boolean(), nullable=True),
        sa.Column("position_effect", sa.String(length=40), nullable=True),
        sa.Column("parent_order_id", sa.String(length=180), nullable=True),
        sa.Column("raw_row_json", sa.JSON(), nullable=True),
        sa.Column("parse_warnings", sa.JSON(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.UniqueConstraint("run_id", "order_id", name="uq_order_run_order_id"),
    )
    for name, cols in {
        "ix_orders_run_id": ["run_id"],
        "ix_orders_trade_id": ["trade_id"],
        "ix_orders_symbol": ["symbol"],
        "ix_orders_side": ["side"],
        "ix_orders_order_time": ["order_time"],
        "ix_orders_position_effect": ["position_effect"],
        "ix_orders_run_symbol_time": ["run_id", "symbol", "order_time"],
    }.items():
        op.create_index(name, "orders", cols)

    op.create_table(
        "fills",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.String(length=180), sa.ForeignKey("backtest_runs.run_id"), nullable=False),
        sa.Column("fill_id", sa.String(length=180), nullable=False),
        sa.Column("order_id", sa.String(length=180), nullable=True),
        sa.Column("trade_id", sa.String(length=180), nullable=True),
        sa.Column("symbol", sa.String(length=80), nullable=True),
        sa.Column("side", sa.String(length=40), nullable=True),
        sa.Column("fill_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("price", sa.Numeric(28, 10), nullable=True),
        sa.Column("qty", sa.Numeric(28, 10), nullable=True),
        sa.Column("notional", sa.Numeric(28, 10), nullable=True),
        sa.Column("fee", sa.Numeric(28, 10), nullable=True),
        sa.Column("fee_currency", sa.String(length=40), nullable=True),
        sa.Column("liquidity", sa.String(length=40), nullable=True),
        sa.Column("reduce_only", sa.Boolean(), nullable=True),
        sa.Column("position_effect", sa.String(length=40), nullable=True),
        sa.Column("realized_pnl", sa.Numeric(28, 10), nullable=True),
        sa.Column("raw_row_json", sa.JSON(), nullable=True),
        sa.Column("parse_warnings", sa.JSON(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.UniqueConstraint("run_id", "fill_id", name="uq_fill_run_fill_id"),
    )
    for name, cols in {
        "ix_fills_run_id": ["run_id"],
        "ix_fills_order_id": ["order_id"],
        "ix_fills_trade_id": ["trade_id"],
        "ix_fills_symbol": ["symbol"],
        "ix_fills_side": ["side"],
        "ix_fills_fill_time": ["fill_time"],
        "ix_fills_position_effect": ["position_effect"],
        "ix_fills_run_symbol_time": ["run_id", "symbol", "fill_time"],
    }.items():
        op.create_index(name, "fills", cols)

    op.create_table(
        "positions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.String(length=180), sa.ForeignKey("backtest_runs.run_id"), nullable=False),
        sa.Column("position_id", sa.String(length=180), nullable=True),
        sa.Column("trade_id", sa.String(length=180), nullable=True),
        sa.Column("symbol", sa.String(length=80), nullable=True),
        sa.Column("side", sa.String(length=40), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("qty", sa.Numeric(28, 10), nullable=True),
        sa.Column("avg_price", sa.Numeric(28, 10), nullable=True),
        sa.Column("market_price", sa.Numeric(28, 10), nullable=True),
        sa.Column("notional", sa.Numeric(28, 10), nullable=True),
        sa.Column("unrealized_pnl", sa.Numeric(28, 10), nullable=True),
        sa.Column("realized_pnl", sa.Numeric(28, 10), nullable=True),
        sa.Column("position_effect", sa.String(length=40), nullable=True),
        sa.Column("raw_row_json", sa.JSON(), nullable=True),
        sa.Column("parse_warnings", sa.JSON(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
    )
    for name, cols in {
        "ix_positions_run_id": ["run_id"],
        "ix_positions_position_id": ["position_id"],
        "ix_positions_trade_id": ["trade_id"],
        "ix_positions_symbol": ["symbol"],
        "ix_positions_side": ["side"],
        "ix_positions_timestamp": ["timestamp"],
        "ix_positions_effect": ["position_effect"],
        "ix_positions_run_symbol_time": ["run_id", "symbol", "timestamp"],
    }.items():
        op.create_index(name, "positions", cols)

    op.create_table(
        "symbol_summaries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.String(length=180), sa.ForeignKey("backtest_runs.run_id"), nullable=False),
        sa.Column("symbol", sa.String(length=80), nullable=False),
        sa.Column("trade_count", sa.Integer(), nullable=True),
        sa.Column("gross_pnl", sa.Numeric(28, 10), nullable=True),
        sa.Column("net_pnl", sa.Numeric(28, 10), nullable=True),
        sa.Column("fee_total", sa.Numeric(28, 10), nullable=True),
        sa.Column("slippage_total", sa.Numeric(28, 10), nullable=True),
        sa.Column("funding_total", sa.Numeric(28, 10), nullable=True),
        sa.Column("win_rate", sa.Numeric(20, 10), nullable=True),
        sa.Column("avg_return", sa.Numeric(20, 10), nullable=True),
        sa.Column("max_drawdown", sa.Numeric(20, 10), nullable=True),
        sa.Column("avg_holding_minutes", sa.Numeric(20, 4), nullable=True),
        sa.Column("selection_count", sa.Integer(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.UniqueConstraint("run_id", "symbol", name="uq_symbol_summary_run_symbol"),
    )
    op.create_index("ix_symbol_summaries_run_id", "symbol_summaries", ["run_id"])
    op.create_index("ix_symbol_summaries_symbol", "symbol_summaries", ["symbol"])
    op.create_index("ix_symbol_summaries_run_symbol", "symbol_summaries", ["run_id", "symbol"])

    op.create_table(
        "cost_summaries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.String(length=180), sa.ForeignKey("backtest_runs.run_id"), nullable=False),
        sa.Column("category", sa.String(length=120), nullable=False),
        sa.Column("amount", sa.Numeric(28, 10), nullable=True),
        sa.Column("currency", sa.String(length=40), nullable=True),
        sa.Column("bps", sa.Numeric(20, 10), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
    )
    op.create_index("ix_cost_summaries_run_id", "cost_summaries", ["run_id"])
    op.create_index("ix_cost_summaries_category", "cost_summaries", ["category"])
    op.create_index("ix_cost_summaries_run_category", "cost_summaries", ["run_id", "category"])

    op.create_table(
        "candidate_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.String(length=180), sa.ForeignKey("backtest_runs.run_id"), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("symbol", sa.String(length=80), nullable=False),
        sa.Column("is_in_universe", sa.Boolean(), nullable=True),
        sa.Column("is_candidate", sa.Boolean(), nullable=True),
        sa.Column("is_selected", sa.Boolean(), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("score", sa.Numeric(28, 10), nullable=True),
        sa.Column("blocked_reason", sa.String(length=240), nullable=True),
        sa.Column("volume_24h", sa.Numeric(28, 10), nullable=True),
        sa.Column("spread_bps", sa.Numeric(20, 10), nullable=True),
        sa.Column("volatility", sa.Numeric(20, 10), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
    )
    for name, cols in {
        "ix_candidate_snapshots_run_id": ["run_id"],
        "ix_candidate_snapshots_timestamp": ["timestamp"],
        "ix_candidate_snapshots_symbol": ["symbol"],
        "ix_candidates_run_timestamp": ["run_id", "timestamp"],
        "ix_candidates_run_symbol": ["run_id", "symbol"],
        "ix_candidates_selected": ["run_id", "is_selected"],
    }.items():
        op.create_index(name, "candidate_snapshots", cols)

    op.create_table(
        "import_files",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.String(length=180), sa.ForeignKey("backtest_runs.run_id"), nullable=False),
        sa.Column("file_name", sa.String(length=260), nullable=False),
        sa.Column("file_type", sa.String(length=80), nullable=True),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("file_hash", sa.String(length=64), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("schema_detected", sa.JSON(), nullable=True),
        sa.Column("validation_status", sa.String(length=40), nullable=False),
        sa.Column("validation_errors", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_import_files_run_id", "import_files", ["run_id"])
    op.create_index("ix_import_files_file_hash", "import_files", ["file_hash"])
    op.create_index("ix_import_files_run_name", "import_files", ["run_id", "file_name"])

    op.create_table(
        "import_row_issues",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.String(length=180), sa.ForeignKey("backtest_runs.run_id"), nullable=False),
        sa.Column("file_name", sa.String(length=260), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=True),
        sa.Column("issue_code", sa.String(length=120), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("raw_row_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_import_row_issues_run_id", "import_row_issues", ["run_id"])
    op.create_index("ix_import_row_issues_run_file", "import_row_issues", ["run_id", "file_name"])
    op.create_index("ix_import_row_issues_code", "import_row_issues", ["issue_code"])

    op.create_table(
        "run_tags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.String(length=180), sa.ForeignKey("backtest_runs.run_id"), nullable=False),
        sa.Column("tag", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("run_id", "tag", name="uq_run_tag"),
    )
    op.create_index("ix_run_tags_run_id", "run_tags", ["run_id"])
    op.create_index("ix_run_tags_tag", "run_tags", ["tag"])

    op.create_table(
        "notes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.String(length=180), sa.ForeignKey("backtest_runs.run_id"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_notes_run_id", "notes", ["run_id"])

    op.create_table(
        "attachments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.String(length=180), sa.ForeignKey("backtest_runs.run_id"), nullable=False),
        sa.Column("file_name", sa.String(length=260), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("file_hash", sa.String(length=64), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("mime_type", sa.String(length=160), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_attachments_run_id", "attachments", ["run_id"])
    op.create_index("ix_attachments_run_file", "attachments", ["run_id", "file_name"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor", sa.String(length=160), nullable=True),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("target_type", sa.String(length=120), nullable=False),
        sa.Column("target_id", sa.String(length=180), nullable=False),
        sa.Column("details_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_created_at", "audit_logs", ["created_at"])
    op.create_index("ix_audit_target", "audit_logs", ["target_type", "target_id"])


def downgrade() -> None:
    for table in [
        "audit_logs",
        "attachments",
        "notes",
        "run_tags",
        "import_row_issues",
        "import_files",
        "candidate_snapshots",
        "cost_summaries",
        "symbol_summaries",
        "trades",
        "positions",
        "fills",
        "orders",
        "equity_points",
        "backtest_metrics",
        "backtest_configs",
        "backtest_runs",
        "users",
        "workspaces",
    ]:
        op.drop_table(table)
