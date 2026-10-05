"""Same shop with a lock around check-and-create."""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass


@dataclass
class Order:
    id: str
    item: str
    amount: float
    idempotency_key: str


class OrderService:
    def __init__(self) -> None:
        self.orders: list[Order] = []
        self.payments: list[dict] = []
        self._by_key: dict[str, Order] = {}
        self._lock = threading.Lock()

    def place_order(self, item: str, amount: float, idempotency_key: str) -> Order:
        with self._lock:
            existing = self._by_key.get(idempotency_key)
            if existing is not None:
                return existing
            time.sleep(0.02)
            order = Order(
                id=str(uuid.uuid4()),
                item=item,
                amount=amount,
                idempotency_key=idempotency_key,
            )
            self.orders.append(order)
            self.payments.append({"order_id": order.id, "amount": amount})
            self._by_key[idempotency_key] = order
            return order
