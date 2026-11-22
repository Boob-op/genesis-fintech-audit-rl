"""Offset-aware period and FX date rules."""

from datetime import datetime

from fintech_audit_rl.schemas.public import policy_timezone


def in_period(instant: datetime, start: datetime, end: datetime) -> bool:
    if any(value.tzinfo is None or value.utcoffset() is None for value in (instant, start, end)):
        raise ValueError("all instants require offsets")
    if start >= end:
        raise ValueError("invalid period")
    return start <= instant < end


def local_fx_date(instant: datetime, timezone: str) -> str:
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("instant requires offset")
    return instant.astimezone(policy_timezone(timezone)).date().isoformat()
