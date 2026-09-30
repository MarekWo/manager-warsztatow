"""Moving a row up or down a list (buttons instead of drag and drop: keyboard-friendly)."""

from typing import Any

from django.db import transaction


def move(items: list[Any], pk: int, direction: str) -> bool:
    """Swap the row `pk` with its neighbour and renumber `order`; False if `pk` is not listed."""
    index = next((i for i, item in enumerate(items) if item.pk == pk), None)
    if index is None:
        return False
    other = index - 1 if direction == "up" else index + 1
    if 0 <= other < len(items):
        items[index], items[other] = items[other], items[index]
        with transaction.atomic():
            for order, item in enumerate(items):
                if item.order != order:
                    item.order = order
                    item.save(update_fields=["order"])
    return True
