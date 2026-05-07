from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


SUPPORTED_SCHEMA_VERSIONS = {"1.0"}
MARKET_TYPES = {"spot", "perp", "futures", "options", "other"}


class Manifest(BaseModel):
    schema_version: str = "1.0"
    run_id: str = Field(min_length=1, max_length=180)
    title: str | None = None
    strategy_name: str | None = None
    strategy_version: str | None = None
    strategy_family: str | None = None
    exchange: str | None = None
    market_type: Literal["spot", "perp", "futures", "options", "other"] = "other"
    base_currency: str = Field(min_length=1)
    initial_capital: Decimal = Field(gt=0)
    timeframe: str | None = None
    start_time: datetime
    end_time: datetime
    created_by: str | None = None
    data_source: str | None = None
    data_version: str | None = None
    code_version: str | None = None
    tags: list[str] = Field(default_factory=list)
    notes: str | None = None

    model_config = ConfigDict(extra="allow")

    @field_validator("schema_version")
    @classmethod
    def schema_version_supported(cls, value: str) -> str:
        if value not in SUPPORTED_SCHEMA_VERSIONS:
            raise ValueError(f"unsupported schema_version: {value}")
        return value

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        return sorted({tag.strip() for tag in value if tag and tag.strip()})

    @model_validator(mode="after")
    def check_time_range(self) -> "Manifest":
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be earlier than end_time")
        return self


class ValidateOptions(BaseModel):
    record_start_at: datetime | None = None


class RunPatch(BaseModel):
    title: str | None = None
    tags: list[str] | None = None
    notes: str | None = None
    status: str | None = None


class NoteCreate(BaseModel):
    content: str = Field(min_length=1)


class NoteUpdate(BaseModel):
    content: str = Field(min_length=1)


class SafeQueryFilter(BaseModel):
    table: str
    run_id: str | None = None
    columns: list[str] = Field(default_factory=list)
    filters: dict[str, Any] = Field(default_factory=dict)
    sort_by: str | None = None
    sort_dir: Literal["asc", "desc"] = "asc"
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)


class BitgetImportRequest(BaseModel):
    run_id: str = Field(min_length=1, max_length=180)
    title: str | None = None
    product_type: str = "usdt-futures"
    symbols: list[str] = Field(default_factory=list)
    start_time: datetime
    end_time: datetime
    base_currency: str = "USDT"
    max_pages: int = Field(default=10, ge=1, le=100)

    @model_validator(mode="after")
    def check_range(self) -> "BitgetImportRequest":
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be earlier than end_time")
        self.symbols = [symbol.strip().upper() for symbol in self.symbols if symbol.strip()]
        return self

