"""Single sequential click. Passes on the buggy shop — it hides the race."""

from shop.orders import OrderService


def test_single_click_place_order() -> None:
    service = OrderService()
    first = service.place_order("widget", 10.0, "idem-1")
    second = service.place_order("widget", 10.0, "idem-1")
    assert first.id == second.id
    assert len(service.orders) == 1
    assert len(service.payments) == 1
