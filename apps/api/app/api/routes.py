from __future__ import annotations

import csv
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.models import (
    Attachment,
    AuditLog,
    BacktestConfig,
    BacktestMetric,
    BacktestRun,
    CandidateSnapshot,
    CostSummary,
    EquityPoint,
    FillRecord,
    ImportFile,
    ImportRowIssue,
    Note,
    OrderRecord,
    PositionRecord,
    RunTag,
    SymbolSummary,
    Trade,
)
from app.models.base import utcnow
from app.schemas.common import ImportResult, Page, ValidationReport
from app.schemas.imports import BitgetImportRequest, NoteCreate, NoteUpdate, RunPatch, SafeQueryFilter
from app.schemas.runs import (
    AttachmentOut,
    CandidateSnapshotOut,
    CompareResponse,
    ConfigDiffItem,
    ConfigDiffResponse,
    ConfigResponse,
    CostSummaryOut,
    DashboardStats,
    EquityPointOut,
    FillOut,
    MetricItem,
    NoteOut,
    OrderOut,
    PositionOut,
    RunDetail,
    RunSummary,
    SymbolSummaryOut,
    TradeOut,
)
from app.services.importer import BacktestImporter, sanitize_filename, sha256_file
from app.services.bitget_importer import BitgetImportService


router = APIRouter()

COMMON_METRICS = [
    "total_return",
    "annualized_return",
    "max_drawdown",
    "sharpe",
    "sortino",
    "calmar",
    "win_rate",
    "profit_factor",
    "trade_count",
    "gross_pnl",
    "net_pnl",
    "fee_total",
    "slippage_total",
    "funding_total",
]


def metric_value(metric: BacktestMetric) -> Any:
    if metric.metric_value_numeric is not None:
        return float(metric.metric_value_numeric)
    return metric.metric_value_text


def metrics_for_runs(db: Session, run_ids: list[str]) -> dict[str, dict[str, Any]]:
    if not run_ids:
        return {}
    rows = db.scalars(select(BacktestMetric).where(BacktestMetric.run_id.in_(run_ids))).all()
    result: dict[str, dict[str, Any]] = {run_id: {} for run_id in run_ids}
    for metric in rows:
        result.setdefault(metric.run_id, {})[metric.metric_key] = metric_value(metric)
    return result


def run_summary_from_model(run: BacktestRun, metrics: dict[str, Any] | None = None) -> RunSummary:
    return RunSummary.model_validate(run).model_copy(update={"metrics": metrics or {}})


def run_detail_from_model(run: BacktestRun, metrics: dict[str, Any], files: list[dict[str, Any]]) -> RunDetail:
    return RunDetail.model_validate(run).model_copy(update={"metrics": metrics, "files": files})


def apply_pagination(stmt, limit: int, offset: int):
    return stmt.limit(limit).offset(offset)


async def save_upload(upload: UploadFile, settings: Settings) -> Path:
    suffix = Path(upload.filename or "upload.zip").suffix or ".zip"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    size = 0
    max_bytes = settings.max_upload_mb * 1024 * 1024
    try:
        while chunk := await upload.read(1024 * 1024):
            size += len(chunk)
            if size > max_bytes:
                raise HTTPException(status_code=413, detail=f"檔案超過上限 {settings.max_upload_mb} MB")
            tmp.write(chunk)
    finally:
        tmp.close()
    return Path(tmp.name)


def require_run(db: Session, run_id: str) -> BacktestRun:
    run = db.scalar(select(BacktestRun).where(BacktestRun.run_id == run_id))
    if run is None:
        raise HTTPException(status_code=404, detail="找不到回測紀錄")
    return run


def flatten_diff(left: Any, right: Any, path: str = "$") -> list[ConfigDiffItem]:
    if isinstance(left, dict) and isinstance(right, dict):
        keys = sorted(set(left) | set(right))
        items: list[ConfigDiffItem] = []
        for key in keys:
            next_path = f"{path}.{key}"
            if key not in left:
                items.append(ConfigDiffItem(path=next_path, left=None, right=right[key]))
            elif key not in right:
                items.append(ConfigDiffItem(path=next_path, left=left[key], right=None))
            else:
                items.extend(flatten_diff(left[key], right[key], next_path))
        return items
    if isinstance(left, list) and isinstance(right, list):
        if left == right:
            return []
        return [ConfigDiffItem(path=path, left=left, right=right)]
    if left != right:
        return [ConfigDiffItem(path=path, left=left, right=right)]
    return []


@router.get("/health")
def health(settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    return {
        "ok": True,
        "project": settings.project_name,
        "timezone": settings.default_timezone,
        "record_start_at": settings.record_start_at.isoformat(),
    }


@router.post("/import/validate", response_model=ValidationReport)
async def validate_import(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ValidationReport:
    path = await save_upload(file, settings)
    try:
        if not zipfile.is_zipfile(path):
            raise HTTPException(status_code=400, detail="目前 validate API 需要 zip 檔")
        importer = BacktestImporter(db, settings)
        prepared = importer.validate_zip(path)
        return prepared.report
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        if "prepared" in locals():
            BacktestImporter.cleanup_prepared(prepared)
        path.unlink(missing_ok=True)


@router.post("/import/backtest", response_model=ImportResult)
async def import_backtest(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ImportResult:
    return await import_backtest_zip(file, db, settings)


@router.post("/import/backtest-zip", response_model=ImportResult)
async def import_backtest_zip(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ImportResult:
    path = await save_upload(file, settings)
    try:
        if not zipfile.is_zipfile(path):
            raise HTTPException(status_code=400, detail="請上傳 zip 檔")
        importer = BacktestImporter(db, settings)
        prepared = importer.validate_zip(path)
        if not prepared.report.ok:
            raise HTTPException(status_code=422, detail=prepared.report.model_dump(mode="json"))
        try:
            return importer._write_import(prepared, original_zip=path)
        finally:
            importer.cleanup_prepared(prepared)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        if "prepared" in locals():
            BacktestImporter.cleanup_prepared(prepared)
        path.unlink(missing_ok=True)


@router.get("/bitget/status")
def bitget_status(settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    missing = []
    if not settings.bitget_api_key:
        missing.append("API_KEY")
    if not settings.bitget_api_secret:
        missing.append("API_SECRET")
    if not settings.bitget_api_passphrase:
        missing.append("API_PASSPHRASE")
    return {
        "configured": not missing,
        "missing": missing,
        "base_url": settings.bitget_api_base_url,
        "mode": "read_only_import",
        "record_start_at": settings.record_start_at.isoformat(),
    }


@router.get("/bitget/recorded-data")
def bitget_recorded_data(
    order_limit: int = Query(200, ge=1, le=1000),
    fill_limit: int = Query(200, ge=1, le=1000),
    issue_limit: int = Query(50, ge=1, le=500),
    log_limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    record_start = settings.record_start_at.astimezone(timezone.utc)
    real_run_filter = BacktestRun.data_source == "bitget_api_v2"

    order_base = (
        select(OrderRecord)
        .join(BacktestRun, BacktestRun.run_id == OrderRecord.run_id)
        .where(real_run_filter, OrderRecord.order_time.is_not(None), OrderRecord.order_time >= record_start)
    )
    fill_base = (
        select(FillRecord)
        .join(BacktestRun, BacktestRun.run_id == FillRecord.run_id)
        .where(real_run_filter, FillRecord.fill_time.is_not(None), FillRecord.fill_time >= record_start)
    )
    run_ids = select(BacktestRun.run_id).where(real_run_filter)

    total_runs = db.scalar(select(func.count()).select_from(BacktestRun).where(real_run_filter)) or 0
    total_orders = db.scalar(select(func.count()).select_from(order_base.order_by(None).subquery())) or 0
    total_fills = db.scalar(select(func.count()).select_from(fill_base.order_by(None).subquery())) or 0
    last_order_time = db.scalar(
        select(func.max(OrderRecord.order_time))
        .join(BacktestRun, BacktestRun.run_id == OrderRecord.run_id)
        .where(real_run_filter, OrderRecord.order_time.is_not(None), OrderRecord.order_time >= record_start)
    )
    last_fill_time = db.scalar(
        select(func.max(FillRecord.fill_time))
        .join(BacktestRun, BacktestRun.run_id == FillRecord.run_id)
        .where(real_run_filter, FillRecord.fill_time.is_not(None), FillRecord.fill_time >= record_start)
    )

    order_rows = db.execute(
        select(OrderRecord, BacktestRun.title, BacktestRun.imported_at)
        .join(BacktestRun, BacktestRun.run_id == OrderRecord.run_id)
        .where(real_run_filter, OrderRecord.order_time.is_not(None), OrderRecord.order_time >= record_start)
        .order_by(OrderRecord.order_time.desc(), OrderRecord.id.desc())
        .limit(order_limit)
    ).all()
    fill_rows = db.execute(
        select(FillRecord, BacktestRun.title, BacktestRun.imported_at)
        .join(BacktestRun, BacktestRun.run_id == FillRecord.run_id)
        .where(real_run_filter, FillRecord.fill_time.is_not(None), FillRecord.fill_time >= record_start)
        .order_by(FillRecord.fill_time.desc(), FillRecord.id.desc())
        .limit(fill_limit)
    ).all()
    issue_rows = db.scalars(
        select(ImportRowIssue)
        .where(ImportRowIssue.run_id.in_(run_ids))
        .order_by(ImportRowIssue.created_at.desc(), ImportRowIssue.id.desc())
        .limit(issue_limit)
    ).all()
    log_rows = db.scalars(
        select(AuditLog)
        .where(AuditLog.target_id.in_(run_ids))
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(log_limit)
    ).all()

    def order_item(row: OrderRecord, run_title: str | None, imported_at: datetime) -> dict[str, Any]:
        return {
            "id": row.id,
            "run_id": row.run_id,
            "run_title": run_title,
            "imported_at": imported_at,
            "order_id": row.order_id,
            "trade_id": row.trade_id,
            "symbol": row.symbol,
            "side": row.side,
            "order_type": row.order_type,
            "order_time": row.order_time,
            "status": row.status,
            "price": row.price,
            "qty": row.qty,
            "filled_qty": row.filled_qty,
            "reduce_only": row.reduce_only,
            "position_effect": row.position_effect,
            "parent_order_id": row.parent_order_id,
            "metadata_json": row.metadata_json,
        }

    def fill_item(row: FillRecord, run_title: str | None, imported_at: datetime) -> dict[str, Any]:
        return {
            "id": row.id,
            "run_id": row.run_id,
            "run_title": run_title,
            "imported_at": imported_at,
            "fill_id": row.fill_id,
            "order_id": row.order_id,
            "trade_id": row.trade_id,
            "symbol": row.symbol,
            "side": row.side,
            "fill_time": row.fill_time,
            "price": row.price,
            "qty": row.qty,
            "notional": row.notional,
            "fee": row.fee,
            "fee_currency": row.fee_currency,
            "liquidity": row.liquidity,
            "position_effect": row.position_effect,
            "realized_pnl": row.realized_pnl,
            "metadata_json": row.metadata_json,
        }

    return {
        "source": "bitget_api_v2",
        "record_start_at": record_start,
        "summary": {
            "real_import_runs": total_runs,
            "orders": total_orders,
            "fills": total_fills,
            "last_order_time": last_order_time,
            "last_fill_time": last_fill_time,
        },
        "orders": [order_item(row, run_title, imported_at) for row, run_title, imported_at in order_rows],
        "fills": [fill_item(row, run_title, imported_at) for row, run_title, imported_at in fill_rows],
        "row_issues": [
            {
                "id": row.id,
                "run_id": row.run_id,
                "file_name": row.file_name,
                "row_number": row.row_number,
                "issue_code": row.issue_code,
                "message": row.message,
                "created_at": row.created_at,
            }
            for row in issue_rows
        ],
        "audit_logs": [
            {
                "id": row.id,
                "action": row.action,
                "target_type": row.target_type,
                "target_id": row.target_id,
                "details_json": row.details_json,
                "created_at": row.created_at,
            }
            for row in log_rows
        ],
    }


@router.post("/bitget/import-readonly", response_model=ImportResult)
def import_bitget_readonly(
    payload: BitgetImportRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ImportResult:
    try:
        return BitgetImportService(db, settings).import_read_only_history(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail="Bitget API 回傳 HTTP 錯誤，請確認金鑰權限、交易對與時間範圍") from exc


@router.get("/runs", response_model=Page[RunSummary])
def list_runs(
    q: str | None = None,
    strategy_name: str | None = None,
    strategy_version: str | None = None,
    exchange: str | None = None,
    market_type: str | None = None,
    timeframe: str | None = None,
    tag: str | None = None,
    include_archived: bool = False,
    sort_by: str = "imported_at",
    sort_dir: str = "desc",
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> Page[RunSummary]:
    stmt = select(BacktestRun)
    if not include_archived:
        stmt = stmt.where(BacktestRun.archived_at.is_(None))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(BacktestRun.run_id.ilike(like), BacktestRun.title.ilike(like), BacktestRun.strategy_name.ilike(like)))
    filters = {
        BacktestRun.strategy_name: strategy_name,
        BacktestRun.strategy_version: strategy_version,
        BacktestRun.exchange: exchange,
        BacktestRun.market_type: market_type,
        BacktestRun.timeframe: timeframe,
    }
    for column, value in filters.items():
        if value:
            stmt = stmt.where(column == value)
    if tag:
        stmt = stmt.join(RunTag, RunTag.run_id == BacktestRun.run_id).where(RunTag.tag == tag)
    metric_sort = sort_by in COMMON_METRICS
    if metric_sort:
        metric_subq = (
            select(BacktestMetric.run_id, BacktestMetric.metric_value_numeric.label("sort_value"))
            .where(BacktestMetric.metric_key == sort_by)
            .subquery()
        )
        stmt = stmt.outerjoin(metric_subq, metric_subq.c.run_id == BacktestRun.run_id)
        order_col = metric_subq.c.sort_value
    else:
        order_col = getattr(BacktestRun, sort_by, BacktestRun.imported_at)
    stmt = stmt.order_by(desc(order_col) if sort_dir == "desc" else asc(order_col))
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    runs = db.scalars(apply_pagination(stmt, limit, offset)).all()
    metric_map = metrics_for_runs(db, [run.run_id for run in runs])
    return Page(items=[run_summary_from_model(run, metric_map.get(run.run_id, {})) for run in runs], total=total, limit=limit, offset=offset)


@router.get("/runs/{run_id}", response_model=RunDetail)
def get_run(run_id: str, db: Session = Depends(get_db)) -> RunDetail:
    run = require_run(db, run_id)
    metrics = metrics_for_runs(db, [run_id]).get(run_id, {})
    files = [
        {
            "id": item.id,
            "file_name": item.file_name,
            "file_type": item.file_type,
            "file_hash": item.file_hash,
            "row_count": item.row_count,
            "validation_status": item.validation_status,
        }
        for item in db.scalars(select(ImportFile).where(ImportFile.run_id == run_id).order_by(ImportFile.file_name)).all()
    ]
    return run_detail_from_model(run, metrics, files)


@router.patch("/runs/{run_id}", response_model=RunDetail)
def patch_run(run_id: str, payload: RunPatch, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> RunDetail:
    run = require_run(db, run_id)
    if payload.title is not None:
        run.title = payload.title
    if payload.tags is not None:
        run.tags = sorted({tag.strip() for tag in payload.tags if tag.strip()})
        db.query(RunTag).filter(RunTag.run_id == run_id).delete()
        for tag in run.tags:
            db.add(RunTag(run_id=run_id, tag=tag))
    if payload.notes is not None:
        run.notes = payload.notes
    if payload.status is not None:
        run.status = payload.status
    db.add(AuditLog(actor=settings.default_user_email, action="patch_run", target_type="backtest_run", target_id=run_id, details_json=payload.model_dump(exclude_none=True)))
    db.commit()
    db.refresh(run)
    return get_run(run_id, db)


@router.post("/runs/{run_id}/archive", response_model=RunDetail)
def archive_run(run_id: str, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> RunDetail:
    run = require_run(db, run_id)
    run.status = "archived"
    run.archived_at = utcnow()
    db.add(AuditLog(actor=settings.default_user_email, action="archive_run", target_type="backtest_run", target_id=run_id, details_json={}))
    db.commit()
    db.refresh(run)
    return get_run(run_id, db)


@router.delete("/runs/{run_id}", response_model=RunDetail)
def delete_run(run_id: str, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> RunDetail:
    run = require_run(db, run_id)
    run.status = "deleted"
    run.archived_at = utcnow()
    db.add(AuditLog(actor=settings.default_user_email, action="soft_delete_run", target_type="backtest_run", target_id=run_id, details_json={}))
    db.commit()
    db.refresh(run)
    return get_run(run_id, db)


@router.get("/runs/{run_id}/metrics", response_model=list[MetricItem])
def get_metrics(run_id: str, db: Session = Depends(get_db)) -> list[MetricItem]:
    require_run(db, run_id)
    rows = db.scalars(select(BacktestMetric).where(BacktestMetric.run_id == run_id).order_by(BacktestMetric.metric_key)).all()
    return [MetricItem.model_validate(row, from_attributes=True) for row in rows]


@router.get("/runs/{run_id}/config", response_model=ConfigResponse)
def get_config(run_id: str, db: Session = Depends(get_db)) -> ConfigResponse:
    require_run(db, run_id)
    config = db.scalar(select(BacktestConfig).where(BacktestConfig.run_id == run_id))
    if not config:
        raise HTTPException(status_code=404, detail="找不到設定檔")
    return ConfigResponse(run_id=run_id, config_json=config.config_json, config_hash=config.config_hash)


@router.get("/runs/{run_id}/config-diff", response_model=ConfigDiffResponse)
def get_config_diff(run_id: str, compare_to: str, db: Session = Depends(get_db)) -> ConfigDiffResponse:
    left = get_config(run_id, db)
    right = get_config(compare_to, db)
    return ConfigDiffResponse(run_id=run_id, compare_to=compare_to, differences=flatten_diff(left.config_json, right.config_json))


@router.get("/runs/{run_id}/equity", response_model=list[EquityPointOut])
def get_equity(run_id: str, limit: int = Query(5000, ge=1, le=20000), db: Session = Depends(get_db)) -> list[EquityPointOut]:
    require_run(db, run_id)
    rows = db.scalars(select(EquityPoint).where(EquityPoint.run_id == run_id).order_by(EquityPoint.timestamp).limit(limit)).all()
    return [EquityPointOut.model_validate(row) for row in rows]


@router.get("/runs/{run_id}/trades", response_model=Page[TradeOut])
def get_trades(
    run_id: str,
    symbol: str | None = None,
    side: str | None = None,
    exit_reason: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    sort_by: str = "entry_time",
    sort_dir: str = "desc",
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> Page[TradeOut]:
    require_run(db, run_id)
    stmt = select(Trade).where(Trade.run_id == run_id)
    if symbol:
        stmt = stmt.where(Trade.symbol == symbol)
    if side:
        stmt = stmt.where(Trade.side == side.lower())
    if exit_reason:
        stmt = stmt.where(Trade.exit_reason == exit_reason)
    if start_time:
        stmt = stmt.where(Trade.entry_time >= start_time)
    if end_time:
        stmt = stmt.where(Trade.entry_time <= end_time)
    order_col = getattr(Trade, sort_by, Trade.entry_time)
    stmt = stmt.order_by(desc(order_col) if sort_dir == "desc" else asc(order_col))
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    rows = db.scalars(apply_pagination(stmt, limit, offset)).all()
    return Page(items=[TradeOut.model_validate(row) for row in rows], total=total, limit=limit, offset=offset)


@router.get("/runs/{run_id}/trades/export")
def export_trades(run_id: str, db: Session = Depends(get_db)) -> StreamingResponse:
    require_run(db, run_id)
    rows = db.scalars(select(Trade).where(Trade.run_id == run_id).order_by(Trade.entry_time)).all()
    tmp = tempfile.NamedTemporaryFile(mode="w", delete=False, newline="", encoding="utf-8-sig", suffix=".csv")
    columns = [
        "trade_id",
        "symbol",
        "side",
        "entry_time",
        "exit_time",
        "entry_price",
        "exit_price",
        "qty",
        "notional",
        "gross_pnl",
        "fee",
        "slippage",
        "funding",
        "net_pnl",
        "return_pct",
        "holding_minutes",
        "exit_reason",
    ]
    writer = csv.DictWriter(tmp, fieldnames=columns)
    writer.writeheader()
    for row in rows:
        writer.writerow({col: getattr(row, col).isoformat() if isinstance(getattr(row, col), datetime) else getattr(row, col) for col in columns})
    tmp.close()
    return FileResponse(tmp.name, media_type="text/csv", filename=f"{run_id}_trades.csv")


@router.get("/runs/{run_id}/orders", response_model=Page[OrderOut])
def get_orders(
    run_id: str,
    symbol: str | None = None,
    position_effect: str | None = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> Page[OrderOut]:
    require_run(db, run_id)
    stmt = select(OrderRecord).where(OrderRecord.run_id == run_id)
    if symbol:
        stmt = stmt.where(OrderRecord.symbol == symbol)
    if position_effect:
        stmt = stmt.where(OrderRecord.position_effect == position_effect)
    stmt = stmt.order_by(OrderRecord.order_time.desc().nullslast(), OrderRecord.id.desc())
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    rows = db.scalars(apply_pagination(stmt, limit, offset)).all()
    return Page(items=[OrderOut.model_validate(row) for row in rows], total=total, limit=limit, offset=offset)


@router.get("/runs/{run_id}/fills", response_model=Page[FillOut])
def get_fills(
    run_id: str,
    symbol: str | None = None,
    position_effect: str | None = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> Page[FillOut]:
    require_run(db, run_id)
    stmt = select(FillRecord).where(FillRecord.run_id == run_id)
    if symbol:
        stmt = stmt.where(FillRecord.symbol == symbol)
    if position_effect:
        stmt = stmt.where(FillRecord.position_effect == position_effect)
    stmt = stmt.order_by(FillRecord.fill_time.desc().nullslast(), FillRecord.id.desc())
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    rows = db.scalars(apply_pagination(stmt, limit, offset)).all()
    return Page(items=[FillOut.model_validate(row) for row in rows], total=total, limit=limit, offset=offset)


@router.get("/runs/{run_id}/positions", response_model=Page[PositionOut])
def get_positions(
    run_id: str,
    symbol: str | None = None,
    position_effect: str | None = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> Page[PositionOut]:
    require_run(db, run_id)
    stmt = select(PositionRecord).where(PositionRecord.run_id == run_id)
    if symbol:
        stmt = stmt.where(PositionRecord.symbol == symbol)
    if position_effect:
        stmt = stmt.where(PositionRecord.position_effect == position_effect)
    stmt = stmt.order_by(PositionRecord.timestamp.desc().nullslast(), PositionRecord.id.desc())
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    rows = db.scalars(apply_pagination(stmt, limit, offset)).all()
    return Page(items=[PositionOut.model_validate(row) for row in rows], total=total, limit=limit, offset=offset)


@router.get("/runs/{run_id}/import-row-issues")
def get_import_row_issues(
    run_id: str,
    file_name: str | None = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    require_run(db, run_id)
    stmt = select(ImportRowIssue).where(ImportRowIssue.run_id == run_id)
    if file_name:
        stmt = stmt.where(ImportRowIssue.file_name == file_name)
    stmt = stmt.order_by(ImportRowIssue.id)
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    rows = db.scalars(apply_pagination(stmt, limit, offset)).all()
    return {
        "items": [
            {
                "id": row.id,
                "file_name": row.file_name,
                "row_number": row.row_number,
                "issue_code": row.issue_code,
                "message": row.message,
                "raw_row_json": row.raw_row_json,
                "created_at": row.created_at,
            }
            for row in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/runs/{run_id}/symbols", response_model=Page[SymbolSummaryOut])
def get_symbols(run_id: str, symbol: str | None = None, limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0), db: Session = Depends(get_db)) -> Page[SymbolSummaryOut]:
    require_run(db, run_id)
    stmt = select(SymbolSummary).where(SymbolSummary.run_id == run_id)
    if symbol:
        stmt = stmt.where(SymbolSummary.symbol == symbol)
    stmt = stmt.order_by(SymbolSummary.symbol)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(apply_pagination(stmt, limit, offset)).all()
    return Page(items=[SymbolSummaryOut.model_validate(row) for row in rows], total=total, limit=limit, offset=offset)


@router.get("/runs/{run_id}/costs", response_model=list[CostSummaryOut])
def get_costs(run_id: str, db: Session = Depends(get_db)) -> list[CostSummaryOut]:
    require_run(db, run_id)
    rows = db.scalars(select(CostSummary).where(CostSummary.run_id == run_id).order_by(CostSummary.category)).all()
    return [CostSummaryOut.model_validate(row) for row in rows]


@router.get("/runs/{run_id}/candidates", response_model=Page[CandidateSnapshotOut])
def get_candidates(
    run_id: str,
    symbol: str | None = None,
    is_selected: bool | None = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> Page[CandidateSnapshotOut]:
    require_run(db, run_id)
    stmt = select(CandidateSnapshot).where(CandidateSnapshot.run_id == run_id)
    if symbol:
        stmt = stmt.where(CandidateSnapshot.symbol == symbol)
    if is_selected is not None:
        stmt = stmt.where(CandidateSnapshot.is_selected == is_selected)
    stmt = stmt.order_by(CandidateSnapshot.timestamp.desc(), CandidateSnapshot.symbol)
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    rows = db.scalars(apply_pagination(stmt, limit, offset)).all()
    return Page(items=[CandidateSnapshotOut.model_validate(row) for row in rows], total=total, limit=limit, offset=offset)


@router.get("/compare", response_model=CompareResponse)
def compare_runs(run_ids: str, db: Session = Depends(get_db)) -> CompareResponse:
    ids = [item.strip() for item in run_ids.split(",") if item.strip()]
    if len(ids) < 2:
        raise HTTPException(status_code=400, detail="請至少選擇兩個 run_id")
    runs = db.scalars(select(BacktestRun).where(BacktestRun.run_id.in_(ids))).all()
    metrics = metrics_for_runs(db, ids)
    equity: dict[str, list[EquityPointOut]] = {}
    for run_id in ids:
        rows = db.scalars(select(EquityPoint).where(EquityPoint.run_id == run_id).order_by(EquityPoint.timestamp).limit(2000)).all()
        equity[run_id] = [EquityPointOut.model_validate(row) for row in rows]
    diffs: dict[str, list[ConfigDiffItem]] = {}
    base = ids[0]
    for compare_to in ids[1:]:
        diffs[f"{base}__{compare_to}"] = get_config_diff(base, compare_to, db).differences
    return CompareResponse(
        run_ids=ids,
        runs=[run_summary_from_model(run, metrics.get(run.run_id, {})) for run in runs],
        metrics=metrics,
        equity=equity,
        config_diffs=diffs,
    )


@router.get("/aggregate/runs")
def aggregate_runs(db: Session = Depends(get_db)) -> dict[str, Any]:
    total_runs = db.scalar(select(func.count()).select_from(BacktestRun).where(BacktestRun.archived_at.is_(None))) or 0
    total_trades = db.scalar(select(func.count()).select_from(Trade)) or 0
    return {"total_runs": total_runs, "total_trades": total_trades}


@router.get("/aggregate/by-strategy")
def aggregate_by_strategy(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    rows = db.execute(select(BacktestRun.strategy_name, func.count()).group_by(BacktestRun.strategy_name).order_by(func.count().desc())).all()
    return [{"strategy_name": row[0] or "未指定", "count": row[1]} for row in rows]


@router.get("/aggregate/by-symbol")
def aggregate_by_symbol(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    rows = db.execute(select(Trade.symbol, func.count()).where(Trade.symbol.is_not(None)).group_by(Trade.symbol).order_by(func.count().desc()).limit(200)).all()
    return [{"symbol": row[0], "trade_count": row[1]} for row in rows]


@router.get("/aggregate/by-tag")
def aggregate_by_tag(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    rows = db.execute(select(RunTag.tag, func.count()).group_by(RunTag.tag).order_by(func.count().desc())).all()
    return [{"tag": row[0], "count": row[1]} for row in rows]


@router.get("/dashboard", response_model=DashboardStats)
def dashboard(db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> DashboardStats:
    runs = db.scalars(select(BacktestRun).where(BacktestRun.archived_at.is_(None)).order_by(BacktestRun.imported_at.desc()).limit(5)).all()
    metrics = metrics_for_runs(db, [run.run_id for run in runs])
    total_runs = db.scalar(select(func.count()).select_from(BacktestRun).where(BacktestRun.archived_at.is_(None))) or 0
    total_trades = db.scalar(select(func.count()).select_from(Trade)) or 0
    stored_bytes = 0
    storage_root = settings.storage_root
    if storage_root.exists():
        stored_bytes = sum(path.stat().st_size for path in storage_root.rglob("*") if path.is_file())
    imported_rows = db.execute(
        select(func.date(BacktestRun.imported_at), func.count()).group_by(func.date(BacktestRun.imported_at)).order_by(func.date(BacktestRun.imported_at))
    ).all()

    def distribution(column, key: str) -> list[dict[str, Any]]:
        rows = db.execute(select(column, func.count()).group_by(column).order_by(func.count().desc())).all()
        return [{key: row[0] or "未指定", "count": row[1]} for row in rows]

    return DashboardStats(
        total_runs=total_runs,
        total_trades=total_trades,
        stored_bytes=stored_bytes,
        recent_runs=[run_summary_from_model(run, metrics.get(run.run_id, {})) for run in runs],
        runs_imported_over_time=[{"date": str(row[0]), "count": row[1]} for row in imported_rows],
        strategy_distribution=distribution(BacktestRun.strategy_name, "name"),
        market_type_distribution=distribution(BacktestRun.market_type, "name"),
        exchange_distribution=distribution(BacktestRun.exchange, "name"),
        tag_distribution=aggregate_by_tag(db),
        timeframe_distribution=distribution(BacktestRun.timeframe, "name"),
    )


@router.get("/runs/{run_id}/notes", response_model=list[NoteOut])
def get_notes(run_id: str, db: Session = Depends(get_db)) -> list[NoteOut]:
    require_run(db, run_id)
    rows = db.scalars(select(Note).where(Note.run_id == run_id).order_by(Note.created_at.desc())).all()
    return [NoteOut.model_validate(row) for row in rows]


@router.post("/runs/{run_id}/notes", response_model=NoteOut)
def create_note(run_id: str, payload: NoteCreate, db: Session = Depends(get_db)) -> NoteOut:
    require_run(db, run_id)
    note = Note(run_id=run_id, content=payload.content)
    db.add(note)
    db.commit()
    db.refresh(note)
    return NoteOut.model_validate(note)


@router.patch("/notes/{note_id}", response_model=NoteOut)
def update_note(note_id: int, payload: NoteUpdate, db: Session = Depends(get_db)) -> NoteOut:
    note = db.get(Note, note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="找不到備註")
    note.content = payload.content
    db.commit()
    db.refresh(note)
    return NoteOut.model_validate(note)


@router.delete("/notes/{note_id}")
def delete_note(note_id: int, db: Session = Depends(get_db)) -> dict[str, bool]:
    note = db.get(Note, note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="找不到備註")
    db.delete(note)
    db.commit()
    return {"ok": True}


@router.post("/runs/{run_id}/attachments", response_model=AttachmentOut)
async def upload_attachment(run_id: str, file: UploadFile = File(...), db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> AttachmentOut:
    require_run(db, run_id)
    name = sanitize_filename(file.filename or "attachment")
    target_dir = settings.storage_root / "runs" / sanitize_filename(run_id) / "attachments"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / name
    size = 0
    max_bytes = settings.max_upload_mb * 1024 * 1024
    with target.open("wb") as handle:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > max_bytes:
                target.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail=f"檔案超過上限 {settings.max_upload_mb} MB")
            handle.write(chunk)
    attachment = Attachment(run_id=run_id, file_name=name, file_path=str(target), file_hash=sha256_file(target), file_size=size, mime_type=file.content_type)
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return AttachmentOut.model_validate(attachment)


@router.get("/runs/{run_id}/attachments", response_model=list[AttachmentOut])
def list_attachments(run_id: str, db: Session = Depends(get_db)) -> list[AttachmentOut]:
    require_run(db, run_id)
    rows = db.scalars(select(Attachment).where(Attachment.run_id == run_id).order_by(Attachment.created_at.desc())).all()
    return [AttachmentOut.model_validate(row) for row in rows]


@router.get("/attachments/{attachment_id}/download")
def download_attachment(attachment_id: int, db: Session = Depends(get_db)) -> FileResponse:
    attachment = db.get(Attachment, attachment_id)
    if attachment is None:
        raise HTTPException(status_code=404, detail="找不到附件")
    return FileResponse(attachment.file_path, filename=attachment.file_name, media_type=attachment.mime_type)


@router.get("/runs/{run_id}/files/{file_id}/download")
def download_import_file(run_id: str, file_id: int, db: Session = Depends(get_db)) -> FileResponse:
    require_run(db, run_id)
    item = db.get(ImportFile, file_id)
    if item is None or item.run_id != run_id:
        raise HTTPException(status_code=404, detail="找不到匯入檔案")
    return FileResponse(item.file_path, filename=item.file_name)


@router.get("/runs/{run_id}/export")
def export_run(run_id: str, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> FileResponse:
    require_run(db, run_id)
    source = settings.storage_root / "runs" / sanitize_filename(run_id) / "raw"
    if not source.exists():
        raise HTTPException(status_code=404, detail="找不到原始檔案資料夾")
    target = Path(tempfile.gettempdir()) / f"{sanitize_filename(run_id)}_export.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for item in source.rglob("*"):
            if item.is_file():
                archive.write(item, item.relative_to(source))
    return FileResponse(target, filename=f"{run_id}_export.zip", media_type="application/zip")


@router.get("/export/all")
def export_all(db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> FileResponse:
    target = Path(tempfile.gettempdir()) / f"backtest_records_export_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for run in db.scalars(select(BacktestRun)).all():
            source = settings.storage_root / "runs" / sanitize_filename(run.run_id) / "raw"
            if source.exists():
                for item in source.rglob("*"):
                    if item.is_file():
                        archive.write(item, Path(run.run_id) / item.relative_to(source))
    return FileResponse(target, filename=target.name, media_type="application/zip")


TABLES = {
    "runs": BacktestRun,
    "metrics": BacktestMetric,
    "trades": Trade,
    "orders": OrderRecord,
    "fills": FillRecord,
    "positions": PositionRecord,
    "equity": EquityPoint,
    "symbols": SymbolSummary,
    "costs": CostSummary,
    "candidates": CandidateSnapshot,
}


@router.post("/explorer/query")
def explorer_query(payload: SafeQueryFilter, db: Session = Depends(get_db)) -> dict[str, Any]:
    model = TABLES.get(payload.table)
    if model is None:
        raise HTTPException(status_code=400, detail="不支援的資料表")
    allowed_columns = {column.name: getattr(model, column.name) for column in model.__table__.columns}
    columns = payload.columns or list(allowed_columns.keys())[:20]
    if any(column not in allowed_columns for column in columns):
        raise HTTPException(status_code=400, detail="包含不支援的欄位")
    stmt = select(*[allowed_columns[column] for column in columns])
    if payload.run_id and "run_id" in allowed_columns:
        stmt = stmt.where(allowed_columns["run_id"] == payload.run_id)
    for key, value in payload.filters.items():
        if key in allowed_columns and value not in (None, ""):
            stmt = stmt.where(allowed_columns[key] == value)
    if payload.sort_by in allowed_columns:
        stmt = stmt.order_by(desc(allowed_columns[payload.sort_by]) if payload.sort_dir == "desc" else asc(allowed_columns[payload.sort_by]))
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    rows = db.execute(stmt.limit(payload.limit).offset(payload.offset)).all()
    return {"items": [dict(zip(columns, row, strict=False)) for row in rows], "total": total, "limit": payload.limit, "offset": payload.offset}
