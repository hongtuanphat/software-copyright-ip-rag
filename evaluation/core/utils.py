"""Utilities for evaluation validation."""
from typing import Any

def get_expected_behavior(req: dict[str, Any]) -> str | None:
    value = req.get("expected_behavior")
    if value is None:
        return None
    value = str(value).strip().lower()
    if value in {"answer", "refuse"}:
        return value
    return None

def is_out_of_scope(req: dict[str, Any]) -> bool | None:
    behavior = get_expected_behavior(req)
    if behavior is None:
        return None
    return behavior == "refuse"

def get_refused(res: dict[str, Any]) -> bool | None:
    value = res.get("refused")
    if isinstance(value, bool):
        return value
    return None
