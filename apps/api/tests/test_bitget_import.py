from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.imports import BitgetImportRequest
from app.services.bitget import BitgetReadOnlyClient


class RecordingBitgetClient(BitgetReadOnlyClient):
    def __init__(self, responses: list[dict]):
        self.responses = responses
        self.calls: list[tuple[str, dict]] = []

    def get(self, request_path: str, params: dict):
        self.calls.append((request_path, params))
        return self.responses.pop(0)


def utc(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, tzinfo=timezone.utc)


def test_history_orders_uses_contract_orders_history_endpoint_and_paginates():
    client = RecordingBitgetClient(
        [
            {"code": "00000", "data": {"entrustedList": [{"orderId": "a"}], "endId": "a"}},
            {"code": "00000", "data": {"entrustedList": [{"orderId": "b"}], "endId": "b"}},
            {"code": "00000", "data": {"entrustedList": [], "endId": "b"}},
        ]
    )

    rows = client.iter_history_orders(
        product_type="USDT-FUTURES",
        symbol="BTCUSDT",
        start_time=utc(2026, 5, 7),
        end_time=utc(2026, 5, 8),
        max_pages=3,
    )

    assert rows == [{"orderId": "a"}, {"orderId": "b"}]
    assert client.calls[0][0] == "/api/v2/mix/order/orders-history"
    assert client.calls[0][1]["productType"] == "USDT-FUTURES"
    assert client.calls[0][1]["symbol"] == "BTCUSDT"
    assert client.calls[1][1]["idLessThan"] == "a"


def test_fill_history_uses_private_contract_order_fills_endpoint():
    client = RecordingBitgetClient(
        [
            {"code": "00000", "data": {"fillList": [{"tradeId": "t1"}], "endId": "t1"}},
            {"code": "00000", "data": {"fillList": [], "endId": None}},
            {"code": "00000", "data": {"fillList": [{"tradeId": "t2"}], "endId": None}},
        ]
    )

    rows = client.iter_fill_history(
        product_type="USDT-FUTURES",
        start_time=utc(2026, 5, 7),
        end_time=utc(2026, 5, 16),
        max_pages=2,
    )

    assert rows == [{"tradeId": "t1"}, {"tradeId": "t2"}]
    assert {call[0] for call in client.calls} == {"/api/v2/mix/order/fills"}
    assert client.calls[0][1]["productType"] == "USDT-FUTURES"
    assert client.calls[0][1]["endTime"] - client.calls[0][1]["startTime"] == 7 * 24 * 60 * 60 * 1000
    assert client.calls[2][1]["startTime"] == client.calls[0][1]["endTime"]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("usdt-futures", "USDT-FUTURES"),
        ("合約", "USDT-FUTURES"),
        ("幣本位", "COIN-FUTURES"),
        ("USDC-FUTURES", "USDC-FUTURES"),
    ],
)
def test_bitget_import_request_normalizes_contract_product_type(value: str, expected: str):
    payload = BitgetImportRequest(
        run_id="bitget_test",
        product_type=value,
        start_time=datetime.fromisoformat("2026-05-07T18:30:00+08:00"),
        end_time=datetime.fromisoformat("2026-05-07T19:30:00+08:00"),
    )

    assert payload.product_type == expected


def test_bitget_import_request_rejects_spot_product_type():
    with pytest.raises(ValidationError):
        BitgetImportRequest(
            run_id="bitget_test",
            product_type="spot",
            start_time=datetime.fromisoformat("2026-05-07T18:30:00+08:00"),
            end_time=datetime.fromisoformat("2026-05-07T19:30:00+08:00"),
        )
