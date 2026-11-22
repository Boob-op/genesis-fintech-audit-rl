"""Exact TP/FP/FN and F1 edge cases."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Metrics:
    tp: int
    fp: int
    fn: int
    precision: Decimal
    recall: Decimal
    f1: Decimal


def metrics(tp: int, submitted: int, expected: int) -> Metrics:
    if any(type(value) is not int or value < 0 for value in (tp, submitted, expected)):
        raise ValueError("counts must be nonnegative integers")
    if tp > min(submitted, expected):
        raise ValueError("TP exceeds submitted or expected count")
    fp, fn = submitted - tp, expected - tp
    precision = Decimal(tp) / submitted if submitted else Decimal(0)
    recall = Decimal(tp) / expected if expected else Decimal(0)
    if submitted == expected == 0:
        f1 = Decimal(1)
    else:
        denominator = 2 * tp + fp + fn
        f1 = Decimal(2 * tp) / denominator if denominator else Decimal(0)
    return Metrics(tp, fp, fn, precision, recall, f1)
