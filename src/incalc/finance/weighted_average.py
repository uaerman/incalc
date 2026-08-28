"""Weighted average calculations for purchase cost and maturity."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CostResult:
    total_quantity: float
    total_cost: float
    average_cost: float


@dataclass(frozen=True)
class MaturityResult:
    total_amount: float
    average_days: float


def average_cost(entries: list[tuple[float, float]]) -> CostResult:
    if not entries or any(quantity <= 0 or price < 0 for quantity, price in entries):
        raise ValueError("each quantity must be positive and each price non-negative")
    total_quantity = sum(quantity for quantity, _ in entries)
    total_cost = sum(quantity * price for quantity, price in entries)
    return CostResult(total_quantity, total_cost, total_cost / total_quantity)


def average_maturity(entries: list[tuple[float, float]]) -> MaturityResult:
    if not entries or any(amount <= 0 or days < 0 for amount, days in entries):
        raise ValueError("each amount must be positive and days cannot be negative")
    total_amount = sum(amount for amount, _ in entries)
    return MaturityResult(total_amount, sum(amount * days for amount, days in entries) / total_amount)
