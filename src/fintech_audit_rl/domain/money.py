"""Exact event-level currency conversion."""

from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation


def convert_minor(source_minor: int, rate: str, source_exponent: int, target_exponent: int) -> int:
    if type(source_minor) is not int or source_minor < 0:
        raise ValueError("source_minor must be a nonnegative integer")
    if type(source_exponent) is not int or type(target_exponent) is not int:
        raise ValueError("currency exponents must be integers")
    if not 0 <= source_exponent <= 3 or not 0 <= target_exponent <= 3:
        raise ValueError("unsupported currency exponent")
    if type(rate) is not str:
        raise ValueError("rate must be a decimal string")
    try:
        parsed = Decimal(rate)
    except InvalidOperation as error:
        raise ValueError("invalid FX rate") from error
    if not parsed.is_finite() or parsed <= 0:
        raise ValueError("FX rate must be positive and finite")
    value = Decimal(source_minor) * parsed * Decimal(10) ** (target_exponent - source_exponent)
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_EVEN))
