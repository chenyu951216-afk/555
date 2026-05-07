from __future__ import annotations

import csv
import hashlib
import json
import mimetypes
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
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
    User,
    Workspace,
)
from app.schemas.common import FileValidationSummary, ImportResult, ValidationIssue, ValidationReport
from app.schemas.imports import Manifest


REQUIRED_FILES = {"manifest.json", "config.json", "metrics.json"}
OPTIONAL_FILES = {
    "equity_curve.csv",
    "trades.csv",
    "symbol_summary.csv",
    "cost_summary.csv",
    "positions.csv",
    "orders.csv",
    "fills.csv",
    "candidate_snapshot.csv",
    "notes.md",
}
FILE_TYPES = {
    "manifest.json": "manifest",
    "config.json": "config",
    "metrics.json": "metrics",
    "equity_curve.csv": "equity",
    "trades.csv": "trades",
    "orders.csv": "orders",
    "fills.csv": "fills",
    "positions.csv": "positions",
    "symbol_summary.csv": "symbol_summary",
    "cost_summary.csv": "cost_summary",
    "candidate_snapshot.csv": "candidate_snapshot",
    "notes.md": "notes",
}
TRADE_NUMERIC_FIELDS = {
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
}
EQUITY_NUMERIC_FIELDS = {
    "equity",
    "cash",
    "position_value",
    "unrealized_pnl",
    "realized_pnl",
    "drawdown",
    "exposure",
    "leverage",
}
SYMBOL_NUMERIC_FIELDS = {
    "gross_pnl",
    "net_pnl",
    "fee_total",
    "slippage_total",
    "funding_total",
    "win_rate",
    "avg_return",
    "max_drawdown",
    "avg_holding_minutes",
}
SYMBOL_INT_FIELDS = {"trade_count", "selection_count"}
COST_NUMERIC_FIELDS = {"amount", "bps"}
CANDIDATE_NUMERIC_FIELDS = {"score", "volume_24h", "spread_bps", "volatility"}
ORDER_NUMERIC_FIELDS = {"price", "qty", "filled_qty"}
FILL_NUMERIC_FIELDS = {"price", "qty", "notional", "fee", "realized_pnl"}
POSITION_NUMERIC_FIELDS = {"qty", "avg_price", "market_price", "notional", "unrealized_pnl", "realized_pnl"}
POSITION_EFFECTS = {"open", "increase", "reduce", "partial_close", "close", "partial_take_profit", "stop_loss", "unknown"}


@dataclass
class PreparedImport:
    folder: Path
    files: dict[str, Path]
    manifest: Manifest | None
    config_json: dict[str, Any] | None
    metrics_json: dict[str, Any] | None
    report: ValidationReport
    temp_root: Path | None = None


def sanitize_filename(name: str) -> str:
    clean = Path(name.replace("\\", "/")).name
    return "".join(ch for ch in clean if ch.isalnum() or ch in "._- ()[]").strip() or "file"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_json(data: Any) -> str:
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def parse_datetime(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        raw = str(value).strip()
        if raw.endswith("Z"):
            raw = f"{raw[:-1]}+00:00"
        dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"invalid numeric value: {value}") from exc


def parse_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(Decimal(str(value)))


def parse_bool(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    lowered = str(value).strip().lower()
    if lowered in {"true", "1", "yes", "y"}:
        return True
    if lowered in {"false", "0", "no", "n"}:
        return False
    raise ValueError(f"invalid boolean value: {value}")


def tolerant(parse_fn, value: Any, field: str, warnings: list[dict[str, str]]) -> Any:
    try:
        return parse_fn(value)
    except Exception as exc:
        warnings.append({"field": field, "message": str(exc), "raw_value": "" if value is None else str(value)})
        return None


def normalize_position_effect(row: dict[str, Any]) -> str | None:
    raw = (
        row.get("position_effect")
        or row.get("effect")
        or row.get("position_action")
        or row.get("action")
        or row.get("open_close")
        or ""
    )
    value = str(raw).strip().lower()
    aliases = {
        "entry": "open",
        "open": "open",
        "increase": "increase",
        "add": "increase",
        "add_position": "increase",
        "exit": "close",
        "close": "close",
        "reduce": "reduce",
        "partial": "partial_close",
        "partial_close": "partial_close",
        "partial_take_profit": "partial_take_profit",
        "partial_tp": "partial_take_profit",
        "take_profit": "partial_take_profit",
        "tp": "partial_take_profit",
        "stop": "stop_loss",
        "sl": "stop_loss",
    }
    if value in aliases:
        return aliases[value]
    if value in POSITION_EFFECTS:
        return value
    reduce_only = row.get("reduce_only")
    try:
        if parse_bool(reduce_only) is True:
            return "reduce"
    except Exception:
        pass
    return value or None


def first_value(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def is_after_record_start(value: datetime | None, record_start: datetime) -> bool:
    return value is not None and value >= record_start


def issue(level: str, code: str, message: str, file_name: str | None = None, row: int | None = None, field: str | None = None) -> ValidationIssue:
    return ValidationIssue(level=level, code=code, message=message, file_name=file_name, row=row, field=field)


def csv_summary(path: Path, file_name: str) -> FileValidationSummary:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = list(reader.fieldnames or [])
        row_count = sum(1 for _ in reader)
    return FileValidationSummary(
        file_name=file_name,
        file_type=FILE_TYPES.get(file_name),
        file_hash=sha256_file(path),
        row_count=row_count,
        columns=columns,
    )


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("JSON root must be an object")
    return data


def detect_import_root(extract_dir: Path) -> Path:
    if (extract_dir / "manifest.json").exists():
        return extract_dir
    children = [item for item in extract_dir.iterdir() if item.is_dir()]
    for child in children:
        if (child / "manifest.json").exists():
            return child
    return extract_dir


def safe_extract_zip(zip_path: Path, target_dir: Path) -> None:
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            member_path = Path(member.filename)
            if member_path.is_absolute() or ".." in member_path.parts:
                raise ValueError(f"unsafe zip entry: {member.filename}")
        archive.extractall(target_dir)


class BacktestImporter:
    def __init__(self, db: Session, settings: Settings):
        self.db = db
        self.settings = settings

    def validate_zip(self, zip_path: Path, record_start_at: datetime | None = None) -> PreparedImport:
        temp_dir = Path(tempfile.mkdtemp(prefix="backtest-validate-"))
        safe_extract_zip(zip_path, temp_dir)
        root = detect_import_root(temp_dir)
        return self.validate_folder(root, record_start_at=record_start_at, temp_root=temp_dir)

    def validate_folder(self, folder: Path, record_start_at: datetime | None = None, temp_root: Path | None = None) -> PreparedImport:
        record_start = (record_start_at or self.settings.record_start_at).astimezone(timezone.utc)
        files = {item.name: item for item in folder.iterdir() if item.is_file()}
        lower_lookup = {name.lower(): path for name, path in files.items()}
        normalized = {name: lower_lookup[name] for name in lower_lookup}
        report = ValidationReport(ok=True, record_start_at=record_start)
        manifest: Manifest | None = None
        config_json: dict[str, Any] | None = None
        metrics_json: dict[str, Any] | None = None

        missing = sorted(REQUIRED_FILES - set(normalized))
        for file_name in missing:
            report.errors.append(issue("error", "missing_required_file", f"缺少必要檔案 {file_name}", file_name=file_name))

        if "manifest.json" in normalized:
            try:
                raw_manifest = read_json(normalized["manifest.json"])
                manifest = Manifest.model_validate(raw_manifest)
                report.run_id = manifest.run_id
                exists = self.db.scalar(select(BacktestRun.id).where(BacktestRun.run_id == manifest.run_id))
                if exists:
                    report.errors.append(issue("error", "duplicate_run_id", f"run_id 已存在：{manifest.run_id}", "manifest.json", field="run_id"))
            except (ValueError, json.JSONDecodeError) as exc:
                report.errors.append(issue("error", "invalid_manifest_json", f"manifest.json 無法解析：{exc}", "manifest.json"))
            except ValidationError as exc:
                for err in exc.errors():
                    loc = ".".join(str(part) for part in err.get("loc", [])) or None
                    report.errors.append(issue("error", "manifest_validation_error", str(err.get("msg")), "manifest.json", field=loc))

        if "config.json" in normalized:
            try:
                config_json = read_json(normalized["config.json"])
                report.config_hash = sha256_json(config_json)
            except (ValueError, json.JSONDecodeError) as exc:
                report.errors.append(issue("error", "invalid_config_json", f"config.json 無法解析：{exc}", "config.json"))

        if "metrics.json" in normalized:
            try:
                metrics_json = read_json(normalized["metrics.json"])
            except (ValueError, json.JSONDecodeError) as exc:
                report.errors.append(issue("error", "invalid_metrics_json", f"metrics.json 無法解析：{exc}", "metrics.json"))

        for file_name, path in normalized.items():
            if file_name.endswith(".csv"):
                summary = csv_summary(path, file_name)
                self._validate_csv_rows(path, file_name, summary, record_start)
                report.errors.extend(summary.errors)
                report.warnings.extend(summary.warnings)
            else:
                summary = FileValidationSummary(
                    file_name=file_name,
                    file_type=FILE_TYPES.get(file_name),
                    file_hash=sha256_file(path),
                    row_count=None,
                    columns=[],
                )
            report.files.append(summary)

        for recommended in ["equity_curve.csv", "trades.csv", "symbol_summary.csv", "cost_summary.csv", "notes.md"]:
            if recommended not in normalized:
                report.warnings.append(issue("warning", "missing_recommended_file", f"未提供建議檔案 {recommended}", recommended))

        if config_json is not None or metrics_json is not None:
            parts = []
            for name in [
                "manifest.json",
                "config.json",
                "metrics.json",
                "trades.csv",
                "orders.csv",
                "fills.csv",
                "positions.csv",
                "equity_curve.csv",
                "symbol_summary.csv",
                "cost_summary.csv",
            ]:
                if name in normalized:
                    parts.append(sha256_file(normalized[name]))
            report.result_hash = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest() if parts else None

        report.ok = not report.errors
        return PreparedImport(folder=folder, files=normalized, manifest=manifest, config_json=config_json, metrics_json=metrics_json, report=report, temp_root=temp_root)

    def import_zip(self, zip_path: Path, record_start_at: datetime | None = None) -> ImportResult:
        prepared = self.validate_zip(zip_path, record_start_at=record_start_at)
        try:
            if not prepared.report.ok or prepared.manifest is None or prepared.config_json is None or prepared.metrics_json is None:
                raise ValueError("validation failed")
            return self._write_import(prepared, original_zip=zip_path)
        finally:
            self.cleanup_prepared(prepared)

    def import_folder(self, folder: Path, record_start_at: datetime | None = None) -> ImportResult:
        prepared = self.validate_folder(folder, record_start_at=record_start_at)
        if not prepared.report.ok or prepared.manifest is None or prepared.config_json is None or prepared.metrics_json is None:
            raise ValueError("validation failed")
        return self._write_import(prepared, original_zip=None)

    @staticmethod
    def cleanup_prepared(prepared: PreparedImport) -> None:
        if prepared.temp_root and prepared.temp_root.exists():
            shutil.rmtree(prepared.temp_root, ignore_errors=True)

    def _validate_csv_rows(self, path: Path, file_name: str, summary: FileValidationSummary, record_start: datetime) -> None:
        required_columns = {
            "equity_curve.csv": {"timestamp", "equity"},
            "trades.csv": {"symbol", "side"},
            "symbol_summary.csv": {"symbol"},
            "cost_summary.csv": {"category"},
            "candidate_snapshot.csv": {"timestamp", "symbol"},
            "orders.csv": {"symbol", "side"},
            "fills.csv": {"symbol", "side"},
            "positions.csv": {"symbol"},
        }.get(file_name, set())
        missing_columns = sorted(required_columns - set(summary.columns))
        for column in missing_columns:
            summary.errors.append(issue("error", "missing_column", f"缺少欄位 {column}", file_name, field=column))

        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row_number, row in enumerate(reader, start=2):
                try:
                    if file_name == "equity_curve.csv":
                        ts = parse_datetime(row.get("timestamp"))
                        if not is_after_record_start(ts, record_start):
                            summary.skipped_rows += 1
                            continue
                        parse_decimal(row.get("equity"))
                        for field in EQUITY_NUMERIC_FIELDS - {"equity"}:
                            parse_decimal(row.get(field))
                    elif file_name == "trades.csv":
                        entry_time = parse_datetime(row.get("entry_time")) if row.get("entry_time") else None
                        if not is_after_record_start(entry_time, record_start):
                            summary.skipped_rows += 1
                            continue
                        if row.get("exit_time"):
                            parse_datetime(row.get("exit_time"))
                        side = (row.get("side") or "").lower()
                        if side and side not in {"long", "short", "buy", "sell"}:
                            summary.warnings.append(issue("warning", "unknown_side", f"side 未在常見值內：{side}", file_name, row_number, "side"))
                        for field in TRADE_NUMERIC_FIELDS:
                            parse_decimal(row.get(field))
                    elif file_name == "orders.csv":
                        order_time = parse_datetime(first_value(row, "order_time", "created_at", "submitted_at", "timestamp"))
                        if not is_after_record_start(order_time, record_start):
                            summary.skipped_rows += 1
                            continue
                        for field in ORDER_NUMERIC_FIELDS:
                            parse_decimal(row.get(field))
                        if row.get("reduce_only"):
                            parse_bool(row.get("reduce_only"))
                    elif file_name == "fills.csv":
                        fill_time = parse_datetime(first_value(row, "fill_time", "timestamp", "created_at"))
                        order_time_raw = first_value(row, "order_time", "order_created_at", "order_submitted_at")
                        record_time = parse_datetime(order_time_raw) if order_time_raw else fill_time
                        if not is_after_record_start(record_time, record_start):
                            summary.skipped_rows += 1
                            continue
                        for field in FILL_NUMERIC_FIELDS:
                            parse_decimal(row.get(field))
                        if row.get("reduce_only"):
                            parse_bool(row.get("reduce_only"))
                    elif file_name == "positions.csv":
                        position_time = parse_datetime(first_value(row, "timestamp", "time", "created_at"))
                        if not is_after_record_start(position_time, record_start):
                            summary.skipped_rows += 1
                            continue
                        for field in POSITION_NUMERIC_FIELDS:
                            parse_decimal(row.get(field))
                    elif file_name == "symbol_summary.csv":
                        for field in SYMBOL_NUMERIC_FIELDS:
                            parse_decimal(row.get(field))
                        for field in SYMBOL_INT_FIELDS:
                            parse_int(row.get(field))
                    elif file_name == "cost_summary.csv":
                        for field in COST_NUMERIC_FIELDS:
                            parse_decimal(row.get(field))
                    elif file_name == "candidate_snapshot.csv":
                        ts = parse_datetime(row.get("timestamp"))
                        if not is_after_record_start(ts, record_start):
                            summary.skipped_rows += 1
                            continue
                        for field in CANDIDATE_NUMERIC_FIELDS:
                            parse_decimal(row.get(field))
                        parse_int(row.get("rank"))
                        for field in ["is_in_universe", "is_candidate", "is_selected"]:
                            parse_bool(row.get(field))
                except Exception as exc:
                    summary.warnings.append(issue("warning", "row_skipped", f"資料列無法完整解析，匯入時會略過：{exc}", file_name, row_number))
                    summary.skipped_rows += 1
        if summary.errors:
            summary.validation_status = "error"
        elif summary.warnings or summary.skipped_rows:
            summary.validation_status = "warning"

    def _ensure_local_user(self) -> tuple[Workspace, User]:
        workspace = self.db.scalar(select(Workspace).where(Workspace.slug == "personal"))
        if workspace is None:
            workspace = Workspace(name=self.settings.default_workspace_name, slug="personal")
            self.db.add(workspace)
            self.db.flush()
        user = self.db.scalar(select(User).where(User.email == self.settings.default_user_email))
        if user is None:
            user = User(workspace_id=workspace.id, email=self.settings.default_user_email, display_name="Local User")
            self.db.add(user)
            self.db.flush()
        return workspace, user

    def _write_import(self, prepared: PreparedImport, original_zip: Path | None) -> ImportResult:
        manifest = prepared.manifest
        assert manifest is not None
        config_json = prepared.config_json or {}
        metrics_json = prepared.metrics_json or {}
        record_start = (prepared.report.record_start_at or self.settings.record_start_at).astimezone(timezone.utc)
        counts: dict[str, int] = {}
        storage_dir = self.settings.storage_root / "runs" / sanitize_filename(manifest.run_id)
        raw_dir = storage_dir / "raw"
        storage_dir.mkdir(parents=True, exist_ok=True)
        if raw_dir.exists():
            shutil.rmtree(raw_dir)
        shutil.copytree(prepared.folder, raw_dir)
        if original_zip:
            shutil.copy2(original_zip, storage_dir / "original.zip")

        try:
            workspace, user = self._ensure_local_user()
            run = BacktestRun(
                workspace_id=workspace.id,
                user_id=user.id,
                run_id=manifest.run_id,
                title=manifest.title,
                strategy_name=manifest.strategy_name,
                strategy_version=manifest.strategy_version,
                strategy_family=manifest.strategy_family,
                exchange=manifest.exchange,
                market_type=manifest.market_type,
                base_currency=manifest.base_currency,
                initial_capital=manifest.initial_capital,
                timeframe=manifest.timeframe,
                start_time=parse_datetime(manifest.start_time),
                end_time=parse_datetime(manifest.end_time),
                created_by=manifest.created_by,
                data_source=manifest.data_source,
                data_version=manifest.data_version,
                code_version=manifest.code_version,
                schema_version=manifest.schema_version,
                status="active",
                tags=manifest.tags,
                notes=manifest.notes,
                config_hash=prepared.report.config_hash,
                result_hash=prepared.report.result_hash,
            )
            self.db.add(run)
            self.db.flush()
            self.db.add(
                BacktestConfig(
                    run_id=manifest.run_id,
                    config_json=config_json,
                    config_hash=prepared.report.config_hash or sha256_json(config_json),
                    raw_file_path=str(raw_dir / "config.json"),
                )
            )
            counts["metrics"] = self._insert_metrics(manifest.run_id, metrics_json)
            counts["equity"] = self._insert_equity(manifest.run_id, prepared.files.get("equity_curve.csv"), record_start)
            counts["trades"] = self._insert_trades(manifest.run_id, prepared.files.get("trades.csv"), record_start)
            counts["orders"] = self._insert_orders(manifest.run_id, prepared.files.get("orders.csv"), record_start)
            counts["fills"] = self._insert_fills(manifest.run_id, prepared.files.get("fills.csv"), record_start)
            counts["positions"] = self._insert_positions(manifest.run_id, prepared.files.get("positions.csv"), record_start)
            counts["symbols"] = self._insert_symbols(manifest.run_id, prepared.files.get("symbol_summary.csv"))
            if counts["symbols"] == 0 and counts["trades"] > 0:
                counts["symbols"] = self._derive_symbol_summary(manifest.run_id)
            counts["costs"] = self._insert_costs(manifest.run_id, prepared.files.get("cost_summary.csv"), metrics_json, manifest.base_currency)
            counts["candidates"] = self._insert_candidates(manifest.run_id, prepared.files.get("candidate_snapshot.csv"), record_start)
            counts["files"] = self._insert_import_files(manifest.run_id, prepared, raw_dir)
            counts["notes"] = self._insert_notes(manifest.run_id, prepared.files.get("notes.md"), manifest.notes)
            counts["attachments"] = self._insert_attachments(manifest.run_id, prepared.folder, raw_dir)
            for tag in manifest.tags:
                self.db.add(RunTag(run_id=manifest.run_id, tag=tag))
            self.db.add(
                AuditLog(
                    actor=self.settings.default_user_email,
                    action="import_backtest",
                    target_type="backtest_run",
                    target_id=manifest.run_id,
                    details_json={"counts": counts, "record_start_at": record_start.isoformat()},
                )
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return ImportResult(ok=True, run_id=manifest.run_id, validation=prepared.report, imported_counts=counts)

    def _insert_metrics(self, run_id: str, metrics_json: dict[str, Any]) -> int:
        count = 0
        for key, value in metrics_json.items():
            numeric_value = None
            text_value = None
            try:
                if isinstance(value, bool):
                    text_value = str(value).lower()
                else:
                    numeric_value = parse_decimal(value)
            except Exception:
                text_value = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
            self.db.add(
                BacktestMetric(
                    run_id=run_id,
                    metric_key=key,
                    metric_value_numeric=numeric_value,
                    metric_value_text=text_value,
                    metric_category="general",
                )
            )
            count += 1
        return count

    def _insert_equity(self, run_id: str, path: Path | None, record_start: datetime) -> int:
        if not path:
            return 0
        rows: list[EquityPoint] = []
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for index, row in enumerate(csv.DictReader(handle), start=1):
                try:
                    timestamp = parse_datetime(row.get("timestamp"))
                    equity = parse_decimal(row.get("equity"))
                    if not is_after_record_start(timestamp, record_start):
                        self._record_row_issue(
                            run_id,
                            "equity_curve.csv",
                            index + 1,
                            "outside_record_window",
                            "timestamp 無法確認為紀錄起點之後，未寫入 equity_points 核心表。",
                            row,
                        )
                        continue
                    if timestamp is None or equity is None:
                        continue
                    rows.append(
                        EquityPoint(
                            run_id=run_id,
                            timestamp=timestamp,
                            equity=equity,
                            cash=parse_decimal(row.get("cash")),
                            position_value=parse_decimal(row.get("position_value")),
                            unrealized_pnl=parse_decimal(row.get("unrealized_pnl")),
                            realized_pnl=parse_decimal(row.get("realized_pnl")),
                            drawdown=parse_decimal(row.get("drawdown")),
                            exposure=parse_decimal(row.get("exposure")),
                            leverage=parse_decimal(row.get("leverage")),
                        )
                    )
                    if len(rows) >= 5000:
                        self.db.add_all(rows)
                        self.db.flush()
                        rows.clear()
                except Exception:
                    self._record_row_issue(
                        run_id,
                        "equity_curve.csv",
                        index + 1,
                        "row_parse_error",
                        "equity_curve.csv 資料列無法解析，原始列已保留於匯入檔。",
                        row,
                    )
                    continue
        if rows:
            self.db.add_all(rows)
        return self.db.scalar(select(func.count()).select_from(EquityPoint).where(EquityPoint.run_id == run_id)) or len(rows)

    def _insert_trades(self, run_id: str, path: Path | None, record_start: datetime) -> int:
        if not path:
            return 0
        count = 0
        batch: list[Trade] = []
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for index, row in enumerate(csv.DictReader(handle), start=1):
                warnings: list[dict[str, str]] = []
                entry_time = tolerant(parse_datetime, row.get("entry_time"), "entry_time", warnings) if row.get("entry_time") else None
                if not is_after_record_start(entry_time, record_start):
                    self._record_row_issue(
                        run_id,
                        "trades.csv",
                        index + 1,
                        "outside_record_window",
                        "entry_time 無法確認為紀錄起點之後，未寫入 trades 核心表。",
                        row,
                    )
                    continue
                exit_time = tolerant(parse_datetime, row.get("exit_time"), "exit_time", warnings) if row.get("exit_time") else None
                trade_id = row.get("trade_id") or f"{run_id}_trade_{index:08d}"
                known = {
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
                }
                batch.append(
                    Trade(
                        run_id=run_id,
                        trade_id=trade_id,
                        symbol=(row.get("symbol") or "").strip() or None,
                        side=(row.get("side") or "").strip().lower() or None,
                        entry_time=entry_time,
                        exit_time=exit_time,
                        entry_price=tolerant(parse_decimal, row.get("entry_price"), "entry_price", warnings),
                        exit_price=tolerant(parse_decimal, row.get("exit_price"), "exit_price", warnings),
                        qty=tolerant(parse_decimal, row.get("qty"), "qty", warnings),
                        notional=tolerant(parse_decimal, row.get("notional"), "notional", warnings),
                        gross_pnl=tolerant(parse_decimal, row.get("gross_pnl"), "gross_pnl", warnings),
                        fee=tolerant(parse_decimal, row.get("fee"), "fee", warnings),
                        slippage=tolerant(parse_decimal, row.get("slippage"), "slippage", warnings),
                        funding=tolerant(parse_decimal, row.get("funding"), "funding", warnings),
                        net_pnl=tolerant(parse_decimal, row.get("net_pnl"), "net_pnl", warnings),
                        return_pct=tolerant(parse_decimal, row.get("return_pct"), "return_pct", warnings),
                        holding_minutes=tolerant(parse_decimal, row.get("holding_minutes"), "holding_minutes", warnings),
                        exit_reason=(row.get("exit_reason") or "").strip() or None,
                        raw_row_json=dict(row),
                        parse_warnings=warnings or None,
                        metadata_json={k: v for k, v in row.items() if k not in known and v not in (None, "")} or None,
                    )
                )
                count += 1
                if len(batch) >= 5000:
                    self.db.add_all(batch)
                    self.db.flush()
                    batch.clear()
        if batch:
            self.db.add_all(batch)
        return count

    def _insert_orders(self, run_id: str, path: Path | None, record_start: datetime) -> int:
        if not path:
            return 0
        count = 0
        batch: list[OrderRecord] = []
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for index, row in enumerate(csv.DictReader(handle), start=1):
                warnings: list[dict[str, str]] = []
                order_time = tolerant(parse_datetime, first_value(row, "order_time", "created_at", "submitted_at", "timestamp"), "order_time", warnings)
                if not is_after_record_start(order_time, record_start):
                    self._record_row_issue(
                        run_id,
                        "orders.csv",
                        index + 1,
                        "outside_record_window",
                        "order_time 無法確認為紀錄起點之後，未寫入 orders 核心表。",
                        row,
                    )
                    continue
                order_id = first_value(row, "order_id", "client_order_id", "id") or f"{run_id}_order_{index:08d}"
                known = {
                    "order_id",
                    "client_order_id",
                    "id",
                    "trade_id",
                    "symbol",
                    "side",
                    "order_type",
                    "type",
                    "order_time",
                    "created_at",
                    "submitted_at",
                    "timestamp",
                    "status",
                    "price",
                    "qty",
                    "filled_qty",
                    "reduce_only",
                    "position_effect",
                    "effect",
                    "position_action",
                    "action",
                    "open_close",
                    "parent_order_id",
                }
                batch.append(
                    OrderRecord(
                        run_id=run_id,
                        order_id=str(order_id),
                        trade_id=(row.get("trade_id") or "").strip() or None,
                        symbol=(row.get("symbol") or "").strip() or None,
                        side=(row.get("side") or "").strip().lower() or None,
                        order_type=(first_value(row, "order_type", "type") or "").strip() or None,
                        order_time=order_time,
                        status=(row.get("status") or "").strip() or None,
                        price=tolerant(parse_decimal, row.get("price"), "price", warnings),
                        qty=tolerant(parse_decimal, row.get("qty"), "qty", warnings),
                        filled_qty=tolerant(parse_decimal, row.get("filled_qty"), "filled_qty", warnings),
                        reduce_only=tolerant(parse_bool, row.get("reduce_only"), "reduce_only", warnings) if row.get("reduce_only") else None,
                        position_effect=normalize_position_effect(row),
                        parent_order_id=(row.get("parent_order_id") or "").strip() or None,
                        raw_row_json=dict(row),
                        parse_warnings=warnings or None,
                        metadata_json={k: v for k, v in row.items() if k not in known and v not in (None, "")} or None,
                    )
                )
                count += 1
                if len(batch) >= 5000:
                    self.db.add_all(batch)
                    self.db.flush()
                    batch.clear()
        if batch:
            self.db.add_all(batch)
        return count

    def _insert_fills(self, run_id: str, path: Path | None, record_start: datetime) -> int:
        if not path:
            return 0
        count = 0
        batch: list[FillRecord] = []
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for index, row in enumerate(csv.DictReader(handle), start=1):
                warnings: list[dict[str, str]] = []
                fill_time = tolerant(parse_datetime, first_value(row, "fill_time", "timestamp", "created_at"), "fill_time", warnings)
                order_time_raw = first_value(row, "order_time", "order_created_at", "order_submitted_at")
                order_time = tolerant(parse_datetime, order_time_raw, "order_time", warnings) if order_time_raw else None
                if order_time is None:
                    warnings.append(
                        {
                            "field": "order_time",
                            "message": "order_time missing; fill_time used as fallback for the 16:00 record window",
                            "raw_value": "",
                        }
                    )
                record_time = order_time or fill_time
                if not is_after_record_start(record_time, record_start):
                    self._record_row_issue(
                        run_id,
                        "fills.csv",
                        index + 1,
                        "outside_record_window",
                        "order_time/fill_time 無法確認為紀錄起點之後，未寫入 fills 核心表。",
                        row,
                    )
                    continue
                fill_id = first_value(row, "fill_id", "id", "execution_id") or f"{run_id}_fill_{index:08d}"
                known = {
                    "fill_id",
                    "id",
                    "execution_id",
                    "order_id",
                    "trade_id",
                    "symbol",
                    "side",
                    "fill_time",
                    "timestamp",
                    "created_at",
                    "order_time",
                    "order_created_at",
                    "order_submitted_at",
                    "price",
                    "qty",
                    "notional",
                    "fee",
                    "fee_currency",
                    "liquidity",
                    "reduce_only",
                    "position_effect",
                    "effect",
                    "position_action",
                    "action",
                    "open_close",
                    "realized_pnl",
                }
                batch.append(
                    FillRecord(
                        run_id=run_id,
                        fill_id=str(fill_id),
                        order_id=(row.get("order_id") or "").strip() or None,
                        trade_id=(row.get("trade_id") or "").strip() or None,
                        symbol=(row.get("symbol") or "").strip() or None,
                        side=(row.get("side") or "").strip().lower() or None,
                        fill_time=fill_time,
                        price=tolerant(parse_decimal, row.get("price"), "price", warnings),
                        qty=tolerant(parse_decimal, row.get("qty"), "qty", warnings),
                        notional=tolerant(parse_decimal, row.get("notional"), "notional", warnings),
                        fee=tolerant(parse_decimal, row.get("fee"), "fee", warnings),
                        fee_currency=(row.get("fee_currency") or "").strip() or None,
                        liquidity=(row.get("liquidity") or "").strip() or None,
                        reduce_only=tolerant(parse_bool, row.get("reduce_only"), "reduce_only", warnings) if row.get("reduce_only") else None,
                        position_effect=normalize_position_effect(row),
                        realized_pnl=tolerant(parse_decimal, row.get("realized_pnl"), "realized_pnl", warnings),
                        raw_row_json=dict(row),
                        parse_warnings=warnings or None,
                        metadata_json={k: v for k, v in row.items() if k not in known and v not in (None, "")} or None,
                    )
                )
                count += 1
                if len(batch) >= 5000:
                    self.db.add_all(batch)
                    self.db.flush()
                    batch.clear()
        if batch:
            self.db.add_all(batch)
        return count

    def _insert_positions(self, run_id: str, path: Path | None, record_start: datetime) -> int:
        if not path:
            return 0
        count = 0
        batch: list[PositionRecord] = []
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for index, row in enumerate(csv.DictReader(handle), start=1):
                warnings: list[dict[str, str]] = []
                timestamp = tolerant(parse_datetime, first_value(row, "timestamp", "time", "created_at"), "timestamp", warnings)
                if not is_after_record_start(timestamp, record_start):
                    self._record_row_issue(
                        run_id,
                        "positions.csv",
                        index + 1,
                        "outside_record_window",
                        "timestamp 無法確認為紀錄起點之後，未寫入 positions 核心表。",
                        row,
                    )
                    continue
                known = {
                    "position_id",
                    "trade_id",
                    "symbol",
                    "side",
                    "timestamp",
                    "time",
                    "created_at",
                    "qty",
                    "avg_price",
                    "market_price",
                    "notional",
                    "unrealized_pnl",
                    "realized_pnl",
                    "position_effect",
                    "effect",
                    "position_action",
                    "action",
                    "open_close",
                }
                batch.append(
                    PositionRecord(
                        run_id=run_id,
                        position_id=(row.get("position_id") or f"{run_id}_position_{index:08d}").strip() or None,
                        trade_id=(row.get("trade_id") or "").strip() or None,
                        symbol=(row.get("symbol") or "").strip() or None,
                        side=(row.get("side") or "").strip().lower() or None,
                        timestamp=timestamp,
                        qty=tolerant(parse_decimal, row.get("qty"), "qty", warnings),
                        avg_price=tolerant(parse_decimal, row.get("avg_price"), "avg_price", warnings),
                        market_price=tolerant(parse_decimal, row.get("market_price"), "market_price", warnings),
                        notional=tolerant(parse_decimal, row.get("notional"), "notional", warnings),
                        unrealized_pnl=tolerant(parse_decimal, row.get("unrealized_pnl"), "unrealized_pnl", warnings),
                        realized_pnl=tolerant(parse_decimal, row.get("realized_pnl"), "realized_pnl", warnings),
                        position_effect=normalize_position_effect(row),
                        raw_row_json=dict(row),
                        parse_warnings=warnings or None,
                        metadata_json={k: v for k, v in row.items() if k not in known and v not in (None, "")} or None,
                    )
                )
                count += 1
                if len(batch) >= 5000:
                    self.db.add_all(batch)
                    self.db.flush()
                    batch.clear()
        if batch:
            self.db.add_all(batch)
        return count

    def _insert_symbols(self, run_id: str, path: Path | None) -> int:
        if not path:
            return 0
        count = 0
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                try:
                    known = {
                        "symbol",
                        "trade_count",
                        "gross_pnl",
                        "net_pnl",
                        "fee_total",
                        "slippage_total",
                        "funding_total",
                        "win_rate",
                        "avg_return",
                        "max_drawdown",
                        "avg_holding_minutes",
                        "selection_count",
                    }
                    symbol = (row.get("symbol") or "").strip()
                    if not symbol:
                        continue
                    self.db.add(
                        SymbolSummary(
                            run_id=run_id,
                            symbol=symbol,
                            trade_count=parse_int(row.get("trade_count")),
                            gross_pnl=parse_decimal(row.get("gross_pnl")),
                            net_pnl=parse_decimal(row.get("net_pnl")),
                            fee_total=parse_decimal(row.get("fee_total")),
                            slippage_total=parse_decimal(row.get("slippage_total")),
                            funding_total=parse_decimal(row.get("funding_total")),
                            win_rate=parse_decimal(row.get("win_rate")),
                            avg_return=parse_decimal(row.get("avg_return")),
                            max_drawdown=parse_decimal(row.get("max_drawdown")),
                            avg_holding_minutes=parse_decimal(row.get("avg_holding_minutes")),
                            selection_count=parse_int(row.get("selection_count")),
                            metadata_json={k: v for k, v in row.items() if k not in known and v not in (None, "")} or None,
                        )
                    )
                    count += 1
                except Exception:
                    continue
        return count

    def _derive_symbol_summary(self, run_id: str) -> int:
        rows = self.db.execute(
            select(
                Trade.symbol,
                func.count(Trade.id),
                func.sum(Trade.gross_pnl),
                func.sum(Trade.net_pnl),
                func.sum(Trade.fee),
                func.sum(Trade.slippage),
                func.sum(Trade.funding),
                func.avg(Trade.return_pct),
                func.avg(Trade.holding_minutes),
            )
            .where(Trade.run_id == run_id, Trade.symbol.is_not(None))
            .group_by(Trade.symbol)
        ).all()
        for row in rows:
            self.db.add(
                SymbolSummary(
                    run_id=run_id,
                    symbol=row[0],
                    trade_count=row[1],
                    gross_pnl=row[2],
                    net_pnl=row[3],
                    fee_total=row[4],
                    slippage_total=row[5],
                    funding_total=row[6],
                    avg_return=row[7],
                    avg_holding_minutes=row[8],
                )
            )
        return len(rows)

    def _insert_costs(self, run_id: str, path: Path | None, metrics_json: dict[str, Any], base_currency: str | None) -> int:
        count = 0
        if path:
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                for row in csv.DictReader(handle):
                    try:
                        category = (row.get("category") or "").strip()
                        if not category:
                            continue
                        known = {"category", "amount", "currency", "bps", "description"}
                        self.db.add(
                            CostSummary(
                                run_id=run_id,
                                category=category,
                                amount=parse_decimal(row.get("amount")),
                                currency=(row.get("currency") or base_currency or "").strip() or None,
                                bps=parse_decimal(row.get("bps")),
                                description=(row.get("description") or "").strip() or None,
                                metadata_json={k: v for k, v in row.items() if k not in known and v not in (None, "")} or None,
                            )
                        )
                        count += 1
                    except Exception:
                        continue
        if count == 0:
            for key, category in {"fee_total": "fee", "slippage_total": "slippage", "funding_total": "funding"}.items():
                if key in metrics_json:
                    self.db.add(
                        CostSummary(
                            run_id=run_id,
                            category=category,
                            amount=parse_decimal(metrics_json.get(key)),
                            currency=base_currency,
                            description=f"generated from metrics.{key}",
                        )
                    )
                    count += 1
        return count

    def _insert_candidates(self, run_id: str, path: Path | None, record_start: datetime) -> int:
        if not path:
            return 0
        count = 0
        batch: list[CandidateSnapshot] = []
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for index, row in enumerate(csv.DictReader(handle), start=1):
                try:
                    timestamp = parse_datetime(row.get("timestamp"))
                    if not is_after_record_start(timestamp, record_start):
                        self._record_row_issue(
                            run_id,
                            "candidate_snapshot.csv",
                            index + 1,
                            "outside_record_window",
                            "timestamp 無法確認為紀錄起點之後，未寫入 candidate_snapshots 核心表。",
                            row,
                        )
                        continue
                    symbol = (row.get("symbol") or "").strip()
                    if not symbol:
                        continue
                    known = {
                        "timestamp",
                        "symbol",
                        "is_in_universe",
                        "is_candidate",
                        "is_selected",
                        "rank",
                        "score",
                        "blocked_reason",
                        "volume_24h",
                        "spread_bps",
                        "volatility",
                    }
                    batch.append(
                        CandidateSnapshot(
                            run_id=run_id,
                            timestamp=timestamp,
                            symbol=symbol,
                            is_in_universe=parse_bool(row.get("is_in_universe")),
                            is_candidate=parse_bool(row.get("is_candidate")),
                            is_selected=parse_bool(row.get("is_selected")),
                            rank=parse_int(row.get("rank")),
                            score=parse_decimal(row.get("score")),
                            blocked_reason=(row.get("blocked_reason") or "").strip() or None,
                            volume_24h=parse_decimal(row.get("volume_24h")),
                            spread_bps=parse_decimal(row.get("spread_bps")),
                            volatility=parse_decimal(row.get("volatility")),
                            metadata_json={k: v for k, v in row.items() if k not in known and v not in (None, "")} or None,
                        )
                    )
                    count += 1
                    if len(batch) >= 10000:
                        self.db.add_all(batch)
                        self.db.flush()
                        batch.clear()
                except Exception:
                    self._record_row_issue(
                        run_id,
                        "candidate_snapshot.csv",
                        index + 1,
                        "row_parse_error",
                        "candidate_snapshot.csv 資料列無法解析，原始列已保留於匯入檔。",
                        row,
                    )
                    continue
        if batch:
            self.db.add_all(batch)
        return count

    def _record_row_issue(self, run_id: str, file_name: str, row_number: int, issue_code: str, message: str, row: dict[str, Any]) -> None:
        self.db.add(
            ImportRowIssue(
                run_id=run_id,
                file_name=file_name,
                row_number=row_number,
                issue_code=issue_code,
                message=message,
                raw_row_json=dict(row),
            )
        )

    def _insert_import_files(self, run_id: str, prepared: PreparedImport, raw_dir: Path) -> int:
        count = 0
        summary_by_name = {summary.file_name: summary for summary in prepared.report.files}
        for file_name in prepared.files:
            source = raw_dir / file_name
            summary = summary_by_name.get(file_name)
            self.db.add(
                ImportFile(
                    run_id=run_id,
                    file_name=file_name,
                    file_type=FILE_TYPES.get(file_name),
                    file_path=str(source),
                    file_hash=sha256_file(source),
                    row_count=summary.row_count if summary else None,
                    schema_detected={"columns": summary.columns} if summary and summary.columns else None,
                    validation_status=summary.validation_status if summary else "ok",
                    validation_errors=[item.model_dump() for item in (summary.errors + summary.warnings)] if summary else None,
                )
            )
            count += 1
        return count

    def _insert_notes(self, run_id: str, notes_path: Path | None, manifest_notes: str | None) -> int:
        content = ""
        if notes_path:
            content = notes_path.read_text(encoding="utf-8-sig")
        if manifest_notes:
            content = f"{manifest_notes}\n\n{content}".strip()
        if not content.strip():
            return 0
        self.db.add(Note(run_id=run_id, content=content.strip()))
        return 1

    def _insert_attachments(self, run_id: str, folder: Path, raw_dir: Path) -> int:
        attachments_dir = folder / "attachments"
        raw_attachments_dir = raw_dir / "attachments"
        if not attachments_dir.exists() or not attachments_dir.is_dir():
            return 0
        count = 0
        for source in attachments_dir.rglob("*"):
            if not source.is_file():
                continue
            relative = source.relative_to(attachments_dir)
            copied = raw_attachments_dir / relative
            mime_type = mimetypes.guess_type(copied.name)[0]
            self.db.add(
                Attachment(
                    run_id=run_id,
                    file_name=str(relative).replace("\\", "/"),
                    file_path=str(copied),
                    file_hash=sha256_file(copied),
                    file_size=copied.stat().st_size,
                    mime_type=mime_type,
                )
            )
            count += 1
        return count
