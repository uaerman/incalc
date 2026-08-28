"""Profit, margin, and markup calculations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Result:
    unit_profit: float
    total_cost: float
    total_revenue: float
    total_profit: float
    profit_margin: float
    markup: float


def calculate(*, unit_cost: float, unit_price: float, quantity: float) -> Result:
    if unit_cost <= 0:
        raise ValueError("unit cost must be positive")
    if unit_price <= 0:
        raise ValueError("sale price must be positive")
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    unit_profit = unit_price - unit_cost
    total_cost = unit_cost * quantity
    total_revenue = unit_price * quantity
    total_profit = unit_profit * quantity
    return Result(unit_profit, total_cost, total_revenue, total_profit,
                  unit_profit / unit_price * 100, unit_profit / unit_cost * 100)
