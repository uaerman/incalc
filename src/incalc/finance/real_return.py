"""After-tax returns adjusted for inflation using the Fisher equation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Result:
    net_nominal_return: float
    real_return: float


def calculate(*, nominal_return: float, inflation: float, tax: float = 0) -> Result:
    if inflation <= -100:
        raise ValueError("inflation must be greater than -100")
    if not 0 <= tax < 100:
        raise ValueError("tax must be between 0 and 100")
    net_nominal = nominal_return * (1 - tax / 100)
    real = (1 + net_nominal / 100) / (1 + inflation / 100) * 100 - 100
    return Result(net_nominal, real)
