from datetime import datetime
from decimal import Decimal
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field


T = TypeVar("T")


class ApiError(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int = Field(ge=1, le=5000)
    offset: int = Field(ge=0)


class ValidationIssue(BaseModel):
    level: str
    code: str
    message: str
    file_name: str | None = None
    row: int | None = None
    field: str | None = None


class FileValidationSummary(BaseModel):
    file_name: str
    file_type: str | None = None
    file_hash: str | None = None
    row_count: int | None = None
    columns: list[str] = Field(default_factory=list)
    validation_status: str = "ok"
    errors: list[ValidationIssue] = Field(default_factory=list)
    warnings: list[ValidationIssue] = Field(default_factory=list)
    skipped_rows: int = 0


class ValidationReport(BaseModel):
    ok: bool
    run_id: str | None = None
    record_start_at: datetime | None = None
    errors: list[ValidationIssue] = Field(default_factory=list)
    warnings: list[ValidationIssue] = Field(default_factory=list)
    files: list[FileValidationSummary] = Field(default_factory=list)
    result_hash: str | None = None
    config_hash: str | None = None


class ImportResult(BaseModel):
    ok: bool
    run_id: str
    validation: ValidationReport
    imported_counts: dict[str, int]


class DecimalModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, json_encoders={Decimal: lambda v: float(v)})

