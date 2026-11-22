"""Common terminal reward from the organizer's formula."""

from decimal import Decimal


def terminal_reward(f1: Decimal, inspection_steps: int) -> Decimal:
    if type(inspection_steps) is not int or not 0 <= inspection_steps <= 100:
        raise ValueError("inspection_steps outside contract")
    if not Decimal(0) <= f1 <= Decimal(1):
        raise ValueError("F1 outside [0,1]")
    raw = Decimal(2) * f1 - 1 - Decimal("0.002") * inspection_steps
    return max(Decimal(-1), min(Decimal(1), raw))
