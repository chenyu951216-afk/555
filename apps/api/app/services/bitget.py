from __future__ import annotations

import base64
import hashlib
import hmac
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

import httpx

from app.core.config import Settings
from app.services.importer import parse_bool, parse_datetime


class BitgetReadOnlyClient:
    """Read-only Bitget REST client for importing historical records.

    This client intentionally implements only GET endpoints used for record keeping.
    It does not include any place/modify/cancel order methods.
    """

    def __init__(self, settings: Settings):
        if not settings.bitget_api_key or not settings.bitget_api_secret or not settings.bitget_api_passphrase:
            raise ValueError("後端尚未讀到 Bitget API 金鑰、密鑰或通行短語")
        self.base_url = settings.bitget_api_base_url.rstrip("/")
        self.api_key = settings.bitget_api_key
        self.api_secret = settings.bitget_api_secret
        self.passphrase = settings.bitget_api_passphrase
        self.locale = settings.bitget_locale

    def _sign(self, timestamp_ms: str, method: str, request_path: str, query_string: str = "", body: str = "") -> str:
        path_with_query = request_path if not query_string else f"{request_path}?{query_string}"
        payload = f"{timestamp_ms}{method.upper()}{path_with_query}{body}"
        digest = hmac.new(self.api_secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).digest()
        return base64.b64encode(digest).decode("utf-8")

    def _headers(self, method: str, request_path: str, query_string: str = "", body: str = "") -> dict[str, str]:
        timestamp_ms = str(int(time.time() * 1000))
        return {
            "ACCESS-KEY": self.api_key,
            "ACCESS-SIGN": self._sign(timestamp_ms, method, request_path, query_string, body),
            "ACCESS-TIMESTAMP": timestamp_ms,
            "ACCESS-PASSPHRASE": self.passphrase,
            "Content-Type": "application/json",
            "locale": self.locale,
        }

    def get(self, request_path: str, params: dict[str, Any]) -> dict[str, Any]:
        clean_params = {key: value for key, value in params.items() if value not in (None, "", [])}
        query_string = urlencode(clean_params)
        headers = self._headers("GET", request_path, query_string=query_string)
        with httpx.Client(timeout=30) as client:
            response = client.get(f"{self.base_url}{request_path}", params=clean_params, headers=headers)
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != "00000":
            raise ValueError(f"Bitget API 錯誤：{payload.get('code')} {payload.get('msg')}")
        return payload

    def iter_history_orders(
        self,
        product_type: str,
        start_time: datetime,
        end_time: datetime,
        symbol: str | None = None,
        max_pages: int = 10,
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        id_less_than: str | None = None
        for _ in range(max_pages):
            payload = self.get(
                "/api/v2/mix/order/orders-history",
                {
                    "productType": product_type,
                    "symbol": symbol,
                    "startTime": int(start_time.timestamp() * 1000),
                    "endTime": int(end_time.timestamp() * 1000),
                    "limit": "100",
                    "idLessThan": id_less_than,
                },
            )
            data = payload.get("data") or {}
            batch = data.get("entrustedList") or []
            items.extend(batch)
            next_id = data.get("endId")
            if not batch or not next_id or next_id == id_less_than:
                break
            id_less_than = next_id
        return items

    def iter_fill_history(
        self,
        product_type: str,
        start_time: datetime,
        end_time: datetime,
        symbol: str | None = None,
        max_pages: int = 10,
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        window_start = start_time
        while window_start < end_time:
            window_end = min(window_start + timedelta(days=7), end_time)
            id_less_than: str | None = None
            for _ in range(max_pages):
                payload = self.get(
                    "/api/v2/mix/order/fills",
                    {
                        "productType": product_type,
                        "symbol": symbol,
                        "startTime": int(window_start.timestamp() * 1000),
                        "endTime": int(window_end.timestamp() * 1000),
                        "limit": "100",
                        "idLessThan": id_less_than,
                    },
                )
                data = payload.get("data") or {}
                batch = data.get("fillList") or []
                items.extend(batch)
                next_id = data.get("endId")
                if not batch or not next_id or next_id == id_less_than:
                    break
                id_less_than = next_id
            window_start = window_end
        return items


def ms_to_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
    except Exception:
        return parse_datetime(value)


def decimal_or_none(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    return Decimal(str(value))


def bitget_reduce_only(value: Any) -> bool | None:
    if value in (None, ""):
        return None
    if str(value).upper() == "YES":
        return True
    if str(value).upper() == "NO":
        return False
    return parse_bool(value)


def bitget_position_effect(row: dict[str, Any]) -> str | None:
    trade_side = str(row.get("tradeSide") or "").lower()
    order_source = str(row.get("orderSource") or "").lower()
    reduce_only = bitget_reduce_only(row.get("reduceOnly"))
    if "profit" in order_source:
        return "partial_take_profit"
    if "loss" in order_source:
        return "stop_loss"
    if "close" in order_source:
        return "close"
    if trade_side == "open":
        return "open"
    if trade_side == "close":
        return "close"
    if trade_side.startswith("reduce") or "reduce" in trade_side or "offset_close" in trade_side:
        return "reduce"
    if "close" in trade_side:
        return "close"
    if reduce_only is True:
        return "reduce"
    if trade_side in {"buy_single", "sell_single"}:
        return "open"
    return trade_side or None
