from decimal import Decimal

from personal_affairs.application.idempotency import json_safe


def test_json_safe_converts_postgres_decimal_values() -> None:
    assert json_safe({"confidence": Decimal("0.9500")}) == {"confidence": 0.95}
