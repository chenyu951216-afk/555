from __future__ import annotations

import json
import shutil
from datetime import timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import AuditLog, BacktestMetric, BacktestRun, FillRecord, ImportFile, ImportRowIssue, OrderRecord, RunTag, User, Workspace
from app.models.base import utcnow
from app.schemas.common import FileValidationSummary, ImportResult, ValidationReport
from app.schemas.imports import BitgetImportRequest
from app.services.bitget import BitgetReadOnlyClient, bitget_position_effect, bitget_reduce_only, decimal_or_none, ms_to_datetime
from app.services.importer import is_after_record_start, sanitize_filename, sha256_file, sha256_json


def _local_user(db: Session, settings: Settings) -> tuple[Workspace, User]:
    workspace = db.scalar(select(Workspace).where(Workspace.slug == "personal"))
    if workspace is None:
        workspace = Workspace(name=settings.default_workspace_name, slug="personal")
        db.add(workspace)
        db.flush()
    user = db.scalar(select(User).where(User.email == settings.default_user_email))
    if user is None:
        user = User(workspace_id=workspace.id, email=settings.default_user_email, display_name="Local User")
        db.add(user)
        db.flush()
    return workspace, user


class BitgetImportService:
    def __init__(self, db: Session, settings: Settings, client: BitgetReadOnlyClient | None = None):
        self.db = db
        self.settings = settings
        self.client = client or BitgetReadOnlyClient(settings)

    def import_read_only_history(self, payload: BitgetImportRequest) -> ImportResult:
        record_start = self.settings.record_start_at.astimezone(timezone.utc)
        start_time = max(payload.start_time.astimezone(timezone.utc), record_start)
        end_time = payload.end_time.astimezone(timezone.utc)
        if start_time >= end_time:
            raise ValueError("結束時間必須晚於最早計入時間")
        if self.db.scalar(select(BacktestRun.id).where(BacktestRun.run_id == payload.run_id)):
            raise ValueError(f"紀錄代號已存在：{payload.run_id}")

        symbols = payload.symbols or [None]
        all_orders: list[dict[str, Any]] = []
        all_fills: list[dict[str, Any]] = []
        for symbol in symbols:
            all_orders.extend(
                self.client.iter_history_orders(
                    product_type=payload.product_type,
                    start_time=start_time,
                    end_time=end_time,
                    symbol=symbol,
                    max_pages=payload.max_pages,
                )
            )
            all_fills.extend(
                self.client.iter_fill_history(
                    product_type=payload.product_type,
                    start_time=start_time,
                    end_time=end_time,
                    symbol=symbol,
                    max_pages=payload.max_pages,
                )
            )

        counts = {"orders": 0, "fills": 0, "row_issues": 0, "metrics": 0}
        try:
            workspace, user = _local_user(self.db, self.settings)
            storage_dir = self.settings.storage_root / "runs" / sanitize_filename(payload.run_id)
            if storage_dir.exists():
                shutil.rmtree(storage_dir, ignore_errors=True)
            result_hash = sha256_json({"orders": all_orders, "fills": all_fills, "start_time": start_time.isoformat(), "end_time": end_time.isoformat()})
            run = BacktestRun(
                workspace_id=workspace.id,
                user_id=user.id,
                run_id=payload.run_id,
                title=payload.title or f"Bitget read-only import {payload.run_id}",
                strategy_name="bitget_readonly_order_capture",
                strategy_version="v1",
                strategy_family="external_records",
                exchange="bitget",
                market_type="perp" if "futures" in payload.product_type.lower() else "other",
                base_currency=payload.base_currency,
                initial_capital=None,
                timeframe=None,
                start_time=start_time,
                end_time=end_time,
                created_by="bitget_readonly_api",
                data_source="bitget_api_v2",
                data_version=payload.product_type,
                code_version="readonly_importer_v1",
                schema_version="1.0",
                status="active",
                tags=["bitget", "readonly_api", "orders", "fills", "record_start_1830"],
                notes="Bitget API 唯讀匯入；系統沒有實作任何下單端點。",
                result_hash=result_hash,
            )
            self.db.add(run)
            self.db.flush()
            for tag in run.tags:
                self.db.add(RunTag(run_id=payload.run_id, tag=tag))
            counts["files"] = self._write_raw_files(payload, all_orders, all_fills, storage_dir)
            counts["orders"] = self._insert_orders(payload.run_id, all_orders, start_time)
            order_created_at = {
                str(row.get("orderId")): ms_to_datetime(row.get("cTime"))
                for row in all_orders
                if row.get("orderId")
            }
            counts["fills"] = self._insert_fills(payload.run_id, all_fills, start_time, order_created_at)
            counts["row_issues"] = (
                self.db.scalar(select(func.count()).select_from(ImportRowIssue).where(ImportRowIssue.run_id == payload.run_id))
                or 0
            )
            metrics = {
                "order_count": counts["orders"],
                "fill_count": counts["fills"],
                "bitget_raw_order_count": len(all_orders),
                "bitget_raw_fill_count": len(all_fills),
                "row_issue_count": counts["row_issues"],
            }
            for key, value in metrics.items():
                self.db.add(BacktestMetric(run_id=payload.run_id, metric_key=key, metric_value_numeric=value, metric_category="bitget_import"))
                counts["metrics"] += 1
            self.db.add(
                AuditLog(
                    actor=self.settings.default_user_email,
                    action="bitget_readonly_import",
                    target_type="backtest_run",
                    target_id=payload.run_id,
                    details_json={
                        "product_type": payload.product_type,
                        "symbols": payload.symbols,
                        "start_time": start_time.isoformat(),
                        "end_time": end_time.isoformat(),
                        "counts": counts,
                    },
                )
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            if "storage_dir" in locals() and isinstance(storage_dir, Path):
                shutil.rmtree(storage_dir, ignore_errors=True)
            raise

        report = ValidationReport(
            ok=True,
            run_id=payload.run_id,
            record_start_at=record_start,
            result_hash=result_hash,
            files=[
                FileValidationSummary(
                    file_name="bitget_orders_history.json",
                    file_type="bitget_api_json",
                    row_count=len(all_orders),
                    validation_status="ok",
                ),
                FileValidationSummary(
                    file_name="bitget_fill_history.json",
                    file_type="bitget_api_json",
                    row_count=len(all_fills),
                    validation_status="ok",
                ),
            ],
        )
        return ImportResult(ok=True, run_id=payload.run_id, validation=report, imported_counts=counts)

    def _write_raw_files(
        self,
        payload: BitgetImportRequest,
        orders: list[dict[str, Any]],
        fills: list[dict[str, Any]],
        storage_dir: Path,
    ) -> int:
        raw_dir = storage_dir / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        files: dict[str, Any] = {
            "bitget_import_request.json": payload.model_dump(mode="json"),
            "bitget_orders_history.json": orders,
            "bitget_fill_history.json": fills,
        }
        row_counts = {
            "bitget_import_request.json": 1,
            "bitget_orders_history.json": len(orders),
            "bitget_fill_history.json": len(fills),
        }
        for file_name, content in files.items():
            target = raw_dir / file_name
            target.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
            self.db.add(
                ImportFile(
                    run_id=payload.run_id,
                    file_name=file_name,
                    file_type="bitget_api_json",
                    file_path=str(target),
                    file_hash=sha256_file(target),
                    row_count=row_counts[file_name],
                    schema_detected={"source": "bitget_api_v2", "format": "json"},
                    validation_status="ok",
                    validation_errors=[],
                )
            )
        return len(files)

    def _insert_orders(self, run_id: str, rows: list[dict[str, Any]], start_time) -> int:
        count = 0
        for index, row in enumerate(rows, start=1):
            order_time = ms_to_datetime(row.get("cTime"))
            if not is_after_record_start(order_time, start_time):
                self._row_issue(run_id, "bitget.orders-history", index, "outside_record_window", "cTime 早於匯入起點，或時間無法解析", row)
                continue
            order_id = str(row.get("orderId") or row.get("clientOid") or f"{run_id}_bitget_order_{index:08d}")
            self.db.add(
                OrderRecord(
                    run_id=run_id,
                    order_id=order_id,
                    trade_id=None,
                    symbol=str(row.get("symbol") or "").upper() or None,
                    side=str(row.get("side") or "").lower() or None,
                    order_type=row.get("orderType"),
                    order_time=order_time,
                    status=row.get("status"),
                    price=decimal_or_none(row.get("priceAvg") or row.get("price")),
                    qty=decimal_or_none(row.get("size")),
                    filled_qty=decimal_or_none(row.get("baseVolume") or row.get("size")),
                    reduce_only=bitget_reduce_only(row.get("reduceOnly")),
                    position_effect=bitget_position_effect(row),
                    parent_order_id=None,
                    raw_row_json=row,
                    metadata_json={
                        "clientOid": row.get("clientOid"),
                        "orderSource": row.get("orderSource"),
                        "tradeSide": row.get("tradeSide"),
                        "posSide": row.get("posSide"),
                        "posMode": row.get("posMode"),
                        "quoteVolume": row.get("quoteVolume"),
                        "fee": row.get("fee"),
                    },
                )
            )
            count += 1
        return count

    def _insert_fills(self, run_id: str, rows: list[dict[str, Any]], start_time, order_created_at: dict[str, Any]) -> int:
        count = 0
        for index, row in enumerate(rows, start=1):
            fill_time = ms_to_datetime(row.get("cTime"))
            if not is_after_record_start(fill_time, start_time):
                self._row_issue(run_id, "bitget.order-fills", index, "outside_record_window", "cTime 早於匯入起點，或時間無法解析", row)
                continue
            order_id = str(row.get("orderId") or "") or None
            linked_order_time = order_created_at.get(order_id) if order_id else None
            if order_id and linked_order_time is not None:
                if not is_after_record_start(linked_order_time, start_time):
                    self._row_issue(
                        run_id,
                        "bitget.order-fills",
                        index,
                        "order_before_record_window",
                        "linked order cTime is earlier than import start; fill preserved as row issue only",
                        row,
                    )
                    continue
            else:
                self._row_issue(
                    run_id,
                    "bitget.order-fills",
                    index,
                    "unverified_order_time",
                    "找不到對應的 Bitget 訂單紀錄；此成交只保留為匯入問題，不計入核心表",
                    row,
                )
                continue
            fee_amount = None
            fee_currency = row.get("marginCoin")
            fee_detail = row.get("feeDetail") or []
            if isinstance(fee_detail, list) and fee_detail:
                first_fee = fee_detail[0] or {}
                fee_amount = first_fee.get("totalFee")
                fee_currency = first_fee.get("feeCoin") or fee_currency
            fill_id = str(row.get("tradeId") or f"{run_id}_bitget_fill_{index:08d}")
            self.db.add(
                FillRecord(
                    run_id=run_id,
                    fill_id=fill_id,
                    order_id=order_id,
                    trade_id=fill_id,
                    symbol=str(row.get("symbol") or "").upper() or None,
                    side=str(row.get("side") or "").lower() or None,
                    fill_time=fill_time,
                    price=decimal_or_none(row.get("price")),
                    qty=decimal_or_none(row.get("baseVolume")),
                    notional=decimal_or_none(row.get("quoteVolume")),
                    fee=decimal_or_none(fee_amount),
                    fee_currency=fee_currency,
                    liquidity=row.get("tradeScope"),
                    reduce_only=None,
                    position_effect=bitget_position_effect(row),
                    realized_pnl=decimal_or_none(row.get("profit")),
                    raw_row_json=row,
                    metadata_json={
                        "tradeSide": row.get("tradeSide"),
                        "posMode": row.get("posMode"),
                        "enterPointSource": row.get("enterPointSource"),
                    },
                )
            )
            count += 1
        return count

    def _row_issue(self, run_id: str, file_name: str, row_number: int, issue_code: str, message: str, row: dict[str, Any]) -> None:
        self.db.add(
            ImportRowIssue(
                run_id=run_id,
                file_name=file_name,
                row_number=row_number,
                issue_code=issue_code,
                message=message,
                raw_row_json=row,
                created_at=utcnow(),
            )
        )
