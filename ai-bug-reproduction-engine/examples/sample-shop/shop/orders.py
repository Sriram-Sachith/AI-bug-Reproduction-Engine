"""In-memory shop with a seeded TOCTOU bug on idempotency keys."""

from __future__ import annotations

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
    """place_order checks the key, then creates. Those steps are not atomic."""

    def __init__(self) -> None:
        self.orders: list[Order] = []
        self.payments: list[dict] = []
        self._by_key: dict[str, Order] = {}

    def place_order(self, item: str, amount: float, idempotency_key: str) -> Order:
        existing = self._by_key.get(idempotency_key)
        if existing is not None:
            return existing
        # Simulated persistence round-trip that widens the race window.
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
