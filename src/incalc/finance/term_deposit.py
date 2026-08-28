"""TL term-deposit interest and maturity comparisons."""

from __future__ import annotations

from dataclasses import dataclass


COMPARISON_TERMS = (32, 46, 92, 181, 365, 366)


@dataclass(frozen=True)
class Result:
    gross_interest: float
    withholding_rate: float
    withholding: float
    net_interest: float
    maturity_balance: float


def withholding_rate(days: int) -> float:
    """TL deposit withholding schedule effective for accounts opened from 2025-07-09."""
    if days <= 0:
        raise ValueError("term must be at least one day")
    if days <= 180:
        return 17.5
    if days <= 365:
        return 15
    return 10


def calculate(*, principal: float, annual_rate: float, days: int) -> Result:
    if principal <= 0:
        raise ValueError("principal must be positive")
    if annual_rate < 0:
        raise ValueError("annual rate cannot be negative")
    tax_rate = withholding_rate(days)
    gross = principal * annual_rate / 100 * days / 365
    withholding = gross * tax_rate / 100
    net = gross - withholding
    return Result(gross, tax_rate, withholding, net, principal + net)
